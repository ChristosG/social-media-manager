import io
import uuid

import pytest
from PIL import Image
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.repo import images as images_repo

pytestmark = pytest.mark.asyncio


def _png_bytes(w=120, h=80, color=(200, 60, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


async def test_upload_image_stores_org_image_and_returns_signed_url(db_pool):
    org = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post(
            "/images/upload",
            headers={"x-user-id": str(uuid.uuid4()), "x-tenant-id": org},
            files={"file": ("mine.png", _png_bytes(), "image/png")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] and body["url"].startswith("/api/v1/img/" + body["id"])
    # The bytes really landed as an org image (publish reads from this table).
    img = await images_repo.get_image(org, body["id"])
    assert img is not None and img["data"][:8] == b"\x89PNG\r\n\x1a\n"


async def test_upload_rejects_non_image(db_pool):
    org = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post(
            "/images/upload",
            headers={"x-user-id": str(uuid.uuid4()), "x-tenant-id": org},
            files={"file": ("evil.svg", b"<svg onload=alert(1)>", "image/svg+xml")},
        )
    assert r.status_code == 415


async def test_upload_reencodes_jpeg_to_png(db_pool):
    """A JPEG upload is decoded and re-encoded to PNG, so we never serve raw client bytes."""
    org = str(uuid.uuid4())
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 120, 200)).save(buf, format="JPEG")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post(
            "/images/upload",
            headers={"x-user-id": str(uuid.uuid4()), "x-tenant-id": org},
            files={"file": ("photo.jpg", buf.getvalue(), "image/jpeg")},
        )
    assert r.status_code == 200
    img = await images_repo.get_image(org, r.json()["id"])
    assert img["data"][:8] == b"\x89PNG\r\n\x1a\n"   # stored as PNG, not the original JPEG
