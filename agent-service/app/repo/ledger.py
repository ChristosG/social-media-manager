import json
import re
import uuid
from app.db.pool import org_tx

STATUSES = {"suggested","drafting","drafted","approved","scheduled","posted","archived"}
# Statuses that count as a LIVE idea for dedup (mirrors the partial unique index in migration 024).
_LIVE = ("suggested","drafting","drafted","approved","scheduled")

_COLS = ("id,title,brief,status,platform,content,sources,idea_group,idea_key,planned_for,planned_at,"
         "image_ids,refine_suggestions,pillar,origin,external_post_id,created_at,updated_at")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def idea_slug(title: str) -> str:
    """A stable, normalized key for an idea so re-suggesting / re-drafting the SAME idea reuses its row
    instead of creating a near-identical twin. Lowercased alphanumerics, collapsed to single hyphens."""
    s = _SLUG_RE.sub("-", (title or "").lower()).strip("-")
    return s[:80] or "idea"


def _post(r) -> dict:
    return {"id": str(r["id"]), "title": r["title"], "brief": r["brief"], "status": r["status"],
            "platform": r["platform"], "content": r["content"], "sources": json.loads(r["sources"]),
            "idea_group": str(r["idea_group"]) if r["idea_group"] else None,
            "idea_key": r["idea_key"],
            "planned_for": r["planned_for"].isoformat() if r["planned_for"] else None,
            "planned_at": r["planned_at"].isoformat() if r["planned_at"] else None,
            "image_ids": [str(i) for i in (r["image_ids"] or [])],
            "refine_suggestions": json.loads(r["refine_suggestions"]) if r["refine_suggestions"] else [],
            "pillar": r["pillar"],
            "origin": r["origin"], "external_post_id": r["external_post_id"],
            "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat()}


async def list_posts(org_id: str, status: str | None = None) -> list[dict]:
    q = f"SELECT {_COLS} FROM posts"
    args: list = []
    if status:
        q += " WHERE status=$1"; args.append(status)
    q += " ORDER BY updated_at DESC LIMIT 200"
    async with org_tx(org_id) as c:
        rows = await c.fetch(q, *args)
    return [_post(r) for r in rows]


async def get_post(org_id: str, post_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_COLS} FROM posts WHERE id=$1", uuid.UUID(post_id))
    return _post(r) if r else None


async def create_post(org_id: str, title: str, brief: str | None, status: str = "suggested",
                      origin: str = "user_requested", sources: list | None = None,
                      dedup: bool = False, idea_key: str | None = None) -> dict:
    """Insert a ledger post. When dedup=True (or an explicit idea_key is given) the post carries a normalized
    idea_key; with dedup=True an existing LIVE row for the same idea is returned instead of creating a
    duplicate (the partial unique index in migration 024 is the backstop). Direct callers that pass neither
    keep idea_key NULL and the legacy insert-always behavior."""
    key = None
    if dedup or idea_key is not None:
        key = idea_key if idea_key is not None else idea_slug(title)
    async with org_tx(org_id) as c:
        if key and dedup:
            ex = await c.fetchrow(
                f"SELECT {_COLS} FROM posts WHERE idea_key=$1 AND status = ANY($2::text[]) "
                "ORDER BY updated_at DESC LIMIT 1", key, list(_LIVE))
            if ex:
                return _post(ex)
        r = await c.fetchrow(
            f"INSERT INTO posts(org_id,title,brief,status,origin,sources,idea_key) "
            f"VALUES($1,$2,$3,$4,$5,$6::jsonb,$7) RETURNING {_COLS}",
            uuid.UUID(org_id), title, brief, status, origin, json.dumps(sources or []), key)
    return _post(r)


async def update_post(org_id: str, post_id: str, status: str | None, content: str | None,
                      platform: str | None, suggestions: list[str] | None = None,
                      pillar: str | None = None) -> bool:
    sets, args, i = [], [], 1
    cols = [("status", status), ("content", content), ("platform", platform)]
    if suggestions is not None:
        cols.append(("refine_suggestions", json.dumps(suggestions)))
    if pillar is not None:
        cols.append(("pillar", pillar))
    for col, val in cols:
        if val is not None:
            cast = "::jsonb" if col == "refine_suggestions" else ""
            sets.append(f"{col}=${i}{cast}"); args.append(val); i += 1
    if not sets:
        return False
    sets.append("updated_at=now()")
    args.append(uuid.UUID(post_id))
    async with org_tx(org_id) as c:
        async with c.transaction():
            # Record the PRIOR caption before overwriting it — only when content actually changes to a
            # new non-null value, so revisions accumulate on real edits (not status-only updates).
            if content is not None:
                prev = await c.fetchval("SELECT content FROM posts WHERE id=$1", uuid.UUID(post_id))
                if prev is not None and prev != content:
                    await c.execute(
                        "INSERT INTO post_revisions(org_id, post_id, content, source) VALUES($1,$2,$3,'edit')",
                        uuid.UUID(org_id), uuid.UUID(post_id), prev)
                    await c.execute(
                        "DELETE FROM post_revisions WHERE post_id=$1 AND id NOT IN ("
                        "  SELECT id FROM post_revisions WHERE post_id=$1 ORDER BY created_at DESC LIMIT 20)",
                        uuid.UUID(post_id))
            res = await c.execute(f"UPDATE posts SET {','.join(sets)} WHERE id=${i}", *args)
    return res.endswith(" 1")


async def mark_posted(org_id: str, post_id: str) -> bool:
    """Flip a ledger post to 'posted' and stamp posted_at after it publishes live, so the Posts list, the
    status funnel and the 'published' insight reflect reality (the scheduled_posts row going 'published'
    alone left the post stuck at 'drafted'). Status-only — never touches content, so it can't spawn a
    spurious revision. Idempotent: a post already 'posted' (or a missing id) is a harmless no-op."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE posts SET status='posted', posted_at=COALESCE(posted_at, now()), updated_at=now() "
            "WHERE id=$1 AND status <> 'posted'",
            uuid.UUID(post_id))
    return res.endswith(" 1")


async def undo_caption(org_id: str, post_id: str) -> str | None:
    """Restore the most recent prior caption from history (pop it). Returns the restored caption, or None
    when there is no revision to undo to. Persisted, so undo survives a reload/relogin."""
    async with org_tx(org_id) as c:
        async with c.transaction():
            rev = await c.fetchrow(
                "SELECT id, content FROM post_revisions WHERE post_id=$1 "
                "ORDER BY created_at DESC, id DESC LIMIT 1 FOR UPDATE", uuid.UUID(post_id))
            if not rev:
                return None
            await c.execute("UPDATE posts SET content=$1, updated_at=now() WHERE id=$2",
                            rev["content"], uuid.UUID(post_id))
            await c.execute("DELETE FROM post_revisions WHERE id=$1", rev["id"])
            return rev["content"]


async def delete_post(org_id: str, post_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM posts WHERE id=$1", uuid.UUID(post_id))
    return res.endswith(" 1")


async def set_planned_for(org_id: str, post_id: str, planned) -> bool:
    """Set the DATE a post is planned for (clears any sub-day time). Kept for back-compat; prefer
    set_planned_at when a time matters."""
    async with org_tx(org_id) as c:
        res = await c.execute("UPDATE posts SET planned_for=$1, planned_at=NULL, updated_at=now() WHERE id=$2",
                              planned, uuid.UUID(post_id))
    return res.endswith(" 1")


async def set_planned_at(org_id: str, post_id: str, planned_at) -> bool:
    """Set the full date+TIME a post is planned for. Also derives planned_for (the date) so date-range
    bucketing keeps working. `planned_at` is a timezone-aware datetime."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE posts SET planned_at=$1::timestamptz, planned_for=($1::timestamptz)::date, "
            "updated_at=now() WHERE id=$2",
            planned_at, uuid.UUID(post_id))
    return res.endswith(" 1")


async def set_images(org_id: str, post_id: str, image_ids: list[str]) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE posts SET image_ids=$1::uuid[], updated_at=now() WHERE id=$2",
            [uuid.UUID(i) for i in image_ids], uuid.UUID(post_id))
    return res.endswith(" 1")


async def list_planned_in_range(org_id: str, frm, to) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            f"SELECT {_COLS} FROM posts WHERE planned_for >= $1 AND planned_for <= $2 "
            "ORDER BY COALESCE(planned_at, planned_for::timestamptz)",
            frm, to)
    return [_post(r) for r in rows]
