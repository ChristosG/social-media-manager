import uuid, json, pytest
from datetime import date, timedelta
from app.agent import tools
from app.repo import campaigns as camp
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


class _Fake:
    async def ainvoke(self, *a, **k):
        class M:
            content = json.dumps(["A family's clean water story", "The science of BioSand",
                                  "Community committee spotlight", "Why maintenance matters"])
        return M()


async def test_plan_campaign_persists_proposed(monkeypatch):
    org = str(uuid.uuid4())
    set_identity(user_id=str(uuid.uuid4()), org_id=org)
    monkeypatch.setattr(tools, "_model", _Fake())
    # Must be a FUTURE date, computed from today rather than hardcoded: plan_campaign deliberately clamps
    # any past start forward to today (it can't trust an LLM-supplied year). A literal date silently
    # becomes a past date as time passes, and the test then asserts against the clamp instead of the
    # behaviour it means to pin — that an explicit start IS honoured.
    start = (date.today() + timedelta(days=7)).isoformat()
    msg = await tools.plan_campaign.ainvoke({"brief": "2-week clean water awareness push", "count": 3,
                                             "platform": "instagram", "start": start, "cadence_days": 3})
    assert "campaign" in msg.lower()
    rows = await camp.list_campaigns(org)
    assert len(rows) == 1
    full = await camp.get(org, rows[0]["id"])
    assert full["status"] == "proposed" and len(full["slots"]) == 3
    assert full["slots"][0]["slot_date"] == start
    assert full["slots"][0]["platform"] == "instagram"


async def test_campaigns_api_list(monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    org = str(uuid.uuid4())
    from datetime import date
    await camp.create(org, "x", "instagram", [{"slot_date": date(2026,7,6), "angle": "a", "platform": "instagram"}])
    h = {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/campaigns", headers=h)
        assert r.status_code == 200 and len(r.json()["campaigns"]) == 1
        cid = r.json()["campaigns"][0]["id"]
        assert (await c.get(f"/campaigns/{cid}", headers=h)).json()["campaign"]["brief"] == "x"
