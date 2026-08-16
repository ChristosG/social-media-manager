import json
import uuid
from datetime import datetime
from app.db.pool import org_tx

_COLS = ("id, org_id, connection_id, provider, external_id, post_external_id, scheduled_post_id, "
         "author_name, author_external_id, message, permalink, commented_at, status, reply_text, "
         "reply_external_id, reply_mode, replied_at, created_at, updated_at")
# Same columns, qualified — needed when we LEFT JOIN scheduled_posts (which also has id/created_at/etc.).
_QCOLS = ", ".join(f"comments.{c}" for c in _COLS.split(", "))


def _post_context(r) -> dict | None:
    """Build the parent-post context for a comment (caption snippet + first image id + the post's public
    permalink) from the JOINed scheduled_posts row, so the inbox can show WHICH post a comment is on.
    Returns None for comments on posts we didn't publish through the app (nothing to show)."""
    cap = r.get("post_caption")
    imgs = r.get("post_image_ids")
    if not cap and not imgs:
        return None
    result = r.get("post_result")
    result = result if isinstance(result, dict) else (json.loads(result) if result else {})
    permalink = next((v.get("permalink") for v in result.values()
                      if isinstance(v, dict) and v.get("permalink")), None)
    return {
        "caption": (cap or "")[:140],
        "image_ids": [str(i) for i in (imgs or [])][:1],   # one thumbnail is enough
        "permalink": permalink,
    }


def _row(r) -> dict:
    return {
        "id": str(r["id"]),
        "connection_id": str(r["connection_id"]),
        "provider": r["provider"],
        "external_id": r["external_id"],
        "post_external_id": r["post_external_id"],
        "scheduled_post_id": str(r["scheduled_post_id"]) if r["scheduled_post_id"] else None,
        "author_name": r["author_name"],
        "author_external_id": r["author_external_id"],
        "message": r["message"],
        "permalink": r["permalink"],
        "commented_at": r["commented_at"].isoformat() if r["commented_at"] else None,
        "status": r["status"],
        "reply_text": r["reply_text"],
        "reply_external_id": r["reply_external_id"],
        "reply_mode": r["reply_mode"],
        "replied_at": r["replied_at"].isoformat() if r["replied_at"] else None,
        "created_at": r["created_at"].isoformat(),
    }


def _dt(v):
    return datetime.fromisoformat(v) if isinstance(v, str) else v


async def upsert_many(org_id: str, connection_id: str, provider: str, comments: list[dict]) -> list[dict]:
    """Idempotently insert comments. Returns ONLY the rows that were newly inserted (ON CONFLICT DO
    NOTHING), so the caller drafts a reply exactly once per comment. Each dict: external_id, message,
    post_external_id?, author_name?, author_external_id?, permalink?, commented_at?, scheduled_post_id?."""
    if not comments:
        return []
    cid = uuid.UUID(connection_id)
    out: list[dict] = []
    async with org_tx(org_id) as c:
        for cm in comments:
            sp = cm.get("scheduled_post_id")
            r = await c.fetchrow(
                "INSERT INTO comments(org_id, connection_id, provider, external_id, post_external_id, "
                "scheduled_post_id, author_name, author_external_id, message, permalink, commented_at) "
                "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) "
                "ON CONFLICT (org_id, provider, external_id) DO NOTHING "
                f"RETURNING {_COLS}",
                uuid.UUID(org_id), cid, provider, cm["external_id"], cm.get("post_external_id"),
                uuid.UUID(sp) if sp else None, cm.get("author_name"), cm.get("author_external_id"),
                cm.get("message") or "", cm.get("permalink"), _dt(cm.get("commented_at")),
            )
            if r:
                out.append(_row(r))
    return out


async def newest_commented_at(org_id: str, connection_id: str) -> datetime | None:
    """The most recent provider timestamp stored for a connection — the `since` cursor for the next poll."""
    async with org_tx(org_id) as c:
        v = await c.fetchval(
            "SELECT max(commented_at) FROM comments WHERE connection_id=$1", uuid.UUID(connection_id))
    return v


async def list_for(org_id: str, status: str | None = None, limit: int = 100) -> list[dict]:
    # LEFT JOIN the parent scheduled_post so each comment carries the post it's on (caption + image +
    # permalink) — the inbox shows that context as a clickable chip. Comments on posts not published
    # through the app simply get post=None.
    base = (f"SELECT {_QCOLS}, sp.caption AS post_caption, sp.image_ids AS post_image_ids, "
            "sp.result AS post_result FROM comments "
            "LEFT JOIN scheduled_posts sp ON sp.id = comments.scheduled_post_id ")
    order = "ORDER BY comments.commented_at DESC NULLS LAST, comments.created_at DESC "
    async with org_tx(org_id) as c:
        if status:
            rows = await c.fetch(base + "WHERE comments.status=$1 " + order + "LIMIT $2", status, limit)
        else:
            rows = await c.fetch(base + order + "LIMIT $1", limit)
    out = []
    for r in rows:
        d = _row(r)
        d["post"] = _post_context(r)
        out.append(d)
    return out


async def get(org_id: str, comment_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_COLS} FROM comments WHERE id=$1", uuid.UUID(comment_id))
    return _row(r) if r else None


async def set_draft(org_id: str, comment_id: str, reply_text: str) -> None:
    """Store an AI-suggested reply on an open comment (not posted yet)."""
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE comments SET reply_text=$1, reply_mode='draft', updated_at=now() "
            "WHERE id=$2 AND status='open'", reply_text, uuid.UUID(comment_id))


async def list_open_unevaluated(org_id: str, limit: int = 200) -> list[dict]:
    """Open comments whose drafted reply has NOT yet been through the auto-post safety gate (auto_eval_at
    IS NULL). The auto-post pass classifies each of these exactly once and then stamps auto_eval_at — so a
    static backlog the classifier always rejects is never re-fed to the LLM on every poll."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT id, connection_id, provider, external_id, message, reply_text FROM comments "
            "WHERE status='open' AND auto_eval_at IS NULL AND reply_text <> '' "
            "ORDER BY commented_at DESC NULLS LAST LIMIT $1", limit)
    return [{"id": str(r["id"]), "connection_id": str(r["connection_id"]), "provider": r["provider"],
             "external_id": r["external_id"], "message": r["message"], "reply_text": r["reply_text"]}
            for r in rows]


async def mark_auto_evaluated(org_id: str, comment_id: str) -> None:
    """Record that a comment's drafted reply has been through the auto-post safety gate (safe -> posted, or
    unsafe/banned -> left as a human-review draft). Idempotent; keeps the LLM classifier at once-per-comment
    so the auto-reply poll never re-classifies a backlog it can't clear."""
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE comments SET auto_eval_at=now(), updated_at=now() WHERE id=$1", uuid.UUID(comment_id))


async def mark_replied(org_id: str, comment_id: str, reply_text: str, reply_external_id: str,
                       reply_mode: str) -> bool:
    """Atomically record a posted reply. Exactly-once: the `reply_external_id IS NULL` guard means a second
    call (racing worker / double-click) is a no-op, so we never double-reply. Returns True if this call won."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "UPDATE comments SET status='replied', reply_text=$1, reply_external_id=$2, reply_mode=$3, "
            "replied_at=now(), updated_at=now() "
            "WHERE id=$4 AND reply_external_id IS NULL RETURNING id",
            reply_text, reply_external_id, reply_mode, uuid.UUID(comment_id))
        return r is not None


async def ignore(org_id: str, comment_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE comments SET status='ignored', updated_at=now() WHERE id=$1 AND status='open'",
            uuid.UUID(comment_id))
    return res.endswith(" 1")
