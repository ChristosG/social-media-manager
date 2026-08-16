"""Scope-gated Meta page-insights adapter.

Mirrors comments_connector: same Graph base URL/version, same `appsecret_proof` pattern.
This module is deliberately DORMANT — `insights_capable` returns False and `fetch_page_insights`
returns None — when the connection lacks the required scope.  It NEVER raises into the caller.
"""
import hashlib
import hmac
import httpx
from app.config import get_settings

_GRAPH = "https://graph.facebook.com/v21.0"

# Required scopes per provider.  Lower-cased for comparison.
_FB_SCOPE = "pages_read_engagement"
_IG_SCOPE = "instagram_manage_insights"

# Page metrics to fetch, as {output_key: graph_metric}. Meta deprecated `page_impressions` (invalid-metric
# error from 2025-11-15, fully removed ~2026-06-15) in favour of the "views" metric `page_views_total`. We
# request each metric in its OWN call and aggregate what succeeds, so a single future deprecation degrades
# that one number to 0 instead of zeroing the whole panel.
_FB_METRICS = {"impressions": "page_views_total", "engagements": "page_post_engagements"}


def insights_capable(conn: dict) -> bool:
    """True if *conn*'s granted scopes include the insights scope for its provider."""
    provider = (conn.get("provider") or "").lower()
    scopes = conn.get("scopes") or ""
    if provider == "facebook":
        return _FB_SCOPE in scopes
    if provider == "instagram":
        return _IG_SCOPE in scopes
    return False


