"""
Unit tests for export functions.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.exports import export_to_csv, export_to_json
from knowledge_lookup.models import (
    ConceptType,
    KnowledgeSource,
    LookupResult,
    UnifiedConcept,
)


class TestExports:
    """Tests for export functions."""

    @pytest.fixture
    def sample_result(self):
        """Create sample lookup result for testing."""
        concept = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test Disease", concept_type=ConceptType.DISEASE
        )
        concept.add_identifier(KnowledgeSource.BIOPORTAL, "TEST:001", "Test Disease")
        concept.add_identifier(KnowledgeSource.OLS, "TEST:001", "Test Disease")
        concept.synonyms = ["synonym1", "synonym2"]
        concept.definitions = ["definition1"]
        concept.semantic_types = ["Disease"]
        concept.categories = ["Category1"]
        concept.parents = ["parent1"]
        concept.children = ["child1"]
        concept.confidence_score = 0.95

        result = LookupResult(
            query="test disease",
            concepts=[concept],
            total_found=1,  # Set total_found since concepts are provided directly
            execution_time=2.5,
            sources_queried=[KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.BIOPORTAL],
            errors={KnowledgeSource.OLS: Exception("Test error")},
        )
        return result

    def test_export_to_json_dict_return(self, sample_result):
        """Test export_to_json returns dict when no filepath provided."""
        result = export_to_json(sample_result)

        assert isinstance(result, dict)
        assert result["query"] == "test disease"
        assert result["execution_time"] == 2.5
        assert result["total_found"] == 1
        assert len(result["concepts"]) == 1

        concept_data = result["concepts"][0]
        assert concept_data["primary_label"] == "Test Disease"
        assert concept_data["primary_id"] == "TEST:001"
        assert concept_data["concept_type"] == "disease"
        assert concept_data["confidence_score"] == 0.95
        assert set(concept_data["sources"]) == {"bioportal", "ols"}
        assert concept_data["synonyms"] == ["synonym1", "synonym2"]
        assert concept_data["definitions"] == ["definition1"]
        assert len(concept_data["identifiers"]) == 2

    def test_export_to_json_file_creation(self, sample_result):
        """Test export_to_json creates file when filepath provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / "test_export.json"

            result = export_to_json(sample_result, filepath)

            assert filepath.exists()
            assert result == str(filepath)

            # Verify file contents
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                assert data["query"] == "test disease"
                assert len(data["concepts"]) == 1

    def test_export_to_json_directory_creation(self, sample_result):
        """Test export_to_json creates directories when needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "dir" / "test_export.json"

            result = export_to_json(sample_result, nested_path)

            assert nested_path.exists()
            assert result == str(nested_path)

    @patch("knowledge_lookup.exports.logger")
    def test_export_to_json_logging(self, mock_logger, sample_result):
        """Test export_to_json logs file creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / "test_export.json"

            export_to_json(sample_result, filepath)

            mock_logger.info.assert_called_once()

    def test_export_to_csv_with_concepts(self, sample_result):
        """Test export_to_csv with concepts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / "test_export.csv"

            result = export_to_csv(sample_result, filepath)

            assert filepath.exists()
            assert result == str(filepath)

            # Verify CSV contents
            with open(filepath, encoding="utf-8") as f:
                lines = f.readlines()
                assert len(lines) == 2  # Header + 1 data row
                assert lines[0].startswith("primary_label,primary_id")
                assert "Test Disease" in lines[1]

    def test_export_to_csv_empty_concepts(self):
        """Test export_to_csv with no concepts."""
        result = LookupResult(query="empty", concepts=[])

        csv_result = export_to_csv(result)
        assert csv_result is None

    @patch("knowledge_lookup.exports.logger")
    def test_export_to_csv_empty_concepts_logging(self, mock_logger):
        """Test export_to_csv logs warning for empty concepts."""
        result = LookupResult(query="empty", concepts=[])

        export_to_csv(result)

        mock_logger.warning.assert_called_once_with("No concepts to export.")

    def test_export_to_csv_directory_creation(self, sample_result):
        """Test export_to_csv creates directories when needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "dir" / "test_export.csv"

            result = export_to_csv(sample_result, nested_path)

            assert nested_path.exists()
            assert result == str(nested_path)

    @patch("knowledge_lookup.exports.logger")
    def test_export_to_csv_logging(self, mock_logger, sample_result):
        """Test export_to_csv logs file creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / "test_export.csv"

            export_to_csv(sample_result, filepath)

            mock_logger.info.assert_called_once()

    def test_export_to_json_with_errors(self, sample_result):
        """Test export_to_json includes error information."""
        result = export_to_json(sample_result)

        assert "errors" in result
        assert "ols" in result["errors"]
        assert "Test error" in result["errors"]["ols"]

    def test_export_to_json_sources_info(self, sample_result):
        """Test export_to_json includes source information."""
        result = export_to_json(sample_result)

        assert result["sources_queried"] == ["bioportal", "ols"]
        assert result["sources_succeeded"] == ["bioportal"]
