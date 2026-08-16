"""The campaign draft tools: add a user-typed custom draft, and delete a draft (per-card trash)."""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import campaigns as camp, ledger as led

pytestmark = pytest.mark.usefixtures("db_pool")


def _h(org):
    return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


async def _campaign(org):
    return await camp.create(org, "brief", "instagram",
                             [{"angle": "one", "platform": "instagram", "slot_date": date(2026, 7, 1),
                               "slot_at": None}])


async def test_custom_draft_creates_drafted_post():
    org = str(uuid.uuid4())
    c = await _campaign(org)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        r = await cl.post(f"/campaigns/{c['id']}/custom-draft",
                          json={"caption": "My own caption", "date": "2026-07-05"}, headers=_h(org))
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] and body["post_id"]
    again = await camp.get(org, c["id"])
    assert len(again["slots"]) == 2   # original + the custom one
    post = await led.get_post(org, body["post_id"])
    assert post["status"] == "drafted" and post["content"] == "My own caption" and post["origin"] == "custom"


async def test_custom_draft_requires_caption():
    org = str(uuid.uuid4())
    c = await _campaign(org)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        r = await cl.post(f"/campaigns/{c['id']}/custom-draft", json={"caption": "   "}, headers=_h(org))
        assert r.status_code == 422


async def test_delete_slot_archives_post_and_drops_slot():
    org = str(uuid.uuid4())
    c = await _campaign(org)
    sid = c["slots"][0]["id"]
    p = await led.create_post(org, "t", "b", status="drafted")
    await camp.attach_post(org, sid, p["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        r = await cl.delete(f"/campaigns/{c['id']}/slots/{sid}", headers=_h(org))
        assert r.status_code == 200
    again = await camp.get(org, c["id"])
    assert len(again["slots"]) == 0
    assert (await led.get_post(org, p["id"]))["status"] == "archived"


async def test_delete_slot_rejects_foreign_slot():
    org = str(uuid.uuid4())
    c = await _campaign(org)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        r = await cl.delete(f"/campaigns/{c['id']}/slots/{uuid.uuid4()}", headers=_h(org))
        assert r.status_code == 404
