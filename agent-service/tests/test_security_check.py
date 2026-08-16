import uuid

import pytest

from app.db import pool, security_check


@pytest.mark.usefixtures("db_pool")
async def test_self_check_detects_missing_secdef_readers():
    # The test DB has FORCE RLS (from migrations) but NOT the hand-applied SECURITY DEFINER readers,
    # so the check must FLAG the missing readers and must NOT complain about FORCE RLS.
    async with pool.raw_conn() as conn:
        problems = await security_check.run_security_self_check(conn)
    assert any("sched_due_posts" in p and "MISSING" in p for p in problems)
    assert not any("FORCE ROW LEVEL SECURITY" in p for p in problems)


@pytest.mark.usefixtures("db_pool")
async def test_org_tx_rejects_non_uuid_org():
    with pytest.raises(ValueError):
        async with pool.org_tx("not-a-uuid"):
            pass
    # a valid uuid is accepted
    async with pool.org_tx(str(uuid.uuid4())) as conn:
        assert await conn.fetchval("SELECT 1") == 1


def test_record_and_current_roundtrip():
    security_check.record(["boom"])
    assert security_check.current_problems() == ["boom"]
    security_check.record([])
    assert security_check.current_problems() == []
