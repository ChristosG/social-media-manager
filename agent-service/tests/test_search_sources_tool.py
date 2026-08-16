import uuid
import pytest
from app.security.context import set_identity
from app.repo import sources as src_repo, documents as doc_repo
from app.sources import embed, retrieve
import app.agent.tools as tools

pytestmark = pytest.mark.asyncio


async def test_search_sources_tool_returns_cited(db_pool, monkeypatch):
    async def fake_embed_query(q): return [0.10] * 2560
    monkeypatch.setattr(embed, "embed_query", fake_embed_query)
    org = str(uuid.uuid4()); set_identity("u", org)
    sid = (await src_repo.create_source(org, "web", "S", {"url": "http://s"}))["id"]
    did, _ = await doc_repo.upsert_document(org, sid, "http://s/x", "Tax news", None, None, "h", 10)
    await doc_repo.replace_chunks(org, did, [(0, "VAT cut for charities", [0.10] * 2560)])

    out = await tools.search_sources.ainvoke({"query": "tax"})
    assert "http://s/x" in out and "VAT cut for charities" in out


async def test_search_sources_tool_handles_empty(db_pool, monkeypatch):
    async def fake_embed_query(q): return [0.10] * 2560
    monkeypatch.setattr(embed, "embed_query", fake_embed_query)
    org = str(uuid.uuid4()); set_identity("u", org)
    out = await tools.search_sources.ainvoke({"query": "nothing here"})
    assert "no" in out.lower() and "source" in out.lower()


async def test_search_resilient_when_embed_fails(db_pool, monkeypatch):
    async def boom(q): raise RuntimeError("emb down")
    monkeypatch.setattr(embed, "embed_query", boom)
    assert await retrieve.search(str(uuid.uuid4()), "q") == []
