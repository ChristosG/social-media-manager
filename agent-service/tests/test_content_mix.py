"""Task 3 — content-mix breakdown by content pillar.

Seeds posts in counted statuses with assorted pillars (incl. a NULL one), then asserts the
`/insights/summary` payload carries a `content_mix` list with per-pillar counts and an
`'uncategorized'` bucket for the post with no pillar.
"""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.repo import ledger as led

pytestmark = pytest.mark.asyncio


def _h(org):
    return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _seed(org):
    """3 fundraising + 1 stories + 1 with NULL pillar, all in counted statuses."""
    async def _mk(pillar, status):
        p = await led.create_post(org, "t", "brief", status="suggested")
        await led.update_post(org, p["id"], status, "caption", "facebook", pillar=pillar)
        return p["id"]

    for _ in range(3):
        await _mk("fundraising", "drafted")
    await _mk("stories", "approved")
    # NULL pillar (pillar never set) — must land in the 'uncategorized' bucket.
    p = await led.create_post(org, "t", "brief", status="suggested")
    await led.update_post(org, p["id"], "scheduled", "caption", "facebook")


async def test_content_mix_groups_by_pillar(db_pool):
    org = str(uuid.uuid4())
    await _seed(org)
    async with await _client() as cl:
        r = await cl.get("/insights/summary?platform=all&range=30", headers=_h(org))
    assert r.status_code == 200
    mix = r.json()["content_mix"]
    assert isinstance(mix, list)
    by = {row["pillar"]: row["count"] for row in mix}
    assert by["fundraising"] == 3
    assert by["stories"] == 1
    assert by["uncategorized"] == 1
    # ordered by count desc → fundraising leads
    assert mix[0]["pillar"] == "fundraising"
