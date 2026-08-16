from app.agent import tools
from app.agent.platforms import PLATFORMS


def test_cap_from_platform_max_chars():
    # instagram max_chars=2200 -> ceil(2200/3)+150 = 734+150 = 884
    assert tools._cap_tokens(PLATFORMS["instagram"]) == 884
    # x max_chars=280 -> ceil(280/3)+150 = 94+150 = 244
    assert tools._cap_tokens(PLATFORMS["x"]) == 244


def test_cap_handles_missing_config():
    assert tools._cap_tokens({}) is None
    assert tools._cap_tokens(None) is None


def test_gen_model_respects_test_injection(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(tools, "_model", sentinel)
    assert tools._gen_model(PLATFORMS["instagram"]) is sentinel
