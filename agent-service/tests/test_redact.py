"""F3 regression: a Meta Graph error must never carry the OAuth access token into logs/DB.

httpx's HTTPStatusError embeds the full request URL — including ?access_token=… — in its message,
which previously flowed verbatim into logger.exception() and into sources.last_error (str(e)[:300]).
"""
import httpx
import pytest

from app.security.redact import redact_secrets
from app.social import graph

_TOKEN = "EAABxLiveLooKingPageToken0123456789abcdefGHIJKLmnopQRSTuvwx"


def test_redact_scrubs_query_form():
    s = f"GET https://graph.facebook.com/v21.0/page/posts?limit=15&access_token={_TOKEN}&appsecret_proof=deadbeef"
    out = redact_secrets(s)
    assert _TOKEN not in out
    assert "deadbeef" not in out
    assert "access_token=<redacted>" in out
    assert "appsecret_proof=<redacted>" in out
    # non-secret context is preserved
    assert "graph.facebook.com" in out and "limit=15" in out


def test_redact_scrubs_json_form():
    s = f'{{"access_token": "{_TOKEN}", "client_secret": "sk_live_abc123", "name": "Acme"}}'
    out = redact_secrets(s)
    assert _TOKEN not in out and "sk_live_abc123" not in out
    assert "Acme" in out  # benign fields kept


def test_redact_noop_on_clean_text():
    s = "Graph API error 404 for /page/published_posts"
    assert redact_secrets(s) == s


@pytest.mark.asyncio
async def test_graph_error_does_not_leak_token(monkeypatch):
    """A 4xx from the Graph API must raise an error that contains neither the token nor access_token=…"""
    monkeypatch.setattr(
        graph, "_transport",
        httpx.MockTransport(lambda req: httpx.Response(401, json={"error": {"message": "expired"}})),
    )
    with pytest.raises(Exception) as ei:
        await graph.fetch_facebook_posts(_TOKEN, "page-1", limit=10)
    msg = str(ei.value)
    assert _TOKEN not in msg
    assert "access_token=" not in msg
