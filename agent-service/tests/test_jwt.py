import base64, time, jwt, pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.security.jwt import JWTValidator, Claims


def _keypair_b64():
    priv = Ed25519PrivateKey.generate()
    raw_pub = priv.public_key().public_bytes_raw()
    return priv, base64.standard_b64encode(raw_pub).decode()


def test_valid_token_returns_claims():
    priv, pub_b64 = _keypair_b64()
    token = jwt.encode(
        {"sub": "user-1", "tid": "org-1", "roles": ["owner"],
         "exp": int(time.time()) + 60},
        priv, algorithm="EdDSA")
    claims = JWTValidator(pub_b64).validate(token)
    assert claims == Claims(sub="user-1", tid="org-1", roles=["owner"], email=None)


def test_invalid_signature_rejected():
    _, pub_b64 = _keypair_b64()
    other, _ = _keypair_b64()
    token = jwt.encode({"sub": "x", "exp": int(time.time()) + 60}, other, algorithm="EdDSA")
    with pytest.raises(ValueError):
        JWTValidator(pub_b64).validate(token)


def test_malformed_roles_claim_fails_closed():
    """A non-list `roles` claim must yield no roles, never a misparsed/substring-matchable one."""
    priv, pub_b64 = _keypair_b64()
    token = jwt.encode(
        {"sub": "user-1", "roles": "superadmin", "exp": int(time.time()) + 60},
        priv, algorithm="EdDSA")
    claims = JWTValidator(pub_b64).validate(token)
    assert claims.roles == []


def test_claims_are_frozen():
    """Validated identity is immutable — it can't be reassigned downstream."""
    import dataclasses
    c = Claims(sub="u")
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.sub = "attacker"
