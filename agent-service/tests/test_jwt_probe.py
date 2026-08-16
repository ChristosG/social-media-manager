import base64

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.security.jwt import JWTValidator
from app.security.jwt_probe import evaluate_identity, _extract_token


def _keypair():
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return priv, JWTValidator(base64.standard_b64encode(raw).decode())


def test_clean_when_token_matches_headers():
    priv, v = _keypair()
    tok = jwt.encode({"sub": "u1", "tid": "t1"}, priv, algorithm="EdDSA")
    assert evaluate_identity(v, tok, "u1", "t1") == []


def test_flags_sub_mismatch():
    priv, v = _keypair()
    tok = jwt.encode({"sub": "u1", "tid": "t1"}, priv, algorithm="EdDSA")
    problems = evaluate_identity(v, tok, "u2", "t1")
    assert problems and problems[0].startswith("sub(")


def test_flags_invalid_token():
    _priv, v = _keypair()
    problems = evaluate_identity(v, "not-a-jwt", "u1", "t1")
    assert problems and problems[0].startswith("invalid-token")


def test_missing_token_only_flagged_when_authenticated():
    _priv, v = _keypair()
    assert evaluate_identity(v, None, "u1", None) == ["missing-token"]
    assert evaluate_identity(v, None, None, None) == []   # unauthenticated path → not flagged


def test_extract_token_from_bearer_or_header():
    assert _extract_token("Bearer abc.def", None) == "abc.def"
    assert _extract_token(None, "xyz") == "xyz"
    assert _extract_token("Basic nope", None) is None
    assert _extract_token(None, None) is None


def _reset_probe():
    """Drop the cached validator + settings so env changes take effect."""
    import app.security.jwt_probe as probe
    from app.config import get_settings
    get_settings.cache_clear()
    probe._validator_cache = probe._UNSET


def test_check_identity_and_enforced_with_key(monkeypatch):
    """The WS handler relies on enforced()+check_identity behaving exactly like the HTTP probe."""
    import app.security.jwt_probe as probe
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setenv("JWT_PUBLIC_KEY", base64.standard_b64encode(raw).decode())
    monkeypatch.setenv("JWT_ENFORCE", "true")
    _reset_probe()
    try:
        tok = jwt.encode({"sub": "u1", "tid": "t1"}, priv, algorithm="EdDSA")
        assert probe.enforced() is True
        assert probe.check_identity(tok, "u1", "t1") == []           # valid + matching → clean
        assert probe.check_identity(None, "u1", "t1") == ["missing-token"]
        bad = probe.check_identity(tok, "u2", "t1")
        assert bad and bad[0].startswith("sub(")                     # token/header mismatch → flagged
    finally:
        _reset_probe()


def test_no_enforcement_without_key(monkeypatch):
    """No public key configured → cannot verify → never enforce and never block (dev/local safety)."""
    import app.security.jwt_probe as probe
    monkeypatch.delenv("JWT_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("JWT_ENFORCE", "true")
    _reset_probe()
    try:
        assert probe.enforced() is False
        assert probe.check_identity(None, "u1", "t1") == []
    finally:
        _reset_probe()
