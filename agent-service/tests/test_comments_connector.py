from datetime import datetime, timezone
import httpx
import pytest
from app.social import comments_connector as cc

pytestmark = pytest.mark.asyncio


def _settings():
    return type("S", (), {"meta_app_secret": "sec"})()


async def test_fb_fetch_normalizes_and_filters_since(monkeypatch):
    def handler(req):
        path = req.url.path
        if path.endswith("/published_posts"):
            return httpx.Response(200, json={"data": [{"id": "P1"}, {"id": "P2"}]})
        if path.endswith("/P1/comments"):
            return httpx.Response(200, json={"data": [
                {"id": "C_old", "message": "old", "created_time": "2026-06-01T00:00:00+0000",
                 "from": {"id": "u1", "name": "Sam"}, "permalink_url": "https://fb/c1"},
                {"id": "C_new", "message": " hi ", "created_time": "2026-06-10T00:00:00+0000",
                 "from": {"id": "u2", "name": "Lee"}}]})
        if path.endswith("/P2/comments"):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404, json={"error": {"message": "x"}})
    monkeypatch.setattr(cc, "get_settings", _settings)
    monkeypatch.setattr(cc, "_transport", httpx.MockTransport(handler))
    since = datetime(2026, 6, 5, tzinfo=timezone.utc)
    out = await cc.fetch_comments("facebook", "PAGE", "tok", since=since)
    assert [c["external_id"] for c in out] == ["C_new"]           # old one filtered out
    assert out[0]["message"] == "hi" and out[0]["author_name"] == "Lee"
    assert out[0]["post_external_id"] == "P1"


async def test_ig_fetch_normalizes(monkeypatch):
    def handler(req):
        path = req.url.path
        if path.endswith("/media"):
            return httpx.Response(200, json={"data": [{"id": "M1"}]})
        if path.endswith("/M1/comments"):
            return httpx.Response(200, json={"data": [
                {"id": "IGC1", "text": "love it", "timestamp": "2026-06-10T00:00:00+0000",
                 "username": "fan"}]})
        return httpx.Response(404, json={"error": {"message": "x"}})
    monkeypatch.setattr(cc, "get_settings", _settings)
    monkeypatch.setattr(cc, "_transport", httpx.MockTransport(handler))
    out = await cc.fetch_comments("instagram", "IGUSER", "tok")
    assert out[0]["external_id"] == "IGC1" and out[0]["author_name"] == "fan"
    assert out[0]["message"] == "love it" and out[0]["post_external_id"] == "M1"


async def test_post_reply_fb_and_ig(monkeypatch):
    seen = []
    def handler(req):
        seen.append(req.url.path)
        return httpx.Response(200, json={"id": "NEWREPLY"})
    monkeypatch.setattr(cc, "get_settings", _settings)
    monkeypatch.setattr(cc, "_transport", httpx.MockTransport(handler))
    assert (await cc.post_reply("facebook", "C1", "tok", "thanks"))["id"] == "NEWREPLY"
    assert (await cc.post_reply("instagram", "IGC1", "tok", "thanks"))["id"] == "NEWREPLY"
    assert seen[0].endswith("/C1/comments") and seen[1].endswith("/IGC1/replies")


async def test_error_raises(monkeypatch):
    monkeypatch.setattr(cc, "get_settings", _settings)
    monkeypatch.setattr(cc, "_transport", httpx.MockTransport(
        lambda r: httpx.Response(400, json={"error": {"message": "bad token", "code": 190}})))
    with pytest.raises(cc.CommentError):
        await cc.fetch_comments("facebook", "PAGE", "tok")
