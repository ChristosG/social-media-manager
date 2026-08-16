from app.agent import tools
from app.agent.drafting import build_draft_prompt
from app.agent.platforms import PLATFORMS


def test_is_revision_catches_transform_and_anaphora():
    # The cues we already had still hold.
    assert tools._is_revision("make it warmer") is True
    assert tools._is_revision("Adjust the tone to be more urgent") is True
    # The reported miss: "transform it accordingly" never threaded the prior caption in, so the post
    # was silently re-drafted from scratch (identical output). It's a short, anaphoric instruction.
    assert tools._is_revision("transform it accordingly") is True
    assert tools._is_revision("redo this") is True
    assert tools._is_revision("apply that") is True
    # A brand-new topic is NOT a revision (don't hijack a real brief into rewriting the current post).
    assert tools._is_revision("a post about our summer camp for grieving kids") is False


def test_revision_prompt_instructs_real_rewrite_not_minimal_edit():
    cfg = {"label": "Instagram", "max_chars": 2200, "tone": "warm", "hashtags": "3-5"}
    dp = build_draft_prompt("X", "make it warmer", cfg, None, [],
                            previous="Our AI helps relief teams coordinate.")
    # Still revision mode: prior caption + the change, no fresh-idea framing.
    assert "CURRENT POST" in dp and "Our AI helps relief teams coordinate." in dp and "Idea:" not in dp
    # The fix: instruct a genuine re-voicing, and DROP the minimize-diff phrasing that made soft nudges
    # ("warmer/friendlier") converge back to the same text.
    assert "REWRITE" in dp
    assert "change only what's asked" not in dp


def test_capped_model_keyed_on_temperature(monkeypatch):
    # Revision turns run hotter so a soft nudge actually moves the text; the cache must keep the
    # warm/cool variants distinct (it used to be keyed on max_tokens alone).
    monkeypatch.setattr(tools, "_model", None)
    tools._capped_model.cache_clear()
    cool = tools._capped_model(200, 0.3)
    warm = tools._capped_model(200, 0.7)
    assert cool is not warm
    assert cool.temperature == 0.3 and warm.temperature == 0.7


def test_gen_model_passes_temperature(monkeypatch):
    monkeypatch.setattr(tools, "_model", None)
    tools._capped_model.cache_clear()
    assert tools._gen_model(PLATFORMS["instagram"], 0.7).temperature == 0.7
    # default stays cool for fresh drafts
    assert tools._gen_model(PLATFORMS["instagram"]).temperature == 0.3
