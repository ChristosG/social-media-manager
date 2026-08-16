import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api import social as social_api
from app.sources import ingest
from app.repo import connections as conn_repo, sources as src_repo
from app.social import oauth

pytestmark = pytest.mark.asyncio


async def test_ensure_source_creates_once_then_reuses(db_pool, monkeypatch):
    scheduled = []
    monkeypatch.setattr(social_api.ingest, "schedule_ingest", lambda o, s: scheduled.append(s))
    org = str(uuid.uuid4())
    conn = await conn_repo.create_connection(org, "instagram", "ig-1", "Paws IG",
                                             token="tok", scopes="instagram_basic")
    s1 = await social_api.ensure_source_and_ingest(org, conn)
    s2 = await social_api.ensure_source_and_ingest(org, conn)   # rerun == reconnect
    assert s1["id"] == s2["id"]                                  # reused, not duplicated
    assert s1["connection_id"] == conn["id"]
    assert s1["kind"] == "instagram"
    assert scheduled == [s1["id"], s1["id"]]                     # ingest fired both times
    bound = [x for x in await src_repo.list_sources(org) if x["connection_id"] == conn["id"]]
    assert len(bound) == 1


async def test_add_source_is_idempotent(db_pool, monkeypatch):
    monkeypatch.setattr(ingest, "schedule_ingest", lambda o, s: None)
    org = str(uuid.uuid4())
    conn = await conn_repo.create_connection(org, "facebook", "page-1", "Paws Page",
                                             token="tok", scopes="pages_show_list")
    transport = ASGITransport(app=app)
    h = {"x-user-id": "u", "x-tenant-id": org}
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r1 = await ac.post(f"/social/connections/{conn['id']}/sources", headers=h)
        r2 = await ac.post(f"/social/connections/{conn['id']}/sources", headers=h)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]               # same source, no dup
    bound = [x for x in await src_repo.list_sources(org) if x["connection_id"] == conn["id"]]
    assert len(bound) == 1


async def test_callback_auto_creates_sources_and_ingests(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    state = oauth.sign_state(org, "u")
    nonce = oauth.state_nonce(state)
    scheduled = []
    monkeypatch.setattr(social_api.ingest, "schedule_ingest", lambda o, s: scheduled.append(s))

    async def fake_exchange(code): return "LONG-LIVED-TOKEN"
    async def fake_scopes(token): return "instagram_basic,pages_show_list"
    async def fake_pages(token):
        return [{"id": "page-1", "name": "Paws Page", "access_token": "PAGE-TOK",
                 "instagram_business_account": {"id": "ig-1", "username": "paws"}}]
    monkeypatch.setattr(social_api.oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(social_api.oauth, "granted_scopes", fake_scopes)
    monkeypatch.setattr(social_api.oauth, "list_pages", fake_pages)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get(f"/social/callback?code=abc&state={state}",
                         cookies={"social_oauth_nonce": nonce})
        assert r.status_code == 303

    sources = await src_repo.list_sources(org)
    assert sorted(s["kind"] for s in sources) == ["facebook", "instagram"]   # one per connection
    assert all(s["connection_id"] for s in sources)
    assert sorted(scheduled) == sorted(s["id"] for s in sources)             # ingest fired for each


async def test_disconnect_removes_bound_sources_and_docs(db_pool, monkeypatch):
    from app.repo import documents as doc_repo
    monkeypatch.setattr(ingest, "schedule_ingest", lambda o, s: None)
    org = str(uuid.uuid4())
    conn = await conn_repo.create_connection(org, "instagram", "ig-disc", "IG",
                                             token="tok", scopes="instagram_basic")
    src = await social_api.ensure_source_and_ingest(org, conn)
    await doc_repo.upsert_document(org, src["id"], "https://instagram.com/p/DISC", "post",
                                   None, None, "hash-disc", 10)
    assert await doc_repo.count_documents(org, src["id"]) == 1
    transport = ASGITransport(app=app)
    h = {"x-user-id": "u", "x-tenant-id": org}
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.delete(f"/social/connections/{conn['id']}", headers=h)
        assert r.status_code == 200
    assert await src_repo.get_source_by_connection(org, conn["id"]) is None   # source deleted
    assert await doc_repo.count_documents(org, src["id"]) == 0                # docs cascaded


async def test_disconnect_missing_connection_404(db_pool):
    org = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.delete(f"/social/connections/{uuid.uuid4()}",
                            headers={"x-user-id": "u", "x-tenant-id": org})
        assert r.status_code == 404
