import asyncio
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import ledger as led, memory as mem
from app.repo import insights as ins
from app.repo import post_metrics as pm
from app.social import insights_connector as ic

pytestmark = pytest.mark.usefixtures("db_pool")


def _h(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


async def test_insights_summary_counts_owned_data():
    org = str(uuid.uuid4())
    await led.create_post(org, "a", "b", status="suggested")
    await led.create_post(org, "c", "d", status="drafted")
    await led.create_post(org, "e", "f", status="posted")
    await mem.create_entry(org, "banned_topic", {"topic": "politics"}, key=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/insights/summary", headers=_h(org))
        assert r.status_code == 200
        body = r.json()
        funnel = body["status_funnel"]
        assert funnel.get("suggested") == 1 and funnel.get("drafted") == 1 and funnel.get("posted") == 1
        assert body["learned_count"] >= 1
        assert "posts_per_day" in body
        # Meta block is present but dormant — no connection registered for this fresh org
        assert body["meta_available"] is False
        assert "meta" not in body


async def test_insights_org_scoped():
    org_a, org_b = str(uuid.uuid4()), str(uuid.uuid4())
    await led.create_post(org_a, "only-a", "b", status="posted")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        rb = await c.get("/insights/summary", headers=_h(org_b))
        assert rb.json()["status_funnel"].get("posted", 0) == 0


async def test_insights_meta_dormant_without_connection():
    """An org with zero social connections must get meta_available=False and no 'meta' key."""
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/insights/summary", headers=_h(org))
        assert r.status_code == 200
        body = r.json()
        assert body["meta_available"] is False
        assert "meta" not in body


async def test_meta_block_cached_serves_from_cache_and_invalidates(monkeypatch):
    """The live Meta call happens once per TTL; invalidate_meta() forces the next load to re-fetch."""
    org = str(uuid.uuid4())
    calls = {"n": 0}

    async def fake_meta(_org):
        calls["n"] += 1
        return "ok", {"reach": 1}

    monkeypatch.setattr(ins, "_meta_block", fake_meta)
    s1, _ = await ins._meta_block_cached(org)
    s2, _ = await ins._meta_block_cached(org)          # within TTL → cached, no second live call
    assert s1 == "ok" and s2 == "ok" and calls["n"] == 1

    ins.invalidate_meta(org)
    await ins._meta_block_cached(org)                  # cache cleared → live again
    assert calls["n"] == 2


async def test_meta_block_is_time_boxed(monkeypatch):
    """A slow/hung Meta is bounded by _META_DEADLINE and degrades to 'error' instead of stalling."""
    org = str(uuid.uuid4())

    async def slow_meta(_org):
        await asyncio.sleep(5)
        return "ok", {"reach": 99}

    monkeypatch.setattr(ins, "_meta_block", slow_meta)
    monkeypatch.setattr(ins, "_META_DEADLINE", 0.2)
    status, meta = await ins._meta_block_cached(org)
    assert status == "error" and meta is None


async def test_published_kpi_respects_platform_filter():
    """The published count must reflect the selected platform — All sums, FB and IG each show their own."""
    org = str(uuid.uuid4())
    p1 = await led.create_post(org, "a", "b", status="drafted")
    await led.update_post(org, p1["id"], "posted", "cap a", "facebook")
    p2 = await led.create_post(org, "c", "d", status="drafted")
    await led.update_post(org, p2["id"], "posted", "cap c", "instagram")
    allv = await ins.insights_dashboard(org, platform="all")
    fb = await ins.insights_dashboard(org, platform="facebook")
    ig = await ins.insights_dashboard(org, platform="instagram")
    assert allv["kpis"]["published"]["value"] == 2
    assert fb["kpis"]["published"]["value"] == 1
    assert ig["kpis"]["published"]["value"] == 1


async def test_all_followers_sums_latest_per_provider():
    """The 'All' followers KPI sums the latest snapshot of EACH provider, not a single latest row."""
    org = str(uuid.uuid4())
    await pm.record_follower_snapshot(org, None, "facebook", 3)
    await pm.record_follower_snapshot(org, None, "instagram", 5)
    await pm.record_follower_snapshot(org, None, "facebook", 4)   # newer FB snapshot wins
    d = await ins.insights_dashboard(org, platform="all")
    assert d["kpis"]["followers"]["value"] == 9   # 4 (latest FB) + 5 (latest IG)


async def test_fetch_follower_count_prefers_followers_count(monkeypatch):
    """A FB page with fan_count=0 but followers_count>0 must report followers, not the legacy fan count."""
    async def fake_get(url, params):
        assert "followers_count" in params["fields"]
        return {"followers_count": 7, "fan_count": 0}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "p")
    assert await ic.fetch_follower_count("facebook", "PAGE", "tok") == 7


async def test_import_account_creates_imported_posts_with_metrics(monkeypatch):
    """Importing a connected account's real posts lands them as origin='imported' posts + metric snapshots,
    and is idempotent (a re-import adds nothing)."""
    from app.repo import insights_import as imp
    org = str(uuid.uuid4())

    async def fake_posts(provider, account_id, token, limit=25):
        return [
            {"external_id": "IG_1", "caption": "hello world", "permalink": "p1", "image_url": None,
             "posted_at": "2026-06-01T10:00:00+0000", "media_type": "IMAGE",
             "metrics": {"likes": 5, "comments": 2, "engagement": 7}},
            {"external_id": "IG_2", "caption": "second post", "permalink": "p2", "image_url": None,
             "posted_at": "2026-06-02T10:00:00+0000", "media_type": "IMAGE",
             "metrics": {"likes": 1, "comments": 0, "engagement": 1}},
        ]

    monkeypatch.setattr(ic, "fetch_account_posts", fake_posts)
    conn = {"id": str(uuid.uuid4()), "provider": "instagram", "external_id": "IGACCT", "scopes": ""}

    res = await imp.import_account(org, conn, "tok")
    assert res["imported"] == 2 and res["metrics"] == 2
    posts = await led.list_posts(org)
    assert len(posts) == 2
    assert all(p["origin"] == "imported" and p["status"] == "posted" for p in posts)
    assert {p["external_post_id"] for p in posts} == {"IG_1", "IG_2"}

    res2 = await imp.import_account(org, conn, "tok")   # idempotent — dedups on the Meta id
    assert res2["imported"] == 0
    assert len(await led.list_posts(org)) == 2

    # The imported posts power the published KPI + top posts (ordered by the field-derived engagement).
    d = await ins.insights_dashboard(org, platform="instagram")
    assert d["kpis"]["published"]["value"] == 2
    assert len(d["top_posts"]) == 2
    assert d["top_posts"][0]["engagement"] == 7   # IG_1 (5+2) ranks above IG_2


async def test_fetch_account_posts_reads_ig_engagement_from_fields(monkeypatch):
    """IG likes/comments come from plain media FIELDS (like_count/comments_count), not /insights — so they
    work without the instagram_manage_insights scope."""
    async def fake_get(url, params):
        assert "like_count" in params["fields"] and "comments_count" in params["fields"]
        return {"data": [{"id": "M1", "caption": "hi", "permalink": "p", "timestamp": "2026-06-01T00:00:00+0000",
                          "like_count": 9, "comments_count": 3, "media_type": "IMAGE"}]}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "p")
    rows = await ic.fetch_account_posts("instagram", "IG", "tok")
    assert len(rows) == 1
    assert rows[0]["metrics"] == {"likes": 9, "comments": 3, "engagement": 12}
