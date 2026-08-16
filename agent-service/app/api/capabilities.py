from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity, require_admin
from app.repo import capabilities as repo

router = APIRouter()


class CapabilityIn(BaseModel):
    kind: str
    name: str
    config: dict = {}


class CapabilityPatch(BaseModel):
    config: dict | None = None
    enabled: bool | None = None
    name: str | None = None


@router.get("/capabilities")
async def list_(kind: str | None = None, effective: bool = False,
                ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    rows = await (repo.list_effective(org_id, kind) if effective else repo.list_all(org_id, kind))
    return {"capabilities": rows}


@router.post("/capabilities")
async def create(body: CapabilityIn, ident: tuple[str, str] = Depends(require_admin)):
    user_id, org_id = ident
    try:
        return await repo.create_capability(org_id, body.kind, body.name, body.config, user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/capabilities/{cap_id}")
async def update(cap_id: str, body: CapabilityPatch, ident: tuple[str, str] = Depends(require_admin)):
    _, org_id = ident
    if not await repo.update_capability(org_id, cap_id, body.config, body.enabled, body.name):
        raise HTTPException(status_code=404, detail="not found (globals are read-only; create an org override instead)")
    return {"ok": True}


@router.delete("/capabilities/{cap_id}")
async def delete(cap_id: str, ident: tuple[str, str] = Depends(require_admin)):
    _, org_id = ident
    if not await repo.delete_capability(org_id, cap_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"message": "deleted"}
