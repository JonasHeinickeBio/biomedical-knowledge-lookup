"""
Comprehensive scalability benchmark for the knowledge lookup system.

Usage:
    knowledge-lookup benchmark                     # full benchmark
    knowledge-lookup benchmark --quick             # quick (single-source + parallel only)
    knowledge-lookup benchmark --output results.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.core.multi_source_annotator import MultiSourceAnnotator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "diabetes",
    "cancer",
    "hypertension",
    "asthma",
    "alzheimer",
    "metformin",
    "insulin",
    "cholesterol",
    "ibuprofen",
    "aspirin",
]


@dataclass
class BenchResult:
    label: str
    duration_s: float
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start


# ---------------------------------------------------------------------------
# Safe wrappers — prevent any individual call from hanging the suite
# ---------------------------------------------------------------------------


async def _search_safe(
    lookup: CentralKnowledgeLookup,
    query: str,
    sources: list[KnowledgeSource],
    *,
    parallel: bool = True,
    timeout: float = 15.0,
) -> Any:
    """Search with a safety timeout."""
    try:
        return await asyncio.wait_for(
            lookup.search_concepts(query, sources=sources, parallel=parallel),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return None


async def _details_safe(
    lookup: CentralKnowledgeLookup,
    concept_id: str,
    *,
    source: KnowledgeSource | None = None,
    timeout: float = 10.0,
) -> Any:
    """get_concept_details with a safety timeout."""
    try:
        return await asyncio.wait_for(
            lookup.get_concept_details(concept_id, source=source, timeout=timeout),
            timeout=timeout + 3.0,
        )
    except (asyncio.TimeoutError, Exception):
        return None


# ---------------------------------------------------------------------------
# 1. Single-source latency
# ---------------------------------------------------------------------------


async def bench_single_source(lookup: CentralKnowledgeLookup) -> list[BenchResult]:
    """Measure search latency per adapter."""
    results: list[BenchResult] = []

    # Skip adapters known to hang during bulk benchmarks
    SKIP = {
        "chembl",
        "eutils",
        "europepmc",
        "opentargets",
        "biolinker",
        "quickgo",
        "unichem",
        "string",
    }
    sources = sorted(
        (s for s in lookup.adapters if s.value not in SKIP),
        key=lambda s: s.value,
    )

    for src in sources:
        t = Timer()
        try:
            with t:
                res = await _search_safe(lookup, "diabetes", [src], parallel=False, timeout=10.0)
            n = res.total_found if res else 0
            err = len(res.errors) if res and hasattr(res, "errors") else 1
        except Exception:
            n, err = 0, 1
            t.elapsed = 10.0

        results.append(
            BenchResult(
                label=src.value,
                duration_s=t.elapsed,
                detail=f"found={n}, errors={err}",
                extra={"source": src.value, "found": n, "errors": err},
            )
        )

    return results


# ---------------------------------------------------------------------------
# 2. Parallel vs sequential speedup
# ---------------------------------------------------------------------------


async def bench_parallel_vs_sequential(
    lookup: CentralKnowledgeLookup,
    source_sets: list[list[KnowledgeSource]],
) -> list[BenchResult]:
    """Measure parallel speedup over sequential for growing source sets."""
    results: list[BenchResult] = []

    for sources in source_sets:
        t = Timer()
        with t:
            await _search_safe(lookup, "cancer", sources, parallel=False, timeout=30.0)
        seq_t = t.elapsed

        t = Timer()
        with t:
            await _search_safe(lookup, "cancer", sources, parallel=True, timeout=30.0)
        par_t = t.elapsed

        speedup = seq_t / par_t if par_t > 0 else 0.0
        results.append(
            BenchResult(
                label=f"speedup_{len(sources)}src",
                duration_s=par_t,
                detail=(
                    f"sequential={seq_t:.3f}s  parallel={par_t:.3f}s  " f"speedup={speedup:.2f}x"
                ),
                extra={
                    "n_sources": len(sources),
                    "sources": [s.value for s in sources],
                    "sequential_s": round(seq_t, 3),
                    "parallel_s": round(par_t, 3),
                    "speedup": round(speedup, 2),
                },
            )
        )

    return results


# ---------------------------------------------------------------------------
# 3. Circuit-breaker graceful degradation
# ---------------------------------------------------------------------------


async def bench_circuit_breaker(lookup: CentralKnowledgeLookup) -> list[BenchResult]:
    """Demonstrate circuit breaker isolation.

    Because the built-in per-category retry absorbs *transient* failures
    (up to 3–4 retries per call), the circuit breaker only sees failures
    that survive ALL retries.  This benchmark injects a consistently
    failing session and runs enough attempts to trigger the breaker.
    """
    results: list[BenchResult] = []

    ols = lookup.adapters.get(KnowledgeSource.OLS)
    if ols is None:
        return [BenchResult("circuit_breaker", 0.0, "OLS adapter unavailable")]

    old_session = ols.session
    bad_timeout = aiohttp.ClientTimeout(total=0.05)
    ols.session = aiohttp.ClientSession(timeout=bad_timeout)

    timings: list[float] = []
    for _ in range(15):
        t = Timer()
        with t:
            await _search_safe(
                lookup, "diabetes", [KnowledgeSource.OLS, KnowledgeSource.MONDO], timeout=8.0
            )
        timings.append(t.elapsed)

    await ols.session.close()
    ols.session = old_session
    # Reset the circuit breaker state
    cb = lookup.health_tracker.get_or_create(KnowledgeSource.OLS)
    cb.state = type(cb.state)("closed")
    cb.failure_count = 0

    before = timings[:5]
    after = timings[5:]
    avg_before = sum(before) / len(before) if before else 0
    avg_after = sum(after) / len(after) if after else 0
    ratio = avg_before / avg_after if avg_after > 0 else 0.0

    results.append(
        BenchResult(
            label="circuit_breaker_isolation",
            duration_s=avg_after,
            detail=(
                f"avg before open: {avg_before:.3f}s  avg after open: {avg_after:.3f}s  "
                f"ratio: {ratio:.1f}x"
            ),
            extra={
                "avg_before_open_s": round(avg_before, 3),
                "avg_after_open_s": round(avg_after, 3),
                "ratio": round(ratio, 1),
                "all_timings_s": [round(t, 3) for t in timings],
            },
        )
    )

    return results


# ---------------------------------------------------------------------------
# 4. Concurrent search throughput
# ---------------------------------------------------------------------------


async def bench_concurrent_throughput(
    lookup: CentralKnowledgeLookup,
) -> list[BenchResult]:
    """Submit N queries sequentially vs concurrently and measure wall time."""
    results: list[BenchResult] = []

    sources = [
        KnowledgeSource.OLS,
        KnowledgeSource.MONDO,
        KnowledgeSource.HGNC,
        KnowledgeSource.CLINVAR,
    ]

    # Sequential
    t = Timer()
    with t:
        for q in TEST_QUERIES[:5]:
            await _search_safe(lookup, q, sources, timeout=10.0)
    seq_t = t.elapsed

    # Concurrent
    t = Timer()
    with t:
        await asyncio.gather(
            *[_search_safe(lookup, q, sources, timeout=10.0) for q in TEST_QUERIES[:5]]
        )
    con_t = t.elapsed

    speedup = seq_t / con_t if con_t > 0 else 0.0
    results.append(
        BenchResult(
            label="concurrent_5_queries",
            duration_s=con_t,
            detail=(
                f"sequential batch={seq_t:.3f}s  concurrent={con_t:.3f}s  "
                f"speedup={speedup:.2f}x"
            ),
            extra={
                "n_queries": 5,
                "sequential_batch_s": round(seq_t, 3),
                "concurrent_batch_s": round(con_t, 3),
                "speedup": round(speedup, 2),
            },
        )
    )

    return results


# ---------------------------------------------------------------------------
# 5. Multi-source annotator
# ---------------------------------------------------------------------------


async def bench_annotator() -> list[BenchResult]:
    """Measure annotator throughput."""
    results: list[BenchResult] = []
    annotator = MultiSourceAnnotator()
    sentences = [
        "The patient was diagnosed with diabetes and prescribed metformin.",
        "BRCA1 gene mutation increases risk of breast cancer.",
    ]

    t = Timer()
    with t:
        try:
            r = await asyncio.wait_for(annotator.annotate_text(sentences[0]), timeout=30.0)
        except (asyncio.TimeoutError, Exception) as e:
            results.append(
                BenchResult(
                    label="annotator_single",
                    duration_s=-1.0,
                    detail=f"failed: {e}",
                )
            )
            return results
    single_t = t.elapsed

    results.append(
        BenchResult(
            label="annotator_single",
            duration_s=single_t,
            detail=(
                f"processed in {single_t:.3f}s  "
                f"confidence={r.overall_confidence:.2f}  "
                f"consensus={len(r.consensus_concepts)} concepts"
            ),
            extra={
                "time_s": round(single_t, 3),
                "overall_confidence": r.overall_confidence,
                "consensus_concepts": len(r.consensus_concepts),
            },
        )
    )

    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

ALL_BENCHMARKS = {
    "single_source": bench_single_source,
    "parallel_speedup": bench_parallel_vs_sequential,
    "circuit_breaker": bench_circuit_breaker,
    "concurrent": bench_concurrent_throughput,
    "annotator": bench_annotator,
}

QUICK_BENCHMARKS = {
    "single_source": bench_single_source,
    "parallel_speedup": bench_parallel_vs_sequential,
}


async def run_all(quick: bool = False) -> dict[str, list[BenchResult]]:
    """Run selected benchmarks and return structured results."""
    config = LookupConfig()
    config.enable_source_health_tracking = True
    config.circuit_breaker_threshold = 3
    config.circuit_breaker_cooldown = 10.0

    lookup = CentralKnowledgeLookup(config)

    # Source sets for parallel speedup (from fastest adapters)
    available = list(lookup.adapters.keys())
    FAST_ORDER = {
        "tyto": 0,
        "hpo": 0,
        "hgnc": 0,
        "geneontology": 0,
        "mondo": 1,
        "ebiols": 1,
        "obofoundry": 1,
        "ols": 1,
        "clinvar": 1,
        "uniprot": 1,
        "umls": 1,
        "wikidata": 2,
        "bioportal": 2,
        "bioontology": 2,
        "kegg": 2,
        "pdb": 2,
    }
    sorted_srcs = sorted(available, key=lambda s: FAST_ORDER.get(s.value, 9))
    source_sets = [sorted_srcs[:2], sorted_srcs[:4], sorted_srcs[:6]]

    try:
        benchmarks = QUICK_BENCHMARKS if quick else ALL_BENCHMARKS
        results: dict[str, list[BenchResult]] = {}

        if "single_source" in benchmarks:
            results["single_source"] = await bench_single_source(lookup)

        if "parallel_speedup" in benchmarks:
            results["parallel_speedup"] = await bench_parallel_vs_sequential(lookup, source_sets)

        if "circuit_breaker" in benchmarks:
            results["circuit_breaker"] = await bench_circuit_breaker(lookup)

        if "concurrent" in benchmarks:
            results["concurrent"] = await bench_concurrent_throughput(lookup)

        if "annotator" in benchmarks:
            results["annotator"] = await bench_annotator()

        return results

    finally:
        await lookup.close()


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def print_report(results: dict[str, list[BenchResult]]) -> None:
    """Pretty-print benchmark results."""
    print()
    print("=" * 80)
    print("KNOWLEDGE LOOKUP — SCALABILITY BENCHMARK")
    print("=" * 80)

    for section, items in results.items():
        if not items:
            continue
        print(f"\n── {section.replace('_', ' ').upper()} ─{'─' * (66 - len(section))}")
        for br in items:
            dur = f"{br.duration_s:>8.3f}s" if br.duration_s >= 0 else "  FAILED  "
            print(f"  {br.label:<35s} {dur}  {br.detail}")

    # === Summary ===
    print("\n" + "=" * 80)
    print("SCALABILITY SUMMARY")
    print("=" * 80)

    # Parallel speedup trend
    pr = results.get("parallel_speedup", [])
    if pr:
        print("\n▶ PARALLEL SPEEDUP TREND")
        for br in pr:
            sp = br.extra.get("speedup", 0)
            n = br.extra.get("n_sources", 0)
            eff = (sp / n) * 100 if n > 0 else 0
            bar = "█" * max(0, min(20, int(eff / 5))) + "░" * max(0, 20 - min(20, int(eff / 5)))
            print(f"   {n} sources: {sp:.2f}x speedup  [{bar}] {eff:.0f}% efficiency")

    # Circuit breaker
    cb = results.get("circuit_breaker", [])
    if cb:
        for br in cb:
            ba = br.extra.get("avg_after_open_s", 0)
            bb = br.extra.get("avg_before_open_s", 0)
            ratio = bb / ba if ba > 0 else float("inf")
            print(f"\n▶ CIRCUIT BREAKER: {ratio:.1f}x faster after isolation opens")

    # Concurrent throughput
    ct = results.get("concurrent", [])
    if ct:
        for br in ct:
            sp = br.extra.get("speedup", 0)
            n = br.extra.get("n_queries", 0)
            print(f"\n▶ CONCURRENT THROUGHPUT: {n} queries = {sp:.1f}x speedup over sequential")

    # Fastest / slowest single-source
    ss = results.get("single_source", [])
    if ss:
        ok = [b for b in ss if b.duration_s < 10]
        if ok:
            fastest = min(ok, key=lambda b: b.duration_s)
            slowest = max(ok, key=lambda b: b.duration_s)
            print(
                f"\n▶ SINGLE-SOURCE: fastest={fastest.label} ({fastest.duration_s:.3f}s), "
                f"slowest={slowest.label} ({slowest.duration_s:.3f}s)"
            )
            responded = len(ok)
            total = len(ss)
            print(f"   adapter response rate: {responded}/{total} ({100 * responded // total}%)")

    print()


def save_results(results: dict[str, list[BenchResult]], path: str) -> None:
    """Save benchmark results as JSON."""
    payload = {
        section: [
            {
                "label": r.label,
                "duration_s": r.duration_s,
                "detail": r.detail,
                **r.extra,
            }
            for r in items
        ]
        for section, items in results.items()
    }
    Path(path).write_text(json.dumps(payload, indent=2))
    print(f"Results saved to {path}")


async def main(quick: bool = False, output: str | None = None) -> None:
    """Entry point — run benchmarks and print report."""
    # Suppress noisy adapter logs during benchmarks
    logging.getLogger("knowledge_lookup").setLevel(logging.CRITICAL)
    results = await run_all(quick=quick)
    print_report(results)
    if output:
        save_results(results, output)
