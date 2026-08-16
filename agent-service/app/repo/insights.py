"""Insights aggregation over the owned `post_metrics` / `audience_snapshots` tables plus the legacy
owned-data funnel and the optional Meta page-insights block.

`insights_dashboard()` is the Phase-1 dashboard the API now serves. It computes KPI cards (reach,
engagement, link_clicks, followers, published) with a period-over-period delta, a weekly series, and a
top-posts table — all from per-post snapshots. The older `summary()` shape (status_funnel / posts_per_day /
learned_count / comments / meta_*) is folded INTO the dashboard payload so nothing that consumed it breaks.

Latest-per-post: a post can be snapshotted many times (engagement keeps climbing); for window totals we use
the LATEST snapshot per post (DISTINCT ON (post_id) ... ORDER BY captured_at DESC) so we count each post's
current numbers once, never double-counting earlier snapshots.

Weekly series: a fully-correct weekly "latest-per-post within each week" is more machinery than Phase 1
needs; we instead sum the metric values of all snapshots captured in each week. This over-counts when a post
is snapshotted twice in the same week, but it's monotonic, cheap, and good enough to draw a trend line — the
KPI cards (which DO use latest-per-post) are the authoritative numbers.
"""
import asyncio
import json
import time
import uuid

from app.db.pool import org_tx
from app.repo import connections as conn_repo
from app.social import insights_connector as ic

# Statuses that count as "published" for the published-count KPI.
_PUBLISHED_STATUSES = ("posted", "scheduled")
# Per-post metric keys we surface as KPIs / in top_posts. `engagement` drives the top-posts ordering.
_KPI_KEYS = ("reach", "engagement", "link_clicks")


async def _table_exists(c, name: str) -> bool:
    return bool(await c.fetchval("SELECT to_regclass($1)", f"public.{name}"))


def _kpi(cur: float, prev: float) -> dict:
    """A KPI card: current value + period-over-period delta. delta_pct is 0 when prev is 0 (no baseline)."""
    delta = round((cur - prev) / prev * 100) if prev else 0
    return {"value": int(cur), "delta_pct": delta}


