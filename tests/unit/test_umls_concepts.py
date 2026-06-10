"""
Unit tests for umls/concepts module.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.umls.concepts import UMLSConceptService
from knowledge_lookup.umls.models import UMLSConcept


class MockAPIClient:
    """Mock API client for testing."""

    def __init__(self, response_data=None):
        self.response_data = response_data or {}

    def make_request(self, endpoint, params=None):
        return self.response_data.get(endpoint, {})


class TestUMLSConceptService:
    """Tests for UMLSConceptService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock API client."""
        return MockAPIClient()

    @pytest.fixture
    def service(self, mock_client):
        """Create a UMLSConceptService instance."""
        return UMLSConceptService(mock_client)

    @pytest.fixture
    def service_with_version(self, mock_client):
        """Create a UMLSConceptService with custom version."""
        return UMLSConceptService(mock_client, version="2024AA")

    def test_service_initialization(self, mock_client):
        """Test service initialization."""
        service = UMLSConceptService(mock_client)
        assert service.api_client == mock_client
        assert service.version == "current"

    def test_service_initialization_custom_version(self, mock_client):
        """Test service initialization with custom version."""
        service = UMLSConceptService(mock_client, version="2024AA")
        assert service.version == "2024AA"

    def test_get_concept_details_success(self, service):
        """Test get_concept_details with successful response."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Diabetes mellitus",
                "semanticTypes": [{"name": "Disease or Syndrome"}],
                "definitions": [{"value": "A metabolic disease"}],
            },
            "/content/current/CUI/C0012345/atoms": {
                "results": [
                    {"name": "diabetes mellitus", "rootSource": "MMSL"},
                    {"name": "DM", "rootSource": "MMSL"},
                ]
            },
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None
        assert concept.name == "Diabetes mellitus"
        assert "Disease or Syndrome" in concept.semantic_types

    def test_get_concept_details_not_found(self, service):
        """Test get_concept_details with empty response."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": None,
        }

        concept = service.get_concept_details("C0012345")
        assert concept is None

    def test_get_concept_details_string_response(self, service):
        """Test get_concept_details with string response (error)."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": "Error: Invalid CUI",
        }

        concept = service.get_concept_details("C0012345")
        assert concept is None

    def test_get_concept_details_missing_fields(self, service):
        """Test get_concept_details with minimal response."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {"name": "Test Concept"},
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None
        assert concept.name == "Test Concept"

    def test_get_concept_details_error_handling(self, service):
        """Test get_concept_details handles API errors gracefully."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {"name": "Test Concept"},
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_atoms(self, service):
        """Test get_concept_atoms."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/atoms": {
                "results": [
                    {"name": "diabetes mellitus", "rootSource": "MMSL"},
                    {"name": "DM", "rootSource": "MMSL"},
                ]
            }
        }

        atoms = service.get_concept_atoms("C0012345")
        assert len(atoms) == 2

    def test_get_concept_atoms_with_source_filter(self, service):
        """Test get_concept_atoms with source filter."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/atoms": {"results": []}
        }

        atoms = service.get_concept_atoms("C0012345", source="SNOMEDCT_US")
        assert isinstance(atoms, list)

    def test_get_concept_atoms_error(self, service):
        """Test get_concept_atoms handles errors."""
        service.api_client.response_data = {}

        atoms = service.get_concept_atoms("C0012345")
        assert atoms == []

    def test_get_concept_relationships(self, service):
        """Test get_concept_relationships."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": {
                "results": [
                    {
                        "relatedId": "C0012346",
                        "relatedIdName": "Type 1 Diabetes",
                        "relationLabel": "isa",
                        "additionalRelationLabel": "CHD",
                    }
                ]
            }
        }

        relationships = service.get_concept_relationships("C0012345")
        assert len(relationships) == 1

    def test_get_concept_relationships_with_include_related(self, service):
        """Test get_concept_relationships with include_related."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": {"results": []}
        }

        relationships = service.get_concept_relationships("C0012345", include_related=True)
        assert isinstance(relationships, list)

    def test_get_concept_relationships_error(self, service):
        """Test get_concept_relationships handles errors."""
        service.api_client.response_data = {}

        relationships = service.get_concept_relationships("C0012345")
        assert relationships == []

    def test_get_concept_hierarchy(self, service):
        """Test get_concept_hierarchy."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": {
                "results": [
                    {
                        "relatedId": "C0012346",
                        "relatedIdName": "Parent concept",
                        "relationLabel": "isa",
                        "additionalRelationLabel": "PAR",
                    },
                    {
                        "relatedId": "C0012347",
                        "relatedIdName": "Child concept",
                        "relationLabel": "isa",
                        "additionalRelationLabel": "CHD",
                    },
                ]
            }
        }

        hierarchy = service.get_concept_hierarchy("C0012345")
        assert hierarchy["cui"] == "C0012345"
        assert len(hierarchy["parents"]) == 1
        assert len(hierarchy["children"]) == 1

    def test_get_concept_hierarchy_with_levels(self, service):
        """Test get_concept_hierarchy with levels parameter."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": {"results": []}
        }

        hierarchy = service.get_concept_hierarchy("C0012345", levels=2)
        assert "cui" in hierarchy

    def test_get_concept_hierarchy_error(self, service):
        """Test get_concept_hierarchy handles errors."""
        service.api_client.response_data = {}

        hierarchy = service.get_concept_hierarchy("C0012345")
        assert hierarchy["cui"] == "C0012345"
        assert hierarchy["parents"] == []
        assert hierarchy["children"] == []

    def test_get_cui_from_code(self, service):
        """Test get_cui_from_code."""
        service.api_client.response_data = {
            "/content/current/source/SNOMEDCT_US/123456": {
                "results": [{"concept": "/content/current/CUI/C0012345"}]
            }
        }

        cui = service.get_cui_from_code("123456", "SNOMEDCT_US")
        assert cui == "C0012345"

    def test_get_cui_from_code_not_found(self, service):
        """Test get_cui_from_code with no results."""
        service.api_client.response_data = {
            "/content/current/source/SNOMEDCT_US/999999": {"results": []}
        }

        cui = service.get_cui_from_code("999999", "SNOMEDCT_US")
        assert cui is None

    def test_get_cui_from_code_error(self, service):
        """Test get_cui_from_code handles errors."""
        service.api_client.response_data = {}

        cui = service.get_cui_from_code("123456", "SNOMEDCT_US")
        assert cui is None

    def test_get_concept_atoms_string_response(self, service):
        """Test get_concept_atoms with string response (API error)."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/atoms": "Error: Invalid CUI",
        }

        atoms = service.get_concept_atoms("C0012345")
        assert atoms == []

    def test_get_concept_relationships_string_response(self, service):
        """Test get_concept_relationships with string response."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": "Error: Invalid CUI",
        }

        relationships = service.get_concept_relationships("C0012345")
        assert relationships == []

    def test_get_concept_hierarchy_empty_relationships(self, service):
        """Test get_concept_hierarchy with empty relationships."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        hierarchy = service.get_concept_hierarchy("C0012345")
        assert hierarchy["parents"] == []
        assert hierarchy["children"] == []

    def test_get_concept_details_semantic_types_as_string(self, service):
        """Test get_concept_details with semanticTypes as string (URL)."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
                "semanticTypes": "https://some.url/st",
            },
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_atoms_missing_name(self, service):
        """Test get_concept_atoms when atoms lack name field."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/atoms": {
                "results": [{"rootSource": "MMSL"}]
            }
        }

        atoms = service.get_concept_atoms("C0012345")
        assert isinstance(atoms, list)  # Still returns, may be empty names

    def test_get_concept_relationships_with_multiple_types(self, service):
        """Test get_concept_relationships with different relation types."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345/relations": {
                "results": [
                    {
                        "relatedId": "C0012346",
                        "relatedIdName": "Parent",
                        "relationLabel": "isa",
                        "additionalRelationLabel": "PAR",
                    },
                    {
                        "relatedId": "C0012347",
                        "relatedIdName": "RB (broader)",
                        "relationLabel": "rb",
                        "additionalRelationLabel": "RB",
                    },
                    {
                        "relatedId": "C0012348",
                        "relatedIdName": "RN (narrower)",
                        "relationLabel": "rn",
                        "additionalRelationLabel": "RN",
                    },
                ]
            }
        }

        relationships = service.get_concept_relationships("C0012345")
        assert len(relationships) == 3

    def test_get_concept_details_semantic_types_list_error(self, service):
        """Test get_concept_details handles semanticTypes list error."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test",
                "semanticTypes": [None, "bad"],  # Will cause exception
                "definitions": [{"value": "def"}],
            },
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_details_definitions_as_url_fetch_error(self, service):
        """Test get_concept_details when definitions URL fetch fails."""
        responses = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
                "definitions": "https://some.url/definitions",
            },
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        def make_request_side_effect(endpoint, params=None):
            if "definitions" in endpoint:
                raise Exception("API Error")
            return responses.get(endpoint, {})

        service.api_client.response_data = responses
        service.api_client.make_request = make_request_side_effect

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_details_definitions_list_error(self, service):
        """Test get_concept_details handles definitions list error."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
                "definitions": [None, "bad"],  # Will cause exception in .get()
            },
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_details_atom_not_dict(self, service):
        """Test get_concept_details when atom is not a dictionary."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
            },
            "/content/current/CUI/C0012345/atoms": {
                "results": [
                    "not a dict",
                    123,
                    {"name": "valid atom", "rootSource": "MMSL"},
                ]
            },
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None
        assert "valid atom" in concept.synonyms

    def test_get_concept_details_atom_processing_error(self, service):
        """Test get_concept_details handles atom processing error."""

        class BadAtom(dict):
            def get(self, key, default=None):
                if key == "name":
                    raise ValueError("Atom processing error")
                return super().get(key, default)

        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
            },
            "/content/current/CUI/C0012345/atoms": {
                "results": [BadAtom({"name": "bad", "rootSource": "MMSL"})]
            },
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_details_relationships_error(self, service):
        """Test get_concept_details handles relationships fetch error."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
            },
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": Exception("Relations API Error"),
        }

        def make_request_side_effect(endpoint, params=None):
            if "relations" in endpoint:
                raise Exception("Relations API Error")
            return {"results": []}

        service.api_client.make_request = make_request_side_effect

        concept = service.get_concept_details("C0012345")
        assert concept is not None

    def test_get_concept_details_constructor_error(self, service):
        """Test get_concept_details handles UMLSConcept constructor error."""
        service.api_client.response_data = {
            "/content/current/CUI/C0012345": {
                "name": "Test Concept",
                "semanticTypes": [{"name": "Disease or Syndrome"}],
                "definitions": [{"value": "A test definition"}],
            },
            "/content/current/CUI/C0012345/atoms": {"results": []},
            "/content/current/CUI/C0012345/relations": {"results": []},
        }

        with patch(
            "knowledge_lookup.umls.concepts.UMLSConcept",
            side_effect=ValueError("Constructor error"),
        ):
            concept = service.get_concept_details("C0012345")
            assert concept is None

    def test_get_concept_details_top_level_error(self, service):
        """Test get_concept_details handles top-level error."""
        service.api_client.response_data = {}

        def make_request_side_effect(endpoint, params=None):
            if "C0012345" in endpoint:
                raise Exception("Top level API error")
            return {}

        service.api_client.make_request = make_request_side_effect

        concept = service.get_concept_details("C0012345")
        assert concept is None