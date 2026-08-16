import uuid

import pytest

from app.db.pool import org_tx
from app.repo import jobs
from app.security.context import set_identity
from app.worker import registry
from app.worker.runner import Worker

pytestmark = pytest.mark.usefixtures("db_pool")


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    registry.clear()


def _org() -> str:
    org = str(uuid.uuid4())
    set_identity(user_id=str(uuid.uuid4()), org_id=org)
    return org


async def test_process_runs_handler_and_succeeds():
    org = _org()
    seen = {}

    @registry.register("t_ok")
    async def _h(ctx, payload):
        seen["payload"] = payload
        await ctx.progress(step=1)      # records progress + renews lease

    j = await jobs.enqueue(org, "t_ok", payload={"x": 7})
    assert await Worker().process(org, j["id"]) == "succeeded"
    assert seen["payload"] == {"x": 7}
    done = await jobs.get(org, j["id"])
    assert done["state"] == "succeeded" and done["progress"] == {"step": 1}


async def test_failing_handler_retries_then_dead_letters():
    org = _org()

    @registry.register("t_boom")
    async def _h(ctx, payload):
        raise RuntimeError("nope")

    j = await jobs.enqueue(org, "t_boom", max_attempts=2)
    assert await Worker().process(org, j["id"]) == "queued"   # attempt 1 → retry
    assert await Worker().process(org, j["id"]) == "dead"     # attempt 2 → dead-letter
    d = await jobs.get(org, j["id"])
    assert d["state"] == "dead" and "nope" in d["last_error"]


async def test_no_handler_is_not_fatal():
    org = _org()
    j = await jobs.enqueue(org, "t_missing")
    assert await Worker().process(org, j["id"]) == "no_handler"


async def test_lost_claim_race_returns_none():
    org = _org()

    @registry.register("t_x")
    async def _h(ctx, payload):
        ...

    j = await jobs.enqueue(org, "t_x")
    assert await jobs.claim(org, j["id"], "another-worker") is not None
    assert await Worker().process(org, j["id"]) is None       # already running → we lose the race


async def test_reaper_requeues_a_lease_expired_job():
    org = _org()
    j = await jobs.enqueue(org, "t_y")
    await jobs.claim(org, j["id"], "dead-worker", lease_secs=300)
    async with org_tx(org) as c:                              # simulate the worker dying mid-run
        await c.execute("UPDATE jobs SET leased_until = now() - interval '1 minute' WHERE id=$1",
                        uuid.UUID(j["id"]))
    assert await jobs.requeue_stale(org, j["id"]) == "queued"
    assert (await jobs.get(org, j["id"]))["state"] == "queued"
