"""
Base classes for knowledge source adapters.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

import aiohttp

from .models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from .utils.retry_utils import (
    CircuitBreaker,
    CircuitBreakerOpen,
    ErrorCategory,
    classify_error,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default per-category retry strategies shared by all adapter HTTP calls
DEFAULT_RETRY_STRATEGIES: dict[ErrorCategory, tuple[int, float, float]] = {
    ErrorCategory.NETWORK_ERROR: (3, 0.0, 0.0),  # 2 immediate retries
    ErrorCategory.RATE_LIMITED: (4, 2.0, 60.0),  # exponential backoff, up to 60s
    ErrorCategory.SERVER_ERROR: (4, 1.5, 30.0),
    ErrorCategory.TRANSIENT: (2, 0.0, 0.0),  # 1 immediate retry
    ErrorCategory.CLIENT_ERROR: (1, 0.0, 0.0),  # never retry
    ErrorCategory.UNKNOWN: (2, 1.0, 5.0),
}


class KnowledgeSourceAdapter(ABC):
    """
    Abstract base class for knowledge source adapters.
    Each adapter implements the interface to a specific knowledge source.
    """

    def __init__(self, config: LookupConfig):
        self.config = config
        self.source = self.get_source()
        self.session: aiohttp.ClientSession | None = None
        self._circuit_breaker: CircuitBreaker | None = None

    def set_circuit_breaker(self, cb: CircuitBreaker) -> None:
        """Attach a circuit breaker (injected by the orchestrator)."""
        self._circuit_breaker = cb

    # ------------------------------------------------------------------
    # Smart retry primitive — available to ALL adapters
    # ------------------------------------------------------------------

    async def _call_with_retry(
        self,
        operation_name: str,
        operation: Callable[[], Any],
        strategies: dict[ErrorCategory, tuple[int, float, float]] | None = None,
    ) -> Any:
        """Execute *operation* with smart retry and circuit-breaker protection.

        Parameters
        ----------
        operation_name :
            Human-readable label for logging (e.g. ``"search_concepts"``).
        operation :
            Async callable that performs the actual work.
        strategies :
            Optional per-category retry overrides.  Falls back to
            :data:`DEFAULT_RETRY_STRATEGIES`.

        Raises
        ------
        CircuitBreakerOpen
            When the circuit breaker is open and the call is short-circuited.
        """
        strat = strategies or DEFAULT_RETRY_STRATEGIES
        last_exc: Exception | None = None

        for attempt in range(1, 100):  # upper bound — strategies cap actual tries
            # --- circuit-breaker gate (check before every attempt) ---
            if self._circuit_breaker is not None and not self._circuit_breaker.allow_request():
                raise CircuitBreakerOpen(
                    f"Circuit breaker is {self._circuit_breaker.state.value} "
                    f"({self._circuit_breaker.failure_count} consecutive failures) "
                    f"for {self.source.value} ({operation_name})"
                )

            try:
                result = await operation()

                # Success — update circuit breaker
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_success()
                return result

            except CircuitBreakerOpen:
                raise  # don't retry these — pass through immediately

            except Exception as exc:
                last_exc = exc
                category = classify_error(exc)
                max_tries, factor, max_delay = strat.get(category, strat[ErrorCategory.UNKNOWN])

                if attempt >= max_tries:
                    if self._circuit_breaker is not None:
                        self._circuit_breaker.record_failure()
                    raise

                # Compute delay for this attempt
                delay = 0.0
                if factor > 0:
                    delay = factor * (2 ** (attempt - 1))
                    if max_delay > 0:
                        delay = min(delay, max_delay)
                if delay > 0:
                    await asyncio.sleep(delay)

        # Should never reach here (strategies bound attempts)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(
            f"_call_with_retry({operation_name}): unexpected exit from retry loop"
        )  # pragma: no cover

    # ------------------------------------------------------------------
    # Circuit-breaker notification for adapters that handle errors
    # internally but still want to report failures
    # ------------------------------------------------------------------

    def _notify_circuit_breaker(self, error: Exception | None = None) -> None:
        """Explicitly record a failure in the circuit breaker.

        Call this from adapter code that catches its own errors and returns
        ``[]`` / ``None`` so the circuit breaker still sees the failure.
        """
        if self._circuit_breaker is not None:
            if error is not None:
                self._circuit_breaker.record_failure()
            else:
                self._circuit_breaker.record_success()

    # ------------------------------------------------------------------
    # Standard interface
    # ------------------------------------------------------------------

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @abstractmethod
    def get_source(self) -> KnowledgeSource:
        """Return the knowledge source this adapter handles."""
        pass

    @abstractmethod
    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search for concepts matching the query.

        Args:
            query: Search term
            limit: Maximum number of results

        Returns:
            List of unified concepts
        """
        pass

    @abstractmethod
    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get detailed information about a specific concept.

        Args:
            concept_id: Identifier of the concept

        Returns:
            Unified concept with details or None if not found
        """
        pass

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """
        Get mappings/cross-references for a concept.
        Default implementation returns empty list.

        Args:
            concept_id: Identifier of the concept

        Returns:
            List of mapping dictionaries
        """
        return []

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """
        Get relationships for a concept.
        Default implementation returns empty list.

        Args:
            concept_id: Identifier of the concept

        Returns:
            List of relationship dictionaries
        """
        return []

    def is_available(self) -> bool:
        """
        Check if this knowledge source is available.
        Default implementation returns True.
        """
        return True

    def get_rate_limit(self) -> float:
        """Get rate limit for this source (requests per second)."""
        return self.config.rate_limits.get(self.source, 1.0)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_per_source)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_request(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request with smart retry and error handling."""
        request_headers = headers or {}
        if "User-Agent" not in request_headers:
            request_headers["User-Agent"] = "AID-PAIS-Knowledge-Lookup/1.0"

        async def _do() -> dict[str, Any]:
            session = await self._get_session()
            if json_data:
                async with session.post(
                    url, params=params, headers=request_headers, json=json_data
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                async with session.get(url, params=params, headers=request_headers) as response:
                    response.raise_for_status()
                    return await response.json()

        return await self._call_with_retry("_make_request", _do)

    async def _make_request_text(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> str:
        """Make HTTP request with smart retry and return text response."""

        async def _do() -> str:
            session = await self._get_session()
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                return await response.text()

        return await self._call_with_retry("_make_request_text", _do)

    async def close(self):
        """Close the adapter and cleanup resources."""
        if self.session and not self.session.closed:
            await self.session.close()

    def _create_concept(
        self, concept_id: str, label: str, concept_type: ConceptType = ConceptType.UNKNOWN
    ) -> UnifiedConcept:
        """Create a unified concept with this source as primary."""
        concept = UnifiedConcept(
            primary_id=concept_id, primary_label=label, concept_type=concept_type
        )
        concept.add_identifier(self.source, concept_id, label)
        return concept

    def _determine_concept_type(
        self, semantic_types: list[str], categories: list[str] | None = None
    ) -> ConceptType:
        """
        Determine concept type from semantic types and categories.
        Override in subclasses for source-specific logic.
        """
        semantic_types = [st.lower() for st in semantic_types]
        categories = [cat.lower() for cat in (categories or [])]

        # Disease detection
        if any(
            term in semantic_types for term in ["disease", "disorder", "syndrome", "condition"]
        ):
            return ConceptType.DISEASE

        # Symptom detection
        if any(term in semantic_types for term in ["symptom", "sign", "finding"]):
            return ConceptType.SYMPTOM

        # Drug detection
        if any(
            term in semantic_types for term in ["drug", "medication", "pharmaceutical", "compound"]
        ):
            return ConceptType.DRUG

        # Gene detection
        if any(term in semantic_types for term in ["gene", "genetic"]):
            return ConceptType.GENE

        # Protein detection
        if any(term in semantic_types for term in ["protein", "enzyme"]):
            return ConceptType.PROTEIN

        # Anatomy detection
        if any(term in semantic_types for term in ["anatomy", "anatomical", "body part", "organ"]):
            return ConceptType.ANATOMY

        # Procedure detection
        if any(term in semantic_types for term in ["procedure", "therapy", "treatment"]):
            return ConceptType.PROCEDURE

        # Chemical detection
        if any(term in semantic_types for term in ["chemical", "substance", "compound"]):
            return ConceptType.CHEMICAL

        # Organism detection
        if any(term in semantic_types for term in ["organism", "species", "bacteria", "virus"]):
            return ConceptType.ORGANISM

        return ConceptType.UNKNOWN
