from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import memory as repo

router = APIRouter()


class MemoryIn(BaseModel):
    kind: str
    value: dict
    key: str | None = None
    source: str = "manual"


class MemoryPatch(BaseModel):
    value: dict | None = None
    active: bool | None = None


@router.get("/memory")
async def list_(kind: str | None = None, include_pending: bool = False,
                ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"entries": await repo.list_entries(org_id, kind, include_pending=include_pending)}


@router.get("/memory/pending")
async def list_pending(ident: tuple[str, str] = Depends(require_identity)):
    """Durable memory the assistant learned while reading untrusted external sources, awaiting approval."""
    _, org_id = ident
    return {"entries": await repo.list_pending(org_id)}


@router.post("/memory/{entry_id}/approve")
async def approve(entry_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if not await repo.approve_entry(org_id, entry_id):
        raise HTTPException(status_code=404, detail="not found or already approved")
    return {"ok": True}


@router.post("/memory")
async def create(body: MemoryIn, ident: tuple[str, str] = Depends(require_identity)):
    user_id, org_id = ident
    try:
        return await repo.create_entry(org_id, body.kind, body.value, body.key, body.source, user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/memory/{entry_id}")
async def update(entry_id: str, body: MemoryPatch, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if not await repo.update_entry(org_id, entry_id, body.value, body.active):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.delete("/memory/{entry_id}")
async def delete(entry_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if not await repo.delete_entry(org_id, entry_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"message": "deleted"}
