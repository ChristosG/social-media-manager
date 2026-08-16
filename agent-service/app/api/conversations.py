from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import conversations as repo

router = APIRouter()


class CreateConv(BaseModel):
    title: str = "New conversation"
    model: str | None = None


class UpdateConv(BaseModel):
    title: str | None = None
    model: str | None = None
    system_prompt: str | None = None


def _conv_response(row: dict, model: str | None = None, system_prompt: str | None = None) -> dict:
    """Wrap a repo conversation row into the API shape (model/system_prompt not stored in DB)."""
    return {
        "id": row["id"],
        "title": row["title"],
        "model": model,
        "system_prompt": system_prompt,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.post("/conversations")
async def create(body: CreateConv, ident: tuple[str, str] = Depends(require_identity)):
    user_id, org_id = ident
    row = await repo.create_conversation(org_id, user_id, body.title)
    return {"conversation": _conv_response(row, model=body.model)}


@router.get("/conversations")
async def list_(ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    rows = await repo.list_conversations(org_id)
    return {"conversations": rows, "total": len(rows)}


@router.get("/conversations/{conv_id}")
async def get(conv_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    conv = await repo.get_conversation(org_id, conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = await repo.get_messages(org_id, conv_id)
    # Campaign/post binding ("Edit in chat" / "Refine in chat"). Surfaced so the client can keep a persistent
    # "Apply to post" affordance for the bound post and tell when there are unapplied caption changes (by
    # comparing the conversation draft against the post's current caption).
    binding = await repo.get_binding(org_id, conv_id) or {}
    active_post_id = binding.get("active_post_id")
    active_post_caption = None
    if active_post_id:
        from app.repo import ledger as _led
        bound_post = await _led.get_post(org_id, active_post_id)
        if bound_post:
            active_post_caption = bound_post.get("content")
        else:
            active_post_id = None  # post was removed — drop the stale binding from the response
    return {
        "conversation": _conv_response(conv),
        "messages": messages,
        "active_post_id": active_post_id,
        "active_campaign_id": binding.get("active_campaign_id"),
        "active_post_caption": active_post_caption,
    }


@router.put("/conversations/{conv_id}")
async def update(
    conv_id: str,
    body: UpdateConv,
    ident: tuple[str, str] = Depends(require_identity),
):
    _, org_id = ident
    # We need at least a title to update; if none given, fetch current title first
    if body.title is not None:
        title = body.title
    else:
        existing = await repo.get_conversation(org_id, conv_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        title = existing["title"]

    row = await repo.update_conversation(org_id, conv_id, title)
    if row is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation": _conv_response(row, model=body.model, system_prompt=body.system_prompt)}


@router.delete("/conversations/{conv_id}")
async def delete(conv_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    deleted = await repo.delete_conversation(org_id, conv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"message": "deleted"}


@router.get("/conversations/{conv_id}/draft")
async def get_draft(conv_id: str, ident: tuple[str, str] = Depends(require_identity)):
    from app.repo import conversation_drafts as drafts_repo
    from app.security.img_sign import image_url
    _, org = ident
    d = await drafts_repo.get_draft(org, conv_id)
    if not d:
        return {"draft": None}
    images = [{"id": i, "url": image_url(i, org)} for i in d["image_ids"]]
    return {"draft": {"caption": d["caption"], "images": images}}
