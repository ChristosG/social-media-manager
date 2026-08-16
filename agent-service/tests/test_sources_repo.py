import uuid
import pytest
from app.repo import sources as repo

pytestmark = pytest.mark.asyncio


async def test_create_list_get_and_state(db_pool):
    org = str(uuid.uuid4())
    s = await repo.create_source(org, "web", "Capital Economy",
                                 {"url": "https://www.capital.gr/oikonomia", "type": "auto", "latest_n": 15})
    assert s["kind"] == "web" and s["config"]["url"].endswith("/oikonomia")
    assert s["last_status"] == "pending"
    got = await repo.get_source(org, s["id"])
    assert got and got["id"] == s["id"]
    assert any(x["id"] == s["id"] for x in await repo.list_sources(org))
    ok = await repo.set_state(org, s["id"], last_status="ok", detected_kind="section",
                              feed_url="https://www.capital.gr/feed", last_error=None)
    assert ok
    assert (await repo.get_source(org, s["id"]))["last_status"] == "ok"


async def test_rls_isolation(db_pool):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    s = await repo.create_source(a, "web", "A", {"url": "http://a"})
    assert await repo.get_source(b, s["id"]) is None
    assert all(x["id"] != s["id"] for x in await repo.list_sources(b))


async def test_create_source_binds_connection_and_lookup(db_pool):
    org = str(uuid.uuid4())
    conn_id = str(uuid.uuid4())
    assert await repo.get_source_by_connection(org, conn_id) is None
    s = await repo.create_source(org, "instagram", "IG Acct", {}, connection_id=conn_id)
    assert s["connection_id"] == conn_id
    got = await repo.get_source_by_connection(org, conn_id)
    assert got is not None and got["id"] == s["id"]
    plain = await repo.create_source(org, "web", "No conn", {"url": "https://x"})
    assert plain["connection_id"] is None


async def test_get_source_by_connection_rls_isolation(db_pool):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    conn_id = str(uuid.uuid4())
    await repo.create_source(a, "facebook", "A Page", {}, connection_id=conn_id)
    assert await repo.get_source_by_connection(b, conn_id) is None
