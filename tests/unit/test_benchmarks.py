"""
Unit tests for the modular benchmarking system.
"""

import asyncio
import time

import pytest
from knowledge_lookup.benchmarks import (
    Benchmarker,
    BenchmarkRegistry,
    BenchmarkResult,
    BenchmarkSuite,
    benchmark,
    generate_report,
)

# ---------------------------------------------------------------------------
# BenchmarkResult
# ---------------------------------------------------------------------------


class TestBenchmarkResult:
    def test_total_s(self):
        r = BenchmarkResult(name="test", iterations=3, durations_s=[0.1, 0.2, 0.3])
        assert abs(r.total_s - 0.6) < 1e-9

    def test_mean_s(self):
        r = BenchmarkResult(name="test", iterations=2, durations_s=[0.1, 0.3])
        assert abs(r.mean_s - 0.2) < 1e-9

    def test_min_max(self):
        r = BenchmarkResult(name="test", iterations=3, durations_s=[0.1, 0.5, 0.3])
        assert r.min_s == pytest.approx(0.1)
        assert r.max_s == pytest.approx(0.5)

    def test_stddev_single_sample(self):
        r = BenchmarkResult(name="test", iterations=1, durations_s=[0.1])
        assert r.stddev_s == 0.0

    def test_ops_per_second(self):
        r = BenchmarkResult(name="test", iterations=10, durations_s=[0.1] * 10)
        # 10 iterations / 1.0 s total = 10 ops/s
        assert abs(r.ops_per_second - 10.0) < 0.01

    def test_ops_per_second_zero_duration(self):
        r = BenchmarkResult(name="test", iterations=1, durations_s=[])
        assert r.ops_per_second == 0.0

    def test_to_dict_keys(self):
        r = BenchmarkResult(name="x", iterations=1, durations_s=[0.05])
        d = r.to_dict()
        for key in ("name", "iterations", "total_s", "mean_s", "min_s", "max_s", "ops_per_second"):
            assert key in d

    def test_repr(self):
        r = BenchmarkResult(name="my_bench", iterations=5, durations_s=[0.01] * 5)
        assert "my_bench" in repr(r)


# ---------------------------------------------------------------------------
# BenchmarkSuite
# ---------------------------------------------------------------------------


class TestBenchmarkSuite:
    def test_add_and_get(self):
        suite = BenchmarkSuite(name="s")
        r = BenchmarkResult(name="op1", iterations=1, durations_s=[0.05])
        suite.add(r)
        assert suite.get("op1") is r

    def test_get_missing_returns_none(self):
        suite = BenchmarkSuite(name="s")
        assert suite.get("nope") is None

    def test_names(self):
        suite = BenchmarkSuite(name="s")
        suite.add(BenchmarkResult(name="a", durations_s=[0.1]))
        suite.add(BenchmarkResult(name="b", durations_s=[0.2]))
        assert suite.names() == ["a", "b"]

    def test_len(self):
        suite = BenchmarkSuite(name="s")
        assert len(suite) == 0
        suite.add(BenchmarkResult(name="a", durations_s=[0.1]))
        assert len(suite) == 1

    def test_iter(self):
        suite = BenchmarkSuite(name="s")
        suite.add(BenchmarkResult(name="a", durations_s=[0.1]))
        results = list(suite)
        assert len(results) == 1

    def test_to_dict(self):
        suite = BenchmarkSuite(name="my_suite")
        suite.add(BenchmarkResult(name="op", durations_s=[0.1]))
        d = suite.to_dict()
        assert d["name"] == "my_suite"
        assert len(d["results"]) == 1


# ---------------------------------------------------------------------------
# Benchmarker
# ---------------------------------------------------------------------------


