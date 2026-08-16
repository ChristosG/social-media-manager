"""Shared single-image FLUX generation.

Used by BOTH the `generate_image` chat tool path and the campaign/ledger per-post image endpoint, so an
image made from a campaign post looks the same as one made in chat. One place that knows how to turn a
caption/subject into a stored, signed image."""
from app.repo import images as images_repo
from app.agent import flux
from app.security.img_sign import image_url

_CFG = 2.0   # prompt adherence; mid of the usable 1-3 band


async def generate_one(org: str, *, prompt: str, caption: str = "", platform: str = "") -> dict:
    """Generate ONE image (FLUX) from a subject/caption, store it, and return {"id","url"} (signed display
    URL). Reuses the tool's prompt/dimension/voice helpers so the look matches chat-made images. Raises
    RuntimeError if the generator is unreachable so callers can surface a clean error."""
    # Deferred import: tools imports image_gen at module top, so importing tools here only at call time
    # avoids a module-load cycle.
    from app.agent.tools import _resolve_dims, _voice_and_banned
    from app.agent.image_brief import visual_brief
    width, height, plat_key = await _resolve_dims(org, platform, None)
    voice, _ = await _voice_and_banned(org)
    subject = (prompt or caption or "social media image").strip()
    # Distil the post text into a clean visual SCENE rather than feeding the caption (CTAs/hashtags/org name)
    # to FLUX, which used to bake garbled text into the image.
    enhanced = await visual_brief(caption or prompt, voice, plat_key)
    out = await flux.generate(enhanced, width=width, height=height, steps=4, cfg=_CFG)
    if not out:
        raise RuntimeError("image generator unavailable")
    png, used_seed = out
    img_id = await images_repo.create_image(
        org, subject[:120], enhanced, png, width, height, 4, _CFG, used_seed, platform=plat_key)
    return {"id": str(img_id), "url": image_url(str(img_id), org)}
