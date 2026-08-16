import pytest
from app.agent.followups import generate_title

pytestmark = pytest.mark.asyncio


class _FakeResp:
    def __init__(self, content): self.content = content


class _FakeModel:
    def __init__(self, content): self._content = content
    async def ainvoke(self, prompt): return _FakeResp(self._content)


async def test_generate_title_strips_quotes_and_punctuation():
    m = _FakeModel('"Open-Source Hackathon Post."')
    t = await generate_title("Write a post about our hackathon", "Here's your post …", model=m)
    assert t == "Open-Source Hackathon Post"


async def test_generate_title_takes_first_line_only():
    m = _FakeModel("Clean Water Campaign\n(here is why...)")
    t = await generate_title("u", "a", model=m)
    assert t == "Clean Water Campaign"


async def test_generate_title_empty_user_returns_blank():
    m = _FakeModel("Should Not Be Used")
    assert await generate_title("", "something", model=m) == ""


async def test_generate_title_swallows_model_errors():
    class _Boom:
        async def ainvoke(self, prompt): raise RuntimeError("llm down")
    assert await generate_title("u", "a", model=_Boom()) == ""
