import json
import re
import uuid
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
import app.api.ws as wsmod
import app.agent.followups as fu
from app.graph.graph import build_graph
from app.main import app


def _stub_followups():
    """Inject a fake follow-up model so tests don't reach the real Qwen."""
    class F(GenericFakeChatModel):
        async def ainvoke(self, *a, **k):
            return AIMessage(content='["Draft it for LinkedIn", "Suggest 3 more", "Make it warmer"]')
    fu._model = F(messages=iter([AIMessage(content="x")]))


def _h(user, org):
    return {"X-User-Id": user, "X-Tenant-Id": org}


def _new_conv(client, user, org):
    return client.post("/conversations", json={"title": "t"}, headers=_h(user, org)).json()["conversation"]["id"]


def test_ws_streams_tokens_and_persists():
    wsmod._graph = build_graph(model=GenericFakeChatModel(messages=iter([AIMessage(content="Hi NPO")])))
    _stub_followups()
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    with TestClient(app) as client:                       # lifespan opens pool in the portal loop
        conv = _new_conv(client, user, org)
        with client.websocket_connect("/ws/chat", headers=_h(user, org)) as wsconn:
            wsconn.send_text(json.dumps({"action": "send", "conversation_id": conv, "content": "hello"}))
            frames = []
            while True:
                f = json.loads(wsconn.receive_text())
                frames.append(f)
                if f["type"] in ("done", "error"):
                    break
    assert frames[-1]["type"] == "done", f"got {frames[-1]}"
    assert "".join(f["data"] for f in frames if f["type"] == "token") == "Hi NPO"

    done_frame = frames[-1]
    assert "message" in done_frame, f"done frame missing 'message': {done_frame}"
    msg = done_frame["message"]
    assert msg["conversation_id"] == conv
    assert msg["role"] == "assistant"
    assert msg["content"] == "Hi NPO"
    uuid.UUID(msg["id"])  # raises if not a valid UUID
    assert done_frame.get("followups") == ["Draft it for LinkedIn", "Suggest 3 more", "Make it warmer"]


def test_ws_resume_replays_completed_generation():
    """After a turn finishes (within the grace window), a reconnect + `resume` replays it —
    the response is never lost on reload."""
    wsmod._graph = build_graph(model=GenericFakeChatModel(messages=iter([AIMessage(content="Resumed reply")])))
    _stub_followups()
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    with TestClient(app) as client:
        conv = _new_conv(client, user, org)
        with client.websocket_connect("/ws/chat", headers=_h(user, org)) as ws1:
            ws1.send_text(json.dumps({"action": "send", "conversation_id": conv, "content": "hello"}))
            while True:
                if json.loads(ws1.receive_text())["type"] in ("done", "error"):
                    break
        # Reconnect (simulating a page reload) and resume.
        with client.websocket_connect("/ws/chat", headers=_h(user, org)) as ws2:
            ws2.send_text(json.dumps({"action": "resume", "conversation_id": conv}))
            frames = []
            while True:
                f = json.loads(ws2.receive_text())
                frames.append(f)
                if f["type"] in ("done", "error", "no_active_stream"):
                    break
    types = [f["type"] for f in frames]
    assert "resume_replay" in types, f"got {types}"
    replay = next(f for f in frames if f["type"] == "resume_replay")
    assert replay["content"] == "Resumed reply" and replay["conversation_id"] == conv
    assert frames[-1]["type"] == "done" and frames[-1]["message"]["content"] == "Resumed reply"


def test_ws_resume_no_active_stream():
    org, user = str(uuid.uuid4()), str(uuid.uuid4())
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat", headers=_h(user, org)) as ws:
            ws.send_text(json.dumps({"action": "resume", "conversation_id": str(uuid.uuid4())}))
            f = json.loads(ws.receive_text())
    assert f["type"] == "no_active_stream"


def test_ws_resume_rejects_cross_tenant():
    """Org B must NOT be able to resume Org A's generation (IDOR / cross-tenant leak)."""
    wsmod._graph = build_graph(model=GenericFakeChatModel(messages=iter([AIMessage(content="A private reply")])))
    _stub_followups()
    org_a, user_a = str(uuid.uuid4()), str(uuid.uuid4())
    org_b, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    with TestClient(app) as client:
        conv_a = _new_conv(client, user_a, org_a)
        with client.websocket_connect("/ws/chat", headers=_h(user_a, org_a)) as wsa:
            wsa.send_text(json.dumps({"action": "send", "conversation_id": conv_a, "content": "hi"}))
            while True:
                if json.loads(wsa.receive_text())["type"] in ("done", "error"):
                    break
        with client.websocket_connect("/ws/chat", headers=_h(user_b, org_b)) as wsb:
            wsb.send_text(json.dumps({"action": "resume", "conversation_id": conv_a}))
            f = json.loads(wsb.receive_text())
    assert f["type"] == "no_active_stream", f"cross-tenant resume leaked: {f}"


