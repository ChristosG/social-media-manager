import uuid
from app.db.pool import org_tx
from app.repo import jobs


def _slot(r) -> dict:
    return {
        "id": str(r["id"]),
        "slot_date": r["slot_date"].isoformat(),
        "slot_at": r["slot_at"].isoformat() if r["slot_at"] else None,
        "angle": r["angle"],
        "platform": r["platform"],
        "post_id": str(r["post_id"]) if r["post_id"] else None,
        "position": r["position"],
    }


def _campaign(r, slots: list[dict]) -> dict:
    return {
        "id": str(r["id"]),
        "brief": r["brief"],
        "platform": r["platform"],
        "status": r["status"],
        "fill_status": r["fill_status"],
        "fill_error": r["fill_error"],
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
        "slots": slots,
    }


_CAMP_COLS = "id, brief, platform, status, fill_status, fill_error, created_at, updated_at"
_SLOT_COLS = "id, slot_date, slot_at, angle, platform, post_id, position"


async def _fetch_slots(conn, campaign_id: uuid.UUID) -> list[dict]:
    rows = await conn.fetch(
        f"SELECT {_SLOT_COLS} FROM campaign_slots WHERE campaign_id=$1 ORDER BY position",
        campaign_id,
    )
    return [_slot(r) for r in rows]


async def create(org_id: str, brief: str, platform: str | None, slots: list[dict]) -> dict:
    camp_id = uuid.uuid4()
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"INSERT INTO campaigns(id, org_id, brief, platform) VALUES($1,$2,$3,$4) "
            f"RETURNING {_CAMP_COLS}",
            camp_id, uuid.UUID(org_id), brief, platform,
        )
        for pos, slot in enumerate(slots):
            await c.execute(
                "INSERT INTO campaign_slots(org_id, campaign_id, slot_date, slot_at, angle, platform, position) "
                "VALUES($1,$2,$3,$4,$5,$6,$7)",
                uuid.UUID(org_id), camp_id,
                slot["slot_date"], slot.get("slot_at"),
                slot["angle"], slot.get("platform"), pos,
            )
        fetched_slots = await _fetch_slots(c, camp_id)
    return _campaign(r, fetched_slots)


async def get(org_id: str, campaign_id: str) -> dict | None:
    cid = uuid.UUID(campaign_id)
    async with org_tx(org_id) as c:
        r = await c.fetchrow(f"SELECT {_CAMP_COLS} FROM campaigns WHERE id=$1", cid)
        if r is None:
            return None
        slots = await _fetch_slots(c, cid)
    return _campaign(r, slots)


async def list_campaigns(org_id: str) -> list[dict]:
    async with org_tx(org_id) as c:
        rows = await c.fetch(f"SELECT {_CAMP_COLS} FROM campaigns ORDER BY created_at DESC")
        result = []
        for r in rows:
            slots = await _fetch_slots(c, r["id"])
            result.append(_campaign(r, slots))
    return result


async def latest_proposed(org_id: str) -> dict | None:
    """The org's most recently proposed (not-yet-approved) campaign — the one chat 'approve'/'edit' acts on."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            f"SELECT {_CAMP_COLS} FROM campaigns WHERE status='proposed' ORDER BY created_at DESC LIMIT 1")
        if r is None:
            return None
        slots = await _fetch_slots(c, r["id"])
    return _campaign(r, slots)


async def archive_other_proposed(org_id: str, keep_id: str) -> int:
    """Keep a single active proposal: archive every OTHER 'proposed' campaign. Stops the duplicate pileup
    where each re-plan left a new proposed campaign behind."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE campaigns SET status='archived', updated_at=now() "
            "WHERE status='proposed' AND id <> $1", uuid.UUID(keep_id))
    try:
        return int(res.split()[-1])
    except Exception:
        return 0


async def update_brief(org_id: str, campaign_id: str, brief: str) -> bool:
    """Rewrite a campaign's brief/description — used when the user changes its scope ('make it 3 weeks')
    so the saved description reflects the new shape instead of the stale original."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE campaigns SET brief=$1, updated_at=now() WHERE id=$2",
            brief, uuid.UUID(campaign_id),
        )
    return res.endswith(" 1")


async def set_status(org_id: str, campaign_id: str, status: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE campaigns SET status=$1, updated_at=now() WHERE id=$2",
            status, uuid.UUID(campaign_id),
        )
    return res.endswith(" 1")


async def set_fill_status(org_id: str, campaign_id: str, fill_status: str | None,
                          fill_error: str | None = None) -> bool:
    """Track background fill progress so the panel can poll: 'filling' | 'done' | 'error'."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE campaigns SET fill_status=$1, fill_error=$2, updated_at=now() WHERE id=$3",
            fill_status, fill_error, uuid.UUID(campaign_id),
        )
    return res.endswith(" 1")


