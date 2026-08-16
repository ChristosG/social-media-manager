import uuid
import pytest
from app.repo import scheduled_posts as sp
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio


async def _make(org, status="pending", attempts=0, age_secs=0):
    row = await sp.create(
        org, targets=[{"provider": "instagram", "connection_id": str(uuid.uuid4())}],
        caption="c", image_ids=[str(uuid.uuid4())], content_hash=str(uuid.uuid4()),
        scheduled_at_now=True, created_by=None, post_id=None)
    if status != "pending" or attempts or age_secs:
        async with org_tx(org) as c:
            await c.execute(
                "UPDATE scheduled_posts SET status=$2, attempts=$3, "
                "updated_at = now() - make_interval(secs => $4) WHERE id=$1",
                uuid.UUID(row["id"]), status, attempts, age_secs)
    return row["id"]


async def test_reap_requeues_stuck_post_with_attempts_left(db_pool):
    org = str(uuid.uuid4())
    sp_id = await _make(org, status="publishing", attempts=1, age_secs=600)
    assert await sp.reap(org, sp_id, 5) == "pending"           # recovered for retry
    assert (await sp.get(org, sp_id))["status"] == "pending"


async def test_reap_fails_post_past_max_attempts(db_pool):
    org = str(uuid.uuid4())
    sp_id = await _make(org, status="publishing", attempts=5, age_secs=600)
    assert await sp.reap(org, sp_id, 5) == "failed"            # poison guard — don't reap forever
    done = await sp.get(org, sp_id)
    assert done["status"] == "failed"
    assert "_reaper" in done["result"]


async def test_reap_is_noop_when_not_publishing(db_pool):
    org = str(uuid.uuid4())
    sp_id = await _make(org, status="pending")
    assert await sp.reap(org, sp_id, 5) is None                # only acts on 'publishing'
    assert (await sp.get(org, sp_id))["status"] == "pending"