def test_ws_send_rejects_foreign_conversation():
    """Sending to a conversation the caller doesn't own is rejected (RLS-scoped ownership check)."""
    org_a, user_a = str(uuid.uuid4()), str(uuid.uuid4())
    org_b, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    with TestClient(app) as client:
        conv_a = _new_conv(client, user_a, org_a)
        with client.websocket_connect("/ws/chat", headers=_h(user_b, org_b)) as wsb:
            wsb.send_text(json.dumps({"action": "send", "conversation_id": conv_a, "content": "hijack"}))
            f = json.loads(wsb.receive_text())
    assert f["type"] == "error" and "not found" in f["data"], f"foreign send not rejected: {f}"


def test_aimessagechunk_with_toolcall_still_has_content():
    """ws.py streams a token whenever the chunk's content is truthy, regardless of any tool call.
    Pin the predicate: a chunk carrying BOTH caption text AND a tool-call open-brace must still stream."""
    from langchain_core.messages import AIMessageChunk
    # A chunk that carries caption text AND opens a tool call (the caption-first shape).
    chunk = AIMessageChunk(content="Here's the caption",
                           tool_call_chunks=[{"name": "generate_image", "args": "{", "id": "1", "index": 0}])
    # ws.py streams a token whenever content is truthy (regardless of tool_calls), so the caption streams.
    assert bool(getattr(chunk, "content", ""))
    assert getattr(chunk, "tool_calls", None) is not None or chunk.tool_call_chunks  # it really does carry a tool call


CAP = ("POV: Your laptop is your new bestie ☕️✨ #CGLabs #CafeCodeUp #CommunityFirst")


def test_strip_repeated_caption_removes_model_paste():
    """draft_post streamed the caption (1st copy); the model then pasted it again with a lead-in.
    The dedup keeps the streamed copy once and drops the model's redundant paste + artifacts."""
    buffer = (
        f"{CAP}"                                  # streamed live by draft_post (first occurrence)
        "Got it! Here's the Gen-Z-friendly caption for your post:\n\n"
        f"\"{CAP}\"\n\n"                           # the model's redundant paste (quoted)
        "Now, shall I regenerate the images to match this new vibe?"
    )
    out = wsmod._strip_repeated_caption(buffer, CAP)
    assert out.count(CAP) == 1                      # caption appears exactly once
    assert "Now, shall I regenerate the images" in out  # the useful follow-up survives
    assert "Here's the Gen-Z-friendly caption" not in out  # dangling lead-in cleaned
    assert '""' not in out and '“”' not in out      # empty quote pairs cleaned


def test_strip_captions_from_narration_removes_all_copies():
    """The caption already streamed live; the buffered closing narration pastes it again (possibly twice).
    We strip EVERY copy + lead-in artifacts so only the agent's intro/outro line remains."""
    # The 9B re-pastes the caption with its NEWLINES COLLAPSED to spaces — the real duplicate-caption bug.
    collapsed = re.sub(r"\s+", " ", CAP)
    narr = (
        "Here is the caption:\n\n"
        f"\"{CAP}\"\n\n"
        f"{collapsed}\n\n"
        "Want me to generate a matching image? 🏴‍☠️"
    )
    out = wsmod._strip_captions_from_narration(narr, [CAP])
    assert CAP not in out                                  # no verbatim copy survives
    assert collapsed not in out                             # nor the whitespace-collapsed re-paste
    assert "Want me to generate a matching image" in out   # the useful outro survives
    assert "caption:" not in out                            # dangling "…caption…:" lead-in cleaned


def test_strip_repeated_caption_noop_when_shown_once():
    buffer = f"Great idea! Here's your post:\n\n{CAP}\n\nWant me to add images?"
    assert wsmod._strip_repeated_caption(buffer, CAP) == buffer   # single copy → unchanged


