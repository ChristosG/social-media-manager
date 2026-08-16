import uuid
from app.db.pool import org_tx


async def upsert_caption(org_id: str, conversation_id: str, caption: str) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO conversation_drafts(conversation_id, org_id, caption) VALUES($1,$2,$3) "
            "ON CONFLICT (conversation_id) DO UPDATE SET caption=EXCLUDED.caption, updated_at=now()",
            uuid.UUID(conversation_id), uuid.UUID(org_id), caption)


async def upsert_images(org_id: str, conversation_id: str, image_ids: list[str], *,
                        replace: bool = False) -> None:
    """Persist the draft's image set for a conversation.

    By default this ACCUMULATES: every image generated across the chat is appended (order-preserving,
    de-duplicated) so the publish dialog can offer the user the whole set to pick from — they remove the
    ones they don't want. Pass ``replace=True`` to overwrite instead. Read-modify-write runs inside a
    single per-org transaction; conversations are effectively single-writer (one user, sequential turns).
    """
    new_ids = [uuid.UUID(i) for i in image_ids]
    async with org_tx(org_id) as c:
        if replace:
            merged = new_ids
        else:
            row = await c.fetchrow(
                "SELECT image_ids FROM conversation_drafts WHERE conversation_id=$1",
                uuid.UUID(conversation_id))
            existing = list(row["image_ids"]) if row and row["image_ids"] else []
            seen = set(existing)
            merged = existing + [i for i in new_ids if not (i in seen or seen.add(i))]
        await c.execute(
            "INSERT INTO conversation_drafts(conversation_id, org_id, image_ids) VALUES($1,$2,$3) "
            "ON CONFLICT (conversation_id) DO UPDATE SET image_ids=EXCLUDED.image_ids, updated_at=now()",
            uuid.UUID(conversation_id), uuid.UUID(org_id), merged)


async def get_draft(org_id: str, conversation_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT caption, image_ids FROM conversation_drafts WHERE conversation_id=$1",
            uuid.UUID(conversation_id))
    if r is None:
        return None
    return {"caption": r["caption"], "image_ids": [str(i) for i in (r["image_ids"] or [])]}
