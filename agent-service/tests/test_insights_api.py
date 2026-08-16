"""Task 4 — aggregated insights dashboard API + per-post drill-down + throttled refresh.

Seeds two posts (one facebook, one instagram) with per-post metric snapshots and a follower snapshot,
then exercises the new /insights/summary shape, the per-post series, and the refresh throttle.
"""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.repo import ledger as led, post_metrics as pm, org_settings as os_repo
from app.repo import jobs as jobs_repo
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio


def _h(org):
    return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _seed(org):
    """Two posts with one latest metric snapshot each, plus a follower snapshot. Returns (fb_id, ig_id)."""
    fb = await led.create_post(org, "FB post", "brief", status="suggested")
    await led.update_post(org, fb["id"], "posted", "facebook caption here", "facebook")
    await pm.record_snapshot(org, fb["id"], None, "facebook", "ext-fb-1",
                             {"reach": 100, "engagement": 10, "link_clicks": 4})

    ig = await led.create_post(org, "IG post", "brief", status="suggested")
    await led.update_post(org, ig["id"], "posted", "instagram caption here", "instagram")
    await pm.record_snapshot(org, ig["id"], None, "instagram", "ext-ig-1",
                             {"reach": 50, "engagement": 8})

    async with org_tx(org) as c:
        await c.execute(
            "INSERT INTO audience_snapshots(org_id, connection_id, provider, followers) "
            "VALUES($1, NULL, 'facebook', $2)",
            uuid.UUID(org), 1234)
    return fb["id"], ig["id"]


async def test_summary_returns_aggregated_dashboard(db_pool):
    org = str(uuid.uuid4())
    fb_id, ig_id = await _seed(org)
    async with await _client() as cl:
        r = await cl.get("/insights/summary?platform=all&range=30", headers=_h(org))
    assert r.status_code == 200
    body = r.json()

    kpis = body["kpis"]
    # both posts counted: reach 100 + 50 = 150, engagement 10 + 8 = 18, link_clicks 4 + 0 = 4
    assert kpis["reach"]["value"] == 150
    assert "delta_pct" in kpis["reach"]
    assert kpis["engagement"]["value"] == 18
    assert kpis["link_clicks"]["value"] == 4
    assert kpis["followers"]["value"] == 1234
    assert kpis["published"]["value"] == 2

    assert isinstance(body["series"], list)

    top = body["top_posts"]
    assert len(top) == 2
    # ordered by engagement desc → FB (10) before IG (8)
    assert top[0]["post_id"] == fb_id
    assert top[0]["reach"] == 100 and top[0]["engagement"] == 10
    assert top[0]["caption"] == "facebook caption here"
    assert top[1]["post_id"] == ig_id

    assert "updated_at" in body
    assert "meta_status" in body


async def test_summary_platform_filter(db_pool):
    org = str(uuid.uuid4())
    await _seed(org)
    async with await _client() as cl:
        r = await cl.get("/insights/summary?platform=facebook", headers=_h(org))
    assert r.status_code == 200
    body = r.json()
    # only the FB snapshot's metrics counted → reach 100, not 150
    assert body["kpis"]["reach"]["value"] == 100
    assert body["kpis"]["engagement"]["value"] == 10
    assert len(body["top_posts"]) == 1
    assert body["top_posts"][0]["provider"] == "facebook"


async def test_post_series_drilldown(db_pool):
    org = str(uuid.uuid4())
    fb_id, _ = await _seed(org)
    # a second, later snapshot for the same post → the series has two points
    await pm.record_snapshot(org, fb_id, None, "facebook", "ext-fb-1",
                             {"reach": 120, "engagement": 14, "link_clicks": 6})
    async with await _client() as cl:
        r = await cl.get(f"/insights/posts/{fb_id}", headers=_h(org))
    assert r.status_code == 200
    series = r.json()
    assert isinstance(series, list) and len(series) == 2
    # ordered by captured_at asc → first snapshot (reach 100) then the later one (reach 120)
    assert series[0]["reach"] == 100
    assert series[1]["reach"] == 120
    assert all("captured_at" in p and "engagement" in p for p in series)


async def test_refresh_is_throttled(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    await _seed(org)

    calls = {"n": 0}
    orig_enqueue = jobs_repo.enqueue

    async def counting_enqueue(*a, **k):
        calls["n"] += 1
        return await orig_enqueue(*a, **k)

    monkeypatch.setattr(jobs_repo, "enqueue", counting_enqueue)

    async with await _client() as cl:
        r1 = await cl.post("/insights/refresh", headers=_h(org))
        assert r1.status_code == 200
        b1 = r1.json()
        assert b1["enqueued"] is True
        assert isinstance(b1["cooldown_seconds"], int)

        # immediate second call → throttled, no new enqueue
        r2 = await cl.post("/insights/refresh", headers=_h(org))
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["enqueued"] is False
        assert b2["cooldown_seconds"] > 0

    # the throttle timestamp is set, and the second call did not enqueue again
    assert await os_repo.insights_refreshed_at(org) is not None
    first_call_count = calls["n"]
    assert first_call_count >= 1  # at least one enqueue happened on the first call
    # second call must not have added more enqueues beyond the first call's total
    # (re-run to be explicit about the invariant we care about)
    async with await _client() as cl:
        r3 = await cl.post("/insights/refresh", headers=_h(org))
        assert r3.json()["enqueued"] is False
    assert calls["n"] == first_call_count
