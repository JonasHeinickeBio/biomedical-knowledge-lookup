"""Helpers for aiohttp sessions that may outlive the event loop they were created on."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Seconds to wait for a session to close on another thread's event loop.
CROSS_LOOP_CLOSE_TIMEOUT = 5.0


async def close_session(session: Any | None, owner_loop: asyncio.AbstractEventLoop | None) -> None:
    """Close ``session`` best-effort, on its owning loop when that loop is still running.

    A session whose loop has already been closed is closed from the running loop
    instead; transports that can no longer be torn down cleanly are dropped.
    """
    if session is None or session.closed:
        return
    try:
        running = asyncio.get_running_loop()
        if owner_loop is not None and owner_loop is not running and owner_loop.is_running():
            # Another thread still drives the session's loop: close it over there.
            future = asyncio.run_coroutine_threadsafe(session.close(), owner_loop)
            try:
                await asyncio.wait_for(asyncio.wrap_future(future), CROSS_LOOP_CLOSE_TIMEOUT)
            except TimeoutError:
                future.cancel()
                logger.warning(
                    "Timed out after %.1fs closing an HTTP session on its owning event loop",
                    CROSS_LOOP_CLOSE_TIMEOUT,
                )
            return
        await session.close()
    except Exception as exc:
        logger.warning("Could not close HTTP session cleanly: %s", exc)
