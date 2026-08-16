import hmac
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from app.security.context import require_identity
from app.social import oauth
from app.repo import connections as conn_repo, sources as sources_repo, jobs as jobs_repo
from app.sources import ingest

router = APIRouter()


async def _enqueue_import(org: str, connection_id: str) -> None:
    """Queue a one-off import of this connection's real posts (+ metrics) into the ledger, so Insights reflect
    the account from the moment it connects. Best-effort — a queue hiccup must never fail the OAuth callback."""
    try:
        await jobs_repo.enqueue(org, "import_posts", payload={"connection_id": connection_id},
                                dedup_key=f"import-{connection_id}")
    except Exception:
        pass


async def ensure_source_and_ingest(org: str, conn: dict) -> dict:
    """Idempotently bind a source to a connection and (re)ingest its posts. Keyed on connection_id
    (create_connection upserts, so reconnect reuses the same id) — first connect creates + ingests,
    reconnect just refreshes. The single seam used by both the OAuth callback and add_source."""
    src = await sources_repo.get_source_by_connection(org, conn["id"])
    if src is None:
        src = await sources_repo.create_source(
            org, conn["provider"], conn["display_name"] or conn["provider"], {},
            connection_id=conn["id"])
    ingest.schedule_ingest(org, src["id"])   # fire-and-forget; single-flight guards overlap
    return src


@router.get("/social/connect/{provider}")
async def connect(provider: str, response: Response, popup: int = 0,
                  ident: tuple[str, str] = Depends(require_identity)):
    user, org = ident
    if provider not in ("facebook", "instagram"):
        raise HTTPException(status_code=422, detail="invalid provider")
    if not oauth.get_settings().meta_app_id:
        raise HTTPException(status_code=503, detail="META_APP_ID not configured — see docs/meta-social-setup.md")
    state = oauth.sign_state(org, user, popup=bool(popup))
    # Bind the flow to THIS browser session: the callback must echo this nonce as a cookie, so a state
    # issued for one org cannot be completed in a victim's browser (OAuth CSRF / cross-account capture).
    response.set_cookie("social_oauth_nonce", oauth.state_nonce(state) or "", max_age=oauth._STATE_TTL,
                        httponly=True, secure=True, samesite="lax", path="/")
    return {"authorize_url": oauth.authorize_url(provider, state)}


# Meta's redirect is a full-page browser navigation (no app auth), so we can't return JSON — we bounce
# back into the SPA with the outcome. We carry it BOTH ways: a query string (handled immediately by the
# Studio page when the session survives the reload) AND a short-lived, non-HttpOnly cookie (read by the
# app after auth restores, so the toast still fires even if the user is bounced through re-login —
# access tokens are in-memory, so a full reload without "Remember me" logs the browser out).
def _popup_html(result: str, params: str) -> str:
    """Minimal page for the popup reconnect flow: signal the opener (same-origin) and close. Falls back
    to a full-page redirect if there's no opener (e.g. the flow wasn't actually opened in a popup)."""
    r = json.dumps(result).replace("</", "<\\/")
    redirect = json.dumps(f"/studio?{params}").replace("</", "<\\/")
    return (
        "<!doctype html><meta charset='utf-8'><title>Reconnecting</title><script>"
        "(function(){var r=" + r + ";"
        "try{if(window.opener){window.opener.postMessage({type:'social_result',result:r},"
        "window.location.origin);window.close();return;}}catch(e){}"
        "location.replace(" + redirect + ");})();"
        "</script>Reconnecting…"
    )


def _popup_from_state(state: str) -> bool:
    """Best-effort read of the popup flag from the (signed) state, used to pick the response shape even
    on the early error branches. False on any verification failure."""
    p = oauth.verify_state(state, None)
    return bool(p and p.get("p"))


def _back(params: str, result: str, popup: bool = False) -> Response:
    if popup:
        resp: Response = HTMLResponse(_popup_html(result, params))
    else:
        resp = RedirectResponse(url=f"/studio?{params}", status_code=303)
    resp.delete_cookie("social_oauth_nonce", path="/")   # one-time: consume the session binding
    resp.set_cookie("social_result", result, max_age=300, secure=True, samesite="lax", path="/")
    return resp


@router.get("/social/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    # Browser redirect from Meta — NO app auth. Identity is in the SIGNED state, AND the state must match
    # the per-session cookie set when the flow began (binds the callback to the initiating browser).
    popup = _popup_from_state(state)
    if error:   # user hit "Cancel" / denied permissions at Meta
        return _back("social=error&reason=denied", "error:denied", popup)
    payload = oauth.verify_state(state, None)
    cookie_nonce = request.cookies.get("social_oauth_nonce")
    if (not payload or not code or not cookie_nonce
            or not hmac.compare_digest(cookie_nonce, str(payload.get("n", "")))):
        return _back("social=error&reason=invalid", "error:invalid", popup)
    org = payload["o"]
    try:
        token = await oauth.exchange_code(code)
        scopes = await oauth.granted_scopes(token)
        pages = await oauth.list_pages(token)
    except Exception:
        return _back("social=error&reason=meta", "error:meta", popup)
    n = 0
    try:
        for p in pages:
            page_tok = p.get("access_token") or token
            fb_conn = await conn_repo.create_connection(org, "facebook", p["id"], p.get("name"),
                                                        token=page_tok, scopes=scopes)
            await ensure_source_and_ingest(org, fb_conn)
            await _enqueue_import(org, fb_conn["id"])
            n += 1
            iga = p.get("instagram_business_account")
            if iga and iga.get("id"):
                ig_conn = await conn_repo.create_connection(org, "instagram", iga["id"],
                                                           iga.get("username") or p.get("name"),
                                                           token=page_tok, scopes=scopes)
                await ensure_source_and_ingest(org, ig_conn)
                await _enqueue_import(org, ig_conn["id"])
                n += 1
    except Exception:
        return _back("social=error&reason=save", "error:save", popup)
    return _back(f"social=connected&linked={n}", f"connected:{n}", popup)


@router.get("/social/connections")
async def connections(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    return {"connections": await conn_repo.list_connections(org)}


class RefreshBody(BaseModel):
    provider: str | None = None
    force: bool = False


@router.post("/social/refresh")
async def refresh_social(body: RefreshBody, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if body.provider and body.provider not in ("facebook", "instagram"):
        raise HTTPException(status_code=422, detail="invalid provider")
    return await ingest.refresh_org_social(org, body.provider, body.force)


@router.post("/social/connections/{connection_id}/sources")
async def add_source(connection_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    conn = await conn_repo.get_connection(org, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    return await ensure_source_and_ingest(org, conn)


@router.delete("/social/connections/{connection_id}")
async def disconnect(connection_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if not await conn_repo.get_connection(org, connection_id):
        raise HTTPException(status_code=404, detail="not found")
    # Delete the connection's source(s) first so their documents cascade away — otherwise a later
    # reconnect orphans them and the new source can't re-ingest (deduped by (org,url)).
    await sources_repo.delete_sources_by_connection(org, connection_id)
    await conn_repo.delete_connection(org, connection_id)
    return {"ok": True}


@router.get("/social/posts")
async def social_posts(provider: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if provider not in ("facebook", "instagram"):
        raise HTTPException(status_code=422, detail="invalid provider")
    from app.repo import documents as docs_repo
    return {"posts": await docs_repo.list_social_posts(org, provider)}
