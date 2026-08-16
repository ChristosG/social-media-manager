from app.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/npo")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "abc")
    monkeypatch.setenv("LLM_BASE_URL", "http://qwen-vllm:6888/v1")
    monkeypatch.setenv("LLM_MODEL", "/models/Qwen3.5-9B")
    s = Settings()
    assert s.database_url.startswith("postgresql://")
    assert s.llm_model == "/models/Qwen3.5-9B"
    assert s.http_port == 8085  # default
