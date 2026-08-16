from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import profile as repo


router = APIRouter()


class ProfileIn(BaseModel):
    name: str | None = None
    mission: str | None = None
    one_liner: str | None = None
    audience: str | None = None
    regions: list[str] | None = None
    default_platform: str | None = None


class ProgramIn(BaseModel):
    name: str
    description: str | None = None
    source_url: str | None = None


class ProgramPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    source_url: str | None = None


@router.get("/profile")
async def get(ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"profile": await repo.get_profile(org_id)}


@router.put("/profile")
async def put(body: ProfileIn, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"profile": await repo.upsert_profile(org_id, body.mission, body.one_liner, body.audience,
                                                 body.regions, body.default_platform, body.name)}


@router.get("/programs")
async def list_programs(ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"programs": await repo.list_programs(org_id)}


@router.post("/programs")
async def create_program(body: ProgramIn, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    return {"program": await repo.create_program(org_id, body.name, body.description, body.source_url)}


@router.put("/programs/{program_id}")
async def update_program(program_id: str, body: ProgramPatch, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if not await repo.update_program(org_id, program_id, body.name, body.description, body.source_url):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.delete("/programs/{program_id}")
async def delete_program(program_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    if not await repo.delete_program(org_id, program_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}
