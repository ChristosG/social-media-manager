import pytest
from datetime import date
from app.security import context as ctx
from app.repo import campaigns as camp, ledger as led
from app.agent import tools, campaign_fill

pytestmark = pytest.mark.asyncio
ORG = "8b000000-0000-0000-0000-000000000001"


async def _seed(monkeypatch):
    ctx.set_identity("u", ORG)
    async def fake_draft_one(org, angle, platform, profile):
        return (f"caption for {angle}", ["Shorter"], "stories")
    monkeypatch.setattr(campaign_fill, "_draft_one", fake_draft_one)


async def test_get_campaign_lists_slots(db_pool, monkeypatch):
    await _seed(monkeypatch)
    c = await camp.create(ORG, "donations", "facebook",
                          [{"angle": "Leo story", "platform": "facebook", "slot_date": date(2026, 7, 1), "slot_at": None}])
    ctx.active_campaign_var.set(c["id"])
    out = await tools.get_campaign.ainvoke({})
    assert "Leo story" in out


async def test_add_campaign_post_appends_drafted_slot(db_pool, monkeypatch):
    await _seed(monkeypatch)
    c = await camp.create(ORG, "donations", "facebook",
                          [{"angle": "one", "platform": "facebook", "slot_date": date(2026, 7, 1), "slot_at": None}])
    ctx.active_campaign_var.set(c["id"])
    out = await tools.add_campaign_post.ainvoke({"angle": "Volunteer spotlight", "date": "2026-07-04"})
    again = await camp.get(ORG, c["id"])
    assert len(again["slots"]) == 2
    new = [s for s in again["slots"] if s["angle"] == "Volunteer spotlight"][0]
    assert new["post_id"]
    assert (await led.get_post(ORG, new["post_id"]))["content"] == "caption for Volunteer spotlight"


async def test_tools_require_bound_campaign(db_pool, monkeypatch):
    await _seed(monkeypatch)
    ctx.active_campaign_var.set(None)
    out = await tools.add_campaign_post.ainvoke({"angle": "x", "date": "2026-07-04"})
    assert "edit in chat" in out.lower() or "no campaign" in out.lower()
