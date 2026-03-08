"""
Modular benchmarking system for the knowledge lookup system.
"""

import asyncio
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from .central_lookup import CentralKnowledgeLookup
from .models import KnowledgeSource, LookupConfig, LookupResult

logger = logging.getLogger(__name__)

@dataclass
class BenchmarkMetric:
    """Metrics for a single benchmark run."""
    name: str
    query: str
    sources: List[str]
    execution_time: float
    total_found: int
    success_count: int
    error_count: int
    parallel: bool
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

class KnowledgeLookupBenchmarker:
    """
    Modular benchmarker for testing performance and accuracy of knowledge source lookups.
    """

    def __init__(self, lookup: Optional[CentralKnowledgeLookup] = None):
        self.lookup = lookup or CentralKnowledgeLookup()
        self.metrics: List[BenchmarkMetric] = []

    async def benchmark_single_source(self, source: KnowledgeSource, queries: List[str]) -> List[BenchmarkMetric]:
        """Benchmark performance of a single knowledge source."""
        results = []
        for query in queries:
            start_time = time.time()
            try:
                res = await self.lookup.search_concepts(query, sources=[source], parallel=False)
                duration = time.time() - start_time
                metric = BenchmarkMetric(
                    name=f"single_source_{source.value}",
                    query=query,
                    sources=[source.value],
                    execution_time=duration,
                    total_found=res.total_found,
                    success_count=len(res.sources_succeeded),
                    error_count=len(res.errors),
                    parallel=False
                )
                results.append(metric)
                self.metrics.append(metric)
            except Exception as e:
                logger.error(f"Benchmark failed for {source.value} with query '{query}': {e}")
        
        return results

    async def benchmark_combinations(self, combinations: List[List[KnowledgeSource]], queries: List[str], parallel: bool = True) -> List[BenchmarkMetric]:
        """Benchmark performance of different source combinations."""
        results = []
        for combo in combinations:
            combo_names = [s.value for s in combo]
            for query in queries:
                start_time = time.time()
                try:
                    res = await self.lookup.search_concepts(query, sources=combo, parallel=parallel)
                    duration = time.time() - start_time
                    metric = BenchmarkMetric(
                        name=f"combo_{'_'.join(combo_names)}",
                        query=query,
                        sources=combo_names,
                        execution_time=duration,
                        total_found=res.total_found,
                        success_count=len(res.sources_succeeded),
                        error_count=len(res.errors),
                        parallel=parallel
                    )
                    results.append(metric)
                    self.metrics.append(metric)
                except Exception as e:
                    logger.error(f"Benchmark failed for combo {combo_names} with query '{query}': {e}")
        
        return results

    async def benchmark_parallel_vs_sequential(self, sources: List[KnowledgeSource], queries: List[str]) -> Dict[str, List[BenchmarkMetric]]:
        """Compare parallel vs sequential lookup performance."""
        parallel_results = await self.benchmark_combinations([sources], queries, parallel=True)
        sequential_results = await self.benchmark_combinations([sources], queries, parallel=False)
        
        # Tag them for identification
        for m in parallel_results: m.name += "_parallel"
        for m in sequential_results: m.name += "_sequential"
        
        return {
            "parallel": parallel_results,
            "sequential": sequential_results
        }

    def get_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics from recorded metrics."""
        if not self.metrics:
            return {}
            
        summary = {
            "total_runs": len(self.metrics),
            "avg_execution_time": sum(m.execution_time for m in self.metrics) / len(self.metrics),
            "total_found": sum(m.total_found for m in self.metrics),
            "by_name": {}
        }
        
        # Group by name
        names = set(m.name for m in self.metrics)
        for name in names:
            name_metrics = [m for m in self.metrics if m.name == name]
            summary["by_name"][name] = {
                "count": len(name_metrics),
                "avg_time": sum(m.execution_time for m in name_metrics) / len(name_metrics),
                "avg_found": sum(m.total_found for m in name_metrics) / len(name_metrics),
                "success_rate": sum(1 for m in name_metrics if m.error_count == 0) / len(name_metrics)
            }
            
        return summary

    def save_results(self, filepath: Union[str, Path]):
        """Save benchmark results to a JSON file."""
        data = [asdict(m) for m in self.metrics]
        summary = self.get_summary()
        
        output = {
            "summary": summary,
            "metrics": data
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Benchmark results saved to {filepath}")

    def print_report(self):
        """Print a nicely formatted benchmark report to the console."""
        summary = self.get_summary()
        if not summary:
            print("No benchmark data available.")
            return
            
        print("\n" + "="*80)
        print("KNOWLEDGE LOOKUP BENCHMARK REPORT")
        print("="*80)
        print(f"Total runs: {summary['total_runs']}")
        print(f"Overall average time: {summary['avg_execution_time']:.3f}s")
        print("-" * 80)
        print(f"{'Benchmark Name':<40} | {'Runs':<6} | {'Avg Time':<10} | {'Avg Found':<10} | {'Success'}")
        print("-" * 80)
        
        for name, stats in sorted(summary['by_name'].items()):
            print(f"{name:<40} | {stats['count']:<6} | {stats['avg_time']:<10.3f} | {stats['avg_found']:<10.1f} | {stats['success_rate']*100:.1f}%")
        print("="*80 + "\n")
