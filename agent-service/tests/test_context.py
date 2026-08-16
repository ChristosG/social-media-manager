import asyncio
from app.security.context import org_id_var, set_identity, current_org


async def _worker(org):
    set_identity(user_id="u", org_id=org)
    await asyncio.sleep(0.01)
    return current_org()


async def test_contextvar_is_isolated_across_tasks():
    results = await asyncio.gather(_worker("org-A"), _worker("org-B"), _worker("org-C"))
    assert sorted(results) == ["org-A", "org-B", "org-C"]  # no bleed


def test_system_prompt_lists_content_types_and_skills():
    from app.graph.context import build_system_prompt
    content_types = [{"name": "Volunteer Spotlight", "config": {"description": "Feature a volunteer."}}]
    skills = [{"name": "Always sign off", "config": {"instruction": "End every post with 'Adopt, don't shop.'"}}]
    sp = build_system_prompt([], None, [], content_types=content_types, skill_prompts=skills)
    assert "Volunteer Spotlight" in sp and "Feature a volunteer." in sp
    assert "Adopt, don't shop." in sp


def test_agent_mode_does_not_make_the_agent_roleplay_the_voice():
    """The keystone: in agent_mode the brand voice + style rules are framed as CONTENT the tools apply,
    NOT as behavior for the agent — so a 'write in pirate language' rule can't hijack the planner into
    role-playing in chat (which was killing tool-calling)."""
    from app.graph.context import build_system_prompt
    mem = [
        {"kind": "brand_voice", "value": {"descriptor": "playful pirate"}, "key": None},
        {"kind": "style_rule", "value": {"rule": "write in pirate language"}, "key": None},
        {"kind": "banned_topic", "value": {"topic": "politics"}, "key": None},
    ]
    agent = build_system_prompt(mem, {"mission": "rescue dogs"}, [], agent_mode=True)
    # Voice is acknowledged as content, but NOT as "always write in this voice", and the style rule is
    # not injected as a behavioral directive (the "STYLE RULES (always follow)" block is omitted).
    assert "Always write in this voice" not in agent
    assert "STYLE RULES (always follow)" not in agent
    assert "never role-play" in agent.lower() or "do not role-play" in agent.lower()
    # The brain still must respect hard constraints + know the mission.
    assert "politics" in agent and "rescue dogs" in agent

    # The content generators (default mode) keep the full voice + rules so captions stay on-brand.
    content = build_system_prompt(mem, None, [])
    assert "Always write in this voice" in content and "STYLE RULES (always follow)" in content


def test_system_prompt_includes_programs_and_audience():
    from app.graph.context import build_system_prompt
    sp = build_system_prompt([], {"mission": "help kids", "audience": "bereaved teens"}, [],
                             programs=[{"name": "Summer Camp", "description": "a healing weekend"}])
    assert "Summer Camp" in sp and "a healing weekend" in sp
    assert "bereaved teens" in sp and "ORG PROGRAMS" in sp


def test_system_prompt_includes_org_name():
    from app.graph.context import build_system_prompt
    sp = build_system_prompt([], {"name": "BRCAStrong", "mission": "support warriors"}, [], agent_mode=True)
    assert "BRCAStrong" in sp and "[Organization Name]" in sp  # names it + forbids the placeholder


def test_system_prompt_tolerates_non_object_config():
    """A non-object config (future seed/SQL bug) must not crash the per-turn prompt build."""
    from app.graph.context import build_system_prompt
    content_types = [{"name": "Weird", "config": [1, 2, 3]}]
    skills = [{"name": "Bad", "config": "oops"}]
    sp = build_system_prompt([], None, [], content_types=content_types, skill_prompts=skills)
    assert "Weird" in sp  # name still listed, no crash
