import hashlib
import hmac
from urllib.parse import urlparse

from app.config import get_settings


_MIN_SECRET_LEN = 16


def _secret() -> bytes:
    """Stable HMAC secret so signed URLs in persisted messages keep working across restarts.

    FAILS CLOSED: the unauthenticated /img endpoint trusts the signed `org` to scope an RLS read,
    so a guessable or empty signing key would let an attacker forge URLs and enumerate any org's
    images. Refuse to operate without a configured, sufficiently-long IMAGE_URL_SECRET rather than
    falling back to a repo-public default (mirrors social.crypto._key). In deploy it defaults to
    NPO_OWNER_PASSWORD via compose, so this only bites a genuinely misconfigured deployment."""
    secret = get_settings().image_url_secret
    if not secret or len(secret) < _MIN_SECRET_LEN:
        raise RuntimeError(
            "IMAGE_URL_SECRET is not configured or is too short (need >=16 chars). Refusing to sign "
            "image URLs without it — the /img endpoint scopes per-org reads by the signed org, so a "
            "weak key is an org-enumeration vulnerability.")
    return secret.encode()


def sign_image(image_id: str, org_id: str) -> str:
    return hmac.new(_secret(), f"{image_id}:{org_id}".encode(), hashlib.sha256).hexdigest()


def verify_image(image_id: str, org_id: str, sig: str) -> bool:
    if not (image_id and org_id and sig):
        return False
    return hmac.compare_digest(sign_image(image_id, org_id), sig)


def image_url(image_id: str, org_id: str) -> str:
    """A self-authorizing, RLS-scoped URL the browser can load directly (no Bearer needed).
    The org is part of the signed payload, so the unauthenticated /img endpoint can trust it
    to scope the per-org read."""
    return f"/api/v1/img/{image_id}?o={org_id}&s={sign_image(image_id, org_id)}"


def _public_base() -> str:
    """Public origin (scheme://host) external services (Meta/Instagram) can reach. Derived from the
    registered OAuth redirect URI — always the public host, since Meta uses it for the OAuth flow."""
    u = urlparse(get_settings().meta_oauth_redirect or "")
    return f"{u.scheme}://{u.netloc}" if u.scheme == "https" and u.netloc else ""


def public_image_url(image_id: str, org_id: str, fmt: str | None = None) -> str:
    """Absolute signed image URL for SERVER-SIDE fetchers (Meta/Instagram) that cannot resolve the
    browser-relative image_url(). Raises if no public origin is configured — a path-only URL is
    silently unfetchable by Meta (the cause of 'media could not be fetched from this URI')."""
    base = _public_base()
    if not base:
        raise RuntimeError("no public origin configured (META_OAUTH_REDIRECT) — cannot build a "
                           "Meta-fetchable image URL")
    url = f"{base}{image_url(image_id, org_id)}"
    if fmt:
        url += f"&fmt={fmt}"
    return url
