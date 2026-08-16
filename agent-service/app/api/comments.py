from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import connections as cr, comments as comment_repo, org_settings as os_repo
from app.social import comments_connector as cc
from app.comments.ingest import ingest_org_comments
from app.security.img_sign import image_url

router = APIRouter()


class ReplyBody(BaseModel):
    text: str


class SettingsBody(BaseModel):
    auto_reply_safe: bool


async def _can_engage_any(org: str) -> bool:
    return any(cr.can_engage(c) for c in await cr.list_connections(org))


@router.get("/comments")
async def list_comments(status: str | None = None, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    items = await comment_repo.list_for(org, status=status)
    # Sign the parent-post thumbnail (HMAC, tenant-scoped) so the inbox can render it without exposing ids.
    for it in items:
        p = it.get("post")
        if p and p.get("image_ids"):
            p["image_url"] = image_url(p["image_ids"][0], org)
    return {"items": items, "can_engage": await _can_engage_any(org)}


@router.get("/comments/settings")
async def get_settings(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    s = await os_repo.get(org)
    return {"auto_reply_safe": s["auto_reply_safe"], "can_engage": await _can_engage_any(org)}


@router.put("/comments/settings")
async def put_settings(body: SettingsBody, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    await os_repo.set_auto_reply_safe(org, body.auto_reply_safe)
    result = None
    if body.auto_reply_safe:
        # Turning it ON should clear the existing simple-comment backlog immediately, not just affect
        # future comments — run a forced ingest pass (which now auto-posts safe open comments).
        result = await ingest_org_comments(org, force=True)
    return {"auto_reply_safe": body.auto_reply_safe, "result": result}


@router.post("/comments/poll")
async def poll(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    return await ingest_org_comments(org, force=True)


@router.post("/comments/{comment_id}/reply")
async def reply(comment_id: str, body: ReplyBody, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(422, "reply text is empty")
    c = await comment_repo.get(org, comment_id)
    if not c:
        raise HTTPException(404, "comment not found")
    if c["reply_external_id"]:
        raise HTTPException(409, "already replied")
    conn = await cr.get_connection(org, c["connection_id"])
    if not conn or not cr.can_engage(conn):
        raise HTTPException(422, f"{c['provider']} not authorized to reply — reconnect")
    token = await cr.get_token(org, c["connection_id"])
    if not token:
        raise HTTPException(422, "missing access token — reconnect")
    try:
        res = await cc.post_reply(c["provider"], c["external_id"], token, text)
    except cc.CommentError as e:
        raise HTTPException(502, f"reply failed: {e}")
    if not await comment_repo.mark_replied(org, comment_id, text, res["id"], "draft"):
        raise HTTPException(409, "already replied")   # lost the exactly-once race
    return await comment_repo.get(org, comment_id)


@router.post("/comments/{comment_id}/ignore")
async def ignore(comment_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if not await comment_repo.ignore(org, comment_id):
        raise HTTPException(409, "not ignorable (already replied or ignored)")
    return {"ok": True}
