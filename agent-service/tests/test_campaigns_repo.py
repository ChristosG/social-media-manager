import uuid
from datetime import date
import pytest
from app.repo import campaigns as camp

pytestmark = pytest.mark.usefixtures("db_pool")


async def test_create_with_slots_and_get():
    org = str(uuid.uuid4())
    c = await camp.create(org, "2-week clean water push", "instagram", [
        {"slot_date": date(2026, 7, 6), "angle": "family story", "platform": "instagram"},
        {"slot_date": date(2026, 7, 9), "angle": "the science of BioSand", "platform": "instagram"},
    ])
    got = await camp.get(org, c["id"])
    assert got["brief"].startswith("2-week") and got["status"] == "proposed"
    assert [s["angle"] for s in got["slots"]] == ["family story", "the science of BioSand"]
    assert got["slots"][0]["slot_date"] == "2026-07-06"


async def test_list_and_org_scoped():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    await camp.create(a, "A campaign", "x", [{"slot_date": date(2026, 7, 6), "angle": "z", "platform": "x"}])
    assert len(await camp.list_campaigns(a)) == 1
    assert await camp.list_campaigns(b) == []


async def test_approve_sets_status():
    org = str(uuid.uuid4())
    c = await camp.create(org, "c", "x", [{"slot_date": date(2026, 7, 6), "angle": "z", "platform": "x"}])
    assert await camp.set_status(org, c["id"], "approved") is True
    assert (await camp.get(org, c["id"]))["status"] == "approved"


async def test_attach_post_to_slot():
    org = str(uuid.uuid4())
    from app.repo import ledger as led
    c = await camp.create(org, "c", "x", [{"slot_date": date(2026, 7, 6), "angle": "z", "platform": "x"}])
    slot_id = c["slots"][0]["id"]
    p = await led.create_post(org, "t", "b")
    assert await camp.attach_post(org, slot_id, p["id"]) is True
    got = await camp.get(org, c["id"])
    assert got["slots"][0]["post_id"] == p["id"]
