import pytest
from datetime import date, datetime, timezone
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.repo import ledger as led, scheduled_posts as sp
from app.repo import campaigns as camp
from app.social.content_hash import content_hash

pytestmark = pytest.mark.asyncio
ORG = "55555555-5555-5555-5555-555555555555"
USER = "66666666-6666-6666-6666-666666666666"
H = {"X-User-Id": USER, "X-Tenant-Id": ORG}
PLANNED_AT = datetime(2026, 7, 1, 11, 0, 0, tzinfo=timezone.utc)


async def test_post_that_is_planned_and_scheduled_appears_once(db_pool):
    p = await led.create_post(ORG, "Leo angle", "Leo angle", status="approved")
    await led.update_post(ORG, p["id"], "approved", "Meet Leo…", None)
    await led.set_planned_at(ORG, p["id"], PLANNED_AT)
    chash = content_hash("Meet Leo…", [])
    await sp.create(ORG, targets=[{"provider": "facebook", "connection_id": None}],
                    caption="Meet Leo…", image_ids=[], content_hash=chash, scheduled_at_now=False,
                    created_by=USER, post_id=p["id"], scheduled_at="2026-07-01T11:00:00+00:00")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        r = await cl.get("/social/calendar?frm=2026-06-29&to=2026-07-05", headers=H)
    items = [i for i in r.json()["items"] if i.get("post_id") == p["id"]]
    assert len(items) == 1
    assert items[0]["stage"] == "scheduled"
    assert items[0]["caption"] == "Meet Leo…"


async def test_campaign_post_item_carries_campaign_id_and_suggestions(db_pool):
    c = await camp.create(ORG, "brief", "facebook",
                          [{"angle": "Leo", "platform": "facebook", "slot_date": date(2026, 7, 2), "slot_at": None}])
    p = await led.create_post(ORG, "Leo", "Leo", status="approved")
    await led.update_post(ORG, p["id"], "approved", "Meet Leo…", None, suggestions=["Shorter", "Add a CTA"])
    await led.set_planned_at(ORG, p["id"], datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc))
    await camp.attach_post(ORG, c["slots"][0]["id"], p["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        r = await cl.get("/social/calendar?frm=2026-06-29&to=2026-07-05", headers=H)
    it = next(i for i in r.json()["items"] if i.get("post_id") == p["id"])
    assert it["campaign_id"] == c["id"]
    assert it["refine_suggestions"] == ["Shorter", "Add a CTA"]
