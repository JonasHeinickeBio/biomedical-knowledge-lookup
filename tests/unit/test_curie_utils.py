"""
Unit tests for curie_utils module.
"""

import pytest
from knowledge_lookup.curie_utils import (
    concept_identifier_to_reference,
    normalize_curie,
    normalize_identifier,
    parse_curie_or_uri,
    reference_to_concept_identifier,
    validate_prefix,
)

pytest.importorskip("curies", reason="curie_utils requires the 'curie' extra")


class TestReferenceConversion:
    """Tests for curies Reference conversion utilities."""

    def test_reference_to_concept_identifier(self) -> None:
        """Test converting curies Reference to concept identifier dict."""
        from curies import Reference

        ref = Reference(prefix="doid", identifier="9351")
        result = reference_to_concept_identifier(ref)
        assert result["source"] == "DOID"
        assert result["identifier"] == "9351"
        assert result["url"] is None  # bare Reference has no resolvable URI

    def test_concept_identifier_to_reference(self) -> None:
        """Test converting concept identifier dict to curies Reference."""
        concept_id = {"source": "DOID", "identifier": "9351"}
        result = concept_identifier_to_reference(concept_id)
        assert result is not None
        assert result.prefix == "doid"
        assert result.identifier == "9351"

    def test_concept_identifier_to_reference_invalid(self) -> None:
        """Test conversion with invalid input returns None."""
        assert concept_identifier_to_reference({"source": "", "identifier": ""}) is None
        assert concept_identifier_to_reference({}) is None


class TestNormalization:
    """Tests for identifier normalization utilities."""

    def test_normalize_identifier_basic(self) -> None:
        """Identifier normalization keeps the local part unchanged for DOID."""
        pytest.importorskip("pyobo", reason="normalize_identifier requires pyobo")
        assert normalize_identifier("doid", "9351") == "9351"

    def test_normalize_identifier_unknown_prefix(self) -> None:
        """standardize_identifier only touches the identifier, not the prefix,
        so an unregistered prefix still returns the (unchanged) identifier."""
        assert normalize_identifier("not-a-real-prefix-xyz", "1") == "1"

    def test_normalize_curie_basic(self) -> None:
        """A registered CURIE normalizes to its lowercase canonical prefix."""
        assert normalize_curie("DOID:9351") == "doid:9351"

    def test_normalize_curie_unknown_prefix(self) -> None:
        """An unregistered prefix can't be standardized, so the original
        CURIE is returned unchanged rather than raising or losing data."""
        assert normalize_curie("NOT-A-REAL-PREFIX-XYZ:1") == "NOT-A-REAL-PREFIX-XYZ:1"

    def test_parse_curie_or_uri_curie(self) -> None:
        """A CURIE string parses to (prefix, identifier)."""
        result = parse_curie_or_uri("DOID:9351")
        assert result is not None
        prefix, identifier = result
        assert prefix.lower() in ("doid", "mondo")  # bioregistry may map to a preferred prefix
        assert identifier == "9351"

    def test_parse_curie_or_uri_uri(self) -> None:
        """A resolvable OBO PURL parses to (prefix, identifier)."""
        result = parse_curie_or_uri("http://purl.obolibrary.org/obo/DOID_9351")
        assert result is not None
        prefix, identifier = result
        assert isinstance(prefix, str) and prefix
        assert identifier == "9351"

    def test_parse_curie_or_uri_invalid(self) -> None:
        """An unparsable string returns None rather than raising."""
        assert parse_curie_or_uri("not-a-valid-curi") is None


class TestValidation:
    """Tests for prefix validation utilities."""

    def test_validate_prefix_valid(self) -> None:
        """A registered prefix (any casing) validates as True."""
        assert validate_prefix("doid") is True
        assert validate_prefix("DOID") is True

    def test_validate_prefix_invalid(self) -> None:
        """An unregistered prefix validates as False."""
        assert validate_prefix("not-a-real-prefix") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
