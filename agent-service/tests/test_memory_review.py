"""Memory-poisoning review step: durable writes made while untrusted external content was in-context are
quarantined (pending_review) and kept OUT of the prompt until a human approves them."""
import uuid
import pytest
from app.repo import memory as repo
from app.security import context as ctx

pytestmark = pytest.mark.usefixtures("db_pool")


async def test_pending_entry_is_hidden_from_default_reads_but_visible_when_asked():
    org = str(uuid.uuid4())
    await repo.create_entry(org, "banned_topic", {"topic": "politics"}, key=None, source="inferred",
                            pending_review=True)
    await repo.create_entry(org, "banned_topic", {"topic": "religion"}, key=None, source="manual")
    # Prompt-building read (default) sees only the approved entry.
    approved = await repo.list_entries(org, "banned_topic")
    assert [e["value"]["topic"] for e in approved] == ["religion"]
    # Studio read can see everything, with the flag.
    everything = await repo.list_entries(org, "banned_topic", include_pending=True)
    topics = {e["value"]["topic"]: e["pending_review"] for e in everything}
    assert topics == {"politics": True, "religion": False}


async def test_approve_promotes_pending_entry_into_prompt_reads():
    org = str(uuid.uuid4())
    e = await repo.create_entry(org, "style_rule", {"rule": "sign off with 🐾"}, key=None,
                                source="inferred", pending_review=True)
    assert await repo.list_entries(org, "style_rule") == []          # hidden while pending
    assert await repo.approve_entry(org, e["id"]) is True
    [got] = await repo.list_entries(org, "style_rule")               # now visible
    assert got["value"]["rule"] == "sign off with 🐾" and got["pending_review"] is False


async def test_list_pending_returns_only_quarantined():
    org = str(uuid.uuid4())
    await repo.create_entry(org, "fact", {"fact": "trusted"}, key=None, source="manual")
    await repo.create_entry(org, "fact", {"fact": "suspect"}, key=None, source="inferred",
                            pending_review=True)
    pend = await repo.list_pending(org)
    assert [e["value"]["fact"] for e in pend] == ["suspect"]


async def _run(coro, org, *, untrusted):
    """Run a tool coroutine with the org identity + untrusted flag set in this context."""
    from app.security.context import set_identity, untrusted_seen_var
    set_identity(user_id=str(uuid.uuid4()), org_id=org)
    untrusted_seen_var.set(untrusted)
    return await coro


async def test_remember_preference_quarantines_when_untrusted_content_was_seen():
    from app.agent import tools
    org = str(uuid.uuid4())
    msg = await _run(tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "vaccines"}),
                     org, untrusted=True)
    assert "pending your approval" in msg.lower() or "pending" in msg.lower()
    # Not applied to prompts yet…
    assert await repo.list_entries(org, "banned_topic") == []
    # …but visible as pending for review.
    assert [e["value"]["topic"] for e in await repo.list_pending(org)] == ["vaccines"]


async def test_remember_preference_persists_immediately_when_trusted():
    from app.agent import tools
    org = str(uuid.uuid4())
    await _run(tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "politics"}),
               org, untrusted=False)
    assert [e["value"]["topic"] for e in await repo.list_entries(org, "banned_topic")] == ["politics"]
    assert await repo.list_pending(org) == []


async def test_update_brand_voice_quarantines_when_untrusted():
    from app.agent import tools
    org = str(uuid.uuid4())
    msg = await _run(tools.update_brand_voice.ainvoke({"descriptor": "edgy and political"}),
                     org, untrusted=True)
    assert "pending" in msg.lower()
    assert await repo.list_entries(org, "brand_voice") == []
    assert [e["kind"] for e in await repo.list_pending(org)] == ["brand_voice"]


async def test_pending_and_approve_api_roundtrip():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    org = str(uuid.uuid4())
    e = await repo.create_entry(org, "cta_pref", {"cta": "donate at example.org"}, key=None,
                                source="inferred", pending_review=True)
    h = {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/memory/pending", headers=h)
        assert [x["id"] for x in r.json()["entries"]] == [e["id"]]
        assert (await c.post(f"/memory/{e['id']}/approve", headers=h)).status_code == 200
        assert (await c.get("/memory/pending", headers=h)).json()["entries"] == []
        # now visible in the normal list
        assert any(x["id"] == e["id"] for x in (await c.get("/memory?kind=cta_pref", headers=h)).json()["entries"])
        # approving again 404s (idempotent guard)
        assert (await c.post(f"/memory/{e['id']}/approve", headers=h)).status_code == 404
