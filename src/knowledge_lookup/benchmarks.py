"""
Modular Benchmarking System for the Knowledge Lookup Library

Provides a reusable, composable framework for measuring the performance of any
component in the library — cache backends, adapter calls, batch operations, etc.

Key primitives
--------------
* :class:`BenchmarkResult`   — stores timing and iteration statistics for one run.
* :class:`BenchmarkSuite`    — groups related :class:`BenchmarkResult` objects.
* :class:`Benchmarker`       — context-manager / callable that measures a block.
* :func:`benchmark`          — decorator for sync *and* async callables.
* :class:`BenchmarkRegistry` — global registry for named reusable benchmarks.
* :func:`generate_report`    — formats a :class:`BenchmarkSuite` as human-readable text.

Quick-start
-----------
::

    from knowledge_lookup.benchmarks import Benchmarker, benchmark, BenchmarkRegistry

    # --- context manager ---
    with Benchmarker("my_operation") as bm:
        do_something()
    print(bm.result)

    # --- decorator ---
    @benchmark("fetch_data", iterations=5)
    def fetch_data(query: str):
        ...

    result = fetch_data("diabetes")  # returns original return value; result stored in registry

    # --- async decorator ---
    @benchmark("async_fetch", iterations=3)
    async def async_fetch(query: str):
        ...

    # --- registry ---
    registry = BenchmarkRegistry.instance()
    suite = registry.suite("my_suite")
    print(generate_report(suite))
"""

from __future__ import annotations

