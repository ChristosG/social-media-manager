"""Boot-time security/integrity self-check — make silent failure loud.

A multi-tenant system must never quietly ship in a state where (a) a table lost FORCE RLS, (b) the runtime
role gained BYPASSRLS, or (c) the cross-tenant SECURITY DEFINER readers are absent (in which case scheduled
publishing / source ingest / comment handling silently never run — they swallow the missing-function error).
These are integrity invariants, so we assert them at boot and, on violation, mark the service NOT READY
(/readyz → 503) rather than crash — visible to the operator and the orchestrator, recoverable without a
crash-loop.

The 4 readers are intentionally owned by `platform` (a BYPASSRLS superuser) with SECURITY DEFINER so they can
read across orgs returning ids-only; npo_owner (the migration role) is NOT BYPASSRLS, so they cannot live in
the npo_owner migrations — their application is version-controlled in the deploy path and their PRESENCE is
asserted here.
"""
import logging

logger = logging.getLogger(__name__)

# Conservative, verified-critical set (each is FORCE RLS in prod). Kept explicit to avoid false unreadiness.
_RLS_TABLES = ("posts", "conversations", "scheduled_posts", "campaigns", "connections")
_SECDEF_READERS = ("sched_due_posts", "sched_stale_publishing", "sched_due_sources", "engage_capable_orgs",
                   "job_due", "job_reap_stale")

_problems: list[str] = []


async def run_security_self_check(conn) -> list[str]:
    """Return a list of integrity violations (empty = healthy). Uses catalog queries only (works as the
    DML-only runtime role)."""
    problems: list[str] = []

    rows = await conn.fetch(
        "SELECT relname, relforcerowsecurity FROM pg_class WHERE relname = ANY($1::text[]) AND relkind='r'",
        list(_RLS_TABLES))
    force = {r["relname"]: r["relforcerowsecurity"] for r in rows}
    for t in _RLS_TABLES:
        if t not in force:
            problems.append(f"RLS table '{t}' is missing")
        elif not force[t]:
            problems.append(f"RLS table '{t}' is NOT FORCE ROW LEVEL SECURITY")

    frows = await conn.fetch(
        "SELECT p.proname, p.prosecdef, r.rolbypassrls FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner "
        "WHERE p.proname = ANY($1::text[])", list(_SECDEF_READERS))
    fmap = {r["proname"]: r for r in frows}
    for fn in _SECDEF_READERS:
        if fn not in fmap:
            problems.append(f"SECURITY DEFINER reader {fn}() is MISSING — scheduled publishing / ingest / "
                            f"comments will silently never run")
        elif not fmap[fn]["prosecdef"]:
            problems.append(f"{fn}() is not SECURITY DEFINER")
        elif not fmap[fn]["rolbypassrls"]:
            problems.append(f"{fn}() owner lacks BYPASSRLS — its cross-tenant read is RLS-filtered to zero")

    app_bypass = await conn.fetchval("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'npo_app'")
    if app_bypass:
        problems.append("runtime role npo_app has BYPASSRLS — tenant isolation is broken")

    return problems


def record(problems: list[str]) -> None:
    """Store the latest result so /readyz can reflect it."""
    global _problems
    _problems = list(problems)


def current_problems() -> list[str]:
    return list(_problems)