class TestBenchmarkerContextManager:
    def test_measures_elapsed_time(self):
        with Benchmarker("sleep_test") as bm:
            time.sleep(0.01)
        assert bm.result.total_s >= 0.01
        assert len(bm.result.durations_s) == 1

    def test_stores_in_suite(self):
        suite = BenchmarkSuite(name="ctx_suite")
        with Benchmarker("ctx_op", suite=suite) as bm:
            pass
        assert suite.get("ctx_op") is bm.result

    def test_captures_error(self):
        bm = Benchmarker("err_test")
        try:
            with bm:
                raise ValueError("oops")
        except ValueError:
            pass
        assert bm.result.error is not None
        assert "oops" in bm.result.error


class TestBenchmarkerRun:
    def test_run_single_iteration(self):
        bm = Benchmarker("single")
        result = bm.run(lambda: 42)
        assert result == 42
        assert bm.result.iterations == 1
        assert len(bm.result.durations_s) == 1

    def test_run_multiple_iterations(self):
        bm = Benchmarker("multi", iterations=5)
        bm.run(lambda: None)
        assert bm.result.iterations == 5
        assert len(bm.result.durations_s) == 5

    def test_run_returns_last_value(self):
        counter = {"n": 0}

        def inc():
            counter["n"] += 1
            return counter["n"]

        bm = Benchmarker("counter", iterations=3)
        last = bm.run(inc)
        assert last == 3

    def test_run_with_args(self):
        bm = Benchmarker("add")
        result = bm.run(lambda a, b: a + b, 3, 4)
        assert result == 7

    def test_run_handles_exception(self):
        def bad():
            raise RuntimeError("fail")

        bm = Benchmarker("bad", iterations=1)
        bm.run(bad)
        assert bm.result.error is not None

    def test_run_warmup_not_counted(self):
        call_times = []

        def log_time():
            call_times.append(time.perf_counter())

        bm = Benchmarker("warmup_test", iterations=2, warmup=3)
        bm.run(log_time)
        # 3 warmup + 2 timed = 5 total calls
        assert len(call_times) == 5
        # But only 2 durations recorded
        assert bm.result.iterations == 2

    def test_run_memory_tracking(self):
        bm = Benchmarker("mem_test", track_memory=True)
        bm.run(lambda: [0] * 1000)
        assert bm.result.peak_memory_bytes is not None
        assert bm.result.peak_memory_bytes >= 0


@pytest.mark.asyncio
class TestBenchmarkerRunAsync:
    async def test_run_async_single(self):
        bm = Benchmarker("async_single")

        async def noop():
            return "ok"

        result = await bm.run_async(noop)
        assert result == "ok"
        assert bm.result.iterations == 1

    async def test_run_async_multiple_iterations(self):
        bm = Benchmarker("async_multi", iterations=4)

        async def noop():
            await asyncio.sleep(0)

        await bm.run_async(noop)
        assert bm.result.iterations == 4

    async def test_run_async_stores_in_suite(self):
        suite = BenchmarkSuite(name="async_suite")
        bm = Benchmarker("async_op", suite=suite)

        async def noop():
            pass

        await bm.run_async(noop)
        assert suite.get("async_op") is bm.result


# ---------------------------------------------------------------------------
# @benchmark decorator
# ---------------------------------------------------------------------------


