"""One constrained caption-refine call: takes the current caption + an intent (a chip label or custom
text), returns (new_caption, new_chips). Reuses the drafting revision prompt so 'make it warmer' genuinely
rewrites rather than nudging. The model is injectable for tests."""
from app.agent.drafting import build_draft_prompt, CHIPS_SUFFIX, split_caption_chips
from app.agent.platforms import PLATFORMS
from app.agent import tools as _tools
from app.repo import profile as profile_repo


async def refine_caption(org_id: str, caption: str, intent: str, platform: str | None,
                         model=None) -> tuple[str, list[str]]:
    voice, banned, rules, ctas = await _tools._draft_directives(org_id)
    pcfg = PLATFORMS.get((platform or "").lower(), {})
    profile = await profile_repo.get_profile(org_id)
    prompt = build_draft_prompt(
        "", intent or "improve it", pcfg, voice, banned, (profile or {}).get("mission"),
        previous=caption, rules=rules, ctas=ctas,
        programs=await profile_repo.list_programs(org_id), org_name=(profile or {}).get("name"),
    ) + CHIPS_SUFFIX
    resp = await (model or _tools._gen_model(pcfg)).ainvoke(prompt)
    return split_caption_chips((getattr(resp, "content", "") or "").strip())
