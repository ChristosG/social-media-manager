import uuid
import httpx
import pytest
from app.social import graph
from app.repo import sources as sr, connections as cr, documents as dr
from app.sources import ingest, embed

pytestmark = pytest.mark.asyncio


def _mock(json_body):
    return httpx.MockTransport(lambda req: httpx.Response(200, json=json_body))


async def test_fetch_facebook_posts_maps_documents(monkeypatch):
    monkeypatch.setattr(graph, "_transport", _mock({"data": [
        {"id": "p1", "message": "We saved 12 dogs today!", "created_time": "2026-06-01T10:00:00+0000",
         "permalink_url": "https://facebook.com/page/posts/p1"},
        {"id": "p2", "message": "", "created_time": "2026-06-02T10:00:00+0000"},  # empty → skipped
    ]}))
    posts = await graph.fetch_facebook_posts("tok", "page-1", limit=10)
    assert len(posts) == 1 and posts[0]["text"] == "We saved 12 dogs today!"
    assert posts[0]["url"].endswith("/p1")


async def test_fetch_instagram_posts_maps_documents(monkeypatch):
    monkeypatch.setattr(graph, "_transport", _mock({"data": [
        {"id": "m1", "caption": "Adoption Friday! 🎉", "timestamp": "2026-06-03T12:00:00+0000",
         "permalink": "https://instagram.com/p/m1"},
    ]}))
    posts = await graph.fetch_instagram_posts("tok", "ig-1", limit=10)
    assert posts[0]["text"].startswith("Adoption Friday") and posts[0]["url"].endswith("/m1")


async def test_appsecret_proof_is_hmac(monkeypatch):
    monkeypatch.setattr(graph, "get_settings", lambda: type("S", (), {"meta_app_secret": "appsecret"})())
    import hmac, hashlib
    assert graph._appsecret_proof("tok") == hmac.new(b"appsecret", b"tok", hashlib.sha256).hexdigest()


async def test_ingest_social_source_end_to_end(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    conn = await cr.create_connection(org, "instagram", "ig-9", "Our IG", token="tok")
    s = await sr.create_source(org, "instagram", "Our IG", {})
    # link the source to the connection
    await sr.set_state(org, s["id"], **{})  # no-op; set connection_id directly via repo update below
    from app.db.pool import org_tx
    async with org_tx(org) as c:
        await c.execute("UPDATE sources SET connection_id=$1 WHERE id=$2", uuid.UUID(conn["id"]), uuid.UUID(s["id"]))

    async def fake_ig(token, ig_id, limit=15):
        return [{"url": "https://instagram.com/p/a", "title": "t", "text": "Meet Luna 🐶", "published_at": None}]
    async def fake_embed_texts(texts, batch=16):
        return [[0.02] * 2560 for _ in texts]
    monkeypatch.setattr(ingest, "fetch_instagram_posts", fake_ig)
    monkeypatch.setattr(embed, "embed_texts", fake_embed_texts)

    res = await ingest.ingest_social_source(org, s["id"])
    assert res["status"] == "ok" and res["ingested"] == 1
    assert await dr.count_documents(org, s["id"]) == 1
