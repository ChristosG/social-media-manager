import uuid
import pytest
from app.sources import scheduler
from app.repo import sources as sr

pytestmark = pytest.mark.asyncio


async def test_due_sources_graceful_when_function_absent(db_pool):
    # sched_due_sources is NOT installed in the test DB → returns [] (must not raise)
    assert await scheduler._due_sources() == []


async def test_tick_ingests_due_and_advances_next_due(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    sid = (await sr.create_source(org, "web", "S", {"url": "http://s"}))["id"]
    async def fake_due(limit=20): return [(org, sid)]
    ran = []
    async def fake_run(o, s): ran.append(s); return {"status": "ok"}
    monkeypatch.setattr(scheduler, "_due_sources", fake_due)
    monkeypatch.setattr(scheduler, "run_ingest", fake_run)
    n = await scheduler.tick()
    assert n == 1 and ran == [sid]
    assert (await sr.get_source(org, sid))["next_due_at"] is not None