def _proof(token: str) -> str:
    """HMAC-SHA256 of the token under the app secret (appsecret_proof)."""
    return hmac.new(get_settings().meta_app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


async def _graph_get(url: str, params: dict) -> dict:
    """Real httpx GET to the Graph API.  Test seam: monkeypatch this on the module."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _first_value(data: dict) -> int:
    """Pull the first numeric value out of a single-metric /insights response, defaulting to 0."""
    values = (data.get("data") or [{}])[0].get("values") or []
    v = values[0].get("value") if values else 0
    return int(v) if isinstance(v, (int, float)) else 0


# Per-post metric maps. FB post insights vs IG media insights use different metric names; we fetch each in
# its own call (resilient to a single deprecation) and normalise to {reach, engagement, link_clicks, ...}.
# NOTE: exact metric strings are best-effort per Meta's current docs — verify against a live call; the
# per-metric resilience degrades a wrong/dead name to 0 rather than crashing.
_FB_POST_METRICS = {"reach": "post_impressions_unique", "engagement": "post_engaged_users",
                    "link_clicks": "post_clicks"}
_IG_POST_METRICS = {"reach": "reach", "likes": "likes", "comments": "comments",
                    "engagement": "total_interactions"}


async def fetch_post_metrics(provider: str, external_id: str, token: str) -> dict:
    """Best-effort per-post metrics, normalised. Never raises; missing/dead metrics default to 0."""
    metric_map = _FB_POST_METRICS if (provider or "").lower() == "facebook" else _IG_POST_METRICS
    proof = _proof(token)
    out: dict[str, int] = {}
    for key, metric in metric_map.items():
        try:
            data = await _graph_get(f"{_GRAPH}/{external_id}/insights",
                                    {"metric": metric, "access_token": token, "appsecret_proof": proof})
            out[key] = _first_value(data)
        except Exception:
            out[key] = 0
    return out


async def fetch_follower_count(provider: str, external_id: str, token: str) -> int:
    """Current follower count for a page/IG account. 0 on any failure (never raises).

    FB Pages: prefer `followers_count` (page *followers*) over the legacy `fan_count` (page *likes*) — a
    modern page routinely has fan_count=0 while followers_count>0, which is why the old fan_count-only path
    reported 0 followers. We request both and take followers_count, falling back to fan_count. IG exposes
    only `followers_count`.
    """
    prov = (provider or "").lower()
    fields = "followers_count,fan_count" if prov == "facebook" else "followers_count"
    try:
        data = await _graph_get(f"{_GRAPH}/{external_id}",
                                {"fields": fields, "access_token": token, "appsecret_proof": _proof(token)})
        for key in ("followers_count", "fan_count"):
            v = data.get(key)
            if isinstance(v, (int, float)):
                return int(v)
        return 0
    except Exception:
        return 0


def _summary_count(field) -> int:
    """Pull `.summary.total_count` out of a FB edge field (likes/comments requested with .summary(true))."""
    if isinstance(field, dict):
        s = field.get("summary")
        if isinstance(s, dict) and isinstance(s.get("total_count"), (int, float)):
            return int(s["total_count"])
    return 0


async def fetch_account_posts(provider: str, account_id: str, token: str, limit: int = 25) -> list[dict]:
    """List the connected account's recent posts WITH their Meta object id (graph.py's listing drops the id,
    which we need to dedup + link metrics) AND inline engagement. Crucially, likes/comments come from plain
    object FIELDS (IG `like_count`/`comments_count` under instagram_basic; FB `likes/comments.summary`) — NOT
    the `/insights` endpoint — so engagement is captured even when the account lacks the insights scope.
    Normalised to [{external_id, caption, permalink, image_url, posted_at, media_type, metrics}].
    Never raises; [] on failure."""
    prov = (provider or "").lower()
    proof = _proof(token)
    try:
        if prov == "facebook":
            data = await _graph_get(
                f"{_GRAPH}/{account_id}/published_posts",
                {"fields": "id,message,created_time,permalink_url,full_picture,shares,"
                           "likes.summary(true).limit(0),comments.summary(true).limit(0)",
                 "limit": limit, "access_token": token, "appsecret_proof": proof})
            rows = []
            for p in data.get("data", []):
                likes = _summary_count(p.get("likes"))
                comments = _summary_count(p.get("comments"))
                shares = (p.get("shares") or {}).get("count", 0) if isinstance(p.get("shares"), dict) else 0
                rows.append({
                    "external_id": p.get("id"), "caption": (p.get("message") or "").strip(),
                    "permalink": p.get("permalink_url"), "image_url": p.get("full_picture"),
                    "posted_at": p.get("created_time"), "media_type": "post",
                    "metrics": {"likes": likes, "comments": comments, "shares": int(shares or 0),
                                "engagement": likes + comments + int(shares or 0)}})
        else:
            data = await _graph_get(
                f"{_GRAPH}/{account_id}/media",
                {"fields": "id,caption,timestamp,permalink,media_url,thumbnail_url,media_type,"
                           "like_count,comments_count",
                 "limit": limit, "access_token": token, "appsecret_proof": proof})
            rows = []
            for p in data.get("data", []):
                likes = int(p.get("like_count") or 0)
                comments = int(p.get("comments_count") or 0)
                rows.append({
                    "external_id": p.get("id"), "caption": (p.get("caption") or "").strip(),
                    "permalink": p.get("permalink"),
                    "image_url": p.get("thumbnail_url") or p.get("media_url"),
                    "posted_at": p.get("timestamp"), "media_type": p.get("media_type"),
                    "metrics": {"likes": likes, "comments": comments,
                                "engagement": likes + comments}})
        return [r for r in rows if r.get("external_id")]
    except Exception:
        return []


async def fetch_page_insights(conn: dict, token: str) -> dict | None:
    """Return ``{"impressions": int, "engagements": int}`` for *conn*, or None.

    Returns None when the connection lacks the insights scope OR every metric call fails (a genuine error,
    so the caller can distinguish 'no permission' from 'we have permission but Meta/the metric failed' and
    show an honest message). A partial success (one metric works, one is deprecated) still returns numbers.
    It NEVER raises.
    """
    if not insights_capable(conn):
        return None
    proof = _proof(token)
    page_id = conn["external_id"]
    out: dict[str, int] = {"impressions": 0, "engagements": 0}
    any_ok = False
    for out_key, metric in _FB_METRICS.items():
        try:
            data = await _graph_get(
                f"{_GRAPH}/{page_id}/insights",
                {"metric": metric, "access_token": token, "appsecret_proof": proof},
            )
            out[out_key] = _first_value(data)
            any_ok = True
        except Exception:
            continue  # one metric failing (e.g. a deprecation) must not zero the others
    return out if any_ok else None
