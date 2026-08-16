import uuid
import pytest
from app.repo import sources as src_repo, documents as doc_repo
from app.sources import store, embed

pytestmark = pytest.mark.asyncio


async def test_persist_article_chunks_and_embeds(db_pool, monkeypatch):
    async def fake_embed_texts(texts, batch=16):
        return [[0.01] * 2560 for _ in texts]
    monkeypatch.setattr(embed, "embed_texts", fake_embed_texts)

    org = str(uuid.uuid4())
    sid = (await src_repo.create_source(org, "web", "S", {"url": "http://s"}))["id"]
    art = {"url": "http://s/a", "title": "T", "author": None, "published_at": None,
           "text": "Para one is here.\n\n" + ("Long body. " * 200)}
    changed = await store.persist_article(org, sid, art)
    assert changed is True
    assert await doc_repo.count_documents(org, sid) == 1
    assert await store.persist_article(org, sid, art) is False
