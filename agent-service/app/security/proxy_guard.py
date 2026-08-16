"""Network ACL: only the trusted reverse proxies may reach agent-service.

agent-service is not host-exposed — it is reached only by the gateway (authenticated /api + /ws) and by
nginx (the unauthenticated-by-design signed routes: /img HMAC URLs, /social/callback signed-state). Both
inject a shared secret as X-Proxy-Secret. When AGENT_PROXY_SECRET is configured, this middleware rejects
(403) any HTTP request that doesn't carry the matching secret — so a compromised peer container on the
network cannot reach us even though every route already has its own crypto check. Belt-and-suspenders.

Empty secret => disabled (no behavior change). Infra endpoints are always exempt so the orchestrator's
healthcheck (which hits /readyz from inside the container, without the header) stays green.

WebSocket upgrades are NOT seen by BaseHTTPMiddleware, so /ws/chat enforces the same secret inline.
"""
import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import get_settings

logger = logging.getLogger("proxy_guard")

# Same infra exemptions as the JWT probe: these carry no identity and are hit locally by the healthcheck.
_SKIP = {"/health", "/livez", "/readyz", "/metrics"}

_PROXY_SECRET_HEADER = "x-proxy-secret"


def proxy_secret() -> str:
    return get_settings().agent_proxy_secret or ""


def proxy_secret_ok(presented: str | None) -> bool:
    """True when the network ACL is satisfied: disabled, or the presented secret matches (constant-time)."""
    secret = proxy_secret()
    if not secret:
        return True
    return bool(presented) and hmac.compare_digest(presented, secret)


class ProxyGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if proxy_secret() and request.url.path not in _SKIP:
            if not proxy_secret_ok(request.headers.get(_PROXY_SECRET_HEADER)):
                logger.warning("proxy-guard: REJECTED %s — missing/invalid X-Proxy-Secret", request.url.path)
                return JSONResponse({"detail": "forbidden"}, status_code=403)
        return await call_next(request)
