"""
UMLS Authentication Module

This module handles authentication and low-level API communication for the UMLS API.
"""

import logging
import time

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def umls_retry(max_retries: int = 3):
    """Decorator to apply retry logic for UMLS API requests."""
    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, RuntimeError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


class UMLSAuthenticator:
    """Handles UMLS authentication with TGT caching."""

    def __init__(
        self,
        api_key: str,
        auth_url: str = "https://utslogin.nlm.nih.gov",
        timeout: float = 30.0,
        cache_duration: int = 3600,
    ):
        self.api_key = api_key
        self.auth_url = auth_url
        self.timeout = timeout
        self.cache_duration = cache_duration

        # Token caching
        self.tgt: str | None = None
        self.tgt_expires: float | None = None

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0

    def ensure_tgt(self):
        """Ensure we have a valid TGT, refreshing if necessary."""
        current_time = time.time()

        if self.tgt is None or self.tgt_expires is None or current_time >= self.tgt_expires:

            self.tgt = self._get_tgt()
            self.tgt_expires = current_time + self.cache_duration
            self.cache_misses += 1
            logger.info("TGT refreshed")
        else:
            self.cache_hits += 1

    @umls_retry()
    def _get_tgt(self) -> str:
        """Obtain Ticket Granting Ticket (TGT) using API key."""
        url = f"{self.auth_url}/cas/v1/api-key"
        response = requests.post(url, data={"apikey": self.api_key}, timeout=self.timeout)

        if response.status_code != 201:
            raise RuntimeError(f"TGT fetch failed: {response.status_code} - {response.text}")

        return response.headers["location"]

    @umls_retry()
    def get_service_ticket(self) -> str:
        """Obtain a service ticket from the TGT."""
        self.ensure_tgt()

        if self.tgt is None:
            raise RuntimeError("TGT is None - authentication failed")

        response = requests.post(
            self.tgt,
            data={"service": "http://umlsks.nlm.nih.gov"},
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Service ticket fetch failed: {response.status_code} - {response.text}"
            )

        return response.text

    def clear_cache(self):
        """Clear authentication cache."""
        self.tgt = None
        self.tgt_expires = None
        logger.info("Authentication cache cleared")

    def get_statistics(self) -> dict[str, int]:
        """Get authentication statistics."""
        return {"cache_hits": self.cache_hits, "cache_misses": self.cache_misses}

    def reset_statistics(self):
        """Reset authentication statistics."""
        self.cache_hits = 0
        self.cache_misses = 0


class UMLSAPIClient:
    """Low-level UMLS API client for making authenticated requests."""

    def __init__(
        self,
        authenticator: UMLSAuthenticator,
        api_url: str = "https://uts-ws.nlm.nih.gov/rest",
        timeout: float = 30.0,
        rate_limit: float = 0.1,
    ):
        self.authenticator = authenticator
        self.api_url = api_url
        self.timeout = timeout
        self.rate_limit = rate_limit

        self.last_request_time = 0.0
        self.request_count = 0

    def _rate_limit_check(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    @umls_retry()
    def make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an authenticated request to the UMLS API."""
        self._rate_limit_check()

        params = params or {}
        params["ticket"] = self.authenticator.get_service_ticket()

        url = f"{self.api_url}{endpoint}"

        response = requests.get(url, params=params, timeout=self.timeout)

        if response.status_code != 200:
            raise RuntimeError(
                f"API request failed: {url} ({response.status_code}) - {response.text}"
            )

        self.request_count += 1

        try:
            result = response.json()

            # Handle case where the entire response is a string (error message)
            if isinstance(result, str):
                raise RuntimeError(f"UMLS API error: {result}")

            # Handle case where result is not a dictionary
            if not isinstance(result, dict):
                raise RuntimeError(f"UMLS API returned unexpected data type: {type(result)}")

            # Get the actual result content
            api_result = result.get("result", {})

            # Handle case where API returns error message as string in result field
            if isinstance(api_result, str):
                # If result is a string (error message), raise an exception
                raise RuntimeError(f"UMLS API error: {api_result}") from None

            return api_result if isinstance(api_result, dict) else {}
        except ValueError as e:
            raise RuntimeError(f"Invalid JSON returned from {url}: {response.text}") from e

    def get_statistics(self) -> dict[str, int]:
        """Get API client statistics."""
        return {"total_requests": self.request_count}
