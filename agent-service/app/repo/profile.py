import uuid
from app.db.pool import org_tx


async def get_profile(org_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT name,mission,one_liner,audience,regions,default_platform,updated_at FROM org_profile WHERE org_id=$1",
            uuid.UUID(org_id))
    if not r:
        return None
    return {"name": r["name"], "mission": r["mission"], "one_liner": r["one_liner"], "audience": r["audience"],
            "regions": list(r["regions"]), "default_platform": r["default_platform"],
            "updated_at": r["updated_at"].isoformat()}


async def list_programs(org_id: str) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT id, name, description, source_url, updated_at FROM programs WHERE org_id=$1 ORDER BY updated_at",
            uuid.UUID(org_id))
    return [{"id": str(r["id"]), "name": r["name"], "description": r["description"],
             "source_url": r["source_url"], "updated_at": r["updated_at"].isoformat()} for r in rows]


async def create_program(org_id: str, name: str, description: str | None = None,
                         source_url: str | None = None) -> dict:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "INSERT INTO programs(org_id, name, description, source_url) VALUES($1,$2,$3,$4) "
            "RETURNING id,name,description,source_url",
            uuid.UUID(org_id), name, description, source_url)
    return {"id": str(r["id"]), "name": r["name"], "description": r["description"], "source_url": r["source_url"]}


async def update_program(org_id: str, program_id: str, name: str | None = None,
                         description: str | None = None, source_url: str | None = None) -> bool:
    sets, args, i = [], [], 1
    for col, val in (("name", name), ("description", description), ("source_url", source_url)):
        if val is not None:
            sets.append(f"{col}=${i}"); args.append(val); i += 1
    if not sets:
        return False
    sets.append("updated_at=now()")
    args.append(uuid.UUID(program_id))
    async with org_tx(org_id) as c:
        res = await c.execute(f"UPDATE programs SET {','.join(sets)} WHERE id=${i}", *args)
    return res.endswith(" 1")


async def delete_program(org_id: str, program_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM programs WHERE id=$1", uuid.UUID(program_id))
    return res.endswith(" 1")


async def replace_programs(org_id: str, programs: list[dict]) -> int:
    """Replace the org's programs (research is authoritative). programs: [{name, description, source_url?}]."""
    async with org_tx(org_id) as c:
        await c.execute("DELETE FROM programs WHERE org_id=$1", uuid.UUID(org_id))
        for p in programs:
            if not p.get("name"):
                continue
            await c.execute(
                "INSERT INTO programs(org_id, name, description, source_url) VALUES($1,$2,$3,$4)",
                uuid.UUID(org_id), str(p["name"])[:120], (p.get("description") or None), (p.get("source_url") or None))
    return len([p for p in programs if p.get("name")])


async def upsert_profile(org_id: str, mission: str | None, one_liner: str | None,
                         audience: str | None, regions: list[str] | None,
                         default_platform: str | None = None, name: str | None = None) -> dict:
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO org_profile(org_id,mission,one_liner,audience,regions,default_platform,name) "
            "VALUES($1,$2,$3,$4,COALESCE($5,'{}'::text[]),$6,$7) "
            "ON CONFLICT (org_id) DO UPDATE SET mission=COALESCE($2,org_profile.mission), "
            "one_liner=COALESCE($3,org_profile.one_liner), audience=COALESCE($4,org_profile.audience), "
            "regions=COALESCE($5,org_profile.regions), "
            "default_platform=COALESCE($6,org_profile.default_platform), "
            "name=COALESCE($7,org_profile.name), updated_at=now()",
            uuid.UUID(org_id), mission, one_liner, audience, regions, default_platform, name)
    return await get_profile(org_id)
