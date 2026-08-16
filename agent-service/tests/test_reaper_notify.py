"""The stuck-post reaper used to fail a post silently; it must now notify the user when it gives up
(parity with the normal publish-failure path), but not on a routine requeue."""
import pytest
from app.social import publish_worker as pw

pytestmark = pytest.mark.asyncio


async def test_reaper_notifies_when_it_fails_a_post(monkeypatch):
    async def fake_stale():
        return [("org1", "sp1")]
    async def fake_reap(org, sp_id, max_attempts):
        return "failed"
    calls = []
    async def fake_create(org, *a, **k):
        calls.append((org, a))
    monkeypatch.setattr(pw, "_stale_publishing", fake_stale)
    monkeypatch.setattr(pw.sp, "reap", fake_reap)
    monkeypatch.setattr(pw.nr, "create", fake_create)
    await pw.reap_stale()
    assert calls and calls[0][1][1] == "publish_failed"   # (org, None, "publish_failed", title, body)


async def test_reaper_does_not_notify_on_requeue(monkeypatch):
    async def fake_stale():
        return [("org1", "sp1")]
    async def fake_reap(org, sp_id, max_attempts):
        return "pending"                                  # requeued for another attempt — not a failure
    calls = []
    async def fake_create(org, *a, **k):
        calls.append(org)
    monkeypatch.setattr(pw, "_stale_publishing", fake_stale)
    monkeypatch.setattr(pw.sp, "reap", fake_reap)
    monkeypatch.setattr(pw.nr, "create", fake_create)
    await pw.reap_stale()
    assert calls == []
