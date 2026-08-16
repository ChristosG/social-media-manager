"""Background comment-ingest worker. Mirrors app/social/publish_worker: each tick reads engage-capable
orgs via a platform-owned SECURITY DEFINER reader (ids only) and runs the org-scoped ingest (throttled).
Best-effort — never crashes startup; disabled gracefully until engage_capable_orgs is installed."""
import asyncio
import logging

from app.db import pool as dbpool
from app.comments.ingest import ingest_org_comments

logger = logging.getLogger(__name__)
_warned_missing = False


async def _engage_orgs(limit: int = 100) -> list[str]:
    global _warned_missing
    if dbpool._pool is None:
        return []
    try:
        async with dbpool._pool.acquire() as c:
            rows = await c.fetch("SELECT org_id FROM engage_capable_orgs($1)", limit)
        return [str(r["org_id"]) for r in rows]
    except Exception as e:
        if not _warned_missing:
            logger.warning("comments worker: engage_capable_orgs unavailable (%s); comment polling disabled "
                           "until scripts/setup_publish_fn.sql is applied as the platform superuser", e)
            _warned_missing = True
        return []


async def tick() -> int:
    n = 0
    for org_id in await _engage_orgs():
        try:
            await ingest_org_comments(org_id)   # throttled (not force) so the loop won't hammer the Graph API
            n += 1
        except Exception:
            logger.exception("comments worker: ingest failed org=%s", org_id)
    return n


async def loop(interval: float = 120.0) -> None:
    logger.info("comments worker started (every %ss)", interval)
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("comments worker tick error")
        await asyncio.sleep(interval)
