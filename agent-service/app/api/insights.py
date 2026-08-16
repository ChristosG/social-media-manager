import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from app.security.context import require_identity
from app.repo import insights as repo
from app.repo import org_settings as os_repo
from app.repo import post_metrics as pm
from app.repo import jobs as jobs_repo

logger = logging.getLogger(__name__)
router = APIRouter()

# Manual-refresh throttle: a "Refresh now" click enqueues a metrics/follower sweep at most once per window.
MIN_POLL_INTERVAL = timedelta(minutes=10)
_COOLDOWN_SECONDS = int(MIN_POLL_INTERVAL.total_seconds())


@router.get("/insights/summary")
async def summary(platform: str = "all", range: int = 30,
                  ident: tuple[str, str] = Depends(require_identity)):
    """Aggregated insights dashboard. `platform` ∈ {all, facebook, instagram}; `range` is window days."""
    _, org = ident
    return await repo.insights_dashboard(org, platform=platform, range_days=range)


@router.get("/insights/posts/{post_id}")
async def post_series(post_id: str, ident: tuple[str, str] = Depends(require_identity)):
    """Per-post metric series (the captured snapshots) for the drill-down chart."""
    _, org = ident
    return await repo.post_series(org, post_id)


@router.post("/insights/refresh")
async def refresh(ident: tuple[str, str] = Depends(require_identity)):
    """Throttled manual refresh: enqueue a metrics re-poll for recently-published posts plus a follower
    snapshot, at most once per MIN_POLL_INTERVAL. Best-effort — a queue hiccup never 500s the click."""
    _, org = ident
    last = await os_repo.insights_refreshed_at(org)
    if last:
        elapsed = datetime.now(timezone.utc) - last
        if elapsed < MIN_POLL_INTERVAL:
            remaining = int((MIN_POLL_INTERVAL - elapsed).total_seconds())
            return {"enqueued": False, "cooldown_seconds": max(remaining, 0)}

    await os_repo.touch_insights_refreshed(org)
    repo.invalidate_meta(org)   # next dashboard load re-fetches the live Meta block, not the cached one
    try:
        posts = await pm.young_published_posts(org)
        for p in posts:
            ext = p.get("external_post_id")
            if not ext:
                continue
            await jobs_repo.enqueue(
                org, "metrics_poll",
                payload={"post_id": p["post_id"], "connection_id": p.get("connection_id"),
                         "provider": p.get("provider"), "external_post_id": ext},
                dedup_key=f"mp-refresh-{p['post_id']}-{ext}")
        # Follower snapshot intent — one sweep across the org's connected accounts.
        await jobs_repo.enqueue(org, "audience_poll", payload={}, dedup_key="audience-refresh")
        # Pull in any new real posts from the connected accounts (+ their metrics) so Insights stay current.
        await jobs_repo.enqueue(org, "import_posts", payload={}, dedup_key="import-refresh")
    except Exception:
        logger.exception("insights: refresh enqueue failed org=%s", org)

    return {"enqueued": True, "cooldown_seconds": _COOLDOWN_SECONDS}
