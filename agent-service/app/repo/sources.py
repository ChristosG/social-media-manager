import json
import uuid
from app.db.pool import org_tx

_COLS = ("id, org_id, kind, name, config, connection_id, enabled, cadence, detected_kind, "
         "feed_url, last_refreshed_at, last_status, last_error, next_due_at, created_at, updated_at")


def _source(r) -> dict:
    return {"id": str(r["id"]), "org_id": str(r["org_id"]), "kind": r["kind"], "name": r["name"],
            "config": json.loads(r["config"]) if isinstance(r["config"], str) else r["config"],
            "connection_id": str(r["connection_id"]) if r["connection_id"] else None,
            "enabled": r["enabled"], "cadence": r["cadence"], "detected_kind": r["detected_kind"],
            "feed_url": r["feed_url"],
            "last_refreshed_at": r["last_refreshed_at"].isoformat() if r["last_refreshed_at"] else None,
            "last_status": r["last_status"], "last_error": r["last_error"],
            "next_due_at": r["next_due_at"].isoformat() if r["next_due_at"] else None,
            "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat()}


async def create_source(org_id: str, kind: str, name: str, config: dict, cadence: str = "daily",
                        connection_id: str | None = None) -> dict:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"INSERT INTO sources(org_id, kind, name, config, cadence, connection_id) "
            f"VALUES($1,$2,$3,$4,$5,$6) RETURNING {_COLS}",
            uuid.UUID(org_id), kind, name, json.dumps(config), cadence,
            uuid.UUID(connection_id) if connection_id else None)
    return _source(r)


async def list_sources(org_id: str, kind: str | None = None) -> list[dict]:
    q = f"SELECT {_COLS} FROM sources"
    args: list = []
    if kind:
        q += " WHERE kind=$1"; args.append(kind)
    q += " ORDER BY created_at DESC"
    async with org_tx(org_id) as c:
        rows = await c.fetch(q, *args)
    return [_source(r) for r in rows]


async def get_source(org_id: str, source_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_COLS} FROM sources WHERE id=$1", uuid.UUID(source_id))
    return _source(r) if r else None


async def get_source_by_connection(org_id: str, connection_id: str | None) -> dict | None:
    """Return the source bound to a connection (first match) or None. connection_id is expected
    unique per org — enforced at the app layer (ensure_source_and_ingest), not by a DB constraint."""
    if not connection_id:
        return None
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_COLS} FROM sources WHERE connection_id=$1",
                             uuid.UUID(connection_id))
    return _source(r) if r else None


async def set_state(org_id: str, source_id: str, **fields) -> bool:
    """Update machine-written state columns. Accepts: last_status, last_error, detected_kind,
    feed_url, last_refreshed_at, next_due_at, enabled, name, config."""
    allowed = {"last_status", "last_error", "detected_kind", "feed_url", "last_refreshed_at",
               "next_due_at", "enabled", "name", "config"}
    sets, args, i = [], [], 1
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "config":
            sets.append(f"config=${i}::jsonb"); args.append(json.dumps(v))
        else:
            sets.append(f"{k}=${i}"); args.append(v)
        i += 1
    if not sets:
        return False
    sets.append("updated_at=now()")
    args.append(uuid.UUID(source_id))
    async with org_tx(org_id) as c:
        res = await c.execute(f"UPDATE sources SET {','.join(sets)} WHERE id=${i}", *args)
    return res.endswith(" 1")


async def delete_source(org_id: str, source_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM sources WHERE id=$1", uuid.UUID(source_id))
    return res.endswith(" 1")


async def delete_sources_by_connection(org_id: str, connection_id: str) -> int:
    """Delete every source bound to a connection (their documents cascade via FK). Returns the count.
    Used by disconnect so a later reconnect re-ingests fresh instead of orphaning sources/documents."""
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM sources WHERE connection_id=$1", uuid.UUID(connection_id))
    return int(res.rsplit(" ", 1)[-1]) if res.startswith("DELETE") else 0
