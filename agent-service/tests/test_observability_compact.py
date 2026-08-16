"""The observability proxy must NOT dump the whole message history at every step (the 'walls of
repeated JSON' problem) — it shows a compact digest by default and keeps the raw for on-demand."""
from app.api.observability import _classify_level, _compact, _msg_preview


def _history():
    return {"messages": [
        {"type": "system", "content": "You are an assistant."},
        {"type": "human", "content": "SOURCES: ...long grounding block...\n\nUser message: write a post"},
        {"type": "ai", "content": "", "tool_calls": [{"name": "draft_post"}]},
    ]}


def test_compact_collapses_message_history_to_a_digest():
    out = _compact("agent", "node", _history(), is_output=False)
    assert "3 message(s)" in out and "incl. system prompt" in out
    # The latest turns are previewed, and the prepended grounding block is stripped from the human line.
    assert "write a post" in out and "long grounding block" not in out
    assert "calls draft_post" in out
    # Crucially, it is NOT the full indented JSON dump.
    assert '"messages"' not in out


def test_compact_tool_input_drops_plumbing_keys():
    out = _compact("draft_post", "tool",
                   {"idea_title": "Gala", "platform": "linkedin", "messages": [1, 2], "org_id": "x"},
                   is_output=False)
    assert "Gala" in out and "linkedin" in out
    assert "messages" not in out and "org_id" not in out


def test_compact_tool_output_is_the_text():
    assert _compact("draft_post", "tool", "Here is your caption.", is_output=True) == "Here is your caption."


def test_msg_preview_strips_grounding_prefix():
    p = _msg_preview({"type": "human", "content": "BLOCK\n\nUser message: hello there"})
    assert p == "human: hello there"


def test_interrupt_spans_render_as_paused_not_error():
    # The HITL publish gate pauses the graph via interrupt(); LangGraph propagates that as an
    # exception, so Langfuse records the span as ERROR — but it is an intended pause, not a failure.
    level, msg = _classify_level("ERROR", "(Interrupt(value={'kind': 'publish_proposal', 'caption': '...'}),)")
    assert level == "PAUSED"
    assert "approval" in msg.lower()


def test_real_errors_keep_level_and_surface_the_message():
    level, msg = _classify_level("ERROR", "Connection error.")
    assert level == "ERROR"
    assert msg == "Connection error."


def test_default_level_carries_no_status_message():
    assert _classify_level("DEFAULT", "") == ("DEFAULT", None)
    assert _classify_level(None, None) == (None, None)
