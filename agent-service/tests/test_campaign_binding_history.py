"""Sticky conversation binding + campaign update + semantic history match.

These cover the regression where "Edit in chat" / "Refine in chat" lost the campaign/post on follow-up
turns (the binding was per-turn only), and the new plan-from-history feature (embed → similar).
"""
import uuid
import pytest
from app.repo import conversations as conv_repo
from app.repo import campaigns as camp
from app.repo import campaign_history as hist
from app.agent import tools
from app.security import context as ctx

pytestmark = pytest.mark.usefixtures("db_pool")


def _unit_vec(idx: int, dim: int = 2560) -> list[float]:
    v = [0.0] * dim
    v[idx] = 1.0
    return v


async def test_conversation_binding_persists_and_inherits():
    org = str(uuid.uuid4())
    user = str(uuid.uuid4())
    ctx.set_identity(user, org)
    conv = await conv_repo.create_conversation(org, user, "Edit campaign")

    # No binding yet.
    assert await conv_repo.get_binding(org, conv["id"]) == {"active_campaign_id": None, "active_post_id": None}

    cid, pid = str(uuid.uuid4()), str(uuid.uuid4())
    await conv_repo.set_binding(org, conv["id"], campaign_id=cid, post_id=pid)

    # A follow-up turn (no fresh post_context) inherits exactly what was stored.
    b = await conv_repo.get_binding(org, conv["id"])
    assert b == {"active_campaign_id": cid, "active_post_id": pid}

    # A campaign-only rebind clears the post.
    cid2 = str(uuid.uuid4())
    await conv_repo.set_binding(org, conv["id"], campaign_id=cid2, post_id=None)
    b2 = await conv_repo.get_binding(org, conv["id"])
    assert b2 == {"active_campaign_id": cid2, "active_post_id": None}


async def test_update_campaign_brief_rewrites_description():
    from datetime import date
    org = str(uuid.uuid4())
    ctx.set_identity(str(uuid.uuid4()), org)
    c = await camp.create(org, "a 2-week donation boost campaign", "instagram",
                          [{"slot_date": date(2026, 7, 6), "angle": "a", "platform": "instagram"}])

    # The tool is bound to the active campaign via the ContextVar (as the WS layer sets it).
    ctx.active_campaign_var.set(c["id"])
    out = await tools.update_campaign.ainvoke({"brief": "a 3-week donation boost campaign"})
    assert "updated" in out.lower()
    assert (await camp.get(org, c["id"]))["brief"] == "a 3-week donation boost campaign"


async def test_update_campaign_without_binding_is_a_noop_message():
    org = str(uuid.uuid4())
    ctx.set_identity(str(uuid.uuid4()), org)
    ctx.active_campaign_var.set(None)
    out = await tools.update_campaign.ainvoke({"brief": "anything"})
    assert "edit in chat" in out.lower()


async def test_campaign_history_similar_ranks_by_topic():
    from datetime import date
    org = str(uuid.uuid4())
    ctx.set_identity(str(uuid.uuid4()), org)
    a = await camp.create(org, "summer water drive", "instagram",
                          [{"slot_date": date(2026, 7, 6), "angle": "splash day", "platform": "instagram"}])
    b = await camp.create(org, "winter coat appeal", "instagram",
                          [{"slot_date": date(2026, 1, 6), "angle": "warm coats", "platform": "instagram"}])
    await hist.upsert_embedding(org, a["id"], a["brief"], _unit_vec(0))
    await hist.upsert_embedding(org, b["id"], b["brief"], _unit_vec(1))

    # Query close to A's vector → A ranks first with a high score; both are returned.
    res = await hist.similar(org, _unit_vec(0), k=3)
    assert res and res[0]["campaign_id"] == a["id"]
    assert res[0]["score"] > 0.9
    ids = {r["campaign_id"] for r in res}
    assert a["id"] in ids and b["id"] in ids
    # Engagement aggregates default to 0 with no metrics, and the post count reflects the slots.
    assert res[0]["engagement"] == 0 and res[0]["posts"] == 1


async def test_apply_to_post_saves_staged_caption():
    from app.repo import ledger as led
    from app.repo import conversation_drafts as drafts
    org = str(uuid.uuid4())
    user = str(uuid.uuid4())
    ctx.set_identity(user, org)
    conv = await conv_repo.create_conversation(org, user, "Refine post")
    p = await led.create_post(org, "t", "t", status="drafted")
    await led.update_post(org, p["id"], "drafted", "original caption", None)
    # Bind the chat to the post and stage a refined caption (as refine_campaign_post does).
    ctx.active_post_var.set(p["id"])
    ctx.conv_id_var.set(conv["id"])
    await drafts.upsert_caption(org, conv["id"], "a shiny new caption")

    out = await tools.apply_to_post.ainvoke({})
    assert "saved" in out.lower()
    assert (await led.get_post(org, p["id"]))["content"] == "a shiny new caption"


async def test_apply_to_post_without_bound_post_is_a_noop_message():
    org = str(uuid.uuid4())
    ctx.set_identity(str(uuid.uuid4()), org)
    ctx.active_post_var.set(None)
    out = await tools.apply_to_post.ainvoke({})
    assert "refine in chat" in out.lower()


async def test_generate_image_attaches_to_active_post():
    from app.repo import ledger as led
    org = str(uuid.uuid4())
    ctx.set_identity(str(uuid.uuid4()), org)
    p = await led.create_post(org, "t", "t", status="drafted")
    ctx.active_post_var.set(p["id"])
    img = str(uuid.uuid4())
    assert await tools._attach_images_to_active_post(org, [img]) is True
    assert (await led.get_post(org, p["id"]))["image_ids"] == [img]
    # Idempotent: attaching the same image again is a no-op (no duplicate, returns False — nothing changed).
    assert await tools._attach_images_to_active_post(org, [img]) is False
    assert (await led.get_post(org, p["id"]))["image_ids"] == [img]


async def test_campaign_history_excludes_self():
    from datetime import date
    org = str(uuid.uuid4())
    ctx.set_identity(str(uuid.uuid4()), org)
    a = await camp.create(org, "gala night", "instagram",
                          [{"slot_date": date(2026, 7, 6), "angle": "x", "platform": "instagram"}])
    await hist.upsert_embedding(org, a["id"], a["brief"], _unit_vec(3))
    assert await hist.similar(org, _unit_vec(3), k=3, exclude_id=a["id"]) == []
