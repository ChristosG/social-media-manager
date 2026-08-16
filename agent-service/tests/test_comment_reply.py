import pytest
from app.agent import comment_reply as cr

pytestmark = pytest.mark.asyncio


class FakeModel:
    def __init__(self, content):
        self._content = content
        self.prompts = []

    async def ainvoke(self, prompt):
        self.prompts.append(prompt)
        return type("R", (), {"content": self._content})()


async def test_draft_reply_cleans_and_includes_voice():
    m = FakeModel('"Thank you so much, Sam! 💛"')
    out = await cr.draft_reply({"message": "love your work", "author_name": "Sam"},
                               profile={"one_liner": "We rescue dogs"}, voice="warm and playful",
                               banned=["politics"], model=m)
    assert out == "Thank you so much, Sam! 💛"          # surrounding quotes stripped
    assert "warm and playful" in m.prompts[0] and "politics" in m.prompts[0]


async def test_draft_reply_empty_comment():
    assert await cr.draft_reply({"message": "  "}, model=FakeModel("x")) == ""


async def test_classify_safe_parses_json():
    m = FakeModel('Sure: {"safe": true, "confidence": 0.92, "reason": "simple thanks"}')
    v = await cr.classify_safety({"message": "thank you!"}, "You're welcome!", model=m)
    assert v["safe"] is True and v["confidence"] == 0.92


async def test_classify_unsafe_and_clamps():
    m = FakeModel('{"safe": false, "confidence": 1.7, "reason": "complaint"}')
    v = await cr.classify_safety({"message": "this is broken and I want a refund"},
                                 "We'll refund you today.", model=m)
    assert v["safe"] is False and v["confidence"] == 1.0


async def test_classify_fails_closed_on_garbage():
    v = await cr.classify_safety({"message": "hi"}, "hello", model=FakeModel("not json at all"))
    assert v["safe"] is False and v["confidence"] == 0.0
