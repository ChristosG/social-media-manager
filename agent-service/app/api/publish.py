from datetime import datetime, date, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import connections as cr, scheduled_posts as sp, ledger as led
from app.repo import profile as profile_repo
from app.repo import campaigns as camp
from app.repo import insights as insights_repo
from app.repo import org_settings as os_repo
from app.social.content_hash import content_hash
from app.agent.besttime import suggested_slots
from app.agent.lifecycle import lifecycle_for

router = APIRouter()


def spr_to_post(s: dict | None) -> dict | None:
    """Shape a scheduled_posts row for lifecycle_for (it reads status/scheduled_at/updated_at/result)."""
    return None if s is None else {
        "status": s.get("status"), "scheduled_at": s.get("scheduled_at"),
        "updated_at": s.get("updated_at"), "result": s.get("result")}


class PublishBody(BaseModel):
    targets: list[str]
    caption: str = ""
    image_ids: list[str] = []
    scheduled_at: str | None = None
    post_id: str | None = None
    confirm: bool = False


async def run_one(org_id: str, sp_id: str) -> None:
    from app.social.publish_worker import run_one as _run
    await _run(org_id, sp_id)


@router.post("/social/publish")
async def publish(body: PublishBody, ident: tuple[str, str] = Depends(require_identity)):
    user, org = ident
    if not body.targets:
        raise HTTPException(422, "no targets selected")
    targets = []
    for cid in body.targets:
        conn = await cr.get_connection(org, cid)
        if not conn:
            raise HTTPException(404, f"connection {cid} not found")
        if not cr.can_publish(conn):
            raise HTTPException(422, f"{conn['provider']} not authorized to publish — reconnect")
        if conn["provider"] == "instagram" and not body.image_ids:
            raise HTTPException(422, "Instagram requires at least one image")
        targets.append({"provider": conn["provider"], "connection_id": cid})

    chash = content_hash(body.caption, body.image_ids)
    if not body.confirm:
        for t in targets:
            if await sp.exists_active_or_published(org, chash, t["provider"]):
                raise HTTPException(409, "duplicate")
    now = body.scheduled_at is None
    row = await sp.create(org, targets=targets, caption=body.caption, image_ids=body.image_ids,
                          content_hash=chash, scheduled_at_now=now, created_by=user,
                          post_id=body.post_id, scheduled_at=body.scheduled_at)
    if now:
        await run_one(org, row["id"])
        return await sp.get(org, row["id"])
    return {"status": "scheduled", "id": row["id"], "scheduled_at": row["scheduled_at"]}


@router.get("/social/scheduled")
async def list_scheduled(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    return {"items": await sp.list_recent(org)}


@router.delete("/social/scheduled/{sp_id}")
async def cancel(sp_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if not await sp.cancel(org, sp_id):
        raise HTTPException(409, "not cancelable (already in progress or done)")
    return {"ok": True}


class PlanBody(BaseModel):
    planned_for: str | None = None   # date (legacy / date-only)
    planned_at: str | None = None    # full ISO date+time (preferred when a time matters)


@router.get("/social/calendar")
async def calendar(frm: str, to: str, platform: str | None = None,
                   ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    d0, d1 = date.fromisoformat(frm), date.fromisoformat(to)
    dt0 = datetime.combine(d0, time.min, tzinfo=timezone.utc)
    dt1 = datetime.combine(d1, time.max, tzinfo=timezone.utc)
    sched = await sp.list_in_range(org, dt0, dt1)
    planned = await led.list_planned_in_range(org, d0, d1)
    sched_by_post = {s["post_id"]: s for s in sched if s.get("post_id")}
    by_post: dict[str, dict] = {}
    for p in planned:
        spr = sched_by_post.get(p["id"])
        life = lifecycle_for(p, spr_to_post(spr))
        by_post[p["id"]] = {
            "post_id": p["id"], "id": (spr or {}).get("id") or p["id"],
            "when": p["planned_at"] or p["planned_for"], "stage": life["stage"],
            "title": (p["content"] or p["title"] or "")[:80], "caption": p["content"],
            "platform": p["platform"], "image_ids": p["image_ids"],
            "targets": (spr or {}).get("targets"), "permalink": life["permalink"], "error": life["error"],
            "refine_suggestions": p["refine_suggestions"]}
    for s in sched:
        pid = s.get("post_id")
        if pid and pid in by_post:
            continue
        life = lifecycle_for({"status": "approved"}, spr_to_post(s))
        key = pid or s["id"]
        by_post[key] = {
            "post_id": pid, "id": s["id"], "when": s["scheduled_at"], "stage": life["stage"],
            "title": (s["caption"] or "")[:80], "caption": s["caption"],
            "targets": s["targets"], "permalink": life["permalink"], "error": life["error"]}
    camp_ids = await camp.campaign_ids_for_posts(org, [pid for pid in by_post if pid])
    for pid, it in by_post.items():
        it["campaign_id"] = camp_ids.get(it.get("post_id"))
        it.setdefault("refine_suggestions", [])
    items = list(by_post.values())
    prof = await profile_repo.get_profile(org)
    platform = platform or (prof or {}).get("default_platform") or "instagram"
    week_start = d0 - timedelta(days=d0.weekday())
    org_windows = await insights_repo.best_windows(org, platform)   # None until ~8 measured posts
    suggested = suggested_slots(platform, week_start, count=3, org_windows=org_windows)
    return {"items": items, "suggested": suggested,
            "suggested_basis": "your posts" if org_windows else "general"}


@router.patch("/social/scheduled/{sp_id}/reschedule")
async def reschedule(sp_id: str, body: dict, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    new_at = datetime.fromisoformat(body["when"])
    if new_at.tzinfo is None:
        new_at = new_at.replace(tzinfo=timezone.utc)
    if not await sp.reschedule(org, sp_id, new_at):
        raise HTTPException(409, "not reschedulable (already publishing/done)")
    return {"ok": True}


@router.put("/ledger/{post_id}/plan")
async def plan(post_id: str, body: PlanBody, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if body.planned_at:
        # Full date+time wins. Normalize to a tz-aware datetime (assume UTC if the client sent none).
        dt = datetime.fromisoformat(body.planned_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ok = await led.set_planned_at(org, post_id, dt)
    else:
        planned = date.fromisoformat(body.planned_for) if body.planned_for else None
        ok = await led.set_planned_for(org, post_id, planned)
    if not ok:
        raise HTTPException(404, "post not found")
    return {"ok": True}


class UtmBody(BaseModel):
    utm_tagging: bool


@router.get("/social/settings")
async def get_social_settings(ident: tuple[str, str] = Depends(require_identity)):
    """Publish-related org settings (currently the opt-in UTM link tagging)."""
    _, org = ident
    s = await os_repo.get(org)
    return {"utm_tagging": bool(s.get("utm_tagging"))}


@router.put("/social/settings")
async def set_social_settings(body: UtmBody, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    await os_repo.set_utm_tagging(org, body.utm_tagging)
    return {"utm_tagging": body.utm_tagging}
