import uuid
from datetime import datetime
from app.db.pool import org_tx

# Single settings row per org. Created lazily on first read (defaults) / first write (upsert).


async def get(org_id: str) -> dict:
    """Return the org's settings, with defaults if no row exists yet."""
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT auto_reply_safe, comments_polled_at, utm_tagging FROM org_settings WHERE org_id=$1",
            uuid.UUID(org_id))
    if r is None:
        return {"auto_reply_safe": False, "comments_polled_at": None, "utm_tagging": False}
    return {
        "auto_reply_safe": r["auto_reply_safe"],
        "comments_polled_at": r["comments_polled_at"].isoformat() if r["comments_polled_at"] else None,
        "utm_tagging": r["utm_tagging"],
    }


async def set_auto_reply_safe(org_id: str, enabled: bool) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO org_settings(org_id, auto_reply_safe) VALUES($1,$2) "
            "ON CONFLICT (org_id) DO UPDATE SET auto_reply_safe=EXCLUDED.auto_reply_safe, updated_at=now()",
            uuid.UUID(org_id), enabled)


async def set_utm_tagging(org_id: str, enabled: bool) -> None:
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO org_settings(org_id, utm_tagging) VALUES($1,$2) "
            "ON CONFLICT (org_id) DO UPDATE SET utm_tagging=EXCLUDED.utm_tagging, updated_at=now()",
            uuid.UUID(org_id), enabled)


async def utm_tagging(org_id: str) -> bool:
    """Whether the org opted in to UTM-tagging outbound links on publish (default False)."""
    async with org_tx(org_id) as c:
        v = await c.fetchval("SELECT utm_tagging FROM org_settings WHERE org_id=$1", uuid.UUID(org_id))
    return bool(v)


async def touch_comments_polled(org_id: str) -> None:
    """Record that comments were just polled (drives the ingest throttle)."""
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO org_settings(org_id, comments_polled_at) VALUES($1, now()) "
            "ON CONFLICT (org_id) DO UPDATE SET comments_polled_at=now(), updated_at=now()",
            uuid.UUID(org_id))


async def comments_polled_at(org_id: str) -> datetime | None:
    async with org_tx(org_id) as c:
        return await c.fetchval(
            "SELECT comments_polled_at FROM org_settings WHERE org_id=$1", uuid.UUID(org_id))


async def touch_insights_refreshed(org_id: str) -> None:
    """Record that insights were just refreshed (drives the refresh throttle)."""
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO org_settings(org_id, insights_refreshed_at) VALUES($1, now()) "
            "ON CONFLICT (org_id) DO UPDATE SET insights_refreshed_at=now(), updated_at=now()",
            uuid.UUID(org_id))


async def insights_refreshed_at(org_id: str) -> datetime | None:
    async with org_tx(org_id) as c:
        return await c.fetchval(
            "SELECT insights_refreshed_at FROM org_settings WHERE org_id=$1", uuid.UUID(org_id))
