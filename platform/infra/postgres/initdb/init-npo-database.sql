-- Create the `npo` database + a SPLIT-ROLE least-privilege model for the agent-service.
-- Runs on FIRST container start (mounted into /docker-entrypoint-initdb.d/). Idempotent:
-- safe to re-run manually if the postgres volume already exists:
--   docker exec -e NPO_OWNER_PASSWORD="$NPO_OWNER_PASSWORD" -e NPO_DB_PASSWORD="$NPO_DB_PASSWORD" -i postgres \
--     psql -U "$POSTGRES_USER" -d postgres -f /docker-entrypoint-initdb.d/init-npo-database.sql
--
-- TWO roles, by design (defense-in-depth on top of FORCE ROW LEVEL SECURITY):
--   npo_owner  — owns the schema, tables, and RLS policies; runs migrations (DDL). Used ONLY at
--                service startup. NOSUPERUSER, so FORCE RLS still applies to it too.
--   npo_app    — the runtime role used for every request. DML-only (SELECT/INSERT/UPDATE/DELETE),
--                no ownership. So even a SQL-injection executed as npo_app cannot DROP POLICY or
--                ALTER TABLE ... NO FORCE to disable tenant isolation — it simply lacks the rights.
-- Both passwords come from env (psql \getenv) — never hardcoded in version control.

\getenv npo_owner_pw NPO_OWNER_PASSWORD
\getenv npo_app_pw NPO_DB_PASSWORD

-- Roles (idempotent): create if absent, then (re)set the password at top level. psql interpolates
-- :'...' here but NOT inside dollar-quoted DO blocks, so passwords must be set outside the DO.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'npo_owner') THEN
    CREATE ROLE npo_owner LOGIN NOSUPERUSER;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'npo_app') THEN
    CREATE ROLE npo_app LOGIN NOSUPERUSER;
  END IF;
END $$;
ALTER ROLE npo_owner PASSWORD :'npo_owner_pw';
ALTER ROLE npo_app  PASSWORD :'npo_app_pw';

-- Database owned by npo_owner (idempotent — \gexec runs the CREATE only when absent).
SELECT 'CREATE DATABASE npo OWNER npo_owner'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'npo')\gexec
ALTER DATABASE npo OWNER TO npo_owner;

\connect npo
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;

-- npo_owner owns the schema (creates tables via migrations); npo_app gets USAGE only — no CREATE,
-- so it can never add/alter/drop objects in public.
ALTER SCHEMA public OWNER TO npo_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE npo TO npo_app;
GRANT USAGE ON SCHEMA public TO npo_app;

-- Tables/sequences created later by npo_owner auto-grant DML (never DDL) to npo_app, so new
-- migrations don't have to remember to GRANT.
ALTER DEFAULT PRIVILEGES FOR ROLE npo_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO npo_app;
ALTER DEFAULT PRIVILEGES FOR ROLE npo_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO npo_app;
