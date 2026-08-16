import uuid
import asyncpg
import pytest
from datetime import datetime, timezone
from app.repo import ledger as led
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


def test_idea_slug_normalizes():
    assert led.idea_slug("Clean Water, Safe Future!") == "clean-water-safe-future"
    assert led.idea_slug("  A  B  ") == "a-b"
    assert led.idea_slug("***") == "idea"
    assert led.idea_slug("") == "idea"


async def test_create_post_dedup_returns_existing_live_row():
    org = str(uuid.uuid4()); set_identity("u", org)
    a = await led.create_post(org, "Volunteer Spotlight", "x", "suggested", dedup=True)
    b = await led.create_post(org, "volunteer   spotlight!", "y", "suggested", dedup=True)
    assert a["id"] == b["id"]                       # same idea -> same row, no duplicate
    assert a["idea_key"] == "volunteer-spotlight"
    assert len(await led.list_posts(org)) == 1


async def test_create_post_without_dedup_is_legacy_null_group():
    org = str(uuid.uuid4()); set_identity("u", org)
    a = await led.create_post(org, "Same Title", "x", "suggested")
    b = await led.create_post(org, "Same Title", "x", "suggested")
    assert a["id"] != b["id"]
    assert a["idea_key"] is None and b["idea_key"] is None


async def test_dedup_ignores_archived_so_idea_can_recur():
    org = str(uuid.uuid4()); set_identity("u", org)
    a = await led.create_post(org, "Earth Day", "x", "suggested", dedup=True)
    await led.update_post(org, a["id"], "archived", None, None)
    b = await led.create_post(org, "Earth Day", "x", "suggested", dedup=True)
    assert a["id"] != b["id"]                        # an archived idea doesn't block a fresh suggestion


async def test_live_idea_group_is_unique():
    org = str(uuid.uuid4()); set_identity("u", org)
    await led.create_post(org, "X", "a", "suggested", idea_key="dup-key")
    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        await led.create_post(org, "Y", "b", "drafting", idea_key="dup-key")


async def test_set_planned_at_sets_time_and_date_and_get_post():
    org = str(uuid.uuid4()); set_identity("u", org)
    p = await led.create_post(org, "Timed", "x", "drafted")
    dt = datetime(2026, 7, 6, 22, 30, tzinfo=timezone.utc)
    assert await led.set_planned_at(org, p["id"], dt) is True
    got = await led.get_post(org, p["id"])
    assert got["planned_at"].startswith("2026-07-06T22:30")
    assert got["planned_for"] == "2026-07-06"
    assert got["image_ids"] == []
