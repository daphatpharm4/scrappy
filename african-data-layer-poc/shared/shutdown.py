import asyncio
import logging
import signal
from contextlib import AsyncExitStack
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

ShutdownCallback = Callable[[], Awaitable[None]]


def register_shutdown(app, callbacks: list[ShutdownCallback]) -> None:
    @app.on_event("shutdown")
    async def _shutdown() -> None:
        logger.info("Service shutting down")
        async with AsyncExitStack() as stack:
            for cb in callbacks:
                await stack.enter_async_context(_noop_async_context(cb))


class _noop_async_context:
    def __init__(self, cb: ShutdownCallback) -> None:
        self.cb = cb

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        await self.cb()
        return False


def install_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
