import uuid
import pytest
from app.social import crypto
from app.repo import connections as repo

pytestmark = pytest.mark.asyncio


def test_token_encrypt_decrypt_roundtrip_and_nonced():
    tok = "EAAB-super-secret-token-xyz"
    aad = b"org-1|facebook|page-9"
    a = crypto.encrypt_token(tok, aad)
    b = crypto.encrypt_token(tok, aad)
    assert isinstance(a, (bytes, bytearray)) and a != b          # random nonce → different ciphertext
    assert crypto.decrypt_token(a, aad) == tok and crypto.decrypt_token(b, aad) == tok


def test_decrypt_fails_when_aad_row_identity_differs():
    # a ciphertext sealed for one row must not decrypt under another row's identity (substitution guard)
    blob = crypto.encrypt_token("tok", b"org-A|facebook|page-1")
    with pytest.raises(crypto.InvalidTag):
        crypto.decrypt_token(blob, b"org-B|facebook|page-1")


def test_key_fails_closed_without_meta_token_key(monkeypatch):
    class _S:
        meta_token_key = ""        # not configured
    monkeypatch.setattr(crypto, "get_settings", lambda: _S())
    with pytest.raises(RuntimeError):
        crypto.encrypt_token("x", b"aad")   # refuses rather than using a default/public key


async def test_connections_repo_stores_encrypted_and_hides_token(db_pool):
    org = str(uuid.uuid4())
    c = await repo.create_connection(org, "facebook", "page-123", "My Page",
                                     token="secret-tok", scopes="pages_read_engagement")
    assert "access_token" not in c and "access_token_enc" not in c   # never exposed in the dict
    assert c["provider"] == "facebook" and c["external_id"] == "page-123" and c["status"] == "active"
    # the plaintext token is retrievable only via the explicit decrypt path
    assert await repo.get_token(org, c["id"]) == "secret-tok"
    # listing hides tokens too
    lst = await repo.list_connections(org)
    assert lst and all("access_token" not in x for x in lst)


async def test_connections_rls_isolation(db_pool):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    c = await repo.create_connection(a, "instagram", "ig-1", "IG", token="t")
    assert await repo.get_connection(b, c["id"]) is None
    assert await repo.get_token(b, c["id"]) is None
