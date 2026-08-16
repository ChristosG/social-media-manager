from app.agent.platforms import resolve_platform, PLATFORMS
from app.agent.drafting import build_suggest_prompt, build_draft_prompt


def test_resolve_platform():
    assert resolve_platform("LinkedIn")[0] == "linkedin"
    assert resolve_platform("nope") is None


def test_suggest_prompt_includes_dedup_and_brief():
    sp = build_suggest_prompt({"mission": "End plastic"}, "BRAND VOICE: warm.", ["Old idea"], 2, "flood relief", None)
    assert "flood relief" in sp and "Old idea" in sp and "End plastic" in sp and "exactly 2" in sp


def test_draft_prompt_includes_voice_and_platform_limit():
    cfg = {"label": "X", "max_chars": 280, "tone": "punchy", "hashtags": "1-2"}
    dp = build_draft_prompt("Beach cleanup", "rally volunteers", cfg, "playful pirate", ["politics"])
    assert "280" in dp and "playful pirate" in dp and "politics" in dp


def test_draft_prompt_anchors_on_mission():
    cfg = {"label": "LinkedIn", "max_chars": 3000, "tone": "warm", "hashtags": "2-3"}
    dp = build_draft_prompt("New Arrivals", "introduce rescued pets", cfg, None, [],
                            mission="We rescue and rehome abandoned dogs and cats")
    assert "rescue and rehome abandoned dogs and cats" in dp


def test_draft_prompt_aims_for_target_length_not_the_ceiling():
    # Instagram: aim for the ideal length (~600), with max_chars as a hard ceiling — so the model stops
    # writing 2200-char walls of text.
    from app.agent.platforms import PLATFORMS
    ig = {"label": "Instagram", **PLATFORMS["instagram"]}
    dp = build_draft_prompt("Camp", "story", ig, None, [])
    assert "600" in dp and "2200" in dp and "HARD ceiling" in dp and "never pad" in dp.lower()


def test_draft_prompt_falls_back_to_fraction_of_max_when_no_target():
    # A custom platform config without target_chars still aims short (~30% of the ceiling), not the max.
    cfg = {"label": "Custom", "max_chars": 2000, "tone": "warm", "hashtags": "1-2"}
    dp = build_draft_prompt("X", "y", cfg, None, [])
    assert "600" in dp                                   # round(2000*0.3) = 600, not 2000-as-target


def test_draft_prompt_uses_org_name_and_forbids_placeholders():
    # The "[Organization Name]" bug: the writer must know the org name and never emit bracket placeholders.
    cfg = {"label": "Instagram", "max_chars": 2200, "tone": "warm", "hashtags": "3-5"}
    dp = build_draft_prompt("Sisterhood", "a survivor story", cfg, None, [], org_name="BRCAStrong")
    assert "BRCAStrong" in dp
    assert "[Organization Name]" in dp and "NEVER output bracketed placeholders" in dp  # the instruction names it


def test_draft_prompt_grounds_in_real_programs():
    # The caption writer must see the org's ACTUAL programs so "a post about our programs" reflects them
    # (not generic copy). This was the gap behind "it didn't even read my programs".
    cfg = {"label": "Instagram", "max_chars": 2200, "tone": "warm", "hashtags": "3-5"}
    dp = build_draft_prompt("Summer fun", "highlight the camp", cfg, None, [],
                            programs=[{"name": "Summer Camp", "description": "A weekend where grieving kids share stories"},
                                      {"name": "Support Groups", "description": "Monthly grief groups"}])
    assert "Summer Camp" in dp and "Support Groups" in dp and "don't invent" in dp


def test_draft_prompt_includes_taught_style_rules_and_cta():
    # Durable preferences the user TAUGHT (e.g. "write in pirate language") must reach the caption writer,
    # not just the suggestion text — this was the bug where preferences were ignored in the actual post.
    cfg = {"label": "Instagram", "max_chars": 2200, "tone": "warm", "hashtags": "3-5"}
    dp = build_draft_prompt("Beach cleanup", "rally volunteers", cfg, None, [],
                            rules=["write in pirate language", "no exclamation marks"],
                            ctas=["end with our donation link"])
    assert "write in pirate language" in dp and "no exclamation marks" in dp
    assert "end with our donation link" in dp


def test_draft_prompt_revises_existing_when_previous_given():
    cfg = {"label": "Instagram", "max_chars": 2200, "tone": "warm", "hashtags": "3-5"}
    dp = build_draft_prompt("AI for field teams", "make it warmer", cfg, None, [],
                            previous="Our AI helps relief teams coordinate.")
    # Revision mode: includes the current post + the change instruction, and does NOT use the 'Idea:' framing.
    assert "Our AI helps relief teams coordinate." in dp and "make it warmer" in dp
    assert "CURRENT POST" in dp and "Idea:" not in dp
