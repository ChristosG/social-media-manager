import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


def _h(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


@pytest.mark.usefixtures("db_pool")
async def test_ledger_create_list_status_filter_and_rls():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        p = (await c.post("/ledger", json={"title": "Beach cleanup", "brief": "impact story"}, headers=_h(org))).json()
        assert p["status"] == "suggested"
        await c.put(f"/ledger/{p['id']}", json={"status": "drafted", "platform": "linkedin"}, headers=_h(org))
        drafted = (await c.get("/ledger?status=drafted", headers=_h(org))).json()["posts"]
        assert any(x["id"] == p["id"] and x["platform"] == "linkedin" for x in drafted)
        assert (await c.get("/ledger", headers=_h(str(uuid.uuid4())))).json()["posts"] == []
