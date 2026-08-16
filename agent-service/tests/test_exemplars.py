"""Exemplars: top-performing posts are fed into the draft writer, but only once there's enough measured
history (>=6 posts) so small-N noise can't mislead the model, and never as wording to copy."""
import json
import uuid
import pytest
from app.repo import insights as ins, ledger as led
from app.db.pool import org_tx
from app.agent.drafting import build_draft_prompt

pytestmark = pytest.mark.asyncio


def _fresh_org() -> str:
    # The test DB is shared and never truncated; a fresh org per test avoids cross-run row accumulation
    # (post_metrics from a prior run would otherwise break the <6-measured guard + the top-N ordering).
    return str(uuid.uuid4())


async def _post_with_engagement(org, caption, engagement):
    p = await led.create_post(org, caption[:40], caption, status="posted")
    await led.update_post(org, p["id"], "posted", caption, None)
    async with org_tx(org) as c:
        await c.execute(
            "INSERT INTO post_metrics(org_id, post_id, provider, metrics) VALUES($1,$2,'facebook',$3::jsonb)",
            uuid.UUID(org), uuid.UUID(p["id"]), json.dumps({"engagement": engagement, "reach": engagement * 5}))
    return p["id"]


async def test_exemplars_guarded_below_min_measured(db_pool):
    org = _fresh_org()
    for i in range(5):                      # only 5 measured → below the >=6 guard
        await _post_with_engagement(org, f"caption {i}", i)
    assert await ins.top_exemplars(org) == []


async def test_exemplars_returns_top_by_engagement(db_pool):
    org = _fresh_org()
    for i in range(6):                      # 6 measured → guard passes
        await _post_with_engagement(org, f"perf {i}", i * 10)   # engagement 0,10,20,30,40,50
    ex = await ins.top_exemplars(org, limit=3)
    assert len(ex) == 3
    assert [e["engagement"] for e in ex] == [50, 40, 30]        # top 3, descending
    assert ex[0]["caption"] == "perf 5"


def test_build_draft_prompt_injects_exemplars():
    prompt = build_draft_prompt("t", "angle", {}, None, [],
                                exemplars=[{"caption": "Meet Leo, who found his voice", "engagement": 50}])
    assert "RESONATED" in prompt and "Meet Leo, who found his voice" in prompt
    assert "NEVER" in prompt                                    # the don't-parrot guard


def test_build_draft_prompt_no_exemplars_no_block():
    prompt = build_draft_prompt("t", "angle", {}, None, [], exemplars=[])
    assert "RESONATED" not in prompt
