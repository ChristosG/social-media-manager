from datetime import date as _date, datetime, time as _time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.security.context import require_identity
from app.repo import campaigns as camp, ledger as led, scheduled_posts as sp, connections as cr
from app.security.img_sign import image_url
from app.agent.lifecycle import lifecycle_for
from app.social.content_hash import content_hash
from app.agent import refine

router = APIRouter()


async def _enriched(org: str, c: dict) -> dict:
    """Attach each slot's drafted post (caption + signed images + planned time) and its lifecycle stage, plus
    a campaign-level progress summary — everything the detail view needs in one fetch."""
    counts = {"drafted": 0, "approved": 0, "scheduled": 0, "posted": 0, "failed": 0}
    for slot in c["slots"]:
        pid = slot.get("post_id")
        post = await led.get_post(org, pid) if pid else None
        if post:
            slot["post"] = {
                "id": post["id"], "caption": post["content"], "status": post["status"],
                "planned_at": post["planned_at"],
                "images": [{"id": i, "url": image_url(i, org)} for i in post["image_ids"]],
            }
            slot["lifecycle"] = lifecycle_for(post, await sp.latest_for_post(org, pid))
        else:
            slot["post"] = None
            slot["lifecycle"] = lifecycle_for(None, None)
        counts[slot["lifecycle"]["stage"]] = counts.get(slot["lifecycle"]["stage"], 0) + 1
    c["progress"] = {"total": len(c["slots"]), **{k: counts.get(k, 0) for k in
                     ("drafted", "approved", "scheduled", "posted", "failed")}}
    return c


