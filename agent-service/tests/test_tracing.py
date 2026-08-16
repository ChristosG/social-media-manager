"""Langfuse tracing is opt-in and must be a no-op (never raise) when unconfigured."""
import importlib

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_settings_cache():
    """These tests clear + repopulate the global get_settings lru-cache with Langfuse keys set.
    Without cleanup that polluted (langfuse-enabled) Settings leaks into later tests (e.g. test_ws,
    which would then build a real Langfuse handler and break streaming). Reset caches on teardown."""
    yield
    get_settings.cache_clear()
    import app.obs.tracing as t
    t.get_handler.cache_clear()


def _reload_tracing(monkeypatch, **env):
    """Re-import the tracing module with a fresh settings cache under the given env."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    import app.obs.tracing as tracing
    importlib.reload(tracing)
    tracing.get_handler.cache_clear()
    return tracing


def test_disabled_when_keys_unset(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    tracing = _reload_tracing(monkeypatch)
    assert tracing.get_handler() is None
    # Config splat must be empty so callers can always pass it to .astream()
    assert tracing.trace_config(org_id="o1", conv_id="c1") == {}


def _fake_handler(monkeypatch):
    """Swap the real CallbackHandler for a no-network stub so tests stay deterministic
    (the real one spawns a background flush thread that would try to reach Langfuse)."""
    import langfuse.callback as lf

    class _Stub:
        def __init__(self, **kw): self.kw = kw

    monkeypatch.setattr(lf, "CallbackHandler", _Stub)


def test_enabled_builds_config(monkeypatch):
    _fake_handler(monkeypatch)
    tracing = _reload_tracing(
        monkeypatch,
        LANGFUSE_PUBLIC_KEY="pk-lf-test",
        LANGFUSE_SECRET_KEY="sk-lf-test",
        LANGFUSE_HOST="http://localhost:3001",
    )
    handler = tracing.get_handler()
    assert handler is not None
    cfg = tracing.trace_config(org_id="org-123", conv_id="conv-abc", reasoning=True)
    assert cfg["callbacks"] == [handler]
    assert cfg["metadata"]["langfuse_session_id"] == "conv-abc"
    assert cfg["metadata"]["langfuse_user_id"] == "org-123"
    assert cfg["metadata"]["reasoning"] is True
    assert "org:org-123" in cfg["tags"]


def test_config_drops_none_values(monkeypatch):
    _fake_handler(monkeypatch)
    tracing = _reload_tracing(
        monkeypatch, LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk")
    assert tracing.get_handler() is not None
    cfg = tracing.trace_config(org_id="o", conv_id=None)
    assert "langfuse_session_id" not in cfg["metadata"]
