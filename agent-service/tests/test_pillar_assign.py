from app.agent.drafting import split_pillar, split_caption_chips, DEFAULT_PILLARS


def test_split_pillar_valid():
    cap, pil = split_pillar("Meet Leo…\nPILLAR: stories", DEFAULT_PILLARS)
    assert cap == "Meet Leo…" and pil == "stories"


def test_split_pillar_out_of_vocab_is_none():
    cap, pil = split_pillar("Body\nPILLAR: nonsense", DEFAULT_PILLARS)
    assert cap == "Body" and pil is None


def test_split_pillar_absent():
    cap, pil = split_pillar("Just a caption", DEFAULT_PILLARS)
    assert cap == "Just a caption" and pil is None


def test_split_pillar_case_insensitive_and_org_vocab():
    # an org-configured vocab + a model that shouted the value
    cap, pil = split_pillar("Body\nPILLAR: Volunteers", ["volunteers", "events"])
    assert cap == "Body" and pil == "volunteers"


def test_pillar_then_chips_compose():
    # the exact order _draft_one uses: strip PILLAR first, then CHIPS — both come off cleanly.
    raw = "Caption here\nCHIPS: a | b\nPILLAR: stories"
    caption_chips_raw, pillar = split_pillar(raw, DEFAULT_PILLARS)
    caption, chips = split_caption_chips(caption_chips_raw)
    assert caption == "Caption here"
    assert chips == ["a", "b"]
    assert pillar == "stories"
