"""
Pytest configuration and fixtures for the test suite.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from knowledge_lookup import LookupConfig
from knowledge_lookup.models import (
    ConceptType,
    KnowledgeSource,
    LookupResult,
    UnifiedConcept,
)

# Fix Typer 0.9.x compatibility with Click 8.1+
try:
    import typer.core
    import click
    
    def robust_metavar(original_func):
        def wrapper(self, *args, **kwargs):
            try:
                return original_func(self, *args, **kwargs)
            except TypeError:
                # If it failed with TypeError, try calling with fewer args
                if len(args) > 0:
                    return wrapper(self, *args[:-1], **kwargs)
                return original_func(self)
        return wrapper

    # Patch Click and Typer methods that commonly cause signature issues
    click.ParamType.get_metavar = robust_metavar(click.ParamType.get_metavar)
    click.Parameter.make_metavar = robust_metavar(click.Parameter.make_metavar)
    typer.core.TyperArgument.make_metavar = robust_metavar(typer.core.TyperArgument.make_metavar)
    typer.core.TyperOption.make_metavar = robust_metavar(typer.core.TyperOption.make_metavar)

except (ImportError, AttributeError):
    pass

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def lookup_config():
    """Provide a default LookupConfig for testing."""
    return LookupConfig(
        max_results_per_source=20,
        timeout_per_source=30.0,
        rate_limits={},
    )


@pytest.fixture
def sample_unified_concept():
    """Provide a sample UnifiedConcept for testing."""
    concept = UnifiedConcept(
        primary_id="TEST:001",
        primary_label="Test Concept",
        concept_type=ConceptType.DISEASE,
        synonyms=["test", "testing"],
        definitions=["A test concept for unit testing"],
        source_data={
            KnowledgeSource.OLS: {
                "ontology": "TEST",
                "iri": "http://test.org/001",
            }
        },
    )
    concept.add_identifier(KnowledgeSource.OLS, "TEST:001", "Test Concept")
    return concept


@pytest.fixture
def sample_unified_concepts() -> list[UnifiedConcept]:
    """Provide multiple sample UnifiedConcepts for testing."""
    return [
        UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
            synonyms=["diabetes", "DM"],
            definitions=["A metabolic disease"],
        ),
        UnifiedConcept(
            primary_id="HP:0000819",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.PHENOTYPE,
            synonyms=["diabetes"],
            definitions=["Diabetes mellitus phenotype"],
        ),
    ]


@pytest.fixture
def mock_http_response():
    """Provide a mock HTTP response."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"result": "success"})
    mock_response.text = AsyncMock(return_value='{"result": "success"}')
    return mock_response


@pytest.fixture
def mock_bioportal_response():
    """Provide a mock BioPortal API response."""
    return {
        "collection": [
            {
                "@id": "http://purl.bioontology.org/ontology/SNOMEDCT/73211009",
                "prefLabel": "Diabetes mellitus",
                "synonym": ["Diabetes", "DM"],
                "definition": ["A metabolic disease"],
                "cui": ["C0011849"],
                "semanticType": ["Disease or Syndrome"],
            }
        ]
    }


@pytest.fixture
def mock_ols_response():
    """Provide a mock OLS API response."""
    return {
        "response": {
            "docs": [
                {
                    "iri": "http://purl.obolibrary.org/obo/DOID_9351",
                    "label": "diabetes mellitus",
                    "description": ["A metabolic disease"],
                    "synonyms": ["diabetes", "DM"],
                    "ontology_name": "doid",
                    "short_form": "DOID_9351",
                }
            ]
        }
    }


@pytest.fixture
def mock_umls_response():
    """Provide a mock UMLS API response."""
    return {
        "result": {
            "results": [
                {
                    "ui": "C0011849",
                    "name": "Diabetes Mellitus",
                    "rootSource": "MTH",
                    "semanticTypes": [{"name": "Disease or Syndrome"}],
                }
            ]
        }
    }


@pytest.fixture
def mock_chembl_response():
    """Provide a mock ChEMBL API response."""
    return {
        "molecules": [
            {
                "molecule_chembl_id": "CHEMBL1234",
                "pref_name": "Test Compound",
                "molecule_synonyms": [{"molecule_synonym": "Test"}],
            }
        ]
    }


@pytest.fixture
def sample_lookup_result(sample_unified_concepts) -> LookupResult:
    """Provide a sample LookupResult for testing."""
    result = LookupResult(
        query="diabetes",
        concepts=sample_unified_concepts,
        total_found=len(sample_unified_concepts),
        sources_queried=[KnowledgeSource.OLS, KnowledgeSource.BIOPORTAL],
        sources_succeeded=[KnowledgeSource.OLS],
        sources_failed=[KnowledgeSource.BIOPORTAL],
        execution_time=1.5,
        errors={KnowledgeSource.BIOPORTAL: "API timeout"},
    )
    return result
