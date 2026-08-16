import json
import logging
from datetime import datetime, date, time, timezone, timedelta
from fastapi import APIRouter, Depends
from app.security.context import require_identity
from app.repo import scheduled_posts as sp, ledger as led, profile as profile_repo
from app.agent.campaign import dedup_angles

router = APIRouter()
logger = logging.getLogger(__name__)


def _model_for_proactive():
    from app.agent.tools import _m
    return _m()


async def _gaps(org: str, start: date, days: int = 7) -> list[str]:
    end = start + timedelta(days=days - 1)
    dt0 = datetime.combine(start, time.min, tzinfo=timezone.utc)
    dt1 = datetime.combine(end, time.max, tzinfo=timezone.utc)
    taken = set()
    for s in await sp.list_in_range(org, dt0, dt1):
        taken.add(s["scheduled_at"][:10])
    for p in await led.list_planned_in_range(org, start, end):
        taken.add(p["planned_for"][:10])
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        if d not in taken:
            out.append(d)
    return out


def _parse(content: str) -> list[dict]:
    try:
        arr = json.loads(content)
    except Exception:
        try:
            arr = json.loads(content[content.index("["):content.rindex("]") + 1])
        except Exception:
            return []
    out = []
    for x in arr if isinstance(arr, list) else []:
        if isinstance(x, dict) and x.get("title"):
            out.append({"title": str(x["title"]), "angle": str(x.get("angle", ""))})
    return out


@router.get("/proactive/this-week")
async def this_week(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    today = date.today()
    gaps = await _gaps(org, today, 7)
    suggestions: list[dict] = []
    try:
        profile = await profile_repo.get_profile(org)
        existing = [p["title"] for p in await led.list_posts(org)]
        mission = (profile or {}).get("mission") or ""
        prompt = (
            "You help a nonprofit plan timely social posts. Propose 3 fresh, distinct post ideas for the "
            f"coming week. Org mission: {mission}. Return ONLY a JSON array of objects "
            '{"title": "...", "angle": "..."} — short, specific, non-generic.')
        resp = await _model_for_proactive().ainvoke(prompt)
        ideas = _parse(getattr(resp, "content", "") or "")
        # dedup titles against the existing ledger
        kept_titles = dedup_angles([i["title"] for i in ideas], existing)
        suggestions = [i for i in ideas if i["title"] in kept_titles][:3]
    except Exception:
        logger.exception("proactive this-week: idea generation failed org=%s", org)
        suggestions = []
    return {"suggestions": suggestions, "gaps": gaps}
