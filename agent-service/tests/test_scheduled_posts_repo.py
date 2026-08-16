import uuid, pytest
from app.repo import scheduled_posts as sp

pytestmark = pytest.mark.asyncio


async def test_create_and_claim_is_exactly_once(db_pool):
    org = str(uuid.uuid4())
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": str(uuid.uuid4())}],
                          caption="hi", image_ids=[], content_hash="h", scheduled_at_now=True,
                          created_by=None, post_id=None)
    first = await sp.claim(org, row["id"])
    second = await sp.claim(org, row["id"])
    assert first is not None and second is None     # only one wins -> no double publish


async def test_cancel_only_pending(db_pool):
    org = str(uuid.uuid4())
    row = await sp.create(org, targets=[], caption="x", image_ids=[], content_hash="h",
                          scheduled_at_now=False, created_by=None, post_id=None,
                          scheduled_at="2999-01-01T00:00:00+00:00")
    assert await sp.cancel(org, row["id"]) is True
    assert await sp.cancel(org, row["id"]) is False


async def test_recent_duplicate_lookup(db_pool):
    org = str(uuid.uuid4())
    await sp.create(org, targets=[{"provider": "instagram", "connection_id": "c1"}],
                    caption="dup", image_ids=[], content_hash="HASH", scheduled_at_now=True,
                    created_by=None, post_id=None)
    assert await sp.exists_active_or_published(org, "HASH", "instagram") is True
    assert await sp.exists_active_or_published(org, "OTHER", "instagram") is False
    assert await sp.exists_active_or_published(org, "HASH", "facebook") is False


async def test_finish_and_get(db_pool):
    org = str(uuid.uuid4())
    row = await sp.create(org, targets=[{"provider":"facebook","connection_id":"c1"}], caption="c",
                          image_ids=[], content_hash="h", scheduled_at_now=True, created_by=None, post_id=None)
    await sp.claim(org, row["id"])
    await sp.finish(org, row["id"], "published", {"c1": {"permalink": "https://x/p", "id": "1"}})
    got = await sp.get(org, row["id"])
    assert got["status"] == "published" and got["result"]["c1"]["permalink"] == "https://x/p"


async def test_list_recent(db_pool):
    org = str(uuid.uuid4())
    await sp.create(org, targets=[], caption="a", image_ids=[], content_hash="h",
                    scheduled_at_now=True, created_by=None, post_id=None)
    items = await sp.list_recent(org)
    assert len(items) >= 1
