"""Pull comments for an org, draft AI replies, and (when auto-reply is on) auto-post the safe ones.

Idempotent + best-effort: ingest leans on the repo's unique-key upsert (draft once per comment) and the
exactly-once reply guard, and never raises into the worker loop. Auto-posting is gated by BOTH the org's
`auto_reply_safe` toggle AND the conservative classifier (safe + high confidence)."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.repo import (connections as cr, comments as comment_repo, org_settings as os_repo,
                      notifications as nr, profile as profile_repo, memory as mem_repo,
                      scheduled_posts as sp_repo)
from app.social import comments_connector as cc
from app.agent import comment_reply
from app.agent.safety import contains_banned

logger = logging.getLogger(__name__)
MIN_POLL_INTERVAL = timedelta(minutes=10)   # auto-poll throttle; force=True (Poll now) bypasses
_AUTO_CONFIDENCE = 0.8                       # auto-post only when the classifier is both safe AND confident
_ingesting: set[str] = set()                # in-process single-flight per org


async def _post_link_map(org_id: str) -> dict[str, str]:
    """Map published post/media id -> our scheduled_post id, so an incoming comment can be linked back to the
    post that produced it. Best-effort over recent rows."""
    out: dict[str, str] = {}
    for sp in await sp_repo.list_recent(org_id, limit=100):
        for v in (sp.get("result") or {}).values():
            if isinstance(v, dict) and v.get("id"):
                out[str(v["id"])] = sp["id"]
    return out


async def _voice_and_banned(org_id: str) -> tuple[str, list[str]]:
    entries = await mem_repo.list_entries(org_id)
    voice = next((e["value"].get("descriptor", "") for e in entries if e["kind"] == "brand_voice"), "")
    banned = [e["value"].get("topic", "") for e in entries if e["kind"] == "banned_topic"]
    return voice, [b for b in banned if b]


async def _draft_for_new(org_id: str, comment: dict, profile: dict | None, voice: str,
                         banned: list[str]) -> bool:
    """Draft + store a suggested reply for one freshly-ingested comment. Returns True if a draft was saved.
    Never raises. Auto-posting is handled separately so it covers existing open comments too."""
    try:
        reply = await comment_reply.draft_reply(comment, profile, voice, banned)
    except Exception:
        logger.exception("comments: draft_reply failed org=%s comment=%s", org_id, comment["id"])
        reply = ""
    if not reply:
        return False
    await comment_repo.set_draft(org_id, comment["id"], reply)
    return True


async def _auto_post_open(org_id: str, token_by_conn: dict[str, str],
                          banned: list[str] | None = None) -> set[str]:
    """Auto-post every OPEN comment whose drafted reply the classifier rates safe + confident. Covers BOTH
    comments ingested this pass AND ones drafted earlier (e.g. before the toggle was switched on) — so
    turning auto-reply on actually clears the simple backlog. Exactly-once via mark_replied. Never raises.
    Returns the set of comment ids that were auto-posted."""
    posted: set[str] = set()
    banned = banned or []
    # Only comments not yet auto-evaluated (auto_eval_at IS NULL). Each open draft is classified at most
    # ONCE: a static backlog the classifier always rejects (or that we can't post) is never re-fed to the
    # LLM on the next poll. This is what turns the auto-reply poll from an idle vLLM burn into a no-op.
    for c in await comment_repo.list_open_unevaluated(org_id):
        token = token_by_conn.get(c["connection_id"])
        reply = (c.get("reply_text") or "").strip()
        if not token or not reply:
            continue   # no token/reply for this conn yet — leave unevaluated (no LLM call) and retry later
        try:
            # Deterministic ground-truth gate BEFORE the LLM verdict: a banned topic in the reply (or in
            # the attacker-controlled comment we'd be echoing) is never auto-posted, regardless of what the
            # classifier says — it falls back to a human-reviewed draft. Defends the public-posting path
            # against a fooled/injected safety classifier.
            if contains_banned(reply, banned) or contains_banned(c.get("message") or "", banned):
                logger.info("comments: banned topic in reply/comment — leaving as draft org=%s comment=%s",
                            org_id, c["id"])
                await comment_repo.mark_auto_evaluated(org_id, c["id"])
                continue
            verdict = await comment_reply.classify_safety(c, reply)
            # Stamp BEFORE acting on the verdict: the LLM safety classifier runs exactly once per comment,
            # so an unsafe (or safe-but-unpostable) comment is never re-classified on a later poll.
            await comment_repo.mark_auto_evaluated(org_id, c["id"])
            if not (verdict["safe"] and verdict["confidence"] >= _AUTO_CONFIDENCE):
                continue
            res = await cc.post_reply(c["provider"], c["external_id"], token, reply)
            if await comment_repo.mark_replied(org_id, c["id"], reply, res["id"], "auto"):
                posted.add(c["id"])
        except Exception:
            logger.exception("comments: auto-post failed org=%s comment=%s — leaving as draft",
                             org_id, c["id"])
            await comment_repo.mark_auto_evaluated(org_id, c["id"])
    return posted


def _comment_link(comment_id: str, status: str) -> str:
    return f"/workspace?tab=comments&comment={comment_id}&cstatus={status}"


async def _notify_new_comments(org_id: str, new_rows: list[dict], auto_ids: set[str]) -> None:
    """One notification per new comment, deep-linking to that exact comment (and the right status tab) so a
    click lands on it. Auto-replied ones say so. Caps the burst with a summary tail to avoid flooding."""
    _CAP = 8
    for row in new_rows[:_CAP]:
        author = row.get("author_name") or "Someone"
        body = (row.get("message") or "").strip()[:140]
        if row["id"] in auto_ids:
            await nr.create(org_id, None, "comment", f"Auto-replied to {author}", body,
                            link=_comment_link(row["id"], "replied"))
        else:
            await nr.create(org_id, None, "comment", f"New comment from {author}", body,
                            link=_comment_link(row["id"], "open"))
    extra = len(new_rows) - _CAP
    if extra > 0:
        await nr.create(org_id, None, "comment", f"+{extra} more new comment(s)",
                        "Open the Comments inbox to review them.", link="/workspace?tab=comments")


async def ingest_org_comments(org_id: str, provider: str | None = None, force: bool = False) -> dict:
    """Fetch + process comments for one org. Throttled unless force=True. Returns a summary dict."""
    if org_id in _ingesting:
        return {"status": "busy", "new": 0, "drafted": 0, "auto_replied": 0}
    if not force:
        last = await os_repo.comments_polled_at(org_id)
        if last and (datetime.now(timezone.utc) - last) < MIN_POLL_INTERVAL:
            return {"status": "throttled", "new": 0, "drafted": 0, "auto_replied": 0}

    _ingesting.add(org_id)
    try:
        conns = [c for c in await cr.list_connections(org_id) if cr.can_engage(c)
                 and (not provider or c["provider"] == provider)]
        if not conns:
            await os_repo.touch_comments_polled(org_id)
            return {"status": "ok", "connections": 0, "new": 0, "drafted": 0, "auto_replied": 0}

        settings = await os_repo.get(org_id)
        auto_safe = bool(settings.get("auto_reply_safe"))
        profile = await profile_repo.get_profile(org_id)
        voice, banned = await _voice_and_banned(org_id)
        link_map = await _post_link_map(org_id)

        # Pass 1: fetch + ingest new comments, drafting a suggested reply for each.
        all_new: list[dict] = []
        token_by_conn: dict[str, str] = {}
        for conn in conns:
            token = await cr.get_token(org_id, conn["id"])
            if not token:
                continue
            token_by_conn[conn["id"]] = token
            since = await comment_repo.newest_commented_at(org_id, conn["id"])
            try:
                fetched = await cc.fetch_comments(conn["provider"], conn["external_id"], token, since=since)
            except Exception:
                logger.exception("comments: fetch failed org=%s conn=%s", org_id, conn["id"])
                continue
            for f in fetched:
                f["scheduled_post_id"] = link_map.get(f.get("post_external_id") or "")
            new_rows = await comment_repo.upsert_many(org_id, conn["id"], conn["provider"], fetched)
            all_new.extend(new_rows)
            for row in new_rows:
                await _draft_for_new(org_id, row, profile, voice, banned)

        # Pass 2: when auto-reply is on, auto-post the safe OPEN comments (new + any earlier backlog).
        auto_ids = await _auto_post_open(org_id, token_by_conn, banned) if auto_safe else set()
        total_new = len(all_new)
        new_auto = sum(1 for r in all_new if r["id"] in auto_ids)
        drafted = total_new - new_auto
        auto_replied = len(auto_ids)   # total auto-posted this pass (new + cleared backlog)

        await os_repo.touch_comments_polled(org_id)
        await _notify_new_comments(org_id, all_new, auto_ids)
        return {"status": "ok", "connections": len(conns), "new": total_new,
                "drafted": drafted, "auto_replied": auto_replied}
    finally:
        _ingesting.discard(org_id)
