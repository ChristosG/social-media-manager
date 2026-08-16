from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App identity
    app_name: str = "Platform"

    # Domain & sender
    mail_domain: str
    mail_from_name: str = ""  # defaults to app_name
    mail_from_address: str = ""  # defaults to noreply@MAIL_DOMAIN

    # SMTP relay connection
    smtp_host: str = "postfix"
    smtp_port: int = 25
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False

    # API key for authenticating requests
    api_key: str

    # Rate limiting
    rate_limit_per_recipient: int = 10  # per minute
    rate_limit_global: int = 100  # per minute

    # Service
    host: str = "0.0.0.0"
    port: int = 8025

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def sender(self) -> str:
        name = self.mail_from_name or self.app_name
        address = self.mail_from_address or f"noreply@{self.mail_domain}"
        return f"{name} <{address}>"


@lru_cache
def get_settings() -> Settings:
    return Settings()
