import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import conversation_drafts as drafts

pytestmark = pytest.mark.asyncio


async def test_upserts_are_field_isolated(db_pool):
    org = str(uuid.uuid4()); conv = str(uuid.uuid4())
    assert await drafts.get_draft(org, conv) is None
    await drafts.upsert_caption(org, conv, "Save a life this Saturday! 🐾")
    img = str(uuid.uuid4())
    await drafts.upsert_images(org, conv, [img])
    d = await drafts.get_draft(org, conv)
    assert d["caption"] == "Save a life this Saturday! 🐾"   # caption preserved when images set
    assert d["image_ids"] == [img]
    await drafts.upsert_caption(org, conv, "New caption")    # changing caption keeps images
    d = await drafts.get_draft(org, conv)
    assert d["caption"] == "New caption" and d["image_ids"] == [img]


async def test_upsert_images_accumulates_across_turns(db_pool):
    """Every image generated in the chat is kept (order-preserving, de-duplicated) so the publish
    dialog can offer the whole set; the user removes the ones they don't want."""
    org = str(uuid.uuid4()); conv = str(uuid.uuid4())
    a, b, c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await drafts.upsert_images(org, conv, [a, b])     # turn 1: 2 images
    await drafts.upsert_images(org, conv, [c])        # turn 2: +1 image
    await drafts.upsert_images(org, conv, [b, c])     # turn 3: dupes ignored
    d = await drafts.get_draft(org, conv)
    assert d["image_ids"] == [a, b, c]                # accumulated, order preserved, no dupes


async def test_upsert_images_replace_overwrites(db_pool):
    org = str(uuid.uuid4()); conv = str(uuid.uuid4())
    a, b, c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await drafts.upsert_images(org, conv, [a, b])
    await drafts.upsert_images(org, conv, [c], replace=True)
    d = await drafts.get_draft(org, conv)
    assert d["image_ids"] == [c]


async def test_draft_rls_isolation(db_pool):
    a, b = str(uuid.uuid4()), str(uuid.uuid4()); conv = str(uuid.uuid4())
    await drafts.upsert_caption(a, conv, "A's draft")
    assert await drafts.get_draft(b, conv) is None


async def test_draft_endpoint_returns_signed_image_urls(db_pool):
    org = str(uuid.uuid4()); conv = str(uuid.uuid4()); img = str(uuid.uuid4())
    await drafts.upsert_caption(org, conv, "Caption here")
    await drafts.upsert_images(org, conv, [img])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get(f"/conversations/{conv}/draft", headers={"x-user-id": "u", "x-tenant-id": org})
        assert r.status_code == 200
        d = r.json()["draft"]
        assert d["caption"] == "Caption here"
        assert len(d["images"]) == 1 and d["images"][0]["id"] == img
        assert d["images"][0]["url"].startswith("/api/v1/img/" + img)


async def test_draft_endpoint_null_when_absent(db_pool):
    org = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get(f"/conversations/{uuid.uuid4()}/draft", headers={"x-user-id": "u", "x-tenant-id": org})
        assert r.status_code == 200 and r.json()["draft"] is None
