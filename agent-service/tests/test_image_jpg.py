"""Tests for JPEG variant on the signed /img route.

Instagram requires JPEG; the route currently serves PNG only.
These tests exercise ?fmt=jpg conversion and confirm no regression on PNG.
"""
import io
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from PIL import Image

from app.main import app
from app.repo import images as images_repo
from app.security.img_sign import image_url

pytestmark = pytest.mark.asyncio


def _make_png_bytes(width: int = 1080, height: int = 1080) -> bytes:
    """Create a solid-colour RGBA PNG as test fixture data."""
    img = Image.new("RGBA", (width, height), color=(255, 127, 0, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _store_png(org_id: str) -> str:
    """Insert a test PNG row via the real images-repo and return its id."""
    data = _make_png_bytes()
    image_id = await images_repo.create_image(
        org_id=org_id,
        prompt="test image",
        enhanced_prompt=None,
        data=data,
        width=1080,
        height=1080,
        steps=20,
        cfg=7.0,
        seed=42,
        sampler_name=None,
        platform=None,
        fmt="png",
        created_by=None,
    )
    return image_id


async def test_jpeg_variant_returns_jpeg(db_pool):
    """GET /img/<id>?...&fmt=jpg must return image/jpeg with a valid JPEG body."""
    org = str(uuid.uuid4())
    image_id = await _store_png(org)

    # image_url produces /api/v1/img/... (nginx strips /api/v1 prefix before ASGI);
    # for ASGI tests we strip it ourselves.
    signed_path = image_url(image_id, org).replace("/api/v1", "", 1)
    url = signed_path + "&fmt=jpg"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(url)

    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    assert r.headers["content-type"] == "image/jpeg", (
        f"expected image/jpeg, got {r.headers['content-type']}"
    )
    # Verify the body is genuinely a JPEG
    Image.open(io.BytesIO(r.content)).verify()


async def test_png_still_served_without_fmt(db_pool):
    """No regression: omitting fmt=jpg must still return image/png."""
    org = str(uuid.uuid4())
    image_id = await _store_png(org)

    signed_path = image_url(image_id, org).replace("/api/v1", "", 1)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(signed_path)

    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    assert r.headers["content-type"] == "image/png", (
        f"expected image/png, got {r.headers['content-type']}"
    )


async def test_jpeg_bad_sig_is_403(db_pool):
    """HMAC sig still enforced even when fmt=jpg is appended."""
    org = str(uuid.uuid4())
    image_id = await _store_png(org)

    url = f"/img/{image_id}?o={org}&s=badsignature&fmt=jpg"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(url)

    assert r.status_code == 403
