"""Angle parsing for plan_campaign. The headline case: a local LLM emits a MALFORMED JSON array with commas
INSIDE the quotes, all on one line — which previously collapsed into a single 'blob' slot in the campaign."""
from app.agent.campaign import parse_angles


def test_parses_clean_json_array():
    assert parse_angles('["First angle", "Second angle", "Third angle"]') == \
        ["First angle", "Second angle", "Third angle"]


def test_recovers_malformed_commas_inside_quotes():
    # The exact shape that produced the 1396-char blob slot in prod.
    blob = '["Meet the counselors," "How Winter Camp helps," "Inside a Support Group session,"]'
    angles = parse_angles(blob)
    assert angles == ["Meet the counselors", "How Winter Camp helps", "Inside a Support Group session"]
    assert len(angles) == 3   # never one blob


def test_strips_markdown_fence_and_prose():
    content = 'Sure! Here are the angles:\n```json\n["Angle one", "Angle two", "Angle three"]\n```'
    assert parse_angles(content) == ["Angle one", "Angle two", "Angle three"]


def test_flattens_objects():
    content = '[{"title": "Angle A"}, {"angle": "Angle B"}]'
    assert parse_angles(content) == ["Angle A", "Angle B"]


def test_falls_back_to_bullet_lines():
    content = "- First idea here\n- Second idea here\n- Third idea here"
    assert parse_angles(content) == ["First idea here", "Second idea here", "Third idea here"]


def test_empty_returns_empty():
    assert parse_angles("") == []
    assert parse_angles("   ") == []
