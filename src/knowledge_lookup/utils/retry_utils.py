"""
Retry utilities for knowledge source adapters.
Provides standardized retry decorators with sensible defaults for API calls.
"""

import logging
from collections.abc import Callable

import backoff


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

    Example:
        @create_api_retry_decorator()
        def api_call(self):
            # Your API call here
            pass
    """

    # Default error detection for common API errors
    def default_is_retryable_error(error_msg: str) -> bool:
        """Default logic to determine if an error is retryable."""
        error_str = str(error_msg).lower()

        # HTTP 5xx server errors
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True

        # Connection errors
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

        # HTML error pages (some APIs return HTML on server errors)
        if "error for url" in error_str and (
            "<!doctype html>" in error_str or "html lang=" in error_str
        ):
            return True

        return False

    # Use provided error checker or default
    error_checker = is_retryable_error or default_is_retryable_error

    # Default backoff callback
    def default_on_backoff(details):
        logger = logging.getLogger(logger_name)
        logger.warning(
            f"API retry attempt {details.get('tries', '?')}. "
            f"Waiting {details.get('wait', '?')} seconds..."
        )

    # Default giveup callback
    def default_on_giveup(details):
        logger = logging.getLogger(logger_name)
        logger.error(
            f"API call failed after {details.get('tries', '?')} attempts. "
            f"This may indicate a service outage."
        )

    # Use provided callbacks or defaults
    backoff_callback = on_backoff or default_on_backoff
    giveup_callback = on_giveup or default_on_giveup

    return backoff.on_exception(
        backoff_strategy,
        Exception,
        max_tries=max_tries,
        giveup=lambda e: not error_checker(str(e)),
        on_backoff=backoff_callback,
        on_giveup=giveup_callback,
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

    Args:
        max_tries: Maximum number of attempts (default: 4)
        backoff_strategy: Backoff strategy (default: exponential)
        on_backoff: Custom backoff callback
        on_giveup: Custom giveup callback
        logger_name: Logger name for callbacks

    Returns:
        Decorator for HTTP request methods
    """

    def is_http_retryable_error(error_msg: str) -> bool:
        """Check if HTTP-related error is retryable."""
        error_str = str(error_msg).lower()

        # HTTP 5xx server errors
        if any(f" {code} " in f" {error_str} " for code in [500, 502, 503, 504]):
            return True

        # Connection and network errors
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

        # DNS and resolution errors
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
    Includes ChEMBL-specific error detection for HTML error pages and server errors.

    Args:
        max_tries: Maximum number of attempts (default: 4)
        backoff_strategy: Backoff strategy (default: exponential)
        on_backoff: Custom backoff callback
        on_giveup: Custom giveup callback
        logger_name: Logger name for callbacks

    Returns:
        Decorator for ChEMBL API methods
    """

    def is_chembl_retryable_error(error_msg: str) -> bool:
        """Check if ChEMBL-specific error is retryable."""
        error_str = str(error_msg).lower()

        # HTTP 5xx server errors
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True

        # Connection errors
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

        # HTML error pages (ChEMBL returns HTML on server errors)
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
