import asyncio
import logging
from datetime import datetime, timezone, timedelta
from app.repo import sources as src_repo, documents as doc_repo
from app.repo import connections as conn_repo
from app.sources import store
from app.sources.discover import discover as discover_source   # re-exported for test monkeypatch
from app.sources.extract import extract_article                # re-exported for test monkeypatch
from app.agent import research
from app.security.redact import redact_secrets
from app.social.graph import fetch_facebook_posts, fetch_instagram_posts  # re-exported for test monkeypatch

logger = logging.getLogger(__name__)
_KEEP_PER_SOURCE = 60
MIN_REFRESH_INTERVAL = timedelta(minutes=30)   # on-open auto-refresh throttle; force=True bypasses

_ingesting: set[str] = set()   # in-process single-flight (one uvicorn worker)
_bg: set = set()               # keep refs to detached ingest tasks so they aren't GC'd


async def ingest_source(org_id: str, source_id: str) -> dict:
    """Discover → fetch → extract → persist the latest articles for one source; update its state.
    Returns {status, ingested, skipped, failed}. Never raises — failures land in source state."""
    src = await src_repo.get_source(org_id, source_id)
    if not src:
        return {"status": "failed", "ingested": 0, "skipped": 0, "failed": 0, "error": "source not found"}
    cfg = src["config"] or {}
    url = cfg.get("url")
    if not url:
        await src_repo.set_state(org_id, source_id, last_status="failed", last_error="no url")
        return {"status": "failed", "ingested": 0, "skipped": 0, "failed": 0, "error": "no url"}

    ingested = skipped = failed = 0
    feed_url = detected = None
    try:
        detected, feed_url, urls = await discover_source(url, cfg.get("type", "auto"), int(cfg.get("latest_n", 15)))
        for u in urls:
            try:
                html = await research.fetch_html(u)
                art = extract_article(html, u) if html else None
                if not art:
                    failed += 1; continue
                art["url"] = u
                if await store.persist_article(org_id, source_id, art):
                    ingested += 1
                else:
                    skipped += 1
            except Exception:
                logger.exception("ingest article failed url=%s", u)
                failed += 1
        await doc_repo.prune_documents(org_id, source_id, keep=_KEEP_PER_SOURCE)
    except Exception as e:
        logger.exception("ingest_source failed source=%s", source_id)
        safe_err = redact_secrets(str(e))
        await src_repo.set_state(org_id, source_id, last_status="failed", last_error=safe_err[:300])
        return {"status": "failed", "ingested": ingested, "skipped": skipped, "failed": failed, "error": safe_err}

    total_docs = await doc_repo.count_documents(org_id, source_id)
    status = "ok" if total_docs > 0 else ("partial" if (ingested or skipped) else "failed")
    if failed and (ingested or skipped):
        status = "partial"
    await src_repo.set_state(org_id, source_id, last_status=status, detected_kind=detected,
                             feed_url=feed_url, last_error=None,
                             last_refreshed_at=datetime.now(timezone.utc))
    return {"status": status, "ingested": ingested, "skipped": skipped, "failed": failed}


