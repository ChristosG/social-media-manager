import pytest
from datetime import date
from app.repo import campaigns as camp, ledger as led

pytestmark = pytest.mark.asyncio
ORG = "8a000000-0000-0000-0000-000000000001"


async def test_add_slot_appends_at_next_position(db_pool):
    c = await camp.create(ORG, "b", "facebook",
                          [{"angle": "one", "platform": "facebook", "slot_date": date(2026, 7, 1), "slot_at": None}])
    slot = await camp.add_slot(ORG, c["id"], angle="two", slot_date=date(2026, 7, 3),
                               slot_at=None, platform="facebook")
    assert slot["angle"] == "two" and slot["position"] == 1
    again = await camp.get(ORG, c["id"])
    assert [s["angle"] for s in again["slots"]] == ["one", "two"]


async def test_remove_slot_deletes_it(db_pool):
    c = await camp.create(ORG, "b", "facebook",
                          [{"angle": "one", "platform": "facebook", "slot_date": date(2026, 7, 1), "slot_at": None},
                           {"angle": "two", "platform": "facebook", "slot_date": date(2026, 7, 2), "slot_at": None}])
    sid = c["slots"][0]["id"]
    assert await camp.remove_slot(ORG, c["id"], sid) is True
    again = await camp.get(ORG, c["id"])
    assert [s["angle"] for s in again["slots"]] == ["two"]
    assert await camp.remove_slot(ORG, c["id"], sid) is False


async def test_slot_in_campaign_guard(db_pool):
    c = await camp.create(ORG, "b", "facebook",
                          [{"angle": "one", "platform": "facebook", "slot_date": date(2026, 7, 1), "slot_at": None}])
    assert await camp.slot_in_campaign(ORG, c["id"], c["slots"][0]["id"]) is True
    assert await camp.slot_in_campaign(ORG, c["id"], "8a000000-0000-0000-0000-0000000000ff") is False
