import json
import uuid
from datetime import datetime, timezone
from app.db.pool import org_tx

_COLS = ("id, org_id, targets, caption, image_ids, content_hash, scheduled_at, status, attempts, "
         "result, post_id, created_by, created_at, updated_at")


def _row(r) -> dict:
    return {
        "id": str(r["id"]),
        "org_id": str(r["org_id"]),
        "targets": r["targets"] if isinstance(r["targets"], list) else json.loads(r["targets"]),
        "caption": r["caption"],
        "image_ids": [str(i) for i in (r["image_ids"] or [])],
        "content_hash": r["content_hash"],
        "scheduled_at": r["scheduled_at"].isoformat(),
        "status": r["status"],
        "attempts": r["attempts"],
        "result": r["result"] if isinstance(r["result"], dict) else json.loads(r["result"] or "{}"),
        "post_id": str(r["post_id"]) if r["post_id"] else None,
        "created_by": str(r["created_by"]) if r["created_by"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


async def create(
    org_id: str,
    targets: list,
    caption: str,
    image_ids: list,
    content_hash: str,
    scheduled_at_now: bool,
    created_by,
    post_id,
    scheduled_at=None,
) -> dict:
    imgs = [uuid.UUID(i) for i in image_ids]
    pid = uuid.UUID(post_id) if post_id else None
    cb = uuid.UUID(created_by) if created_by else None
    # asyncpg requires datetime objects for timestamptz — parse ISO strings if needed
    if scheduled_at is not None and isinstance(scheduled_at, str):
        scheduled_at = datetime.fromisoformat(scheduled_at)
    async with org_tx(org_id) as c:
        if scheduled_at_now:
            r = await c.fetchrow(
                f"INSERT INTO scheduled_posts(org_id,targets,caption,image_ids,content_hash,"
                f"scheduled_at,created_by,post_id) VALUES($1,$2,$3,$4,$5,now(),$6,$7) RETURNING {_COLS}",
                uuid.UUID(org_id), json.dumps(targets), caption, imgs, content_hash, cb, pid,
            )
        else:
            r = await c.fetchrow(
                f"INSERT INTO scheduled_posts(org_id,targets,caption,image_ids,content_hash,"
                f"scheduled_at,created_by,post_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING {_COLS}",
                uuid.UUID(org_id), json.dumps(targets), caption, imgs, content_hash, scheduled_at, cb, pid,
            )
        return _row(r)


async def claim(org_id: str, sp_id: str) -> dict | None:
    """Atomic state transition: pending -> publishing. Returns None if already claimed."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"UPDATE scheduled_posts SET status='publishing', attempts=attempts+1, updated_at=now() "
            f"WHERE id=$1 AND status='pending' RETURNING {_COLS}",
            uuid.UUID(sp_id),
        )
        return _row(r) if r else None


async def finish(org_id: str, sp_id: str, status: str, result: dict) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE scheduled_posts SET status=$1, result=$2::jsonb, updated_at=now() WHERE id=$3",
            status, json.dumps(result), uuid.UUID(sp_id),
        )


async def requeue(org_id: str, sp_id: str, result: dict) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE scheduled_posts SET status='pending', result=$1::jsonb, updated_at=now() WHERE id=$2",
            json.dumps(result), uuid.UUID(sp_id),
        )


async def reap(org_id: str, sp_id: str, max_attempts: int) -> str | None:
    """Recover a post stuck in 'publishing' (a worker claimed it then died before reaching a terminal
    state). If it has attempts left, requeue it to 'pending' so the worker retries — exactly-once holds
    because run_one skips targets that already have a result id. If it has exhausted attempts, mark it
    'failed' so it can't be reaped forever (poison guard). The WHERE status='publishing' guard makes this
    a no-op if the row finished on its own in the meantime. Returns the new status, or None if no-op."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "UPDATE scheduled_posts "
            "SET status = CASE WHEN attempts >= $2 THEN 'failed' ELSE 'pending' END, "
            "    result = CASE WHEN attempts >= $2 "
            "        THEN result || jsonb_build_object('_reaper', "
            "             'stuck in publishing; gave up after ' || attempts || ' attempts') "
            "        ELSE result END, "
            "    updated_at = now() "
            "WHERE id=$1 AND status='publishing' RETURNING status",
            uuid.UUID(sp_id), max_attempts,
        )
        return r["status"] if r else None


async def cancel(org_id: str, sp_id: str) -> bool:
    async with org_tx(org_id) as c:
        r = await c.execute(
            "UPDATE scheduled_posts SET status='canceled', updated_at=now() "
            "WHERE id=$1 AND status='pending'",
            uuid.UUID(sp_id),
        )
        return r.endswith("1")


async def get(org_id: str, sp_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"SELECT {_COLS} FROM scheduled_posts WHERE id=$1",
            uuid.UUID(sp_id),
        )
        return _row(r) if r else None


async def latest_for_post(org_id: str, post_id: str) -> dict | None:
    """The most recent scheduled_post linked to a ledger post — drives a post's lifecycle stage."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"SELECT {_COLS} FROM scheduled_posts WHERE post_id=$1 ORDER BY created_at DESC LIMIT 1",
            uuid.UUID(post_id),
        )
        return _row(r) if r else None


async def list_recent(org_id: str, limit: int = 50) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            f"SELECT {_COLS} FROM scheduled_posts ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [_row(r) for r in rows]


async def list_in_range(org_id: str, frm, to) -> list[dict]:
    """Scheduled/published posts whose scheduled_at is in [frm, to). For the calendar."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            f"SELECT {_COLS} FROM scheduled_posts WHERE scheduled_at >= $1 AND scheduled_at < $2 "
            f"ORDER BY scheduled_at", frm, to)
    return [_row(r) for r in rows]


async def reschedule(org_id: str, sp_id: str, new_at) -> bool:
    """Move a still-pending scheduled post to a new time. Refuses once the worker has claimed it
    (status != 'pending'), so we never race the exactly-once publish claim."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE scheduled_posts SET scheduled_at=$1, updated_at=now() WHERE id=$2 AND status='pending'",
            new_at, uuid.UUID(sp_id))
    return res.endswith(" 1")


async def exists_active_or_published(org_id: str, content_hash: str, provider: str) -> bool:
    """Returns True if a non-failed post with the same content_hash already targets this provider."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT 1 FROM scheduled_posts WHERE content_hash=$1 "
            "AND status IN ('pending','publishing','published') "
            "AND targets @> $2::jsonb LIMIT 1",
            content_hash,
            json.dumps([{"provider": provider}]),
        )
        return r is not None
