import uuid
from app.db.pool import org_tx


async def create_attachment(org_id: str, user_id: str | None, filename: str, mime_type: str | None,
                            file_size: int | None, content_text: str | None, data: bytes,
                            status: str = "ready") -> dict:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "INSERT INTO attachments(org_id,user_id,filename,mime_type,file_size,content_text,data,status) "
            "VALUES($1,$2,$3,$4,$5,$6,$7,$8) "
            "RETURNING id, filename, mime_type, file_size, status, created_at",
            uuid.UUID(org_id), uuid.UUID(user_id) if user_id else None, filename, mime_type,
            file_size, content_text, data, status)
    return {
        "id": str(r["id"]),
        "filename": r["filename"],
        "mime_type": r["mime_type"],
        "file_size": r["file_size"],
        "status": r["status"],
        "created_at": r["created_at"].isoformat(),
    }


async def get_attachment(org_id: str, attachment_id: str) -> dict | None:
    """Fetch a single attachment incl. bytes + extracted text (for download), or None."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT id, filename, mime_type, file_size, content_text, data, status "
            "FROM attachments WHERE id=$1", uuid.UUID(attachment_id))
    if not r:
        return None
    return {
        "id": str(r["id"]),
        "filename": r["filename"],
        "mime_type": r["mime_type"],
        "file_size": r["file_size"],
        "content_text": r["content_text"],
        "data": bytes(r["data"]) if r["data"] is not None else b"",
        "status": r["status"],
    }


async def link_to_message(org_id: str, message_id: str, ids: list[str]) -> None:
    """Attach previously-uploaded files to the message they were sent with. Only links rows that are
    still unlinked (message_id IS NULL) so an id can't be re-homed onto a later message."""
    if not ids:
        return
    uuids = [uuid.UUID(i) for i in ids]
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE attachments SET message_id=$1 WHERE id = ANY($2::uuid[]) AND message_id IS NULL",
            uuid.UUID(message_id), uuids)


async def list_for_messages(org_id: str, message_ids: list[str]) -> dict[str, list[dict]]:
    """Return {message_id: [attachment-meta, …]} for the given messages (no bytes/text). The UI renders
    `original_filename`, which we mirror from `filename`."""
    if not message_ids:
        return {}
    uuids = [uuid.UUID(i) for i in message_ids]
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT id, message_id, filename, mime_type, file_size, status, created_at "
            "FROM attachments WHERE message_id = ANY($1::uuid[]) ORDER BY created_at",
            uuids)
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(str(r["message_id"]), []).append({
            "id": str(r["id"]),
            "message_id": str(r["message_id"]),
            "filename": r["filename"],
            "original_filename": r["filename"],
            "mime_type": r["mime_type"] or "application/octet-stream",
            "file_size": r["file_size"] or 0,
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        })
    return out


async def get_texts(org_id: str, ids: list[str]) -> list[tuple[str, str]]:
    """Return (filename, content_text) for ready rows with non-empty extracted text."""
    if not ids:
        return []
    uuids = [uuid.UUID(i) for i in ids]
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT filename, content_text FROM attachments "
            "WHERE id = ANY($1::uuid[]) AND status='ready' "
            "AND content_text IS NOT NULL AND content_text <> '' "
            "ORDER BY created_at",
            uuids)
    return [(r["filename"], r["content_text"]) for r in rows]
