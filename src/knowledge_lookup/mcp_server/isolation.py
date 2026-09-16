"""
Keep adapters that block the event loop off the server's loop.

A few adapters wrap synchronous client libraries (``chembl_webresource_client``,
``owlready2`` via Tyto, ``bioservices``) and call them from
inside ``async def`` methods. In a script that only costs latency; in a server,
one slow ChEMBL query freezes the event loop, so no other request is served,
per-source timeouts cannot fire, and the client sees the whole server hang.

:class:`ThreadedAdapter` runs such an adapter's coroutines on a private event
loop in a daemon thread. Blocking calls then only block that thread, and
``asyncio.wait_for`` timeouts on the server's loop work again.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, cast

from ..models import KnowledgeSource

if TYPE_CHECKING:
    from ..base import KnowledgeSourceAdapter
    from ..core.central_lookup import CentralKnowledgeLookup

logger = logging.getLogger(__name__)

#: Adapters built on synchronous third-party clients rather than aiohttp.
THREAD_ISOLATED_SOURCES: frozenset[KnowledgeSource] = frozenset(
    {
        KnowledgeSource.CHEMBL,
        KnowledgeSource.TYTO,
        KnowledgeSource.EUTILS,
        KnowledgeSource.QUICKGO,
        KnowledgeSource.UNICHEM,
    }
)

_CLOSE_TIMEOUT_SECONDS = 5.0


class ThreadedAdapter:
    """Proxy that runs an adapter's coroutine methods on a dedicated loop thread.

    Attribute access is forwarded to the wrapped adapter; coroutine methods are
    submitted to the private loop and awaited from the caller's loop. Cancelling
    the awaiting task (e.g. on timeout) returns immediately, while a call stuck
    in blocking I/O finishes in the background.
    """

    def __init__(self, adapter: KnowledgeSourceAdapter) -> None:
        self._adapter = adapter
        self._loop = asyncio.new_event_loop()
        source = getattr(adapter, "source", None)
        name = str(getattr(source, "value", source) or type(adapter).__name__).lower()
        self._thread = threading.Thread(target=self._run_loop, name=f"adapter-{name}", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    @property
    def wrapped(self) -> KnowledgeSourceAdapter:
        return self._adapter

    async def _submit(self, coro: Coroutine[Any, Any, Any]) -> Any:
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, self._loop))

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._adapter, name)
        if not asyncio.iscoroutinefunction(attr):
            return attr

        async def call(*args: Any, **kwargs: Any) -> Any:
            return await self._submit(attr(*args, **kwargs))

        return call

    async def close(self) -> None:
        try:
            await asyncio.wait_for(self._submit(self._adapter.close()), _CLOSE_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 - shutdown is best-effort
            logger.debug("Closing %s failed: %s", self._thread.name, exc)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)


def isolate_blocking_adapters(
    lookup: CentralKnowledgeLookup,
    sources: frozenset[KnowledgeSource] = THREAD_ISOLATED_SOURCES,
) -> None:
    """Wrap *lookup*'s adapters for *sources* in :class:`ThreadedAdapter`, in place."""
    for source in sources:
        adapter = lookup.adapters.get(source)
        if adapter is not None and not isinstance(adapter, ThreadedAdapter):
            lookup.adapters[source] = cast("KnowledgeSourceAdapter", ThreadedAdapter(adapter))
