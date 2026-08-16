from app.agent.drafting import split_caption_chips


def test_split_caption_chips_parses_trailing_line():
    raw = "1 in 5 grieving kids never gets support.\nCHIPS: Lead with the number | Add the source | Simpler"
    caption, chips = split_caption_chips(raw)
    assert caption == "1 in 5 grieving kids never gets support."
    assert chips == ["Lead with the number", "Add the source", "Simpler"]


def test_split_caption_chips_absent_returns_empty():
    caption, chips = split_caption_chips("Just a caption, no chips line.")
    assert caption == "Just a caption, no chips line."
    assert chips == []


def test_split_caption_chips_caps_at_three():
    caption, chips = split_caption_chips("x\nCHIPS: a | b | c | d | e")
    assert chips == ["a", "b", "c"]
