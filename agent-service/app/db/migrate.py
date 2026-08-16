import asyncio
from pathlib import Path
import asyncpg
from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(dsn: str | None = None) -> list[str]:
    # Migrations run DDL, so they connect as the owner role (npo_owner), not the
    # DML-only runtime role (npo_app) that serves requests.
    #
    # WARNING for DML in migrations (backfills): the tenant tables are FORCE ROW LEVEL SECURITY, which
    # applies the org policy to npo_owner as well — and no migration sets `app.org`, so
    # `org_id = current_setting('app.org', true)::uuid` is `org_id = NULL` → never true. A backfill
    # UPDATE/DELETE therefore matches ZERO rows, raises no error, and is still recorded as applied.
    # DDL is unaffected (policies gate DML only). To backfill, bracket the statement with
    #   ALTER TABLE <t> NO FORCE ROW LEVEL SECURITY;  …  ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
    # which is safe here because each file runs in one transaction and ALTER takes ACCESS EXCLUSIVE.
    # See 034_comment_auto_eval.sql for the worked example.
    dsn = dsn or get_settings().migration_database_url
    conn = await asyncpg.connect(dsn)
    applied: list[str] = []
    try:
        # Serialize concurrent replica cold-starts: only one process applies migrations at a time. The
        # session-level lock auto-releases when this connection closes (finally). (8274,1971) is an
        # arbitrary fixed key for the migration runner.
        await conn.execute("SELECT pg_advisory_lock(8274, 1971)")
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
        )
        done = {r["name"] for r in await conn.fetch("SELECT name FROM schema_migrations")}
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in done:
                continue
            async with conn.transaction():
                await conn.execute(sql_file.read_text())
                await conn.execute("INSERT INTO schema_migrations(name) VALUES($1)", sql_file.name)
            applied.append(sql_file.name)
    finally:
        await conn.close()
    return applied


if __name__ == "__main__":
    print("applied:", asyncio.run(run_migrations()))
