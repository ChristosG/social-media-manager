import app.security.proxy_guard as pg
from app.config import get_settings


def _reset():
    get_settings.cache_clear()


def test_disabled_when_no_secret(monkeypatch):
    """No AGENT_PROXY_SECRET → ACL is off and everything is allowed (default, dev-safe)."""
    monkeypatch.delenv("AGENT_PROXY_SECRET", raising=False)
    _reset()
    try:
        assert pg.proxy_secret() == ""
        assert pg.proxy_secret_ok(None) is True
        assert pg.proxy_secret_ok("anything") is True
    finally:
        _reset()


def test_enforced_when_secret_set(monkeypatch):
    """Secret set → only the matching value passes (constant-time compare)."""
    monkeypatch.setenv("AGENT_PROXY_SECRET", "s3cr3t-value")
    _reset()
    try:
        assert pg.proxy_secret() == "s3cr3t-value"
        assert pg.proxy_secret_ok("s3cr3t-value") is True
        assert pg.proxy_secret_ok("wrong") is False
        assert pg.proxy_secret_ok("") is False
        assert pg.proxy_secret_ok(None) is False
    finally:
        _reset()
