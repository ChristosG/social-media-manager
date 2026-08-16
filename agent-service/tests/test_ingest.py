import uuid
import pytest
from app.repo import sources as src_repo, documents as doc_repo
from app.sources import ingest, discover, extract, embed
import app.agent.research as research

pytestmark = pytest.mark.asyncio


async def test_ingest_source_end_to_end(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    sid = (await src_repo.create_source(org, "web", "S",
            {"url": "http://s/section", "type": "section", "latest_n": 2}))["id"]

    async def fake_discover(url, type_hint="auto", latest_n=15):
        return ("section", "http://s/feed", ["http://s/a1", "http://s/a2"])
    async def fake_fetch(u, max_bytes=None):
        return f"<html><article><p>{'Body about nonprofits. ' * 30}</p></article></html>"
    def fake_extract(html, url):
        return {"title": "T", "author": None, "published_at": None, "text": "Nonprofit body. " * 60}
    async def fake_embed_texts(texts, batch=16):
        return [[0.02] * 2560 for _ in texts]

    monkeypatch.setattr(ingest, "discover_source", fake_discover)
    monkeypatch.setattr(research, "fetch_html", fake_fetch)
    monkeypatch.setattr(ingest, "extract_article", fake_extract)
    monkeypatch.setattr(embed, "embed_texts", fake_embed_texts)

    summary = await ingest.ingest_source(org, sid)
    assert summary["status"] == "ok" and summary["ingested"] == 2
    assert await doc_repo.count_documents(org, sid) == 2
    s = await src_repo.get_source(org, sid)
    assert s["last_status"] == "ok" and s["detected_kind"] == "section" and s["feed_url"] == "http://s/feed"


async def test_ingest_marks_failed_when_no_articles(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    sid = (await src_repo.create_source(org, "web", "S", {"url": "http://s", "type": "section"}))["id"]
    async def empty_discover(url, type_hint="auto", latest_n=15):
        return ("section", None, [])
    monkeypatch.setattr(ingest, "discover_source", empty_discover)
    summary = await ingest.ingest_source(org, sid)
    assert summary["status"] == "failed"
    assert (await src_repo.get_source(org, sid))["last_status"] == "failed"
