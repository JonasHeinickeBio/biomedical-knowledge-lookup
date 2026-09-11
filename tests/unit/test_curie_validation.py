"""
Integration tests for CURIE utilities.
"""

import pytest
from knowledge_lookup.curie_utils import (
    create_local_converter,
    get_bioregistry_converter,
    get_prefix_mapping,
    get_source_prefix_mapping,
    normalize_curie,
    parse_curie_or_uri,
    validate_curie_pattern,
    validate_prefix,
)

pytest.importorskip("curies", reason="curie_utils requires the 'curie' extra")


class TestValidationIntegration:
    """Integration tests for validation utilities."""

    def test_get_bioregistry_converter(self) -> None:
        """The shared converter loads and exposes bioregistry's records."""
        converter = get_bioregistry_converter()
        assert converter is not None
        assert converter.has_prefix("doid")

    def test_get_prefix_mapping(self) -> None:
        """Prefix mapping covers every registered prefix, keyed to itself."""
        mapping = get_prefix_mapping()
        assert isinstance(mapping, dict)
        assert mapping.get("doid") == "doid"

    def test_validate_prefix_known(self) -> None:
        assert validate_prefix("doid") is True

    def test_validate_prefix_unknown(self) -> None:
        assert validate_prefix("not-a-real-prefix-xyz") is False

    def test_create_local_converter(self) -> None:
        """A local converter round-trips CURIE <-> URI for the given map."""
        prefix_map = {
            "doid": "http://purl.obolibrary.org/obo/DOID_",
            "mondo": "http://purl.obolibrary.org/obo/MONDO_",
        }
        converter = create_local_converter(prefix_map)
        assert converter.compress("http://purl.obolibrary.org/obo/DOID_9351") == "doid:9351"
        assert converter.expand("mondo:0005404") == "http://purl.obolibrary.org/obo/MONDO_0005404"

    def test_get_source_prefix_mapping(self) -> None:
        """Every KnowledgeSource gets a lowercase CURIE prefix."""
        mapping = get_source_prefix_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) > 0
        assert all(v == v.lower() for v in mapping.values())

    def test_validate_curie_pattern_valid(self) -> None:
        """A DOID identifier matching DOID's numeric pattern validates."""
        assert validate_curie_pattern("doid", "9351") is True

    def test_validate_curie_pattern_invalid(self) -> None:
        """A non-numeric identifier fails DOID's pattern."""
        assert validate_curie_pattern("doid", "not-a-number") is False


class TestNormalizationIntegration:
    """Integration tests for normalization utilities."""

    def test_normalize_curie_known(self) -> None:
        assert normalize_curie("DOID:9351") == "doid:9351"

    def test_parse_curie_or_uri_curie(self) -> None:
        result = parse_curie_or_uri("DOID:9351")
        assert result is not None
        prefix, identifier = result
        assert isinstance(prefix, str) and prefix
        assert identifier == "9351"

    def test_parse_curie_or_uri_uri(self) -> None:
        result = parse_curie_or_uri("http://purl.obolibrary.org/obo/DOID_9351")
        assert result is not None
        prefix, identifier = result
        assert isinstance(prefix, str) and prefix
        assert identifier == "9351"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
