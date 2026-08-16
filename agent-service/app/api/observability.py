"""In-app window into Langfuse traces — so the agent's steps are visible in our own UI,
not only in the Langfuse dashboard.

The agent-service is the only component that holds the Langfuse secret key, so it proxies
the Langfuse *public API* (Basic-auth pk:sk) and — critically — scopes every query to the
caller's org. We trace each turn with `langfuse_user_id = org_id`, so filtering the proxy
by `userId == X-Tenant-Id` keeps one NPO from ever seeing another's traces, mirroring the
RLS guarantee we enforce on our own tables. Admin-gated (it's a Settings view).

This module also does the *interpretation* the UI shouldn't have to: it categorizes each
observation (llm / tool / node / plumbing), pulls a human-readable summary out of the raw
LangGraph payloads, and returns the FULL input/output text (generously capped) so nothing
is clipped in the viewer.
"""
import base64
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.security.context import require_admin

router = APIRouter()
logger = logging.getLogger(__name__)

# Internal LangGraph plumbing nodes the user doesn't care about by default.
_PLUMBING = {"__start__", "__end__", "_write", "_route", "tools_condition", "LangGraph", "RunnableSequence"}
_NODE_NAMES = {"load_context", "agent", "tools"}
_MAX = 12000     # cap for the RAW (on-demand) view — full payload, just bounded
_COMPACT = 1500  # cap for the default compact view — a readable digest, not a wall of JSON


