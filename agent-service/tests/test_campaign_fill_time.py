import uuid
import pytest
from datetime import date, datetime, timezone
from app.repo import campaigns as camp, ledger as led
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


class _Fake:
    async def ainvoke(self, *a, **k):
        return type("M", (), {"content": "Caption here. 💧"})()


async def test_fill_uses_slot_time_and_returns_structured(monkeypatch):
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    from app.agent import tools
    monkeypatch.setattr(tools, "_model", _Fake())
    c = await camp.create(org, "push", "instagram", [
        {"slot_date": date(2026, 7, 6), "slot_at": datetime(2026, 7, 6, 22, 30, tzinfo=timezone.utc),
         "angle": "evening story", "platform": "instagram"},
    ])
    from app.agent.campaign_fill import fill_campaign
    res = await fill_campaign(org, c["id"])
    assert res["filled"] == 1 and res["failed"] == 0 and res["total"] == 1
    full = await camp.get(org, c["id"])
    assert full["fill_status"] == "done" and full["status"] == "approved"
    post = await led.get_post(org, full["slots"][0]["post_id"])
    assert post["planned_at"].startswith("2026-07-06T22:30")   # the slot's real time, not a hardcoded noon


async def test_fill_records_slot_error_not_swallowed(monkeypatch):
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    from app.agent import tools

    class _Boom:
        async def ainvoke(self, *a, **k):
            raise RuntimeError("model down")

    monkeypatch.setattr(tools, "_model", _Boom())
    c = await camp.create(org, "push", "instagram", [
        {"slot_date": date(2026, 7, 6), "angle": "x", "platform": "instagram"},
    ])
    from app.agent.campaign_fill import fill_campaign
    res = await fill_campaign(org, c["id"])
    assert res["filled"] == 0 and res["failed"] == 1
    assert "model down" in res["errors"][0]["message"]          # the real error surfaces, not swallowed
    full = await camp.get(org, c["id"])
    assert full["fill_status"] == "error" and full["fill_error"]
