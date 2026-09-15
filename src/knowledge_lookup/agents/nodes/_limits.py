"""Safeguards that bound the workflow's network fan-out.

The network nodes (``expand``, ``lookup``, ``detail_gather``, ``enrichment``)
each issue one search per term, concept or source, and every adapter call
sleeps for its rate limit (1 s by default). Unbounded, these multiply —
expansion terms x sources x concepts — and a small query could run for many
minutes. The nodes use these helpers to instantiate only the adapters they
query, cap concurrency, and stop waiting once a per-node time budget is spent,
continuing with whatever finished.

A budget can only fire when the event loop gets control back: an adapter that
blocks the loop with a synchronous call delays it until that call returns.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import TypeVar

from ...mcp_server.sources import normalize_source_name
from ...models import KnowledgeSource

T = TypeVar("T")

# Per-node wall-clock budgets in seconds.
EXPAND_TIMEOUT = 45.0
LOOKUP_TIMEOUT = 60.0
DETAIL_GATHER_TIMEOUT = 45.0
ENRICHMENT_TIMEOUT = 30.0

# Timeout for a single per-concept search in detail_gather / enrichment.
CALL_TIMEOUT = 15.0

# Searches a node runs at the same time.
MAX_CONCURRENCY = 5


def resolve_sources(names: Iterable[str] | None) -> list[KnowledgeSource] | None:
    """Map user source names (``"hpo"``, ``"GO"``) to :class:`KnowledgeSource` members.

    Unknown names are dropped. Returns ``None`` when no names were given,
    meaning "all available sources".
    """
    if not names:
        return None
    resolved: list[KnowledgeSource] = []
    for name in names:
        try:
            source = KnowledgeSource(normalize_source_name(name))
        except ValueError:
            continue
        if source not in resolved:
            resolved.append(source)
    return resolved


async def gather_bounded(
    factories: Sequence[Callable[[], Awaitable[T]]],
    *,
    timeout: float,
    concurrency: int = MAX_CONCURRENCY,
) -> tuple[list[T | BaseException | None], int]:
    """Run coroutine factories, at most *concurrency* at a time, within *timeout* seconds.

    Returns ``(results, unfinished)``: ``results[i]`` is the value of
    ``factories[i]()``, the exception it raised, or ``None`` if it had not
    finished when the budget ran out (it is then cancelled). ``unfinished``
    counts those cancelled calls.
    """
    if not factories:
        return [], 0

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _run(factory: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await factory()

    tasks = [asyncio.ensure_future(_run(f)) for f in factories]
    try:
        _, pending = await asyncio.wait(tasks, timeout=timeout)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    results: list[T | BaseException | None] = []
    for task in tasks:
        if task in pending or task.cancelled():
            results.append(None)
        elif task.exception() is not None:
            results.append(task.exception())
        else:
            results.append(task.result())
    return results, len(pending)
