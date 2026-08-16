"""visual_brief turns a caption into a clean image-generator prompt — the literal caption (CTAs, hashtags,
URLs, emoji) must NEVER reach FLUX, which used to render those words as garbled text."""
import pytest
from app.agent import image_brief

pytestmark = pytest.mark.asyncio


async def test_visual_brief_distils_scene_and_drops_caption_text(monkeypatch):
    class _Resp:
        content = "A group of children laughing together in a sunlit summer camp meadow"

    class _Model:
        async def ainvoke(self, prompt):
            assert "Donate now" in prompt   # the caption reaches the LLM as INPUT context
            return _Resp()

    monkeypatch.setattr(image_brief, "_m", lambda: _Model())
    caption = "Donate now! Your $50 funds a camp weekend. #MyrasKids #DonateNow https://x.org/give"
    brief = await image_brief.visual_brief(caption, voice="warm", platform="instagram")

    assert "summer camp meadow" in brief
    assert "no text" in brief and "no logos" in brief
    # None of the caption's words/markers leak into the FLUX prompt:
    assert "#MyrasKids" not in brief and "Donate now" not in brief and "http" not in brief


async def test_visual_brief_falls_back_when_llm_unavailable(monkeypatch):
    class _Model:
        async def ainvoke(self, prompt):
            raise RuntimeError("model down")

    monkeypatch.setattr(image_brief, "_m", lambda: _Model())
    brief = await image_brief.visual_brief("Save the whales 🐋 #ocean", voice=None, platform=None)
    assert "no text" in brief
    assert "🐋" not in brief and "#ocean" not in brief
