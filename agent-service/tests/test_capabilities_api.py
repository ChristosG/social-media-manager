import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


def _admin(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org, "X-Roles": "owner"}
def _member(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org, "X-Roles": "member"}


@pytest.mark.usefixtures("db_pool")
async def test_list_effective_includes_globals():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/capabilities?effective=true&kind=platform", headers=_member(org))
    assert r.status_code == 200
    assert any(cap["name"] == "linkedin" for cap in r.json()["capabilities"])


@pytest.mark.usefixtures("db_pool")
async def test_member_cannot_write_admin_can():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        denied = await c.post("/capabilities", headers=_member(org),
                              json={"kind": "platform", "name": "bluesky", "config": {"label": "Bluesky"}})
        assert denied.status_code == 403
        ok = await c.post("/capabilities", headers=_admin(org),
                          json={"kind": "platform", "name": "bluesky", "config": {"label": "Bluesky"}})
        assert ok.status_code == 200 and ok.json()["name"] == "bluesky"


@pytest.mark.usefixtures("db_pool")
async def test_invalid_kind_rejected():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/capabilities", headers=_admin(org), json={"kind": "wormhole", "name": "x", "config": {}})
    assert r.status_code == 422
