import os
# Isolated throwaway Postgres for tests. Two roles, mirroring production:
#   npo_owner — owns tables + policies, runs migrations (DDL).
#   npo_app   — DML-only runtime role the pool connects as (RLS applies; cannot DROP POLICY).
os.environ.setdefault("TEST_DATABASE_URL", "postgresql://npo_app:changeme@localhost:55432/npo")
os.environ.setdefault("TEST_MIGRATION_DATABASE_URL", "postgresql://npo_owner:changeme@localhost:55432/npo")
# The app lifespan opens a pool against DATABASE_URL (npo_app); migrations use MIGRATION_DATABASE_URL (npo_owner).
os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
os.environ.setdefault("MIGRATION_DATABASE_URL", os.environ["TEST_MIGRATION_DATABASE_URL"])
os.environ.setdefault("JWT_PUBLIC_KEY", "")
os.environ.setdefault("META_TOKEN_KEY", "test-only-meta-token-key-rotate-me-0123456789")  # crypto fails closed without it
os.environ.setdefault("IMAGE_URL_SECRET", "test-only-image-url-secret-0123456789")        # image + OAuth-state signing
os.environ.setdefault("META_OAUTH_REDIRECT", "https://test.example/api/v1/social/callback")  # public origin for server-side (Meta) image URLs

import pytest
from app.db.migrate import run_migrations
from app.db import pool as dbpool


@pytest.fixture
async def db_pool():
    """Run migrations (idempotent) and open/close the pool per test function.

    Opt-in (not autouse): only tests that explicitly request this fixture will
    touch the database. This allows the WebSocket test to open its own pool
    inside TestClient's lifespan (the portal/sync event loop) without hitting
    the asyncpg "Future attached to a different loop" error caused by a
    pre-existing pool created in pytest-asyncio's per-test loop.

    Function scope ensures asyncpg connections share the same event loop as the
    test, avoiding the "Future attached to a different loop" error that arises
    when a session-scoped pool is reused across pytest-asyncio's per-test loops.
    """
    await run_migrations(os.environ["MIGRATION_DATABASE_URL"])  # DDL as npo_owner
    await dbpool.init_pool()  # pool connects as npo_app (DML-only)
    yield
    await dbpool.close_pool()
