import base64
from dataclasses import dataclass, field

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


@dataclass(frozen=True, eq=True)
class Claims:
    """Validated identity from a JWT. Frozen so request-scoped identity can't be mutated downstream."""
    sub: str
    tid: str | None = None
    roles: list[str] = field(default_factory=list)
    email: str | None = None


class JWTValidator:
    def __init__(self, public_key_b64: str):
        raw = base64.standard_b64decode(public_key_b64)
        if len(raw) != 32:
            raise ValueError(f"invalid Ed25519 public key length: {len(raw)}")
        self._key = Ed25519PublicKey.from_public_bytes(raw)

    def validate(self, token: str) -> Claims:
        try:
            payload = jwt.decode(token, self._key, algorithms=["EdDSA"])
        except jwt.PyJWTError as e:
            raise ValueError(f"invalid token: {e}") from e
        if "sub" not in payload:
            raise ValueError("token missing sub")
        # Fail closed on a malformed roles claim (non-list): no roles, never a misparsed one.
        raw_roles = payload.get("roles", [])
        roles = [str(r) for r in raw_roles] if isinstance(raw_roles, list) else []
        return Claims(
            sub=payload["sub"],
            tid=payload.get("tid"),
            roles=roles,
            email=payload.get("email"),
        )
