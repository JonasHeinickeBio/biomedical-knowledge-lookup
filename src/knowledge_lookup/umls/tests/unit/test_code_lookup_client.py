#!/usr/bin/env python3
"""
Unit tests for UMLSCodeLookupClient

These tests use mocks to test the client behavior without making actual API calls.
"""

import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aid_pais_knowledgegraph.umls.code_lookup_client import (
    CodeLookupResult,
    CodeMapping,
    UMLSCodeLookupClient,
)


class TestCodeMapping:
    """Test the CodeMapping dataclass."""

    def test_successful_mapping(self):
        """Test successful mapping properties."""
        mapping = CodeMapping(
            cui="C0011847",
            code="250.00",
            vocab_abbr="ICD9CM",
            vocab_name="International Classification of Diseases, Ninth Revision, Clinical Modification",
            term="Diabetes mellitus",
            term_type="PT",
        )

        assert mapping.is_successful is True
        assert mapping.cui == "C0011847"
        assert mapping.code == "250.00"
        assert mapping.vocab_abbr == "ICD9CM"
        assert mapping.term == "Diabetes mellitus"

    def test_failed_mapping(self):
        """Test failed mapping properties."""
        mapping = CodeMapping(cui="C0011847", error_message="No codes found")

        assert mapping.is_successful is False
        assert mapping.error_message == "No codes found"
        assert mapping.cui == "C0011847"


class TestCodeLookupResult:
    """Test the CodeLookupResult dataclass."""

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        successful_mapping = CodeMapping(cui="C0011847", code="250.00", vocab_abbr="ICD9CM")

        failed_mapping = CodeMapping(cui="C0000000", error_message="Not found")

        result = CodeLookupResult(
            cuis=["C0011847", "C0000000"],
            mappings=[successful_mapping, failed_mapping],
            total_processed=2,
            successful_mappings=1,
            failed_mappings=1,
            total_codes_found=1,
        )

        assert result.success_rate == 50.0
        assert result.average_codes_per_cui == 0.5
        assert len(result.get_successful_mappings()) == 1
        assert len(result.get_failed_mappings()) == 1

    def test_to_dataframe(self):
        """Test conversion to pandas DataFrame."""
        mapping = CodeMapping(
            cui="C0011847",
            code="250.00",
            vocab_abbr="ICD9CM",
            vocab_name="ICD9CM",
            term="Diabetes mellitus",
            term_type="PT",
        )

        result = CodeLookupResult(
            cuis=["C0011847"],
            mappings=[mapping],
            total_processed=1,
            successful_mappings=1,
            total_codes_found=1,
        )

        df = result.to_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["cui"] == "C0011847"
        assert df.iloc[0]["code"] == "250.00"
        assert df.iloc[0]["is_successful"] is True

    def test_get_vocabulary_stats(self):
        """Test vocabulary statistics."""
        mappings = [
            CodeMapping(cui="C0011847", code="250.00", vocab_abbr="ICD9CM"),
            CodeMapping(cui="C0011847", code="E10", vocab_abbr="ICD10CM"),
            CodeMapping(cui="C0011847", code="250.00", vocab_abbr="ICD9CM"),
        ]

        result = CodeLookupResult(
            cuis=["C0011847"],
            mappings=mappings,
            total_processed=1,
            successful_mappings=1,
            total_codes_found=3,
        )

        vocab_stats = result.get_vocabulary_stats()
        assert vocab_stats["ICD9CM"] == 2
        assert vocab_stats["ICD10CM"] == 1


