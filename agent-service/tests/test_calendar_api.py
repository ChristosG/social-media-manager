import uuid
from datetime import datetime, timezone, date
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import scheduled_posts as sp, ledger as led

pytestmark = pytest.mark.usefixtures("db_pool")


def _h(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


async def test_calendar_merges_scheduled_and_planned():
    org = str(uuid.uuid4())
    await sp.create(org, targets=[{"connection_id": "c", "provider": "facebook", "external_id": "p"}],
                    caption="scheduled one", image_ids=[], content_hash="hh",
                    scheduled_at_now=False, created_by=None, post_id=None,
                    scheduled_at=datetime(2026, 7, 10, 12, tzinfo=timezone.utc))
    p = await led.create_post(org, "planned idea", "b", status="suggested")
    await led.set_planned_for(org, p["id"], date(2026, 7, 15))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/social/calendar?frm=2026-07-01&to=2026-07-31", headers=_h(org))
        assert r.status_code == 200
        items = r.json()["items"]
        stages = {i["stage"] for i in items}
        assert "scheduled" in stages
        assert any(i["stage"] in ("drafting", "drafted", "approved") and i["title"] == "planned idea"
                   for i in items)


async def test_plan_a_ledger_date():
    org = str(uuid.uuid4())
    p = await led.create_post(org, "x", "b", status="suggested")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.put(f"/ledger/{p['id']}/plan", json={"planned_for": "2026-08-01"}, headers=_h(org))
        assert r.status_code == 200


async def test_calendar_includes_suggested_slots():
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/social/calendar?frm=2026-07-06&to=2026-07-12&platform=instagram",
                        headers={"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org})
        sug = r.json()["suggested"]
        assert isinstance(sug, list) and len(sug) == 3 and all("2026-07" in s for s in sug)
