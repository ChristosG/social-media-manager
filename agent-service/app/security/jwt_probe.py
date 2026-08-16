"""Defense-in-depth JWT verification of the gateway-forwarded Ed25519 token.

agent-service is reached only through the gateway, which validates the Ed25519 access token and injects
X-User-Id / X-Tenant-Id. Trusting those headers alone makes tenant isolation depend on network reachability,
so we ALSO verify the forwarded token here and derive trust from VERIFIED claims. The flip from the original
log-only soak to enforcement is controlled by JWT_ENFORCE (default on, reversible).

This module exposes the check as pure, reusable functions so both the HTTP middleware AND the WebSocket
handler (BaseHTTPMiddleware does NOT intercept WS upgrades) enforce identically:
  * ``enforced()``        — is enforcement active AND a public key configured to verify against?
  * ``check_identity()``  — list of problems comparing a forwarded token to the identity headers ([] = clean).
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import get_settings
from app.security.jwt import JWTValidator

logger = logging.getLogger("jwt_probe")

# Probes are pointless on infra endpoints that carry no identity.
_SKIP = {"/health", "/livez", "/readyz", "/metrics"}

_UNSET = object()
_validator_cache: object | JWTValidator | None = _UNSET


def _get_validator() -> JWTValidator | None:
    """Lazily build (and cache) the Ed25519 validator from JWT_PUBLIC_KEY. None when no key is configured."""
    global _validator_cache
    if _validator_cache is _UNSET:
        pub = get_settings().jwt_public_key
        _validator_cache = JWTValidator(pub) if pub else None
    return _validator_cache  # type: ignore[return-value]


def enforced() -> bool:
    """True when enforcement is on AND a key is configured. With no key we cannot verify, so we never block."""
    return bool(get_settings().jwt_enforce) and _get_validator() is not None


def evaluate_identity(validator: JWTValidator, token: str | None,
                      hdr_user: str | None, hdr_tenant: str | None) -> list[str]:
    """Pure check (testable): return a list of problems comparing a forwarded token to the gateway's
    identity headers. Empty list = clean. 'missing-token' only when the request looks authenticated
    (carries a user header) but no token came through."""
    if not token:
        return ["missing-token"] if hdr_user else []
    try:
        claims = validator.validate(token)
    except ValueError as e:
        return [f"invalid-token: {e}"]
    problems: list[str] = []
    if hdr_user and claims.sub != hdr_user:
        problems.append(f"sub({claims.sub})!=X-User-Id({hdr_user})")
    if hdr_tenant and claims.tid and claims.tid != hdr_tenant:
        problems.append(f"tid({claims.tid})!=X-Tenant-Id({hdr_tenant})")
    return problems


def check_identity(token: str | None, hdr_user: str | None, hdr_tenant: str | None) -> list[str]:
    """Module-level convenience over evaluate_identity using the cached validator. Returns [] (clean) when
    no validator is configured — callers should gate on enforced() before treating problems as fatal."""
    v = _get_validator()
    if v is None:
        return []
    return evaluate_identity(v, token, hdr_user, hdr_tenant)


def _extract_token(authorization: str | None, x_auth_token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return (x_auth_token or "").strip() or None


class JwtProbeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._seen_missing: set[str] = set()   # dedup the 'missing-token' log per path (log-only mode)

    async def dispatch(self, request, call_next):
        if _get_validator() is not None and request.url.path not in _SKIP:
            try:
                token = _extract_token(request.headers.get("authorization"),
                                       request.headers.get("x-auth-token"))
                hdr_user = request.headers.get("x-user-id")
                problems = check_identity(token, hdr_user, request.headers.get("x-tenant-id"))
                if problems:
                    if enforced():
                        # The identity headers aren't backed by a valid, matching token → not from the
                        # gateway (or tampered). Reject before any tenant data is touched.
                        logger.warning("jwt-enforce: REJECTED %s — %s", request.url.path, ", ".join(problems))
                        return JSONResponse({"detail": "unauthorized"}, status_code=401)
                    self._log_only(request.url.path, problems)
            except Exception:
                # Never let the auth check itself 500 a request; fail closed only on a definite problem above.
                logger.exception("jwt-probe: unexpected error (ignored)")
        return await call_next(request)

    def _log_only(self, path: str, problems: list[str]) -> None:
        for p in problems:
            if p == "missing-token":
                if path not in self._seen_missing:
                    self._seen_missing.add(path)
                    logger.warning("jwt-probe: identity headers but NO forwarded token on %s", path)
            else:
                logger.warning("jwt-probe: %s on %s", p, path)
