"""
Unit tests for factory functions.
"""

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.core.factory import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestFactory:
    """Tests for factory functions."""

    def test_create_knowledge_lookup_default(self):
        """Test create_knowledge_lookup with default parameters."""
        lookup = create_knowledge_lookup()

        assert isinstance(lookup.config, LookupConfig)
        assert lookup.config.enabled_sources == list(KnowledgeSource)
        assert lookup.config.api_keys == {}

    def test_create_knowledge_lookup_with_api_keys(self):
        """Test create_knowledge_lookup with API keys."""
        api_keys = {"bioportal": "test_key"}
        lookup = create_knowledge_lookup(api_keys=api_keys)

        assert lookup.config.api_keys == api_keys

    def test_create_knowledge_lookup_with_sources(self):
        """Test create_knowledge_lookup with specific sources."""
        sources = [KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS]
        lookup = create_knowledge_lookup(enabled_sources=sources)

        assert lookup.config.enabled_sources == sources

    def test_create_knowledge_lookup_with_kwargs(self):
        """Test create_knowledge_lookup with additional kwargs."""
        lookup = create_knowledge_lookup(max_results_per_source=5, timeout_per_source=10.0)

        assert lookup.config.max_results_per_source == 5
        assert lookup.config.timeout_per_source == 10.0

    def test_create_knowledge_lookup_combined_config(self):
        """Test create_knowledge_lookup with combined configuration."""
        api_keys = {"bioportal": "test_key"}
        sources = [KnowledgeSource.BIOPORTAL]

        lookup = create_knowledge_lookup(
            api_keys=api_keys, enabled_sources=sources, fast_mode=True, max_results_per_source=20
        )

        assert lookup.config.api_keys == api_keys
        assert lookup.config.enabled_sources == sources
        assert lookup.config.max_results_per_source == 20
