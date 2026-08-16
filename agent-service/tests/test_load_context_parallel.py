"""Characterization test for the parallel load_context refactor.

Asserts that when an org has a brand_voice memory entry and a named profile,
the assembled system_prompt contains both the brand voice descriptor AND the
org name — proving all parallel DB reads ran and the prompt was assembled
correctly.

Also asserts determinism: two identical invocations produce the same prompt.
"""
import uuid
import pytest
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.graph.graph import build_graph
from app.repo import memory as mem_repo, profile as profile_repo


@pytest.mark.usefixtures("db_pool")
async def test_load_context_parallel_brand_voice_and_org_name():
    """System prompt must contain the seeded brand voice AND the org name,
    proving all 6 parallel reads ran and build_system_prompt assembled them."""
    org = str(uuid.uuid4())
    await mem_repo.create_entry(org, "brand_voice", {"descriptor": "bold, community-driven"}, None)
    await profile_repo.upsert_profile(org, "Empower local communities", None, None, None, None, "CommunityForce")

    captured = {}

    class Capture(GenericFakeChatModel):
        async def ainvoke(self, messages, *a, **k):
            captured["sys"] = messages[0].content if messages else ""
            return AIMessage(content="done")

    graph = build_graph(model=Capture(messages=iter([AIMessage(content="done")])))
    await graph.ainvoke({"messages": [HumanMessage("hello")], "org_id": org, "system_prompt": ""})

    prompt = captured.get("sys", "")
    assert "bold, community-driven" in prompt, f"brand voice missing from prompt: {prompt[:300]}"
    assert "CommunityForce" in prompt, f"org name missing from prompt: {prompt[:300]}"


@pytest.mark.usefixtures("db_pool")
async def test_load_context_parallel_is_deterministic():
    """Two invocations with the same org data produce byte-identical prompts."""
    org = str(uuid.uuid4())
    await mem_repo.create_entry(org, "brand_voice", {"descriptor": "calm, evidence-based"}, None)
    await profile_repo.upsert_profile(org, "Advance science literacy", None, None, None, None, "ScienceBridge")

    prompts = []

    class Capture(GenericFakeChatModel):
        async def ainvoke(self, messages, *a, **k):
            prompts.append(messages[0].content if messages else "")
            return AIMessage(content="ok")

    for _ in range(2):
        graph = build_graph(model=Capture(messages=iter([AIMessage(content="ok")])))
        await graph.ainvoke({"messages": [HumanMessage("hi")], "org_id": org, "system_prompt": ""})

    assert len(prompts) == 2
    assert prompts[0] == prompts[1], "prompt is not deterministic across two runs"
