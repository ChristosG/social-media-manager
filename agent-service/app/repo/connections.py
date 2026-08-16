import uuid
from app.db.pool import org_tx
from app.social import crypto

_PUBLISH_SCOPES = {"instagram": "instagram_content_publish", "facebook": "pages_manage_posts"}
# Reading + replying to comments. FB needs both read (fetch) and manage (reply); IG bundles both in one scope.
_ENGAGE_SCOPES = {"instagram": ("instagram_manage_comments",),
                  "facebook": ("pages_read_engagement", "pages_manage_engagement")}


def can_publish(conn: dict) -> bool:
    need = _PUBLISH_SCOPES.get(conn.get("provider"))
    return bool(need and need in (conn.get("scopes") or ""))


def can_engage(conn: dict) -> bool:
    """True if this connection's granted scopes allow reading AND replying to comments."""
    if conn.get("status") != "active":
        return False
    need = _ENGAGE_SCOPES.get(conn.get("provider"))
    scopes = conn.get("scopes") or ""
    return bool(need and all(s in scopes for s in need))

_COLS = "id, org_id, provider, external_id, display_name, token_expires_at, scopes, status, created_at, updated_at"


def _aad(org_id: str, provider: str, external_id: str) -> bytes:
    """Associated data binding a token ciphertext to its row identity (defense-in-depth on top of RLS):
    a stored ciphertext can't be swapped onto another (org, provider, external_id) row and still decrypt."""
    return f"{org_id}|{provider}|{external_id}".encode()


def _conn(r) -> dict:
    return {"id": str(r["id"]), "org_id": str(r["org_id"]), "provider": r["provider"],
            "external_id": r["external_id"], "display_name": r["display_name"],
            "token_expires_at": r["token_expires_at"].isoformat() if r["token_expires_at"] else None,
            "scopes": r["scopes"], "status": r["status"],
            "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat()}


async def create_connection(org_id: str, provider: str, external_id: str, display_name: str | None,
                            token: str, token_expires_at=None, scopes: str | None = None) -> dict:
    enc = crypto.encrypt_token(token, _aad(org_id, provider, external_id))
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "INSERT INTO connections(org_id, provider, external_id, display_name, access_token_enc, "
            "token_expires_at, scopes) VALUES($1,$2,$3,$4,$5,$6,$7) "
            "ON CONFLICT (org_id, provider, external_id) DO UPDATE SET "
            "access_token_enc=EXCLUDED.access_token_enc, display_name=EXCLUDED.display_name, "
            "token_expires_at=EXCLUDED.token_expires_at, scopes=EXCLUDED.scopes, status='active', updated_at=now() "
            f"RETURNING {_COLS}",
            uuid.UUID(org_id), provider, external_id, display_name, enc, token_expires_at, scopes)
    return _conn(r)


async def list_connections(org_id: str) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(f"SELECT {_COLS} FROM connections ORDER BY created_at DESC")
    return [_conn(r) for r in rows]


async def get_connection(org_id: str, connection_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_COLS} FROM connections WHERE id=$1", uuid.UUID(connection_id))
    return _conn(r) if r else None


async def get_token(org_id: str, connection_id: str) -> str | None:
    """Decrypt + return the access token. The ONLY path that exposes plaintext — callers use it
    transiently for a Graph call and never persist/log it. Rebuilds the row-bound AAD so a swapped
    ciphertext fails to decrypt."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT access_token_enc, provider, external_id FROM connections WHERE id=$1",
            uuid.UUID(connection_id))
    if r is None or r["access_token_enc"] is None:
        return None
    return crypto.decrypt_token(r["access_token_enc"], _aad(org_id, r["provider"], r["external_id"]))


async def set_status(org_id: str, connection_id: str, status: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("UPDATE connections SET status=$1, updated_at=now() WHERE id=$2",
                              status, uuid.UUID(connection_id))
    return res.endswith(" 1")


async def delete_connection(org_id: str, connection_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM connections WHERE id=$1", uuid.UUID(connection_id))
    return res.endswith(" 1")
