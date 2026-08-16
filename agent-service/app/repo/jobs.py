"""Durable job queue repo — the publish-worker pattern generalized (atomic claim + lease + reaper).

Org-scoped operations run under RLS via org_tx. The worker tier finds DUE jobs across orgs with a
SECURITY DEFINER reader (added with the worker), then calls claim() per-org here. enqueue() can run inside
a caller's existing org_tx (pass `conn`) so a job is enqueued in the SAME transaction as the business
write — no dual-write gap."""
import json
import logging
import uuid

import asyncpg

from app.db.pool import org_tx, raw_conn

logger = logging.getLogger(__name__)
_warned: set[str] = set()


def _warn_once(fn: str) -> None:
    if fn not in _warned:
        _warned.add(fn)
        logger.error("SECURITY DEFINER reader %s() is missing — background work for it will not run until "
                     "`deploy.sh db-functions` is applied", fn)

_COLS = ("id, org_id, kind, dedup_key, priority, payload, state, attempts, max_attempts, run_after, "
         "leased_until, locked_by, progress, last_error, created_at, updated_at")

LIVE = ("queued", "running")


def _row(r) -> dict:
    return {
        "id": str(r["id"]), "org_id": str(r["org_id"]), "kind": r["kind"], "dedup_key": r["dedup_key"],
        "priority": r["priority"],
        "payload": r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"] or "{}"),
        "state": r["state"], "attempts": r["attempts"], "max_attempts": r["max_attempts"],
        "run_after": r["run_after"].isoformat(),
        "leased_until": r["leased_until"].isoformat() if r["leased_until"] else None,
        "locked_by": r["locked_by"],
        "progress": r["progress"] if isinstance(r["progress"], dict) else json.loads(r["progress"] or "{}"),
        "last_error": r["last_error"],
        "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat(),
    }


async def _enqueue(c, org_id, kind, payload, dedup_key, priority, max_attempts, run_after) -> dict | None:
    r = await c.fetchrow(
        f"INSERT INTO jobs(org_id, kind, dedup_key, priority, payload, max_attempts, run_after) "
        f"VALUES($1,$2,$3,$4,$5::jsonb,$6, COALESCE($7, now())) "
        f"ON CONFLICT (org_id, kind, dedup_key) WHERE dedup_key IS NOT NULL AND state IN ('queued','running') "
        f"DO NOTHING RETURNING {_COLS}",
        uuid.UUID(org_id), kind, dedup_key, priority, json.dumps(payload or {}), max_attempts, run_after)
    if r:
        return _row(r)
    # A live job for this (kind, dedup_key) already exists — return it (idempotent enqueue).
    ex = await c.fetchrow(
        f"SELECT {_COLS} FROM jobs WHERE kind=$1 AND dedup_key=$2 AND state = ANY($3::text[]) "
        "ORDER BY created_at LIMIT 1", kind, dedup_key, list(LIVE))
    return _row(ex) if ex else None


async def enqueue(org_id: str, kind: str, *, payload: dict | None = None, dedup_key: str | None = None,
                  priority: int = 100, max_attempts: int = 5, run_after=None, conn=None) -> dict | None:
    """Enqueue a job (idempotent on (kind, dedup_key) for live jobs). Pass `conn` to enqueue inside an
    existing org_tx (transactional enqueue alongside the business write)."""
    if conn is not None:
        return await _enqueue(conn, org_id, kind, payload, dedup_key, priority, max_attempts, run_after)
    async with org_tx(org_id) as c:
        return await _enqueue(c, org_id, kind, payload, dedup_key, priority, max_attempts, run_after)


async def claim(org_id: str, job_id: str, locked_by: str, lease_secs: int = 300) -> dict | None:
    """Atomic queued -> running with a lease. Returns None if already claimed (lost the race)."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"UPDATE jobs SET state='running', attempts=attempts+1, locked_by=$2, "
            f"leased_until=now() + make_interval(secs => $3::int), updated_at=now() "
            f"WHERE id=$1 AND state='queued' RETURNING {_COLS}",
            uuid.UUID(job_id), locked_by, lease_secs)
        return _row(r) if r else None


async def heartbeat(org_id: str, job_id: str, locked_by: str, lease_secs: int = 300,
                    progress: dict | None = None) -> bool:
    """Extend the lease (and optionally record progress) while still the lease holder."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE jobs SET leased_until=now() + make_interval(secs => $3::int), "
            "progress=COALESCE($4::jsonb, progress), updated_at=now() "
            "WHERE id=$1 AND state='running' AND locked_by=$2",
            uuid.UUID(job_id), locked_by, lease_secs, json.dumps(progress) if progress is not None else None)
    return res.endswith(" 1")


async def succeed(org_id: str, job_id: str, progress: dict | None = None) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE jobs SET state='succeeded', leased_until=NULL, locked_by=NULL, "
            "progress=COALESCE($2::jsonb, progress), updated_at=now() WHERE id=$1 AND state='running'",
            uuid.UUID(job_id), json.dumps(progress) if progress is not None else None)
    return res.endswith(" 1")


async def fail(org_id: str, job_id: str, error: str, backoff_secs: int = 30) -> str | None:
    """Record a failure: requeue with backoff if attempts remain, else mark dead (DLQ). Returns the new
    state ('queued' | 'dead') or None if the job wasn't running."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "UPDATE jobs SET "
            "  state = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'queued' END, "
            "  run_after = now() + make_interval(secs => $3::int), "
            "  leased_until=NULL, locked_by=NULL, last_error=$2, updated_at=now() "
            "WHERE id=$1 AND state='running' RETURNING state",
            uuid.UUID(job_id), error, backoff_secs)
    return r["state"] if r else None


async def get(org_id: str, job_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_COLS} FROM jobs WHERE id=$1", uuid.UUID(job_id))
    return _row(r) if r else None


# ── Worker-tier cross-org readers (via SECURITY DEFINER fns; ids only, then claim per-org under RLS) ──

async def due(lim: int, kinds: list[str]) -> list[tuple[str, str]]:
    """(org_id, job_id) of due queued jobs for the given kinds, across all orgs. Degrades to [] (warns
    once) if the reader isn't installed, so a misconfigured deploy never crash-loops the worker."""
    if not kinds:
        return []
    async with raw_conn() as c:
        try:
            rows = await c.fetch("SELECT org_id, job_id FROM job_due($1, $2::text[])", lim, list(kinds))
        except asyncpg.UndefinedFunctionError:
            _warn_once("job_due")
            return []
    return [(str(r["org_id"]), str(r["job_id"])) for r in rows]


async def reap_due(lim: int) -> list[tuple[str, str]]:
    """(org_id, job_id) of jobs whose lease expired (worker died mid-run), across all orgs."""
    async with raw_conn() as c:
        try:
            rows = await c.fetch("SELECT org_id, job_id FROM job_reap_stale($1)", lim)
        except asyncpg.UndefinedFunctionError:
            _warn_once("job_reap_stale")
            return []
    return [(str(r["org_id"]), str(r["job_id"])) for r in rows]


async def requeue_stale(org_id: str, job_id: str) -> str | None:
    """Reaper action: a running job whose lease expired → back to 'queued' (or 'dead' at max attempts).
    Returns the new state, or None if it wasn't actually stale (another worker already handled it)."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "UPDATE jobs SET state = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'queued' END, "
            "leased_until=NULL, locked_by=NULL, last_error='lease expired (worker presumed dead)', "
            "updated_at=now() WHERE id=$1 AND state='running' AND leased_until < now() RETURNING state",
            uuid.UUID(job_id))
    return r["state"] if r else None
