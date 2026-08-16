import asyncio
import logging
from datetime import datetime, timedelta, timezone
from app.db import pool as dbpool
from app.repo import sources as src_repo
from app.sources.ingest import run_ingest

logger = logging.getLogger(__name__)
_REFRESH_INTERVAL = timedelta(days=1)
_warned_missing = False


async def _due_sources(limit: int = 20) -> list[tuple[str, str]]:
    """Cross-org (org_id, source_id) pairs due for refresh, via the platform-owned SECURITY DEFINER
    function (bypasses RLS, ids only). Returns [] if the function isn't installed (setup not run) or on
    any error — the scheduler must never crash startup."""
    global _warned_missing
    if dbpool._pool is None:
        return []
    try:
        async with dbpool._pool.acquire() as c:
            rows = await c.fetch("SELECT org_id, source_id FROM sched_due_sources($1)", limit)
        return [(str(r["org_id"]), str(r["source_id"])) for r in rows]
    except Exception as e:
        if not _warned_missing:
            logger.warning("scheduler: sched_due_sources unavailable (%s); daily auto-refresh disabled "
                           "until scripts/setup_scheduler_fn.sql is applied as the platform superuser", e)
            _warned_missing = True
        return []


async def tick() -> int:
    """One scheduler pass: ingest each due source, then push its next_due_at out one interval."""
    due = await _due_sources()
    n = 0
    for org_id, source_id in due:
        try:
            await run_ingest(org_id, source_id)
            await src_repo.set_state(org_id, source_id,
                                     next_due_at=datetime.now(timezone.utc) + _REFRESH_INTERVAL)
            n += 1
        except Exception:
            logger.exception("scheduler: ingest failed org=%s source=%s", org_id, source_id)
    return n


async def scheduler_loop(interval_s: int = 300) -> None:
    logger.info("source refresh scheduler started (every %ss)", interval_s)
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduler tick error")
        await asyncio.sleep(interval_s)
