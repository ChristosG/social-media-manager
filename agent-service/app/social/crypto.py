import os
from cryptography.exceptions import InvalidTag  # re-exported for callers/tests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from app.config import get_settings

_MIN_KEY_LEN = 16
__all__ = ["encrypt_token", "decrypt_token", "InvalidTag"]


def _key() -> bytes:
    """Derive the 32-byte AES-256-GCM key from META_TOKEN_KEY via HKDF-SHA256 (domain-separated).

    FAILS CLOSED: refuses to operate without a configured, sufficiently-long META_TOKEN_KEY. It never
    falls back to another secret or a hardcoded default, so OAuth tokens can never be encrypted under a
    guessable or repo-public key. Set META_TOKEN_KEY to a strong value (ideally a base64 32-byte random
    key) in deploy/.env before connecting social accounts."""
    secret = get_settings().meta_token_key
    if not secret or len(secret) < _MIN_KEY_LEN:
        raise RuntimeError(
            "META_TOKEN_KEY is not configured or is too short (need >=16 chars; a base64 32-byte random "
            "key is recommended). Refusing to encrypt/decrypt OAuth tokens without it.")
    return HKDF(algorithm=hashes.SHA256(), length=32,
                salt=b"social-studio/meta-token/v1", info=b"meta-token-enc").derive(secret.encode())


def encrypt_token(plaintext: str, aad: bytes) -> bytes:
    """AES-256-GCM encrypt → nonce||ciphertext||tag. `aad` binds the ciphertext to its row identity
    (e.g. org|provider|external_id), so a ciphertext copied onto a different row fails authentication."""
    nonce = os.urandom(12)
    return nonce + AESGCM(_key()).encrypt(nonce, plaintext.encode(), aad)


def decrypt_token(blob, aad: bytes) -> str:
    """Decrypt; raises cryptography.exceptions.InvalidTag if the ciphertext or the `aad` (row identity)
    doesn't match what was sealed."""
    raw = bytes(blob)
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], aad).decode()
