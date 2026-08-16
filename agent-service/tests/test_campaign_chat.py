import uuid
import json
import pytest
from app.agent import tools
from app.repo import campaigns as camp
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


class _Angles:
    async def ainvoke(self, *a, **k):
        return type("M", (), {"content": json.dumps(["angle one", "angle two", "angle three"])})()


class _Draft:
    async def ainvoke(self, *a, **k):
        return type("M", (), {"content": "A lovely caption. 💧"})()


async def test_replan_keeps_a_single_proposal(monkeypatch):
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    monkeypatch.setattr(tools, "_model", _Angles())
    await tools.plan_campaign.ainvoke({"brief": "first", "count": 2, "start": "2026-07-06"})
    await tools.plan_campaign.ainvoke({"brief": "second", "count": 2, "start": "2026-07-06"})
    proposed = [c for c in await camp.list_campaigns(org) if c["status"] == "proposed"]
    assert len(proposed) == 1                        # re-planning REPLACED, didn't stack duplicates
    assert proposed[0]["brief"] == "second"


async def test_approve_campaign_drafts_latest_proposed(monkeypatch):
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    monkeypatch.setattr(tools, "_model", _Angles())
    await tools.plan_campaign.ainvoke({"brief": "clean water", "count": 2, "start": "2026-07-06"})
    monkeypatch.setattr(tools, "_model", _Draft())
    msg = await tools.approve_campaign.ainvoke({})
    assert "drafted 2" in msg.lower()
    approved = [c for c in await camp.list_campaigns(org) if c["status"] == "approved"]
    assert len(approved) == 1 and all(s["post_id"] for s in approved[0]["slots"])


async def test_approve_with_no_proposal_is_graceful():
    org = str(uuid.uuid4()); set_identity(user_id=str(uuid.uuid4()), org_id=org)
    msg = await tools.approve_campaign.ainvoke({})
    assert "don't see a campaign" in msg.lower()
