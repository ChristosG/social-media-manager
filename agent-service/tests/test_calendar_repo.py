import uuid
from datetime import datetime, timezone, date
import pytest
from app.repo import scheduled_posts as sp, ledger as led

pytestmark = pytest.mark.usefixtures("db_pool")


async def test_list_in_range_filters_by_scheduled_at():
    org = str(uuid.uuid4())
    await sp.create(org, targets=[{"connection_id": "c", "provider": "facebook", "external_id": "p"}],
                    caption="in range", image_ids=[], content_hash="h1",
                    scheduled_at_now=False, created_by=None, post_id=None,
                    scheduled_at=datetime(2026, 7, 10, 12, tzinfo=timezone.utc))
    await sp.create(org, targets=[{"connection_id": "c", "provider": "facebook", "external_id": "p"}],
                    caption="out of range", image_ids=[], content_hash="h2",
                    scheduled_at_now=False, created_by=None, post_id=None,
                    scheduled_at=datetime(2026, 8, 1, 12, tzinfo=timezone.utc))
    got = await sp.list_in_range(org, datetime(2026, 7, 1, tzinfo=timezone.utc),
                                 datetime(2026, 7, 31, tzinfo=timezone.utc))
    assert [r["caption"] for r in got] == ["in range"]


async def test_reschedule_only_pending():
    org = str(uuid.uuid4())
    s = await sp.create(org, targets=[{"connection_id": "c", "provider": "facebook", "external_id": "p"}],
                        caption="cap", image_ids=[], content_hash="h3",
                        scheduled_at_now=False, created_by=None, post_id=None,
                        scheduled_at=datetime(2026, 7, 10, 12, tzinfo=timezone.utc))
    new = datetime(2026, 7, 12, 9, tzinfo=timezone.utc)
    assert await sp.reschedule(org, s["id"], new) is True
    got = await sp.get(org, s["id"])
    assert got["scheduled_at"].startswith("2026-07-12")
    await sp.claim(org, s["id"])
    assert await sp.reschedule(org, s["id"], datetime(2026, 7, 20, tzinfo=timezone.utc)) is False


async def test_planned_for_roundtrip_and_range():
    org = str(uuid.uuid4())
    p = await led.create_post(org, "Future idea", "brief", status="suggested")
    assert await led.set_planned_for(org, p["id"], date(2026, 7, 15)) is True
    got = await led.list_planned_in_range(org, date(2026, 7, 1), date(2026, 7, 31))
    assert [x["title"] for x in got] == ["Future idea"]
    assert got[0]["planned_for"] == "2026-07-15"