@router.get("/campaigns")
async def list_(ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    return {"campaigns": await camp.list_campaigns(org)}


@router.get("/campaigns/{campaign_id}")
async def get_(campaign_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    c = await camp.get(org, campaign_id)
    if not c:
        raise HTTPException(404, "not found")
    return {"campaign": await _enriched(org, c)}


@router.post("/campaigns/{campaign_id}/approve")
async def approve(campaign_id: str, ident: tuple[str, str] = Depends(require_identity)):
    """Enqueue a DURABLE campaign_fill job and return immediately. The agent-worker drafts each slot under
    the approver's identity; the panel polls GET /campaigns/{id} for fill_status: 'filling' → 'done'|'error'.
    Unlike the old in-process BackgroundTask, a deploy/crash mid-fill no longer strands the campaign in
    'filling' forever — the job has a lease and is reaped + retried. Idempotent against double-click."""
    user_id, org = ident
    c = await camp.get(org, campaign_id)
    if not c:
        raise HTTPException(404, "campaign not found")
    pending = [s for s in c["slots"] if not s.get("post_id")]
    if not pending:
        return {"status": "done", "filled": 0, "total": 0, "message": "every post is already drafted"}
    job = await camp.begin_fill(org, campaign_id, user_id)
    return {"status": "filling", "total": len(pending), "job_id": (job or {}).get("id")}


async def _campaign_post_ids(org: str, campaign_id: str) -> tuple[dict, set[str]]:
    """Load a campaign (404 if gone) and the set of post ids attached to its slots — the authz boundary for
    per-post actions: a post may only be approved through the campaign it actually belongs to."""
    c = await camp.get(org, campaign_id)
    if not c:
        raise HTTPException(404, "campaign not found")
    return c, {s["post_id"] for s in c["slots"] if s.get("post_id")}


@router.post("/campaigns/{campaign_id}/posts/{post_id}/refine")
async def refine_post(campaign_id: str, post_id: str, body: dict,
                      ident: tuple[str, str] = Depends(require_identity)):
    """Return a refined-caption PROPOSAL for one campaign post (no write — the client shows a diff and
    commits via PUT /ledger/{id} on Apply). Authz: the post must belong to this campaign."""
    _, org = ident
    _, post_ids = await _campaign_post_ids(org, campaign_id)
    if post_id not in post_ids:
        raise HTTPException(404, "post is not part of this campaign")
    post = await led.get_post(org, post_id)
    if not post:
        raise HTTPException(404, "post not found")
    caption, chips = await refine.refine_caption(
        org, post["content"] or "", (body.get("intent") or "").strip(), post.get("platform"))
    if not caption:
        raise HTTPException(502, "couldn't refine — try again")
    return {"caption": caption, "suggestions": chips}


@router.post("/campaigns/{campaign_id}/posts/{post_id}/approve")
async def approve_post(campaign_id: str, post_id: str,
                       ident: tuple[str, str] = Depends(require_identity)):
    """Mark ONE drafted campaign post as approved — the review gate before it can be scheduled. Idempotent:
    re-approving (or approving an already-scheduled post) is a no-op success; a not-yet-drafted post is 409."""
    _, org = ident
    _, post_ids = await _campaign_post_ids(org, campaign_id)
    if post_id not in post_ids:
        raise HTTPException(404, "post is not part of this campaign")
    post = await led.get_post(org, post_id)
    if not post:
        raise HTTPException(404, "post not found")
    if post["status"] == "drafting":
        raise HTTPException(409, "this post hasn't finished drafting yet")
    if post["status"] == "drafted":
        await led.update_post(org, post_id, "approved", None, None)
    return {"ok": True, "status": "approved"}


@router.delete("/campaigns/{campaign_id}/slots/{slot_id}")
async def delete_slot(campaign_id: str, slot_id: str, ident: tuple[str, str] = Depends(require_identity)):
    """Remove one post from a campaign (the per-card trash button). Refuses an already-published post; for a
    scheduled one it cancels the pending publish first, then archives the post and drops the slot."""
    _, org = ident
    if not await camp.slot_in_campaign(org, campaign_id, slot_id):
        raise HTTPException(404, "slot is not part of this campaign")
    c = await camp.get(org, campaign_id)
    slot = next((s for s in (c["slots"] if c else []) if s["id"] == slot_id), None)
    pid = slot.get("post_id") if slot else None
    if pid:
        post = await led.get_post(org, pid)
        if post and post["status"] == "posted":
            raise HTTPException(409, "this post is already published — it can't be deleted here")
        spr = await sp.latest_for_post(org, pid)   # cancel a pending/scheduled publish so it doesn't fire
        if spr and spr.get("id"):
            try:
                await sp.cancel(org, spr["id"])
            except Exception:
                pass
        await led.update_post(org, pid, "archived", None, None)
    await camp.remove_slot(org, campaign_id, slot_id)
    return {"ok": True}


class CustomDraftBody(BaseModel):
    caption: str
    date: str | None = None   # YYYY-MM-DD; defaults to tomorrow
    time: str | None = None   # HH:MM; defaults to noon


@router.post("/campaigns/{campaign_id}/custom-draft")
async def custom_draft(campaign_id: str, body: CustomDraftBody,
                       ident: tuple[str, str] = Depends(require_identity)):
    """Add a draft the user TYPED themselves (not via chat) to a campaign — it lands as a normal drafted post
    so it then has every AI feature (image gen, refine chips). Creates the slot + ledger post + links them."""
    _, org = ident
    c = await camp.get(org, campaign_id)
    if not c:
        raise HTTPException(404, "not found")
    caption = (body.caption or "").strip()
    if not caption:
        raise HTTPException(422, "caption is required")
    d = _date.fromisoformat(body.date) if body.date else (_date.today() + timedelta(days=1))
    when = datetime.combine(d, _time.fromisoformat(body.time) if body.time else _time(hour=12)) \
        .replace(tzinfo=timezone.utc)
    platform = c["platform"] or "instagram"
    slot = await camp.add_slot(org, campaign_id, angle=caption[:120], slot_date=d, slot_at=when, platform=platform)
    p = await led.create_post(org, caption[:120], caption, status="drafted", origin="custom",
                              idea_key=f"camp-{slot['id']}")
    await led.update_post(org, p["id"], "drafted", caption, platform)
    await led.set_planned_at(org, p["id"], when)
    await camp.attach_post(org, slot["id"], p["id"])
    return {"ok": True, "slot_id": slot["id"], "post_id": p["id"]}


@router.post("/campaigns/{campaign_id}/approve-posts")
async def approve_all_posts(campaign_id: str, ident: tuple[str, str] = Depends(require_identity)):
    """Bulk-approve every drafted post in the campaign in one click. Skips posts still drafting or already
    past approval. Returns how many were newly approved."""
    _, org = ident
    c, post_ids = await _campaign_post_ids(org, campaign_id)
    approved = 0
    for pid in post_ids:
        post = await led.get_post(org, pid)
        if post and post["status"] == "drafted":
            if await led.update_post(org, pid, "approved", None, None):
                approved += 1
    return {"ok": True, "approved": approved}


@router.post("/campaigns/{campaign_id}/schedule-approved")
async def schedule_approved(campaign_id: str, ident: tuple[str, str] = Depends(require_identity)):
    """One-click: schedule every APPROVED post in the campaign at the date already on its card, to the org's
    connected account(s) for that platform. Best-effort — a post is SKIPPED (with a reason) when it has no
    connected account, is an Instagram post without an image, has a past/missing date, or already has an
    identical post queued. Each scheduled post then flows through the normal publish worker at its time."""
    user, org = ident
    c = await camp.get(org, campaign_id)
    if not c:
        raise HTTPException(404, "campaign not found")
    pub_by_provider: dict[str, list[str]] = {}
    for conn in await cr.list_connections(org):
        if cr.can_publish(conn):
            pub_by_provider.setdefault(conn["provider"], []).append(conn["id"])

    now = datetime.now(timezone.utc)
    scheduled, skipped = [], []
    for slot in c["slots"]:
        pid = slot.get("post_id")
        if not pid:
            continue
        post = await led.get_post(org, pid)
        if not post or post["status"] != "approved":   # only approved posts are eligible (the F-C gate)
            continue
        platform = (post.get("platform") or slot.get("platform") or "").lower()
        conn_ids = pub_by_provider.get(platform, [])
        if not conn_ids:
            skipped.append({"post_id": pid, "reason": f"no connected {platform or 'social'} account"}); continue
        if platform == "instagram" and not post["image_ids"]:
            skipped.append({"post_id": pid, "reason": "Instagram needs an image"}); continue
        when = post["planned_at"] or slot.get("slot_at")
        try:
            when_dt = datetime.fromisoformat(when) if when else None
        except ValueError:
            when_dt = None
        if when_dt is None:
            skipped.append({"post_id": pid, "reason": "no valid date set"}); continue
        if when_dt.tzinfo is None:
            when_dt = when_dt.replace(tzinfo=timezone.utc)
        if when_dt <= now:
            skipped.append({"post_id": pid, "reason": "the date is in the past — reschedule it"}); continue
        chash = content_hash(post["content"] or "", post["image_ids"])
        if await sp.exists_active_or_published(org, chash, platform):
            skipped.append({"post_id": pid, "reason": "already scheduled"}); continue
        targets = [{"provider": platform, "connection_id": cid} for cid in conn_ids]
        row = await sp.create(org, targets=targets, caption=post["content"] or "", image_ids=post["image_ids"],
                              content_hash=chash, scheduled_at_now=False, created_by=user,
                              post_id=pid, scheduled_at=when_dt.isoformat())
        scheduled.append({"post_id": pid, "scheduled_at": row["scheduled_at"]})
    return {"scheduled": len(scheduled), "skipped": skipped, "items": scheduled}


@router.delete("/campaigns/{campaign_id}")
async def remove(campaign_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org = ident
    if not await camp.set_status(org, campaign_id, "archived"):
        raise HTTPException(404, "not found")
    return {"ok": True}
