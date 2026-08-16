import uuid
from app.db.pool import org_tx


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


async def upsert_document(org_id: str, source_id: str, url: str, title: str | None, author: str | None,
                          published_at, content_hash: str, char_count: int,
                          image_url: str | None = None) -> tuple[str, bool]:
    """Insert or update by (org,url). Returns (document_id, changed) where changed is False when the
    content_hash is unchanged (caller skips re-embedding)."""
    async with org_tx(org_id) as c:
        existing = await c.fetchrow(
            "SELECT id, content_hash FROM documents WHERE org_id=$1 AND url=$2",
            uuid.UUID(org_id), url)
        if existing and existing["content_hash"] == content_hash:
            return str(existing["id"]), False
        if existing:
            await c.execute(
                "UPDATE documents SET title=$1, author=$2, published_at=$3, content_hash=$4, "
                "char_count=$5, fetched_at=now(), image_url=$7 WHERE id=$6",
                title, author, published_at, content_hash, char_count, existing["id"], image_url)
            return str(existing["id"]), True
        did = await c.fetchval(
            "INSERT INTO documents(org_id, source_id, url, title, author, published_at, content_hash, "
            "char_count, image_url) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id",
            uuid.UUID(org_id), uuid.UUID(source_id), url, title, author, published_at, content_hash,
            char_count, image_url)
        return str(did), True


async def replace_chunks(org_id: str, document_id: str, chunks: list[tuple[int, str, list[float]]]) -> None:
    async with org_tx(org_id) as c:
        await c.execute("DELETE FROM chunks WHERE document_id=$1", uuid.UUID(document_id))
        for ord_, text, emb in chunks:
            await c.execute(
                "INSERT INTO chunks(org_id, document_id, ord, text, embedding) VALUES($1,$2,$3,$4,$5::vector)",
                uuid.UUID(org_id), uuid.UUID(document_id), ord_, text, _vec_literal(emb))


async def search_chunks(org_id: str, query_embedding: list[float], k: int = 6) -> list[dict]:
    q = ("SELECT d.url, d.title, c.text, s.kind, 1 - (c.embedding <=> $1::vector) AS score "
         "FROM chunks c JOIN documents d ON d.id = c.document_id JOIN sources s ON s.id = d.source_id "
         "ORDER BY c.embedding <=> $1::vector LIMIT $2")
    async with org_tx(org_id) as c:
        rows = await c.fetch(q, _vec_literal(query_embedding), k)
    return [{"url": r["url"], "title": r["title"], "text": r["text"], "kind": r["kind"],
             "score": float(r["score"])} for r in rows]


async def list_documents(org_id: str, source_id: str) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT id, url, title, author, published_at, fetched_at, char_count "
            "FROM documents WHERE source_id=$1 ORDER BY COALESCE(published_at, fetched_at) DESC",
            uuid.UUID(source_id))
    return [{"id": str(r["id"]), "url": r["url"], "title": r["title"], "author": r["author"],
             "published_at": r["published_at"].isoformat() if r["published_at"] else None,
             "fetched_at": r["fetched_at"].isoformat(), "char_count": r["char_count"]} for r in rows]


async def delete_document(org_id: str, source_id: str, document_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM documents WHERE id=$1 AND source_id=$2",
                              uuid.UUID(document_id), uuid.UUID(source_id))
    return res.endswith(" 1")


async def count_documents(org_id: str, source_id: str) -> int:
    async with org_tx(org_id) as c:
        return await c.fetchval("SELECT count(*) FROM documents WHERE source_id=$1", uuid.UUID(source_id))


async def count_chunks(org_id: str, document_id: str) -> int:
    async with org_tx(org_id) as c:
        return await c.fetchval("SELECT count(*) FROM chunks WHERE document_id=$1", uuid.UUID(document_id))


async def source_stats(org_id: str) -> dict[str, dict]:
    """Per-source knowledge footprint: {source_id: {documents, chunks}} for the Knowledge tab.
    One round-trip across all of the org's sources (RLS-scoped)."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT d.source_id, count(DISTINCT d.id) AS docs, count(ch.id) AS chunks "
            "FROM documents d LEFT JOIN chunks ch ON ch.document_id = d.id "
            "GROUP BY d.source_id")
    return {str(r["source_id"]): {"documents": int(r["docs"]), "chunks": int(r["chunks"])} for r in rows}


async def list_social_posts(org_id: str, provider: str, limit: int = 60) -> list[dict]:
    """Return documents belonging to sources of kind=provider (facebook/instagram), newest first."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT d.url, d.title, d.published_at, d.image_url, s.name AS source_name "
            "FROM documents d JOIN sources s ON s.id = d.source_id "
            "WHERE s.kind = $1 ORDER BY d.published_at DESC NULLS LAST, d.fetched_at DESC LIMIT $2",
            provider, limit)
        return [{"url": r["url"], "title": r["title"],
                 "published_at": r["published_at"].isoformat() if r["published_at"] else None,
                 "image_url": r["image_url"], "source_name": r["source_name"]} for r in rows]


async def prune_documents(org_id: str, source_id: str, keep: int = 60) -> int:
    """Delete all but the `keep` newest documents for a source (chunks cascade)."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "DELETE FROM documents WHERE source_id=$1 AND id NOT IN ("
            "  SELECT id FROM documents WHERE source_id=$1 "
            "  ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT $2)",
            uuid.UUID(source_id), keep)
    return int(res.split()[-1])


async def reconcile_to_urls(org_id: str, source_id: str, keep_urls: list[str], since) -> int:
    """Remove documents for a source that the latest fetch no longer returned — i.e. posts DELETED on the
    platform. Bounded to the refreshed window: only documents with published_at >= `since` (the oldest post
    we just saw) are eligible, so posts older than the fetch window (which we simply didn't re-observe) are
    never wrongly pruned. `keep_urls` is the set of URLs present in the latest fetch. Chunks cascade."""
    if since is None:
        return 0
    async with org_tx(org_id) as c:
        res = await c.execute(
            "DELETE FROM documents WHERE source_id=$1 AND published_at >= $2 "
            "AND url <> ALL($3::text[])",
            uuid.UUID(source_id), since, keep_urls or [])
    return int(res.split()[-1])
