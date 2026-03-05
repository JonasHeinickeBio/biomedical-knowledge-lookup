#!/usr/bin/env python3
"""
Unit tests for UMLSSemanticTypesClient

These tests use mocks to test the client behavior without making actual API calls.
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock
import tempfile
import os

from aid_pais_knowledgegraph.umls.semantic_types_client import (
    UMLSSemanticTypesClient,
    SemanticTypeMapping,
    SemanticTypesResult
)


class TestSemanticTypeMapping:
    """Test the SemanticTypeMapping dataclass."""
    
    def test_successful_mapping(self):
        """Test successful mapping properties."""
        mapping = SemanticTypeMapping(
            search_string="diabetes",
            cui="C0011847",
            ui="D003920",
            name="Diabetes Mellitus",
            semantic_type="Disease or Syndrome",
            semantic_type_uri="T047"
        )
        
        assert mapping.is_successful is True
        assert mapping.search_string == "diabetes"
        assert mapping.cui == "C0011847"
        assert mapping.semantic_type == "Disease or Syndrome"
    
    def test_failed_mapping(self):
        """Test failed mapping properties."""
        mapping = SemanticTypeMapping(
            search_string="invalidterm",
            error_message="No results found"
        )
        
        assert mapping.is_successful is False
        assert mapping.error_message == "No results found"


class TestSemanticTypesResult:
    """Test the SemanticTypesResult dataclass."""
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        successful_mapping = SemanticTypeMapping(
            search_string="diabetes",
            cui="C0011847"
        )
        
        failed_mapping = SemanticTypeMapping(
            search_string="invalid",
            error_message="Not found"
        )
        
        result = SemanticTypesResult(
            search_strings=["diabetes", "invalid"],
            mappings=[successful_mapping, failed_mapping],
            total_processed=2,
            successful_mappings=1,
            failed_mappings=1
        )
        
        assert result.success_rate == 50.0
        assert len(result.get_successful_mappings()) == 1
        assert len(result.get_failed_mappings()) == 1
    
    def test_to_dataframe(self):
        """Test conversion to pandas DataFrame."""
        mapping = SemanticTypeMapping(
            search_string="diabetes",
            cui="C0011847",
            ui="D003920",
            name="Diabetes Mellitus"
        )
        
        result = SemanticTypesResult(
            search_strings=["diabetes"],
            mappings=[mapping],
            total_processed=1,
            successful_mappings=1
        )
        
        df = result.to_dataframe()
        assert len(df) == 1
        assert df.iloc[0]['search_string'] == "diabetes"
        assert df.iloc[0]['cui'] == "C0011847"
        assert df.iloc[0]['is_successful'] is True


class TestUMLSSemanticTypesClient:
    """Test the UMLSSemanticTypesClient class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.client = UMLSSemanticTypesClient(self.api_key)
    
    def test_initialization(self):
        """Test client initialization."""
        assert self.client.api_key == self.api_key
        assert self.client.version == "current"
        assert self.client.max_concurrent_requests == 10
        assert self.client.request_delay == 0.1
    
    def test_custom_initialization(self):
        """Test client initialization with custom parameters."""
        client = UMLSSemanticTypesClient(
            api_key="custom_key",
            version="2023AA",
            max_concurrent_requests=20,
            request_delay=0.05
        )
        
        assert client.api_key == "custom_key"
        assert client.version == "2023AA"
        assert client.max_concurrent_requests == 20
        assert client.request_delay == 0.05
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with UMLSSemanticTypesClient(self.api_key) as client:
            assert client.session is not None
            assert isinstance(client.session, aiohttp.ClientSession)
        
        # Session should be closed after exiting context
        assert client.session.closed
    
    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test successful HTTP request."""
        mock_response_data = {
            "result": {
                "results": [
                    {"ui": "C0011847", "name": "Diabetes Mellitus"}
                ]
            }
        }
        
        async with UMLSSemanticTypesClient(self.api_key) as client:
            # Mock the session.get method
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            # Mock the session and its get method
            client.session = AsyncMock()
            client.session.get = AsyncMock()
            client.session.get.return_value.__aenter__.return_value = mock_response
            
            result = await client._make_request(
                "https://test.com/api",
                {"string": "diabetes"}
            )
            
            assert result == mock_response_data
            # Verify API key was added to params
            call_args = client.session.get.call_args
            assert call_args[1]['params']['apiKey'] == self.api_key
    
    @pytest.mark.asyncio
    async def test_make_request_error(self):
        """Test HTTP request with error."""
        async with UMLSSemanticTypesClient(self.api_key) as client:
            # Mock the session and its get method to raise an error
            client.session = AsyncMock()
            client.session.get = AsyncMock()
            client.session.get.return_value.__aenter__.side_effect = aiohttp.ClientError("Network error")
            
            with pytest.raises(aiohttp.ClientError):
                await client._make_request(
                    "https://test.com/api",
                    {"string": "diabetes"}
                )
    
    @pytest.mark.asyncio
    async def test_search_string_success(self):
        """Test successful string search."""
        mock_search_response = {
            "result": {
                "results": [
                    {"ui": "C0011847"},
                    {"ui": "C0011849"}
                ]
            }
        }
        
        async with UMLSSemanticTypesClient(self.api_key) as client:
            # Mock the _make_request method
            client._make_request = AsyncMock(return_value=mock_search_response)
            
            cuis = await client._search_string("diabetes")
            
            assert len(cuis) == 2
            assert "C0011847" in cuis
            assert "C0011849" in cuis
    
    @pytest.mark.asyncio
    async def test_search_string_no_results(self):
        """Test string search with no results."""
        mock_search_response = {
            "result": {
                "results": []
            }
        }
        
        async with UMLSSemanticTypesClient(self.api_key) as client:
            client._make_request = AsyncMock(return_value=mock_search_response)
            
            cuis = await client._search_string("invalidterm")
            
            assert len(cuis) == 0
    
    @pytest.mark.asyncio
    async def test_get_semantic_types_success(self):
        """Test successful semantic types retrieval."""
        mock_content_response = {
            "result": {
                "ui": "C0011847",
                "name": "Diabetes Mellitus",
                "semanticTypes": [
                    {
                        "name": "Disease or Syndrome",
                        "uri": "T047"
                    }
                ]
            }
        }
        
        async with UMLSSemanticTypesClient(self.api_key) as client:
            client._make_request = AsyncMock(return_value=mock_content_response)
            
            ui, name, semantic_type, semantic_type_uri = await client._get_semantic_types("C0011847")
            
            assert ui == "C0011847"
            assert name == "Diabetes Mellitus"
            assert semantic_type == "Disease or Syndrome"
            assert semantic_type_uri == "T047"
    
    @pytest.mark.asyncio
    async def test_get_semantic_types_for_string_success(self):
        """Test complete semantic types retrieval for a string."""
        async with UMLSSemanticTypesClient(self.api_key) as client:
            # Mock both search and content retrieval
            client._search_string = AsyncMock(return_value=["C0011847"])
            client._get_semantic_types = AsyncMock(return_value=(
                "C0011847", "Diabetes Mellitus", "Disease or Syndrome", "T047"
            ))
            
            mappings = await client.get_semantic_types_for_string("diabetes")
            
            assert len(mappings) == 1
            mapping = mappings[0]
            assert mapping.search_string == "diabetes"
            assert mapping.cui == "C0011847"
            assert mapping.name == "Diabetes Mellitus"
            assert mapping.is_successful is True
    
    @pytest.mark.asyncio
    async def test_get_semantic_types_for_string_no_results(self):
        """Test semantic types retrieval for string with no results."""
        async with UMLSSemanticTypesClient(self.api_key) as client:
            client._search_string = AsyncMock(return_value=[])
            
            mappings = await client.get_semantic_types_for_string("invalidterm")
            
            assert len(mappings) == 1
            mapping = mappings[0]
            assert mapping.search_string == "invalidterm"
            assert mapping.is_successful is False
            assert mapping.error_message is not None
            assert "No CUIs found" in mapping.error_message
    
    @pytest.mark.asyncio
    async def test_get_semantic_types_for_strings_multiple(self):
        """Test semantic types retrieval for multiple strings."""
        async with UMLSSemanticTypesClient(self.api_key) as client:
            # Mock the single string method
            client.get_semantic_types_for_string = AsyncMock(side_effect=[
                [SemanticTypeMapping(search_string="diabetes", cui="C0011847")],
                [SemanticTypeMapping(search_string="hypertension", cui="C0020538")]
            ])
            
            result = await client.get_semantic_types_for_strings(
                ["diabetes", "hypertension"]
            )
            
            assert result.total_processed == 2
            assert result.successful_mappings == 2
            assert result.failed_mappings == 0
            assert result.success_rate == 100.0
            assert len(result.mappings) == 2
    
    @pytest.mark.asyncio
    async def test_get_semantic_types_from_file(self):
        """Test processing strings from a file."""
        # Create a temporary file with test data
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("diabetes\n")
            f.write("hypertension\n")
            f.write("  \n")  # Empty line should be ignored
            f.write("asthma\n")
            temp_file = f.name
        
        try:
            async with UMLSSemanticTypesClient(self.api_key) as client:
                # Mock the multiple strings method
                client.get_semantic_types_for_strings = AsyncMock(
                    return_value=SemanticTypesResult(
                        search_strings=["diabetes", "hypertension", "asthma"],
                        mappings=[],
                        total_processed=3,
                        successful_mappings=3
                    )
                )
                
                result = await client.get_semantic_types_from_file(temp_file)
                
                assert result.total_processed == 3
                # Verify the method was called with correct strings
                call_args = client.get_semantic_types_for_strings.call_args[0][0]
                assert "diabetes" in call_args
                assert "hypertension" in call_args
                assert "asthma" in call_args
                assert len(call_args) == 3  # Empty line should be filtered out
        finally:
            os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_get_semantic_types_from_file_not_found(self):
        """Test processing from non-existent file."""
        async with UMLSSemanticTypesClient(self.api_key) as client:
            with pytest.raises(FileNotFoundError):
                await client.get_semantic_types_from_file("nonexistent.txt")
    
    def test_save_result_txt(self):
        """Test saving result in text format."""
        mapping = SemanticTypeMapping(
            search_string="diabetes",
            cui="C0011847",
            ui="D003920",
            name="Diabetes Mellitus",
            semantic_type="Disease or Syndrome",
            semantic_type_uri="T047"
        )
        
        result = SemanticTypesResult(
            search_strings=["diabetes"],
            mappings=[mapping],
            total_processed=1,
            successful_mappings=1,
            execution_time=1.5
        )
        
        client = UMLSSemanticTypesClient(self.api_key)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name
        
        try:
            client.save_result(result, temp_file, "txt")
            
            # Verify file was created and has content
            with open(temp_file, 'r') as f:
                content = f.read()
                assert "UMLS Semantic Types Results" in content
                assert "diabetes" in content
                assert "C0011847" in content
                assert "Disease or Syndrome" in content
        finally:
            os.unlink(temp_file)
    
    def test_save_result_json(self):
        """Test saving result in JSON format."""
        mapping = SemanticTypeMapping(
            search_string="diabetes",
            cui="C0011847"
        )
        
        result = SemanticTypesResult(
            search_strings=["diabetes"],
            mappings=[mapping],
            total_processed=1,
            successful_mappings=1
        )
        
        client = UMLSSemanticTypesClient(self.api_key)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            client.save_result(result, temp_file, "json")
            
            # Verify file was created and has valid JSON
            import json
            with open(temp_file, 'r') as f:
                data = json.load(f)
                assert "metadata" in data
                assert "mappings" in data
                assert data["metadata"]["total_processed"] == 1
                assert data["mappings"][0]["search_string"] == "diabetes"
        finally:
            os.unlink(temp_file)
    
    def test_save_result_unsupported_format(self):
        """Test saving result with unsupported format."""
        result = SemanticTypesResult(
            search_strings=[],
            mappings=[],
            total_processed=0
        )
        
        client = UMLSSemanticTypesClient(self.api_key)
        
        with pytest.raises(ValueError, match="Unsupported format"):
            client.save_result(result, "output.xyz", "xyz")
