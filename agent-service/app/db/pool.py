import uuid
from contextlib import asynccontextmanager
import asyncpg
from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    # Bound every statement so one wedged query can't pin a pool connection and starve the hot path.
    await conn.execute("SET statement_timeout = '30s'")


async def init_pool() -> None:
    global _pool
    if _pool is None:
        # Pool sized for concurrent request + WS-turn load. Bounded so the api tier + worker + auth stay
        # well under Postgres max_connections=200 (plenty of headroom on this box).
        _pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=2, max_size=20,
            command_timeout=30, init=_init_conn,
        )


async def ping() -> None:
    """Acquire a pooled connection and run SELECT 1 — the readiness probe. Raises if the pool is
    uninitialized or the DB is unreachable. No org scope (touches no RLS table)."""
    assert _pool is not None, "pool not initialized"
    async with _pool.acquire() as conn:
        await conn.fetchval("SELECT 1")


async def db_now():
    """The database clock (tz-aware) — the single source of truth for time, used to detect app/DB skew."""
    assert _pool is not None, "pool not initialized"
    async with _pool.acquire() as conn:
        return await conn.fetchval("SELECT now()")


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def raw_conn():
    """A pooled connection with NO org scope — for catalog/health queries only (never tenant data)."""
    assert _pool is not None, "pool not initialized"
    async with _pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def org_tx(org_id: str):
    """A transaction with RLS scoped to org_id via SET LOCAL app.org."""
    assert _pool is not None, "pool not initialized"
    # Guard the one string RLS depends on: a non-UUID here could poison set_config('app.org', …).
    uuid.UUID(str(org_id))
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org', $1, true)", org_id)
            yield conn
