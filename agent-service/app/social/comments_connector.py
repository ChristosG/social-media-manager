"""Read comments on the org's published posts and post replies back, via the Meta Graph API.

Mirrors app/social/graph.py + publish.py: same Graph version, `appsecret_proof` on every call, and a
`_transport` test hook (None → real network). Read-only fetch + a single reply POST per comment; the
caller (ingest) owns idempotency/exactly-once via the comments repo."""
import hashlib
import hmac
from datetime import datetime, timezone
import httpx
from app.config import get_settings

_GRAPH = "https://graph.facebook.com/v21.0"
_transport: httpx.MockTransport | None = None   # test hook; None → real network


class CommentError(Exception):
    ...


def _proof(token: str) -> str:
    return hmac.new(get_settings().meta_app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("+0000", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


async def _call(method: str, path: str, token: str, params: dict) -> dict:
    p = {**params, "access_token": token, "appsecret_proof": _proof(token)}
    async with httpx.AsyncClient(timeout=30, transport=_transport) as c:
        r = await (c.post(f"{_GRAPH}/{path}", data=p) if method == "POST"
                   else c.get(f"{_GRAPH}/{path}", params=p))
        body = r.json()
        if r.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            err = body.get("error", {}) if isinstance(body, dict) else {}
            raise CommentError(err.get("error_user_msg") or err.get("message") or "Meta API error")
        return body


def _norm_fb(post_id: str, c: dict) -> dict:
    frm = c.get("from") or {}
    return {"external_id": c.get("id"), "post_external_id": post_id,
            "author_name": frm.get("name"), "author_external_id": frm.get("id"),
            "message": (c.get("message") or "").strip(), "permalink": c.get("permalink_url"),
            "commented_at": _parse_dt(c.get("created_time"))}


def _norm_ig(media_id: str, c: dict) -> dict:
    return {"external_id": c.get("id"), "post_external_id": media_id,
            "author_name": c.get("username"), "author_external_id": None,
            "message": (c.get("text") or "").strip(), "permalink": None,
            "commented_at": _parse_dt(c.get("timestamp"))}


def _after(comments: list[dict], since: datetime | None) -> list[dict]:
    """Keep only comments newer than the cursor (provider `since` filtering is inconsistent across edges, so
    we filter here for correctness). Comments with no timestamp are kept (better a dup than a miss; the repo
    upsert is idempotent)."""
    if since is None:
        return comments
    return [c for c in comments if c["commented_at"] is None or c["commented_at"] > since]


async def fetch_comments(provider: str, account_id: str, token: str, since: datetime | None = None,
                         post_limit: int = 10, comment_limit: int = 50) -> list[dict]:
    """Normalized comments on the account's most recent posts/media, newer than `since`."""
    if provider == "facebook":
        posts = await _call("GET", f"{account_id}/published_posts", token, {"fields": "id", "limit": post_limit})
        out: list[dict] = []
        for p in posts.get("data", []):
            pid = p.get("id")
            if not pid:
                continue
            data = await _call("GET", f"{pid}/comments", token,
                               {"fields": "id,message,created_time,permalink_url,from", "limit": comment_limit})
            out.extend(_norm_fb(pid, c) for c in data.get("data", []) if c.get("id"))
        return _after(out, since)
    if provider == "instagram":
        media = await _call("GET", f"{account_id}/media", token, {"fields": "id", "limit": post_limit})
        out = []
        for m in media.get("data", []):
            mid = m.get("id")
            if not mid:
                continue
            data = await _call("GET", f"{mid}/comments", token,
                               {"fields": "id,text,timestamp,username", "limit": comment_limit})
            out.extend(_norm_ig(mid, c) for c in data.get("data", []) if c.get("id"))
        return _after(out, since)
    raise CommentError(f"unsupported provider {provider}")


async def post_reply(provider: str, comment_external_id: str, token: str, message: str) -> dict:
    """Post a reply to a comment. Returns {id} (provider id of our reply). FB replies are nested comments
    on the comment; IG uses the dedicated /replies edge."""
    if provider == "facebook":
        res = await _call("POST", f"{comment_external_id}/comments", token, {"message": message})
    elif provider == "instagram":
        res = await _call("POST", f"{comment_external_id}/replies", token, {"message": message})
    else:
        raise CommentError(f"unsupported provider {provider}")
    rid = res.get("id")
    if not rid:
        raise CommentError("reply posted but no id returned")
    return {"id": rid}
