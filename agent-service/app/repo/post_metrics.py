"""Per-post performance snapshots (the `post_metrics` table) and the set of recently-published posts worth
re-polling. A published `scheduled_posts.result` is a `{connection_id: {...}}` map; a successful target is
`{"id": <external post id>, "permalink": ..., "status": "ok"}` (see publish_worker.run_one), while the
provider for that connection lives in the `targets` array — so we join provider in Python by connection_id.
"""
import json
import uuid

from app.db.pool import org_tx


async def record_snapshot(org_id: str, post_id: str, connection_id: str | None, provider: str,
                          external_post_id: str | None, metrics: dict) -> None:
    """Append one per-post metrics snapshot."""
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO post_metrics(org_id, post_id, connection_id, provider, external_post_id, metrics) "
            "VALUES($1,$2,$3,$4,$5,$6::jsonb)",
            uuid.UUID(org_id), uuid.UUID(post_id),
            uuid.UUID(connection_id) if connection_id else None, provider, external_post_id,
            json.dumps(metrics or {}))


async def record_follower_snapshot(org_id: str, connection_id: str | None, provider: str,
                                   followers: int) -> None:
    """Append one follower-count snapshot for a connection (drives the Followers KPI trend)."""
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO audience_snapshots(org_id, connection_id, provider, followers) VALUES($1,$2,$3,$4)",
            uuid.UUID(org_id), uuid.UUID(connection_id) if connection_id else None, provider, int(followers))


async def young_published_posts(org_id: str, days: int = 14) -> list[dict]:
    """Posts published in the last `days` that have a published scheduled_posts row, as
    [{post_id, connection_id, provider, external_post_id}] — the set worth re-polling (engagement
    plateaus, so older posts are skipped to stay within Meta rate limits).

    `scheduled_posts` has no published_at column; the row reaches 'published' via finish(), which sets
    updated_at=now(), so updated_at is the publish time for a published row. The DB filters to recent
    published rows that have a post_id (ad-hoc publishes with no ledger post are skipped — post_metrics
    requires a post_id); per-target external ids are extracted from the jsonb result in Python, with the
    provider joined from the targets array by connection_id."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT post_id, targets, result FROM scheduled_posts "
            "WHERE status='published' AND post_id IS NOT NULL "
            "AND updated_at >= now() - make_interval(days => $1::int)",
            days)

    out: list[dict] = []
    for r in rows:
        post_id = str(r["post_id"])
        targets = r["targets"] if isinstance(r["targets"], list) else json.loads(r["targets"] or "[]")
        result = r["result"] if isinstance(r["result"], dict) else json.loads(r["result"] or "{}")
        # provider per connection_id, from the targets array
        provider_by_cid = {t.get("connection_id"): t.get("provider") for t in targets}
        for cid, entry in result.items():
            if not isinstance(entry, dict):
                continue
            ext = entry.get("id")
            if not ext:
                continue  # only successfully-published targets carry an external id
            out.append({
                "post_id": post_id,
                "connection_id": cid,
                "provider": provider_by_cid.get(cid),
                "external_post_id": ext,
            })
    return out