def _auth_header() -> dict[str, str]:
    s = get_settings()
    token = base64.b64encode(f"{s.langfuse_public_key}:{s.langfuse_secret_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _clip(s: str, cap: int = _MAX) -> str:
    return s if len(s) <= cap else s[:cap] + f"\n… (+{len(s) - cap} more chars)"


def _as_text(value, cap: int = _MAX) -> str | None:
    """Pretty-print a trace value (dict/list → indented JSON; str → as-is), capped at `cap`."""
    if value is None:
        return None
    if isinstance(value, str):
        return _clip(value, cap)
    try:
        return _clip(json.dumps(value, indent=2, ensure_ascii=False, default=str), cap)
    except (TypeError, ValueError):
        return _clip(str(value), cap)


def _msg_preview(m: dict, limit: int = 280) -> str:
    """A one-line preview of a single chat message dict (role: text), stripping prepended grounding."""
    role = m.get("type") or m.get("role") or "?"
    c = m.get("content")
    if isinstance(c, list):  # tool/multimodal content blocks → join any text parts
        c = " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    c = (c or "").strip()
    if "User message:" in c:        # drop the grounding/own-posts block we prepend to the human turn
        c = c.split("User message:")[-1].strip()
    tcs = m.get("tool_calls") or []
    if tcs and not c:
        names = ", ".join(t.get("name") or (t.get("function") or {}).get("name") or "?" for t in tcs)
        c = f"→ calls {names}"
    c = " ".join(c.split())
    return f"{role}: {c[:limit]}" + ("…" if len(c) > limit else "")


def _compact(name: str, category: str, value, is_output: bool) -> str | None:
    """A readable digest for the default view. The raw LangGraph payload repeats the WHOLE message
    history at every step (the 'cycling walls of JSON' problem); here we collapse a messages list to a
    count + the latest message preview, show tool args/results plainly, and leave the full thing to the
    on-demand RAW view."""
    if value is None:
        return None
    # Tool steps: just the args (in) or the returned text (out) — never the message history.
    if category == "tool":
        if is_output:
            return _as_text(value, _COMPACT)
        if isinstance(value, dict):
            args = {k: v for k, v in value.items() if k not in ("messages", "org_id", "system_prompt")}
            return _as_text(args or value, _COMPACT)
        return _as_text(value, _COMPACT)
    # LLM / graph-node steps: collapse the messages array to a digest.
    msgs = value.get("messages") if isinstance(value, dict) else None
    if isinstance(msgs, list) and msgs:
        head = f"{len(msgs)} message(s)"
        sys = sum(1 for m in msgs if (m.get("type") or m.get("role")) == "system")
        if sys:
            head += f" (incl. system prompt)"
        # Show the last 1-2 messages — that's the actual delta this step acted on / produced.
        tail = [_msg_preview(m) for m in msgs[-2:]]
        return _clip(head + "\n" + "\n".join(tail), _COMPACT)
    return _as_text(value, _COMPACT)


def _classify_level(level: str | None, status_message: str | None) -> tuple[str | None, str | None]:
    """Interpret a Langfuse observation level for the viewer.

    LangGraph's HITL publish gate pauses the graph by raising interrupt(); Langfuse records that
    propagated exception as an ERROR span even though it's the intended pause. Re-label it PAUSED
    so the viewer doesn't show a failure. Genuine errors keep their level and finally surface
    their statusMessage (previously dropped, so an ERROR chip had no explanation).
    """
    msg = (status_message or "").strip()
    if level == "ERROR" and "Interrupt(" in msg:
        return "PAUSED", "Paused for human approval (publish gate) — resumed on the user's decision"
    if level and level != "DEFAULT" and msg:
        return level, _clip(msg, _COMPACT)
    return level, None


def _category(name: str, obs_type: str) -> str:
    if (obs_type or "").upper() == "GENERATION":
        return "llm"
    if name in _PLUMBING or name.startswith("_"):
        return "plumbing"
    if name in _NODE_NAMES:
        return "node"
    return "tool"   # everything else is a named tool span (suggest_posts, search_sources, web_search…)


def _summary(name: str, category: str, inp, out, model: str | None) -> str:
    """One readable line describing what this step did."""
    if category == "llm":
        # Did the model answer, or call a tool?
        calls = _tool_calls_from_output(out)
        if calls:
            return f"LLM decided to call: {', '.join(calls)}"
        return f"LLM generated a reply ({model})" if model else "LLM generated a reply"
    if category == "tool":
        args = ""
        if isinstance(inp, dict):
            args = ", ".join(f"{k}={v!r}" for k, v in inp.items() if k not in ("messages", "org_id"))
        return f"{name}({args})" if args else f"{name}()"
    if name == "load_context":
        return "Loaded org memory, profile & capabilities → built the system prompt"
    if name == "agent":
        return "Agent step (LLM turn)"
    return name


def _tool_calls_from_output(out) -> list[str]:
    """Extract tool-call names from an LLM/agent output payload, if any."""
    names: list[str] = []
    try:
        msgs = out.get("messages") if isinstance(out, dict) else None
        if isinstance(out, dict) and "tool_calls" in out:
            msgs = [out]
        for m in (msgs or []):
            for tc in (m.get("tool_calls") or []):
                n = tc.get("name") or (tc.get("function") or {}).get("name")
                if n:
                    names.append(n)
    except (AttributeError, TypeError):
        pass
    return names


@router.get("/observability/status")
async def status(ident: tuple[str, str] = Depends(require_admin)):
    """Whether tracing is configured + the browser-reachable UI URL."""
    s = get_settings()
    return {"enabled": s.langfuse_enabled, "ui_url": s.langfuse_public_url}


@router.get("/observability/traces")
async def list_traces(limit: int = 20, ident: tuple[str, str] = Depends(require_admin)):
    """Recent agent turns for THIS org (most recent first), summarised for the list view."""
    _, org_id = ident
    s = get_settings()
    if not s.langfuse_enabled:
        return {"enabled": False, "traces": []}
    params = {"userId": org_id, "limit": min(max(limit, 1), 100), "orderBy": "timestamp.desc"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{s.langfuse_host}/api/public/traces",
                                  params=params, headers=_auth_header())
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        logger.warning("Langfuse traces fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not reach Langfuse")
    traces = [{
        "id": t.get("id"),
        "name": t.get("name"),
        "timestamp": t.get("timestamp"),
        "latency": t.get("latency"),
        "tokens": (t.get("usage") or {}).get("total") if isinstance(t.get("usage"), dict) else None,
        "tags": [tag for tag in (t.get("tags") or []) if not tag.startswith("org:")],
        "user_message": _first_user_message(t.get("input")),
        "assistant_reply": _final_assistant_reply(t.get("output")),
    } for t in data.get("data", [])]
    return {"enabled": True, "traces": traces}


@router.get("/observability/traces/{trace_id}")
async def get_trace(trace_id: str, ident: tuple[str, str] = Depends(require_admin)):
    """Full trace with its nested, categorized observations. Org-checked."""
    _, org_id = ident
    s = get_settings()
    if not s.langfuse_enabled:
        raise HTTPException(status_code=404, detail="tracing disabled")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{s.langfuse_host}/api/public/traces/{trace_id}",
                                  headers=_auth_header())
            r.raise_for_status()
            t = r.json()
    except httpx.HTTPError as e:
        logger.warning("Langfuse trace fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not reach Langfuse")
    # Defence in depth: never return another org's trace even if the id is guessed. Fails closed on a
    # missing userId — an untagged trace is not a recognized org-scoped trace (audit F11).
    if not _trace_visible_to_org(t, org_id):
        raise HTTPException(status_code=404, detail="not found")

    obs = sorted(t.get("observations", []), key=lambda o: o.get("startTime") or "")
    steps = []
    seen: set[tuple] = set()
    for o in obs:
        name = o.get("name") or o.get("type") or "step"
        otype = o.get("type") or ""
        inp, out = o.get("input"), o.get("output")
        cat = _category(name, otype)
        # Langfuse logs the same work at several nesting levels (e.g. a RunnableSequence wrapping the
        # GENERATION it contains) → the viewer showed the same step two-three times. Collapse exact dupes.
        key = (name, cat, o.get("startTime"), o.get("model"))
        if key in seen:
            continue
        seen.add(key)
        level, status_message = _classify_level(o.get("level"), o.get("statusMessage"))
        steps.append({
            "id": o.get("id"),
            "name": name,
            "category": cat,
            "type": otype,
            "latency": o.get("latency"),
            "model": o.get("model"),
            "tokens": (o.get("usage") or {}).get("total") if isinstance(o.get("usage"), dict) else None,
            "level": level,
            "status_message": status_message,
            "summary": _summary(name, cat, inp, out, o.get("model")),
            "input": _compact(name, cat, inp, is_output=False),
            "output": _compact(name, cat, out, is_output=True),
            # Full payloads for the on-demand "raw" view (still bounded). Omitted when identical to compact.
            "raw_input": _as_text(inp),
            "raw_output": _as_text(out),
        })
    return {
        "id": t.get("id"), "name": t.get("name"), "timestamp": t.get("timestamp"),
        "latency": t.get("latency"),
        "user_message": _first_user_message(t.get("input")),
        "assistant_reply": _final_assistant_reply(t.get("output")),
        "steps": steps,
    }


