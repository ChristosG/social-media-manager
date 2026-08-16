import pytest
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.graph.graph import build_graph


async def test_graph_streams_and_appends_reply():
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="Hello there")]))
    graph = build_graph(model=fake)
    out = await graph.ainvoke({"messages": [HumanMessage(content="hi")]})
    assert out["messages"][-1].content == "Hello there"
