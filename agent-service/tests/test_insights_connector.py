import pytest
from app.social import insights_connector as ic


def test_no_scope_is_dormant():
    conn = {"provider": "facebook", "scopes": "pages_manage_posts", "external_id": "p", "id": "x"}
    assert ic.insights_capable(conn) is False


def test_capable_with_read_engagement():
    conn = {"provider": "facebook", "scopes": "pages_read_engagement,pages_show_list", "external_id": "p"}
    assert ic.insights_capable(conn) is True


def test_ig_capable_with_manage_insights():
    conn = {"provider": "instagram", "scopes": "instagram_manage_insights", "external_id": "i"}
    assert ic.insights_capable(conn) is True


@pytest.mark.asyncio
async def test_fetch_maps_metrics(monkeypatch):
    # New contract: one /insights call PER metric (so a single deprecation can't zero the rest).
    async def fake_get(url, params):
        val = {"page_views_total": 1234, "page_post_engagements": 56}[params["metric"]]
        return {"data": [{"values": [{"value": val}]}]}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "proof")
    conn = {"provider": "facebook", "scopes": "pages_read_engagement", "external_id": "p"}
    out = await ic.fetch_page_insights(conn, token="t")
    assert out["impressions"] == 1234 and out["engagements"] == 56


@pytest.mark.asyncio
async def test_fetch_returns_none_without_scope(monkeypatch):
    conn = {"provider": "facebook", "scopes": "pages_manage_posts", "external_id": "p"}
    assert await ic.fetch_page_insights(conn, token="t") is None
