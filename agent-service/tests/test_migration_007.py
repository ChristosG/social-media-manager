import os
import uuid
import asyncpg
import pytest

pytestmark = pytest.mark.asyncio


class _Rollback(Exception):
    pass


async def test_fb3_backfill_copies_url_research_sources(db_pool):
    """The 007 backfill must actually copy an org-scoped FB3 research_source (with a config.url) into
    `sources` — the exact case 006's in-migration INSERT silently dropped. Run the backfill SQL as the
    OWNER (it toggles FORCE RLS, which npo_app cannot), seeded with a capability, then roll back so the
    shared test DB stays clean."""
    conn = await asyncpg.connect(os.environ["MIGRATION_DATABASE_URL"])  # npo_owner
    org = uuid.uuid4()
    try:
        try:
            async with conn.transaction():
                await conn.execute("ALTER TABLE capabilities NO FORCE ROW LEVEL SECURITY")
                await conn.execute("ALTER TABLE sources NO FORCE ROW LEVEL SECURITY")
                await conn.execute(
                    "INSERT INTO capabilities(org_id, kind, name, config) "
                    "VALUES($1,'research_source','Legacy Blog','{\"url\":\"https://example.org/news\"}'::jsonb)",
                    org)
                await conn.execute(
                    "INSERT INTO sources (org_id, kind, name, config) "
                    "SELECT org_id,'web',name, jsonb_build_object('url',config->>'url','type','auto','latest_n',15) "
                    "FROM capabilities WHERE kind='research_source' AND org_id IS NOT NULL "
                    "AND (config->>'url') IS NOT NULL ON CONFLICT DO NOTHING")
                row = await conn.fetchrow(
                    "SELECT kind, config->>'url' AS url FROM sources WHERE org_id=$1", org)
                assert row is not None and row["kind"] == "web" and row["url"] == "https://example.org/news"
                raise _Rollback()  # abort → leaves the DB untouched (DDL + DML both roll back)
        except _Rollback:
            pass
    finally:
        await conn.close()
