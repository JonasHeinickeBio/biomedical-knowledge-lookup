"""
Unit tests for benchmarking module.
"""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.benchmarking import BenchmarkMetric, KnowledgeLookupBenchmarker
from knowledge_lookup.models import KnowledgeSource, LookupResult


class TestBenchmarkMetric:
    """Tests for BenchmarkMetric dataclass."""

    def test_benchmark_metric_creation(self):
        """Test creating a BenchmarkMetric."""
        metric = BenchmarkMetric(
            name="test",
            query="diabetes",
            sources=["bioportal", "ols"],
            execution_time=1.5,
            total_found=10,
            success_count=2,
            error_count=0,
            parallel=True,
        )
        assert metric.name == "test"
        assert metric.query == "diabetes"
        assert metric.execution_time == 1.5
        assert metric.total_found == 10
        assert metric.success_count == 2
        assert metric.parallel is True

    def test_benchmark_metric_defaults(self):
        """Test BenchmarkMetric default values."""
        metric = BenchmarkMetric(
            name="test",
            query="test",
            sources=["test"],
            execution_time=1.0,
            total_found=0,
            success_count=0,
            error_count=0,
            parallel=False,
        )
        assert metric.timestamp is not None
        assert metric.metadata == {}


class TestKnowledgeLookupBenchmarker:
    """Tests for KnowledgeLookupBenchmarker."""

    @pytest.fixture
    def benchmarker(self):
        """Create a benchmarker instance."""
        return KnowledgeLookupBenchmarker()

    @pytest.fixture
    def benchmarker_with_lookup(self):
        """Create a benchmarker with mock lookup."""
        mock_lookup = MagicMock()
        return KnowledgeLookupBenchmarker(lookup=mock_lookup)

    def test_benchmarker_initialization(self):
        """Test benchmarker initialization."""
        benchmarker = KnowledgeLookupBenchmarker()
        assert benchmarker.lookup is not None
        assert benchmarker.metrics == []

    def test_benchmarker_with_custom_lookup(self):
        """Test benchmarker with custom lookup."""
        mock_lookup = MagicMock()
        benchmarker = KnowledgeLookupBenchmarker(lookup=mock_lookup)
        assert benchmarker.lookup == mock_lookup

    def test_get_summary_empty(self, benchmarker):
        """Test get_summary with no metrics."""
        summary = benchmarker.get_summary()
        assert summary == {}

    def test_get_summary_with_metrics(self, benchmarker):
        """Test get_summary with metrics."""
        metric = BenchmarkMetric(
            name="test_benchmark",
            query="test",
            sources=["test"],
            execution_time=1.0,
            total_found=10,
            success_count=1,
            error_count=0,
            parallel=False,
        )
        benchmarker.metrics.append(metric)
        summary = benchmarker.get_summary()
        assert summary["total_runs"] == 1
        assert "test_benchmark" in summary["by_name"]

    def test_get_summary_multiple_metrics(self, benchmarker):
        """Test get_summary with multiple metrics."""
        for i in range(3):
            benchmarker.metrics.append(
                BenchmarkMetric(
                    name="test_benchmark",
                    query="test",
                    sources=["test"],
                    execution_time=1.0 + i,
                    total_found=10 + i,
                    success_count=1,
                    error_count=0,
                    parallel=False,
                )
            )
        summary = benchmarker.get_summary()
        assert summary["total_runs"] == 3

    @pytest.mark.asyncio
    async def test_benchmark_single_source(self, benchmarker):
        """Test benchmark_single_source."""
        mock_result = MagicMock()
        mock_result.total_found = 5
        mock_result.sources_succeeded = [KnowledgeSource.OLS]
        mock_result.errors = {}

        benchmarker.lookup.search_concepts = AsyncMock(return_value=mock_result)

        results = await benchmarker.benchmark_single_source(
            KnowledgeSource.OLS, ["test query"]
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_benchmark_combinations(self, benchmarker):
        """Test benchmark_combinations."""
        mock_result = MagicMock()
        mock_result.total_found = 5
        mock_result.sources_succeeded = [KnowledgeSource.OLS]
        mock_result.errors = {}

        benchmarker.lookup.search_concepts = AsyncMock(return_value=mock_result)

        results = await benchmarker.benchmark_combinations(
            [[KnowledgeSource.OLS]], ["test"], parallel=False
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_benchmark_parallel_vs_sequential(self, benchmarker):
        """Test benchmark_parallel_vs_sequential."""
        mock_result = MagicMock()
        mock_result.total_found = 5
        mock_result.sources_succeeded = [KnowledgeSource.OLS]
        mock_result.errors = {}

        benchmarker.lookup.search_concepts = AsyncMock(return_value=mock_result)

        results = await benchmarker.benchmark_parallel_vs_sequential(
            [KnowledgeSource.OLS], ["test"]
        )
        assert "parallel" in results
        assert "sequential" in results

    def test_save_results(self, benchmarker, tmp_path):
        """Test save_results writes JSON file."""
        metric = BenchmarkMetric(
            name="test",
            query="test",
            sources=["test"],
            execution_time=1.0,
            total_found=10,
            success_count=1,
            error_count=0,
            parallel=False,
        )
        benchmarker.metrics.append(metric)

        filepath = tmp_path / "benchmark_results.json"
        benchmarker.save_results(filepath)

        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert "summary" in data
        assert "metrics" in data

    def test_print_report_empty(self, benchmarker, capsys):
        """Test print_report with no data."""
        benchmarker.print_report()
        captured = capsys.readouterr()
        assert "No benchmark data available" in captured.out

    def test_print_report_with_data(self, benchmarker, capsys):
        """Test print_report with metrics."""
        metric = BenchmarkMetric(
            name="test_benchmark",
            query="test",
            sources=["test"],
            execution_time=1.0,
            total_found=10,
            success_count=1,
            error_count=0,
            parallel=False,
        )
        benchmarker.metrics.append(metric)

        benchmarker.print_report()
        captured = capsys.readouterr()
        assert "BENCHMARK REPORT" in captured.out
        assert "test_benchmark" in captured.out