def _trace_visible_to_org(trace: dict, org_id: str) -> bool:
    """A trace is visible only if it is explicitly tagged with this org's id. Every turn is traced with
    langfuse_user_id=org_id, so a missing/blank userId is NOT a recognized org-scoped trace and must fail
    CLOSED (deny) — otherwise a guessed trace id with no userId would leak across orgs (audit F11)."""
    uid = trace.get("userId")
    return bool(uid) and uid == org_id


def _first_user_message(inp) -> str | None:
    """Pull the human's actual message text out of the graph input payload."""
    try:
        msgs = inp.get("messages") if isinstance(inp, dict) else None
        for m in reversed(msgs or []):
            if (m.get("type") == "human") or (m.get("role") == "user"):
                c = m.get("content")
                if isinstance(c, str) and c.strip():
                    # the real user line is the last paragraph (grounding/own-posts context is prepended)
                    tail = c.strip().split("User message:")[-1].strip()
                    return _clip(tail or c.strip())
    except (AttributeError, TypeError):
        pass
    return None


def _final_assistant_reply(out) -> str | None:
    """Pull the final assistant text out of the graph output payload."""
    try:
        msgs = out.get("messages") if isinstance(out, dict) else None
        for m in reversed(msgs or []):
            if (m.get("type") == "ai") or (m.get("role") == "assistant"):
                c = m.get("content")
                if isinstance(c, str) and c.strip():
                    return _clip(c.strip())
    except (AttributeError, TypeError):
        pass
    return None
