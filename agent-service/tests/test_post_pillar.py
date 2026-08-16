import pytest
from app.repo import ledger as led

pytestmark = pytest.mark.asyncio
ORG = "29000000-0000-0000-0000-000000000001"


async def test_update_post_sets_pillar(db_pool):
    p = await led.create_post(ORG, "Leo", "Leo", status="drafted")
    assert (await led.get_post(ORG, p["id"]))["pillar"] is None
    await led.update_post(ORG, p["id"], "drafted", "Meet Leo…", None, pillar="fundraising")
    got = await led.get_post(ORG, p["id"])
    assert got["pillar"] == "fundraising" and got["content"] == "Meet Leo…"
