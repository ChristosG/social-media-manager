import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


def _h(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


@pytest.mark.usefixtures("db_pool")
async def test_memory_crud_and_org_scoped():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/memory", json={"kind": "brand_voice", "value": {"descriptor": "warm, grassroots"}}, headers=_h(org))
        assert r.status_code == 200
        eid = r.json()["id"]
        r = await c.get("/memory?kind=brand_voice", headers=_h(org))
        assert any(e["value"]["descriptor"] == "warm, grassroots" for e in r.json()["entries"])
        r2 = await c.get("/memory", headers=_h(str(uuid.uuid4())))
        assert r2.json()["entries"] == []
        assert (await c.put(f"/memory/{eid}", json={"active": False}, headers=_h(org))).status_code == 200
        assert (await c.delete(f"/memory/{eid}", headers=_h(org))).status_code == 200


@pytest.mark.usefixtures("db_pool")
async def test_memory_invalid_kind_422():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/memory", json={"kind": "nope", "value": {}}, headers=_h(org))
        assert r.status_code == 422
