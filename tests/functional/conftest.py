"""
Functional test fixtures for adapters.

Provides utilities for testing with real API responses.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from knowledge_lookup.models import KnowledgeSource

FIXTURE_DIR = Path(__file__).parent / "api_fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def generate_response_hash(response: dict[str, Any]) -> str:
    """Generate a hash for an API response to detect changes."""
    response_str = json.dumps(response, sort_keys=True, default=str)
    return hashlib.md5(response_str.encode()).hexdigest()


def get_fixture_path(source: KnowledgeSource) -> Path:
    """Get the fixture file path for a knowledge source."""
    return FIXTURE_DIR / f"{source.value}_responses.json"


def load_fixture_responses(source: KnowledgeSource) -> dict[str, Any]:
    """Load previously recorded API responses for a source."""
    fixture_path = get_fixture_path(source)
    if fixture_path.exists():
        try:
            with open(fixture_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_fixture_responses(source: KnowledgeSource, responses: dict[str, Any]):
    """Save API responses to fixture file."""
    fixture_path = get_fixture_path(source)
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


def requires_network(func):
    """Decorator to mark test as requiring network access."""
    return pytest.mark.network(func)


def requires_api(func):
    """Decorator to mark test as requiring API key AND network access."""
    return pytest.mark.network(pytest.mark.api(func))


@pytest.fixture(scope="module")
def api_responses_cache():
    """Shared cache for API responses within a test module."""
    return {}


@pytest.fixture
def adapter_factory(lookup_config):
    """
    Factory fixture for creating adapters with proper configuration.

    Usage:
        adapter = adapter_factory(KnowledgeSource.UNIPROT)
        async with adapter:
            results = await adapter.search_concepts("test")
    """
    from knowledge_lookup.adapters import ADAPTER_CLASSES

    def create(source: KnowledgeSource):
        adapter_class = ADAPTER_CLASSES.get(source)
        if adapter_class is None:
            raise ValueError(f"No adapter for source: {source}")

        adapter = adapter_class(lookup_config)
        return adapter

    return create


@pytest.fixture
def response_validator():
    """
    Factory fixture for creating response validators.

    Usage:
        validator = response_validator(KnowledgeSource.UNIPROT)
        changes = validator.validate("cache_key", response_data)
    """
    from .validator import APIResponseValidator

    def create(source: KnowledgeSource):
        return APIResponseValidator(source.value)

    return create


@pytest.fixture
def warning_manager():
    """
    Fixture for managing API response change warnings.

    Usage:
        warning_manager.add_warning(KnowledgeSource.UNIPROT, "cache_key", warning)
        warning_manager.print_warnings()
    """
    from .utils import APIWarningManager
    return APIWarningManager()


@pytest.fixture
def adapter(lookup_config):
    """
    Create a default adapter for testing.

    This fixture provides a pre-configured adapter instance.
    The tests use adapter.config to re-create adapters if needed.
    """
    from knowledge_lookup.adapters.uniprot_adapter import UniProtAdapter
    # Return a default adapter instance (UniProt as example)
    return UniProtAdapter(lookup_config)
