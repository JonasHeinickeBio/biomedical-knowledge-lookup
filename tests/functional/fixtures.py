"""
Functional test fixtures for real-world API testing.
"""

import asyncio
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from knowledge_lookup.models import KnowledgeSource

# Base directory for fixture storage
FIXTURE_DIR = Path(__file__).parent / "api_fixtures"
FIXTURE_DIR.mkdir(exist_ok=True)


def get_source_fixture_path(source: KnowledgeSource) -> Path:
    """Get the fixture file path for a knowledge source."""
    return FIXTURE_DIR / f"{source.value}_responses.json"


def generate_response_hash(response: dict[str, Any]) -> str:
    """Generate a hash for an API response to detect changes."""
    # Sort keys for consistent hashing
    response_str = json.dumps(response, sort_keys=True, default=str)
    return hashlib.md5(response_str.encode()).hexdigest()


def load_fixture_responses(source: KnowledgeSource) -> dict[str, Any]:
    """Load previously recorded API responses for a source."""
    fixture_path = get_source_fixture_path(source)
    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return {}


def save_fixture_responses(source: KnowledgeSource, responses: dict[str, Any]):
    """Save API responses to fixture file."""
    fixture_path = get_source_fixture_path(source)
    with open(fixture_path, "w") as f:
        json.dump(responses, f, indent=2, default=str)


def load_env_api_key(source: KnowledgeSource) -> str | None:
    """Load API key from environment for a knowledge source."""
    key_mapping = {
        KnowledgeSource.BIOPORTAL: "BIOPORTAL_API_KEY",
        KnowledgeSource.UMLS: "UMLS_API_KEY",
        KnowledgeSource.DISGENET: "DISGENET_API_KEY",
        KnowledgeSource.DRUGBANK: "DRUGBANK_API_KEY",
    }
    env_key = key_mapping.get(source)
    if env_key:
        return os.environ.get(env_key)
    return None


def requires_api_key(source: KnowledgeSource):
    """Decorator to skip test if API key is not available."""
    api_key = load_env_api_key(source)
    has_key = api_key is not None and len(api_key) > 10

    return pytest.mark.skipif(
        not has_key,
        reason=f"API key for {source.value} not available (set {source.value}_API_KEY)"
    )


def requires_network(func: Callable) -> Callable:
    """Decorator to mark test as requiring network access."""
    return pytest.mark.network(func)


def requires_api(func: Callable) -> Callable:
    """Decorator to mark test as requiring API key AND network access."""
    return pytest.mark.network(pytest.mark.api(func))


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use asyncio event loop policy for async tests."""
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="module")
def api_responses_cache():
    """Shared cache for API responses within a test module."""
    return {}


@pytest.fixture
async def recorded_api_response(api_responses_cache):
    """
    Fixture that records and validates real API responses.

    Usage:
        result, response_data = await recorded_api_response(
            adapter.search_concepts,
            "query",
            cache_key="search_diabetes"
        )

        # Response data is cached for comparison across runs
        # Will warn if response structure changes
    """
    recorded_responses = {}

    async def record(
        api_call: Callable,
        *args,
        cache_key: str = None,
        source: KnowledgeSource = None,
        **kwargs
    ) -> tuple[Any, dict[str, Any]]:
        """
        Record or validate an API response.

        Args:
            api_call: Async function to call
            *args: Arguments to pass to api_call
            cache_key: Unique key for this API call
            source: KnowledgeSource for fixture storage
            **kwargs: Keyword arguments to pass to api_call

        Returns:
            Tuple of (api_result, response_data_dict)
        """
        if cache_key is None:
            cache_key = f"{api_call.__name__}_{args[0] if args else 'unknown'}"

        # Execute the API call
        result = await api_call(*args, **kwargs)

        # Convert result to serializable format if needed
        response_data = {}
        if hasattr(result, '__dict__'):
            response_data = result.__dict__
        elif isinstance(result, (list, dict)):
            response_data = result

        # Store in cache
        if source and cache_key:
            if source.value not in api_responses_cache:
                api_responses_cache[source.value] = {}
            api_responses_cache[source.value][cache_key] = response_data

        return result, response_data

    yield record

    # Cleanup: save cached responses to fixture files
    for source_name, responses in api_responses_cache.items():
        try:
            source_enum = KnowledgeSource(source_name)
            fixture_path = get_source_fixture_path(source_enum)

            # Load existing fixtures
            existing = {}
            if fixture_path.exists():
                with open(fixture_path) as f:
                    existing = json.load(f)

            # Update with new responses
            existing.update(responses)

            # Save back
            with open(fixture_path, "w") as f:
                json.dump(existing, f, indent=2, default=str)
        except (ValueError, TypeError):
            # Skip sources that aren't in enum
            pass


@pytest.fixture
async def adapter_factory(lookup_config):
    """
    Factory fixture for creating adapters with proper configuration.

    Usage:
        adapter = await adapter_factory(KnowledgeSource.UNIPROT)
        async with adapter:
            results = await adapter.search_concepts("test")
    """
    from knowledge_lookup.adapters import ADAPTER_CLASSES

    async def create(source: KnowledgeSource):
        adapter_class = ADAPTER_CLASSES.get(source)
        if adapter_class is None:
            raise ValueError(f"No adapter for source: {source}")

        adapter = adapter_class(lookup_config)
        return adapter

    yield create