async def insights_dashboard(org_id: str, platform: str = "all", range_days: int = 30) -> dict:
    """Aggregated Phase-1 insights dashboard. All owned-data reads run inside one org_tx (RLS-scoped)."""
    range_days = max(1, int(range_days or 30))
    plat = (platform or "all").lower()

    async with org_tx(org_id) as c:
        # ---- KPI window sums via latest-snapshot-per-post ---------------------------------------------
        async def _window_sums(start_offset_days: int, end_offset_days: int, prov_param_idx: int) -> dict:
            """Sum reach/engagement/link_clicks over the LATEST snapshot per post in
            [now-start, now-end]. prov_param_idx is the $N index the provider value lives at (or 0)."""
            prov_sql = f" AND provider = ${prov_param_idx}" if prov_param_idx else ""
            row = await c.fetchrow(
                "WITH latest AS ("
                "  SELECT DISTINCT ON (post_id) post_id, metrics FROM post_metrics "
                "  WHERE captured_at >= now() - make_interval(days => $1::int) "
                "    AND captured_at <  now() - make_interval(days => $2::int)"
                f"   {prov_sql} "
                "  ORDER BY post_id, captured_at DESC"
                ") SELECT "
                "  COALESCE(SUM((metrics->>'reach')::numeric),0)       AS reach, "
                "  COALESCE(SUM((metrics->>'engagement')::numeric),0)  AS engagement, "
                "  COALESCE(SUM((metrics->>'link_clicks')::numeric),0) AS link_clicks "
                "FROM latest",
                start_offset_days, end_offset_days, *([plat] if prov_param_idx else []))
            return {"reach": float(row["reach"]), "engagement": float(row["engagement"]),
                    "link_clicks": float(row["link_clicks"])}

        cur = await _window_sums(range_days, 0, 3 if plat != "all" else 0)
        prev = await _window_sums(2 * range_days, range_days, 3 if plat != "all" else 0)

        # followers — latest audience snapshot (optionally provider-filtered).
        if plat != "all":
            followers = await c.fetchval(
                "SELECT followers FROM audience_snapshots WHERE provider=$1 "
                "ORDER BY captured_at DESC LIMIT 1", plat) or 0
            followers_prev = await c.fetchval(
                "SELECT followers FROM audience_snapshots WHERE provider=$1 "
                "  AND captured_at < now() - make_interval(days => $2::int) "
                "ORDER BY captured_at DESC LIMIT 1", plat, range_days) or 0
        else:
            # "All" = sum of the LATEST snapshot per provider, not a single latest row (which would show
            # just one account's followers and hide the other connected account entirely).
            followers = await c.fetchval(
                "SELECT COALESCE(SUM(followers),0) FROM ("
                "  SELECT DISTINCT ON (provider) followers FROM audience_snapshots "
                "  ORDER BY provider, captured_at DESC) t") or 0
            followers_prev = await c.fetchval(
                "SELECT COALESCE(SUM(followers),0) FROM ("
                "  SELECT DISTINCT ON (provider) followers FROM audience_snapshots "
                "  WHERE captured_at < now() - make_interval(days => $1::int) "
                "  ORDER BY provider, captured_at DESC) t", range_days) or 0

        # published — posts that went live (status posted/scheduled) within each window, by updated_at.
        # Honour the platform filter (the old query ignored it, so All=FB=IG returned the same count).
        if plat != "all":
            pub_cur = await c.fetchval(
                "SELECT count(*) FROM posts WHERE status = ANY($1::text[]) "
                "  AND updated_at >= now() - make_interval(days => $2::int) AND platform = $3",
                list(_PUBLISHED_STATUSES), range_days, plat) or 0
            pub_prev = await c.fetchval(
                "SELECT count(*) FROM posts WHERE status = ANY($1::text[]) "
                "  AND updated_at >= now() - make_interval(days => $2::int) "
                "  AND updated_at <  now() - make_interval(days => $3::int) AND platform = $4",
                list(_PUBLISHED_STATUSES), 2 * range_days, range_days, plat) or 0
        else:
            pub_cur = await c.fetchval(
                "SELECT count(*) FROM posts WHERE status = ANY($1::text[]) "
                "  AND updated_at >= now() - make_interval(days => $2::int)",
                list(_PUBLISHED_STATUSES), range_days) or 0
            pub_prev = await c.fetchval(
                "SELECT count(*) FROM posts WHERE status = ANY($1::text[]) "
                "  AND updated_at >= now() - make_interval(days => $2::int) "
                "  AND updated_at <  now() - make_interval(days => $3::int)",
                list(_PUBLISHED_STATUSES), 2 * range_days, range_days) or 0

        kpis = {
            "reach": _kpi(cur["reach"], prev["reach"]),
            "engagement": _kpi(cur["engagement"], prev["engagement"]),
            "link_clicks": _kpi(cur["link_clicks"], prev["link_clicks"]),
            "followers": _kpi(followers, followers_prev),
            "published": _kpi(pub_cur, pub_prev),
        }

        # ---- weekly series (sum-of-snapshots-in-week approximation; see module docstring) -------------
        series_prov = " AND provider = $2" if plat != "all" else ""
        series_rows = await c.fetch(
            "SELECT date_trunc('week', captured_at) AS week, "
            "  COALESCE(SUM((metrics->>'reach')::numeric),0)      AS reach, "
            "  COALESCE(SUM((metrics->>'engagement')::numeric),0) AS engagement "
            "FROM post_metrics "
            "WHERE captured_at >= now() - make_interval(days => $1::int) "
            f"  {series_prov} "
            "GROUP BY week ORDER BY week",
            range_days, *([plat] if plat != "all" else []))
        series = [{"week": r["week"].date().isoformat(),
                   "reach": int(r["reach"]), "engagement": int(r["engagement"])}
                  for r in series_rows]

        # ---- top posts: latest snapshot per post in window, by engagement desc -----------------------
        top_prov = " AND pm.provider = $2" if plat != "all" else ""
        top_rows = await c.fetch(
            "WITH latest AS ("
            "  SELECT DISTINCT ON (pm.post_id) pm.post_id, pm.provider, pm.metrics "
            "  FROM post_metrics pm "
            "  WHERE pm.captured_at >= now() - make_interval(days => $1::int) "
            f"   {top_prov} "
            "  ORDER BY pm.post_id, pm.captured_at DESC"
            ") "
            "SELECT l.post_id, l.provider, l.metrics, p.content, p.origin, "
            "  (SELECT sp.result FROM scheduled_posts sp "
            "    WHERE sp.post_id = l.post_id AND sp.status='published' "
            "    ORDER BY sp.updated_at DESC LIMIT 1) AS sp_result "
            "FROM latest l LEFT JOIN posts p ON p.id = l.post_id "
            "ORDER BY (l.metrics->>'engagement')::numeric DESC NULLS LAST "
            "LIMIT 5",
            range_days, *([plat] if plat != "all" else []))

        top_posts = []
        for r in top_rows:
            m = r["metrics"] if isinstance(r["metrics"], dict) else json.loads(r["metrics"] or "{}")
            result = r["sp_result"]
            result = result if isinstance(result, dict) else (json.loads(result) if result else {})
            permalink = next((v.get("permalink") for v in result.values()
                              if isinstance(v, dict) and v.get("permalink")), None)
            entry = {
                "post_id": str(r["post_id"]),
                "caption": r["content"],
                "provider": r["provider"],
                "origin": r["origin"],
                "reach": int(m.get("reach") or 0),
                "engagement": int(m.get("engagement") or 0),
                "link_clicks": int(m.get("link_clicks") or 0),
            }
            if permalink:
                entry["permalink"] = permalink
            top_posts.append(entry)

        # ---- updated_at: most recent snapshot we have (any provider, full history) -------------------
        updated_at = await c.fetchval("SELECT max(captured_at) FROM post_metrics")
        updated_at = updated_at.isoformat() if updated_at else None

        # ---- legacy owned-data funnel + secondary widgets (kept so old consumers don't break) --------
        funnel = {r["status"]: r["n"] for r in await c.fetch(
            "SELECT status, count(*) n FROM posts GROUP BY status")}
        per_day = [{"day": r["d"].isoformat(), "count": r["n"]} for r in await c.fetch(
            "SELECT date_trunc('day', created_at)::date d, count(*) n FROM posts "
            "WHERE created_at > now() - interval '30 days' GROUP BY d ORDER BY d")]
        learned = (await c.fetchrow(
            "SELECT count(*) n FROM memory_entries WHERE active AND NOT pending_review"))["n"]
        comments = {}
        if await _table_exists(c, "comments"):
            comments = {r["status"]: r["n"] for r in await c.fetch(
                "SELECT status, count(*) n FROM comments GROUP BY status")}

    meta_status, meta = await _meta_block_cached(org_id)
    mix = await content_mix(org_id, range_days)

    out = {
        "kpis": kpis,
        "series": series,
        "top_posts": top_posts,
        "updated_at": updated_at,
        # secondary widgets / back-compat keys:
        "content_mix": mix,
        "status_funnel": funnel,
        "posts_per_day": per_day,
        "learned_count": learned,
        "comments": comments,
        "meta_available": meta_status == "ok",
        "meta_status": meta_status,
    }
    if meta is not None:
        out["meta"] = meta
    return out


