import json
import uuid
import pytest
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.agent import consolidate
from app.repo import memory as mem_repo, profile as profile_repo

pytestmark = pytest.mark.asyncio


def _fake(text):
    class F(GenericFakeChatModel):
        async def ainvoke(self, *a, **k): return AIMessage(content=text)
    return F(messages=iter([AIMessage(content=text)]))


def test_is_feedback_gates_durable_turns():
    for m in ["from now on only Instagram", "be the voice of our org", "stop being so vague",
              "always sign off with our link", "too corporate"]:
        assert consolidate.is_feedback(m), m
    for m in ["lets go with 2", "draft a post about our camp", "what programs do we run?"]:
        assert not consolidate.is_feedback(m), m


def test_parse_filters_unknown_kinds_and_caps():
    raw = json.dumps([
        {"kind": "brand_voice", "value": "warm, specific, names our programs"},
        {"kind": "bogus", "value": "x"},                       # unknown kind dropped
        {"kind": "style_rule", "value": ""},                   # empty dropped
        {"kind": "default_platform", "value": "Instagram"},
        {"kind": "fact", "value": "a"}, {"kind": "fact", "value": "b"}, {"kind": "fact", "value": "c"},
    ])
    out = consolidate._parse(raw)
    assert len(out) == 3                                        # capped at 3
    assert {"kind": "brand_voice", "value": "warm, specific, names our programs"} in out


@pytest.mark.usefixtures("db_pool")
async def test_consolidate_persists_voice_and_default_platform(db_pool):
    org = str(uuid.uuid4())
    consolidate._model = _fake(json.dumps([
        {"kind": "brand_voice", "value": "specific and warm; names our programs; no vague platitudes"},
        {"kind": "default_platform", "value": "I only post on Instagram"},
        {"kind": "style_rule", "value": "avoid generic platitudes"},
    ]))
    saved = await consolidate.consolidate_memory(org, "be the voice of my org, stop being vague, only IG", "old draft")
    kinds = {s["kind"] for s in saved}
    assert {"brand_voice", "default_platform", "style_rule"} <= kinds
    # brand_voice landed in memory with source=inferred
    voice = next(iter(await mem_repo.list_entries(org, "brand_voice")), None)
    assert voice and "vague" in voice["value"]["descriptor"] and voice["source"] == "inferred"
    # default_platform normalized onto the profile
    prof = await profile_repo.get_profile(org)
    assert prof["default_platform"] == "instagram"


@pytest.mark.usefixtures("db_pool")
async def test_consolidate_noop_when_nothing_durable(db_pool):
    org = str(uuid.uuid4())
    consolidate._model = _fake("[]")
    assert await consolidate.consolidate_memory(org, "make this one shorter", "draft") == []
    assert await mem_repo.list_entries(org) == []
