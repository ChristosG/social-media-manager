import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.db.pool import init_pool, close_pool, ping as db_ping, db_now, raw_conn
from app.db.migrate import run_migrations
from app.db import security_check

logger = logging.getLogger(__name__)


async def _init_db_with_retry(attempts: int = 60, delay: float = 2.0) -> None:
    """Migrate + open the pool, retrying while Postgres is still coming up. This makes a cold
    `docker compose up` deterministic — the agent waits for the DB instead of crash-looping until
    it's ready. run_migrations is idempotent and init_pool guards on a None pool, so retries are safe."""
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            await run_migrations()
            await init_pool()
            if i > 1:
                logger.info("database ready after %d attempt(s)", i)
            return
        except Exception as e:  # asyncpg connection / migration errors while Postgres boots
            last = e
            logger.warning("database not ready yet (attempt %d/%d): %s", i, attempts, e)
            await asyncio.sleep(delay)
    assert last is not None
    raise last
from app.api.conversations import router as conversations_router
from app.api.ws import router as ws_router
from app.api.memory import router as memory_router
from app.api.ledger import router as ledger_router
from app.api.profile import router as profile_router
from app.api.capabilities import router as capabilities_router
from app.api.research import router as research_router
from app.api.attachments import router as attachments_router
from app.api.images import router as images_router
from app.api.sources import router as sources_router
from app.api.social import router as social_router
from app.api.notifications import router as notifications_router
from app.api.publish import router as publish_router
from app.api.comments import router as comments_router
from app.api.observability import router as observability_router
from app.api.prompts import router as prompts_router
from app.api.insights import router as insights_router
from app.api.campaigns import router as campaigns_router
from app.api.proactive import router as proactive_router
from app.sources.scheduler import scheduler_loop
from app.social.publish_worker import loop as publish_loop
from app.comments.worker import loop as comments_loop
from app.social.metrics_scheduler import loop as metrics_scheduler_loop


async def _check_clock_skew() -> None:
    """Compare the app's wall-clock to the DB clock. The whole publish/schedule path is now()-driven, so
    a drifting container clock silently mis-schedules. Log loudly (never abort) so it's visible."""
    try:
        skew = abs((await db_now() - datetime.now(timezone.utc)).total_seconds())
        if skew > 120:
            logger.error("CLOCK SKEW %.0fs between app and DB — scheduling/JWT exp will be wrong; "
                         "fix host NTP and set TZ=UTC", skew)
        else:
            logger.info("clock skew vs DB: %.1fs (ok)", skew)
    except Exception:
        logger.exception("clock-skew check failed")


async def _run_security_self_check() -> None:
    """Assert the multi-tenant integrity invariants at boot; on violation mark NOT READY (not crash)."""
    try:
        async with raw_conn() as conn:
            problems = await security_check.run_security_self_check(conn)
        security_check.record(problems)
        if problems:
            for p in problems:
                logger.error("SECURITY SELF-CHECK FAILED: %s", p)
            logger.error("→ /readyz will report NOT READY until these are resolved")
        else:
            logger.info("security self-check passed (FORCE RLS + SECURITY DEFINER readers + npo_app isolation)")
    except Exception:
        logger.exception("security self-check could not run")
        security_check.record(["self-check errored — see logs"])


def _check_config() -> None:
    """Fail-fast on insecure production config (empty signing secrets, 'changeme' passwords, disabled ACL).
    In prod (DEPLOY_ENV=prod) a problem aborts startup; otherwise it's a loud warning so dev still runs."""
    from app.config import get_settings, prod_config_problems
    s = get_settings()
    problems = prod_config_problems(s)
    if not problems:
        return
    if s.deploy_env.lower() in ("prod", "production"):
        raise RuntimeError("refusing to start — insecure production config: " + "; ".join(problems))
    for p in problems:
        logger.warning("config check (DEPLOY_ENV=%s, not fatal): %s", s.deploy_env, p)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_config()
    await _init_db_with_retry()
    await _check_clock_skew()
    await _run_security_self_check()
    sched_task = asyncio.create_task(scheduler_loop())
    publish_task = asyncio.create_task(publish_loop())
    comments_task = asyncio.create_task(comments_loop())
    metrics_sched_task = asyncio.create_task(metrics_scheduler_loop())
    yield
    sched_task.cancel()
    publish_task.cancel()
    comments_task.cancel()
    metrics_sched_task.cancel()
    await close_pool()


app = FastAPI(title="NPO Agent Service", lifespan=lifespan)
# Defense-in-depth: verify the forwarded Ed25519 token and LOG (never reject) any disagreement with the
# gateway-injected identity headers — the evidence soak before Phase-8 enforcement. No-op if no public key.
from app.security.jwt_probe import JwtProbeMiddleware  # noqa: E402
from app.security.proxy_guard import ProxyGuardMiddleware  # noqa: E402
app.add_middleware(JwtProbeMiddleware)
# Added last → outermost: enforce the network ACL (only the gateway/nginx carry X-Proxy-Secret) before
# the JWT check even runs. No-op when AGENT_PROXY_SECRET is unset.
app.add_middleware(ProxyGuardMiddleware)
app.include_router(conversations_router)
app.include_router(ws_router)
app.include_router(memory_router)
app.include_router(ledger_router)
app.include_router(profile_router)
app.include_router(capabilities_router)
app.include_router(research_router)
app.include_router(attachments_router)
app.include_router(images_router)
app.include_router(sources_router)
app.include_router(social_router)
app.include_router(notifications_router)
app.include_router(publish_router)
app.include_router(comments_router)
app.include_router(observability_router)
app.include_router(prompts_router)
app.include_router(insights_router)
app.include_router(campaigns_router)
app.include_router(proactive_router)

@app.get("/health")
@app.get("/livez")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Static on purpose — never gates on dependencies."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness: can we actually serve? Verifies the DB pool. Returns 503 when not — so the deploy
    healthcheck / future rolling-deploy only routes to instances that can do real work."""
    try:
        await db_ping()
    except Exception as e:
        logger.warning("readyz: not ready: %s", e)
        return JSONResponse({"status": "not ready", "detail": str(e)}, status_code=503)
    problems = security_check.current_problems()
    if problems:
        return JSONResponse({"status": "not ready", "security": problems}, status_code=503)
    return {"status": "ready"}
