import uuid
import httpx
from httpx import ASGITransport
from fastapi.testclient import TestClient
from app.main import app


def _headers(org, user=None):
    return {"X-User-Id": user or str(uuid.uuid4()), "X-Tenant-Id": org}


async def test_create_returns_conversation_wrapper(db_pool):
    """POST /conversations → {"conversation": {id, title, model, system_prompt, created_at, updated_at}}"""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "Hello"}, headers=_headers(org))
        assert r.status_code == 200
        body = r.json()
        assert "conversation" in body, f"missing 'conversation' key: {body}"
        conv = body["conversation"]
        assert conv["title"] == "Hello"
        assert "id" in conv
        assert "created_at" in conv
        assert "updated_at" in conv
        assert "model" in conv        # may be null
        assert "system_prompt" in conv  # may be null


async def test_create_with_model(db_pool):
    """POST /conversations with model field → model echoed back"""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "T", "model": "gpt-4o"}, headers=_headers(org))
        assert r.status_code == 200
        conv = r.json()["conversation"]
        assert conv["model"] == "gpt-4o"


async def test_list_returns_total(db_pool):
    """GET /conversations → {"conversations": [...], "total": int}"""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        await client.post("/conversations", json={"title": "A"}, headers=_headers(org))
        await client.post("/conversations", json={"title": "B"}, headers=_headers(org))
        r = await client.get("/conversations", headers=_headers(org))
        assert r.status_code == 200
        body = r.json()
        assert "conversations" in body
        assert "total" in body, f"missing 'total' key: {body}"
        assert body["total"] == 2
        assert len(body["conversations"]) == 2
        for c in body["conversations"]:
            assert "id" in c
            assert "title" in c
            assert "created_at" in c
            assert "updated_at" in c


async def test_list_scoped_to_org(db_pool):
    """Conversations from another org must not appear."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org1, org2 = str(uuid.uuid4()), str(uuid.uuid4())
        await client.post("/conversations", json={"title": "org1-conv"}, headers=_headers(org1))
        r = await client.get("/conversations", headers=_headers(org2))
        titles = [c["title"] for c in r.json()["conversations"]]
        assert "org1-conv" not in titles


async def test_get_returns_conversation_and_messages(db_pool):
    """GET /conversations/{id} → {"conversation": {...}, "messages": [{id, conversation_id, ...}]}"""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "Test"}, headers=_headers(org))
        conv_id = r.json()["conversation"]["id"]
        r2 = await client.get(f"/conversations/{conv_id}", headers=_headers(org))
        assert r2.status_code == 200
        body = r2.json()
        assert "conversation" in body, f"missing 'conversation' key: {body}"
        assert "messages" in body
        c = body["conversation"]
        assert c["id"] == conv_id
        assert "title" in c
        assert "model" in c
        assert "system_prompt" in c
        assert "created_at" in c
        assert "updated_at" in c
        # No messages yet — empty list is fine
        assert body["messages"] == []


async def test_get_messages_have_required_fields(db_pool):
    """Messages must include id, conversation_id, role, content, token_count, attachments, created_at."""
    # We insert a message via the WS path indirectly — use repo directly for speed
    from app.repo import conversations as repo

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        user = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "T"}, headers=_headers(org, user))
        conv_id = r.json()["conversation"]["id"]

    # Add a message directly through the repo (same pool, same event loop)
    msg_id = await repo.add_message(org, conv_id, "user", "hello")
    assert msg_id is not None  # add_message must now return the new id

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/conversations/{conv_id}", headers=_headers(org))
    msgs = r.json()["messages"]
    assert len(msgs) == 1
    m = msgs[0]
    assert m["id"] == str(msg_id)
    assert m["conversation_id"] == conv_id
    assert m["role"] == "user"
    assert m["content"] == "hello"
    assert "token_count" in m     # may be null
    assert "attachments" in m     # must be []
    assert m["attachments"] == []
    assert "created_at" in m


async def test_put_renames_conversation(db_pool):
    """PUT /conversations/{id} with {title} → updated conversation returned."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "Old"}, headers=_headers(org))
        conv_id = r.json()["conversation"]["id"]
        original_updated_at = r.json()["conversation"]["updated_at"]

        r2 = await client.put(
            f"/conversations/{conv_id}",
            json={"title": "New Title"},
            headers=_headers(org),
        )
        assert r2.status_code == 200
        body = r2.json()
        assert "conversation" in body
        assert body["conversation"]["title"] == "New Title"
        assert body["conversation"]["id"] == conv_id
        # updated_at should be set (not necessarily different within the same second, but present)
        assert "updated_at" in body["conversation"]


async def test_put_with_model_and_system_prompt(db_pool):
    """PUT supports optional model and system_prompt fields."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "T"}, headers=_headers(org))
        conv_id = r.json()["conversation"]["id"]

        r2 = await client.put(
            f"/conversations/{conv_id}",
            json={"title": "T2", "model": "claude-3", "system_prompt": "You are..."},
            headers=_headers(org),
        )
        assert r2.status_code == 200
        conv = r2.json()["conversation"]
        assert conv["model"] == "claude-3"
        assert conv["system_prompt"] == "You are..."


async def test_delete_conversation(db_pool):
    """DELETE /conversations/{id} → {"message": "deleted"}"""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "ToDelete"}, headers=_headers(org))
        conv_id = r.json()["conversation"]["id"]

        r2 = await client.delete(f"/conversations/{conv_id}", headers=_headers(org))
        assert r2.status_code == 200
        assert r2.json() == {"message": "deleted"}

        # Verify it's gone
        r3 = await client.get(f"/conversations/{conv_id}", headers=_headers(org))
        assert r3.status_code == 404


async def test_delete_cascades_messages(db_pool):
    """Deleting a conversation also removes its messages."""
    from app.repo import conversations as repo

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        user = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "C"}, headers=_headers(org, user))
        conv_id = r.json()["conversation"]["id"]

    await repo.add_message(org, conv_id, "user", "msg1")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.delete(f"/conversations/{conv_id}", headers=_headers(org))
        assert r.status_code == 200

    # Messages should be gone (via CASCADE)
    msgs = await repo.get_messages(org, conv_id)
    assert msgs == []


async def test_create_and_list_scoped_to_org(db_pool):
    # Keep the old test name for backwards compatibility
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        org = str(uuid.uuid4())
        r = await client.post("/conversations", json={"title": "Hello"}, headers=_headers(org))
        assert r.status_code == 200
        assert r.json()["conversation"]["title"] == "Hello"
        r2 = await client.get("/conversations", headers=_headers(org))
        assert any(c["title"] == "Hello" for c in r2.json()["conversations"])


def test_missing_tenant_rejected():
    client = TestClient(app)
    r = client.post("/conversations", json={"title": "x"}, headers={"X-User-Id": str(uuid.uuid4())})
    assert r.status_code == 403
