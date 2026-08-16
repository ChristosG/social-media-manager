import json
import uuid
from app.db.pool import org_tx

ALLOWED_KINDS = {"platform", "content_type", "research_source", "skill_prompt", "skill_tool"}


def _row(r) -> dict:
    return {"id": str(r["id"]), "org_id": str(r["org_id"]) if r["org_id"] else None,
            "kind": r["kind"], "name": r["name"], "config": json.loads(r["config"]),
            "enabled": r["enabled"], "is_global": r["org_id"] is None,
            "updated_at": r["updated_at"].isoformat()}


async def list_effective(org_id: str, kind: str | None = None) -> list[dict]:
    """Global defaults merged with org rows: an org row overrides the global of the same (kind,name),
    and a disabled override hides the global. Disabled-filtering happens AFTER override selection."""
    inner = ("SELECT DISTINCT ON (kind, name) id, org_id, kind, name, config, enabled, updated_at "
             "FROM capabilities "
             "WHERE (org_id = current_setting('app.org', true)::uuid OR org_id IS NULL)")
    args: list = []
    if kind:
        inner += " AND kind = $1"; args.append(kind)
    inner += " ORDER BY kind, name, (org_id IS NOT NULL) DESC"  # org row (NOT NULL) wins
    q = f"SELECT * FROM ({inner}) w WHERE w.enabled ORDER BY kind, name"
    async with org_tx(org_id) as c:
        rows = await c.fetch(q, *args)
    return [_row(r) for r in rows]


async def list_all(org_id: str, kind: str | None = None) -> list[dict]:
    """Raw visible rows (globals + own), no merge — for Studio editing."""
    q = "SELECT id, org_id, kind, name, config, enabled, updated_at FROM capabilities WHERE true"
    args: list = []
    if kind:
        q += " AND kind = $1"; args.append(kind)
    q += " ORDER BY kind, name, (org_id IS NOT NULL)"
    async with org_tx(org_id) as c:
        rows = await c.fetch(q, *args)
    return [_row(r) for r in rows]


async def create_capability(org_id: str, kind: str, name: str, config: dict,
                            created_by: str | None = None) -> dict:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"invalid kind: {kind}")
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "INSERT INTO capabilities(org_id, kind, name, config, created_by) VALUES($1,$2,$3,$4,$5) "
            "RETURNING id, org_id, kind, name, config, enabled, updated_at",
            uuid.UUID(org_id), kind, name, json.dumps(config),
            uuid.UUID(created_by) if created_by else None)
    return _row(r)


async def update_capability(org_id: str, cap_id: str, config: dict | None = None,
                            enabled: bool | None = None, name: str | None = None) -> bool:
    sets, args, i = [], [], 1
    if config is not None:  sets.append(f"config=${i}::jsonb"); args.append(json.dumps(config)); i += 1
    if enabled is not None: sets.append(f"enabled=${i}");       args.append(enabled);            i += 1
    if name is not None:    sets.append(f"name=${i}");          args.append(name);               i += 1
    if not sets:
        return False
    sets.append("updated_at=now()")
    args.append(uuid.UUID(cap_id))
    async with org_tx(org_id) as c:
        res = await c.execute(f"UPDATE capabilities SET {','.join(sets)} WHERE id=${i}", *args)
    return res.endswith(" 1")


async def delete_capability(org_id: str, cap_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM capabilities WHERE id=$1", uuid.UUID(cap_id))
    return res.endswith(" 1")


async def resolve_platform(org_id: str, name: str) -> tuple[str, dict] | None:
    """Resolve a platform by name/label from the org's effective registry; fall back to built-in
    defaults — UNLESS the org explicitly disabled that platform, in which case it stays hidden."""
    key = (name or "").strip().lower()
    for p in await list_effective(org_id, "platform"):
        if p["name"].lower() == key or str(p["config"].get("label", "")).lower() == key:
            return p["name"], p["config"]
    # Don't let the hardcoded fallback resurrect a built-in the org has explicitly disabled.
    disabled = {r["name"].lower() for r in await list_all(org_id, "platform") if not r["enabled"]}
    if key in disabled:
        return None
    from app.agent.platforms import PLATFORMS
    return (key, PLATFORMS[key]) if key in PLATFORMS else None
