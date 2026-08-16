import uuid
import pytest
import app.agent.tools as tools
from app.security.context import set_identity

pytestmark = pytest.mark.asyncio


async def test_web_search_tool_formats_results(monkeypatch):
    set_identity("u", str(uuid.uuid4()))
    async def fake(query, max_results=5, include_domains=None):
        assert query == "july awareness days"
        return [
            {"title": "July Awareness", "url": "https://ex.com/july", "content": "Plastic Free July and more."},
            {"title": "Calendar", "url": "https://ex.com/cal", "content": "Disability Pride Month."},
        ]
    monkeypatch.setattr(tools, "web_search", fake)
    out = await tools.web_search_tool.ainvoke({"query": "july awareness days"})
    assert "https://ex.com/july" in out and "Plastic Free July" in out
    assert "cite the urls" in out.lower()


async def test_web_search_tool_handles_no_results(monkeypatch):
    set_identity("u", str(uuid.uuid4()))
    async def fake(query, max_results=5, include_domains=None):
        return []
    monkeypatch.setattr(tools, "web_search", fake)
    out = await tools.web_search_tool.ainvoke({"query": "anything"})
    assert "unavailable" in out.lower()


def test_graph_for_default_is_cached_singleton():
    from app.api import ws
    assert ws.graph_for(False, False) is ws.graph()           # default path reuses the singleton
    g = ws.graph_for(True, True)                               # toggles on → a distinct per-request graph
    assert g is not ws.graph()
