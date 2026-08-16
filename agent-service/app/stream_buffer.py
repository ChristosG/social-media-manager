"""Redis-backed snapshot of an in-flight (or just-finished) assistant turn, so a client that reloads or
reconnects can resume the stream even after a process restart or past the in-memory grace window. Purely
additive: the live path and the in-process `_gens` resume are unchanged — this is only consulted when the
in-process generation is gone. Every call is best-effort; if Redis is down it no-ops and the app behaves
exactly as before.
"""
import json
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

_client = None
_TTL_SECONDS = 900   # keep a turn resumable for 15 min — far beyond the 90s in-memory grace


def _redis():
    global _client
    if _client is None:
        import redis.asyncio as aioredis
        _client = aioredis.from_url(get_settings().redis_url, encoding="utf-8", decode_responses=True)
    return _client


def _key(conv_id: str) -> str:
    return f"genstream:{conv_id}"


async def save(conv_id: str, snapshot: dict) -> None:
    """Persist (overwrite) the turn snapshot for a conversation. Best-effort."""
    try:
        await _redis().set(_key(conv_id), json.dumps(snapshot), ex=_TTL_SECONDS)
    except Exception:
        logger.debug("stream_buffer save failed (conv=%s)", conv_id, exc_info=True)


async def load(conv_id: str) -> dict | None:
    """Read the turn snapshot for a conversation, or None. Best-effort."""
    try:
        raw = await _redis().get(_key(conv_id))
        return json.loads(raw) if raw else None
    except Exception:
        logger.debug("stream_buffer load failed (conv=%s)", conv_id, exc_info=True)
        return None


async def delete(conv_id: str) -> None:
    """Drop the snapshot (e.g. when a fresh turn starts on the same conversation). Best-effort."""
    try:
        await _redis().delete(_key(conv_id))
    except Exception:
        logger.debug("stream_buffer delete failed (conv=%s)", conv_id, exc_info=True)