async def content_mix(org_id: str, range_days: int = 30) -> list[dict]:
    """Post counts by content pillar over the window (owned data — no Meta dep). Drives the mix donut."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT COALESCE(NULLIF(pillar,''),'uncategorized') AS pillar, count(*) AS n FROM posts "
            "WHERE status IN ('drafted','approved','scheduled','posted') "
            "AND created_at > now() - make_interval(days => $1::int) GROUP BY 1 ORDER BY n DESC",
            range_days)
    return [{"pillar": r["pillar"], "count": r["n"]} for r in rows]


async def top_exemplars(org_id: str, limit: int = 3, min_measured: int = 6) -> list[dict]:
    """The org's best-performing posts by latest measured engagement, as [{caption, engagement}], to feed the
    draft writer ('posts like X resonated'). Returns [] until at least `min_measured` posts have metrics, so
    small-N noise can't mislead the model. All-platform (drafting here is platform-agnostic)."""
    async with org_tx(org_id) as c:
        measured = await c.fetchval("SELECT count(DISTINCT post_id) FROM post_metrics")
        if (measured or 0) < min_measured:
            return []
        rows = await c.fetch(
            "WITH latest AS ("
            "  SELECT DISTINCT ON (pm.post_id) pm.post_id, pm.metrics "
            "  FROM post_metrics pm ORDER BY pm.post_id, pm.captured_at DESC"
            ") "
            "SELECT p.content, COALESCE((l.metrics->>'engagement')::numeric, 0) AS engagement "
            "FROM latest l JOIN posts p ON p.id = l.post_id "
            "WHERE p.content IS NOT NULL AND p.content <> '' "
            "ORDER BY (l.metrics->>'engagement')::numeric DESC NULLS LAST "
            "LIMIT $1",
            limit)
    return [{"caption": r["content"], "engagement": int(r["engagement"] or 0)} for r in rows]


