"""
Enhanced retry utilities for knowledge source adapters.

Provides:
- ``ErrorCategory`` — classify errors by type for different retry strategies
- ``CircuitBreaker`` — tracks consecutive failures, stops retrying after
  threshold, auto-recovers after cooldown
- ``CircuitBreakerOpen`` — exception raised when a circuit breaker is open
- ``classify_error`` — classify an exception into an ``ErrorCategory``
- ``smart_retry`` — decorator that applies per-category backoff with optional
  circuit-breaker awareness (internal use; prefer the base class methods)
- Legacy backward-compatible helpers:
  ``create_api_retry_decorator``, ``create_http_retry_decorator``,
  ``create_chembl_retry_decorator``
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

import aiohttp
import backoff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit-breaker exception
# ---------------------------------------------------------------------------


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is open and rejects a request."""


# ---------------------------------------------------------------------------
# Error categorisation
# ---------------------------------------------------------------------------


class ErrorCategory(str, Enum):
    """Category of an error — determines which retry strategy to use."""

    NETWORK_ERROR = "network"
    """Connection / DNS / timeout / SSL errors — transient, retry fast."""

    RATE_LIMITED = "rate_limited"
    """HTTP 429 / 403 quota — retry with exponential backoff."""

    SERVER_ERROR = "server"
    """HTTP 5xx — server-side, retry with moderate backoff."""

    TRANSIENT = "transient"
    """Other temporary errors that might resolve on retry."""

    CLIENT_ERROR = "client"
    """HTTP 4xx (except 429) — not retryable (bad request, not found, etc.)."""

    UNKNOWN = "unknown"
    """Unclassified — cautious single retry then give up."""


