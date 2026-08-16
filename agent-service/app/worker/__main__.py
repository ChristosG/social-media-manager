"""Entrypoint for the dedicated worker tier: `python -m app.worker`.

A stateless, horizontally-scalable process (no HTTP server) that drains the durable `jobs` queue. It does
NOT run migrations — the api tier owns schema. It opens the pool, imports the handlers (registering them),
and runs the engine until SIGTERM."""
import asyncio
import logging

from app.config import get_settings
from app.db.pool import init_pool, close_pool
from app.worker import handlers  # noqa: F401 — importing registers the job handlers
from app.worker.runner import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")


async def _main() -> None:
    await init_pool()
    try:
        await Worker(concurrency=get_settings().worker_concurrency).run()
    finally:
        await close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
