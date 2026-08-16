from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_admin
from app.config import get_settings
from app.agent.research import research_org

router = APIRouter()


class ResearchIn(BaseModel):
    website_url: str = ""
    org_name: str = ""


@router.post("/research")
async def research(body: ResearchIn, ident: tuple[str, str] = Depends(require_admin)):
    """Learn the org from its website + web search, and persist mission/audience/programs. Admin-gated."""
    _, org_id = ident
    name = (body.org_name or "this nonprofit").strip()
    if not body.website_url.strip() and not get_settings().tavily_api_key:
        raise HTTPException(status_code=422, detail="Add your website URL (or configure web search) to research from.")
    result = await research_org(org_id, name, body.website_url.strip())
    if result is None:
        raise HTTPException(status_code=422, detail="Couldn't gather any information — check the website URL and try again.")
    return result
