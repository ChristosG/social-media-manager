import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.repo import sources as src_repo, documents as repo

pytestmark = pytest.mark.asyncio


def _vec(x: float):
    return [x] * 2560


async def _mk_source(org):
    return (await src_repo.create_source(org, "web", "S", {"url": "http://s"}))["id"]


async def test_upsert_dedup_and_replace_chunks(db_pool):
    org = str(uuid.uuid4()); sid = await _mk_source(org)
    did, changed = await repo.upsert_document(org, sid, "http://a", "Title", "Auth", None, "hash1", 100)
    assert changed is True
    _, changed2 = await repo.upsert_document(org, sid, "http://a", "Title", "Auth", None, "hash1", 100)
    assert changed2 is False
    _, changed3 = await repo.upsert_document(org, sid, "http://a", "Title2", "Auth", None, "hash2", 120)
    assert changed3 is True
    await repo.replace_chunks(org, did, [(0, "first", _vec(0.02)), (1, "second", _vec(0.03))])
    assert await repo.count_chunks(org, did) == 2
    await repo.replace_chunks(org, did, [(0, "only", _vec(0.04))])
    assert await repo.count_chunks(org, did) == 1


async def test_cosine_search_orders_by_similarity_and_is_rls_scoped(db_pool):
    org = str(uuid.uuid4()); sid = await _mk_source(org)
    near, _ = await repo.upsert_document(org, sid, "http://near", "Near", None, None, "h1", 10)
    far, _ = await repo.upsert_document(org, sid, "http://far", "Far", None, None, "h2", 10)
    await repo.replace_chunks(org, near, [(0, "near text", _vec(0.10))])
    await repo.replace_chunks(org, far,  [(0, "far text",  _vec(-0.10))])
    hits = await repo.search_chunks(org, _vec(0.10), k=5)
    assert hits and hits[0]["url"] == "http://near" and hits[0]["score"] >= hits[-1]["score"]
    assert await repo.search_chunks(str(uuid.uuid4()), _vec(0.10), k=5) == []


async def test_source_stats_counts_docs_and_chunks(db_pool):
    org = str(uuid.uuid4()); sid = await _mk_source(org)
    d1, _ = await repo.upsert_document(org, sid, "http://a", "A", None, None, "h1", 10)
    d2, _ = await repo.upsert_document(org, sid, "http://b", "B", None, None, "h2", 10)
    await repo.replace_chunks(org, d1, [(0, "x", _vec(0.1)), (1, "y", _vec(0.2))])
    await repo.replace_chunks(org, d2, [(0, "z", _vec(0.3))])
    stats = await repo.source_stats(org)
    assert stats[sid] == {"documents": 2, "chunks": 3}
    assert await repo.source_stats(str(uuid.uuid4())) == {}   # RLS-scoped


async def test_reconcile_removes_deleted_within_window_keeps_older(db_pool):
    """A post deleted on the platform (absent from the latest fetch) is removed, but only within the
    refreshed window — an older un-refetched post is never wrongly pruned."""
    org = str(uuid.uuid4()); sid = await _mk_source(org)
    now = datetime.now(timezone.utc)
    d_old = now - timedelta(days=30)   # older than the window — must survive
    d_a = now - timedelta(days=2)
    d_b = now - timedelta(days=1)      # this one gets "deleted" on the platform
    await repo.upsert_document(org, sid, "http://old", "Old", None, d_old, "h0", 10)
    await repo.upsert_document(org, sid, "http://a", "A", None, d_a, "h1", 10)
    await repo.upsert_document(org, sid, "http://b", "B", None, d_b, "h2", 10)
    # Latest fetch returned only A (B was deleted); window starts at the oldest fetched (A).
    removed = await repo.reconcile_to_urls(org, sid, ["http://a"], d_a)
    assert removed == 1
    urls = {d["url"] for d in await repo.list_documents(org, sid)}
    assert urls == {"http://old", "http://a"}   # deleted B gone, old (pre-window) kept


async def test_prune_keeps_newest(db_pool):
    org = str(uuid.uuid4()); sid = await _mk_source(org)
    for n in range(5):
        await repo.upsert_document(org, sid, f"http://{n}", f"T{n}", None, None, f"h{n}", 10)
    removed = await repo.prune_documents(org, sid, keep=2)
    assert removed == 3
    assert await repo.count_documents(org, sid) == 2
