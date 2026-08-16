"""Insights quick-fix: the deprecated page_impressions metric is gone, the fetch degrades per-metric, and
None is returned only on a genuine error (so the summary can tell 'no scope' from 'Meta failed')."""
import pytest
from app.social import insights_connector as ic

pytestmark = pytest.mark.asyncio

CONN = {"provider": "facebook", "scopes": "pages_read_engagement", "external_id": "page1"}


async def test_uses_views_metric_not_deprecated_impressions(monkeypatch):
    seen = []
    async def fake_get(url, params):
        seen.append(params["metric"])
        return {"data": [{"values": [{"value": 5}]}]}
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "proof")
    await ic.fetch_page_insights(CONN, token="t")
    assert "page_views_total" in seen            # the live replacement is requested
    assert "page_impressions" not in seen        # the dead metric is no longer requested


async def test_partial_metric_success_still_returns(monkeypatch):
    async def fake_get(url, params):
        if params["metric"] == "page_views_total":
            return {"data": [{"name": "page_views_total", "values": [{"value": 1234}]}]}
        raise RuntimeError("page_post_engagements is deprecated")   # one metric dead
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "proof")
    out = await ic.fetch_page_insights(CONN, token="t")
    assert out == {"impressions": 1234, "engagements": 0}           # not zeroed by the dead metric


async def test_all_metrics_fail_returns_none(monkeypatch):
    async def fake_get(url, params):
        raise RuntimeError("all dead")
    monkeypatch.setattr(ic, "_graph_get", fake_get)
    monkeypatch.setattr(ic, "_proof", lambda t: "proof")
    assert await ic.fetch_page_insights(CONN, token="t") is None    # genuine error → None (→ 'error' status)


async def test_no_scope_returns_none():
    conn = {"provider": "facebook", "scopes": "", "external_id": "page1"}
    assert await ic.fetch_page_insights(conn, token="t") is None     # no scope → None (→ 'no_scope' status)
