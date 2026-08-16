import uuid, pytest
from datetime import date
from app.repo import campaigns as camp, ledger as led
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


class _FakeDraft:
    async def astream(self, *a, **k):
        for piece in ["Clean water ", "changes everything. ", "Join us. 💧"]:
            yield type("C", (), {"content": piece})()
    async def ainvoke(self, *a, **k):
        return type("M", (), {"content": "Clean water changes everything. Join us. 💧"})()


async def test_fill_drafts_each_slot_onto_calendar(monkeypatch):
    org = str(uuid.uuid4())
    set_identity(user_id=str(uuid.uuid4()), org_id=org)
    from app.agent import tools
    monkeypatch.setattr(tools, "_model", _FakeDraft())
    c = await camp.create(org, "2-week push", "instagram", [
        {"slot_date": date(2026, 7, 6), "angle": "family story", "platform": "instagram"},
        {"slot_date": date(2026, 7, 9), "angle": "the science", "platform": "instagram"},
    ])
    from app.agent.campaign_fill import fill_campaign
    res = await fill_campaign(org, c["id"])
    assert res["filled"] == 2
    full = await camp.get(org, c["id"])
    assert full["status"] == "approved"
    for slot in full["slots"]:
        assert slot["post_id"] is not None
        # the linked post is drafted, on the slot date, instagram
    posts = await led.list_posts(org)
    drafted = [p for p in posts if p["status"] == "drafted"]
    assert len(drafted) == 2
    assert all(p["planned_for"] in ("2026-07-06", "2026-07-09") for p in drafted)
    assert all(p["platform"] == "instagram" for p in drafted)
