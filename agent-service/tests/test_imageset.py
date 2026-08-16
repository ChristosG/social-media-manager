import json
import pytest
from langchain_core.messages import AIMessage
import app.agent.imageset as imageset

pytestmark = pytest.mark.asyncio


def _fake(text):
    class F:
        async def ainvoke(self, *a, **k):
            return AIMessage(content=text)
    return F()


async def test_tight_mode_repeats_one_prompt():
    out = await imageset.plan_image_set("a rescued dog", 3, "tight")
    assert len(out["prompts"]) == 3 and out["prompts"][0] == out["prompts"][1] == out["prompts"][2]
    assert out["caption"] is None


async def test_distinct_mode_gives_distinct_prompts_with_shared_style_and_caption():
    imageset._model = _fake(json.dumps({
        "caption": "Meet our crew! 🐾",
        "style": "warm documentary photography, golden hour",
        "scenes": ["a volunteer hugging a dog at sunrise", "close-up of a kitten's paw in a hand",
                   "a family adopting a cat in a sunlit room"]}))
    out = await imageset.plan_image_set("adoption stories", 3, "distinct")
    assert out["caption"] == "Meet our crew! 🐾"
    assert len(out["prompts"]) == 3 and len(set(out["prompts"])) == 3          # 3 DISTINCT prompts
    assert all("golden hour" in p for p in out["prompts"])                     # shared style anchor on each


async def test_distinct_pads_when_model_returns_too_few():
    imageset._model = _fake(json.dumps({"caption": "x", "style": "s", "scenes": ["only one scene"]}))
    out = await imageset.plan_image_set("theme", 4, "distinct")
    assert len(out["prompts"]) == 4


async def test_count_clamped():
    out = await imageset.plan_image_set("x", 99, "tight")
    assert len(out["prompts"]) == 10   # clamp 1..10
