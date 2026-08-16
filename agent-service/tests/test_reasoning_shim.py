"""The reasoning shim copies vLLM's non-standard delta.reasoning into additional_kwargs so the WS
layer can stream the thinking trace. Without it, langchain_openai drops the field."""
import app.llm.client  # noqa: F401 — importing applies the monkey-patch
import langchain_openai.chat_models.base as lc_base
from langchain_core.messages import AIMessageChunk


def test_reasoning_field_lands_in_additional_kwargs():
    chunk = lc_base._convert_delta_to_message_chunk(
        {"role": "assistant", "reasoning": "Let me think..."}, AIMessageChunk)
    assert chunk.additional_kwargs.get("reasoning") == "Let me think..."


def test_reasoning_content_alias_also_captured():
    chunk = lc_base._convert_delta_to_message_chunk(
        {"role": "assistant", "reasoning_content": "step 1"}, AIMessageChunk)
    assert chunk.additional_kwargs.get("reasoning") == "step 1"


def test_plain_content_delta_unaffected():
    chunk = lc_base._convert_delta_to_message_chunk(
        {"role": "assistant", "content": "hello"}, AIMessageChunk)
    assert chunk.content == "hello"
    assert "reasoning" not in chunk.additional_kwargs