def classify_error(exc: Exception) -> ErrorCategory:
    """Classify *exc* into an :class:`ErrorCategory`.

    Checks the exception type, string representation, and (where available)
    HTTP status codes for common error patterns.
    """
    msg = str(exc).lower()
    type_name = type(exc).__name__.lower()

    # --- Rate limiting ---
    if any(
        marker in msg
        for marker in [
            "429",
            "rate limit",
            "rate_limit",
            "too many requests",
            "quota exceeded",
        ]
    ):
        return ErrorCategory.RATE_LIMITED

    # --- Server errors (HTTP 5xx) ---
    if any(
        marker in msg for marker in ["500", "502", "503", "504", "internal server"]
    ):
        return ErrorCategory.SERVER_ERROR
    if isinstance(exc, aiohttp.ClientResponseError) and 500 <= exc.status <= 599:
        return ErrorCategory.SERVER_ERROR

    # --- Client errors (HTTP 4xx, excluding 429 which is caught above) ---
    if isinstance(exc, aiohttp.ClientResponseError) and 400 <= exc.status <= 499:
        return ErrorCategory.CLIENT_ERROR
    if any(marker in msg for marker in ["400", "401", "403", "404", "405", "422"]):
        return ErrorCategory.CLIENT_ERROR

    # --- Network / connection errors ---
    if isinstance(
        exc,
        (
            aiohttp.ClientConnectorError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientTimeout,
            asyncio.TimeoutError,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return ErrorCategory.NETWORK_ERROR

    if any(
        marker in msg
        for marker in [
            "connection",
            "timeout",
            "dns",
            "network",
            "name resolution",
            "connection refused",
            "connection reset",
            "ssl",
            "unreachable",
            "broken",
        ]
    ):
        return ErrorCategory.NETWORK_ERROR

    return ErrorCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Default retry strategies (per-category)
# ---------------------------------------------------------------------------
# Each entry is (max_tries, factor_seconds, max_delay_seconds).
# max_tries includes the original attempt.
# factor=0 with max_delay=0 means immediate retry (no backoff).

DEFAULT_RETRY_STRATEGIES: dict[ErrorCategory, tuple[int, float, float]] = {
    ErrorCategory.NETWORK_ERROR: (3, 0.0, 0.0),  # 2 immediate retries
    ErrorCategory.RATE_LIMITED: (4, 2.0, 60.0),  # exp backoff up to 60s
    ErrorCategory.SERVER_ERROR: (4, 1.5, 30.0),
    ErrorCategory.TRANSIENT: (2, 0.0, 0.0),  # 1 immediate retry
    ErrorCategory.CLIENT_ERROR: (1, 0.0, 0.0),  # never retry
    ErrorCategory.UNKNOWN: (2, 1.0, 5.0),
}


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    """State of a circuit breaker."""

    CLOSED = "closed"  # Normal operation — requests pass through
    OPEN = "open"  # Failing — requests are short-circuited
    HALF_OPEN = "half_open"  # Probing — single test request allowed


class CircuitBreaker:
    """Per-source circuit breaker.

    After *threshold* consecutive failures the breaker **opens** and all
    subsequent calls are skipped (short-circuited).  After *cooldown*
    seconds it transitions to **half-open** where one probe call is
    allowed — if it succeeds the breaker resets to **closed**, otherwise
    it re-opens.
    """

    def __init__(self, threshold: int = 5, cooldown: float = 30.0) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.total_calls: int = 0
        self.total_failures: int = 0
        self.total_successes: int = 0

    @staticmethod
    def _now() -> float:
        """Current time from the running event loop, falling back to ``time.monotonic``."""
        try:
            return asyncio.get_running_loop().time()
        except RuntimeError:
            return time.monotonic()

    def record_success(self) -> None:
        """Record a successful call — resets the breaker to closed."""
        self.total_calls += 1
        self.total_successes += 1
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — may open / re-open the breaker."""
        self.total_calls += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = self._now()

        if self.failure_count >= self.threshold:
            self.state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check whether a request should be allowed.

        If the breaker is **open** but the cooldown has elapsed it
        transitions to **half-open** and permits a single probe.
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = self._now() - self.last_failure_time
            if elapsed >= self.cooldown:
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # Half-open — allow the probe
        return True

    @property
    def health(self) -> float:
        """Health score 0..1 based on recent failure ratio."""
        if self.total_calls == 0:
            return 1.0
        return 1.0 - (self.total_failures / self.total_calls)

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of breaker state for diagnostics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "threshold": self.threshold,
            "cooldown": self.cooldown,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "health": self.health,
        }


# ---------------------------------------------------------------------------
# Backward-compatible decorators (unchanged from original)
# ---------------------------------------------------------------------------


def create_api_retry_decorator(
    max_tries: int = 4,
    backoff_strategy: Callable = backoff.expo,
    is_retryable_error: Callable[[str], bool] | None = None,
    on_backoff: Callable | None = None,
    on_giveup: Callable | None = None,
    logger_name: str = __name__,
) -> Callable:
    """
    Create a standardized retry decorator for API calls with sensible defaults.

    Args:
        max_tries: Maximum number of attempts (including initial try)
        backoff_strategy: Backoff strategy function (default: exponential)
        is_retryable_error: Function to determine if error is retryable.
                           If None, uses default HTTP error detection.
        on_backoff: Callback function called on retry attempts
        on_giveup: Callback function called when giving up
        logger_name: Name for the logger to use in callbacks

    Returns:
        Decorator function that can be applied to methods
    """

    def default_is_retryable_error(error_msg: str) -> bool:
        error_str = str(error_msg).lower()
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True
        if any(
            term in error_str
            for term in [
                "connection",
                "timeout",
                "network",
                "unreachable",
                "connection reset",
                "connection refused",
            ]
        ):
            return True
        if "error for url" in error_str and (
            "<!doctype html>" in error_str or "html lang=" in error_str
        ):
            return True
        return False

    error_checker = is_retryable_error or default_is_retryable_error

    def default_on_backoff(details):
        log = logging.getLogger(logger_name)
        log.warning(
            f"API retry attempt {details.get('tries', '?')}. "
            f"Waiting {details.get('wait', '?')} seconds..."
        )

    def default_on_giveup(details):
        log = logging.getLogger(logger_name)
        log.error(
            f"API call failed after {details.get('tries', '?')} attempts. "
            f"This may indicate a service outage."
        )

    return backoff.on_exception(
        backoff_strategy,
        Exception,
        max_tries=max_tries,
        giveup=lambda e: not error_checker(str(e)),
        on_backoff=on_backoff or default_on_backoff,
        on_giveup=on_giveup or default_on_giveup,
    )


def create_http_retry_decorator(
    max_tries: int = 4,
    backoff_strategy: Callable = backoff.expo,
    on_backoff: Callable | None = None,
    on_giveup: Callable | None = None,
    logger_name: str = __name__,
) -> Callable:
    """
    Create a retry decorator specifically for HTTP requests.
    Optimized defaults for HTTP-based API calls.
    """

    def is_http_retryable_error(error_msg: str) -> bool:
        error_str = str(error_msg).lower()
        if any(f" {code} " in f" {error_str} " for code in [500, 502, 503, 504]):
            return True
        if any(
            term in error_str
            for term in [
                "connection failed",
                "connection timeout",
                "read timeout",
                "network unreachable",
                "connection reset",
                "connection refused",
                "ssl error",
                "certificate verify failed",
            ]
        ):
            return True
        if any(
            term in error_str
            for term in [
                "name resolution",
                "dns",
                "nodename nor servname",
                "temporary failure in name resolution",
            ]
        ):
            return True
        return False

    return create_api_retry_decorator(
        max_tries=max_tries,
        backoff_strategy=backoff_strategy,
        is_retryable_error=is_http_retryable_error,
        on_backoff=on_backoff,
        on_giveup=on_giveup,
        logger_name=logger_name,
    )


def create_chembl_retry_decorator(
    max_tries: int = 4,
    backoff_strategy: Callable = backoff.expo,
    on_backoff: Callable | None = None,
    on_giveup: Callable | None = None,
    logger_name: str = __name__,
) -> Callable:
    """
    Create a retry decorator specifically optimized for ChEMBL API calls.
    Includes ChEMBL-specific error detection for HTML error pages.
    """

    def is_chembl_retryable_error(error_msg: str) -> bool:
        error_str = str(error_msg).lower()
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True
        if any(
            term in error_str
            for term in [
                "connection",
                "timeout",
                "network",
                "unreachable",
                "connection reset",
                "connection refused",
            ]
        ):
            return True
        if "error for url" in error_str and (
            "<!doctype html>" in error_str or "html lang=" in error_str
        ):
            return True
        return False

    return create_api_retry_decorator(
        max_tries=max_tries,
        backoff_strategy=backoff_strategy,
        is_retryable_error=is_chembl_retryable_error,
        on_backoff=on_backoff,
        on_giveup=on_giveup,
        logger_name=logger_name,
    )
