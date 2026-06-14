"""
Central Knowledge Lookup System

Unified interface for querying multiple biological knowledge sources.
"""

import asyncio
import csv
import json
import logging
import time
from pathlib import Path
from typing import Any, cast

# Optional imports for formatting
try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None
from concurrent.futures import ThreadPoolExecutor

# RDF support
try:
    from rdflib import Graph

    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

    # Placeholder for Graph class when rdflib is not available
    # This is intentionally used for optional dependency support
    class Graph:  # type: ignore[no-redef]
        """Dummy Graph class when rdflib is not installed."""

        pass


from .adapters import ADAPTER_CLASSES
from .base import KnowledgeSourceAdapter
from .models import (
    ConceptIdentifier,
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    SourceHealth,
    UnifiedConcept,
)
from .utils.retry_utils import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source health tracker — wraps circuit breakers for all adapters
# ---------------------------------------------------------------------------


class SourceHealthTracker:
    """Manages per-source circuit breakers and provides health snapshots.

    Each source gets its own :class:`CircuitBreaker` which is injected
    into the adapter via :meth:`KnowledgeSourceAdapter.set_circuit_breaker`.
    """

    def __init__(self, config: LookupConfig) -> None:
        self._config = config
        self._breakers: dict[KnowledgeSource, CircuitBreaker] = {}

    def get_or_create(self, source: KnowledgeSource) -> CircuitBreaker:
        """Return existing breaker for *source* or create a new one."""
        if source not in self._breakers:
            self._breakers[source] = CircuitBreaker(
                threshold=self._config.circuit_breaker_threshold,
                cooldown=self._config.circuit_breaker_cooldown,
            )
        return self._breakers[source]

    def wire_adapter(self, source: KnowledgeSource, adapter: KnowledgeSourceAdapter) -> None:
        """Create a breaker for *source* and inject it into the adapter."""
        if self._config.enable_source_health_tracking:
            cb = self.get_or_create(source)
            adapter.set_circuit_breaker(cb)

    def get_health(self, source: KnowledgeSource) -> SourceHealth | None:
        """Return a :class:`SourceHealth` snapshot, or ``None`` if untracked."""
        cb = self._breakers.get(source)
        if cb is None:
            return None
        stats = cb.stats()
        return SourceHealth(
            source=source,
            circuit_state=cb.state,
            failure_count=cb.failure_count,
            threshold=cb.threshold,
            cooldown=cb.cooldown,
            total_calls=cb.total_calls,
            total_failures=cb.total_failures,
            total_successes=cb.total_successes,
            health_score=cb.health,
        )

    def all_health(self) -> dict[KnowledgeSource, SourceHealth]:
        """Return health snapshots for every tracked source."""
        return {
            src: health
            for src in self._breakers
            if (health := self.get_health(src)) is not None
        }

    def open_sources(self) -> set[KnowledgeSource]:
        """Return the set of sources whose circuit breaker is open."""
        return {
            src for src, cb in self._breakers.items() if cb.state == CircuitState.OPEN
        }