class TestBenchmarkDecorator:
    def setup_method(self):
        """Reset the global registry before each test."""
        BenchmarkRegistry.reset()

    def test_sync_function_returns_value(self):
        @benchmark("add_two")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_sync_function_records_in_registry(self):
        @benchmark("recorded_op", suite_name="deco_suite")
        def op():
            return 1

        op()
        reg = BenchmarkRegistry.instance()
        suite = reg.suite("deco_suite")
        assert suite.get("recorded_op") is not None

    def test_sync_decorator_with_iterations(self):
        call_count = {"n": 0}

        @benchmark("iter_test", iterations=3, suite_name="deco_suite2")
        def inc():
            call_count["n"] += 1

        inc()
        reg = BenchmarkRegistry.instance()
        result = reg.suite("deco_suite2").get("iter_test")
        assert result is not None
        assert result.iterations == 3
        assert call_count["n"] == 3

    def test_sync_decorator_with_explicit_suite(self):
        suite = BenchmarkSuite(name="explicit")

        @benchmark("expl_op", suite=suite)
        def op():
            return 99

        op()
        assert suite.get("expl_op") is not None

    @pytest.mark.asyncio
    async def test_async_function_returns_value(self):
        @benchmark("async_add")
        async def add(a, b):
            return a + b

        assert await add(10, 5) == 15

    @pytest.mark.asyncio
    async def test_async_function_records_in_registry(self):
        @benchmark("async_recorded", suite_name="async_deco_suite")
        async def op():
            return "x"

        await op()
        reg = BenchmarkRegistry.instance()
        suite = reg.suite("async_deco_suite")
        assert suite.get("async_recorded") is not None


# ---------------------------------------------------------------------------
# BenchmarkRegistry
# ---------------------------------------------------------------------------


class TestBenchmarkRegistry:
    def setup_method(self):
        BenchmarkRegistry.reset()

    def test_singleton(self):
        r1 = BenchmarkRegistry.instance()
        r2 = BenchmarkRegistry.instance()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        r1 = BenchmarkRegistry.instance()
        BenchmarkRegistry.reset()
        r2 = BenchmarkRegistry.instance()
        assert r1 is not r2

    def test_suite_created_on_demand(self):
        reg = BenchmarkRegistry.instance()
        s = reg.suite("new_suite")
        assert isinstance(s, BenchmarkSuite)

    def test_same_suite_returned_twice(self):
        reg = BenchmarkRegistry.instance()
        s1 = reg.suite("x")
        s2 = reg.suite("x")
        assert s1 is s2

    def test_add_result(self):
        reg = BenchmarkRegistry.instance()
        reg.add_result(BenchmarkResult(name="r", durations_s=[0.1]), suite_name="s")
        assert reg.suite("s").get("r") is not None

    def test_suite_names(self):
        reg = BenchmarkRegistry.instance()
        reg.suite("alpha")
        reg.suite("beta")
        assert "alpha" in reg.suite_names()
        assert "beta" in reg.suite_names()

    def test_clear_specific_suite(self):
        reg = BenchmarkRegistry.instance()
        reg.add_result(BenchmarkResult(name="r1", durations_s=[0.1]), suite_name="keep")
        reg.add_result(BenchmarkResult(name="r2", durations_s=[0.1]), suite_name="clear_me")
        reg.clear("clear_me")
        assert len(reg.suite("keep")) == 1
        assert len(reg.suite("clear_me")) == 0

    def test_clear_all_suites(self):
        reg = BenchmarkRegistry.instance()
        reg.suite("a")
        reg.suite("b")
        reg.clear()
        assert reg.suite_names() == []

    def test_to_dict(self):
        reg = BenchmarkRegistry.instance()
        reg.add_result(BenchmarkResult(name="x", durations_s=[0.01]), suite_name="d")
        d = reg.to_dict()
        assert "d" in d


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_empty_suite(self):
        suite = BenchmarkSuite(name="empty")
        report = generate_report(suite)
        assert "empty" in report
        assert "no results" in report

    def test_report_contains_result_name(self):
        suite = BenchmarkSuite(name="rep")
        suite.add(BenchmarkResult(name="my_op", iterations=5, durations_s=[0.01] * 5))
        report = generate_report(suite)
        assert "my_op" in report

    def test_report_with_error(self):
        suite = BenchmarkSuite(name="err_suite")
        r = BenchmarkResult(name="bad_op", durations_s=[0.0], error="something went wrong")
        suite.add(r)
        report = generate_report(suite)
        assert "bad_op" in report or "ERROR" in report

    def test_custom_title(self):
        suite = BenchmarkSuite(name="s")
        report = generate_report(suite, title="My Custom Title")
        assert "My Custom Title" in report
