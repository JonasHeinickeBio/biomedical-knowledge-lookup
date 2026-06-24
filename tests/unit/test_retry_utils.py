"""
Unit tests for retry utilities.
"""

import pytest

pytestmark = pytest.mark.unit
from unittest.mock import MagicMock

from src.knowledge_lookup.utils.retry_utils import (
    create_api_retry_decorator,
    create_chembl_retry_decorator,
    create_http_retry_decorator,
)


class TestRetryUtils:
    """Test suite for retry utilities."""

    def test_create_api_retry_decorator_default_success(self):
        """Test default API retry decorator on success."""
        mock_func = MagicMock(return_value="success")
        mock_func.__name__ = "mock_func"
        decorator = create_api_retry_decorator(max_tries=2)
        decorated_func = decorator(mock_func)

        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_create_api_retry_decorator_retry_on_failure(self):
        """Test API retry decorator retries on failure."""
        mock_func = MagicMock(side_effect=[Exception("500 Internal Server Error"), "success"])
        mock_func.__name__ = "mock_func"
        decorator = create_api_retry_decorator(max_tries=3)
        decorated_func = decorator(mock_func)

        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_create_api_retry_decorator_giveup_on_not_retryable(self):
        """Test API retry decorator gives up on non-retryable error."""
        mock_func = MagicMock(side_effect=Exception("404 Not Found"))
        mock_func.__name__ = "mock_func"
        decorator = create_api_retry_decorator(max_tries=3)
        decorated_func = decorator(mock_func)

        with pytest.raises(Exception) as excinfo:
            decorated_func()

        assert "404 Not Found" in str(excinfo.value)
        assert mock_func.call_count == 1

    def test_create_http_retry_decorator(self):
        """Test HTTP-specific retry decorator."""
        mock_func = MagicMock(side_effect=[Exception("Connection timeout"), "success"])
        mock_func.__name__ = "mock_func"
        decorator = create_http_retry_decorator(max_tries=3)
        decorated_func = decorator(mock_func)

        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_create_chembl_retry_decorator(self):
        """Test ChEMBL-specific retry decorator."""
        mock_func = MagicMock(side_effect=[Exception("error for url <!doctype html> error"), "success"])
        mock_func.__name__ = "mock_func"
        decorator = create_chembl_retry_decorator(max_tries=3)
        decorated_func = decorator(mock_func)

        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry(self):
        """Test retry decorator with async function."""
        async_mock = MagicMock(side_effect=[Exception("503 Service Unavailable"), "async success"])

        # We need a real async function for backoff to work correctly with async
        async def async_func():
            return async_mock()

        decorator = create_api_retry_decorator(max_tries=3)
        decorated_func = decorator(async_func)

        result = await decorated_func()

        assert result == "async success"
        assert async_mock.call_count == 2
