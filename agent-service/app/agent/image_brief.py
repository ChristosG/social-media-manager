"""Turn a post's TEXT into a clean VISUAL prompt for the image model.

The old path fed the literal caption — CTAs, hashtags, org names, emoji — straight into FLUX, which then
tried to render those words, producing the garbled "text in the image" the user reported. Here we ask the
local LLM to distil the post into a concrete photographic SCENE (no words/logos), then append fixed quality
and negative cues. Degrades to a heuristic strip of the caption if the LLM is unavailable.
"""
import logging
import re

from app.llm.client import build_chat_model

logger = logging.getLogger(__name__)
_model = None

# Appended to every brief. (FLUX is guidance-distilled at low cfg, so a separate negative prompt has little
# effect — the strongest lever is simply NOT describing text, plus an explicit in-prompt "no text".)
_QUALITY = ("photographic, social-media ready, clean composition, natural balanced lighting, "
            "no text, no lettering, no words, no captions, no signage, no logos, no watermark")


def _m():
    global _model
    if _model is None:
        _model = build_chat_model()
    return _model


def _strip(text: str) -> str:
    """Heuristic fallback subject: drop hashtags, URLs, emoji and punctuation noise from the caption."""
    t = re.sub(r"#\w+|https?://\S+", " ", text)
    t = re.sub(r"[^\w\s,.'-]", " ", t)          # removes emoji + stray symbols
    return re.sub(r"\s+", " ", t).strip()


async def visual_brief(text: str, voice: str | None = None, platform: str | None = None) -> str:
    """Compose the FLUX prompt: an LLM-distilled visual scene (no words/logos) + quality/negative cues."""
    text = (text or "").strip()
    scene = ""
    if text:
        ask = (
            "You write prompts for a text-to-image generator. Describe ONE photographic scene that would "
            "illustrate the social post below — a single vivid sentence with a concrete subject, setting, mood "
            "and lighting. HARD RULES: describe only what is VISIBLE; absolutely NO text, words, letters, "
            "numbers, captions, hashtags, brand names, logos, signs, or UI anywhere in the image. "
            "Output ONLY the sentence.\n\n"
            f"POST:\n{text[:600]}\n\nVISUAL SCENE:")
        try:
            resp = await _m().ainvoke(ask)
            scene = (resp.content or "").strip().strip('"').splitlines()[0].strip().strip('"')
        except Exception:
            logger.exception("visual_brief: LLM failed; falling back to stripped caption")
    if len(scene) < 8:
        scene = _strip(text)[:200] or "a warm, hopeful nonprofit community scene"
    parts = [scene]
    if voice:
        parts.append(f"{voice} aesthetic")
    if platform:
        parts.append(f"optimized for {platform}")
    parts.append(_QUALITY)
    return ", ".join(parts)
