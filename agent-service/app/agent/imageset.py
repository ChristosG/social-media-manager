import json
from app.llm.client import build_chat_model

_model = None   # tests set a fake; else thinking-off Qwen
# Strong negative on text: FLUX tends to render garbled lettering/signage if not firmly told not to.
_QUALITY = ("high quality, social-media ready, clean composition, balanced lighting, "
            "no text, no lettering, no words, no captions, no signage, no logos, no watermark")


def _m():
    global _model
    if _model is None:
        _model = build_chat_model()
    return _model


def _enhance(subject: str, voice: str | None, platform: str | None) -> str:
    parts = [subject.strip()]
    if voice:
        parts.append(f"visual style reflecting a {voice} brand")
    if platform:
        parts.append(f"optimized for {platform}")
    parts.append(_QUALITY)
    return ", ".join(p for p in parts if p)


def _plan_prompt(theme: str, count: int, voice: str | None, platform: str | None) -> str:
    return (
        f"Plan an Instagram carousel of {count} images on this theme: \"{theme}\".\n"
        "Return ONLY a JSON object with keys: caption (one engaging on-brand caption for the WHOLE carousel), "
        "style (a short shared visual-style clause — art direction, palette, medium — applied to EVERY image so "
        f"they look like one cohesive set), scenes (an array of EXACTLY {count} DISTINCT visual scene "
        "descriptions that tell a story across the theme — each a standalone image prompt with a different "
        "subject/setting/angle; never repeat a scene)."
        + (f"\nBrand voice: {voice}." if voice else "")
        + (f"\nPlatform: {platform}." if platform else "")
        + "\nExample: {\"caption\":\"Meet our crew!\",\"style\":\"warm documentary photography, golden hour\","
          "\"scenes\":[\"a volunteer hugging a rescued dog at sunrise\",\"close-up of a kitten's paw in a hand\"]}"
    )


def _parse(content: str) -> dict:
    try:
        s = content[content.find("{"): content.rfind("}") + 1]
        obj = json.loads(s) if s else {}
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _dedup_pad(scenes: list[str], base: str, count: int) -> list[str]:
    out, seen = [], set()
    for s in scenes:
        k = s.strip().lower()
        if k and k not in seen:
            seen.add(k); out.append(s.strip())
    i = 1
    while len(out) < count:
        out.append(f"{base}, distinct angle {i}"); i += 1
    return out[:count]


async def plan_image_set(base_prompt: str, count: int, mode: str = "distinct",
                         voice: str | None = None, platform: str | None = None) -> dict:
    """Return {caption, style, prompts:[str x count]}. tight → identical prompts (vary seed downstream);
    distinct → N distinct scene prompts + a shared style anchor + a caption, via one thinking-off LLM call."""
    count = max(1, min(int(count or 1), 10))
    if mode == "tight":
        return {"caption": None, "style": "", "prompts": [_enhance(base_prompt, voice, platform)] * count}
    resp = await _m().ainvoke(_plan_prompt(base_prompt, count, voice, platform))
    data = _parse(getattr(resp, "content", "") or "")
    style = str(data.get("style") or "").strip()
    scenes = _dedup_pad([s for s in (data.get("scenes") or []) if isinstance(s, str) and s.strip()],
                        base_prompt, count)
    suffix = ", ".join(x for x in [style, _QUALITY] if x)
    prompts = [f"{s}, {suffix}" for s in scenes]
    # Only accept a string caption — a malformed LLM response (number/list/dict) must not be str()-coerced
    # into a Python repr that then becomes a user-facing, publishable caption.
    raw_caption = data.get("caption")
    caption = raw_caption.strip() if isinstance(raw_caption, str) and raw_caption.strip() else None
    return {"caption": caption, "style": style, "prompts": prompts}
