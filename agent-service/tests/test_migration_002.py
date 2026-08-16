import uuid
import pytest
from app.db import pool as dbpool


@pytest.mark.usefixtures("db_pool")
async def test_memory_and_posts_rls_isolated():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    async with dbpool.org_tx(a) as c:
        await c.execute("INSERT INTO memory_entries(org_id,kind,value) VALUES($1,'brand_voice',$2)",
                        uuid.UUID(a), '{"descriptor":"warm"}')
        await c.execute("INSERT INTO posts(org_id,title) VALUES($1,'A-post')", uuid.UUID(a))
    async with dbpool.org_tx(b) as c:
        await c.execute("INSERT INTO posts(org_id,title) VALUES($1,'B-post')", uuid.UUID(b))
    async with dbpool.org_tx(a) as c:
        titles = {r["title"] for r in await c.fetch("SELECT title FROM posts")}
        kinds = {r["kind"] for r in await c.fetch("SELECT kind FROM memory_entries")}
    assert "A-post" in titles and "B-post" not in titles
    assert kinds == {"brand_voice"}
