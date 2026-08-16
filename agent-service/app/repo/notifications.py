import json
import uuid

from app.db.pool import org_tx

_COLS = "id, org_id, user_id, type, title, body, link, data, read_at, created_at"


def _row(r) -> dict:
    return {
        "id": str(r["id"]),
        "type": r["type"],
        "title": r["title"],
        "body": r["body"],
        "link": r["link"],
        "data": r["data"] if isinstance(r["data"], dict) else json.loads(r["data"] or "{}"),
        "read": r["read_at"] is not None,
        "created_at": r["created_at"].isoformat(),
    }


def _user_uuid(user_id: str | None) -> uuid.UUID | None:
    """Return a UUID if user_id is a valid UUID string, otherwise None.

    The require_identity dependency returns the raw x-user-id header value, which
    may be any string (e.g. "u" in tests, or a real UUID from the gateway).  The
    notifications.user_id column is UUID.  We treat non-UUID user-ids as None so
    that those callers receive org-wide (user_id IS NULL) notifications — the same
    set returned when user_id is genuinely absent.  When the worker creates a
    notification targeting a specific user it passes a proper UUID string and this
    cast succeeds normally.
    """
    if not user_id:
        return None
    try:
        return uuid.UUID(user_id)
    except ValueError:
        return None


async def create(
    org_id: str,
    user_id: str | None,
    type: str,
    title: str,
    body: str = "",
    link: str | None = None,
    data: dict | None = None,
) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO notifications(org_id, user_id, type, title, body, link, data) "
            "VALUES($1, $2, $3, $4, $5, $6, $7::jsonb)",
            uuid.UUID(org_id),
            _user_uuid(user_id),
            type,
            title,
            body,
            link,
            json.dumps(data or {}),
        )


async def list_for(org_id: str, user_id: str | None, limit: int = 50) -> list[dict]:
    uid = _user_uuid(user_id)
    async with org_tx(org_id) as c:
        if uid is None:
            rows = await c.fetch(
                f"SELECT {_COLS} FROM notifications WHERE user_id IS NULL "
                f"ORDER BY created_at DESC LIMIT $1",
                limit,
            )
        else:
            rows = await c.fetch(
                f"SELECT {_COLS} FROM notifications WHERE user_id IS NULL OR user_id=$1 "
                f"ORDER BY created_at DESC LIMIT $2",
                uid,
                limit,
            )
        return [_row(r) for r in rows]


async def unread_count(org_id: str, user_id: str | None) -> int:
    uid = _user_uuid(user_id)
    async with org_tx(org_id) as c:
        if uid is None:
            val = await c.fetchval(
                "SELECT count(*) FROM notifications WHERE read_at IS NULL AND user_id IS NULL",
            )
        else:
            val = await c.fetchval(
                "SELECT count(*) FROM notifications WHERE read_at IS NULL "
                "AND (user_id IS NULL OR user_id=$1)",
                uid,
            )
        return int(val)


async def mark_read(org_id: str, nid: str) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE notifications SET read_at=now() WHERE id=$1 AND read_at IS NULL",
            uuid.UUID(nid),
        )


async def mark_all(org_id: str, user_id: str | None) -> None:
    uid = _user_uuid(user_id)
    async with org_tx(org_id) as c:
        if uid is None:
            await c.execute(
                "UPDATE notifications SET read_at=now() WHERE read_at IS NULL AND user_id IS NULL",
            )
        else:
            await c.execute(
                "UPDATE notifications SET read_at=now() WHERE read_at IS NULL "
                "AND (user_id IS NULL OR user_id=$1)",
                uid,
            )
