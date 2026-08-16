import uuid
import pytest
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio


async def test_global_platforms_seeded_and_visible_to_any_org(db_pool):
    org = str(uuid.uuid4())
    async with org_tx(org) as c:
        rows = await c.fetch("SELECT name FROM capabilities WHERE kind='platform' AND org_id IS NULL")
    names = {r["name"] for r in rows}
    assert {"linkedin", "instagram", "x", "facebook"} <= names


async def test_org_rows_isolated_but_globals_shared(db_pool):
    org_a, org_b = str(uuid.uuid4()), str(uuid.uuid4())
    async with org_tx(org_a) as c:
        await c.execute("INSERT INTO capabilities(org_id, kind, name, config) VALUES($1,'platform','tiktok','{}'::jsonb)",
                        uuid.UUID(org_a))
    async with org_tx(org_b) as c:
        a_rows = await c.fetch("SELECT 1 FROM capabilities WHERE name='tiktok'")
        globals_seen = await c.fetchval("SELECT count(*) FROM capabilities WHERE org_id IS NULL AND kind='platform'")
    assert len(a_rows) == 0
    assert globals_seen >= 4


async def test_npo_app_cannot_insert_global_row(db_pool):
    """WITH CHECK forbids writing a global (org_id NULL) row from an org session."""
    import asyncpg
    org = str(uuid.uuid4())
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with org_tx(org) as c:
            await c.execute("INSERT INTO capabilities(org_id, kind, name, config) VALUES(NULL,'platform','sneaky','{}'::jsonb)")