class TestUMLSCodeLookupClient:
    """Test the UMLSCodeLookupClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.client = UMLSCodeLookupClient(self.api_key)

    def test_initialization(self):
        """Test client initialization."""
        assert self.client.api_key == self.api_key
        assert self.client.version == "current"
        assert self.client.max_concurrent_requests == 15
        assert self.client.request_delay == 0.1
        assert self.client.source_vocabularies == ["ALL"]

    def test_custom_initialization(self):
        """Test client initialization with custom parameters."""
        client = UMLSCodeLookupClient(
            api_key="custom_key",
            version="2023AA",
            max_concurrent_requests=10,
            request_delay=0.05,
            source_vocabularies=["ICD9CM", "ICD10CM"],
        )

        assert client.api_key == "custom_key"
        assert client.version == "2023AA"
        assert client.max_concurrent_requests == 10
        assert client.request_delay == 0.05
        assert client.source_vocabularies == ["ICD9CM", "ICD10CM"]

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with UMLSCodeLookupClient(self.api_key) as client:
            assert client.session is not None
            assert isinstance(client.session, aiohttp.ClientSession)

        # Session should be closed after exiting context
        assert client.session.closed

    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test successful HTTP request."""
        mock_response_data = {
            "result": {"results": [{"ui": "250.00", "name": "Diabetes mellitus"}]}
        }

        async with UMLSCodeLookupClient(self.api_key) as client:
            # Mock the session.get method
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            # Mock the session and its get method
            client.session = AsyncMock()
            client.session.get = AsyncMock()
            client.session.get.return_value.__aenter__.return_value = mock_response

            result = await client._make_request("https://test.com/api", {"cui": "C0011847"})

            assert result == mock_response_data
            # Verify API key was added to params
            call_args = client.session.get.call_args
            assert call_args[1]["params"]["apiKey"] == self.api_key

    @pytest.mark.asyncio
    async def test_get_codes_for_cui_success(self):
        """Test successful code retrieval for a CUI."""
        mock_response = {
            "result": {
                "results": [
                    {
                        "ui": "250.00",
                        "name": "Diabetes mellitus",
                        "rootSource": "ICD9CM",
                        "termType": "PT",
                    },
                    {
                        "ui": "E10",
                        "name": "Type 1 diabetes mellitus",
                        "rootSource": "ICD10CM",
                        "termType": "PT",
                    },
                ]
            }
        }

        async with UMLSCodeLookupClient(self.api_key) as client:
            client._make_request = AsyncMock(return_value=mock_response)

            mappings = await client.get_codes_for_cui("C0011847")

            assert len(mappings) == 2

            # Check first mapping
            assert mappings[0].cui == "C0011847"
            assert mappings[0].code == "250.00"
            assert mappings[0].vocab_abbr == "ICD9CM"
            assert mappings[0].term == "Diabetes mellitus"
            assert mappings[0].term_type == "PT"
            assert mappings[0].is_successful is True

            # Check second mapping
            assert mappings[1].cui == "C0011847"
            assert mappings[1].code == "E10"
            assert mappings[1].vocab_abbr == "ICD10CM"
            assert mappings[1].term == "Type 1 diabetes mellitus"

    async def test_get_codes_for_cui_no_results(self):
        """Test code retrieval for CUI with no results."""
        mock_response: dict[str, Any] = {"result": {"results": []}}

        async with UMLSCodeLookupClient(self.api_key) as client:
            client._make_request = AsyncMock(return_value=mock_response)

            mappings = await client.get_codes_for_cui("C0000000")

            assert len(mappings) == 1
            mapping = mappings[0]
            assert mapping.cui == "C0000000"
            assert mapping.is_successful is False
            assert mapping.error_message is not None
            assert "No codes found" in mapping.error_message

    @pytest.mark.asyncio
    async def test_get_codes_for_cui_with_vocabulary_filter(self):
        """Test code retrieval with vocabulary filtering."""
        mock_response = {
            "result": {
                "results": [
                    {
                        "ui": "250.00",
                        "name": "Diabetes mellitus",
                        "rootSource": "ICD9CM",
                        "termType": "PT",
                    },
                    {
                        "ui": "E10",
                        "name": "Type 1 diabetes mellitus",
                        "rootSource": "ICD10CM",
                        "termType": "PT",
                    },
                ]
            }
        }

        async with UMLSCodeLookupClient(self.api_key, source_vocabularies=["ICD9CM"]) as client:
            client._make_request = AsyncMock(return_value=mock_response)

            mappings = await client.get_codes_for_cui("C0011847")

            # Should filter to only ICD9CM results
            assert len(mappings) == 1
            assert mappings[0].vocab_abbr == "ICD9CM"
            assert mappings[0].code == "250.00"

    @pytest.mark.asyncio
    async def test_get_codes_for_cuis_multiple(self):
        """Test code retrieval for multiple CUIs."""
        async with UMLSCodeLookupClient(self.api_key) as client:
            # Mock the single CUI method
            client.get_codes_for_cui = AsyncMock(
                side_effect=[
                    [CodeMapping(cui="C0011847", code="250.00", vocab_abbr="ICD9CM")],
                    [CodeMapping(cui="C0020538", code="401.9", vocab_abbr="ICD9CM")],
                ]
            )

            result = await client.get_codes_for_cuis(["C0011847", "C0020538"])

            assert result.total_processed == 2
            assert result.successful_mappings == 2
            assert result.failed_mappings == 0
            assert result.success_rate == 100.0
            assert result.total_codes_found == 2
            assert len(result.mappings) == 2

    @pytest.mark.asyncio
    async def test_get_codes_from_file(self):
        """Test processing CUIs from a file."""
        # Create a temporary file with test data
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("C0011847\n")
            f.write("C0020538\n")
            f.write("  \n")  # Empty line should be ignored
            f.write("C0004096\n")
            temp_file = f.name

        try:
            async with UMLSCodeLookupClient(self.api_key) as client:
                # Mock the multiple CUIs method
                client.get_codes_for_cuis = AsyncMock(
                    return_value=CodeLookupResult(
                        cuis=["C0011847", "C0020538", "C0004096"],
                        mappings=[],
                        total_processed=3,
                        successful_mappings=3,
                        total_codes_found=3,
                    )
                )

                result = await client.get_codes_from_file(temp_file)

                assert result.total_processed == 3
                # Verify the method was called with correct CUIs
                call_args = client.get_codes_for_cuis.call_args[0][0]
                assert "C0011847" in call_args
                assert "C0020538" in call_args
                assert "C0004096" in call_args
                assert len(call_args) == 3  # Empty line should be filtered out
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_get_codes_from_file_not_found(self):
        """Test processing from non-existent file."""
        async with UMLSCodeLookupClient(self.api_key) as client:
            with pytest.raises(FileNotFoundError):
                await client.get_codes_from_file("nonexistent.txt")

    def test_save_result_txt(self):
        """Test saving result in text format."""
        mapping = CodeMapping(
            cui="C0011847",
            code="250.00",
            vocab_abbr="ICD9CM",
            vocab_name="ICD9CM",
            term="Diabetes mellitus",
            term_type="PT",
        )

        result = CodeLookupResult(
            cuis=["C0011847"],
            mappings=[mapping],
            total_processed=1,
            successful_mappings=1,
            total_codes_found=1,
            execution_time=1.5,
        )

        client = UMLSCodeLookupClient(self.api_key)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            temp_file = f.name

        try:
            client.save_result(result, temp_file, "txt")

            # Verify file was created and has content
            with open(temp_file) as f:
                content = f.read()
                assert "UMLS Code Lookup Results" in content
                assert "C0011847" in content
                assert "250.00" in content
                assert "ICD9CM" in content
        finally:
            os.unlink(temp_file)

    def test_save_result_json(self):
        """Test saving result in JSON format."""
        mapping = CodeMapping(cui="C0011847", code="250.00", vocab_abbr="ICD9CM")

        result = CodeLookupResult(
            cuis=["C0011847"],
            mappings=[mapping],
            total_processed=1,
            successful_mappings=1,
            total_codes_found=1,
        )

        client = UMLSCodeLookupClient(self.api_key)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_file = f.name

        try:
            client.save_result(result, temp_file, "json")

            # Verify file was created and has valid JSON
            import json

            with open(temp_file) as f:
                data = json.load(f)
                assert "metadata" in data
                assert "mappings" in data
                assert data["metadata"]["total_processed"] == 1
                assert data["mappings"][0]["cui"] == "C0011847"
                assert data["mappings"][0]["code"] == "250.00"
        finally:
            os.unlink(temp_file)

    def test_save_result_unsupported_format(self):
        """Test saving result with unsupported format."""
        result = CodeLookupResult(cuis=[], mappings=[], total_processed=0, total_codes_found=0)

        client = UMLSCodeLookupClient(self.api_key)

        with pytest.raises(ValueError, match="Unsupported format"):
            client.save_result(result, "output.xyz", "xyz")

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling during requests."""
        async with UMLSCodeLookupClient(self.api_key) as client:
            # Mock the session to raise an error
            client.session = AsyncMock()
            client.session.get = AsyncMock()
            client.session.get.return_value.__aenter__.side_effect = aiohttp.ClientError(
                "Network error"
            )

            mappings = await client.get_codes_for_cui("C0011847")

            assert len(mappings) == 1
            mapping = mappings[0]
            assert mapping.cui == "C0011847"
            assert mapping.is_successful is False
            assert mapping.error_message is not None
            assert "Network error" in mapping.error_message

    def test_vocabulary_name_mapping(self):
        """Test vocabulary name mapping functionality."""
        client = UMLSCodeLookupClient(self.api_key)

        # Test known vocabulary
        assert (
            client._get_vocabulary_name("ICD9CM")
            == "International Classification of Diseases, Ninth Revision, Clinical Modification"
        )
        assert (
            client._get_vocabulary_name("ICD10CM")
            == "International Classification of Diseases, 10th Revision, Clinical Modification"
        )
        assert client._get_vocabulary_name("SNOMEDCT_US") == "SNOMED Clinical Terms, US Edition"

        # Test unknown vocabulary
        assert client._get_vocabulary_name("UNKNOWN") == "UNKNOWN"
