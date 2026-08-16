import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.sources import ingest

pytestmark = pytest.mark.asyncio


async def test_add_list_refresh_and_documents(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    headers = {"x-user-id": "u", "x-tenant-id": org}

    async def fake_ingest(o, sid):
        return {"status": "ok", "ingested": 1, "skipped": 0, "failed": 0}
    monkeypatch.setattr(ingest, "ingest_source", fake_ingest)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/sources", headers=headers,
                          json={"name": "Cap", "url": "https://www.capital.gr/oikonomia"})
        assert r.status_code == 200
        sid = r.json()["id"]
        r = await ac.get("/sources", headers=headers)
        assert any(s["id"] == sid for s in r.json()["sources"])
        r = await ac.post(f"/sources/{sid}/refresh", headers=headers)
        assert r.status_code == 200 and r.json()["status"] == "ok"
        r = await ac.get(f"/sources/{sid}/documents", headers=headers)
        assert r.status_code == 200 and "documents" in r.json()


async def test_stats_endpoint_returns_per_source_counts(db_pool):
    org = str(uuid.uuid4())
    headers = {"x-user-id": "u", "x-tenant-id": org}
    from app.repo import sources as src_repo, documents as doc_repo
    sid = (await src_repo.create_source(org, "web", "S", {"url": "http://s"}))["id"]
    did, _ = await doc_repo.upsert_document(org, sid, "http://a", "A", None, None, "h", 10)
    await doc_repo.replace_chunks(org, did, [(0, "x", [0.1] * 2560)])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/sources/stats", headers=headers)
        assert r.status_code == 200
        assert r.json()["stats"][sid] == {"documents": 1, "chunks": 1}


async def test_requires_identity(db_pool):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        assert (await ac.get("/sources")).status_code == 401
