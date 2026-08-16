import json
import uuid
from app.db.pool import org_tx

ALLOWED_KINDS = {"brand_voice","banned_topic","content_pillar","cta_pref","hashtag_pref","style_rule","fact"}

_COLS = "id,kind,key,value,source,active,pending_review,updated_at"


def _row(r: dict) -> dict:
    return {"id": str(r["id"]), "kind": r["kind"], "key": r["key"], "value": json.loads(r["value"]),
            "source": r["source"], "active": r["active"], "pending_review": r["pending_review"],
            "updated_at": r["updated_at"].isoformat()}


async def list_entries(org_id: str, kind: str | None = None, include_pending: bool = False) -> list[dict]:
    """Active memory for the org. By DEFAULT excludes pending_review entries — this is the prompt-building
    read, so quarantined (unapproved) memory never reaches the model. Studio passes include_pending=True
    to show them for approval, badged via the pending_review field."""
    q = f"SELECT {_COLS} FROM memory_entries WHERE active"
    if not include_pending:
        q += " AND NOT pending_review"
    args: list = []
    if kind:
        q += f" AND kind=${len(args) + 1}"; args.append(kind)
    q += " ORDER BY updated_at DESC"
    async with org_tx(org_id) as c:
        rows = await c.fetch(q, *args)
    return [_row(r) for r in rows]


async def org_pillars(org_id: str) -> list[str]:
    """The org's configured content-pillar names. Same source + extraction as graph/context.py:50-53:
    active, non-pending memory of kind='content_pillar', name read from value.name (falling back to the
    entry key). Returns [] when none are configured — callers fall back to DEFAULT_PILLARS."""
    entries = await list_entries(org_id, "content_pillar")
    names = [(e["value"].get("name", e.get("key")) if isinstance(e["value"], dict) else e["value"])
             for e in entries]
    return [str(n) for n in names if n]


async def list_pending(org_id: str) -> list[dict]:
    """Active entries awaiting human review (learned while untrusted external content was in-context)."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            f"SELECT {_COLS} FROM memory_entries WHERE active AND pending_review ORDER BY updated_at DESC")
    return [_row(r) for r in rows]


async def create_entry(org_id: str, kind: str, value: dict, key: str | None, source: str = "manual",
                       created_by: str | None = None, pending_review: bool = False) -> dict:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"invalid kind: {kind}")
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            f"INSERT INTO memory_entries(org_id,kind,key,value,source,created_by,pending_review) "
            f"VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING {_COLS}",
            uuid.UUID(org_id), kind, key, json.dumps(value), source,
            uuid.UUID(created_by) if created_by else None, pending_review)
    return _row(row)


async def approve_entry(org_id: str, entry_id: str) -> bool:
    """Clear the quarantine on a learned entry so it starts shaping prompts."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE memory_entries SET pending_review=false, updated_at=now() WHERE id=$1 AND pending_review",
            uuid.UUID(entry_id))
    return res.endswith(" 1")


async def update_entry(org_id: str, entry_id: str, value: dict | None, active: bool | None) -> bool:
    sets, args, i = [], [], 1
    if value is not None:
        sets.append(f"value=${i}::jsonb"); args.append(json.dumps(value)); i += 1
    if active is not None:
        sets.append(f"active=${i}"); args.append(active); i += 1
    if not sets:
        return False
    sets.append("updated_at=now()")
    args.append(uuid.UUID(entry_id))
    async with org_tx(org_id) as c:
        res = await c.execute(f"UPDATE memory_entries SET {','.join(sets)} WHERE id=${i}", *args)
    return res.endswith(" 1")


async def delete_entry(org_id: str, entry_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM memory_entries WHERE id=$1", uuid.UUID(entry_id))
    return res.endswith(" 1")
