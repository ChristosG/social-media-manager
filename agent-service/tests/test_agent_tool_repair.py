import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from app.graph.graph import _needs_tool_repair, build_graph


def test_detects_invalid_only_tool_call():
    m = AIMessage(content="", tool_calls=[], invalid_tool_calls=[{"name": "draft_post", "args": "BROKEN", "id": "1", "error": "bad json"}])
    assert _needs_tool_repair(m) is True


def test_valid_tool_call_is_not_repair():
    m = AIMessage(content="", tool_calls=[{"name": "draft_post", "args": {}, "id": "1"}])
    assert _needs_tool_repair(m) is False


def test_plain_answer_is_not_repair():
    assert _needs_tool_repair(AIMessage(content="here you go")) is False


def test_empty_message_is_not_repair():
    assert _needs_tool_repair(AIMessage(content="")) is False


# ---------------------------------------------------------------------------
# Graph-level test: repair fires ONCE then the agent gives a plain answer.
# ---------------------------------------------------------------------------

class ScriptedModel:
    """Scripted fake that returns each message in sequence (reuses pattern from test_publish_interrupt)."""
    def __init__(self, script):
        self.script = list(script)
        self.i = 0

    def bind_tools(self, t):
        return self

    async def ainvoke(self, messages, *a, **k):
        msg = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return msg


pytestmark = pytest.mark.asyncio


async def test_repair_fires_once_then_ends():
    """When the model emits only invalid_tool_calls, the repair node injects a nudge, and the
    second agent call returns a plain answer.  The graph must NOT loop beyond that one repair."""
    bad_call = AIMessage(
        content="",
        tool_calls=[],
        invalid_tool_calls=[{"name": "draft_post", "args": "BROKEN {", "id": "x1", "error": "bad json"}],
    )
    plain_answer = AIMessage(content="Here is your draft post.")

    model = ScriptedModel([bad_call, plain_answer])
    graph = build_graph(model=model, tools=[], checkpointer=None)

    out = await graph.ainvoke(
        {"messages": [HumanMessage("Write a post")], "org_id": "", "system_prompt": ""},
    )

    # The final message must be the plain answer (repair fired + agent replied normally).
    assert out["messages"][-1].content == "Here is your draft post.", repr(out["messages"][-1])
    # repair_count must be 1 — it fired exactly once and the cap prevented further loops.
    assert out.get("repair_count", 0) == 1, f"expected repair_count=1, got {out.get('repair_count')}"


async def test_repair_cap_prevents_second_loop():
    """If (hypothetically) the model returns invalid tool calls TWICE, the cap stops it after one
    repair and ends the turn — no infinite loop."""
    bad_call_1 = AIMessage(
        content="",
        tool_calls=[],
        invalid_tool_calls=[{"name": "draft_post", "args": "BAD1", "id": "x1", "error": "err"}],
    )
    bad_call_2 = AIMessage(
        content="",
        tool_calls=[],
        invalid_tool_calls=[{"name": "draft_post", "args": "BAD2", "id": "x2", "error": "err"}],
    )
    # third response is a plain answer — but it should never be reached (cap ends after bad_call_2)
    plain_answer = AIMessage(content="Finally a real answer.")

    model = ScriptedModel([bad_call_1, bad_call_2, plain_answer])
    graph = build_graph(model=model, tools=[], checkpointer=None)

    out = await graph.ainvoke(
        {"messages": [HumanMessage("Write a post")], "org_id": "", "system_prompt": ""},
    )

    # The cap hit — the last message is bad_call_2 (the graph ended rather than looping again).
    # repair_count must be 1 (cap was 1 repair max).
    assert out.get("repair_count", 0) == 1, f"expected repair_count=1, got {out.get('repair_count')}"
    # The graph must have terminated (no infinite loop) — if we reached here, it did not hang.
