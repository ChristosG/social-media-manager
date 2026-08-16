"""Studio → Prompts: view + edit the prompt templates that drive the assistant.

Reading is allowed for any org member; editing is admin-gated (it changes behaviour for the
whole org). Overrides are per-org rows (RLS), consumed on the next message.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.security.context import require_identity, require_admin
from app.repo import prompts as repo

router = APIRouter()


class PromptIn(BaseModel):
    template: str


@router.get("/prompts")
async def list_prompts(ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"prompts": await repo.list_effective(org_id)}


@router.put("/prompts/{key}")
async def set_prompt(key: str, body: PromptIn, ident: tuple[str, str] = Depends(require_admin)):
    _, org_id = ident
    if not body.template.strip():
        raise HTTPException(status_code=422, detail="template must not be empty")
    try:
        await repo.set_override(org_id, key, body.template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.delete("/prompts/{key}")
async def reset_prompt(key: str, ident: tuple[str, str] = Depends(require_admin)):
    """Revert to the built-in default."""
    _, org_id = ident
    await repo.reset_override(org_id, key)
    return {"ok": True}
