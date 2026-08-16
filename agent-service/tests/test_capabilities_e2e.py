"""A non-engineer adds a platform row -> the agent can draft for it next turn, no redeploy."""
import uuid
import pytest
from app.security.context import set_identity
from app.repo import capabilities as cap_repo, ledger as ledger_repo
import app.agent.tools as tools
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

pytestmark = pytest.mark.asyncio


def _fake(text):
    class F(GenericFakeChatModel):
        async def ainvoke(self, *a, **k): return AIMessage(content=text)
    return F(messages=iter([AIMessage(content=text)]))


async def test_added_platform_is_immediately_draftable(db_pool):
    org = str(uuid.uuid4()); set_identity("u", org)
    # 1. platform does not exist yet
    assert await cap_repo.resolve_platform(org, "mastodon") is None
    # 2. an admin adds it (a row write — what the Studio UI will do)
    await cap_repo.create_capability(org, "platform", "mastodon",
                                     {"label": "Mastodon", "max_chars": 500, "tone": "earnest", "hashtags": "2-3"})
    # 3. the agent can now draft for it
    tools._model = _fake("Tooting for a cause!")
    out = await tools.draft_post.ainvoke({"idea_title": "Adoption day", "platform": "mastodon"})
    assert "Tooting for a cause!" in out   # caption is wrapped with a 'shown to user' instruction now
    assert any(p["platform"] == "mastodon" for p in await ledger_repo.list_posts(org))
