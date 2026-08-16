import hashlib
from app.repo import documents as doc_repo
from app.sources import chunk as chunker, embed


async def persist_article(org_id: str, source_id: str, art: dict) -> bool:
    """Chunk → embed → upsert one article. Returns True if it was new/changed (and embedded),
    False if the content hash matched an existing document (skipped)."""
    text = (art.get("text") or "").strip()
    if not text:
        return False
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    did, changed = await doc_repo.upsert_document(
        org_id, source_id, art["url"], art.get("title"), art.get("author"),
        art.get("published_at"), content_hash, len(text),
        image_url=art.get("image_url"))
    if not changed:
        return False
    pieces = chunker.chunk_text(text)
    if not pieces:
        return False
    vectors = await embed.embed_texts(pieces)
    await doc_repo.replace_chunks(org_id, did, [(i, p, v) for i, (p, v) in enumerate(zip(pieces, vectors))])
    return True