async def best_windows(org_id: str, platform: str = "all", min_posts: int = 8,
                       top: int = 4) -> list[tuple[int, int]] | None:
    """The org's strongest (weekday, hour) posting windows by measured engagement, best first — or None when
    fewer than `min_posts` measured posts exist (too little signal → caller keeps the static priors).
    weekday is 0=Mon..6=Sun (matching besttime.PLATFORM_WINDOWS). Uses each post's planned_at as the slot
    time and its latest engagement snapshot; a shrinkage factor stops a single fluke slot from dominating."""
    plat = (platform or "all").lower()
    where_prov = "" if plat == "all" else " AND l.provider = $1"
    params = [] if plat == "all" else [plat]
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "WITH latest AS ("
            "  SELECT DISTINCT ON (pm.post_id) pm.post_id, pm.provider, "
            "         COALESCE((pm.metrics->>'engagement')::numeric, 0) AS eng "
            "  FROM post_metrics pm ORDER BY pm.post_id, pm.captured_at DESC) "
            "SELECT (EXTRACT(ISODOW FROM p.planned_at)::int - 1) AS wd, "
            "       EXTRACT(HOUR FROM p.planned_at)::int AS hr, "
            "       avg(l.eng) AS avg_eng, count(*) AS n "
            "FROM latest l JOIN posts p ON p.id = l.post_id "
            "WHERE p.planned_at IS NOT NULL" + where_prov + " "
            "GROUP BY 1, 2",
            *params)
    total = sum(int(r["n"]) for r in rows)
    if total < min_posts:
        return None
    k = 3   # shrinkage: a slot with few samples is pulled toward the field, so one lucky post can't win
    scored = sorted(rows, key=lambda r: float(r["avg_eng"]) * int(r["n"]) / (int(r["n"]) + k), reverse=True)
    return [(int(r["wd"]), int(r["hr"])) for r in scored[:top]]


async def post_series(org_id: str, post_id: str) -> list[dict]:
    """The captured snapshot series for one post, oldest → newest, for the drill-down chart."""
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT captured_at, metrics FROM post_metrics WHERE post_id=$1 ORDER BY captured_at ASC",
            uuid.UUID(post_id))
    out = []
    for r in rows:
        m = r["metrics"] if isinstance(r["metrics"], dict) else json.loads(r["metrics"] or "{}")
        out.append({
            "captured_at": r["captured_at"].isoformat(),
            "reach": int(m.get("reach") or 0),
            "engagement": int(m.get("engagement") or 0),
            "link_clicks": int(m.get("link_clicks") or 0),
        })
    return out


