import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.sources import ingest
from app.repo import sources as src_repo

pytestmark = pytest.mark.asyncio


def _fake_run_ingest(ran):
    async def run(org, sid):
        ran.append(sid)
        return {"status": "ok", "ingested": 2, "skipped": 0, "failed": 0}
    return run


async def test_refresh_skips_fresh_runs_stale(db_pool, monkeypatch):
    ran = []
    monkeypatch.setattr(ingest, "run_ingest", _fake_run_ingest(ran))
    org = str(uuid.uuid4())
    fresh = await src_repo.create_source(org, "instagram", "IG", {})
    await src_repo.set_state(org, fresh["id"], last_refreshed_at=datetime.now(timezone.utc))
    stale = await src_repo.create_source(org, "facebook", "FB", {})
    await src_repo.set_state(org, stale["id"],
                             last_refreshed_at=datetime.now(timezone.utc) - timedelta(hours=2))

    out = await ingest.refresh_org_social(org)
    assert ran == [stale["id"]]
    assert [r["source_id"] for r in out["refreshed"]] == [stale["id"]]
    assert out["skipped_fresh"] == [fresh["id"]]


async def test_refresh_force_overrides_throttle(db_pool, monkeypatch):
    ran = []
    monkeypatch.setattr(ingest, "run_ingest", _fake_run_ingest(ran))
    org = str(uuid.uuid4())
    fresh = await src_repo.create_source(org, "instagram", "IG", {})
    await src_repo.set_state(org, fresh["id"], last_refreshed_at=datetime.now(timezone.utc))

    out = await ingest.refresh_org_social(org, force=True)
    assert ran == [fresh["id"]]
    assert out["skipped_fresh"] == []


async def test_refresh_provider_filter_and_ignores_web(db_pool, monkeypatch):
    ran = []
    monkeypatch.setattr(ingest, "run_ingest", _fake_run_ingest(ran))
    org = str(uuid.uuid4())
    ig = await src_repo.create_source(org, "instagram", "IG", {})
    await src_repo.create_source(org, "facebook", "FB", {})
    await src_repo.create_source(org, "web", "Blog", {"url": "https://x"})

    out = await ingest.refresh_org_social(org, provider="instagram")
    assert ran == [ig["id"]]
    assert len(out["refreshed"]) == 1


async def test_refresh_api(db_pool, monkeypatch):
    ran = []
    monkeypatch.setattr(ingest, "run_ingest", _fake_run_ingest(ran))
    org = str(uuid.uuid4())
    await src_repo.create_source(org, "instagram", "IG", {})
    transport = ASGITransport(app=app)
    h = {"x-user-id": "u", "x-tenant-id": org}
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/social/refresh", headers=h, json={"force": True})
        assert r.status_code == 200
        body = r.json()
        assert "refreshed" in body and "skipped_fresh" in body
        assert len(ran) == 1
        bad = await ac.post("/social/refresh", headers=h, json={"provider": "twitter"})
        assert bad.status_code == 422
        anon = await ac.post("/social/refresh", json={"force": True})
        assert anon.status_code == 401


async def test_refresh_handles_run_ingest_exception(db_pool, monkeypatch):
    async def boom(org, sid):
        raise RuntimeError("graph down")
    monkeypatch.setattr(ingest, "run_ingest", boom)
    org = str(uuid.uuid4())
    s = await src_repo.create_source(org, "instagram", "IG", {})
    out = await ingest.refresh_org_social(org, force=True)
    assert out["refreshed"] == [
        {"source_id": s["id"], "status": "failed", "ingested": 0, "skipped": 0}
    ]
    assert out["skipped_fresh"] == []


async def test_social_ingest_empty_account_is_ok(db_pool, monkeypatch):
    from app.repo import connections as conn_repo, sources as src_repo
    async def empty_fetch(token, ext_id, n):
        return []
    monkeypatch.setattr(ingest, "fetch_instagram_posts", empty_fetch)
    org = str(uuid.uuid4())
    conn = await conn_repo.create_connection(org, "instagram", "ig-empty", "IG",
                                             token="tok", scopes="instagram_basic")
    src = await src_repo.create_source(org, "instagram", "IG", {}, connection_id=conn["id"])
    r = await ingest.ingest_social_source(org, src["id"])
    assert r["status"] == "ok" and r["ingested"] == 0
    assert (await src_repo.get_source(org, src["id"]))["last_status"] == "ok"
