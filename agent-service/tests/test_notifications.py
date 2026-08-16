import uuid, pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import notifications as nr

pytestmark = pytest.mark.asyncio


async def test_create_list_unread_and_mark(db_pool):
    org = str(uuid.uuid4())
    await nr.create(org, user_id=None, type="publish_ok", title="Published ✓",
                    body="IG", link="https://instagram.com/p/x")
    items = await nr.list_for(org, user_id=None, limit=10)
    assert len(items) == 1 and items[0]["title"] == "Published ✓"
    assert items[0]["read"] is False
    assert await nr.unread_count(org, None) == 1
    await nr.mark_read(org, items[0]["id"])
    assert await nr.unread_count(org, None) == 0


async def test_mark_all(db_pool):
    org = str(uuid.uuid4())
    await nr.create(org, None, "connected", "A")
    await nr.create(org, None, "connected", "B")
    assert await nr.unread_count(org, None) == 2
    await nr.mark_all(org, None)
    assert await nr.unread_count(org, None) == 0


async def test_notifications_endpoint(db_pool):
    org = str(uuid.uuid4())
    await nr.create(org, None, "connected", "Connected", "FB")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/notifications", headers={"x-user-id": "u", "x-tenant-id": org})
    assert r.status_code == 200
    body = r.json()
    assert body["unread_count"] == 1 and len(body["items"]) == 1