class CentralKnowledgeLookup:
    """
    Central lookup class that queries and integrates different knowledge sources.

    Provides unified access to:
    - UMLS (Unified Medical Language System)
    - OLS (Ontology Lookup Service)
    - BioPortal (NCBI BioPortal)
    - BioOntology
    - OxO (Ontology Cross-reference Service)
    - Wikidata
    - DBpedia
    - And more open source knowledge graphs
    """

    def __init__(self, config: LookupConfig | None = None, auto_initialize: bool = True):
        """
        Initialize the central lookup system.

        Args:
            config: Configuration for lookup operations
            auto_initialize: Whether to automatically initialize all enabled adapters
        """
        self.config = config or LookupConfig()
        # If no sources are enabled, enable all sources by default
        if not self.config.enabled_sources:
            self.config.enabled_sources = list(KnowledgeSource)
        self.adapters: dict[KnowledgeSource, KnowledgeSourceAdapter] = {}
        self.health_tracker = SourceHealthTracker(self.config)
        self.executor = ThreadPoolExecutor(max_workers=10)
        if auto_initialize:
            self._initialize_adapters()

    def _initialize_adapters(self):
        """Initialize available knowledge source adapters and wire circuit breakers."""
        typed_adapters = cast(dict[KnowledgeSource, type[KnowledgeSourceAdapter]], ADAPTER_CLASSES)
        for source, adapter_class in typed_adapters.items():
            if self.config.is_source_enabled(source):
                try:
                    adapter = adapter_class(self.config)
                    if adapter.is_available():
                        self.health_tracker.wire_adapter(source, adapter)
                        self.adapters[source] = adapter
                        logger.info(f"Initialized {source.value} adapter")
                    else:
                        logger.warning(f"{source.value} adapter not available")
                except Exception as e:
                    logger.error(f"Failed to initialize {source.value} adapter: {e}")

    def _get_adapter(self, source: KnowledgeSource) -> KnowledgeSourceAdapter | None:
        """Internal helper to get an adapter for a source."""
        return self.adapters.get(source)

    async def add_source(self, source: KnowledgeSource):
        """
        Add a specific knowledge source to the lookup system.
        """
        typed_adapters = cast(dict[KnowledgeSource, type[KnowledgeSourceAdapter]], ADAPTER_CLASSES)
        if source not in typed_adapters:
            raise ValueError(f"Unsupported knowledge source: {source.value}")
        if source in self.adapters:
            logger.info(f"{source.value} adapter already exists")
            return
        try:
            adapter_class = typed_adapters[source]
            adapter = adapter_class(self.config)
            if adapter.is_available():
                self.health_tracker.wire_adapter(source, adapter)
                self.adapters[source] = adapter
                if source not in self.config.enabled_sources:
                    self.config.enabled_sources.append(source)
                logger.info(f"Added {source.value} adapter")
            else:
                raise RuntimeError(f"{source.value} adapter is not available")
        except Exception as e:
            logger.error(f"Failed to add {source.value} adapter: {e}")
            raise RuntimeError(f"Failed to initialize {source.value} adapter: {e}") from e

    def remove_source(self, source: KnowledgeSource):
        """
        Remove a knowledge source from the lookup system.

        Args:
            source: The knowledge source to remove
        """
        if source in self.adapters:
            try:
                # Close the adapter if it has a close method
                adapter = self.adapters[source]
                if hasattr(adapter, "close"):
                    # Note: This is sync, if the adapter needs async close,
                    # this would need to be an async method
                    pass

                del self.adapters[source]

                # Remove from enabled sources in config
                if source in self.config.enabled_sources:
                    self.config.enabled_sources.remove(source)

                logger.info(f"Removed {source.value} adapter")
            except Exception as e:
                logger.error(f"Error removing {source.value} adapter: {e}")
        else:
            logger.warning(f"{source.value} adapter not found")

    def get_available_sources(self) -> list[KnowledgeSource]:
        """
        Get the list of currently available knowledge sources.

        Returns:
            List of available knowledge sources
        """
        return list(self.adapters.keys())

    async def search_concepts(
        self,
        query: str,
        concept_types: list[ConceptType] | None = None,
        sources: list[KnowledgeSource] | None = None,
        max_results: int = 50,
        parallel: bool = True,
    ) -> LookupResult:
        """
        Search for concepts across multiple knowledge sources.

        Args:
            query: Search term or phrase
            concept_types: Filter by specific concept types
            sources: Specific sources to query (if None, uses all available)
            max_results: Maximum total results to return
            parallel: Whether to query sources in parallel

        Returns:
            LookupResult with unified concepts from all sources
        """
        start_time = time.time()

        # Determine which sources to query
        query_sources = sources or list(self.adapters.keys())
        query_sources = [s for s in query_sources if s in self.adapters]

        result = LookupResult(query=query, sources_queried=query_sources)

        if not query_sources:
            logger.warning("No available sources for query")
            return result

        # Query sources
        if parallel and len(query_sources) > 1:
            concepts = await self._search_parallel(query, query_sources, max_results)
        else:
            concepts = await self._search_sequential(query, query_sources, max_results)

        # Process results
        for source, source_concepts in concepts.items():
            if isinstance(source_concepts, Exception):
                result.add_error(source, str(source_concepts))
            else:
                result.add_concepts(source_concepts, source)

        # Filter by concept types if specified
        if concept_types:
            filtered_concepts = []
            for concept in result.concepts:
                if concept.concept_type in concept_types:
                    filtered_concepts.append(concept)
            result.concepts = filtered_concepts
            result.total_found = len(filtered_concepts)

        # Apply deduplication and merging
        if self.config.enable_deduplication:
            result.concepts = self._deduplicate_concepts(result.concepts)
            result.total_found = len(result.concepts)

        # Sort by confidence and limit results
        result.concepts = sorted(result.concepts, key=lambda c: c.confidence_score, reverse=True)[
            :max_results
        ]

        result.execution_time = time.time() - start_time

        # Attach health snapshot
        if self.config.enable_source_health_tracking:
            result.source_health = self.health_tracker.all_health()

        logger.info(
            f"Search for '{query}' completed in {result.execution_time:.2f}s. "
            f"Found {result.total_found} concepts from {len(result.sources_succeeded)} sources."
        )

        return result

    async def get_concept_details(
        self, concept_id: str, source: KnowledgeSource | None = None, timeout: float | None = None
    ) -> UnifiedConcept | None:
        """
        Get detailed information about a specific concept.

        Args:
            concept_id: Identifier of the concept
            source: Specific source to query (if None, tries all sources in parallel)

        Returns:
            Unified concept with detailed information
        """
        _timeout = timeout or self.config.timeout_per_source

        if source and source in self.adapters:
            try:
                return await asyncio.wait_for(
                    self.adapters[source].get_concept_details(concept_id),
                    timeout=_timeout,
                )
            except Exception as e:
                logger.error(f"Failed to get concept details from {source.value}: {e}")
                return None

        # Try all available sources in parallel, return the first success
        async def _try_source(src: KnowledgeSource, adp: KnowledgeSourceAdapter) -> UnifiedConcept | None:
            try:
                return await asyncio.wait_for(
                    adp.get_concept_details(concept_id), timeout=_timeout,
                )
            except Exception:
                return None

        tasks = [
            _try_source(src, adp) for src, adp in self.adapters.items()
        ]
        results = await asyncio.gather(*tasks)

        for concept in results:
            if concept is not None:
                return concept

        return None

    async def find_mappings(
        self, concept_id: str, target_sources: list[KnowledgeSource] | None = None
    ) -> list[ConceptIdentifier]:
        """
        Find cross-references and mappings for a concept.

        Args:
            concept_id: Source concept identifier
            target_sources: Target sources to find mappings to

        Returns:
            List of concept identifiers in other sources
        """
        mappings: list[ConceptIdentifier] = []

        # Get concept details first
        concept = await self.get_concept_details(concept_id)
        if not concept:
            return mappings

        # Extract existing mappings from concept
        for identifier in concept.identifiers:
            if target_sources is None or identifier.source in target_sources:
                mappings.append(identifier)

        # Query mapping services (like OxO) if available
        # This would be implemented when OxO adapter is added

        return mappings

    async def get_concept_hierarchy(
        self,
        concept_id: str,
        levels: int = 1,
        direction: str = "both",  # "up", "down", "both"
    ) -> dict[str, list[UnifiedConcept]]:
        """
        Get hierarchical relationships for a concept.

        Args:
            concept_id: Concept identifier
            levels: Number of hierarchy levels to traverse
            direction: Direction to traverse ("up", "down", "both")

        Returns:
            Dictionary with "parents", "children", and "siblings" lists
        """
        hierarchy: dict[str, list[UnifiedConcept]] = {
            "parents": [],
            "children": [],
            "siblings": [],
        }

        concept = await self.get_concept_details(concept_id)
        if not concept:
            return hierarchy

        # Get immediate parents and children
        if direction in ["up", "both"] and concept.parents:
            for parent_id in concept.parents[:10]:  # Limit to avoid too many requests
                parent_concept = await self.get_concept_details(parent_id)
                if parent_concept:
                    hierarchy["parents"].append(parent_concept)

        if direction in ["down", "both"] and concept.children:
            for child_id in concept.children[:10]:  # Limit to avoid too many requests
                child_concept = await self.get_concept_details(child_id)
                if child_concept:
                    hierarchy["children"].append(child_concept)

        return hierarchy

    async def suggest_similar_concepts(
        self, concept_id: str, similarity_threshold: float = 0.8
    ) -> list[UnifiedConcept]:
        """
        Find concepts similar to the given concept.

        Args:
            concept_id: Reference concept identifier
            similarity_threshold: Minimum similarity score

        Returns:
            List of similar concepts
        """
        concept = await self.get_concept_details(concept_id)
        if not concept:
            return []

        # Search using the concept's label and synonyms
        search_terms = [concept.primary_label] + concept.synonyms[:3]  # Limit search terms

        similar_concepts = []
        for term in search_terms:
            if term:
                result = await self.search_concepts(
                    term,
                    concept_types=(
                        [concept.concept_type]
                        if concept.concept_type != ConceptType.UNKNOWN
                        else None
                    ),
                    max_results=20,
                )

                for similar_concept in result.concepts:
                    if (
                        similar_concept.primary_id != concept_id
                        and similar_concept.confidence_score >= similarity_threshold
                    ):
                        similar_concepts.append(similar_concept)

        # Remove duplicates and sort by confidence
        seen_ids = set()
        unique_similar = []
        for similar_concept in similar_concepts:
            if similar_concept.primary_id not in seen_ids:
                unique_similar.append(similar_concept)
                seen_ids.add(similar_concept.primary_id)

        return sorted(unique_similar, key=lambda c: c.confidence_score, reverse=True)[:10]

    async def _search_parallel(
        self, query: str, sources: list[KnowledgeSource], max_results: int
    ) -> dict[KnowledgeSource, list[UnifiedConcept] | Exception]:
        """Search sources in parallel with per-source timeout."""
        tasks = []
        per_source_limit = max(1, max_results // len(sources))

        for source in sources:
            if source in self.adapters:
                # Skip sources whose circuit breaker is open
                if self.config.enable_source_health_tracking:
                    health = self.health_tracker.get_health(source)
                    if health and health.is_open:
                        logger.warning(
                            "Skipping %s (circuit breaker open, %d consecutive failures)",
                            source.value, health.failure_count,
                        )
                        continue

                task = asyncio.create_task(
                    self._search_single_source(source, query, per_source_limit)
                )
                tasks.append((source, task))

        results: dict[KnowledgeSource, list[UnifiedConcept] | Exception] = {}
        for source, task in tasks:
            try:
                concepts = await asyncio.wait_for(
                    task, timeout=self.config.timeout_per_source
                )
                results[source] = concepts
            except asyncio.TimeoutError:
                msg = f"Timed out after {self.config.timeout_per_source}s"
                results[source] = TimeoutError(msg)
            except Exception as e:
                results[source] = e

        return results

    async def _search_sequential(
        self, query: str, sources: list[KnowledgeSource], max_results: int
    ) -> dict[KnowledgeSource, list[UnifiedConcept] | Exception]:
        """Search sources sequentially."""
        results: dict[KnowledgeSource, list[UnifiedConcept] | Exception] = {}
        per_source_limit = max(1, max_results // len(sources))

        for source in sources:
            try:
                concepts = await self._search_single_source(source, query, per_source_limit)
                results[source] = concepts
            except Exception as e:
                results[source] = e

        return results

    async def _search_single_source(
        self, source: KnowledgeSource, query: str, limit: int
    ) -> list[UnifiedConcept]:
        """Search a single knowledge source."""
        if source not in self.adapters:
            raise ValueError(f"Adapter for {source.value} not available")

        adapter = self.adapters[source]

        # Apply rate limiting
        rate_limit = adapter.get_rate_limit()
        if rate_limit > 0:
            await asyncio.sleep(1.0 / rate_limit)

        return await adapter.search_concepts(query, limit)

    def _deduplicate_concepts(self, concepts: list[UnifiedConcept]) -> list[UnifiedConcept]:
        """Remove duplicate concepts and merge similar ones."""
        if not concepts:
            return concepts

        # Group concepts by normalized label for exact matches
        label_groups: dict[str, list[UnifiedConcept]] = {}
        for concept in concepts:
            normalized_label = concept.primary_label.lower().strip()
            if normalized_label not in label_groups:
                label_groups[normalized_label] = []
            label_groups[normalized_label].append(concept)

        deduplicated = []

        for _label, group_concepts in label_groups.items():
            if len(group_concepts) == 1:
                deduplicated.append(group_concepts[0])
            else:
                # Merge concepts with same label
                merged_concept = group_concepts[0]
                for concept in group_concepts[1:]:
                    merged_concept = merged_concept.merge_with(concept)
                deduplicated.append(merged_concept)

        return deduplicated

    async def get_statistics(self) -> dict[str, Any]:
        """Get usage statistics for the lookup system."""
        stats = {
            "available_sources": list(self.adapters.keys()),
            "total_sources": len(self.adapters),
            "enabled_sources": len(self.config.enabled_sources),
            "config": {
                "max_results_per_source": self.config.max_results_per_source,
                "timeout_per_source": self.config.timeout_per_source,
                "parallel_queries": self.config.parallel_queries,
                "min_confidence_threshold": self.config.min_confidence_threshold,
                "enable_deduplication": self.config.enable_deduplication,
                "similarity_threshold": self.config.similarity_threshold,
                "circuit_breaker_threshold": self.config.circuit_breaker_threshold,
                "circuit_breaker_cooldown": self.config.circuit_breaker_cooldown,
            },
            "source_health": {
                src.value: {
                    "state": h.circuit_state.value,
                    "health_score": h.health_score,
                    "total_calls": h.total_calls,
                    "total_failures": h.total_failures,
                }
                for src, h in self.health_tracker.all_health().items()
            },
        }
        logger.info(
            f"Statistics: {len(self.adapters)} sources available, "
            f"Source health: {sum(1 for h in stats['source_health'].values() if h['state'] == 'open')} open"
        )
        return stats

    def format_results_table(self, result: LookupResult, max_width: int = 120) -> str:
        """
        Format search results as a nice table for console output.

        Args:
            result: LookupResult to format
            max_width: Maximum width for table columns

        Returns:
            Formatted table string
        """
        if not result.concepts:
            return f"No results found for query: '{result.query}'"

        # Helper function to truncate text
        def truncate(text: str, max_len: int) -> str:
            return text[: max_len - 3] + "..." if len(text) > max_len else text

        # Calculate column widths
        label_width = min(40, max(len(c.primary_label) for c in result.concepts[:10]) + 2)
        id_width = min(30, max(len(c.primary_id) for c in result.concepts[:10]) + 2)
        sources_width = min(20, max(len(str(c.sources)) for c in result.concepts[:10]) + 2)

        # Header
        lines = []
        lines.append("=" * max_width)
        lines.append(f"SEARCH RESULTS FOR: '{result.query}'")
        lines.append("=" * max_width)
        lines.append(
            f"Execution time: {result.execution_time:.2f}s | "
            f"Total found: {result.total_found} | "
            f"Sources queried: {len(result.sources_queried)}"
        )
        lines.append("-" * max_width)

        # Table header
        header = f"{'#':<3} {'Label':<{label_width}} {'ID':<{id_width}} {'Sources':<{sources_width}} {'Confidence':<10} {'Type':<15}"  # noqa: E501
        lines.append(header)
        lines.append("-" * max_width)

        # Table rows
        for i, concept in enumerate(result.concepts[:20], 1):  # Limit to 20 for readability
            label = truncate(concept.primary_label, label_width)
            concept_id = truncate(concept.primary_id, id_width)
            sources = truncate(str([s.value for s in concept.sources]), sources_width)
            confidence = f"{concept.confidence_score:.2f}"
            concept_type = concept.concept_type.value[:14]

            row = f"{i:<3} {label:<{label_width}} {concept_id:<{id_width}} {sources:<{sources_width}} {confidence:<10} {concept_type:<15}"  # noqa: E501
            lines.append(row)

        if len(result.concepts) > 20:
            lines.append(f"... and {len(result.concepts) - 20} more results")

        lines.append("=" * max_width)

        # Source health summary
        if result.source_health:
            lines.append("SOURCE HEALTH:")
            opened = [src.value for src, h in result.source_health.items() if h.is_open]
            if opened:
                lines.append(f"  CIRCUIT OPEN: {', '.join(opened)}")
            lines.append(
                f"  Avg health: {sum(h.health_score for h in result.source_health.values()) / max(len(result.source_health), 1):.2f}"
            )

        if result.source_health or result.errors:
            lines.append("")

        # Error summary
        if result.errors:
            lines.append(f"ERRORS: {len(result.errors)} source(s) failed")
            for source, error in result.errors.items():
                lines.append(f"  - {source}: {truncate(str(error), 80)}")

        return "\n".join(lines)

    def format_results_detailed(self, result: LookupResult) -> str:
        """
        Format search results with detailed information for each concept.

        Args:
            result: LookupResult to format

        Returns:
            Detailed formatted string
        """
        if not result.concepts:
            return f"No results found for query: '{result.query}'"

        lines = []
        lines.append("=" * 80)
        lines.append(f"DETAILED RESULTS FOR: '{result.query}'")
        lines.append("=" * 80)
        lines.append(f"Query executed in {result.execution_time:.2f} seconds")
        lines.append(f"Total concepts found: {result.total_found}")
        lines.append(f"Sources queried: {[s.value for s in result.sources_queried]}")
        lines.append(f"Sources succeeded: {[s.value for s in result.sources_succeeded]}")

        if result.errors:
            lines.append(f"Sources with errors: {list(result.errors.keys())}")

        lines.append("\n" + "=" * 80)

        for i, concept in enumerate(result.concepts[:10], 1):  # Limit for readability
            lines.append(f"\n{i}. {concept.primary_label}")
            lines.append(f"   ID: {concept.primary_id}")
            lines.append(f"   Type: {concept.concept_type.value}")
            lines.append(f"   Sources: {[s.value for s in concept.sources]}")
            lines.append(f"   Confidence: {concept.confidence_score:.3f}")

            if concept.definitions:
                definition = concept.definitions[0]
                if len(definition) > 200:
                    definition = definition[:200] + "..."
                lines.append(f"   Definition: {definition}")

            if concept.synonyms:
                synonyms = ", ".join(concept.synonyms[:5])
                if len(concept.synonyms) > 5:
                    synonyms += f" ... (+{len(concept.synonyms) - 5} more)"
                lines.append(f"   Synonyms: {synonyms}")

            if concept.semantic_types:
                types = ", ".join(concept.semantic_types[:3])
                lines.append(f"   Semantic Types: {types}")

            if concept.categories:
                cats = ", ".join(concept.categories[:3])
                lines.append(f"   Categories: {cats}")

            lines.append("-" * 70)

        if len(result.concepts) > 10:
            lines.append(
                f"\n... and {len(result.concepts) - 10} more results (use export functions for full data)"  # noqa: E501
            )

        return "\n".join(lines)

    def export_to_json(
        self, result: LookupResult, filepath: str | Path | None = None
    ) -> str | dict:
        """
        Export search results to JSON format.

        Args:
            result: LookupResult to export
            filepath: Optional file path to save JSON. If None, returns JSON dict

        Returns:
            JSON string if filepath provided, dict otherwise
        """
        json_data: dict[str, Any] = {
            "query": result.query,
            "execution_time": result.execution_time,
            "total_found": result.total_found,
            "sources_queried": [s.value for s in result.sources_queried],
            "sources_succeeded": [s.value for s in result.sources_succeeded],
            "errors": {k: str(v) for k, v in result.errors.items()} if result.errors else {},
            "concepts": [],
        }

        for concept in result.concepts:
            concept_data = {
                "primary_label": concept.primary_label,
                "primary_id": concept.primary_id,
                "concept_type": concept.concept_type.value,
                "confidence_score": concept.confidence_score,
                "sources": [s.value for s in concept.sources],
                "definitions": concept.definitions,
                "synonyms": concept.synonyms,
                "semantic_types": concept.semantic_types,
                "categories": concept.categories,
                "parents": concept.parents,
                "children": concept.children,
                "identifiers": (
                    [
                        {
                            "source": id.source.value,
                            "identifier": id.identifier,
                            "label": id.label,
                            "url": id.url,
                        }
                        for id in concept.identifiers
                    ]
                    if concept.identifiers
                    else []
                ),
            }
            json_data["concepts"].append(concept_data)

        if filepath:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Results exported to JSON: {filepath}")
            return str(filepath)

        return json_data

    def export_to_csv(self, result: LookupResult, filepath: str | Path) -> str:
        """
        Export search results to CSV format.

        Args:
            result: LookupResult to export
            filepath: File path to save CSV

        Returns:
            Path to saved file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "primary_label",
                "primary_id",
                "concept_type",
                "confidence_score",
                "sources",
                "definitions",
                "synonyms",
                "semantic_types",
                "categories",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Header
            writer.writeheader()

            # Write metadata as comment rows
            writer.writerow(
                {
                    "primary_label": f"# Query: {result.query}",
                    "primary_id": f"Execution time: {result.execution_time:.2f}s",
                    "concept_type": f"Total found: {result.total_found}",
                    "confidence_score": f"Sources: {len(result.sources_queried)}",
                    "sources": "",
                    "definitions": "",
                    "synonyms": "",
                    "semantic_types": "",
                    "categories": "",
                }
            )

            # Data rows
            for concept in result.concepts:
                writer.writerow(
                    {
                        "primary_label": concept.primary_label,
                        "primary_id": concept.primary_id,
                        "concept_type": concept.concept_type.value,
                        "confidence_score": concept.confidence_score,
                        "sources": "; ".join([s.value for s in concept.sources]),
                        "definitions": (
                            "; ".join(concept.definitions) if concept.definitions else ""
                        ),
                        "synonyms": "; ".join(concept.synonyms) if concept.synonyms else "",
                        "semantic_types": (
                            "; ".join(concept.semantic_types) if concept.semantic_types else ""
                        ),
                        "categories": "; ".join(concept.categories) if concept.categories else "",
                    }
                )

        logger.info(f"Results exported to CSV: {filepath}")
        return str(filepath)

    def export_to_ttl(
        self,
        result: LookupResult,
        filepath: str | Path,
        namespace: str = "http://example.org/concepts/",
    ) -> str:
        """
        Export search results to Turtle (TTL) RDF format.

        Args:
            result: LookupResult to export
            filepath: File path to save TTL
            namespace: Base namespace for concepts

        Returns:
            Path to saved file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = []

        # Prefixes
        lines.append("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
        lines.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
        lines.append("@prefix skos: <http://www.w3.org/2004/02/skos/core#> .")
        lines.append("@prefix dct: <http://purl.org/dc/terms/> .")
        lines.append(f"@prefix ex: <{namespace}> .")
        lines.append("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
        lines.append("")

        # Query metadata
        query_uri = f"ex:query_{hash(result.query) % 100000}"
        lines.append(f"{query_uri} a dct:BibliographicResource ;")
        lines.append(f'    dct:title "{result.query}" ;')
        lines.append(f'    dct:created "{time.strftime("%Y-%m-%dT%H:%M:%S")}"^^xsd:dateTime ;')
        lines.append(f'    ex:executionTime "{result.execution_time:.2f}"^^xsd:decimal ;')
        lines.append(f'    ex:totalFound "{result.total_found}"^^xsd:integer .')
        lines.append("")

        # Concepts
        for _i, concept in enumerate(result.concepts):
            concept_id = concept.primary_id.replace(":", "_").replace("/", "_").replace("#", "_")
            concept_uri = f"ex:concept_{concept_id}"

            lines.append(f"{concept_uri} a skos:Concept ;")
            lines.append(
                f'    skos:prefLabel "{self._escape_ttl_string(concept.primary_label)}" ;'
            )
            lines.append(f'    dct:identifier "{concept.primary_id}" ;')
            lines.append(f'    ex:conceptType "{concept.concept_type.value}" ;')
            lines.append(f'    ex:confidenceScore "{concept.confidence_score:.3f}"^^xsd:decimal ;')

            # Sources
            for source in concept.sources:
                lines.append(f'    dct:source "{source.value}" ;')

            # Definitions
            for definition in concept.definitions[:3]:  # Limit to avoid too large files
                lines.append(f'    skos:definition "{self._escape_ttl_string(definition)}" ;')

            # Synonyms
            for synonym in concept.synonyms[:10]:  # Limit synonyms
                lines.append(f'    skos:altLabel "{self._escape_ttl_string(synonym)}" ;')

            # Semantic types
            for sem_type in concept.semantic_types[:5]:
                lines.append(f'    ex:semanticType "{self._escape_ttl_string(sem_type)}" ;')

            # Remove last semicolon and add period
            if lines[-1].endswith(" ;"):
                lines[-1] = lines[-1][:-2] + " ."

            lines.append("")

        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Results exported to TTL: {filepath}")
        return str(filepath)

    def _escape_ttl_string(self, text: str) -> str:
        """Escape special characters for TTL format."""
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

    def export_to_dataframe(self, result: LookupResult) -> Any:
        """
        Export search results to pandas DataFrame.

        Args:
            result: LookupResult to export

        Returns:
            pandas DataFrame with results
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for DataFrame export. Install with: pip install pandas"
            ) from None

        data = []
        for concept in result.concepts:
            data.append(
                {
                    "primary_label": concept.primary_label,
                    "primary_id": concept.primary_id,
                    "concept_type": concept.concept_type.value,
                    "confidence_score": concept.confidence_score,
                    "sources": [s.value for s in concept.sources],
                    "num_sources": len(concept.sources),
                    "definitions": concept.definitions,
                    "num_definitions": len(concept.definitions),
                    "synonyms": concept.synonyms,
                    "num_synonyms": len(concept.synonyms),
                    "semantic_types": concept.semantic_types,
                    "categories": concept.categories,
                    "parents": concept.parents,
                    "children": concept.children,
                }
            )

        df = pd.DataFrame(data)

        # Add metadata as attributes
        df.attrs["query"] = result.query
        df.attrs["execution_time"] = result.execution_time
        df.attrs["total_found"] = result.total_found
        df.attrs["sources_queried"] = [s.value for s in result.sources_queried]
        df.attrs["sources_succeeded"] = [s.value for s in result.sources_succeeded]

        return df

    def export_to_excel(self, result: LookupResult, filepath: str | Path) -> str:
        """
        Export search results to Excel format with multiple sheets.

        Args:
            result: LookupResult to export
            filepath: File path to save Excel file

        Returns:
            Path to saved file
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for Excel export. Install with: pip install pandas openpyxl"
            ) from None

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Create main DataFrame
        df = self.export_to_dataframe(result)

        # Create summary data
        summary_data = {
            "Metric": [
                "Query",
                "Execution Time (s)",
                "Total Found",
                "Sources Queried",
                "Sources Succeeded",
            ],
            "Value": [
                result.query,
                result.execution_time,
                result.total_found,
                len(result.sources_queried),
                len(result.sources_succeeded),
            ],
        }
        summary_df = pd.DataFrame(summary_data)

        # Source statistics
        source_stats: dict[str, int] = {}
        for concept in result.concepts:
            for source in concept.sources:
                source_stats[source.value] = source_stats.get(source.value, 0) + 1

        source_df = pd.DataFrame(list(source_stats.items()), columns=["Source", "Concept Count"])
        source_df = source_df.sort_values("Concept Count", ascending=False)

        # Write to Excel with multiple sheets
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # Summary sheet
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Main results sheet
            df.to_excel(writer, sheet_name="Results", index=False)

            # Source statistics sheet
            source_df.to_excel(writer, sheet_name="Source Stats", index=False)

            # Errors sheet (if any)
            if result.errors:
                error_data = [{"Source": k, "Error": str(v)} for k, v in result.errors.items()]
                error_df = pd.DataFrame(error_data)
                error_df.to_excel(writer, sheet_name="Errors", index=False)

        logger.info(f"Results exported to Excel: {filepath}")
        return str(filepath)

    def export_summary_report(self, result: LookupResult, filepath: str | Path) -> str:
        """
        Generate a comprehensive summary report in text format.

        Args:
            result: LookupResult to analyze
            filepath: File path to save report

        Returns:
            Path to saved file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("KNOWLEDGE LOOKUP ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Query: '{result.query}'")
        lines.append(f"Execution Time: {result.execution_time:.2f} seconds")
        lines.append("")

        # Overview
        lines.append("OVERVIEW")
        lines.append("-" * 40)
        lines.append(f"Total concepts found: {result.total_found}")
        lines.append(f"Sources queried: {len(result.sources_queried)}")
        lines.append(f"Sources succeeded: {len(result.sources_succeeded)}")
        lines.append(
            f"Success rate: {len(result.sources_succeeded) / len(result.sources_queried) * 100:.1f}%"  # noqa: E501
        )
        lines.append("")

        # Source breakdown
        source_stats: dict[str, int] = {}
        for concept in result.concepts:
            for source in concept.sources:
                source_stats[source.value] = source_stats.get(source.value, 0) + 1

        lines.append("SOURCE CONTRIBUTION")
        lines.append("-" * 40)
        for source_name, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):
            percentage = count / result.total_found * 100
            lines.append(f"{source_name:15} {count:3d} concepts ({percentage:5.1f}%)")
        lines.append("")

        # Quality metrics
        avg_confidence = 0.0
        if result.concepts:
            confidence_scores = [c.confidence_score for c in result.concepts]
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            high_confidence = len([c for c in result.concepts if c.confidence_score > 0.8])

            lines.append("QUALITY METRICS")
            lines.append("-" * 40)
            lines.append(f"Average confidence score: {avg_confidence:.3f}")
            lines.append(
                f"High confidence results (>0.8): {high_confidence} ({high_confidence / len(result.concepts) * 100:.1f}%)"  # noqa: E501
            )
            lines.append(
                f"Multi-source concepts: {len([c for c in result.concepts if len(c.sources) > 1])}"
            )
            lines.append("")

        # Top results
        lines.append("TOP 10 RESULTS")
        lines.append("-" * 40)
        for i, concept in enumerate(result.concepts[:10], 1):
            lines.append(f"{i:2d}. {concept.primary_label}")
            lines.append(f"    ID: {concept.primary_id}")
            lines.append(f"    Confidence: {concept.confidence_score:.3f}")
            lines.append(f"    Sources: {[s.value for s in concept.sources]}")
            lines.append("")

        # Errors (if any)
        if result.errors:
            lines.append("ERRORS AND ISSUES")
            lines.append("-" * 40)
            for source, error in result.errors.items():
                lines.append(f"{source}: {str(error)[:100]}")
            lines.append("")

        # Recommendations
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 40)
        if result.total_found == 0:
            lines.append("• No results found. Try broader search terms or check spelling.")
        elif result.total_found < 5:
            lines.append("• Few results found. Consider using synonyms or related terms.")
        elif len(source_stats) == 1:
            lines.append(
                "• Results from single source. Consider enabling more sources for comprehensive coverage."  # noqa: E501
            )

        if result.errors:
            lines.append("• Some sources failed. Check error details and network connectivity.")

        if result.concepts and avg_confidence < 0.7:
            lines.append("• Low average confidence. Results may need manual validation.")

        lines.append("")
        lines.append("=" * 80)

        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Summary report generated: {filepath}")
        return str(filepath)

    async def lookup_and_convert_to_rdf(
        self,
        query: str,
        output_path: str | Path | None = None,
        concept_types: list[ConceptType] | None = None,
        sources: list[KnowledgeSource] | None = None,
        max_results: int = 50,
        rdf_format: str = "turtle",
        adapter_hints: Any | None = None,
    ) -> Any:
        """
        Search for concepts and convert results directly to RDF.

        This is a convenience method that combines search and RDF conversion
        in a single call, integrating with the UnifiedRDFConverter.

        Args:
            query: Search term or phrase
            output_path: Optional path to save RDF file
            concept_types: Filter by specific concept types
            sources: Specific sources to query
            max_results: Maximum total results to return
            rdf_format: RDF serialization format ('turtle', 'xml', 'json-ld', 'nt')
            adapter_hints: Optional adapter-specific RDF conversion hints

        Returns:
            RDF Graph containing the search results
        """
        if not HAS_RDFLIB:
            raise ImportError("RDF conversion requires rdflib. Install with: pip install rdflib")

        # Import here to avoid circular imports
        from .rdf_converter import UnifiedRDFConverter

        # Perform the search
        result = await self.search_concepts(
            query=query, concept_types=concept_types, sources=sources, max_results=max_results
        )

        if not result.concepts:
            logger.warning(f"No concepts found for query: {query}")
            # Return empty graph
            from rdflib import Graph

            return Graph()

        # Convert to RDF
        converter = UnifiedRDFConverter(adapter_hints)
        rdf_graph = converter.convert_concepts_to_graph(result.concepts)

        # Save if output path provided
        if output_path:
            converter.save_graph(rdf_graph, output_path, rdf_format)
            logger.info(f"RDF results saved to: {output_path}")

        logger.info(
            f"Converted {len(result.concepts)} concepts to RDF graph with {len(rdf_graph)} triples"
        )
        return rdf_graph

    async def close(self):
        """Close all adapters and cleanup resources."""
        for adapter in self.adapters.values():
            try:
                await adapter.close()
            except Exception as e:
                logger.error(f"Error closing adapter: {e}")

        self.executor.shutdown(wait=True)
        logger.info("Central knowledge lookup system closed")
