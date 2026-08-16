import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.db import pool as dbpool
from app.repo import connections as cr, scheduled_posts as sp, notifications as nr, jobs as _jobs
from app.repo import org_settings as os_repo, ledger as led
from app.social import utm
from app.security.img_sign import public_image_url
from app.social import publish as pub

logger = logging.getLogger(__name__)
_MAX_ATTEMPTS = 5
_STALL_TIMEOUT_S = 300  # a publish finishes in seconds; >5 min in 'publishing' = a worker died mid-claim
_warned_missing = False
_warned_missing_reaper = False


def _has_id(entry) -> bool:
    return isinstance(entry, dict) and bool(entry.get("id"))


def _when_now() -> datetime:
    """The worker's 'now' for scheduling follow-up jobs. (The due-post reader uses SQL now(); this is the
    Python equivalent for computing run_after offsets.)"""
    return datetime.now(timezone.utc)


async def _enqueue_metric_polls(org_id: str, post_id: str | None, connection_id: str, provider: str,
                                ext: str) -> None:
    """After a target publishes, schedule performance re-polls at +24h/+72h/+7d. Best-effort: a failure to
    enqueue must NEVER break publishing, and an ad-hoc publish with no ledger post_id is skipped (post_metrics
    requires a post_id)."""
    if not post_id:
        return
    try:
        now = _when_now()
        for n, delay in enumerate((timedelta(hours=24), timedelta(hours=72), timedelta(days=7))):
            await _jobs.enqueue(org_id, "metrics_poll",
                                payload={"post_id": post_id, "connection_id": connection_id,
                                         "provider": provider, "external_post_id": ext},
                                dedup_key=f"mp-{post_id}-{ext}-{n}", run_after=now + delay)
    except Exception:
        logger.exception("publish: failed to enqueue metric polls org=%s post=%s ext=%s",
                         org_id, post_id, ext)


async def run_one(org_id: str, sp_id: str) -> None:
    """Publish one scheduled post exactly once.

    The atomic claim (pending -> publishing) is the primary exactly-once guard: if another
    worker/inline call already owns the row, claim returns None and we return immediately."""
    row = await sp.claim(org_id, sp_id)
    if row is None:
        return  # already claimed/published — never double-post

    result = dict(row.get("result") or {})  # carry forward prior per-target outcomes
    caption = row["caption"]
    post_id = row.get("post_id")
    # Publish outcomes are workspace-relevant (anyone managing the page cares), so notify org-wide
    # (user_id=None) rather than only the scheduler. created_by is available on the row if per-user
    # targeting is ever wanted.
    notify_user = None
    attempts = row["attempts"]  # claim already incremented this
    try:
        jpg_urls = [public_image_url(i, org_id, fmt="jpg") for i in row["image_ids"]]
    except Exception as e:
        # Misconfiguration (no public origin) — fail the post clearly instead of handing Meta an
        # unfetchable URL and silently failing every target.
        result = {t["connection_id"]: {"error": str(e), "status": "permanent"} for t in row["targets"]}
        await sp.finish(org_id, sp_id, "failed", result)
        await nr.create(org_id, None, "publish_failed", "Couldn't publish", str(e),
                        link=f"/workspace?post={row.get('post_id') or ''}")
        return

    utm_on = await os_repo.utm_tagging(org_id)   # opt-in: tag outbound links so the org can attribute traffic

    for target in row["targets"]:
        cid = target["connection_id"]
        provider = target["provider"]
        if _has_id(result.get(cid)):
            continue  # already succeeded on a prior attempt — never re-publish

        try:
            conn = await cr.get_connection(org_id, cid)
            if conn is None:
                raise pub.PublishPermanentError("connection no longer exists")
            target_id = conn["external_id"]
            token = await cr.get_token(org_id, cid)
            if not token:
                raise pub.PublishAuthError("missing access token")
            cap = utm.tag_links(caption, provider) if utm_on else caption
            res = await pub.publish_to_target(provider, target_id, token, cap, jpg_urls)
            result[cid] = {"id": res["id"], "permalink": res.get("permalink", ""), "status": "ok"}
            # Schedule performance re-polls for this freshly-published target (best-effort; never breaks
            # publishing). Done per-target inside the loop so each id is enqueued exactly once, never again
            # on a later retry of a different target.
            await _enqueue_metric_polls(org_id, post_id, cid, provider, res["id"])
        except pub.PublishTransientError as e:
            result[cid] = {"error": str(e), "status": "transient"}
        except pub.PublishAuthError as e:
            await cr.set_status(org_id, cid, "needs_reconnect")
            result[cid] = {"error": str(e), "status": "auth"}
        except pub.PublishPermanentError as e:
            result[cid] = {"error": str(e), "status": "permanent"}
        except Exception as e:  # unexpected — treat as permanent so we don't retry forever
            logger.exception("publish: unexpected error org=%s sp=%s cid=%s", org_id, sp_id, cid)
            result[cid] = {"error": str(e), "status": "permanent"}

    has_unresolved_transient = any(
        v.get("status") == "transient" for v in result.values() if isinstance(v, dict)
    )
    any_success = any(_has_id(v) for v in result.values())

    if has_unresolved_transient and attempts < _MAX_ATTEMPTS:
        # Back to pending; the loop will retry. No notification on a non-terminal state.
        await sp.requeue(org_id, sp_id, result)
        return

    status = "published" if any_success else "failed"
    await sp.finish(org_id, sp_id, status, result)

    # Reflect the live publish on the ledger post too: scheduled_posts going 'published' isn't enough —
    # the Posts list / status funnel / 'published' insight read post.status, so without this a published
    # post still shows as 'drafted'. Best-effort: a status-flip failure must never undo a real publish.
    if any_success and post_id:
        try:
            await led.mark_posted(org_id, post_id)
        except Exception:
            logger.exception("publish: failed to mark post posted org=%s post=%s", org_id, post_id)

    # Notifications only on terminal states (published/failed).
    if any_success:
        permalink = next(
            (v.get("permalink") for v in result.values() if _has_id(v) and v.get("permalink")),
            None,
        )
        k = sum(1 for v in result.values() if _has_id(v))
        await nr.create(org_id, notify_user, "publish_ok", "Post published ✓",
                        f"Live on {k} account(s).", link=permalink)

    # Include exhausted transients: at this point the requeue branch was skipped (attempts maxed), so a
    # remaining "transient" is genuinely terminal — surface it instead of failing silently.
    errors = [
        v["error"] for v in result.values()
        if isinstance(v, dict) and v.get("status") in ("permanent", "auth", "transient") and v.get("error")
    ]
    if errors:
        await nr.create(org_id, notify_user, "publish_failed", "Couldn't publish",
                        "; ".join(errors), link=f"/workspace?post={post_id or ''}")


