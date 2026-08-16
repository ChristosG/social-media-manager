import json
import uuid
import pytest
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.security.context import set_identity
from app.repo import ledger as ledger_repo, memory as mem_repo
import app.agent.tools as tools


def _fake(text):
    class F(GenericFakeChatModel):
        async def ainvoke(self, *a, **k): return AIMessage(content=text)
    return F(messages=iter([AIMessage(content=text)]))


@pytest.mark.usefixtures("db_pool")
async def test_suggest_posts_writes_ledger_and_dedups():
    org = str(uuid.uuid4()); set_identity("u", org)
    tools._model = _fake(json.dumps([{"title": "Beach cleanup", "angle": "rally volunteers"}]))
    out = await tools.suggest_posts.ainvoke({"count": 1, "brief": "cleanup"})
    assert "Beach cleanup" in out
    assert any(p["title"] == "Beach cleanup" for p in await ledger_repo.list_posts(org))


@pytest.mark.usefixtures("db_pool")
async def test_draft_post_uses_voice_and_saves():
    org = str(uuid.uuid4()); set_identity("u", org)
    await mem_repo.create_entry(org, "brand_voice", {"descriptor": "playful"}, None)
    tools._model = _fake("Ahoy! Join our crew.")
    out = await tools.draft_post.ainvoke({"idea_title": "Volunteer drive", "platform": "linkedin"})
    assert "Ahoy! Join our crew." in out   # caption is wrapped with a 'shown to user' instruction now
    assert any(p["status"] == "drafted" and p["platform"] == "linkedin" for p in await ledger_repo.list_posts(org))


def test_is_revision_distinguishes_tweaks_from_new_posts():
    # Revision instructions → True (now incl. CTA/sign-off asks, which must REVISE not draft-fresh)
    for a in ["make it warmer", "shorter please", "more Gen-Z", "reword this", "for LinkedIn instead",
              "punchier", "add more emoji", "less formal", "add a call to action", "add a CTA",
              "sign off with our donation link"]:
        assert tools._is_revision(a), a
    # New-post briefs → False (draft fresh, don't revise the previous caption)
    for a in ["celebrate our 100th volunteer", "a post about our beach cleanup event",
              "announce the new water program", ""]:
        assert not tools._is_revision(a), a


@pytest.mark.usefixtures("db_pool")
async def test_show_current_post_surfaces_draft_verbatim(db_pool):
    """'give me the caption' → show_current_post pushes the current draft into the draft sink so it's shown
    verbatim (no 9B retyping)."""
    from app.security.context import conv_id_var, draft_sink_var
    from app.repo import conversation_drafts as drafts
    org = str(uuid.uuid4()); conv = str(uuid.uuid4())
    set_identity("u", org); conv_id_var.set(conv)
    sink: list = []; draft_sink_var.set(sink)
    await drafts.upsert_caption(org, conv, "Arrr, the FULL current caption ⚓️ #crew")
    out = await tools.show_current_post.ainvoke({})
    assert sink == ["Arrr, the FULL current caption ⚓️ #crew"]
    assert "do NOT repeat" in out
    conv_id_var.set(None); draft_sink_var.set(None)


@pytest.mark.usefixtures("db_pool")
async def test_draft_post_revises_only_on_revision_cue(db_pool, monkeypatch):
    """draft_post feeds the previous caption ONLY when the instruction is a revision; a new-topic brief
    drafts fresh (previous=''), so the model can't echo/ramble the unrelated prior caption."""
    from app.security.context import conv_id_var
    from app.repo import conversation_drafts as drafts
    org = str(uuid.uuid4()); conv = str(uuid.uuid4())
    set_identity("u", org); conv_id_var.set(conv)
    await drafts.upsert_caption(org, conv, "PREVIOUS caption about a beach cleanup.")
    seen = {}
    real = tools.build_draft_prompt
    monkeypatch.setattr(tools, "build_draft_prompt",
                        lambda *a, **k: (seen.update(previous=k.get("previous", "")), real(*a, **k))[1])
    tools._model = _fake("Fresh post text.")

    await tools.draft_post.ainvoke({"idea_title": "100th Volunteer", "platform": "linkedin",
                                    "angle": "celebrate our 100th volunteer"})
    assert seen["previous"] == ""                                  # new topic → drafted fresh (no echo)

    await tools.draft_post.ainvoke({"idea_title": "100th Volunteer", "platform": "linkedin",
                                    "angle": "make it warmer"})
    assert seen["previous"] == "Fresh post text."                  # revision → current caption fed in
    conv_id_var.set(None)


@pytest.mark.usefixtures("db_pool")
async def test_draft_post_uses_registry_platform(db_pool):
    """A platform added to the registry is immediately draftable — no redeploy."""
    org = str(uuid.uuid4()); set_identity("u", org)
    from app.repo import capabilities as cap_repo
    await cap_repo.create_capability(org, "platform", "threads",
                                     {"label": "Threads", "max_chars": 500, "tone": "casual", "hashtags": "1-2"})
    tools._model = _fake("Hello from Threads!")
    out = await tools.draft_post.ainvoke({"idea_title": "Volunteer drive", "platform": "threads"})
    assert "Hello from Threads!" in out
    assert any(p["status"] == "drafted" and p["platform"] == "threads" for p in await ledger_repo.list_posts(org))


@pytest.mark.usefixtures("db_pool")
async def test_update_brand_voice_persists():
    org = str(uuid.uuid4()); set_identity("u", org)
    await tools.update_brand_voice.ainvoke({"descriptor": "warm, grassroots"})
    v = next(e for e in await mem_repo.list_entries(org, "brand_voice"))
    assert v["value"]["descriptor"] == "warm, grassroots"


@pytest.mark.usefixtures("db_pool")
async def test_list_ledger_reports_status():
    org = str(uuid.uuid4()); set_identity("u", org)
    await ledger_repo.create_post(org, "Gala", None, "suggested")
    assert "Gala" in await tools.list_ledger.ainvoke({})


@pytest.mark.usefixtures("db_pool")
async def test_answer_about_org_includes_programs():
    """answer_about_org must read the programs table, not just the profile mission."""
    from app.db.pool import org_tx
    org = str(uuid.uuid4()); set_identity("u", org)
    async with org_tx(org) as c:
        await c.execute("INSERT INTO org_profile(org_id, mission) VALUES($1, $2)",
                        uuid.UUID(org), "We rescue abandoned dogs and cats")
        await c.execute("INSERT INTO programs(org_id, name, description) VALUES($1, $2, $3)",
                        uuid.UUID(org), "Foster-to-Adopt", "Temporary fosters become permanent homes.")
    out = await tools.answer_about_org.ainvoke({"question": "what programs do we run?"})
    assert "Foster-to-Adopt" in out and "rescue abandoned dogs" in out
