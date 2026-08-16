from app.agent.tools import _parse_ideas


def test_parse_json_array():
    out = _parse_ideas('[{"title":"A","angle":"x"},{"title":"B","angle":"y"}]', 3)
    assert [i["title"] for i in out] == ["A", "B"]


def test_parse_single_object_or_fenced():
    out = _parse_ideas('Here you go:\n```json\n{"title":"Solo","angle":"z"}\n```', 3)
    assert out and out[0]["title"] == "Solo"


def test_parse_falls_back_to_lines_no_braces():
    out = _parse_ideas("1. Beach cleanup\n2. Volunteer spotlight", 2)
    assert [i["title"] for i in out] == ["Beach cleanup", "Volunteer spotlight"]
    assert all("{" not in i["title"] for i in out)


def test_parse_markdown_title_angle_lines():
    # The 9B sometimes returns markdown instead of JSON — we must extract clean title+angle, not store
    # "Title:** X | Angle:** Y" or the "Here are 3 ideas:" header (the malformed-ledger bug).
    content = (
        "Here are 3 distinct social post ideas for your nonprofit:\n"
        '1. **Title:** "The Filter That Changed Everything" | **Angle:** Showcase a household BioSand Filter\n'
        "2. **Title:** Committee Champions — **Angle:** Highlight local women as water stewards\n"
    )
    out = _parse_ideas(content, 3)
    assert [i["title"] for i in out] == ["The Filter That Changed Everything", "Committee Champions"]
    assert out[0]["angle"].startswith("Showcase a household BioSand Filter")
    assert out[1]["angle"].startswith("Highlight local women")
    assert all("Title:" not in i["title"] and "**" not in i["title"] for i in out)
    assert all("Here are" not in i["title"] for i in out)
