import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.sources import ingest

pytestmark = pytest.mark.asyncio


async def test_run_ingest_single_flight(db_pool, monkeypatch):
    calls = []
    async def fake_ingest_source(o, s):
        calls.append(s); return {"status": "ok", "ingested": 1, "skipped": 0, "failed": 0}
    monkeypatch.setattr(ingest, "ingest_source", fake_ingest_source)
    ingest._ingesting.add("dup")
    try:
        r = await ingest.run_ingest("o", "dup")
        assert r["status"] == "skipped" and calls == []
    finally:
        ingest._ingesting.discard("dup")
    r = await ingest.run_ingest("o", "x")
    assert r["status"] == "ok" and calls == ["x"]


async def test_create_source_schedules_background_ingest(db_pool, monkeypatch):
    scheduled = []
    monkeypatch.setattr(ingest, "schedule_ingest", lambda o, s: scheduled.append(s))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/sources", headers={"x-user-id": "u", "x-tenant-id": str(uuid.uuid4())},
                          json={"name": "Cap", "url": "https://www.capital.gr/oikonomia"})
        assert r.status_code == 200
        assert scheduled == [r.json()["id"]]   # ingest-on-add scheduled exactly the new source
