"""Semantic + performance memory of past campaigns.

`plan_campaign` uses this to ground a NEW campaign in the org's prior ones: it embeds the new brief, finds
the most topically-similar past campaigns (`similar`), and folds in how each one actually performed
(`engagement_for`) — so the planner avoids near-duplicates and can draw data-backed conclusions, and the
chat can cite the matched campaigns with a click-through. Embeddings live in `campaign_embeddings` (migration
033), the same 2560-dim space as the RAG `chunks` table; an exact cosine scan is fine for the tiny per-org
corpus. All writes are best-effort at the call site: the embedder being down must never block planning.
"""
import uuid
from app.db.pool import org_tx


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


async def upsert_embedding(org_id: str, campaign_id: str, brief: str, embedding: list[float]) -> None:
    """Store/refresh the embedding for a campaign's brief (idempotent on campaign_id)."""
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO campaign_embeddings(campaign_id, org_id, brief, embedding) "
            "VALUES($1,$2,$3,$4::vector) "
            "ON CONFLICT (campaign_id) DO UPDATE SET brief=EXCLUDED.brief, "
            "embedding=EXCLUDED.embedding, updated_at=now()",
            uuid.UUID(campaign_id), uuid.UUID(org_id), brief, _vec_literal(embedding),
        )


async def similar(org_id: str, query_embedding: list[float], k: int = 3,
                  exclude_id: str | None = None) -> list[dict]:
    """The org's past campaigns most similar to the query brief, best-first, as
    [{campaign_id, brief, score, status, posts, engagement}]. Joins the live campaign so an archived/renamed
    campaign is reflected, and aggregates engagement from the latest metric snapshot of each attached post."""
    q = (
        "SELECT e.campaign_id, c.brief, c.status, "
        "       1 - (e.embedding <=> $1::vector) AS score, "
        "       (SELECT count(*) FROM campaign_slots s WHERE s.campaign_id = e.campaign_id) AS posts, "
        "       COALESCE(("
        "         SELECT SUM((l.metrics->>'engagement')::numeric) "
        "         FROM campaign_slots s "
        "         JOIN LATERAL ("
        "           SELECT metrics FROM post_metrics m "
        "           WHERE m.post_id = s.post_id ORDER BY m.captured_at DESC LIMIT 1"
        "         ) l ON true "
        "         WHERE s.campaign_id = e.campaign_id AND s.post_id IS NOT NULL"
        "       ), 0) AS engagement "
        "FROM campaign_embeddings e JOIN campaigns c ON c.id = e.campaign_id "
        "WHERE ($2::uuid IS NULL OR e.campaign_id <> $2) "
        "ORDER BY e.embedding <=> $1::vector LIMIT $3"
    )
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            q, _vec_literal(query_embedding),
            uuid.UUID(exclude_id) if exclude_id else None, k,
        )
    return [
        {
            "campaign_id": str(r["campaign_id"]),
            "brief": r["brief"],
            "status": r["status"],
            "score": float(r["score"]),
            "posts": int(r["posts"] or 0),
            "engagement": int(r["engagement"] or 0),
        }
        for r in rows
    ]


async def angles_for(org_id: str, campaign_id: str, limit: int = 8) -> list[str]:
    """The angle lines of a past campaign — the concrete ideas to avoid repeating in a new plan."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT angle FROM campaign_slots WHERE campaign_id=$1 ORDER BY position LIMIT $2",
            uuid.UUID(campaign_id), limit,
        )
    return [r["angle"] for r in rows if r["angle"]]
