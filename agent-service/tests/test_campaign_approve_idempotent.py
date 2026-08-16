import uuid
from datetime import date

import pytest

from app.repo import campaigns as camp, ledger as led
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


async def _new_campaign(org: str) -> str:
    c = await camp.create(org, "boost", "instagram",
                          [{"slot_date": date.today(), "angle": "a", "platform": "instagram"}])
    return c["id"]


async def test_try_begin_fill_is_won_once():
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    cid = await _new_campaign(org)
    first = await camp.try_begin_fill(org, cid)
    second = await camp.try_begin_fill(org, cid)   # already 'filling'
    assert first is True and second is False


async def test_dedup_create_post_is_idempotent_for_a_slot():
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    key = f"camp-{uuid.uuid4()}"
    a = await led.create_post(org, "angle", "angle", status="drafting", idea_key=key, dedup=True)
    b = await led.create_post(org, "angle", "angle", status="drafting", idea_key=key, dedup=True)
    assert a["id"] == b["id"]   # second call returns the existing live row, no duplicate, no raise


async def test_begin_fill_marks_filling_and_enqueues_one_job():
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); set_identity(user_id=user, org_id=org)
    cid = await _new_campaign(org)
    job1 = await camp.begin_fill(org, cid, user)
    job2 = await camp.begin_fill(org, cid, user)   # double-click: same live job, no duplicate
    assert job1 and job1["kind"] == "campaign_fill" and job1["payload"]["campaign_id"] == cid
    assert job1["payload"]["user_id"] == user
    assert job2 and job2["id"] == job1["id"]       # idempotent enqueue (deduped per campaign)
    assert (await camp.get(org, cid))["fill_status"] == "filling"
