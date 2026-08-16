from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import ledger as repo
from app.agent import image_gen


router = APIRouter()


class PostIn(BaseModel):
    title: str
    brief: str | None = None
    status: str = "suggested"


class PostPatch(BaseModel):
    status: str | None = None
    content: str | None = None
    platform: str | None = None


class ImagesIn(BaseModel):
    image_ids: list[str]


class GenIn(BaseModel):
    prompt: str | None = None


@router.get("/ledger")
async def list_(status: str | None = None, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"posts": await repo.list_posts(org_id, status)}


@router.post("/ledger")
async def create(body: PostIn, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if body.status not in repo.STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    return await repo.create_post(org_id, body.title, body.brief, body.status)


@router.put("/ledger/{post_id}")
async def update(post_id: str, body: PostPatch, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if body.status is not None and body.status not in repo.STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    if not await repo.update_post(org_id, post_id, body.status, body.content, body.platform):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.delete("/ledger/{post_id}")
async def delete(post_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if not await repo.delete_post(org_id, post_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.put("/ledger/{post_id}/images")
async def set_images(post_id: str, body: ImagesIn, ident: tuple[str, str] = Depends(require_identity)):
    """Replace a post's images (used to add an uploaded/generated image or remove one)."""
    _, org_id = ident
    if not await repo.set_images(org_id, post_id, body.image_ids):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.post("/ledger/{post_id}/undo")
async def undo(post_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    restored = await repo.undo_caption(org, post_id)
    if restored is None:
        raise HTTPException(409, "nothing to undo")
    return {"ok": True, "caption": restored}


@router.post("/ledger/{post_id}/images/generate")
async def generate_post_image(post_id: str, body: GenIn,
                              ident: tuple[str, str] = Depends(require_identity)):
    """Generate one image for a post from its caption (or an override prompt), append it, return {id,url}."""
    _, org_id = ident
    post = await repo.get_post(org_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="not found")
    try:
        img = await image_gen.generate_one(
            org_id, prompt=(body.prompt or post["title"] or ""),
            caption=(post["content"] or ""), platform=(post["platform"] or ""))
    except RuntimeError:
        raise HTTPException(status_code=502, detail="image generator unavailable")
    await repo.set_images(org_id, post_id, post["image_ids"] + [img["id"]])
    return img
