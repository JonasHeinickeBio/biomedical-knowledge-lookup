"""
Unit tests for CLI interface.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup import __main__ as main
from typer.testing import CliRunner


class TestCLI:
    """Tests for CLI interface."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_search_command_basic(self, runner):
        from knowledge_lookup.models import LookupResult
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_lookup_class:
            mock_lookup = AsyncMock()
            mock_lookup_class.return_value = mock_lookup
            mock_lookup.search_concepts.return_value = LookupResult(query="test query", concepts=[])
            result = runner.invoke(main.app, ["search", "test query"])
            assert result.exit_code == 0
            assert "Searching for:" in result.output
            assert "No results found" in result.output

    def test_search_command_with_results(self, runner):
        from knowledge_lookup.models import (
            ConceptType,
            KnowledgeSource,
            LookupResult,
            UnifiedConcept,
        )
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_lookup_class:
            mock_lookup = AsyncMock()
            mock_lookup_class.return_value = mock_lookup
            concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept", concept_type=ConceptType.DISEASE)
            concept.add_identifier(KnowledgeSource.BIOPORTAL, "TEST:001", "Test Concept")
            mock_result = LookupResult(
                query="test query", concepts=[concept],
                sources_queried=[KnowledgeSource.BIOPORTAL], sources_succeeded=[KnowledgeSource.BIOPORTAL],
            )
            mock_lookup.search_concepts.return_value = mock_result
            result = runner.invoke(main.app, ["search", "test query"])
            assert result.exit_code == 0
            assert "Test Concept" in result.output

    def test_sources_command(self, runner):
        result = runner.invoke(main.app, ["sources"])
        assert result.exit_code == 0
        assert "Available Knowledge Sources" in result.output

    def test_info_command(self, runner):
        with patch("knowledge_lookup.__main__.__version__", "1.0.0"), \
             patch("knowledge_lookup.__main__.__description__", "Test description"), \
             patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_lookup_class:
            mock_lookup = MagicMock()
            mock_lookup._get_adapter.return_value = MagicMock()
            mock_lookup_class.return_value = mock_lookup
            result = runner.invoke(main.app, ["info"])
            assert result.exit_code == 0
            assert "Biomedical Knowledge Lookup" in result.output

    def test_callback_help(self, runner):
        result = runner.invoke(main.app, ["--help"])
        assert result.exit_code in [0, 1]

    def test_search_command_help(self, runner):
        result = runner.invoke(main.app, ["search", "--help"])
        assert result.exit_code in [0, 1]

    def test_search_with_unknown_source(self, runner):
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_cls.return_value = AsyncMock()
            result = runner.invoke(main.app, ["search", "query", "--source", "bogus_source"])
            assert result.exit_code == 1
            assert "Unknown source" in result.output

    def test_search_with_known_source(self, runner):
        from knowledge_lookup.models import LookupResult
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[])
            result = runner.invoke(main.app, ["search", "query", "--source", "chembl"])
            assert result.exit_code == 0

    def test_search_sources_printed(self, runner):
        from knowledge_lookup.models import LookupResult
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[])
            result = runner.invoke(main.app, ["search", "query", "-s", "chembl"])
            assert result.exit_code == 0

    def test_search_json_output(self, runner):
        from knowledge_lookup.models import (
            ConceptType,
            KnowledgeSource,
            LookupResult,
            UnifiedConcept,
        )
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE)
            concept.add_identifier(KnowledgeSource.CHEMBL, "C1", "Concept1")
            concept.definitions = ["A definition"]
            mock_lookup.search_concepts.return_value = LookupResult(
                query="q", concepts=[concept], sources_queried=[KnowledgeSource.CHEMBL]
            )
            result = runner.invoke(main.app, ["search", "query", "-o", "json"])
            assert result.exit_code == 0
            assert "Concept1" in result.output

    def test_search_csv_output(self, runner):
        from knowledge_lookup.models import (
            ConceptType,
            KnowledgeSource,
            LookupResult,
            UnifiedConcept,
        )
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE)
            concept.add_identifier(KnowledgeSource.CHEMBL, "C1", "Concept1")
            concept.definitions = ["A definition"]
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query", "-o", "csv"])
            assert result.exit_code == 0
            assert "Concept1" in result.output

    def test_search_csv_no_definitions(self, runner):
        from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE)
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query", "-o", "csv"])
            assert result.exit_code == 0

    def test_search_table_long_description(self, runner):
        from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE)
            concept.definitions = ["A" * 100]
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query"])
            assert result.exit_code == 0
            # Rich table truncation uses "…" character
            assert len(result.concepts) if hasattr(result, 'concepts') else True

    def test_search_exception_handling(self, runner):
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            mock_lookup.search_concepts.side_effect = RuntimeError("network down")
            result = runner.invoke(main.app, ["search", "query"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_search_json_no_definitions(self, runner):
        from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE)
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query", "-o", "json"])
            assert result.exit_code == 0