def test_strip_repeated_caption_noop_when_not_verbatim():
    # Fallback path (no live stream): caption isn't in the buffer verbatim → leave untouched.
    buffer = "Here's a paraphrased version of your post about laptops and cafes."
    assert wsmod._strip_repeated_caption(buffer, CAP) == buffer


def test_superseded_drafts_removed_keeping_final():
    """The agent redrafted 3× in one turn (all streamed live). Only the FINAL caption should remain;
    the earlier superseded drafts are stripped from the buffer. Mirrors the ws.py post-stream cleanup."""
    import re
    d1 = "Draft one: come to our beach cleanup. #cleanup"
    d2 = "Draft two: join the beach cleanup squad! #cleanup"
    final = "Draft three: celebrate our 100th volunteer! 🎉 #volunteers"
    draft_sink = [d1, d2, final]
    buffer = f"{d1}\n\n{d2}\n\n{final}\n\nHere is your post!"

    caption = draft_sink[-1].strip()
    for old in draft_sink[:-1]:
        old = old.strip()
        if old and old != caption:
            buffer = buffer.replace(old, "")
    if wsmod._caption_shown(buffer, caption):
        buffer = wsmod._strip_repeated_caption(buffer, caption)
    buffer = re.sub(r'\n{3,}', "\n\n", buffer).strip()

    assert final in buffer
    assert d1 not in buffer and d2 not in buffer       # superseded drafts gone
    assert buffer.count("#cleanup") == 0               # their hashtags gone too
    assert "Here is your post!" in buffer              # the agent's outro survives


# --- _drop_residual_caption: the wording-agnostic second-caption strip -------------------------------
# These pin the real bug found in prod (conversation a15797dc): draft_post streamed the canonical caption
# (saved + published), then the 9B re-rendered it a SECOND time in its narration in DIFFERENT wording, so
# the token-based _strip_captions_from_narration couldn't catch it → two captions shown, publish diverged.

GREEK_CAP = ("Μια στιγμή που δείχνει πόσο μεγάλη είναι η οικογένειά μας. 🌍✨ "
             "Στο Ελπίδα, η αγάπη δεν έχει σύνορα. #Ελπίδα #ΠαιδιάΜεΚαρκίνο #Solidarity")
ENGLISH_REPASTE = ("A moment that shows how big our family truly is. 🌍✨\n\n"
                   "At ELPIDA, love knows no borders.\n\n"
                   "#ELPIDA #ChildrenWithCancer #Solidarity")


def test_drop_residual_caption_removes_translated_repaste():
    """The exact prod case: canonical is Greek; the model adds an English translation (its own tokens,
    so token-strip misses it). Structural strip drops it + its lead-in, leaving only the intro."""
    narr = f"Here is your Global Solidarity post, in English:\n\n{ENGLISH_REPASTE}"
    out = wsmod._drop_residual_caption(narr, GREEK_CAP)
    assert "ELPIDA" not in out and "#ELPIDA" not in out      # the translated caption block is gone
    assert "love knows no borders" not in out                # …entirely
    assert "in English:" not in out                          # the dangling "…:" lead-in is removed too
    assert out.strip() == ""                                 # nothing but (removed) caption → empty intro


def test_drop_residual_caption_removes_same_language_paraphrase():
    """Single-language manifestation: a reworded re-paste (high word-overlap with the canonical) is dropped."""
    canonical = "Join our beach cleanup this Saturday and help protect our shoreline for everyone."
    paraphrase = "Come to the beach cleanup on Saturday and help us protect the shoreline for all."
    narr = f"Sounds good! Here's the shorter version:\n\n{paraphrase}"
    out = wsmod._drop_residual_caption(narr, canonical)
    assert "protect" not in out and "shoreline" not in out   # the paraphrased caption block is gone
    assert "shorter version" not in out                       # lead-in removed


def test_drop_residual_caption_keeps_short_intro():
    """A genuine one-line intro (no hashtags, short, low overlap) must survive untouched."""
    narr = "Done — I've made it warmer and tightened the opening."
    out = wsmod._drop_residual_caption(narr, GREEK_CAP)
    assert out == narr


def test_looks_like_caption_body_signals():
    assert wsmod._looks_like_caption_body("#a #b #c something", "")                 # hashtag run
    assert wsmod._looks_like_caption_body("x" * 130, "")                            # long block
    assert not wsmod._looks_like_caption_body("Done, updated it.", GREEK_CAP)       # short intro
    assert not wsmod._looks_like_caption_body("", GREEK_CAP)                        # empty
