"""
Batch Concept Extraction Pipeline

Processes CSV, JSON, or plain-text files of biomedical terms through the
UMLS adapter (local cache → REST fallback) for large-scale concept
normalization and enrichment.  Designed for NLP pipeline integration.

Features
--------
- CSV / JSON / plain-text (one-per-line) input
- Automatic de-duplication and progress reporting
- Configurable concurrency and rate-limiting
- Results output as CSV, JSON, or RDF (via ``knowledge_lookup.umls.rdf``)
- Resume support — skips already-processed CUIs on re-run

Usage::

    from knowledge_lookup.umls.batch import BatchProcessor

    processor = BatchProcessor(adapter)
    results = await processor.process_file("terms.csv", column="term")
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..models import UnifiedConcept

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of a batch processing run."""

    total_inputs: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed: float = 0.0
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_inputs": self.total_inputs,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "elapsed_seconds": round(self.elapsed, 2),
            "results": self.results,
            "errors": self.errors,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class BatchProcessor:
    """Process multiple biomedical terms through a UMLS (or any) adapter.

    Parameters
    ----------
    adapter :
        An adapter instance with ``search_concepts(query, limit=...)``.
        Typically a :class:`~knowledge_lookup.adapters.UMLSAdapter`.
    concurrency :
        Maximum number of simultaneous API calls.
    rate_limit :
        Minimum seconds between calls (per-source).  ``0`` disables.
    cache_results :
        Whether to keep results in memory for aggregation.
    """

    def __init__(
        self,
        adapter: Any,
        *,
        concurrency: int = 5,
        rate_limit: float = 0.1,
        cache_results: bool = True,
    ):
        self.adapter = adapter
        self.concurrency = concurrency
        self.rate_limit = rate_limit
        self.cache_results = cache_results
        self._sem = asyncio.Semaphore(concurrency)
        self._last_call: float = 0.0

    # ── Public API ─────────────────────────────────────────────────

    async def process_file(
        self,
        path: str | Path,
        *,
        column: str | None = None,
        limit_per_term: int = 5,
        output_path: str | Path | None = None,
        output_format: str = "json",
        resume: bool = False,
        skip_header: bool = True,
        encoding: str = "utf-8",
    ) -> BatchResult:
        """Process terms from a file.

        Parameters
        ----------
        path :
            Input file path.  Supported formats:
            - ``.csv``  — reads the *column* or first column
            - ``.json`` — reads a list of strings or ``[{...}]``
            - ``.txt``  — one term per line
        column :
            For CSV: the column name containing terms.  ``None`` = first column.
        limit_per_term :
            Maximum concepts to retrieve per term.
        output_path :
            Optional file path to write results.
        output_format :
            ``"json"`` (default), ``"csv"``, or ``"rdf"``.
        resume :
            If ``True``, skip terms already present in *output_path*.
        skip_header :
            Whether to skip the first line of CSV files.
        encoding :
            File encoding.

        Returns
        -------
        Aggregated batch result.
        """
        path = Path(path)
        terms = self._load_terms(path, column=column, skip_header=skip_header, encoding=encoding)

        # Resume: skip terms already in output
        seen_cuis: set[str] = set()
        if resume and output_path and Path(output_path).exists():
            seen_cuis = self._load_existing_cuis(output_path)

        return await self.process_terms(
            terms,
            limit=limit_per_term,
            skip_cuis=seen_cuis,
            output_path=output_path,
            output_format=output_format,
        )

    async def process_terms(
        self,
        terms: list[str],
        *,
        limit: int = 5,
        skip_cuis: set[str] | None = None,
        output_path: str | Path | None = None,
        output_format: str = "json",
    ) -> BatchResult:
        """Process a list of term strings through the adapter.

        Parameters
        ----------
        terms :
            List of biomedical term strings to look up.
        limit :
            Maximum concepts per term.
        skip_cuis :
            CUIs to skip (used for resume support).
        output_path, output_format :
            Same as :meth:`process_file`.

        Returns
        -------
        Aggregated batch result.
        """
        result = BatchResult(total_inputs=len(terms))
        skip = skip_cuis or set()
        start = time.monotonic_ns()

        # Deduplicate terms while preserving order
        seen_terms: set[str] = set()
        unique_terms: list[str] = []
        for t in terms:
            t_clean = t.strip()
            if t_clean and t_clean not in seen_terms:
                seen_terms.add(t_clean)
                unique_terms.append(t_clean)

        result.skipped = len(terms) - len(unique_terms)

        # Process with bounded concurrency
        async def process_one(term: str) -> None:
            async with self._sem:
                await self._throttle()
                try:
                    concepts = await self.adapter.search_concepts(term, limit=limit)
                    entry: dict[str, Any] = {
                        "query": term,
                        "count": len(concepts),
                        "concepts": [
                            {
                                "cui": c.primary_id,
                                "name": c.primary_label,
                                "type": c.concept_type,
                                "score": c.confidence_score,
                                "definitions": c.definitions,
                                "synonyms": c.synonyms,
                            }
                            for c in concepts
                        ],
                    }

                    # Filter already-seen CUIs
                    entry["concepts"] = [c for c in entry["concepts"] if c["cui"] not in skip]
                    skip.update(c["cui"] for c in entry["concepts"])

                    if self.cache_results:
                        result.results.append(entry)
                    result.succeeded += 1
                    logger.info("[OK] %s → %d concepts", term, len(concepts))
                except Exception as exc:
                    result.failed += 1
                    error_entry = {"query": term, "error": str(exc)}
                    result.errors.append(error_entry)
                    logger.warning("[FAIL] %s: %s", term, exc)

        tasks = [process_one(t) for t in unique_terms]
        await asyncio.gather(*tasks)

        result.elapsed = time.monotonic() - start

        # Write output if requested
        if output_path:
            self._write_output(result, Path(output_path), output_format)

        logger.info(
            "Batch done: %d/%d succeeded, %d failed, %d skipped in %.1fs",
            result.succeeded,
            result.total_inputs,
            result.failed,
            result.skipped,
            result.elapsed,
        )
        return result

    async def iter_results(
        self,
        terms: list[str],
        *,
        limit: int = 5,
    ) -> AsyncIterator[dict[str, Any]]:
        """Process terms and yield results one by one (streaming).

        Useful for real-time processing where you want results as soon
        as they're available rather than waiting for the full batch.
        """
        for term in terms:
            term = term.strip()
            if not term:
                continue
            async with self._sem:
                await self._throttle()
                try:
                    concepts = await self.adapter.search_concepts(term, limit=limit)
                    yield {
                        "query": term,
                        "count": len(concepts),
                        "concepts": [
                            {
                                "cui": c.primary_id,
                                "name": c.primary_label,
                                "type": c.concept_type,
                                "score": c.confidence_score,
                            }
                            for c in concepts
                        ],
                    }
                except Exception as exc:
                    yield {"query": term, "error": str(exc)}

    # ── File I/O ────────────────────────────────────────────────────

    @staticmethod
    def _load_terms(
        path: Path,
        column: str | None = None,
        skip_header: bool = True,
        encoding: str = "utf-8",
    ) -> list[str]:
        """Load terms from a file based on its extension."""
        suffix = path.suffix.lower()

        if suffix == ".csv":
            return _load_csv_terms(path, column=column, skip_header=skip_header, encoding=encoding)
        elif suffix == ".json":
            return _load_json_terms(path, encoding=encoding)
        else:
            # Plain text: one term per line
            text = path.read_text(encoding=encoding)
            return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _load_existing_cuis(output_path: str | Path) -> set[str]:
        """Load CUIs from an existing output file for resume support."""
        cuis: set[str] = set()
        path = Path(output_path)
        if not path.exists():
            return cuis
        try:
            data = json.loads(path.read_text())
            for entry in data if isinstance(data, list) else data.get("results", []):
                for c in entry.get("concepts", []):
                    if c.get("cui"):
                        cuis.add(c["cui"])
        except Exception:
            logger.warning("Could not parse existing output for resume: %s", path)
        return cuis

    def _write_output(
        self,
        result: BatchResult,
        path: Path,
        fmt: str,
    ) -> None:
        """Write batch results to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            self._write_csv(result, path)
        elif fmt == "rdf":
            self._write_rdf(result, path)
        else:
            path.write_text(result.to_json(), encoding="utf-8")
            logger.info("Wrote batch results to %s", path)

    def _write_csv(self, result: BatchResult, path: Path) -> None:
        """Write results as flat CSV."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["query", "cui", "name", "type", "score", "definition", "synonyms"])
            for entry in result.results:
                for c in entry.get("concepts", []):
                    writer.writerow(
                        [
                            entry["query"],
                            c.get("cui", ""),
                            c.get("name", ""),
                            c.get("type", ""),
                            c.get("score", ""),
                            "; ".join(c.get("definitions", [])),
                            "; ".join(c.get("synonyms", [])),
                        ]
                    )

    def _write_rdf(self, result: BatchResult, path: Path) -> None:
        """Write results as RDF (Turtle)."""
        from rdflib import Graph

        from .rdf import concept_to_graph

        g = Graph()
        for entry in result.results:
            for c_data in entry.get("concepts", []):
                # Reconstruct a minimal UnifiedConcept for serialisation
                concept = UnifiedConcept(
                    primary_id=c_data.get("cui", ""),
                    primary_label=c_data.get("name", ""),
                    definitions=c_data.get("definitions", []),
                    synonyms=c_data.get("synonyms", []),
                )
                try:
                    concept_to_graph(concept, graph=g)
                except Exception:
                    pass
        g.serialize(destination=str(path), format="turtle")
        logger.info("Wrote batch RDF to %s", path)

    # ── Rate limiting ───────────────────────────────────────────────┐

    async def _throttle(self) -> None:
        """Apply rate limiting between adapter calls."""
        if self.rate_limit <= 0:
            return
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_call = time.monotonic()