# --- Meta page-insights cache -------------------------------------------------------------------
# The Meta block makes a LIVE Graph API call (httpx, 30s ceiling). Serving the interactive dashboard
# straight off that means every insights view blocks on Meta — measured at ~3s, and up to 30s+ when
# Meta is slow/down. So we (1) time-box the live call to _META_DEADLINE and (2) cache the result
# per-process per-org for a short TTL, so at most one dashboard load per TTL pays the Meta cost and a
# Meta outage degrades to "temporarily unavailable" instead of hanging the screen. Single uvicorn
# process → a module-level dict is a correct, sufficient cache. Keyed by org only (the block is not
# platform-filtered), so switching the platform filter reuses it.
_META_CACHE: dict[str, tuple[float, str, dict | None]] = {}
_META_TTL_OK = 300.0    # 'ok' / 'no_scope' are stable facts → cache 5 min
_META_TTL_ERR = 60.0    # a transient error should be retried sooner
_META_DEADLINE = 2.5    # never block the dashboard longer than this on the live Graph call


def invalidate_meta(org_id: str) -> None:
    """Drop the cached Meta block for an org so the next dashboard load fetches live — called when the
    user explicitly asks for fresh numbers (manual 'Refresh')."""
    _META_CACHE.pop(org_id, None)


async def _meta_block_cached(org_id: str) -> tuple[str, dict | None]:
    """`_meta_block` behind a short-TTL, time-boxed cache. A slow/hung Meta is bounded to _META_DEADLINE
    and falls back to the last-known value (or a soft 'error') rather than stalling the insights screen."""
    now = time.monotonic()
    hit = _META_CACHE.get(org_id)
    if hit and now - hit[0] < (_META_TTL_OK if hit[1] != "error" else _META_TTL_ERR):
        return hit[1], hit[2]
    try:
        status, meta = await asyncio.wait_for(_meta_block(org_id), timeout=_META_DEADLINE)
    except (asyncio.TimeoutError, Exception):
        # Time-box tripped or an unexpected failure: keep serving the last-known block if we have one,
        # else report a soft error. Don't refresh the timestamp on a stale hit, so it retries next load.
        if hit:
            return hit[1], hit[2]
        status, meta = "error", None
    _META_CACHE[org_id] = (now, status, meta)
    return status, meta


async def _meta_block(org_id: str) -> tuple[str, dict | None]:
    """Optional Meta page-insights. meta_status: 'no_scope' | 'error' | 'ok' (see original summary docs).

    'no_scope' — no connection has the insights scope (UI: "connect insights permissions").
    'error'    — a capable connection exists but Meta/the metric failed (UI: "temporarily unavailable").
    'ok'       — real numbers. A Meta failure must NEVER break the owned-data dashboard.
    """
    meta_status = "no_scope"
    meta: dict | None = None
    try:
        for conn in await conn_repo.list_connections(org_id):
            if not ic.insights_capable(conn):
                continue
            conn_id = conn.get("id")
            if not conn_id:
                continue
            token = await conn_repo.get_token(org_id, conn_id)
            if not token:
                continue
            meta_status = "error"  # capable connection → only a live fetch flips this to ok
            result = await ic.fetch_page_insights(conn, token=token)
            if result is not None:
                meta_status = "ok"
                meta = result
                break
    except Exception:
        meta_status = "error"
    return meta_status, meta


async def summary(org_id: str) -> dict:
    """Back-compat entrypoint. Now delegates to the full dashboard (a superset of the old shape), so any
    caller still importing `summary` keeps working while serving the richer payload."""
    return await insights_dashboard(org_id)
