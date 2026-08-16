import uuid
import pytest
from app.security.context import set_identity, memory_sink_var
import app.agent.tools as tools


@pytest.mark.usefixtures("db_pool")
async def test_remember_preference_emits_learned_signal():
    org = str(uuid.uuid4()); set_identity("u", org)
    sink: list = []
    memory_sink_var.set(sink)
    await tools.remember_preference.ainvoke({"kind": "style_rule", "value": "always talk in first person"})
    assert sink == [{"kind": "style_rule", "label": "always talk in first person", "pending": False}]


@pytest.mark.usefixtures("db_pool")
async def test_update_brand_voice_emits_learned_signal():
    org = str(uuid.uuid4()); set_identity("u", org)
    sink: list = []
    memory_sink_var.set(sink)
    await tools.update_brand_voice.ainvoke({"descriptor": "warm and grassroots"})
    assert sink == [{"kind": "brand_voice", "label": "warm and grassroots", "pending": False}]


@pytest.mark.usefixtures("db_pool")
async def test_dedup_does_not_emit_learned_signal():
    # The second identical save is a no-op ("Already noted") and must NOT claim it learned anything.
    org = str(uuid.uuid4()); set_identity("u", org)
    sink: list = []
    memory_sink_var.set(sink)
    await tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "politics"})
    sink.clear()
    msg = await tools.remember_preference.ainvoke({"kind": "banned_topic", "value": "Politics"})
    assert "Already noted" in msg
    assert sink == []
