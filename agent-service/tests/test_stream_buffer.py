"""The Redis-backed streaming-resume snapshot: a best-effort round-trip that NEVER raises into the chat path,
so a reload/reconnect can recover a turn after a restart or past the in-memory grace window."""
import pytest
from app import stream_buffer

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    def __init__(self):
        self.store = {}

    async def set(self, k, v, ex=None):
        self.store[k] = v

    async def get(self, k):
        return self.store.get(k)

    async def delete(self, k):
        self.store.pop(k, None)


async def test_save_load_delete_roundtrip(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(stream_buffer, "_redis", lambda: fake)
    snap = {"user_id": "u", "org_id": "o", "buffer": "hello world", "done": True,
            "final_message": {"id": "1", "content": "hello world"}}
    await stream_buffer.save("conv1", snap)
    assert await stream_buffer.load("conv1") == snap
    await stream_buffer.delete("conv1")
    assert await stream_buffer.load("conv1") is None


async def test_best_effort_when_redis_unavailable(monkeypatch):
    class _Down:
        async def set(self, *a, **k):
            raise RuntimeError("redis down")

        async def get(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(stream_buffer, "_redis", lambda: _Down())
    await stream_buffer.save("c", {"x": 1})        # must not raise
    assert await stream_buffer.load("c") is None   # degrades to None, never raises
