"""Handler registry: maps a job `kind` to an async handler. The worker only claims kinds it can handle,
so a job for an unregistered kind is never picked up by a worker that can't run it.

A handler is `async def handler(ctx: JobContext, payload: dict) -> None`. It should be IDEMPOTENT (the job
system is at-least-once: a crash after the work but before `succeed` will retry) and raise on failure (the
worker turns the exception into a retry-with-backoff, then a dead-letter at max attempts)."""
from typing import Awaitable, Callable

Handler = Callable[..., Awaitable[None]]

_HANDLERS: dict[str, Handler] = {}


def register(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        if kind in _HANDLERS:
            raise ValueError(f"duplicate handler for job kind '{kind}'")
        _HANDLERS[kind] = fn
        return fn
    return deco


def get(kind: str) -> Handler | None:
    return _HANDLERS.get(kind)


def kinds() -> list[str]:
    return list(_HANDLERS)


def clear() -> None:        # tests only
    _HANDLERS.clear()
