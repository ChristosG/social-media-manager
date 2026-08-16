"""Scrub credentials out of strings before they reach logs or the database.

The Meta Graph client passes the Page access token as a query parameter; httpx then embeds the full
request URL (token and all) in the HTTPStatusError it raises on a 4xx/5xx. That message used to flow
verbatim into logger.exception() and into the sources.last_error column. redact_secrets() neutralises
the common credential shapes (query `k=v` and JSON `"k": "v"`) so an error string is safe to persist.
"""
import re

# Keys whose values must never survive into a log line or a DB column.
_SECRET_KEYS = ("access_token", "appsecret_proof", "client_secret", "refresh_token", "password", "api_key")

# `access_token=...` up to the next & or whitespace (query-string form).
_QUERY = [re.compile(rf"({re.escape(k)}=)[^&\s\"']+", re.IGNORECASE) for k in _SECRET_KEYS]
# `"access_token": "..."` (JSON-ish form).
_JSON = [re.compile(rf'(["\']?{re.escape(k)}["\']?\s*:\s*["\'])[^"\']+', re.IGNORECASE) for k in _SECRET_KEYS]


def redact_secrets(s: str) -> str:
    """Replace credential values in `s` with <redacted>, leaving surrounding context intact."""
    if not s:
        return s
    out = s
    for pat in _QUERY:
        out = pat.sub(r"\1<redacted>", out)
    for pat in _JSON:
        out = pat.sub(r"\1<redacted>", out)
    return out