import asyncio
import functools
import gc
import logging
import statistics
import time
import tracemalloc
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Stores the outcome of a single benchmark measurement.

    Attributes:
        name: Human-readable name for this benchmark.
        iterations: Number of times the target was executed.
        durations_s: Wall-clock duration of each iteration in seconds.
        peak_memory_bytes: Peak memory increase (bytes) during the last
            iteration as reported by :mod:`tracemalloc`, or ``None`` if memory
            tracking was disabled.
        metadata: Arbitrary key/value pairs (e.g. cache size, query term).
        error: If set, the benchmark raised this exception and timing data
            may be incomplete.
    """

    name: str
    iterations: int = 1
    durations_s: list[float] = field(default_factory=list)
    peak_memory_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    # ------------------------------------------------------------------
    # Derived statistics
    # ------------------------------------------------------------------

    @property
    def total_s(self) -> float:
        """Total elapsed time in seconds."""
        return sum(self.durations_s)

    @property
    def mean_s(self) -> float:
        """Mean duration per iteration in seconds."""
        return statistics.mean(self.durations_s) if self.durations_s else 0.0

    @property
    def min_s(self) -> float:
        """Minimum single-iteration duration in seconds."""
        return min(self.durations_s) if self.durations_s else 0.0

    @property
    def max_s(self) -> float:
        """Maximum single-iteration duration in seconds."""
        return max(self.durations_s) if self.durations_s else 0.0

    @property
    def stddev_s(self) -> float:
        """Standard deviation of per-iteration durations (0 if < 2 samples)."""
        return statistics.stdev(self.durations_s) if len(self.durations_s) >= 2 else 0.0

    @property
    def ops_per_second(self) -> float:
        """Throughput in operations per second."""
        return self.iterations / self.total_s if self.total_s > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_s": self.total_s,
            "mean_s": self.mean_s,
            "min_s": self.min_s,
            "max_s": self.max_s,
            "stddev_s": self.stddev_s,
            "ops_per_second": self.ops_per_second,
            "peak_memory_bytes": self.peak_memory_bytes,
            "metadata": self.metadata,
            "error": self.error,
        }

    def __repr__(self) -> str:
        return (
            f"BenchmarkResult(name={self.name!r}, iterations={self.iterations}, "
            f"mean={self.mean_s * 1000:.2f}ms, ops/s={self.ops_per_second:.1f})"
        )


@dataclass
class BenchmarkSuite:
    """A named collection of :class:`BenchmarkResult` objects.

    Attributes:
        name: Suite identifier.
        results: Ordered list of benchmark results added to this suite.
    """

    name: str
    results: list[BenchmarkResult] = field(default_factory=list)

    def add(self, result: BenchmarkResult) -> None:
        """Append *result* to the suite."""
        self.results.append(result)

    def get(self, name: str) -> BenchmarkResult | None:
        """Return the first result whose :attr:`~BenchmarkResult.name` matches."""
        for r in self.results:
            if r.name == name:
                return r
        return None

    def names(self) -> list[str]:
        """Return a list of all result names in this suite."""
        return [r.name for r in self.results]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "results": [r.to_dict() for r in self.results]}

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self) -> Iterator[BenchmarkResult]:
        return iter(self.results)


# ---------------------------------------------------------------------------
# Benchmarker — the core measurement primitive
# ---------------------------------------------------------------------------


class Benchmarker:
    """Measure the wall-clock time of a code block or callable.

    Can be used as a **context manager** to time an inline block::

        with Benchmarker("my_op") as bm:
            expensive_operation()
        print(bm.result.mean_s)

    Or call :meth:`run` / :meth:`run_async` to time a callable with multiple
    iterations::

        bm = Benchmarker("my_op", iterations=10, track_memory=True)
        result = bm.run(my_function, arg1, kwarg=value)

    Args:
        name: Human-readable label for this measurement.
        iterations: Number of times to repeat the callable (``run``/``run_async``
            only; ignored when used as a context manager).
        track_memory: If ``True``, enable :mod:`tracemalloc` memory tracking
            for the *last* iteration.
        warmup: Number of un-timed warm-up calls before the measured iterations.
        metadata: Arbitrary annotations stored in the result.
        suite: If provided, the completed result is automatically added to
            this :class:`BenchmarkSuite`.
    """

    def __init__(
        self,
        name: str,
        iterations: int = 1,
        track_memory: bool = False,
        warmup: int = 0,
        metadata: dict[str, Any] | None = None,
        suite: BenchmarkSuite | None = None,
    ) -> None:
        self.name = name
        self.iterations = max(1, iterations)
        self.track_memory = track_memory
        self.warmup = max(0, warmup)
        self.metadata = metadata or {}
        self.suite = suite
        self.result: BenchmarkResult = BenchmarkResult(
            name=name, iterations=self.iterations, metadata=self.metadata
        )
        self._start: float = 0.0

    # ------------------------------------------------------------------
    # Context-manager interface
    # ------------------------------------------------------------------

    def __enter__(self) -> Benchmarker:
        gc.disable()
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        elapsed = time.perf_counter() - self._start
        gc.enable()
        self.result.durations_s = [elapsed]
        self.result.iterations = 1
        if exc_val is not None:
            self.result.error = str(exc_val)
        if self.suite is not None:
            self.suite.add(self.result)

    # ------------------------------------------------------------------
    # Callable interface
    # ------------------------------------------------------------------

    def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run *func* and measure its performance.

        Args:
            func: The callable to benchmark.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of the *last* call to *func*.
        """
        # Warm-up rounds (not timed)
        for _ in range(self.warmup):
            try:
                func(*args, **kwargs)
            except Exception:
                pass

        last_return: Any = None
        durations: list[float] = []
        error: str | None = None

        for i in range(self.iterations):
            memory_tracked = self.track_memory and i == self.iterations - 1
            if memory_tracked:
                tracemalloc.start()

            gc.disable()
            t0 = time.perf_counter()
            try:
                last_return = func(*args, **kwargs)
            except Exception as exc:
                import traceback as _tb

                error = "".join(
                    _tb.format_tb(exc.__traceback__) if exc.__traceback__ else []
                ) + str(exc)
                logger.debug(f"Benchmark '{self.name}' raised an exception: {exc}")
            finally:
                elapsed = time.perf_counter() - t0
                gc.enable()
                durations.append(elapsed)

            if memory_tracked:
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                self.result.peak_memory_bytes = peak

        self.result.durations_s = durations
        self.result.iterations = len(durations)
        self.result.error = error

        if self.suite is not None:
            self.suite.add(self.result)

        return last_return

    async def run_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Async version of :meth:`run` for coroutine functions.

        Args:
            func: An async callable (coroutine function).
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of the *last* awaited call.
        """
        # Warm-up rounds
        for _ in range(self.warmup):
            try:
                await func(*args, **kwargs)
            except Exception:
                pass

        last_return: Any = None
        durations: list[float] = []
        error: str | None = None

        for i in range(self.iterations):
            memory_tracked = self.track_memory and i == self.iterations - 1
            if memory_tracked:
                tracemalloc.start()

            t0 = time.perf_counter()
            try:
                last_return = await func(*args, **kwargs)
            except Exception as exc:
                error = str(exc)
                logger.debug(f"Async benchmark '{self.name}' raised an exception: {exc}")
            finally:
                elapsed = time.perf_counter() - t0
                durations.append(elapsed)

            if memory_tracked:
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                self.result.peak_memory_bytes = peak

        self.result.durations_s = durations
        self.result.iterations = len(durations)
        self.result.error = error

        if self.suite is not None:
            self.suite.add(self.result)

        return last_return


# ---------------------------------------------------------------------------
# @benchmark decorator
# ---------------------------------------------------------------------------


def benchmark(
    name: str | None = None,
    *,
    iterations: int = 1,
    warmup: int = 0,
    track_memory: bool = False,
    suite: BenchmarkSuite | None = None,
    registry: BenchmarkRegistry | None = None,
    suite_name: str = "default",
    metadata: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator that benchmarks a sync or async callable.

    The decorated function behaves identically to the original — it returns
    the same value and accepts the same arguments.  After each call the
    :class:`BenchmarkResult` is stored in *suite* or in the global
    :class:`BenchmarkRegistry` under *suite_name*.

    Args:
        name: Override the benchmark name (defaults to ``func.__qualname__``).
        iterations: Number of timed iterations per invocation.
        warmup: Un-timed warm-up calls before the measured iterations.
        track_memory: Enable :mod:`tracemalloc` memory tracking.
        suite: Explicit :class:`BenchmarkSuite` to record results into.
        registry: Explicit :class:`BenchmarkRegistry` (defaults to global).
        suite_name: Suite name used when *suite* is ``None`` (looks up or
            creates a suite in the registry).
        metadata: Static metadata attached to every :class:`BenchmarkResult`.

    Returns:
        A decorator that wraps the target function.
    """

    def decorator(func: F) -> F:
        bm_name = name or func.__qualname__
        _registry = registry or BenchmarkRegistry.instance()

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _suite = suite if suite is not None else _registry.suite(suite_name)
                bm = Benchmarker(
                    bm_name,
                    iterations=iterations,
                    warmup=warmup,
                    track_memory=track_memory,
                    metadata=metadata or {},
                    suite=_suite,
                )
                return await bm.run_async(func, *args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            _suite = suite if suite is not None else _registry.suite(suite_name)
            bm = Benchmarker(
                bm_name,
                iterations=iterations,
                warmup=warmup,
                track_memory=track_memory,
                metadata=metadata or {},
                suite=_suite,
            )
            return bm.run(func, *args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# BenchmarkRegistry — global store
# ---------------------------------------------------------------------------


class BenchmarkRegistry:
    """Singleton registry that stores :class:`BenchmarkSuite` objects by name.

    Use :meth:`instance` to access the global instance::

        registry = BenchmarkRegistry.instance()
        suite = registry.suite("cache_benchmarks")
        print(generate_report(suite))

    To reset all data (e.g. between test runs)::

        BenchmarkRegistry.reset()
    """

    _global_instance: BenchmarkRegistry | None = None

    def __init__(self) -> None:
        self._suites: dict[str, BenchmarkSuite] = {}

    @classmethod
    def instance(cls) -> BenchmarkRegistry:
        """Return the process-wide singleton."""
        if cls._global_instance is None:
            cls._global_instance = cls()
        return cls._global_instance

    @classmethod
    def reset(cls) -> None:
        """Destroy the global singleton (useful for tests)."""
        cls._global_instance = None

    def suite(self, name: str) -> BenchmarkSuite:
        """Get or create a :class:`BenchmarkSuite` with the given *name*."""
        if name not in self._suites:
            self._suites[name] = BenchmarkSuite(name=name)
        return self._suites[name]

    def add_result(self, result: BenchmarkResult, suite_name: str = "default") -> None:
        """Add *result* to the named suite (creating it if needed)."""
        self.suite(suite_name).add(result)

    def all_suites(self) -> list[BenchmarkSuite]:
        """Return all registered suites."""
        return list(self._suites.values())

    def suite_names(self) -> list[str]:
        """Return names of all registered suites."""
        return list(self._suites.keys())

    def clear(self, suite_name: str | None = None) -> None:
        """Clear results — for a specific suite or all suites.

        Args:
            suite_name: If provided, only the named suite is cleared.
                Otherwise, *all* suite data is removed.
        """
        if suite_name is not None:
            if suite_name in self._suites:
                self._suites[suite_name] = BenchmarkSuite(name=suite_name)
        else:
            self._suites.clear()

    def to_dict(self) -> dict[str, Any]:
        return {name: suite.to_dict() for name, suite in self._suites.items()}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

_HEADER_WIDTH = 78
_COL_WIDTH = 12


def generate_report(suite: BenchmarkSuite, *, title: str | None = None) -> str:
    """Format a :class:`BenchmarkSuite` as a human-readable text report.

    Args:
        suite: The suite to report on.
        title: Override the report title (defaults to the suite name).

    Returns:
        A multi-line string suitable for ``print()`` or logging.
    """
    lines: list[str] = []
    heading = title or f"Benchmark Suite: {suite.name}"
    lines.append("=" * _HEADER_WIDTH)
    lines.append(heading.center(_HEADER_WIDTH))
    lines.append("=" * _HEADER_WIDTH)

    if not suite.results:
        lines.append("  (no results)")
        lines.append("=" * _HEADER_WIDTH)
        return "\n".join(lines)

    # Column headers
    col_names = ["Name", "Iter", "Mean (ms)", "Min (ms)", "Max (ms)", "Std (ms)", "ops/s"]
    col_widths = [30, 6, _COL_WIDTH, _COL_WIDTH, _COL_WIDTH, _COL_WIDTH, _COL_WIDTH]

    header = "  ".join(name.ljust(w) for name, w in zip(col_names, col_widths, strict=False))
    lines.append(header)
    lines.append("-" * _HEADER_WIDTH)

    for result in suite.results:
        if result.error:
            row = f"  {'[ERROR] ' + result.name:<28}  {result.error[:50]}"
        else:
            cells = [
                result.name[:30].ljust(col_widths[0]),
                str(result.iterations).ljust(col_widths[1]),
                f"{result.mean_s * 1000:.3f}".ljust(col_widths[2]),
                f"{result.min_s * 1000:.3f}".ljust(col_widths[3]),
                f"{result.max_s * 1000:.3f}".ljust(col_widths[4]),
                f"{result.stddev_s * 1000:.3f}".ljust(col_widths[5]),
                f"{result.ops_per_second:.1f}".ljust(col_widths[6]),
            ]
            row = "  ".join(cells)
            if result.peak_memory_bytes is not None:
                row += f"  peak_mem={result.peak_memory_bytes // 1024}KB"
        lines.append(row)

    lines.append("=" * _HEADER_WIDTH)
    return "\n".join(lines)
