import uuid
import pytest
from app.db import pool as dbpool


async def _seed(org):
    async with dbpool.org_tx(org) as c:
        await c.execute(
            "INSERT INTO conversations(org_id,user_id,title) VALUES($1,$2,$3)",
            uuid.UUID(org), uuid.uuid4(), f"conv-{org}")


@pytest.mark.usefixtures("db_pool")
async def test_org_cannot_read_other_orgs_rows():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    await _seed(a)
    await _seed(b)
    async with dbpool.org_tx(a) as c:
        rows = await c.fetch("SELECT title FROM conversations")
    titles = {r["title"] for r in rows}
    assert f"conv-{a}" in titles
    assert f"conv-{b}" not in titles   # RLS blocks the cross-org row
