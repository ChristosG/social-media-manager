import os, uuid, socket
import pytest
from langchain_core.messages import HumanMessage
from app.security.context import set_identity
from app.graph.graph import build_graph
from app.repo import ledger as ledger_repo, memory as mem_repo

def _qwen_up():
    try:
        with socket.create_connection(("localhost", 6888), 2): return True
    except OSError: return False

pytestmark = pytest.mark.skipif(not _qwen_up(), reason="Qwen :6888 not reachable")


@pytest.mark.usefixtures("db_pool")
async def test_seven_step_voice_persists_and_ledger():
    os.environ["LLM_BASE_URL"] = "http://localhost:6888/v1"
    from app.config import get_settings; get_settings.cache_clear()
    import app.agent.tools as tool_mod; tool_mod._model = None  # use real Qwen
    org = str(uuid.uuid4()); set_identity("u", org)
    g = build_graph()
    history = []
    async def turn(text):
        nonlocal history
        history = history + [HumanMessage(text)]
        out = await g.ainvoke({"messages": history, "org_id": org, "system_prompt": ""},
                              {"recursion_limit": 12})
        history = out["messages"]
        return out["messages"][-1].content
    await turn("Suggest 2 social post ideas for us.")
    await turn("Too corporate — we're warm and grassroots. Keep that in mind.")
    # the correction should have persisted the brand voice
    voices = await mem_repo.list_entries(org, "brand_voice")
    assert voices, "agent did not persist brand voice via update_brand_voice"
    assert "grassroots" in str(voices[0]["value"]).lower()
    # suggestions should be in the ledger
    posts = await ledger_repo.list_posts(org)
    assert len(posts) >= 1, "agent did not record any suggested posts in the ledger"
