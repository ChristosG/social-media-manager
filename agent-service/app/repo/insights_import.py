"""Import a connected Meta account's REAL posts into the ledger so Insights reflect the actual account, not
just what Social Studio published. Each imported post lands as origin='imported', status='posted', carrying
the Meta object id (for dedup + metric linking) and a per-post metrics snapshot. App-created/published posts
are skipped so we never duplicate them.
"""
import json
import logging
import uuid

from app.db.pool import org_tx
from app.repo import post_metrics as pm
from app.social import insights_connector as ic
from app.social.graph import _parse_dt

logger = logging.getLogger(__name__)


async def _known_external_ids(org_id: str) -> set[str]:
    """External ids we already track: previously-imported posts + posts WE published (their Meta ids live in
    scheduled_posts.result). Importing must skip both so an app-published post isn't duplicated as 'imported'."""
    known: set[str] = set()
    async with org_tx(org_id) as c:
        for r in await c.fetch("SELECT external_post_id FROM posts WHERE external_post_id IS NOT NULL"):
            known.add(r["external_post_id"])
        sched = await c.fetch("SELECT result FROM scheduled_posts WHERE status='published'")
    for r in sched:
        res = r["result"]
        res = res if isinstance(res, dict) else (json.loads(res) if res else {})
        for v in res.values():
            if isinstance(v, dict) and v.get("id"):
                known.add(str(v["id"]))
    return known


async def _insert_imported_post(org_id: str, provider: str, ext: str, caption: str, posted_at) -> str | None:
    """Insert one imported ledger post (status='posted', origin='imported'); dedup on (org, external_post_id)
    via the partial unique index. Returns the new post id, or None if it already existed."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "INSERT INTO posts(org_id, title, brief, status, platform, content, origin, external_post_id, "
            "                  posted_at) "
            "VALUES($1,$2,$3,'posted',$4,$5,'imported',$6,$7) "
            "ON CONFLICT (org_id, external_post_id) WHERE external_post_id IS NOT NULL DO NOTHING "
            "RETURNING id",
            uuid.UUID(org_id), (caption or "Imported post")[:120], caption or None, provider,
            caption or None, ext, posted_at)
    return str(r["id"]) if r else None


async def import_account(org_id: str, conn: dict, token: str, limit: int = 25) -> dict:
    """Import recent posts (+ their metrics) for one connection. Best-effort & idempotent. Returns
    {imported, metrics}."""
    provider, account_id = conn.get("provider"), conn.get("external_id")
    cid = conn.get("id")
    if not (provider and account_id and token):
        return {"imported": 0, "metrics": 0}
    posts = await ic.fetch_account_posts(provider, account_id, token, limit=limit)
    known = await _known_external_ids(org_id)
    imported = metrics_n = 0
    for p in posts:
        ext = p.get("external_id")
        if not ext or ext in known:
            continue
        pid = await _insert_imported_post(org_id, provider, ext, p.get("caption") or "",
                                          _parse_dt(p.get("posted_at")))
        if not pid:
            continue
        known.add(ext)
        imported += 1
        # Inline likes/comments/engagement come from plain object fields (no insights scope needed). Only
        # reach/impressions need /insights, so we call it solely when the account actually has that scope.
        metrics = dict(p.get("metrics") or {})
        if ic.insights_capable(conn):
            try:
                for k, v in (await ic.fetch_post_metrics(provider, ext, token)).items():
                    if v and not metrics.get(k):
                        metrics[k] = v
            except Exception:
                logger.exception("import: insights metrics failed org=%s ext=%s", org_id, ext)
        try:
            await pm.record_snapshot(org_id, pid, cid, provider, ext, metrics)
            metrics_n += 1
        except Exception:
            logger.exception("import: snapshot failed org=%s ext=%s", org_id, ext)
    if imported:
        logger.info("import: org=%s provider=%s imported=%d metrics=%d", org_id, provider, imported, metrics_n)
    return {"imported": imported, "metrics": metrics_n}
