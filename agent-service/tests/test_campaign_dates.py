import json
import uuid
from datetime import date, timedelta

import pytest

from app.agent import tools
from app.repo import campaigns as camp
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


class _Angles:
    async def ainvoke(self, *a, **k):
        return type("M", (), {"content": json.dumps(["angle one", "angle two", "angle three"])})()


async def _plan(monkeypatch, **kw) -> list[date]:
    org = str(uuid.uuid4())
    set_identity(user_id=str(uuid.uuid4()), org_id=org)
    monkeypatch.setattr(tools, "_model", _Angles())
    await tools.plan_campaign.ainvoke({"brief": "boost donations", "count": 3, **kw})
    c = await camp.latest_proposed(org)
    return [date.fromisoformat(s["slot_date"]) for s in c["slots"]]


async def test_wrong_year_start_is_clamped_to_today_or_later(monkeypatch):
    # The LLM guessed a past year (2024). Every slot must land on/after today, not two years ago.
    dates = await _plan(monkeypatch, start="2024-06-11")
    assert dates and all(d >= date.today() for d in dates)


async def test_explicit_future_start_is_respected(monkeypatch):
    future = date.today() + timedelta(days=30)
    dates = await _plan(monkeypatch, start=future.isoformat())
    assert dates[0] == future


async def test_no_start_defaults_to_next_monday(monkeypatch):
    dates = await _plan(monkeypatch, start="")
    assert dates[0] >= date.today() and dates[0].weekday() == 0
