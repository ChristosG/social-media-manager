import pytest
from app.repo import ledger as led
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio
ORG = "22222222-2222-2222-2222-222222222222"


async def test_update_records_revision_and_undo_restores(db_pool):
    p = await led.create_post(ORG, "Leo story", "angle", status="drafted")
    await led.update_post(ORG, p["id"], None, "v1 caption", None)
    await led.update_post(ORG, p["id"], None, "v2 caption", None)
    # one revision recorded (v1, the content displaced by v2). The create→v1 write had NULL prior content.
    assert (await led.get_post(ORG, p["id"]))["content"] == "v2 caption"
    restored = await led.undo_caption(ORG, p["id"])
    assert restored == "v1 caption"
    assert (await led.get_post(ORG, p["id"]))["content"] == "v1 caption"
    # nothing left to undo → None, content unchanged
    assert await led.undo_caption(ORG, p["id"]) is None
    assert (await led.get_post(ORG, p["id"]))["content"] == "v1 caption"


async def test_update_stores_refine_suggestions(db_pool):
    p = await led.create_post(ORG, "Stats post", "angle", status="drafted")
    await led.update_post(ORG, p["id"], "drafted", "1 in 5 kids…", None,
                          suggestions=["Lead with the number", "Add the source"])
    got = await led.get_post(ORG, p["id"])
    assert got["refine_suggestions"] == ["Lead with the number", "Add the source"]
