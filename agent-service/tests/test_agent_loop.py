import uuid
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.security.context import set_identity
from app.graph.graph import build_graph
import app.agent.tools as tools


class ScriptedModel:
    def __init__(self, script): self.script = list(script); self.i = 0
    def bind_tools(self, t): return self
    async def ainvoke(self, messages, *a, **k):
        msg = self.script[self.i]; self.i += 1; return msg


@pytest.mark.usefixtures("db_pool")
async def test_agent_calls_tool_then_answers():
    org = str(uuid.uuid4())
    set_identity("u", org)   # tools read current_org()
    call = AIMessage(content="", tool_calls=[{"name": "list_ledger", "args": {}, "id": "c1"}])
    final = AIMessage(content="Here's your ledger.")
    graph = build_graph(model=ScriptedModel([call, final]), tools=tools.ALL_TOOLS)
    out = await graph.ainvoke({"messages": [HumanMessage("what have we worked on?")], "org_id": org, "system_prompt": ""})
    assert out["messages"][-1].content == "Here's your ledger."
    assert any(isinstance(m, ToolMessage) for m in out["messages"])
