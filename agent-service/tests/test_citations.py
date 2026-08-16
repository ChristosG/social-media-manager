import json
import uuid
import pytest
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.security.context import set_identity, sources_sink_var
from app.repo import conversations as conv_repo, ledger as ledger_repo
from app.sources import retrieve
import app.agent.tools as tools


def _fake(text):
    class F(GenericFakeChatModel):
        async def ainvoke(self, *a, **k): return AIMessage(content=text)
    return F(messages=iter([AIMessage(content=text)]))


def test_to_citations_dedups_and_types():
    hits = [
        {"title": "Cleanup recap", "url": "https://acme.org/a", "text": "we cleaned the beach", "kind": "facebook"},
        {"title": "Dup", "url": "https://acme.org/a", "text": "again", "kind": "facebook"},   # dropped (same url)
        {"title": "News", "url": "https://news.test/x", "text": "flooding in texas", "kind": "web"},
    ]
    cites = retrieve.to_citations(hits)
    assert [c["url"] for c in cites] == ["https://acme.org/a", "https://news.test/x"]
    assert cites[0]["kind"] == "facebook" and cites[1]["kind"] == "web"


@pytest.mark.usefixtures("db_pool")
async def test_message_sources_round_trip():
    org = str(uuid.uuid4()); set_identity("u", org)
    conv = await conv_repo.create_conversation(org, str(uuid.uuid4()), "t")
    cites = [{"title": "Src", "url": "https://x.test/1", "kind": "web", "snippet": "hi"}]
    await conv_repo.add_message(org, conv["id"], "assistant", "grounded reply", sources=cites)
    msgs = await conv_repo.get_messages(org, conv["id"])
    assert msgs[0]["sources"] == cites
    # A message with no sources defaults to [] (not null).
    await conv_repo.add_message(org, conv["id"], "user", "hello")
    assert (await conv_repo.get_messages(org, conv["id"]))[-1]["sources"] == []


@pytest.mark.usefixtures("db_pool")
async def test_search_sources_pushes_citations(monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org)
    sink: list = []; sources_sink_var.set(sink)
    hits = [{"title": "Our post", "url": "https://acme.org/p", "text": "volunteer day", "kind": "instagram", "score": 0.9}]
    async def fake_search(*a, **k): return hits
    monkeypatch.setattr(retrieve, "search", fake_search)
    await tools.search_sources.ainvoke({"query": "volunteers"})
    assert sink and sink[0]["url"] == "https://acme.org/p" and sink[0]["kind"] == "instagram"


@pytest.mark.usefixtures("db_pool")
async def test_suggest_posts_persists_sources_on_ledger(monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org)
    sink: list = []; sources_sink_var.set(sink)
    async def fake_web(*a, **k): return [{"title": "Flood news", "url": "https://news.test/flood", "content": "texas"}]
    async def fake_search(*a, **k):
        return [{"title": "Past post", "url": "https://acme.org/old", "text": "we helped", "kind": "facebook", "score": 0.8}]
    monkeypatch.setattr(tools, "web_search", fake_web)
    monkeypatch.setattr(retrieve, "search", fake_search)
    tools._model = _fake(json.dumps([{"title": "Texas flood relief", "angle": "mobilize donors"}]))
    # A "current/trend" cue in the brief authorizes the automatic web search (otherwise we ground only on
    # the org's own ingested material — no surprise Tavily calls when the web-search toggle is off).
    await tools.suggest_posts.ainvoke({"count": 1, "brief": "latest texas flooding right now"})
    post = next(p for p in await ledger_repo.list_posts(org) if p["title"] == "Texas flood relief")
    urls = {s["url"] for s in post["sources"]}
    assert "https://acme.org/old" in urls and "https://news.test/flood" in urls
    assert {s["url"] for s in sink} == urls   # also streamed as chips


@pytest.mark.usefixtures("db_pool")
async def test_suggest_posts_no_web_search_without_trend_cue(monkeypatch):
    """A plain brief ("based on my programs") grounds on OWN material only — no automatic web search."""
    org = str(uuid.uuid4()); set_identity("u", org)
    sink: list = []; sources_sink_var.set(sink)
    called = {"web": False}
    async def fake_web(*a, **k):
        called["web"] = True
        return [{"title": "Flood news", "url": "https://news.test/flood", "content": "texas"}]
    async def fake_search(*a, **k):
        return [{"title": "Past post", "url": "https://acme.org/old", "text": "we helped", "kind": "facebook", "score": 0.8}]
    monkeypatch.setattr(tools, "web_search", fake_web)
    monkeypatch.setattr(retrieve, "search", fake_search)
    tools._model = _fake(json.dumps([{"title": "Programs recap", "angle": "celebrate impact"}]))
    await tools.suggest_posts.ainvoke({"count": 1, "brief": "a post based on my programs"})
    assert called["web"] is False
    assert {s["url"] for s in sink} == {"https://acme.org/old"}
