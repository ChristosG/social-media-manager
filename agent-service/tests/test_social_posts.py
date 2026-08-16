"""Tests for GET /social/posts and list_social_posts repo function (Phase 2 social publishing)."""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import sources as src_repo, documents as doc_repo

pytestmark = pytest.mark.asyncio


async def _mk_social_source(org: str, provider: str = "instagram") -> str:
    s = await src_repo.create_source(org, provider, f"{provider} test source", {})
    return s["id"]


async def test_list_social_posts_newest_first_with_image_url(db_pool):
    org = str(uuid.uuid4())
    sid = await _mk_social_source(org, "instagram")

    now = datetime.now(timezone.utc)
    older = now - timedelta(hours=2)
    newer = now - timedelta(hours=1)

    # Insert two documents — newer first expected in results
    did1, _ = await doc_repo.upsert_document(
        org, sid, "https://instagram.com/p/AAA", "Older post", None,
        older, "hash-older", 100, image_url="https://cdn.example.com/old.jpg")
    did2, _ = await doc_repo.upsert_document(
        org, sid, "https://instagram.com/p/BBB", "Newer post", None,
        newer, "hash-newer", 120, image_url="https://cdn.example.com/new.jpg")

    posts = await doc_repo.list_social_posts(org, "instagram")
    assert len(posts) == 2
    # newest first
    assert posts[0]["url"] == "https://instagram.com/p/BBB"
    assert posts[1]["url"] == "https://instagram.com/p/AAA"
    # image_url carried through
    assert posts[0]["image_url"] == "https://cdn.example.com/new.jpg"
    assert posts[1]["image_url"] == "https://cdn.example.com/old.jpg"
    # source_name present
    assert posts[0]["source_name"] == "instagram test source"
    # published_at is iso string
    assert posts[0]["published_at"] is not None and "T" in posts[0]["published_at"]


async def test_list_social_posts_rls_isolation(db_pool):
    """Posts for one org must not appear when querying another org."""
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    sid_a = await _mk_social_source(org_a, "instagram")
    await doc_repo.upsert_document(
        org_a, sid_a, "https://instagram.com/p/CCC", "A's post", None,
        None, "hash-a", 50, image_url=None)

    posts_b = await doc_repo.list_social_posts(org_b, "instagram")
    assert posts_b == []


async def test_list_social_posts_only_matching_provider(db_pool):
    """facebook source docs must not appear in instagram query."""
    org = str(uuid.uuid4())
    fb_sid = await _mk_social_source(org, "facebook")
    ig_sid = await _mk_social_source(org, "instagram")

    await doc_repo.upsert_document(
        org, fb_sid, "https://facebook.com/post/1", "FB post", None,
        None, "hash-fb", 80, image_url="https://cdn.example.com/fb.jpg")
    await doc_repo.upsert_document(
        org, ig_sid, "https://instagram.com/p/DDD", "IG post", None,
        None, "hash-ig", 80, image_url="https://cdn.example.com/ig.jpg")

    ig_posts = await doc_repo.list_social_posts(org, "instagram")
    assert len(ig_posts) == 1
    assert ig_posts[0]["url"] == "https://instagram.com/p/DDD"

    fb_posts = await doc_repo.list_social_posts(org, "facebook")
    assert len(fb_posts) == 1
    assert fb_posts[0]["url"] == "https://facebook.com/post/1"


async def test_social_posts_api_returns_posts(db_pool):
    org = str(uuid.uuid4())
    sid = await _mk_social_source(org, "instagram")
    now = datetime.now(timezone.utc)
    await doc_repo.upsert_document(
        org, sid, "https://instagram.com/p/EEE", "API test post", None,
        now, "hash-api", 60, image_url="https://cdn.example.com/api.jpg")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/social/posts?provider=instagram",
                         headers={"x-user-id": "u", "x-tenant-id": org})
        assert r.status_code == 200
        data = r.json()
        assert "posts" in data
        assert len(data["posts"]) == 1
        post = data["posts"][0]
        assert post["url"] == "https://instagram.com/p/EEE"
        assert post["image_url"] == "https://cdn.example.com/api.jpg"
        assert post["source_name"] == "instagram test source"


async def test_social_posts_api_invalid_provider(db_pool):
    org = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/social/posts?provider=twitter",
                         headers={"x-user-id": "u", "x-tenant-id": org})
        assert r.status_code == 422


async def test_social_posts_api_requires_identity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/social/posts?provider=instagram")
        assert r.status_code == 401
