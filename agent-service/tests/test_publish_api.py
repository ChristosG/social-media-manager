import uuid, pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import connections as cr
from app.repo import scheduled_posts as sp

pytestmark = pytest.mark.asyncio


async def _seed_ig(org):
    return await cr.create_connection(org, "instagram", "IG1", "@x", token="tok",
                                      scopes="instagram_basic,instagram_content_publish")


async def test_publish_rejects_ig_without_image(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _seed_ig(org)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                          json={"targets": [conn["id"]], "caption": "hi", "image_ids": []})
    assert r.status_code == 422


async def test_publish_rejects_non_publishable(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    conn = await cr.create_connection(org, "instagram", "IG2", "@y", token="t",
                                      scopes="instagram_basic")  # no publish scope
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                          json={"targets": [conn["id"]], "caption": "hi", "image_ids": [str(uuid.uuid4())]})
    assert r.status_code == 422


async def test_publish_now_runs_and_returns(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _seed_ig(org)
    from app.api import publish as papi
    async def fake_run(org_id, sp_id):
        await sp.finish(org_id, sp_id, "published", {conn["id"]: {"id": "M1", "permalink": "https://x/p"}})
    monkeypatch.setattr(papi, "run_one", fake_run)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                          json={"targets": [conn["id"]], "caption": "hi", "image_ids": [str(uuid.uuid4())]})
    assert r.status_code == 200 and r.json()["status"] == "published"


async def test_publish_scheduled_returns_scheduled(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _seed_ig(org)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                          json={"targets": [conn["id"]], "caption": "hi", "image_ids": [str(uuid.uuid4())],
                                "scheduled_at": "2999-01-01T00:00:00+00:00"})
    assert r.status_code == 200 and r.json()["status"] == "scheduled"


async def test_duplicate_guard_409_then_confirm(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _seed_ig(org)
    from app.api import publish as papi
    async def fake_run(org_id, sp_id):
        await sp.finish(org_id, sp_id, "published", {conn["id"]: {"id": "M", "permalink": "p"}})
    monkeypatch.setattr(papi, "run_one", fake_run)
    img = [str(uuid.uuid4())]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r1 = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                           json={"targets": [conn["id"]], "caption": "dup", "image_ids": img})
        assert r1.status_code == 200
        r2 = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                           json={"targets": [conn["id"]], "caption": "dup", "image_ids": img})
        assert r2.status_code == 409                       # identical content already published
        r3 = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                           json={"targets": [conn["id"]], "caption": "dup", "image_ids": img, "confirm": True})
        assert r3.status_code == 200                       # confirm overrides


async def test_list_and_cancel_scheduled(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _seed_ig(org)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/social/publish", headers={"x-user-id": user, "x-tenant-id": org},
                          json={"targets": [conn["id"]], "caption": "later", "image_ids": [str(uuid.uuid4())],
                                "scheduled_at": "2999-01-01T00:00:00+00:00"})
        sid = r.json()["id"]
        lst = await ac.get("/social/scheduled", headers={"x-user-id": user, "x-tenant-id": org})
        assert any(it["id"] == sid for it in lst.json()["items"])
        d = await ac.delete(f"/social/scheduled/{sid}", headers={"x-user-id": user, "x-tenant-id": org})
        assert d.status_code == 200
