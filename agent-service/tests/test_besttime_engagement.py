"""Engagement-aware best-time: once an org has enough measured posts, its own strongest (weekday, hour)
windows lead the calendar suggestions; below the threshold it stays on the static priors."""
import json
import uuid
from datetime import date, datetime, timezone
import pytest
from app.repo import insights as ins, ledger as led
from app.db.pool import org_tx
from app.agent.besttime import suggested_slots, PLATFORM_WINDOWS

pytestmark = pytest.mark.asyncio


def _org() -> str:
    return str(uuid.uuid4())   # shared no-truncate DB → fresh org per test


async def _post_at(org, when: datetime, engagement: int):
    p = await led.create_post(org, "p", "p", status="posted")
    await led.update_post(org, p["id"], "posted", "caption", "facebook")
    await led.set_planned_at(org, p["id"], when)
    async with org_tx(org) as c:
        await c.execute(
            "INSERT INTO post_metrics(org_id, post_id, provider, metrics) VALUES($1,$2,'facebook',$3::jsonb)",
            uuid.UUID(org), uuid.UUID(p["id"]), json.dumps({"engagement": engagement}))


async def test_best_windows_none_below_threshold(db_pool):
    org = _org()
    # a Wednesday (2026-07-01 is a Wednesday) 18:00 post — but only 3 measured (< min_posts=8)
    for _ in range(3):
        await _post_at(org, datetime(2026, 7, 1, 18, tzinfo=timezone.utc), 100)
    assert await ins.best_windows(org, "facebook") is None


async def test_best_windows_surfaces_org_top_slot(db_pool):
    org = _org()
    # 8 high-engagement posts on Wednesday 18:00 (weekday 2, hour 18) → should top the windows
    for _ in range(8):
        await _post_at(org, datetime(2026, 7, 1, 18, tzinfo=timezone.utc), 500)
    # a couple of low-engagement Monday 09:00 posts
    for _ in range(2):
        await _post_at(org, datetime(2026, 6, 29, 9, tzinfo=timezone.utc), 5)
    wins = await ins.best_windows(org, "facebook")
    assert wins is not None
    assert wins[0] == (2, 18)            # Wednesday 18:00 leads (weekday 0=Mon → Wed=2)


def test_suggested_slots_leads_with_org_windows():
    ws = date(2026, 6, 29)               # a Monday
    slots = suggested_slots("facebook", ws, count=3, org_windows=[(2, 18)])
    # the org's Wed-18:00 slot must be present; remainder filled from the static priors
    assert any(s.endswith("T18:00:00") for s in slots)
    assert len(slots) == 3


def test_suggested_slots_falls_back_to_priors_without_org():
    ws = date(2026, 6, 29)
    slots = suggested_slots("facebook", ws, count=3)
    assert len(slots) == 3               # unchanged behaviour when no org windows
