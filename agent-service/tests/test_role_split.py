"""Security regression tests for the npo_owner / npo_app role split.

The runtime role (npo_app) the pool connects as must be able to do DML but MUST NOT
be able to alter the tables or RLS policies — so even a SQL-injection running as
npo_app cannot disable tenant isolation. These tests pin that contract.
"""
import uuid
import asyncpg
import pytest

from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio


async def test_npo_app_cannot_drop_policy(db_pool):
    """npo_app does not own the tables, so DROP POLICY is denied."""
    org = str(uuid.uuid4())
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with org_tx(org) as conn:
            await conn.execute("DROP POLICY conv_isolation ON conversations")


async def test_npo_app_cannot_disable_force_rls(db_pool):
    """ALTER TABLE requires ownership — npo_app cannot turn off FORCE ROW LEVEL SECURITY."""
    org = str(uuid.uuid4())
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with org_tx(org) as conn:
            await conn.execute("ALTER TABLE conversations NO FORCE ROW LEVEL SECURITY")


async def test_npo_app_can_do_dml(db_pool):
    """The split must not break normal request work: npo_app can still INSERT (RLS-scoped)."""
    org = str(uuid.uuid4())
    async with org_tx(org) as conn:
        cid = await conn.fetchval(
            "INSERT INTO conversations(org_id, user_id, title) VALUES($1, $2, $3) RETURNING id",
            uuid.UUID(org), uuid.uuid4(), "role-split ok",
        )
    assert cid is not None
