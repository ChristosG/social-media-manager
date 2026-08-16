"""Langfuse tracing for the agent graph — opt-in and fully no-op when unconfigured.

What this buys us: every assistant turn becomes one Langfuse *trace*, with a nested span
per LangGraph node (`load_context` → `agent` → `tools` → `agent` …), each LLM call (with
prompt, completion, token counts, latency) and each tool call captured automatically by
LangChain's callback mechanism. Traces are grouped by conversation (session) and tagged
with the org, so you can answer "what did the agent actually do on this turn, and why".

Design notes:
- **Zero hard dependency at runtime.** If the `langfuse` package isn't installed, or the
  keys aren't set, `get_handler()` returns `None` and the graph runs exactly as before.
  That keeps the running image working until it's rebuilt with the new dependency.
- **One handler, reused.** The CallbackHandler is cheap to reuse across requests; per-turn
  context (session id, user/org, tags) is attached through the LangChain run `config`
  (see `trace_config`), not by constructing a new handler each time.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_handler():
    """Return a cached Langfuse LangChain CallbackHandler, or None if disabled/unavailable."""
    s = get_settings()
    if not s.langfuse_enabled:
        return None
    try:
        from langfuse.callback import CallbackHandler
    except ImportError:
        logger.warning("LANGFUSE_* keys set but the 'langfuse' package isn't installed — tracing off.")
        return None
    try:
        handler = CallbackHandler(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        )
        logger.info("Langfuse tracing enabled (host=%s).", s.langfuse_host)
        return handler
    except Exception:  # never let observability break a request
        logger.exception("Failed to initialise Langfuse handler — tracing off.")
        return None


def trace_config(*, org_id: str | None = None, conv_id: str | None = None,
                 run_name: str = "agent-turn", **extra_metadata: Any) -> dict:
    """Build the LangChain `config` dict to pass to `graph.astream(..., config=...)`.

    Returns `{}` when tracing is off, so callers can always splat it in unconditionally.
    Groups the trace under the conversation (session) and tags it with the org so traces
    are filterable per-tenant in the Langfuse UI.
    """
    handler = get_handler()
    if handler is None:
        return {}
    metadata = {"langfuse_session_id": conv_id, "langfuse_user_id": org_id, **extra_metadata}
    tags = [t for t in (f"org:{org_id}" if org_id else None,) if t]
    return {
        "callbacks": [handler],
        "run_name": run_name,
        "metadata": {k: v for k, v in metadata.items() if v is not None},
        "tags": tags,
    }