async def _due_posts(limit: int = 20) -> list[tuple[str, str]]:
    """Cross-org (org_id, scheduled_post_id) pairs due to publish, via the platform-owned SECURITY
    DEFINER function (bypasses RLS, ids only). Returns [] if the function isn't installed (setup not
    run) or on any error — the scheduler must never crash startup."""
    global _warned_missing
    if dbpool._pool is None:
        return []
    try:
        async with dbpool._pool.acquire() as c:
            rows = await c.fetch("SELECT org_id, scheduled_post_id FROM sched_due_posts($1)", limit)
        return [(str(r["org_id"]), str(r["scheduled_post_id"])) for r in rows]
    except Exception as e:
        if not _warned_missing:
            logger.warning("publish worker: sched_due_posts unavailable (%s); scheduled publishing "
                           "disabled until scripts/setup_publish_fn.sql is applied as the platform "
                           "superuser", e)
            _warned_missing = True
        return []


async def _stale_publishing(timeout_s: int = _STALL_TIMEOUT_S, limit: int = 20) -> list[tuple[str, str]]:
    """Cross-org (org_id, scheduled_post_id) pairs STUCK in 'publishing' past the stall timeout, via the
    platform-owned SECURITY DEFINER reader. Returns [] (and warns once) if the function isn't installed."""
    global _warned_missing_reaper
    if dbpool._pool is None:
        return []
    try:
        async with dbpool._pool.acquire() as c:
            rows = await c.fetch(
                "SELECT org_id, scheduled_post_id FROM sched_stale_publishing($1, $2)", timeout_s, limit)
        return [(str(r["org_id"]), str(r["scheduled_post_id"])) for r in rows]
    except Exception as e:
        if not _warned_missing_reaper:
            logger.warning("publish worker: sched_stale_publishing unavailable (%s); the stuck-post reaper "
                           "is disabled until scripts/setup_publish_fn.sql is applied as the platform "
                           "superuser", e)
            _warned_missing_reaper = True
        return []


async def reap_stale() -> int:
    """Recover posts stuck in 'publishing' (worker died mid-publish): requeue them (or fail after max
    attempts). Requeued posts become due again and republish only their unfinished targets."""
    n = 0
    for org_id, sp_id in await _stale_publishing():
        try:
            new_status = await sp.reap(org_id, sp_id, _MAX_ATTEMPTS)
            if new_status:
                n += 1
                logger.warning("reaper: recovered stuck post org=%s sp=%s -> %s", org_id, sp_id, new_status)
                # A post the reaper gives up on used to die silently — tell the user, like the normal
                # publish-failure path does, so a stuck post never just vanishes.
                if new_status == "failed":
                    await nr.create(org_id, None, "publish_failed", "A scheduled post failed to publish",
                                    "It was retried several times and didn't go through — open Workspace to "
                                    "review and try again.", link="/workspace")
        except Exception:
            logger.exception("reaper: failed to reap org=%s sp=%s", org_id, sp_id)
    return n


async def tick() -> int:
    """One pass: reap stuck posts first (so requeued ones republish this pass), then publish each due post."""
    await reap_stale()
    due = await _due_posts()
    n = 0
    for org_id, sp_id in due:
        try:
            await run_one(org_id, sp_id)
            n += 1
        except Exception:
            logger.exception("publish worker: run_one failed org=%s sp=%s", org_id, sp_id)
    return n


async def loop(interval: float = 30.0) -> None:
    logger.info("publish worker started (every %ss)", interval)
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("publish worker tick error")
        await asyncio.sleep(interval)
