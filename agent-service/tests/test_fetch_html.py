import pytest
from app.agent import research

pytestmark = pytest.mark.asyncio


async def test_fetch_url_strips_what_fetch_html_returns(monkeypatch):
    async def fake_html(url, max_bytes=None):
        return "<nav>menu</nav><article><p>Body text here.</p></article>"
    monkeypatch.setattr(research, "fetch_html", fake_html)
    out = await research.fetch_url("http://x")
    assert "Body text here." in out
    assert "<" not in out and ">" not in out
