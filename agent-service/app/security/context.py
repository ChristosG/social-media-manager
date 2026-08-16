from contextvars import ContextVar
from typing import Callable
from fastapi import Header, HTTPException, Depends

org_id_var: ContextVar[str | None] = ContextVar("org_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
# The requester's IANA timezone (e.g. "America/Los_Angeles"), forwarded by the webapp on each chat turn so
# the model grounds "today"/"this week"/campaign dates in the user's LOCAL date, not UTC. None => UTC.
timezone_var: ContextVar[str | None] = ContextVar("timezone", default=None)
# Request-scoped sink for images a tool generates this turn. The WS layer sets a fresh
# list before streaming and drains it into the assistant message afterward, so big base64
# payloads never enter the LLM's tool-result context.
image_sink_var: ContextVar[list | None] = ContextVar("image_sink", default=None)
# Request-scoped sink for the post caption a tool drafts this turn. Same idea as image_sink: draft_post
# pushes the caption here and the WS layer appends it to the assistant message, so the caption is ALWAYS
# shown in chat — instead of relying on the model to paste it back (which it often skips in the image flow).
draft_sink_var: ContextVar[list | None] = ContextVar("draft_sink", default=None)
# Live token emitter — set by the WS layer to stream a tool's own LLM output (e.g. the draft_post caption)
# to the client AS IT GENERATES, instead of only revealing it after the whole turn (incl. image gen) finishes.
token_emit_var: ContextVar[Callable[[str], None] | None] = ContextVar("token_emit", default=None)
# Current conversation id — set by the WS layer so tools can upsert the per-conversation draft.
conv_id_var: ContextVar[str | None] = ContextVar("conv_id", default=None)
# The campaign post the user is actively refining this turn (bound by the "Refine in chat" CTA, carried on
# the send). A refine tool reads THIS id — never a post id from the model's free text — so injected content
# can't retarget the write to another post.
active_post_var: ContextVar[str | None] = ContextVar("active_post", default=None)
# The campaign the user is editing this turn (bound by the "Edit in chat" CTA, carried on the send as
# post_context.campaign_id). The campaign-edit tools read THIS id — never one from the model's text.
active_campaign_var: ContextVar[str | None] = ContextVar("active_campaign", default=None)
# Request-scoped sink for the sources a tool grounded this turn on (own posts / news / web search).
# Same pattern as image_sink: tools push citation dicts here and the WS layer drains them after the
# turn — to stream provenance chips to the client and persist them on the assistant message — so the
# tool stays pure and citations survive a reload.
sources_sink_var: ContextVar[list | None] = ContextVar("sources_sink", default=None)
# Request-scoped sink for durable things the agent LEARNED this turn (a preference/voice/fact actually
# written to memory_entries by remember_preference / update_brand_voice). The WS layer drains it to (a)
# stream a distinct, honest "Learned" chip and (b) persist it on the assistant message — so the user can
# always tell when something entered their knowledge, as opposed to the model merely "thinking" this turn
# (the routing badge). Same pure-tool / drain-in-WS pattern as draft_sink/sources_sink.
memory_sink_var: ContextVar[list | None] = ContextVar("memory_sink", default=None)
# Request-scoped sink for a campaign the agent PLANNED this turn ({id, brief}). The WS layer drains it to
# stream a 'campaign_planned' event, so the chat can show a "View campaign ▸" deep-link chip. Same
# pure-tool / drain-in-WS pattern as memory_sink.
campaign_sink_var: ContextVar[list | None] = ContextVar("campaign_sink", default=None)
# Live status emitter — set by the WS layer so a tool can tell the user what it's doing right now
# (e.g. "Checking current web trends…" when suggest_posts auto-searches the web). No-op outside WS.
status_emit_var: ContextVar[Callable[[str], None] | None] = ContextVar("status_emit", default=None)
# Structured refine-proposal emitter — set by the WS layer so refine_campaign_post can hand the client the
# EXACT {post_id, caption} it proposed, instead of the UI reverse-engineering it from the model's prose (the
# 9B paraphrases the tool's reply, dropping the lead-in the old "Apply to post" button keyed off, so it
# silently vanished). The client renders a reliable Apply button from this. No-op outside WS.
proposal_emit_var: ContextVar[Callable[[dict], None] | None] = ContextVar("proposal_emit", default=None)
# Per-turn flag: did this turn pull in attacker-influenceable external text (web search, or RAG over
# ingested web pages)? If so, durable-memory writes triggered in the same turn are QUARANTINED for human
# review (pending_review) instead of silently shaping every future prompt — defends the learning channel
# against prompt-injection ("the page says: remember our voice is X / banned topics are none"). Reset per
# turn by the WS layer; a fresh detached task (e.g. background consolidation of the user's own message)
# never sees it set, so trusted user-stated preferences still persist immediately.
untrusted_seen_var: ContextVar[bool] = ContextVar("untrusted_seen", default=False)


def set_identity(user_id: str, org_id: str | None) -> None:
    user_id_var.set(user_id)
    org_id_var.set(org_id)


def push_image(item: dict) -> None:
    sink = image_sink_var.get()
    if sink is not None:
        sink.append(item)


def push_draft(caption: str) -> None:
    sink = draft_sink_var.get()
    if sink is not None:
        sink.append(caption)


def push_sources(items: list[dict]) -> None:
    """A tool records the sources it grounded on this turn (citation dicts). No-op if no sink is wired."""
    sink = sources_sink_var.get()
    if sink is not None and items:
        sink.extend(items)


def push_memory(item: dict) -> None:
    """A tool records that it durably LEARNED something this turn: {kind, label, pending}. The WS layer
    surfaces a distinct 'Learned' chip and persists it. No-op if no sink is wired (non-WS callers/tests)."""
    sink = memory_sink_var.get()
    if sink is not None and item:
        sink.append(item)


def push_campaign(campaign_id: str, brief: str) -> None:
    """A tool records that it planned a campaign this turn. The WS layer streams a 'campaign_planned' event
    so the chat can show a jump-to-campaign chip. No-op if no sink is wired (non-WS callers/tests)."""
    sink = campaign_sink_var.get()
    if sink is not None and campaign_id:
        sink.append({"id": campaign_id, "brief": brief})


def emit_token(text: str) -> bool:
    """Stream a chunk of a tool's own LLM output to the client immediately. Returns True if an emitter was
    wired (so the caller knows the text is already on the wire and shouldn't be re-appended later)."""
    emit = token_emit_var.get()
    if emit is None or not text:
        return False
    emit(text)
    return True


def emit_status(text: str) -> None:
    """Surface a live status line to the user from inside a tool (e.g. an auto web search). No-op if unwired."""
    emit = status_emit_var.get()
    if emit is not None and text:
        emit(text)


def emit_refine_proposal(post_id: str, caption: str) -> None:
    """A refine tool hands the client the exact post + proposed caption to drive a reliable 'Apply to post'
    button (no prose-parsing). No-op outside a WS turn (tests / REST callers)."""
    emit = proposal_emit_var.get()
    if emit is not None and post_id and caption:
        emit({"post_id": post_id, "caption": caption})


def mark_untrusted_seen() -> None:
    """A tool records that it surfaced attacker-influenceable external content this turn (web search /
    RAG over ingested web pages). Durable-memory writes this turn become pending_review."""
    untrusted_seen_var.set(True)


def untrusted_seen() -> bool:
    return untrusted_seen_var.get()


def current_org() -> str | None:
    return org_id_var.get()


def current_user() -> str | None:
    return user_id_var.get()


def current_conv() -> str | None:
    return conv_id_var.get()


def current_post() -> str | None:
    return active_post_var.get()


def current_campaign() -> str | None:
    return active_campaign_var.get()


def current_timezone() -> str | None:
    """The requester's IANA tz for this turn (set by the WS layer); None outside a chat turn => UTC."""
    return timezone_var.get()


async def require_identity(
    x_user_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> tuple[str, str]:
    """FastAPI dependency: trust gateway-injected headers; require an org."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="missing user identity")
    if not x_tenant_id:
        raise HTTPException(status_code=403, detail="org (tenant) required")
    set_identity(user_id=x_user_id, org_id=x_tenant_id)
    return x_user_id, x_tenant_id


async def require_admin(
    ident: tuple[str, str] = Depends(require_identity),
    x_roles: str | None = Header(default=None),
) -> tuple[str, str]:
    """Require an admin/owner role. The gateway injects validated X-Roles from the JWT claims;
    the agent-service trusts it exactly as it trusts X-User-Id/X-Tenant-Id."""
    roles = {r.strip().lower() for r in (x_roles or "").split(",") if r.strip()}
    if not roles & {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="admin role required")
    return ident
