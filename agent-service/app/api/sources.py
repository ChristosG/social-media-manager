from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import sources as repo, documents as doc_repo
from app.sources import ingest

router = APIRouter()


class SourceIn(BaseModel):
    name: str
    url: str
    type: str = "auto"        # auto | single | section | rss
    latest_n: int = 15


@router.get("/sources")
async def list_(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    return {"sources": await repo.list_sources(org)}


@router.get("/sources/stats")
async def stats(ident: tuple[str, str] = Depends(require_identity)):
    """Per-source knowledge footprint (documents + chunks ingested) for the Knowledge tab."""
    _, org = ident
    return {"stats": await doc_repo.source_stats(org)}


@router.post("/sources")
async def create(body: SourceIn, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if body.type not in ("auto", "single", "section", "rss"):
        raise HTTPException(status_code=422, detail="invalid type")
    s = await repo.create_source(org, "web", body.name,
                                 {"url": body.url, "type": body.type, "latest_n": int(body.latest_n)})
    ingest.schedule_ingest(org, s["id"])   # ingest-on-add: background; status flips pending→ok when done
    return s


@router.post("/sources/{source_id}/refresh")
async def refresh(source_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if await repo.get_source(org, source_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    return await ingest.run_ingest(org, source_id)


@router.get("/sources/{source_id}/documents")
async def documents(source_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if await repo.get_source(org, source_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    return {"documents": await doc_repo.list_documents(org, source_id)}


@router.delete("/sources/{source_id}")
async def delete(source_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if not await repo.delete_source(org, source_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}
