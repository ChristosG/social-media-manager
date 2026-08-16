import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode
import httpx
from app.config import get_settings

_GRAPH = "https://graph.facebook.com/v21.0"
_DIALOG = "https://www.facebook.com/v21.0/dialog/oauth"
# Read-only + comment engagement (read/reply); never publish. FB Login *for Business* drives perms from a
# dashboard Configuration (config_id) and IGNORES this string — there the operator adds these scopes to the
# config; this list only applies to the classic Facebook Login (no config_id) path.
_SCOPES = ("pages_show_list,pages_read_engagement,pages_manage_engagement,read_insights,"
           "instagram_basic,instagram_manage_comments,instagram_manage_insights")
_STATE_TTL = 600
_transport: httpx.MockTransport | None = None


def _state_secret() -> bytes:
    s = get_settings()
    secret = s.meta_app_secret or s.image_url_secret
    if not secret:
        # Fail closed: a hardcoded fallback would let anyone forge a signed OAuth state (CSRF).
        raise RuntimeError("META_APP_SECRET or IMAGE_URL_SECRET must be configured to sign OAuth state.")
    return secret.encode()


# Domain-separate the HMAC so that even when this falls back to image_url_secret (shared with signed
# image URLs), an image signature can never be replayed as a valid OAuth state, and vice versa.
_STATE_DOMAIN = b"oauth_state:v1:"


def _state_sig(body: str) -> str:
    return hmac.new(_state_secret(), _STATE_DOMAIN + body.encode(), hashlib.sha256).hexdigest()


def sign_state(org_id: str, user_id: str, popup: bool = False) -> str:
    payload = {"o": org_id, "u": user_id, "n": base64.urlsafe_b64encode(os.urandom(9)).decode(),
               "e": int(time.time()) + _STATE_TTL}
    if popup:
        payload["p"] = 1
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{body}.{_state_sig(body)}"


def verify_state(state: str, user_id: str | None) -> dict | None:
    try:
        body, sig = state.split(".", 1)
        if not hmac.compare_digest(sig, _state_sig(body)):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
        if int(payload["e"]) < int(time.time()):
            return None
        if user_id is not None and payload.get("u") != user_id:
            return None
        return payload
    except Exception:
        return None


def state_nonce(state: str) -> str | None:
    """The per-flow nonce embedded in a (valid) state — set as a session cookie to bind connect→callback."""
    p = verify_state(state, None)
    return p.get("n") if p else None


def authorize_url(provider: str, state: str) -> str:
    s = get_settings()
    params = {"client_id": s.meta_app_id, "redirect_uri": s.meta_oauth_redirect,
              "state": state, "response_type": "code"}
    # FB Login *for Business* drives permissions from a dashboard Configuration (config_id)
    # and ignores `scope`; classic Facebook Login takes raw `scope`. Support both.
    config_id = getattr(s, "meta_login_config_id", "")
    if config_id:
        params["config_id"] = config_id
    else:
        params["scope"] = _SCOPES
    return _DIALOG + "?" + urlencode(params)


async def _get(path: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=30, transport=_transport) as c:
        r = await c.get(f"{_GRAPH}/{path}", params=params)
        r.raise_for_status()
        return r.json()


async def exchange_code(code: str) -> str:
    s = get_settings()
    short = await _get("oauth/access_token", {"client_id": s.meta_app_id, "client_secret": s.meta_app_secret,
                                              "redirect_uri": s.meta_oauth_redirect, "code": code})
    longt = await _get("oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": s.meta_app_id,
                                              "client_secret": s.meta_app_secret,
                                              "fb_exchange_token": short["access_token"]})
    return longt["access_token"]


async def granted_scopes(token: str) -> str:
    """Comma-joined permissions actually granted for this token (config_id flows vary)."""
    data = await _get("me/permissions", {"access_token": token})
    return ",".join(p["permission"] for p in data.get("data", []) if p.get("status") == "granted")


async def list_pages(user_token: str) -> list[dict]:
    data = await _get("me/accounts", {"access_token": user_token,
                                      "fields": "id,name,access_token,instagram_business_account{id,username}"})
    return data.get("data", [])
