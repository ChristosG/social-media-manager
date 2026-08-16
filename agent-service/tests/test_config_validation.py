"""Boot config fail-fast: prod_config_problems flags empty/placeholder security-critical settings so a
typo'd env var can't silently leave a forgeable image secret or a disabled network ACL in production."""
from app.config import Settings, prod_config_problems


def _settings(**over) -> Settings:
    base = dict(
        jwt_enforce=True, jwt_public_key="pk", agent_proxy_secret="sek",
        image_url_secret="a-strong-image-url-secret-0123456789",
        database_url="postgresql://npo_app:realpw@h/npo",
        migration_database_url="postgresql://npo_owner:realpw@h/npo",
        meta_app_id="", meta_token_key="",
    )
    base.update(over)
    return Settings(**base)


def test_secure_config_has_no_problems():
    assert prod_config_problems(_settings()) == []


def test_empty_image_secret_is_flagged():
    assert any("IMAGE_URL_SECRET" in p for p in prod_config_problems(_settings(image_url_secret="")))


def test_changeme_password_is_flagged():
    probs = prod_config_problems(_settings(database_url="postgresql://npo_app:changeme@h/npo"))
    assert any("DATABASE_URL" in p for p in probs)


def test_empty_proxy_secret_is_flagged():
    assert any("AGENT_PROXY_SECRET" in p for p in prod_config_problems(_settings(agent_proxy_secret="")))


def test_meta_configured_without_token_key_is_flagged():
    probs = prod_config_problems(_settings(meta_app_id="123", meta_token_key=""))
    assert any("META_TOKEN_KEY" in p for p in probs)
