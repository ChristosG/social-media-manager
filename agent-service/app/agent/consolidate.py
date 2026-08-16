"""Background memory consolidation.

The 9B unreliably calls update_brand_voice / remember_preference mid-turn, so durable preferences the user
expresses in chat ("from now on only Instagram", "be the voice of my org, stop being vague") get lost. We
capture them OUT of band instead: after a feedback/correction turn, a detached pass (like followups/title)
reads the user's message and extracts any DURABLE preference, then persists it to structured memory so it
shapes every future draft. Conservative by design — it returns nothing unless the user clearly wants a rule
applied to all future posts. Inferred entries are visible/prunable in Studio → Knowledge.
"""
import json
import logging
import re

from app.llm.client import build_chat_model
from app.repo import memory as mem_repo, profile as profile_repo

logger = logging.getLogger(__name__)

_model = None  # tests set this to a fake; else thinking-off Qwen
def _m():
    global _model
    if _model is None:
        _model = build_chat_model()
    return _model

# kind -> the value sub-field stored in memory_entries.value (mirrors tools._PREF_FIELD)
_FIELD = {"brand_voice": "descriptor", "style_rule": "rule", "banned_topic": "topic",
          "cta_pref": "cta", "content_pillar": "name", "fact": "fact"}
_KINDS = set(_FIELD) | {"default_platform"}

# Feedback/correction cue — same family the router uses. Only these turns trigger consolidation, so we
# don't spend a call on every message. (Kept here to avoid importing the router into the WS hot path.)
_FEEDBACK = re.compile(
    r"\b(too |more |less |instead|redo|rework|again|not quite|isn'?t|doesn'?t|don'?t|stop|always|never|"
    r"from now on|only|prefer|warmer|colder|softer|punchier|simpler|corporate|generic|bland|vague|"
    r"ambiguous|represent|the voice of|face of (my|our|the)|who we are|be (my|our) (voice|assistant))\b", re.I)

_PLATFORMS = {"instagram": ("instagram", "insta", "ig"), "facebook": ("facebook", "fb"),
              "linkedin": ("linkedin",), "twitter": ("twitter", "x", "tweet"),
              "tiktok": ("tiktok", "tik tok"), "threads": ("threads",)}


def is_feedback(message: str) -> bool:
    """Cheap gate: only run consolidation on turns that look like the user is teaching/correcting."""
    return bool(_FEEDBACK.search(message or ""))


def _norm_platform(value: str) -> str | None:
    v = (value or "").strip().lower()
    for key, aliases in _PLATFORMS.items():
        if v == key or any(a in v for a in aliases):
            return key
    return None


_PROMPT = (
    "You extract DURABLE preferences a nonprofit's social-media manager states in chat, so the assistant "
    "applies them to ALL future posts. Read the user's latest message (and the draft it reacted to, for "
    "context). Output ONLY a JSON array. Each item: {\"kind\": one of "
    "[\"brand_voice\",\"style_rule\",\"banned_topic\",\"cta_pref\",\"content_pillar\",\"fact\",\"default_platform\"], "
    "\"value\": short string}. "
    "Rules: include ONLY preferences clearly meant to persist for future posts — a brand/voice/identity "
    "preference -> brand_voice; a writing rule -> style_rule; a topic to avoid -> banned_topic; a "
    "call-to-action preference -> cta_pref; a recurring theme -> content_pillar; a lasting org fact -> "
    "fact; 'I only/mostly post on X' / 'we're an instagram-first org' -> default_platform (value = the "
    "platform name). Do NOT include one-off edits ('make THIS shorter'), or anything not meant to last. "
    "If there is nothing durable, return []. Return ONLY the JSON array.\n\n"
    "DRAFT THE USER REACTED TO (context, may be empty):\n{assistant}\n\nUSER MESSAGE:\n{user}"
)


def _parse(content: str) -> list[dict]:
    try:
        s = content[content.find("["): content.rfind("]") + 1]
        arr = json.loads(s) if s else []
    except Exception:
        return []
    out = []
    for it in arr if isinstance(arr, list) else []:
        if isinstance(it, dict) and it.get("kind") in _KINDS and str(it.get("value") or "").strip():
            out.append({"kind": it["kind"], "value": str(it["value"]).strip()[:200]})
    return out[:3]   # cap: a single turn shouldn't rewrite the whole memory


async def extract_preferences(user_msg: str, assistant_text: str = "") -> list[dict]:
    """LLM-extract durable preferences from a feedback turn. [] on anything non-durable or on failure."""
    prompt = _PROMPT.replace("{assistant}", (assistant_text or "")[:1500]).replace("{user}", user_msg or "")
    try:
        resp = await _m().ainvoke(prompt)
        return _parse(getattr(resp, "content", "") or "")
    except Exception:
        logger.warning("preference extraction failed", exc_info=True)
        return []


async def _persist(org_id: str, kind: str, value: str) -> bool:
    if kind == "default_platform":
        plat = _norm_platform(value)
        if not plat:
            return False
        await profile_repo.upsert_profile(org_id, None, None, None, None, default_platform=plat)
        return True
    field = _FIELD[kind]
    if kind == "brand_voice":
        existing = next(iter(await mem_repo.list_entries(org_id, "brand_voice")), None)
        if existing:
            await mem_repo.update_entry(org_id, existing["id"], {field: value}, None)
        else:
            await mem_repo.create_entry(org_id, "brand_voice", {field: value}, None, "inferred")
        return True
    # Light dedup for the multi-valued kinds — don't stack identical entries.
    existing = await mem_repo.list_entries(org_id, kind)
    if any(str((e["value"] or {}).get(field, "")).strip().lower() == value.lower() for e in existing):
        return False
    await mem_repo.create_entry(org_id, kind, {field: value}, None, "inferred")
    return True


async def consolidate_memory(org_id: str, user_msg: str, assistant_text: str = "") -> list[dict]:
    """Extract + persist durable preferences from one feedback turn. Returns what was saved (for logging/
    tests). Best-effort: never raises into the caller."""
    saved: list[dict] = []
    try:
        for pref in await extract_preferences(user_msg, assistant_text):
            try:
                if await _persist(org_id, pref["kind"], pref["value"]):
                    saved.append(pref)
            except Exception:
                logger.warning("consolidate persist failed kind=%s", pref.get("kind"), exc_info=True)
    except Exception:
        logger.warning("consolidate_memory failed", exc_info=True)
    return saved
