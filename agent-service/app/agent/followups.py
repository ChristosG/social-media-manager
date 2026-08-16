import json
import re

from app.llm.client import build_chat_model

_model = None  # tests may inject a fake; else the thinking-off Qwen


def _m():
    global _model
    if _model is None:
        _model = build_chat_model()
    return _model


_ARR_RE = re.compile(r"\[.*\]", re.S)
_TITLE_RE = re.compile(r'^[\s"\'`#*\-—:.]+|[\s"\'`*\-—:.]+$')


async def generate_title(user_text: str, assistant_text: str, model=None) -> str:
    """A short (3-6 word) title for a conversation, from its first exchange. '' on failure (caller keeps
    the default placeholder)."""
    if not (user_text or "").strip():
        return ""
    prompt = (
        "Write a concise title (3 to 6 words) summarizing what this chat is about, for a sidebar list. "
        "Title Case, no surrounding quotes, no trailing punctuation, no emoji. Return ONLY the title.\n\n"
        f"User: {user_text[:500]}\nAssistant: {assistant_text[:600]}"
    )
    try:
        resp = await (model or _m()).ainvoke(prompt)
        content = getattr(resp, "content", "") or ""
        raw = content.strip().splitlines()[0] if content.strip() else ""
        return _TITLE_RE.sub("", raw)[:60].strip()
    except Exception:
        return ""


def _parse_str_array(content: str) -> list[str]:
    try:
        m = _ARR_RE.search(content or "")
        arr = json.loads(m.group()) if m else []
        return [str(s).strip() for s in arr if isinstance(s, str) and str(s).strip()]
    except Exception:
        return []


async def generate_followups(user_text: str, assistant_text: str, model=None) -> list[str]:
    """Propose up to 3 short, clickable next-step chips for the user. Best-effort; [] on failure."""
    if not (assistant_text or "").strip():
        return []
    prompt = (
        "You suggest the user's next move in a chat with a nonprofit's social-media assistant. "
        "Given the latest exchange, propose 3 SHORT next actions the user could click — each 2 to 6 words, "
        'imperative and concrete (e.g. "Draft it for LinkedIn", "Suggest 3 more", "Make it warmer", '
        '"Write an Instagram version"). Avoid generic filler. Return ONLY a JSON array of 3 strings.\n\n'
        f"User: {user_text[:500]}\nAssistant: {assistant_text[:1500]}"
    )
    try:
        resp = await (model or _m()).ainvoke(prompt)
        return [s[:60] for s in _parse_str_array(getattr(resp, "content", "") or "")][:3]
    except Exception:
        return []
