import uuid
import pytest
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.agent import research
from app.config import get_settings
from app.repo import profile as profile_repo


async def test_web_search_no_key_returns_empty(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "")
    assert await research.web_search("anything") == []


def _json_model(text):
    class F(GenericFakeChatModel):
        async def ainvoke(self, *a, **k):
            return AIMessage(content=text)
    return F(messages=iter([AIMessage(content=text)]))


@pytest.mark.usefixtures("db_pool")
async def test_research_org_populates_profile_and_programs(db_pool, monkeypatch):
    org = str(uuid.uuid4())

    async def fake_fetch(url, max_chars=8000):
        return "We rescue and rehome abandoned dogs and cats across Texas."

    async def fake_search(q, max_results=5, include_domains=None):
        return []

    monkeypatch.setattr(research, "fetch_url", fake_fetch)
    monkeypatch.setattr(research, "web_search", fake_search)
    model = _json_model(
        '{"mission":"Rescue and rehome animals","one_liner":"Saving paws","audience":"Local adopters",'
        '"regions":["Texas"],"programs":[{"name":"Foster-to-Adopt","description":"Temporary fosters become homes."}]}')
    out = await research.research_org(org, "Paws Rescue", "https://paws.example", model=model)
    assert out is not None and out["mission"] == "Rescue and rehome animals"
    prof = await profile_repo.get_profile(org)
    assert prof and prof["mission"] == "Rescue and rehome animals" and prof["regions"] == ["Texas"]
    progs = await profile_repo.list_programs(org)
    assert any(p["name"] == "Foster-to-Adopt" for p in progs)


async def test_research_org_none_when_no_sources(monkeypatch):
    async def fake_fetch(url, max_chars=8000):
        return ""

    async def fake_search(q, max_results=5, include_domains=None):
        return []

    monkeypatch.setattr(research, "fetch_url", fake_fetch)
    monkeypatch.setattr(research, "web_search", fake_search)
    assert await research.research_org("o", "x", "", model=_json_model("{}")) is None


def test_safe_target_blocks_internal_and_metadata():
    """SSRF guard: fetch_url must refuse internal / metadata / non-http targets (literal IPs need no DNS)."""
    from app.agent.research import _safe_target
    assert _safe_target("http://169.254.169.254/latest/meta-data/") is None  # cloud metadata
    assert _safe_target("http://127.0.0.1:6888/") is None                    # loopback
    assert _safe_target("http://10.1.2.3/") is None                          # RFC-1918 private
    assert _safe_target("http://[::1]/") is None                             # IPv6 loopback
    assert _safe_target("ftp://example.com/") is None                        # non-http scheme


async def test_web_search_includes_domains_in_payload(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"results": []}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            captured.update(json or {})
            return FakeResp()

    monkeypatch.setattr(research.httpx, "AsyncClient", FakeClient)
    await research.web_search("q", include_domains=["paws.example"])
    assert captured.get("include_domains") == ["paws.example"]
    get_settings.cache_clear()


@pytest.mark.usefixtures("db_pool")
async def test_research_with_url_enriches_domain_restricted(db_pool, monkeypatch):
    calls = {}

    async def fake_fetch(url, max_chars=8000):
        return "We rescue and rehome dogs across Austin."

    async def fake_search(q, max_results=5, include_domains=None):
        calls["include_domains"] = include_domains
        return []

    monkeypatch.setattr(research, "fetch_url", fake_fetch)
    monkeypatch.setattr(research, "web_search", fake_search)
    out = await research.research_org(
        str(uuid.uuid4()), "Paws", "https://www.paws.example/about",
        model=_json_model('{"mission":"Rescue dogs","one_liner":"","audience":"","regions":[],"programs":[]}'))
    assert out is not None
    assert calls["include_domains"] == ["paws.example"]  # www stripped, domain-restricted


@pytest.mark.usefixtures("db_pool")
async def test_research_no_url_falls_back_to_broad_search(db_pool, monkeypatch):
    calls = {}

    async def fake_fetch(url, max_chars=8000):
        return ""

    async def fake_search(q, max_results=5, include_domains=None):
        calls["include_domains"] = include_domains
        return [{"title": "t", "url": "https://x.example", "content": "Some org info."}]

    monkeypatch.setattr(research, "fetch_url", fake_fetch)
    monkeypatch.setattr(research, "web_search", fake_search)
    out = await research.research_org(
        str(uuid.uuid4()), "Paws", "",
        model=_json_model('{"mission":"m","one_liner":"","audience":"","regions":[],"programs":[]}'))
    assert out is not None
    assert calls["include_domains"] is None  # broad fallback when no URL
