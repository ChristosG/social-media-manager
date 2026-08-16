"""The agent-worker engine.

Drains the durable `jobs` queue with the publish-worker guarantees, generalized:

  • exactly-once via an ATOMIC claim (queued→running) — N replicas are safe, no leader election;
  • a LEASE that an auto-heartbeat renews while a handler runs, so a slow job isn't reaped;
  • a REAPER that requeues jobs whose lease expired (the worker that held them died), dead-lettering at
    max attempts;
  • retry-with-backoff on failure, bounded by max_attempts → dead-letter (visible DLQ row);
  • bounded concurrency so a burst can't overrun the box / GPU;
  • graceful drain on SIGTERM: stop claiming, let in-flight handlers finish within the grace period; any
    that don't are reaped + resumed elsewhere.

The handler runs with the job's tenant identity set (org + a system/user id), so existing org-scoped code
(org_tx / current_org) works unchanged inside a job.
"""
import asyncio
import contextlib
import logging
import os
import signal
import socket
import time

from app.repo import jobs
from app.security.context import set_identity
from app.worker import registry

logger = logging.getLogger("worker")

_SYSTEM_USER = "00000000-0000-0000-0000-000000000000"   # identity for jobs not tied to a specific user


class JobContext:
    """Passed to each handler. Lets a long handler report progress (which also renews the lease)."""
    def __init__(self, worker: "Worker", org_id: str, job: dict):
        self.org_id = org_id
        self.job = job
        self._worker = worker

    async def progress(self, **data) -> None:
        await jobs.heartbeat(self.org_id, self.job["id"], self._worker.id, self._worker.lease_secs, data)


class Worker:
    def __init__(self, *, concurrency: int = 3, lease_secs: int = 300, poll_interval: float = 1.0,
                 reap_interval: float = 30.0, batch: int = 16):
        self.id = f"{socket.gethostname()}:{os.getpid()}"
        self.concurrency = concurrency
        self.lease_secs = lease_secs
        self.poll_interval = poll_interval
        self.reap_interval = reap_interval
        self.batch = batch
        self._sem = asyncio.Semaphore(concurrency)
        self._inflight: set[asyncio.Task] = set()
        self._stopping = asyncio.Event()

    # ── per-job processing (unit-testable; no cross-org reader involved) ──
    async def process(self, org_id: str, job_id: str) -> str | None:
        """Claim + run one job. Returns the terminal outcome: 'succeeded' | 'queued' (retry) | 'dead' |
        'no_handler' | None (lost the claim race)."""
        job = await jobs.claim(org_id, job_id, self.id, self.lease_secs)
        if not job:
            return None
        handler = registry.get(job["kind"])
        if handler is None:
            await jobs.fail(org_id, job_id, f"no handler registered for kind '{job['kind']}'", backoff_secs=300)
            return "no_handler"

        # Run with the job's tenant identity so org-scoped code works inside the handler.
        set_identity(user_id=str(job["payload"].get("user_id") or _SYSTEM_USER), org_id=org_id)
        hb = asyncio.create_task(self._auto_heartbeat(org_id, job_id))
        started = time.monotonic()
        try:
            await handler(JobContext(self, org_id, job), job["payload"])
            await jobs.succeed(org_id, job_id)
            logger.info("job ok kind=%s id=%s org=%s %.1fs attempt=%d",
                        job["kind"], job_id, org_id, time.monotonic() - started, job["attempts"])
            return "succeeded"
        except Exception as e:                                   # noqa: BLE001 — any failure → retry/DLQ
            state = await jobs.fail(org_id, job_id, str(e) or e.__class__.__name__)
            logger.warning("job %s kind=%s id=%s org=%s attempt=%d/%d: %s",
                           "DEAD-LETTERED" if state == "dead" else "will retry",
                           job["kind"], job_id, org_id, job["attempts"], job["max_attempts"], e)
            return state
        finally:
            hb.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb

    async def _auto_heartbeat(self, org_id: str, job_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(max(1.0, self.lease_secs / 3))
                if not await jobs.heartbeat(org_id, job_id, self.id, self.lease_secs):
                    return   # we no longer hold the lease (reaped) — stop renewing
        except asyncio.CancelledError:
            raise

    # ── batch discovery (uses the SECURITY DEFINER readers) ──
    async def poll_once(self) -> int:
        due = await jobs.due(self.batch, registry.kinds())
        for org_id, job_id in due:
            await self._spawn(org_id, job_id)
        return len(due)

    async def _spawn(self, org_id: str, job_id: str) -> None:
        await self._sem.acquire()

        async def _run():
            try:
                await self.process(org_id, job_id)
            except Exception:                                   # noqa: BLE001 — never let one job kill the loop
                logger.exception("unexpected error processing job id=%s org=%s", job_id, org_id)
            finally:
                self._sem.release()

        t = asyncio.create_task(_run())
        self._inflight.add(t)
        t.add_done_callback(self._inflight.discard)

    async def reap_once(self) -> int:
        stale = await jobs.reap_due(self.batch)
        for org_id, job_id in stale:
            new = await jobs.requeue_stale(org_id, job_id)
            if new:
                logger.warning("reaped stale job id=%s org=%s → %s", job_id, org_id, new)
        return len(stale)

    # ── main loop with graceful drain ──
    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._stopping.set)

        logger.info("agent-worker %s up: concurrency=%d kinds=%s", self.id, self.concurrency, registry.kinds())
        await self.reap_once()        # recover anything stranded by a previous crash, immediately
        next_reap = time.monotonic() + self.reap_interval

        while not self._stopping.is_set():
            try:
                await self.poll_once()
                if time.monotonic() >= next_reap:
                    await self.reap_once()
                    next_reap = time.monotonic() + self.reap_interval
            except Exception:                                   # noqa: BLE001
                logger.exception("worker loop error (continuing)")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval)

        # drain: stop claiming, let in-flight handlers finish (the container's stop_grace_period bounds this;
        # anything killed past it keeps its lease and is reaped+resumed elsewhere).
        if self._inflight:
            logger.info("draining %d in-flight job(s)…", len(self._inflight))
            await asyncio.gather(*self._inflight, return_exceptions=True)
        logger.info("agent-worker %s stopped cleanly", self.id)
