from fastapi import APIRouter, Depends

from app.security.context import require_identity
from app.repo import notifications as nr

router = APIRouter()


@router.get("/notifications")
async def list_notifications(ident: tuple[str, str] = Depends(require_identity)):
    user, org = ident
    return {
        "items": await nr.list_for(org, user, limit=50),
        "unread_count": await nr.unread_count(org, user),
    }


@router.post("/notifications/read-all")
async def read_all(ident: tuple[str, str] = Depends(require_identity)):
    user, org = ident
    await nr.mark_all(org, user)
    return {"ok": True}


@router.post("/notifications/{nid}/read")
async def read_one(nid: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    await nr.mark_read(org, nid)
    return {"ok": True}
