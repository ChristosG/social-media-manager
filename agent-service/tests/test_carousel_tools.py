import uuid
import pytest
from app.security.context import set_identity, image_sink_var
from app.agent import flux, imageset
import app.agent.tools as tools

pytestmark = pytest.mark.asyncio


def _fake_flux():
    seeds = iter(range(1000, 9999))
    async def gen(prompt, width=1024, height=1024, steps=4, cfg=1.0, seed=None, sampler_name=None):
        return (b"PNG" + prompt.encode()[:8], seed if seed is not None else next(seeds))
    return gen


async def test_generate_carousel_one_caption_n_distinct_images(db_pool, monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org); image_sink_var.set([])
    monkeypatch.setattr(flux, "generate", _fake_flux())
    async def fake_plan(base, count, mode="distinct", voice=None, platform=None):
        return {"caption": "Meet our rescues! 🐾", "style": "warm",
                "prompts": [f"distinct scene {i}, warm" for i in range(count)]}
    monkeypatch.setattr(imageset, "plan_image_set", fake_plan)

    out = await tools.generate_carousel.ainvoke({"theme": "adoption weekend", "count": 4, "platform": "instagram"})
    assert "Meet our rescues" in out                       # caption surfaced to the agent
    sink = image_sink_var.get()
    assert sink and sink[-1]["kind"] == "gallery" and len(sink[-1]["urls"]) == 4   # N images in one gallery


async def test_generate_image_distinct_uses_planner(db_pool, monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org); image_sink_var.set([])
    monkeypatch.setattr(flux, "generate", _fake_flux())
    calls = {"n": 0}
    async def fake_plan(base, count, mode="distinct", voice=None, platform=None):
        calls["n"] += 1
        return {"caption": None, "style": "", "prompts": [f"scene {i}" for i in range(count)]}
    monkeypatch.setattr(imageset, "plan_image_set", fake_plan)
    out = await tools.generate_image.ainvoke({"prompt": "our shelter", "count": 3, "variation": "distinct"})
    assert calls["n"] == 1                                  # distinct mode invoked the planner
    sink = image_sink_var.get()
    assert sink and len(sink[-1]["urls"]) == 3


async def test_generate_image_tight_default_single(db_pool, monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org); image_sink_var.set([])
    monkeypatch.setattr(flux, "generate", _fake_flux())
    out = await tools.generate_image.ainvoke({"prompt": "a calico kitten"})
    sink = image_sink_var.get()
    assert sink and sink[-1]["kind"] == "image"            # single image unchanged


def test_clamp_helpers():
    assert tools._clamp_cfg(None) == 1.0 and tools._clamp_cfg(5.0) == 3.0 and tools._clamp_cfg(1.5) == 1.5
    assert tools._valid_sampler("euler") == "euler" and tools._valid_sampler("not-real") is None


async def test_generate_carousel_caption_drives_planner(db_pool, monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org); image_sink_var.set([])
    monkeypatch.setattr(flux, "generate", _fake_flux())
    seen = {}
    async def fake_plan(base, count, mode="distinct", voice=None, platform=None):
        seen["base"] = base
        return {"caption": "x", "style": "", "prompts": [f"s{i}" for i in range(count)]}
    monkeypatch.setattr(imageset, "plan_image_set", fake_plan)
    await tools.generate_carousel.ainvoke(
        {"theme": "adoption", "count": 2, "caption": "Save a life this Saturday! 🐾 #adopt"})
    assert seen["base"] == "Save a life this Saturday! 🐾 #adopt"  # caption (not terse theme) drives the planner


async def test_generate_image_distinct_caption_drives_planner(db_pool, monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org); image_sink_var.set([])
    monkeypatch.setattr(flux, "generate", _fake_flux())
    seen = {}
    async def fake_plan(base, count, mode="distinct", voice=None, platform=None):
        seen["base"] = base
        return {"caption": None, "style": "", "prompts": [f"s{i}" for i in range(count)]}
    monkeypatch.setattr(imageset, "plan_image_set", fake_plan)
    await tools.generate_image.ainvoke(
        {"prompt": "shelter dogs", "count": 2, "variation": "distinct", "caption": "Adopt, don't shop! 🐾"})
    assert seen["base"] == "Adopt, don't shop! 🐾"


async def test_generate_carousel_falls_back_to_theme_without_caption(db_pool, monkeypatch):
    org = str(uuid.uuid4()); set_identity("u", org); image_sink_var.set([])
    monkeypatch.setattr(flux, "generate", _fake_flux())
    seen = {}
    async def fake_plan(base, count, mode="distinct", voice=None, platform=None):
        seen["base"] = base
        return {"caption": "c", "style": "", "prompts": [f"s{i}" for i in range(count)]}
    monkeypatch.setattr(imageset, "plan_image_set", fake_plan)
    await tools.generate_carousel.ainvoke({"theme": "adoption weekend", "count": 2})
    assert seen["base"] == "adoption weekend"  # no caption → theme still used


async def test_generate_image_upserts_draft_images(db_pool, monkeypatch):
    from app.security.context import conv_id_var
    from app.repo import conversation_drafts as drafts
    org = str(uuid.uuid4()); conv = str(uuid.uuid4())
    set_identity("u", org); image_sink_var.set([]); conv_id_var.set(conv)
    monkeypatch.setattr(flux, "generate", _fake_flux())
    await tools.generate_image.ainvoke({"prompt": "a senior dog", "count": 1})
    d = await drafts.get_draft(org, conv)
    assert d is not None and len(d["image_ids"]) == 1   # the generated image id landed in the draft
    conv_id_var.set(None)


async def test_generate_image_falls_back_to_draft_caption(db_pool, monkeypatch):
    """The 'yes, add an image' turn: model passes NO caption, but a draft caption was already saved by an
    earlier draft_post. The image must be planned from that stored caption (no re-draft needed)."""
    from app.security.context import conv_id_var
    from app.repo import conversation_drafts as drafts
    import uuid as _uuid
    org = str(_uuid.uuid4()); conv = str(_uuid.uuid4())
    set_identity("u", org); image_sink_var.set([]); conv_id_var.set(conv)
    await drafts.upsert_caption(org, conv, "When the world tilts, we build resilience. 🌍 #CloudResilience")
    monkeypatch.setattr(flux, "generate", _fake_flux())
    seen = {}
    async def fake_plan(base, count, mode="distinct", voice=None, platform=None):
        seen["base"] = base
        return {"caption": "x", "style": "", "prompts": [f"s{i}" for i in range(count)]}
    monkeypatch.setattr(imageset, "plan_image_set", fake_plan)
    # No caption arg — simulates an affirmative-only image turn
    await tools.generate_image.ainvoke({"prompt": "resilient cloud", "count": 3, "variation": "distinct"})
    assert seen["base"] == "When the world tilts, we build resilience. 🌍 #CloudResilience"
    conv_id_var.set(None)


def test_system_prompt_add_image_flow_does_not_force_redraft():
    """The image flow must tell the model to REUSE the caption on add/redo turns, not re-draft it."""
    from app.graph.context import build_system_prompt
    sp = build_system_prompt([], None, [])
    assert "DO NOT call draft_post" in sp           # image-only turns must not re-draft the caption
    assert "pass it UNCHANGED" in sp
    assert "THE CAPTION TEXT" in sp                 # but caption-text edits DO go through draft_post
    # affirmative-only replies are explicitly recognized as image-add intents
    assert "'yes'" in sp