async def try_begin_fill(org_id: str, campaign_id: str) -> bool:
    """Atomically claim the right to draft this campaign: flip fill_status to 'filling' ONLY if it isn't
    already. Returns True iff THIS caller won the claim — so two near-simultaneous approves (double-click,
    two tabs) can never both spawn a fill. Mirrors the publish worker's claim() pattern."""
    async with org_tx(org_id) as c:
        row = await c.fetchrow(
            "UPDATE campaigns SET fill_status='filling', fill_error=NULL, updated_at=now() "
            "WHERE id=$1 AND fill_status IS DISTINCT FROM 'filling' RETURNING id",
            uuid.UUID(campaign_id),
        )
    return row is not None


async def begin_fill(org_id: str, campaign_id: str, user_id: str) -> dict | None:
    """Mark the campaign 'filling' AND enqueue the durable campaign_fill job in ONE transaction. The job
    (deduped per campaign on live state) is the source of truth, so this converges correctly for: a
    double-click / two tabs (a single live job), and a leftover 'filling' from a process that died mid-fill
    before the queue existed (a fresh job is enqueued and the reaper/worker drains it). Returns the job row
    (the new one, or the existing live one)."""
    async with org_tx(org_id) as c:
        await c.execute(
            "UPDATE campaigns SET fill_status='filling', fill_error=NULL, updated_at=now() WHERE id=$1",
            uuid.UUID(campaign_id),
        )
        return await jobs.enqueue(
            org_id, "campaign_fill",
            payload={"campaign_id": campaign_id, "user_id": user_id},
            dedup_key=f"campaign_{campaign_id}", conn=c,
        )


async def update_slot(org_id: str, slot_id: str, angle: str | None = None,
                      slot_date=None, slot_at=None) -> bool:
    """Edit a slot in place (angle / date / time) — used by the campaign-edit flow so 'change the dates'
    mutates the existing campaign instead of creating a duplicate."""
    sets, args, i = [], [], 1
    if angle is not None:
        sets.append(f"angle=${i}"); args.append(angle); i += 1
    if slot_date is not None:
        sets.append(f"slot_date=${i}"); args.append(slot_date); i += 1
    if slot_at is not None:
        sets.append(f"slot_at=${i}"); args.append(slot_at); i += 1
    if not sets:
        return False
    args.append(uuid.UUID(slot_id))
    async with org_tx(org_id) as c:
        res = await c.execute(f"UPDATE campaign_slots SET {','.join(sets)} WHERE id=${i}", *args)
    return res.endswith(" 1")


async def attach_post(org_id: str, slot_id: str, post_id: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute(
            "UPDATE campaign_slots SET post_id=$1 WHERE id=$2",
            uuid.UUID(post_id), uuid.UUID(slot_id),
        )
    return res.endswith(" 1")


async def slot_in_campaign(org_id: str, campaign_id: str, slot_id: str) -> bool:
    """Authz: True iff slot_id is a slot of campaign_id (within this org). The campaign-edit tools call this
    before mutating a slot, so the agent can't touch a slot outside the bound campaign."""
    async with org_tx(org_id) as c:
        r = await c.fetchval(
            "SELECT 1 FROM campaign_slots WHERE id=$1 AND campaign_id=$2",
            uuid.UUID(slot_id), uuid.UUID(campaign_id))
    return r == 1


async def add_slot(org_id: str, campaign_id: str, angle: str, slot_date, slot_at,
                   platform: str | None) -> dict:
    """Append a new slot to a campaign at the next position. Returns the new slot dict."""
    cid = uuid.UUID(campaign_id)
    async with org_tx(org_id) as c:
        pos = await c.fetchval(
            "SELECT COALESCE(MAX(position)+1, 0) FROM campaign_slots WHERE campaign_id=$1", cid)
        r = await c.fetchrow(
            "INSERT INTO campaign_slots(org_id, campaign_id, slot_date, slot_at, angle, platform, position) "
            f"VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING {_SLOT_COLS}",
            uuid.UUID(org_id), cid, slot_date, slot_at, angle, platform, pos)
    return _slot(r)


async def remove_slot(org_id: str, campaign_id: str, slot_id: str) -> bool:
    """Delete a slot from a campaign (campaign-scoped). The attached ledger post (if any) is NOT hard-
    deleted here — callers archive it separately so a scheduled/posted post is never silently dropped."""
    async with org_tx(org_id) as c:
        res = await c.execute(
            "DELETE FROM campaign_slots WHERE id=$1 AND campaign_id=$2",
            uuid.UUID(slot_id), uuid.UUID(campaign_id))
    return res.endswith(" 1")


async def campaign_ids_for_posts(org_id: str, post_ids: list[str]) -> dict[str, str]:
    """Map each given post_id → the campaign_id it's attached to (via campaign_slots). Posts not attached
    to any campaign are simply absent from the result. Used to light up inline refine on the calendar."""
    if not post_ids:
        return {}
    async with org_tx(org_id) as c:
        rows = await c.fetch(
            "SELECT post_id, campaign_id FROM campaign_slots WHERE post_id = ANY($1::uuid[])",
            [uuid.UUID(p) for p in post_ids])
    return {str(r["post_id"]): str(r["campaign_id"]) for r in rows}
