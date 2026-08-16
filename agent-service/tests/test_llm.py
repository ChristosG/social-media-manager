from app.llm.client import build_chat_model


def test_chat_model_sets_thinking_off():
    model = build_chat_model()
    # extra_body carries the vLLM thinking switch
    assert model.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    assert model.model_name == "/models/Qwen3.5-9B"
