import pytest
from app.security import context as ctx
from app.repo import ledger as led
from app.agent import tools, refine as refine_mod

pytestmark = pytest.mark.asyncio
ORG = "77777777-7777-7777-7777-777777777777"


async def test_refine_tool_uses_bound_post_and_proposes(db_pool, monkeypatch):
    ctx.set_identity("u", ORG)
    p = await led.create_post(ORG, "t", "t", status="drafted")
    await led.update_post(ORG, p["id"], "drafted", "original", None)
    ctx.active_post_var.set(p["id"])
    async def fake_refine(org, caption, intent, platform, model=None):
        return ("refined: " + caption, ["Shorter"])
    monkeypatch.setattr(refine_mod, "refine_caption", fake_refine)

    out = await tools.refine_campaign_post.ainvoke({"intent": "warmer"})
    assert "refined: original" in out
    assert (await led.get_post(ORG, p["id"]))["content"] == "original"  # proposal only, no write


async def test_refine_tool_without_bound_post_is_a_noop_message(db_pool):
    ctx.set_identity("u", ORG)
    ctx.active_post_var.set(None)
    out = await tools.refine_campaign_post.ainvoke({"intent": "warmer"})
    assert "open" in out.lower() or "no post" in out.lower()
