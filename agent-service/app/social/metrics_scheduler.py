"""Background insights scheduler. Mirrors app/comments/worker: each tick reads engage-capable orgs via the
platform-owned SECURITY DEFINER reader (ids only) and, throttled to ~once/day per org, enqueues the two
insights fan-out jobs — metrics_sweep (re-poll young published posts) and audience_poll (snapshot followers).

Without this nothing periodically refreshes insights: metrics only update via the publish-time enqueue and
the manual Refresh button. Best-effort — never crashes startup; disabled gracefully until engage_capable_orgs
is installed. The 20h throttle keys off the latest audience_snapshots.captured_at, so an hourly tick still
enqueues at most ~once per org per day (and survives restarts — the throttle is in the DB, not in memory)."""
import asyncio
import logging

from app.db import pool as dbpool
from app.db.pool import org_tx
from app.repo import jobs

logger = logging.getLogger(__name__)
_warned_missing = False

# Throttle window: an org is "due" if its newest audience snapshot is NULL or older than this. ~20h (not 24h)
# so an org polled at, say, 09:00 is due again the next morning rather than slipping a day later each time.
_THROTTLE_HOURS = 20


async def _engage_orgs(limit: int = 200) -> list[str]:
    """Cross-org ids of engage-capable orgs via the platform-owned SECURITY DEFINER reader. Returns [] (and
    warns once) if the function isn't installed — the scheduler must never crash startup."""
    global _warned_missing
    if dbpool._pool is None:
        return []
    try:
        async with dbpool._pool.acquire() as c:
            rows = await c.fetch("SELECT org_id FROM engage_capable_orgs($1)", limit)
        return [str(r["org_id"]) for r in rows]
    except Exception as e:
        if not _warned_missing:
            logger.warning("metrics scheduler: engage_capable_orgs unavailable (%s); periodic insights refresh "
                           "disabled until scripts/setup_publish_fn.sql is applied as the platform superuser", e)
            _warned_missing = True
        return []


async def _is_due(org_id: str) -> bool:
    """True if this org hasn't had an audience snapshot within the throttle window (or ever). Read under the
    org's RLS scope so it sees only that org's snapshots."""
    async with org_tx(org_id) as c:
        recent = await c.fetchval(
            "SELECT 1 FROM audience_snapshots "
            "WHERE captured_at > now() - make_interval(hours => $1::int) LIMIT 1", _THROTTLE_HOURS)
    return recent is None


async def tick(limit: int = 200) -> int:
    """One pass: for each engage-capable org that's due (~daily throttle), enqueue metrics_sweep + audience_poll.
    Returns the number of jobs enqueued. Best-effort — a per-org failure is logged, never raised."""
    n = 0
    for org_id in await _engage_orgs(limit):
        try:
            if not await _is_due(org_id):
                continue
            # dedup_key keeps a still-live sweep/poll for the same org idempotent (a frequent tick reuses it).
            await jobs.enqueue(org_id, "metrics_sweep", payload={}, dedup_key=f"sweep-{org_id}")
            await jobs.enqueue(org_id, "audience_poll", payload={}, dedup_key=f"aud-{org_id}")
            await jobs.enqueue(org_id, "import_posts", payload={}, dedup_key=f"import-{org_id}")
            n += 3
        except Exception:
            logger.exception("metrics scheduler: enqueue failed org=%s", org_id)
    return n


async def loop(interval: float = 3600.0) -> None:
    """Tick every `interval` seconds until cancelled. Hourly tick + the 20h DB throttle ⇒ effectively daily."""
    logger.info("metrics scheduler started (every %ss)", interval)
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("metrics scheduler tick error")
        await asyncio.sleep(interval)
