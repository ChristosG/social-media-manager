"""The publish gate is a real LangGraph interrupt(): when the agent calls publish_post the graph PAUSES
with a preview payload, and only a resume (the user's approval/cancel) lets it proceed."""
import uuid
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from app.security.context import set_identity
from app.repo import connections as conn_repo
from app.graph.graph import build_graph
import app.agent.tools as tools

pytestmark = pytest.mark.asyncio


class ScriptedModel:
    def __init__(self, script): self.script = list(script); self.i = 0
    def bind_tools(self, t): return self
    async def ainvoke(self, messages, *a, **k):
        msg = self.script[min(self.i, len(self.script) - 1)]; self.i += 1; return msg


async def _seed_publishable_conn(org):
    return await conn_repo.create_connection(
        org, "facebook", "page-1", "Our Page", token="tok", scopes="pages_manage_posts")


async def test_publish_post_interrupts_then_cancels(db_pool):
    org = str(uuid.uuid4()); set_identity("u", org)
    await _seed_publishable_conn(org)
    call = AIMessage(content="", tool_calls=[{"name": "publish_post", "args": {"platform": "facebook"}, "id": "c1"}])
    final = AIMessage(content="Okay, nothing was posted — your draft is saved.")
    graph = build_graph(model=ScriptedModel([call, final]), tools=tools.ALL_TOOLS, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t-cancel"}}

    # First pass: the graph must PAUSE on the interrupt, surfacing the preview payload (not finish).
    interrupt_payload = None
    async for mode, chunk in graph.astream(
            {"messages": [HumanMessage("post this to facebook")], "org_id": org, "system_prompt": ""},
            stream_mode=["updates", "messages"], config=config):
        if mode == "updates" and isinstance(chunk, dict) and "__interrupt__" in chunk:
            interrupt_payload = chunk["__interrupt__"][0].value
    assert interrupt_payload is not None
    assert interrupt_payload["kind"] == "publish_proposal"
    assert any(t["provider"] == "facebook" for t in interrupt_payload["targets"])

    # Resume with a CANCEL decision → the tool returns without publishing, the agent narrates.
    out = await graph.ainvoke(Command(resume={"approved": False}), config=config)
    assert "nothing" in out["messages"][-1].content.lower()


async def test_publish_post_without_connections_does_not_interrupt(db_pool):
    org = str(uuid.uuid4()); set_identity("u", org)
    call = AIMessage(content="", tool_calls=[{"name": "publish_post", "args": {}, "id": "c1"}])
    final = AIMessage(content="You'll need to connect an account first.")
    graph = build_graph(model=ScriptedModel([call, final]), tools=tools.ALL_TOOLS, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t-noconn"}}
    out = await graph.ainvoke(
        {"messages": [HumanMessage("publish it")], "org_id": org, "system_prompt": ""}, config=config)
    # No connected accounts → the tool returns a helpful message, no interrupt, the turn completes.
    assert out["messages"][-1].content == "You'll need to connect an account first."
    assert "__interrupt__" not in out
