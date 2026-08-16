import httpx
import pytest
from app.social import publish

pytestmark = pytest.mark.asyncio


def _settings():
    return type("S", (), {"meta_app_id": "appid", "meta_app_secret": "sec"})()


async def test_ig_single_publish_two_step(monkeypatch):
    calls = []
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        q = req.url.query.decode()
        if req.url.path.endswith("/media") and "media_publish" not in req.url.path:
            return httpx.Response(200, json={"id": "CONTAINER1"})
        if req.url.path.endswith("/CONTAINER1") and "status_code" in q:
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if req.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "MEDIA1"})
        if req.url.path.endswith("/MEDIA1"):
            return httpx.Response(200, json={"permalink": "https://instagram.com/p/abc/"})
        return httpx.Response(404, json={"error": {"message": "unexpected", "code": 100}})
    monkeypatch.setattr(publish, "get_settings", _settings)
    monkeypatch.setattr(publish, "_transport", httpx.MockTransport(handler))
    res = await publish.publish_to_target(provider="instagram", target_id="IG1", page_token="tok",
                                          caption="hi", image_jpg_urls=["https://x/img.jpg"])
    assert res["permalink"] == "https://instagram.com/p/abc/"
    assert any(p.endswith("/media_publish") for p in calls)


async def test_ig_requires_image(monkeypatch):
    monkeypatch.setattr(publish, "get_settings", _settings)
    monkeypatch.setattr(publish, "_transport", httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(publish.PublishPermanentError):
        await publish.publish_to_target(provider="instagram", target_id="IG1",
                                        page_token="tok", caption="hi", image_jpg_urls=[])


async def test_ig_carousel(monkeypatch):
    def handler(req):
        q = req.url.query.decode()
        if req.url.path.endswith("/media") and "media_publish" not in req.url.path:
            # both child + carousel container creations
            return httpx.Response(200, json={"id": "C"})
        if req.url.path.endswith("/C") and "status_code" in q:
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if req.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "M"})
        if req.url.path.endswith("/M"):
            return httpx.Response(200, json={"permalink": "https://instagram.com/p/car/"})
        return httpx.Response(404, json={"error": {"message": "x", "code": 100}})
    monkeypatch.setattr(publish, "get_settings", _settings)
    monkeypatch.setattr(publish, "_transport", httpx.MockTransport(handler))
    res = await publish.publish_to_target("instagram", "IG1", "tok", "cap",
                                          ["https://x/1.jpg", "https://x/2.jpg", "https://x/3.jpg"])
    assert res["permalink"].endswith("/car/")


async def test_fb_text_only(monkeypatch):
    def handler(req):
        assert req.url.path.endswith("/feed")
        return httpx.Response(200, json={"id": "PAGE_post1", "permalink_url": "https://fb.com/post1"})
    monkeypatch.setattr(publish, "get_settings", _settings)
    monkeypatch.setattr(publish, "_transport", httpx.MockTransport(handler))
    res = await publish.publish_to_target("facebook", "PAGE", "tok", "hello", [])
    assert "fb.com/post1" in res["permalink"]


async def test_fb_single_image(monkeypatch):
    def handler(req):
        assert req.url.path.endswith("/photos")
        return httpx.Response(200, json={"id": "PH1", "post_id": "PAGE_p1"})
    monkeypatch.setattr(publish, "get_settings", _settings)
    monkeypatch.setattr(publish, "_transport", httpx.MockTransport(handler))
    res = await publish.publish_to_target("facebook", "PAGE", "tok", "cap", ["https://x/1.jpg"])
    assert res["permalink"]


async def test_fb_multi_image(monkeypatch):
    seen = []
    def handler(req):
        seen.append(req.url.path)
        if req.url.path.endswith("/photos"):
            return httpx.Response(200, json={"id": "PH%d" % len(seen)})
        if req.url.path.endswith("/feed"):
            return httpx.Response(200, json={"id": "P1", "permalink_url": "https://fb.com/P1"})
        return httpx.Response(404, json={"error": {"message": "x", "code": 100}})
    monkeypatch.setattr(publish, "get_settings", _settings)
    monkeypatch.setattr(publish, "_transport", httpx.MockTransport(handler))
    res = await publish.publish_to_target("facebook", "PAGE", "tok", "cap",
                                          ["https://x/1.jpg", "https://x/2.jpg"])
    assert res["permalink"].endswith("/P1")
    assert sum(p.endswith("/photos") for p in seen) == 2   # both uploaded unpublished
