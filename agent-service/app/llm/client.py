from langchain_openai import ChatOpenAI
from app.config import get_settings

# ── Reasoning-trace shim ────────────────────────────────────────────────────────
# Our vLLM (`--reasoning-parser qwen3`) streams the thinking trace as a non-standard
# `delta.reasoning` field. langchain_openai 0.2.14's delta→chunk converter is an
# allow-list (content/function_call/tool_calls only), so it silently drops `reasoning`.
# Wrap that module-level converter to copy the trace into additional_kwargs['reasoning']
# so the WS layer can stream it. Internal calls resolve the name via module globals at
# call time, so patching the attribute is sufficient (no fork, LangGraph stays intact).
import langchain_openai.chat_models.base as _lc_base  # noqa: E402

if not getattr(_lc_base, "_npo_reasoning_patched", False):
    _orig_delta = _lc_base._convert_delta_to_message_chunk

    def _delta_with_reasoning(_dict, default_class):
        chunk = _orig_delta(_dict, default_class)
        trace = _dict.get("reasoning") or _dict.get("reasoning_content")
        if trace and hasattr(chunk, "additional_kwargs"):
            chunk.additional_kwargs = {**(chunk.additional_kwargs or {}), "reasoning": trace}
        return chunk

    _lc_base._convert_delta_to_message_chunk = _delta_with_reasoning
    _lc_base._npo_reasoning_patched = True
# ────────────────────────────────────────────────────────────────────────────────


def build_chat_model(enable_thinking: bool = False, temperature: float = 0.3,
                     max_tokens: int | None = None, timeout: int | None = None) -> ChatOpenAI:
    s = get_settings()
    kwargs = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        temperature=temperature,
        # A caller may bound a specific call tighter than the global default (e.g. org research must
        # return inside the 120s proxy/gateway window even though its LLM call could otherwise run long).
        timeout=timeout if timeout is not None else s.request_timeout_s,
        # vLLM runs `--reasoning-parser qwen3`, so with enable_thinking the reasoning is returned
        # separately (delta.reasoning_content) rather than inline <think> tags.
        extra_body={"chat_template_kwargs": {"enable_thinking": enable_thinking}},
        **kwargs,
    )
