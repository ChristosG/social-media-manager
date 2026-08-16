import uuid

import pytest

from app.repo import jobs
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


def _org():
    org = str(uuid.uuid4())
    set_identity(user_id=str(uuid.uuid4()), org_id=org)
    return org


async def test_enqueue_and_claim_lifecycle():
    org = _org()
    j = await jobs.enqueue(org, "campaign_fill", payload={"slot": 1})
    assert j["state"] == "queued" and j["payload"] == {"slot": 1}

    claimed = await jobs.claim(org, j["id"], locked_by="worker-1")
    assert claimed["state"] == "running" and claimed["attempts"] == 1

    # already running → a second claimer loses the race
    assert await jobs.claim(org, j["id"], locked_by="worker-2") is None

    assert await jobs.succeed(org, j["id"]) is True
    assert (await jobs.get(org, j["id"]))["state"] == "succeeded"


async def test_enqueue_is_idempotent_on_dedup_key():
    org = _org()
    a = await jobs.enqueue(org, "source_ingest", dedup_key="src-42")
    b = await jobs.enqueue(org, "source_ingest", dedup_key="src-42")
    assert a["id"] == b["id"]   # one LIVE job per (kind, dedup_key)


async def test_fail_requeues_then_dead_letters():
    org = _org()
    j = await jobs.enqueue(org, "publish", max_attempts=2)
    await jobs.claim(org, j["id"], locked_by="w")
    assert await jobs.fail(org, j["id"], "boom", backoff_secs=0) == "queued"   # attempt 1 < max 2 → retry

    await jobs.claim(org, j["id"], locked_by="w")                              # attempt 2
    assert await jobs.fail(org, j["id"], "boom again", backoff_secs=0) == "dead"
    dead = await jobs.get(org, j["id"])
    assert dead["state"] == "dead" and dead["last_error"] == "boom again"


async def test_heartbeat_extends_lease_only_for_holder():
    org = _org()
    j = await jobs.enqueue(org, "memory_consolidate")
    await jobs.claim(org, j["id"], locked_by="w1")
    assert await jobs.heartbeat(org, j["id"], locked_by="w1", progress={"done": 1}) is True
    assert await jobs.heartbeat(org, j["id"], locked_by="someone-else") is False
    assert (await jobs.get(org, j["id"]))["progress"] == {"done": 1}
