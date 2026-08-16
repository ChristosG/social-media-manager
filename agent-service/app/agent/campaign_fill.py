"""Approve & fill a campaign: draft a ledger post for each slot and place it on the calendar at the slot's
date+time. Robust + observable: per-slot failures are RECORDED (not silently swallowed) and surfaced via a
structured result + the campaign's fill_status, so the panel can show real progress/errors instead of a
blanket toast. Runs in the background (the approve endpoint returns immediately) so it can never trip the
proxy/gateway timeout the way the old synchronous fill did. Each drafted post still flows through the normal
publish gate before going live; filling only drafts onto the calendar."""
import asyncio
import logging
from datetime import date, datetime, time, timezone
from app.config import get_settings
from app.repo import campaigns as camp, ledger as led, profile as profile_repo, memory as mem_repo
from app.repo import insights as insights_repo
from app.agent import tools as _tools           # reuse _gen_model / _draft_directives / build_draft_prompt path
from app.agent.drafting import (build_draft_prompt, CHIPS_SUFFIX, split_caption_chips,
                                pillar_suffix, split_pillar, DEFAULT_PILLARS)
from app.agent.platforms import PLATFORMS

logger = logging.getLogger(__name__)


def _slot_when(slot: dict) -> datetime:
    """The slot's scheduled moment as a tz-aware datetime: its explicit slot_at if set, else the slot_date at
    local noon. This is what lands on the calendar (planned_at), so same-day slots keep their distinct times."""
    if slot.get("slot_at"):
        dt = datetime.fromisoformat(slot["slot_at"])
    else:
        dt = datetime.combine(date.fromisoformat(slot["slot_date"]), time(hour=12))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _draft_one(org: str, angle: str, platform: str,
                     profile: dict | None) -> tuple[str, list[str], str | None]:
    voice, banned, rules, ctas = await _tools._draft_directives(org)
    pcfg = PLATFORMS.get((platform or "").lower(), {})
    mission = (profile or {}).get("mission")
    programs = await profile_repo.list_programs(org)
    pillars = await mem_repo.org_pillars(org)          # [] → pillar_suffix/parse fall back to DEFAULT_PILLARS
    exemplars = await insights_repo.top_exemplars(org)  # [] until >=6 measured posts (small-N guard)
    prompt = build_draft_prompt(
        angle, angle, pcfg, voice, banned, mission,
        rules=rules, ctas=ctas, programs=programs, org_name=(profile or {}).get("name"),
        exemplars=exemplars,
    ) + CHIPS_SUFFIX + pillar_suffix(pillars)
    resp = await _tools._gen_model(pcfg).ainvoke(prompt)
    raw = (getattr(resp, "content", "") or "").strip()
    # Strip the PILLAR line FIRST so it never leaks into chip parsing, then split off the CHIPS line.
    caption_chips_raw, pillar = split_pillar(raw, pillars or DEFAULT_PILLARS)
    caption, chips = split_caption_chips(caption_chips_raw)
    return caption, chips, pillar


async def fill_campaign(org_id: str, campaign_id: str) -> dict:
    """Draft every not-yet-filled slot. Returns {filled, failed, errors:[{slot_id,message}], total}.
    Sets campaign.fill_status to 'filling' → 'done'/'error' and status → 'approved'."""
    c = await camp.get(org_id, campaign_id)
    if not c:
        return {"filled": 0, "failed": 0, "errors": [], "total": 0, "error": "not found"}
    await camp.set_fill_status(org_id, campaign_id, "filling", None)
    try:
        profile = await profile_repo.get_profile(org_id)
    except Exception as e:  # don't let a profile-load blip 500 the whole approve
        logger.exception("campaign fill: profile load failed org=%s", org_id)
        await camp.set_fill_status(org_id, campaign_id, "error", f"couldn't load your org profile: {e}")
        return {"filled": 0, "failed": 0, "total": 0,
                "errors": [{"slot_id": None, "message": f"couldn't load your org profile: {e}"}],
                "error": "profile"}

    pending = [s for s in c["slots"] if not s.get("post_id")]
    # Draft slots CONCURRENTLY (vLLM batches them with ~no per-request latency penalty), bounded by a
    # semaphore so a large campaign doesn't flood the GPU. The slow part — the LLM call — is what we hold
    # the slot under; the quick DB writes run freely (pool-bounded). Each slot is independent + idempotent.
    sem = asyncio.Semaphore(max(1, get_settings().draft_concurrency))

    async def _fill_slot(slot) -> dict | None:
        try:
            async with sem:
                content, chips, pillar = await _draft_one(org_id, slot["angle"], slot["platform"], profile)
            if not content:
                return {"slot_id": slot["id"], "message": "the writer returned an empty caption"}
            # idea_group is unique per slot so campaign posts never dedup against each other or suggestions.
            p = await led.create_post(org_id, slot["angle"][:120], slot["angle"], status="drafting",
                                      idea_key=f"camp-{slot['id']}", dedup=True)
            await led.update_post(org_id, p["id"], "drafted", content, slot["platform"],
                                  suggestions=chips, pillar=pillar)
            await led.set_planned_at(org_id, p["id"], _slot_when(slot))
            await camp.attach_post(org_id, slot["id"], p["id"])
            return None
        except Exception as e:
            logger.exception("campaign fill: slot failed org=%s slot=%s", org_id, slot.get("id"))
            return {"slot_id": slot.get("id"), "message": str(e) or e.__class__.__name__}

    errors = [r for r in await asyncio.gather(*[_fill_slot(s) for s in pending]) if r]
    filled = len(pending) - len(errors)

    try:
        await camp.set_status(org_id, campaign_id, "approved")
    except Exception:
        logger.exception("campaign fill: set_status('approved') failed org=%s", org_id)

    # 'error' only when there was work to do and NONE of it succeeded; otherwise 'done' (partial is still done).
    if pending and filled == 0:
        await camp.set_fill_status(org_id, campaign_id, "error",
                                   errors[0]["message"] if errors else "nothing could be drafted")
    else:
        await camp.set_fill_status(org_id, campaign_id, "done", None)
    return {"filled": filled, "failed": len(errors), "errors": errors, "total": len(pending)}
