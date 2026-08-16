"""Durable job handlers. Importing this module registers them.

Real handlers land as their subsystems are migrated onto the queue (Phase 3+). `campaign_fill` is the
first; `noop` stays for liveness checks."""
import logging

from app.worker import registry
from app.worker.runner import JobContext

logger = logging.getLogger("worker")


@registry.register("noop")
async def noop(ctx: JobContext, payload: dict) -> None:
    """A do-nothing job — proves claim → dispatch → succeed. Useful for liveness checks."""
    logger.info("noop job org=%s payload=%s", ctx.org_id, payload)


@registry.register("campaign_fill")
async def campaign_fill(ctx: JobContext, payload: dict) -> None:
    """Draft every not-yet-filled slot of a campaign. fill_campaign is idempotent (already-filled slots
    carry a post_id and are skipped) and records per-slot errors itself, so we do NOT raise on partial
    failure. We re-raise (→ retry with backoff) only when the campaign existed with work to do and NOTHING
    drafted — a transient fault (LLM/profile blip) worth retrying; a vanished campaign is not."""
    from app.agent.campaign_fill import fill_campaign as _fill
    result = await _fill(ctx.org_id, payload["campaign_id"])
    logger.info("campaign_fill org=%s campaign=%s -> %s", ctx.org_id, payload.get("campaign_id"), result)
    if result.get("error") == "not found":
        return
    if result.get("total", 0) > 0 and result.get("filled", 0) == 0:
        raise RuntimeError(f"campaign_fill drafted 0/{result.get('total')} slots: {result.get('errors')}")


@registry.register("metrics_poll")
async def metrics_poll(ctx: JobContext, payload: dict) -> None:
    """Re-poll one published target's performance and append a snapshot. Best-effort: a missing token /
    provider / external id (e.g. an ad-hoc publish, or a since-disconnected page) is a no-op, not a failure
    — the connector itself never raises and degrades dead metrics to 0."""
    from app.social import insights_connector as ic
    from app.repo import connections as cr, post_metrics as pm
    org = ctx.org_id
    cid, provider, ext = payload.get("connection_id"), payload.get("provider"), payload.get("external_post_id")
    token = await cr.get_token(org, cid) if cid else None
    if not (token and provider and ext and payload.get("post_id")):
        return
    metrics = await ic.fetch_post_metrics(provider, ext, token)
    await pm.record_snapshot(org, payload["post_id"], cid, provider, ext, metrics)


@registry.register("audience_poll")
async def audience_poll(ctx: JobContext, payload: dict) -> None:
    """Snapshot the current follower count for each insights-capable connection (drives the Followers KPI).
    Best-effort: a connection without a token or the insights scope is skipped; the connector never raises."""
    from app.social import insights_connector as ic
    from app.repo import connections as cr, post_metrics as pm
    org = ctx.org_id
    for conn in await cr.list_connections(org):
        # Follower count needs only basic page/IG access (FB: followers_count/fan_count, IG: followers_count
        # under instagram_basic) — NOT the insights scope. Gating this on insights_capable wrongly skipped IG
        # accounts that lack instagram_manage_insights, leaving their Followers KPI permanently 0.
        cid, ext = conn.get("id"), conn.get("external_id")
        token = await cr.get_token(org, cid) if cid else None
        if not (token and ext):
            continue
        followers = await ic.fetch_follower_count(conn.get("provider"), ext, token)
        await pm.record_follower_snapshot(org, cid, conn.get("provider"), followers)


@registry.register("import_posts")
async def import_posts(ctx: JobContext, payload: dict) -> None:
    """Import a connected account's real posts (+ per-post metrics) into the ledger so Insights reflect the
    actual account. payload.connection_id imports one connection; otherwise all of the org's connections.
    Best-effort & idempotent (dedups on the Meta object id)."""
    from app.repo import connections as cr, insights_import as imp
    org = ctx.org_id
    cid = payload.get("connection_id")
    conns = [await cr.get_connection(org, cid)] if cid else await cr.list_connections(org)
    for conn in conns:
        if not conn:
            continue
        token = await cr.get_token(org, conn["id"])
        if not token:
            continue
        await imp.import_account(org, conn, token)


@registry.register("metrics_sweep")
async def metrics_sweep(ctx: JobContext, payload: dict) -> None:
    """Daily fan-out: enqueue a metrics_poll for every still-young published target. dedup_key keeps the
    sweep idempotent across runs (a live poll for the same target is reused, not duplicated)."""
    from app.repo import post_metrics as pm, jobs
    for item in await pm.young_published_posts(ctx.org_id, days=14):
        await jobs.enqueue(ctx.org_id, "metrics_poll", payload=item,
                           dedup_key=f"mp-{item['post_id']}-{item.get('external_post_id')}")
