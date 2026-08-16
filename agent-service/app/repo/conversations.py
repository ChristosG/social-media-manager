import json
import uuid
from app.db.pool import org_tx
from app.repo import attachments as attachments_repo


async def create_conversation(org_id: str, user_id: str, title: str) -> dict:
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            "INSERT INTO conversations(org_id,user_id,title) VALUES($1,$2,$3) "
            "RETURNING id, title, created_at, updated_at",
            uuid.UUID(org_id), uuid.UUID(user_id), title)
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def list_conversations(org_id: str) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations ORDER BY updated_at DESC LIMIT 100"
        )
    return [
        {
            "id": str(r["id"]),
            "title": r["title"],
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]


async def get_conversation(org_id: str, conversation_id: str) -> dict | None:
    """Fetch a single conversation row, or None if not found / not visible."""
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id=$1",
            uuid.UUID(conversation_id),
        )
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def set_binding(org_id: str, conversation_id: str, *,
                      campaign_id: str | None, post_id: str | None) -> None:
    """Persist the campaign/post this conversation is bound to ("Edit in chat" / "Refine in chat").
    Called whenever a turn carries post_context so every LATER turn (and a reload) inherits it."""
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE conversations SET active_campaign_id=$1, active_post_id=$2 WHERE id=$3",
            uuid.UUID(campaign_id) if campaign_id else None,
            uuid.UUID(post_id) if post_id else None,
            uuid.UUID(conversation_id),
        )


async def get_binding(org_id: str, conversation_id: str) -> dict | None:
    """The campaign/post a conversation is bound to, as {active_campaign_id, active_post_id} (str|None each),
    or None if the conversation isn't found. A follow-up turn with no fresh post_context inherits this."""
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            "SELECT active_campaign_id, active_post_id FROM conversations WHERE id=$1",
            uuid.UUID(conversation_id),
        )
    if row is None:
        return None
    return {
        "active_campaign_id": str(row["active_campaign_id"]) if row["active_campaign_id"] else None,
        "active_post_id": str(row["active_post_id"]) if row["active_post_id"] else None,
    }


async def get_messages(org_id: str, conversation_id: str) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT id, role, content, sources, reasoning, route_reason, learned, created_at FROM messages "
            "WHERE conversation_id=$1 ORDER BY created_at",
            uuid.UUID(conversation_id),
        )
    ids = [str(r["id"]) for r in rows]
    by_msg = await attachments_repo.list_for_messages(org_id, ids)
    return [
        {
            "id": str(r["id"]),
            "conversation_id": conversation_id,
            "role": r["role"],
            "content": r["content"],
            "token_count": None,
            "attachments": by_msg.get(str(r["id"]), []),
            "sources": json.loads(r["sources"]) if r["sources"] else [],
            "reasoning": r["reasoning"],
            "route_reason": r["route_reason"],
            "learned": json.loads(r["learned"]) if r["learned"] else [],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


async def add_message(org_id: str, conversation_id: str, role: str, content: str,
                      sources: list | None = None, reasoning: str | None = None,
                      route_reason: str | None = None, learned: list | None = None) -> str:
    """Insert a message and return its new UUID (as a string)."""
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            "INSERT INTO messages(conversation_id, org_id, role, content, sources, reasoning, route_reason, learned) "
            "VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8::jsonb) RETURNING id",
            uuid.UUID(conversation_id), uuid.UUID(org_id), role, content, json.dumps(sources or []),
            reasoning, route_reason, json.dumps(learned) if learned else None,
        )
        await c.execute(
            "UPDATE conversations SET updated_at=now() WHERE id=$1",
            uuid.UUID(conversation_id),
        )
    return str(row["id"])


async def update_conversation(
    org_id: str,
    conversation_id: str,
    title: str,
) -> dict | None:
    """Update the title (and updated_at) of a conversation; return the updated row or None."""
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            "UPDATE conversations SET title=$1, updated_at=now() "
            "WHERE id=$2 "
            "RETURNING id, title, created_at, updated_at",
            title,
            uuid.UUID(conversation_id),
        )
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def delete_conversation(org_id: str, conversation_id: str) -> bool:
    """Hard-delete a conversation (messages cascade). Returns True if a row was deleted."""
    async with org_tx(org_id) as c:
        result = await c.execute(
            "DELETE FROM conversations WHERE id=$1",
            uuid.UUID(conversation_id),
        )
    # asyncpg returns "DELETE N" where N is row count
    return result.endswith(" 1")
