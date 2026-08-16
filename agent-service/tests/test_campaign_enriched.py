import uuid
from datetime import date, timedelta

import pytest

from app.api.campaigns import _enriched
from app.repo import campaigns as camp, ledger as led, scheduled_posts as sp
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


async def _seed_campaign_with_drafted_post(org: str):
    c = await camp.create(org, "boost donations", "instagram",
                          [{"slot_date": date.today(), "angle": "Meet the team", "platform": "instagram"}])
    slot = c["slots"][0]
    p = await led.create_post(org, "Meet the team", "Meet the team", status="drafting",
                              idea_key=f"camp-{slot['id']}")
    await led.update_post(org, p["id"], "drafted", "Meet the women of the Water Committee.", "instagram")
    await camp.attach_post(org, slot["id"], p["id"])
    return c["id"], slot["id"], p["id"]


async def test_enriched_attaches_post_and_drafted_lifecycle():
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    cid, _slot_id, _pid = await _seed_campaign_with_drafted_post(org)
    out = await _enriched(org, await camp.get(org, cid))
    slot = out["slots"][0]
    assert slot["post"]["caption"] == "Meet the women of the Water Committee."
    assert slot["post"]["images"] == []
    assert slot["lifecycle"]["stage"] == "drafted"
    assert out["progress"] == {"total": 1, "drafted": 1, "approved": 0,
                               "scheduled": 0, "posted": 0, "failed": 0}


async def test_approve_post_advances_lifecycle_to_approved():
    from app.api.campaigns import approve_post, approve_all_posts
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); set_identity(user_id=user, org_id=org)
    cid, _slot_id, pid = await _seed_campaign_with_drafted_post(org)
    res = await approve_post(cid, pid, (user, org))
    assert res == {"ok": True, "status": "approved"}
    out = await _enriched(org, await camp.get(org, cid))
    assert out["slots"][0]["lifecycle"]["stage"] == "approved"
    assert out["progress"]["approved"] == 1 and out["progress"]["drafted"] == 0
    # idempotent + bulk are no-ops once approved
    assert (await approve_all_posts(cid, (user, org)))["approved"] == 0


async def test_approve_post_rejects_foreign_post():
    from fastapi import HTTPException
    from app.api.campaigns import approve_post
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); set_identity(user_id=user, org_id=org)
    cid, _slot_id, _pid = await _seed_campaign_with_drafted_post(org)
    with pytest.raises(HTTPException) as e:
        await approve_post(cid, str(uuid.uuid4()), (user, org))   # post id not in this campaign
    assert e.value.status_code == 404


async def test_schedule_approved_skips_when_no_connected_account():
    from app.api.campaigns import approve_post, schedule_approved
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); set_identity(user_id=user, org_id=org)
    cid, _slot_id, pid = await _seed_campaign_with_drafted_post(org)
    await approve_post(cid, pid, (user, org))            # eligible only once approved (the F-C gate)
    res = await schedule_approved(cid, (user, org))
    assert res["scheduled"] == 0                          # org has no connections → nothing scheduled
    assert res["skipped"] and res["skipped"][0]["post_id"] == pid
    assert res["skipped"][0]["reason"].startswith("no connected")


async def test_schedule_approved_ignores_unapproved_posts():
    from app.api.campaigns import schedule_approved
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); set_identity(user_id=user, org_id=org)
    cid, _slot_id, _pid = await _seed_campaign_with_drafted_post(org)   # left 'drafted' (not approved)
    res = await schedule_approved(cid, (user, org))
    assert res["scheduled"] == 0 and res["skipped"] == []   # drafted-but-unapproved posts are not eligible


async def test_enriched_reflects_scheduled_post():
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    cid, _slot_id, pid = await _seed_campaign_with_drafted_post(org)
    future = (date.today() + timedelta(days=2)).isoformat() + "T12:00:00+00:00"
    await sp.create(org, targets=[{"provider": "instagram", "connection_id": str(uuid.uuid4())}],
                    caption="cap", image_ids=[], content_hash="hash-" + pid[:8],
                    scheduled_at_now=False, created_by=None, post_id=pid, scheduled_at=future)
    out = await _enriched(org, await camp.get(org, cid))
    assert out["slots"][0]["lifecycle"]["stage"] == "scheduled"
    assert out["progress"]["scheduled"] == 1


async def test_enriched_undrafted_slot_is_drafting():
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    c = await camp.create(org, "brief", "instagram",
                          [{"slot_date": date.today(), "angle": "angle", "platform": "instagram"}])
    out = await _enriched(org, await camp.get(org, c["id"]))
    assert out["slots"][0]["post"] is None
    assert out["slots"][0]["lifecycle"]["stage"] == "drafting"
