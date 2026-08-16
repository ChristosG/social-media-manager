import uuid
import pytest
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.graph.context import build_system_prompt
from app.graph.graph import build_graph
from app.repo import memory as mem_repo


def test_system_prompt_includes_voice_banned_and_dedup():
    memory = [
        {"kind": "brand_voice", "value": {"descriptor": "warm, grassroots"}},
        {"kind": "banned_topic", "value": {"topic": "politics"}, "key": "politics"},
    ]
    sp = build_system_prompt(memory, {"mission": "End ocean plastic"}, ["Beach cleanup recap"])
    assert "warm, grassroots" in sp
    assert "politics" in sp
    assert "End ocean plastic" in sp
    assert "Beach cleanup recap" in sp


@pytest.mark.usefixtures("db_pool")
async def test_graph_injects_org_brand_voice_into_prompt():
    org = str(uuid.uuid4())
    await mem_repo.create_entry(org, "brand_voice", {"descriptor": "warm, grassroots"}, None)

    captured = {}

    class Capture(GenericFakeChatModel):
        async def ainvoke(self, messages, *a, **k):
            captured["sys"] = messages[0].content if messages else ""
            return AIMessage(content="ok")

    graph = build_graph(model=Capture(messages=iter([AIMessage(content="ok")])))
    await graph.ainvoke({"messages": [HumanMessage("hi")], "org_id": org, "system_prompt": ""})
    assert "warm, grassroots" in captured["sys"]
