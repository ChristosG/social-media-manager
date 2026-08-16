import uuid
import pytest
from app.repo import sources as src_repo, documents as doc_repo
from app.sources import retrieve, embed

pytestmark = pytest.mark.asyncio


async def test_search_returns_cited_hits_above_floor(db_pool, monkeypatch):
    async def fake_embed_query(q):
        return [0.10] * 2560
    monkeypatch.setattr(embed, "embed_query", fake_embed_query)

    org = str(uuid.uuid4())
    sid = (await src_repo.create_source(org, "web", "S", {"url": "http://s"}))["id"]
    near, _ = await doc_repo.upsert_document(org, sid, "http://s/near", "Near", None, None, "h1", 10)
    await doc_repo.replace_chunks(org, near, [(0, "relevant passage", [0.10] * 2560)])
    far, _ = await doc_repo.upsert_document(org, sid, "http://s/far", "Far", None, None, "h2", 10)
    await doc_repo.replace_chunks(org, far, [(0, "unrelated", [-0.10] * 2560)])

    hits = await retrieve.search(org, "anything", k=5, floor=0.5)
    assert [h["url"] for h in hits] == ["http://s/near"]
    block = retrieve.format_sources_block(hits)
    assert "UNTRUSTED" in block and "http://s/near" in block and "relevant passage" in block


def test_is_junk_own_post_unit():
    j = retrieve._is_junk_own_post
    assert j({"kind": "instagram", "text": "Test post from Social Studio 🐾 (automated publish test — safe to delete)"})
    assert j({"kind": "facebook", "text": "hi"})                       # too short
    assert not j({"kind": "instagram", "text": "x" * 200})             # substantial own post
    assert not j({"kind": "web", "text": "short"})                     # length rule is own-posts only


async def test_search_drops_junk_own_posts(db_pool, monkeypatch):
    async def fake_embed_query(q):
        return [0.10] * 2560
    monkeypatch.setattr(embed, "embed_query", fake_embed_query)

    org = str(uuid.uuid4())
    sid = (await src_repo.create_source(org, "instagram", "IG", {"url": "http://ig"}))["id"]
    junk, _ = await doc_repo.upsert_document(org, sid, "http://ig/test", "Test", None, None, "h1", 10)
    await doc_repo.replace_chunks(org, junk, [(0, "Test post from Social Studio 🐾 (safe to delete)", [0.10] * 2560)])
    good, _ = await doc_repo.upsert_document(org, sid, "http://ig/real", "Real", None, None, "h2", 300)
    await doc_repo.replace_chunks(org, good, [(0, "A heartfelt story about the volunteers who rebuilt the shelter " * 3, [0.10] * 2560)])

    hits = await retrieve.search(org, "anything", k=5, floor=0.5)
    urls = [h["url"] for h in hits]
    assert "http://ig/real" in urls and "http://ig/test" not in urls   # junk test post excluded


async def test_empty_when_nothing_clears_floor(db_pool, monkeypatch):
    monkeypatch.setattr(embed, "embed_query", lambda q: _coro([0.10] * 2560))
    org = str(uuid.uuid4())
    assert await retrieve.search(org, "q", k=5, floor=0.99) == []
    assert retrieve.format_sources_block([]) == ""


def _coro(v):
    async def _c():
        return v
    return _c()
