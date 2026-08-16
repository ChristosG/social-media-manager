import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import connections as cr, comments as comment_repo

pytestmark = pytest.mark.asyncio
ENGAGE_FB = "pages_show_list,pages_read_engagement,pages_manage_engagement"


def _hdr(user, org):
    return {"x-user-id": user, "x-tenant-id": org}


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_settings_toggle_and_can_engage(db_pool, monkeypatch):
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    # Enabling the toggle kicks a forced ingest pass — stub it so the test doesn't hit the live Graph API.
    from app.api import comments as capi
    monkeypatch.setattr(capi, "ingest_org_comments",
                        lambda *a, **k: _coro({"status": "ok", "new": 0, "auto_replied": 0}))
    async with await _client() as ac:
        r0 = await ac.get("/comments/settings", headers=_hdr(user, org))
        assert r0.json() == {"auto_reply_safe": False, "can_engage": False}   # no connection yet
        await cr.create_connection(org, "facebook", "PAGE1", "Page", "tok", scopes=ENGAGE_FB)
        r1 = await ac.put("/comments/settings", headers=_hdr(user, org), json={"auto_reply_safe": True})
        assert r1.json()["auto_reply_safe"] is True
        r2 = await ac.get("/comments/settings", headers=_hdr(user, org))
        assert r2.json() == {"auto_reply_safe": True, "can_engage": True}


def _coro(value):
    async def _c():
        return value
    return _c()


async def test_list_filters_by_status(db_pool):
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    conn = await cr.create_connection(org, "facebook", "PAGE1", "Page", "tok", scopes=ENGAGE_FB)
    await comment_repo.upsert_many(org, conn["id"], "facebook",
                                   [{"external_id": "C1", "message": "hi", "commented_at": "2026-06-10T00:00:00+00:00"}])
    async with await _client() as ac:
        r = await ac.get("/comments?status=open", headers=_hdr(user, org))
        body = r.json()
        assert body["can_engage"] is True and len(body["items"]) == 1


async def test_reply_posts_and_marks_replied(db_pool, monkeypatch):
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    conn = await cr.create_connection(org, "facebook", "PAGE1", "Page", "tok", scopes=ENGAGE_FB)
    [c] = await comment_repo.upsert_many(org, conn["id"], "facebook",
                                         [{"external_id": "C1", "message": "love it",
                                           "commented_at": "2026-06-10T00:00:00+00:00"}])
    from app.api import comments as capi
    async def fake_post(provider, ext, token, msg):
        return {"id": "REPLY1"}
    monkeypatch.setattr(capi.cc, "post_reply", fake_post)
    async with await _client() as ac:
        r = await ac.post(f"/comments/{c['id']}/reply", headers=_hdr(user, org), json={"text": "thank you!"})
        assert r.status_code == 200 and r.json()["reply_external_id"] == "REPLY1"
        # second reply -> 409 (exactly-once)
        r2 = await ac.post(f"/comments/{c['id']}/reply", headers=_hdr(user, org), json={"text": "again"})
        assert r2.status_code == 409


async def test_reply_requires_engage_scope(db_pool):
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    conn = await cr.create_connection(org, "facebook", "PAGE1", "Page", "tok", scopes="pages_manage_posts")
    [c] = await comment_repo.upsert_many(org, conn["id"], "facebook",
                                         [{"external_id": "C1", "message": "hi",
                                           "commented_at": "2026-06-10T00:00:00+00:00"}])
    async with await _client() as ac:
        r = await ac.post(f"/comments/{c['id']}/reply", headers=_hdr(user, org), json={"text": "hi"})
        assert r.status_code == 422


async def test_ignore(db_pool):
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    conn = await cr.create_connection(org, "facebook", "PAGE1", "Page", "tok", scopes=ENGAGE_FB)
    [c] = await comment_repo.upsert_many(org, conn["id"], "facebook",
                                         [{"external_id": "C1", "message": "hi",
                                           "commented_at": "2026-06-10T00:00:00+00:00"}])
    async with await _client() as ac:
        assert (await ac.post(f"/comments/{c['id']}/ignore", headers=_hdr(user, org))).status_code == 200
        assert (await ac.post(f"/comments/{c['id']}/ignore", headers=_hdr(user, org))).status_code == 409


async def test_poll_invokes_ingest(db_pool, monkeypatch):
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    from app.api import comments as capi
    async def fake_ingest(org_id, force=False):
        return {"status": "ok", "new": 3, "drafted": 3, "auto_replied": 0, "forced": force}
    monkeypatch.setattr(capi, "ingest_org_comments", fake_ingest)
    async with await _client() as ac:
        r = await ac.post("/comments/poll", headers=_hdr(user, org))
        assert r.json()["new"] == 3 and r.json()["forced"] is True
