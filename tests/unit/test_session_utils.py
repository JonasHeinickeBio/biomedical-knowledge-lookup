"""Unit tests for close_session."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from knowledge_lookup.utils import session_utils
from knowledge_lookup.utils.session_utils import close_session

pytestmark = pytest.mark.unit


@pytest.fixture
def background_loop():
    """An event loop running in another thread, like a caller's long-lived loop."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()


def _session(close):
    session = MagicMock()
    session.closed = False
    session.close = close
    return session


@pytest.mark.asyncio
async def test_none_and_closed_sessions_are_ignored():
    await close_session(None, None)
    closed = MagicMock(closed=True)
    await close_session(closed, None)
    closed.close.assert_not_called()


@pytest.mark.asyncio
async def test_closes_on_current_loop_and_swallows_errors():
    async def boom():
        raise RuntimeError("Event loop is closed")

    await close_session(_session(boom), asyncio.get_running_loop())  # must not raise


@pytest.mark.asyncio
async def test_waits_for_close_on_owning_loop(background_loop):
    closed_on = []

    async def close():
        await asyncio.sleep(0.05)
        closed_on.append(asyncio.get_running_loop())

    await close_session(_session(close), background_loop)

    assert closed_on == [background_loop]  # finished before close_session returned


@pytest.mark.asyncio
async def test_cross_loop_close_times_out(background_loop, monkeypatch):
    monkeypatch.setattr(session_utils, "CROSS_LOOP_CLOSE_TIMEOUT", 0.05)

    async def hang():
        await asyncio.sleep(30)

    await close_session(_session(hang), background_loop)  # returns instead of hanging


@pytest.mark.asyncio
async def test_cross_loop_close_failure_is_logged_not_raised(background_loop):
    async def boom():
        raise ValueError("nope")

    await close_session(_session(boom), background_loop)
