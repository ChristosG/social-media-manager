import uuid
import pytest
from app.security.context import set_identity
from app.repo import memory as mem_repo
from app.graph.context import build_system_prompt
import app.agent.tools as tools


@pytest.mark.usefixtures("db_pool")
async def test_remember_preference_persists_each_kind():
    org = str(uuid.uuid4()); set_identity("u", org)
    await tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "party politics"})
    await tools.remember_preference.ainvoke({"kind": "style_rule", "value": "always sign off with 🐾"})
    await tools.remember_preference.ainvoke({"kind": "cta_pref", "value": "end with our donation link"})
    kinds = {e["kind"] for e in await mem_repo.list_entries(org)}
    assert {"banned_topic", "style_rule", "cta_pref"} <= kinds
    banned = await mem_repo.list_entries(org, "banned_topic")
    assert banned[0]["value"]["topic"] == "party politics"
    assert banned[0]["source"] == "user_correction"


@pytest.mark.usefixtures("db_pool")
async def test_remember_preference_dedups():
    org = str(uuid.uuid4()); set_identity("u", org)
    await tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "Politics"})
    msg = await tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "politics"})
    assert "Already noted" in msg
    assert len(await mem_repo.list_entries(org, "banned_topic")) == 1


@pytest.mark.usefixtures("db_pool")
async def test_remember_preference_rejects_unknown_kind():
    org = str(uuid.uuid4()); set_identity("u", org)
    msg = await tools.remember_preference.ainvoke({"kind": "mood", "value": "happy"})
    assert "update_brand_voice" in msg
    assert await mem_repo.list_entries(org) == []


def test_style_rule_and_cta_injected_into_system_prompt():
    memory = [
        {"kind": "style_rule", "value": {"rule": "always sign off with 🐾"}, "key": None},
        {"kind": "cta_pref", "value": {"cta": "end with our donation link"}, "key": None},
    ]
    sp = build_system_prompt(memory, None, [])
    assert "STYLE RULES" in sp and "🐾" in sp
    assert "CALL-TO-ACTION" in sp and "donation link" in sp
