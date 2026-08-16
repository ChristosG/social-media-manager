import uuid
import pytest
from app.repo import sources as src_repo, documents as doc_repo
from app.sources import embed
from app.api import ws

pytestmark = pytest.mark.asyncio


async def test_grounding_prefix_built_when_org_has_relevant_sources(db_pool, monkeypatch):
    async def fake_embed_query(q): return [0.10] * 2560
    monkeypatch.setattr(embed, "embed_query", fake_embed_query)
    org = str(uuid.uuid4())
    sid = (await src_repo.create_source(org, "web", "S", {"url": "http://s"}))["id"]
    did, _ = await doc_repo.upsert_document(org, sid, "http://s/x", "News", None, None, "h", 10)
    await doc_repo.replace_chunks(org, did, [(0, "grounded fact about adoptions", [0.10] * 2560)])

    prefix = await ws._grounding_prefix(org, "tell me about adoptions", ground=True)
    assert "grounded fact about adoptions" in prefix and "http://s/x" in prefix
    assert await ws._grounding_prefix(org, "tell me about adoptions", ground=False) == ""


async def test_default_on_only_when_org_has_sources(db_pool):
    empty = str(uuid.uuid4())
    assert await ws._should_ground(empty, flag=None) is False
    org = str(uuid.uuid4())
    await src_repo.create_source(org, "web", "S", {"url": "http://s"})
    assert await ws._should_ground(org, flag=None) is True
    assert await ws._should_ground(org, flag=False) is False
