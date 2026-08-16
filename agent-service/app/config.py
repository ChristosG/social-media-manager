from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    http_port: int = 8085
    deploy_env: str = "dev"   # DEPLOY_ENV=prod makes the boot config check fail-fast instead of warn
    # Runtime role: DML-only, used for every request (RLS applies, cannot alter policies).
    database_url: str = "postgresql://npo_app:changeme@postgres:5432/npo"
    # Migration role: owns tables + policies, used ONLY to run migrations at startup.
    migration_database_url: str = "postgresql://npo_owner:changeme@postgres:5432/npo"
    jwt_public_key: str = ""                      # base64 raw 32-byte Ed25519
    # Defense in depth: verify the gateway-forwarded Ed25519 token and REJECT (401) any request whose
    # identity headers aren't backed by a valid, matching token. The Tier-0 log-only soak was clean.
    # Reversible: set JWT_ENFORCE=false to fall back to log-only if anything unexpected appears.
    jwt_enforce: bool = True
    # Network ACL (belt-and-suspenders on top of JWT/HMAC): a shared secret the trusted reverse proxies
    # (gateway + nginx) inject as X-Proxy-Secret. When set, agent-service rejects any request/WS that
    # doesn't carry it — so only the proxies, never another container on the network, can reach us.
    # Empty (default) => disabled. Infra endpoints (/health, /livez, /readyz, /metrics) are always exempt.
    agent_proxy_secret: str = ""         # env AGENT_PROXY_SECRET (field name → uppercased env var)
    # Concurrency: vLLM batches many sequences with ~no per-request latency penalty, so we parallelize
    # rather than serialize. worker_concurrency = jobs drained at once; draft_concurrency = slots of ONE
    # campaign drafted at once (a 5-slot campaign fills in ~one LLM round-trip instead of five).
    worker_concurrency: int = 4          # env WORKER_CONCURRENCY
    draft_concurrency: int = 8           # env DRAFT_CONCURRENCY
    llm_base_url: str = "http://qwen-vllm:6888/v1"
    llm_model: str = "/models/Qwen3.5-9B"
    llm_api_key: str = "none"
    request_timeout_s: int = 120
    tavily_api_key: str = ""
    embed_base_url: str = "http://qwen-emb-vllm:8090/v1"   # Qwen3-Embedding-4B (2560-dim)
    embed_model: str = "qwen3-emb-4b"
    flux_base_url: str = "http://host.docker.internal:8000"  # FLUX image server on the HOST
    redis_url: str = "redis://redis:6379/0"  # streaming-resume buffer (infra redis on platform-net)
    image_url_secret: str = ""  # HMAC secret for signed image URLs (stable across restarts)
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_token_key: str = ""        # AES-GCM key material for encrypting stored OAuth tokens
    meta_oauth_redirect: str = ""   # registered OAuth redirect URI
    meta_login_config_id: str = ""  # FB Login *for Business* config id; empty => classic scope flow

    # Langfuse observability (optional). When both keys are set, every agent turn is traced
    # (graph nodes, LLM calls, tool calls, latency, token usage). Unset => fully no-op.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse:3000"   # in-cluster default; from host use http://localhost:3001
    # Browser-reachable Langfuse URL for the "Open Langfuse" link (the in-cluster host isn't routable
    # from the user's browser). Defaults to the self-host stack's published port.
    langfuse_public_url: str = "http://localhost:3001"

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _insecure(v: str | None) -> bool:
    """True if a security-critical value is empty or an obvious placeholder."""
    return (not v) or ("changeme" in v.lower()) or ("change_me" in v.lower())


def prod_config_problems(s: Settings) -> list[str]:
    """Security-critical settings that must NOT be empty/default in production. Empty list => OK.

    Because the model ignores unknown env vars (extra='ignore'), a typo'd var name silently leaves the
    default in place — so a misconfigured deploy can boot 'green' with a forgeable image secret or a
    disabled network ACL. In prod this list fails the boot (see main.py); in dev it's a warning."""
    probs: list[str] = []
    if s.jwt_enforce and not s.jwt_public_key:
        probs.append("JWT_PUBLIC_KEY is empty while JWT_ENFORCE is on — forwarded tokens can't be verified")
    if not s.agent_proxy_secret:
        probs.append("AGENT_PROXY_SECRET is empty — the network ACL is disabled")
    if _insecure(s.image_url_secret):
        probs.append("IMAGE_URL_SECRET is empty or a placeholder — signed image URLs would be forgeable")
    if "changeme" in s.database_url.lower():
        probs.append("DATABASE_URL still carries the 'changeme' password")
    if "changeme" in s.migration_database_url.lower():
        probs.append("MIGRATION_DATABASE_URL still carries the 'changeme' password")
    if s.meta_app_id and _insecure(s.meta_token_key):
        probs.append("META_TOKEN_KEY is empty while Meta is configured — stored OAuth tokens can't be encrypted")
    return probs
