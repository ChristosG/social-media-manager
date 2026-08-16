import hashlib
import hmac
from datetime import datetime, timezone
import httpx
from app.config import get_settings

_GRAPH = "https://graph.facebook.com/v21.0"
_transport: httpx.MockTransport | None = None   # test hook; None → real network


class GraphError(Exception):
    """A Graph API call failed. Carries a token-free message (see _get) so it is safe to log/persist."""


def _appsecret_proof(token: str) -> str:
    return hmac.new(get_settings().meta_app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("+0000", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


async def _get(path: str, token: str, params: dict) -> dict:
    q = {**params, "access_token": token, "appsecret_proof": _appsecret_proof(token)}
    async with httpx.AsyncClient(timeout=30, transport=_transport) as c:
        r = await c.get(f"{_GRAPH}/{path}", params=q)
        if r.status_code >= 400:
            # Never call raise_for_status(): httpx embeds the full request URL — including
            # ?access_token=<page token> — in the exception, which previously leaked the token into
            # logger.exception() and the sources.last_error column (audit F3). Raise a token-free error.
            raise GraphError(f"Graph API error {r.status_code} for /{path}")
        return r.json()


async def fetch_facebook_posts(token: str, page_id: str, limit: int = 15) -> list[dict]:
    data = await _get(f"{page_id}/published_posts", token,
                      {"fields": "message,created_time,permalink_url,full_picture", "limit": limit})
    out = []
    for p in data.get("data", []):
        msg = (p.get("message") or "").strip()
        if not msg:
            continue
        out.append({"url": p.get("permalink_url") or f"https://facebook.com/{p.get('id', '')}",
                    "title": msg[:80], "text": msg, "published_at": _parse_dt(p.get("created_time")),
                    "image_url": p.get("full_picture")})
    return out[:limit]


async def fetch_instagram_posts(token: str, ig_user_id: str, limit: int = 15) -> list[dict]:
    data = await _get(f"{ig_user_id}/media", token,
                      {"fields": "caption,timestamp,permalink,media_url,thumbnail_url,media_type",
                       "limit": limit})
    out = []
    for p in data.get("data", []):
        cap = (p.get("caption") or "").strip()
        if not cap:
            continue
        out.append({"url": p.get("permalink") or f"https://instagram.com/p/{p.get('id', '')}",
                    "title": cap[:80], "text": cap, "published_at": _parse_dt(p.get("timestamp")),
                    "image_url": p.get("thumbnail_url") or p.get("media_url")})
    return out[:limit]