async def ingest_social_source(org_id: str, source_id: str) -> dict:
    """Pull the connected FB Page / IG account's OWN posts via the Graph API → documents."""
    src = await src_repo.get_source(org_id, source_id)
    if not src or not src.get("connection_id"):
        await src_repo.set_state(org_id, source_id, last_status="failed", last_error="not connected")
        return {"status": "failed", "ingested": 0, "skipped": 0, "failed": 0, "error": "not connected"}
    conn = await conn_repo.get_connection(org_id, src["connection_id"])
    token = await conn_repo.get_token(org_id, src["connection_id"])
    if not conn or not token:
        await src_repo.set_state(org_id, source_id, last_status="failed", last_error="missing connection/token")
        return {"status": "failed", "ingested": 0, "skipped": 0, "failed": 0, "error": "missing token"}
    n = int((src.get("config") or {}).get("latest_n", 15))
    try:
        if src["kind"] == "facebook":
            posts = await fetch_facebook_posts(token, conn["external_id"], n)
        else:
            posts = await fetch_instagram_posts(token, conn["external_id"], n)
    except Exception as e:
        logger.exception("social fetch failed source=%s", source_id)
        safe_err = redact_secrets(str(e))
        await conn_repo.set_status(org_id, src["connection_id"], "needs_reconnect")
        await src_repo.set_state(org_id, source_id, last_status="failed", last_error=safe_err[:300])
        return {"status": "failed", "ingested": 0, "skipped": 0, "failed": 0, "error": safe_err}
    ingested = skipped = 0
    for post in posts:
        try:
            if await store.persist_article(org_id, source_id, post):
                ingested += 1
            else:
                skipped += 1
        except Exception:
            logger.exception("social persist failed")
    # Reconcile deletions: a post removed on the platform won't come back in this fetch, so drop it from
    # the KB (so we stop grounding/citing a deleted post). Bounded to the window we just observed — only
    # documents at/after the oldest fetched post are eligible, so older un-refetched posts are never lost.
    kept_urls = [p["url"] for p in posts if p.get("url")]
    dates = [p["published_at"] for p in posts if p.get("published_at")]
    if kept_urls and dates:
        await doc_repo.reconcile_to_urls(org_id, source_id, kept_urls, min(dates))
    await doc_repo.prune_documents(org_id, source_id, keep=_KEEP_PER_SOURCE)
    # Reaching here means the Graph fetch succeeded (errors are caught above and set 'failed' + last_error).
    # An account with zero posts is healthy, not a failure — only real fetch errors are 'failed'.
    status = "ok"
    await src_repo.set_state(org_id, source_id, last_status=status, detected_kind=src["kind"],
                             last_error=None, last_refreshed_at=datetime.now(timezone.utc))
    return {"status": status, "ingested": ingested, "skipped": skipped, "failed": 0}


async def run_ingest(org_id: str, source_id: str) -> dict:
    """Single-flight wrapper around ingest_source / ingest_social_source: a source already being
    ingested is skipped, so add-on-create, manual Refresh, and the scheduler never double-ingest."""
    if source_id in _ingesting:
        return {"status": "skipped", "ingested": 0, "skipped": 0, "failed": 0, "reason": "already running"}
    # Determine the source kind before acquiring the single-flight lock so the DB round-trip
    # doesn't hold the lock across an await and inadvertently block a concurrent Refresh request.
    try:
        src = await src_repo.get_source(org_id, source_id)
    except Exception:
        src = None
    is_social = src and src["kind"] in ("facebook", "instagram")
    # Re-check after the await (single-threaded asyncio, but the background task could have
    # entered _ingesting while we were awaiting get_source above).
    if source_id in _ingesting:
        return {"status": "skipped", "ingested": 0, "skipped": 0, "failed": 0, "reason": "already running"}
    _ingesting.add(source_id)
    try:
        if is_social:
            return await ingest_social_source(org_id, source_id)
        return await ingest_source(org_id, source_id)
    finally:
        _ingesting.discard(source_id)


def schedule_ingest(org_id: str, source_id: str) -> None:
    """Fire-and-forget background ingest (used for ingest-on-add). Holds a task ref until it finishes."""
    task = asyncio.create_task(run_ingest(org_id, source_id))
    _bg.add(task)
    task.add_done_callback(_bg.discard)


async def refresh_org_social(org_id: str, provider: str | None = None, force: bool = False) -> dict:
    """Refresh the org's facebook/instagram sources. Throttled: a source refreshed within
    MIN_REFRESH_INTERVAL is skipped unless force=True. Awaits the ingests (single-flight guards
    overlap) and returns a per-source summary so the manual Refresh button gets real feedback."""
    sources = await src_repo.list_sources(org_id)
    now = datetime.now(timezone.utc)
    to_run, skipped_fresh = [], []
    for s in sources:
        if s["kind"] not in ("facebook", "instagram"):
            continue
        if provider and s["kind"] != provider:
            continue
        last = s.get("last_refreshed_at")
        if not force and last and (now - datetime.fromisoformat(last)) < MIN_REFRESH_INTERVAL:
            skipped_fresh.append(s["id"])
            continue
        to_run.append(s)
    results = await asyncio.gather(*(run_ingest(org_id, s["id"]) for s in to_run),
                                   return_exceptions=True)
    refreshed = []
    for s, r in zip(to_run, results):
        if isinstance(r, BaseException):
            logger.error("refresh_org_social: run_ingest raised for source=%s", s["id"], exc_info=r)
            refreshed.append({"source_id": s["id"], "status": "failed", "ingested": 0, "skipped": 0})
        else:
            refreshed.append({"source_id": s["id"], "status": r.get("status"),
                              "ingested": r.get("ingested", 0), "skipped": r.get("skipped", 0)})
    return {"refreshed": refreshed, "skipped_fresh": skipped_fresh}