# ── Module-level helpers ────────────────────────────────────────────


def _load_csv_terms(
    path: Path,
    column: str | None = None,
    skip_header: bool = True,
    encoding: str = "utf-8",
) -> list[str]:
    """Extract terms from a CSV file."""
    terms: list[str] = []
    column_index: int = 0  # default: first column
    with open(path, newline="", encoding=encoding) as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                # Header row
                if column is not None:
                    try:
                        column_index = row.index(column)
                    except ValueError:
                        logger.warning("Column '%s' not found; using first column", column)
                        column_index = 0
                if skip_header:
                    continue
            if not row:
                continue
            val = row[column_index].strip() if column_index < len(row) else ""
            if val:
                terms.append(val)
    return terms


def _load_json_terms(path: Path, encoding: str = "utf-8") -> list[str]:
    """Extract terms from a JSON file.

    Supports:
    - ``["term1", "term2", ...]``
    - ``[{"term": "..."}, ...]``  (uses ``"term"`` key)
    - ``{"terms": ["...", ...]}``
    """
    data = json.loads(path.read_text(encoding=encoding))
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return [item.get("term", item.get("name", "")) for item in data]
        return [str(item) for item in data]
    if isinstance(data, dict):
        for key in ("terms", "queries", "items", "data"):
            if key in data and isinstance(data[key], list):
                return [str(item) for item in data[key]]
    logger.warning("Unrecognised JSON structure in %s", path)
    return []
