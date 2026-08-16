import pytest
from app.social import insights_connector as ic

pytestmark = pytest.mark.asyncio


async def test_fb_post_metrics_maps_and_is_resilient(monkeypatch):
    async def fake_get(url, params):
        if params["metric"] == "post_engaged_users":
            raise RuntimeError("dead metric")          # one metric dies
        return {"data": [{"values": [{"value": 100 if params["metric"] == "post_impressions_unique" else 7}]}]}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "p")
    out = await ic.fetch_post_metrics("facebook", "post1", "tok")
    assert out["reach"] == 100 and out["link_clicks"] == 7 and out["engagement"] == 0   # dead → 0, others intact


async def test_ig_post_metrics_maps(monkeypatch):
    async def fake_get(url, params):
        vals = {"reach": 50, "likes": 9, "comments": 2, "total_interactions": 11}
        return {"data": [{"values": [{"value": vals[params["metric"]]}]}]}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "p")
    out = await ic.fetch_post_metrics("instagram", "media1", "tok")
    assert out["reach"] == 50 and out["likes"] == 9 and out["engagement"] == 11


async def test_follower_count_fb_and_failure(monkeypatch):
    async def fake_get(url, params):
        return {"fan_count": 1204}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "p")
    assert await ic.fetch_follower_count("facebook", "page1", "tok") == 1204

    async def boom(url, params):
        raise RuntimeError("nope")
    monkeypatch.setattr(ic, "_graph_get", boom)
    assert await ic.fetch_follower_count("instagram", "ig1", "tok") == 0   # never raises
