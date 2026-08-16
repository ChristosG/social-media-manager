import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from app.graph.graph import build_graph

pytestmark = pytest.mark.asyncio


@tool
def ping() -> str:
    """ping"""
    return "pong"


class _Counting:
    """A minimal fake chat model that yields scripted responses and counts invocations."""
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, msgs):
        r = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return r


async def test_thinking_model_used_only_on_first_step():
    # Step 1 (planning): thinking model decides to call a tool. Step 2 (after the tool): the FAST base
    # model narrates. THINK ONCE = exactly one thinking pass, regardless of tool count.
    thinking = _Counting([AIMessage(content="", tool_calls=[{"name": "ping", "args": {}, "id": "c1"}])])
    base = _Counting([AIMessage(content="final answer")])
    graph = build_graph(model=base, load_memory=False, tools=[ping], thinking_model=thinking)

    out = await graph.ainvoke({"messages": [HumanMessage("hi")], "org_id": None, "system_prompt": ""})

    assert thinking.calls == 1                       # deliberated once, on the planning step
    assert base.calls == 1                            # the post-tool step ran on the fast model
    assert out["messages"][-1].content == "final answer"
    assert any(isinstance(m, ToolMessage) for m in out["messages"])  # the tool actually ran


async def test_no_thinking_model_uses_base_every_step():
    # Without a thinking model (reasoning off), every step uses the base model — unchanged behaviour.
    base = _Counting([
        AIMessage(content="", tool_calls=[{"name": "ping", "args": {}, "id": "c1"}]),
        AIMessage(content="done"),
    ])
    graph = build_graph(model=base, load_memory=False, tools=[ping])
    out = await graph.ainvoke({"messages": [HumanMessage("hi")], "org_id": None, "system_prompt": ""})
    assert base.calls == 2 and out["messages"][-1].content == "done"
