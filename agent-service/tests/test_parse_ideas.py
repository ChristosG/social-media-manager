from app.agent.tools import _parse_ideas


def test_parses_clean_json_array():
    out = _parse_ideas('[{"title":"Clean Water","angle":"family story"}]', 3)
    # Real shape from JSON-array path preserves the exact keys the LLM returns.
    assert out == [{"title": "Clean Water", "angle": "family story"}]


def test_malformed_prose_yields_no_ideas_not_junk():
    bad = 'Title:** "The Filter That Changed Everything" | **Angle:** Showcase a household filter'
    out = _parse_ideas(bad, 3)
    # MUST NOT return the raw prose as a single idea (the live bug).
    assert all('Title:**' not in (i.get("title") or "") for i in out)
    assert all((i.get("title") or "").strip() for i in out)  # no empty/garbage titles


def test_empty_input_yields_empty():
    assert _parse_ideas("", 3) == []
