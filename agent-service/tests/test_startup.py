import pytest
import app.main as main

pytestmark = pytest.mark.asyncio


async def test_init_db_with_retry_waits_then_succeeds(monkeypatch):
    """A cold start must WAIT for Postgres, not crash — retry migrate+pool until the DB is up."""
    calls = {"migrate": 0, "pool": 0}

    async def flaky_migrate(*a, **k):
        calls["migrate"] += 1
        if calls["migrate"] < 3:           # DB still booting for the first two attempts
            raise ConnectionError("postgres not ready")

    async def ok_pool(*a, **k):
        calls["pool"] += 1

    monkeypatch.setattr(main, "run_migrations", flaky_migrate)
    monkeypatch.setattr(main, "init_pool", ok_pool)

    await main._init_db_with_retry(attempts=5, delay=0)
    assert calls["migrate"] == 3 and calls["pool"] == 1   # retried, then opened the pool exactly once


async def test_init_db_with_retry_raises_after_exhausting(monkeypatch):
    """If the DB never comes up, surface the real error (so the container exits + restart-policy retries)."""
    async def always_fail(*a, **k):
        raise ConnectionError("down")

    async def ok_pool(*a, **k):
        pass

    monkeypatch.setattr(main, "run_migrations", always_fail)
    monkeypatch.setattr(main, "init_pool", ok_pool)

    with pytest.raises(ConnectionError):
        await main._init_db_with_retry(attempts=2, delay=0)
