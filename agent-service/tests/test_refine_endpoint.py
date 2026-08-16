import pytest
from datetime import date
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.repo import campaigns as camp, ledger as led
from app.agent import refine as refine_mod

pytestmark = pytest.mark.asyncio
ORG = "33333333-3333-3333-3333-333333333333"
USER = "44444444-4444-4444-4444-444444444444"
H = {"X-User-Id": USER, "X-Tenant-Id": ORG}


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_refine_returns_proposal_without_writing(db_pool, monkeypatch):
    async def fake_refine(org, caption, intent, platform, model=None):
        return ("WARMER: " + caption, ["Shorter", "Add a CTA"])
    monkeypatch.setattr(refine_mod, "refine_caption", fake_refine)

    # camp.create(org_id, brief, platform, slots) — 4 positional args; slot_date must be a date object
    c = await camp.create(ORG, "brief", "facebook",
                          [{"angle": "Leo", "platform": "facebook",
                            "slot_date": date(2026, 7, 1), "slot_at": None}])
    p = await led.create_post(ORG, "Leo", "Leo", status="drafted")
    await led.update_post(ORG, p["id"], "drafted", "original", None)
    await camp.attach_post(ORG, c["slots"][0]["id"], p["id"])

    async with await _client() as cl:
        r = await cl.post(f"/campaigns/{c['id']}/posts/{p['id']}/refine",
                          json={"intent": "Warmer"}, headers=H)
    assert r.status_code == 200
    assert r.json()["caption"].startswith("WARMER: original")
    assert r.json()["suggestions"] == ["Shorter", "Add a CTA"]
    assert (await led.get_post(ORG, p["id"]))["content"] == "original"


async def test_refine_rejects_post_not_in_campaign(db_pool, monkeypatch):
    monkeypatch.setattr(refine_mod, "refine_caption",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")))
    # camp.create(org_id, brief, platform, slots) — 4 positional args; slot_date must be a date object
    c = await camp.create(ORG, "brief", "facebook",
                          [{"angle": "x", "platform": "facebook",
                            "slot_date": date(2026, 7, 1), "slot_at": None}])
    stray = await led.create_post(ORG, "stray", "stray", status="drafted")
    async with await _client() as cl:
        r = await cl.post(f"/campaigns/{c['id']}/posts/{stray['id']}/refine",
                          json={"intent": "Warmer"}, headers=H)
    assert r.status_code == 404


async def test_undo_endpoint_restores_previous(db_pool):
    p = await led.create_post(ORG, "u", "u", status="drafted")
    await led.update_post(ORG, p["id"], None, "v1", None)
    await led.update_post(ORG, p["id"], None, "v2", None)
    async with await _client() as cl:
        r = await cl.post(f"/ledger/{p['id']}/undo", headers=H)
    assert r.status_code == 200 and r.json()["caption"] == "v1"
    assert (await led.get_post(ORG, p["id"]))["content"] == "v1"
