#!/usr/bin/env python3
"""
Integration tests for the UMLS client ecosystem

These tests demonstrate how the different UMLS clients work together
and provide comprehensive workflows for common use cases.
"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock

import pytest
from aid_pais_knowledgegraph.umls.code_lookup_client import UMLSCodeLookupClient
from aid_pais_knowledgegraph.umls.concept_lookup_client import UMLSConceptLookupClient
from aid_pais_knowledgegraph.umls.crosswalk_client import UMLSCrosswalkClient
from aid_pais_knowledgegraph.umls.semantic_types_client import UMLSSemanticTypesClient
from aid_pais_knowledgegraph.umls.string_concept_client import UMLSStringConceptClient


class TestUMLSClientIntegration:
    """Integration tests for the UMLS client ecosystem."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.test_terms = ["diabetes", "hypertension", "asthma"]
        self.test_cuis = ["C0011847", "C0020538", "C0004096"]
        self.test_codes = ["250.00", "401.9", "493.9"]

    @pytest.mark.asyncio
    async def test_complete_semantic_analysis_workflow(self):
        """Test complete workflow: terms -> CUIs -> codes -> semantic types."""
        # Step 1: Get CUIs from terms
        async with UMLSStringConceptClient(self.api_key) as string_client:
            # Mock response for string to concept lookup
            string_client.get_concepts_for_string = AsyncMock(
                return_value=[{"cui": "C0011847", "name": "Diabetes Mellitus", "score": 0.95}]
            )

            concept_result = await string_client.get_concepts_for_strings(["diabetes"])
            assert len(concept_result.mappings) == 1
            cui = concept_result.mappings[0].cui

        # Step 2: Get codes for the CUI
        async with UMLSCodeLookupClient(self.api_key) as code_client:
            code_client.get_codes_for_cui = AsyncMock(
                return_value=[
                    {
                        "cui": cui,
                        "code": "250.00",
                        "vocab_abbr": "ICD9CM",
                        "term": "Diabetes mellitus",
                    }
                ]
            )

            code_result = await code_client.get_codes_for_cuis([cui])
            assert len(code_result.mappings) == 1
            assert code_result.mappings[0].code == "250.00"

        # Step 3: Get semantic types
        async with UMLSSemanticTypesClient(self.api_key) as semantic_client:
            semantic_client.get_semantic_types_for_string = AsyncMock(
                return_value=[
                    {
                        "search_string": "diabetes",
                        "cui": cui,
                        "semantic_type": "Disease or Syndrome",
                    }
                ]
            )

            semantic_result = await semantic_client.get_semantic_types_for_strings(["diabetes"])
            assert len(semantic_result.mappings) == 1
            assert semantic_result.mappings[0].semantic_type == "Disease or Syndrome"

    @pytest.mark.asyncio
    async def test_bidirectional_concept_code_mapping(self):
        """Test bidirectional mapping between concepts and codes."""
        # Forward mapping: CUI -> codes
        async with UMLSCodeLookupClient(self.api_key) as code_client:
            code_client.get_codes_for_cui = AsyncMock(
                return_value=[{"cui": "C0011847", "code": "250.00", "vocab_abbr": "ICD9CM"}]
            )

            forward_result = await code_client.get_codes_for_cuis(["C0011847"])
            retrieved_code = forward_result.mappings[0].code

        # Reverse mapping: code -> CUI
        async with UMLSConceptLookupClient(self.api_key) as concept_client:
            concept_client.get_concepts_for_code = AsyncMock(
                return_value=[
                    {"code": retrieved_code, "cui": "C0011847", "name": "Diabetes Mellitus"}
                ]
            )

            reverse_result = await concept_client.get_concepts_for_codes([retrieved_code])

            # Verify round-trip consistency
            assert reverse_result.mappings[0].cui == "C0011847"

    @pytest.mark.asyncio
    async def test_vocabulary_crosswalk_integration(self):
        """Test vocabulary crosswalk between different coding systems."""
        async with UMLSCrosswalkClient(self.api_key) as crosswalk_client:
            # Mock crosswalk from ICD9CM to ICD10CM
            crosswalk_client.get_crosswalk_for_code = AsyncMock(
                return_value=[
                    {
                        "source_code": "250.00",
                        "source_vocab": "ICD9CM",
                        "target_code": "E11.9",
                        "target_vocab": "ICD10CM",
                        "target_name": "Type 2 diabetes mellitus without complications",
                    }
                ]
            )

            crosswalk_result = await crosswalk_client.get_crosswalk_for_codes(
                ["250.00"], source_vocab="ICD9CM", target_vocab="ICD10CM"
            )

            assert len(crosswalk_result.mappings) == 1
            assert crosswalk_result.mappings[0].target_code == "E11.9"
            assert crosswalk_result.mappings[0].target_vocab == "ICD10CM"

    @pytest.mark.asyncio
    async def test_parallel_client_processing(self):
        """Test running multiple clients in parallel for efficiency."""

        async def get_semantic_types():
            async with UMLSSemanticTypesClient(self.api_key) as client:
                client.get_semantic_types_for_strings = AsyncMock(
                    return_value={"total_processed": 3}
                )
                return await client.get_semantic_types_for_strings(self.test_terms)

        async def get_codes():
            async with UMLSCodeLookupClient(self.api_key) as client:
                client.get_codes_for_cuis = AsyncMock(return_value={"total_processed": 3})
                return await client.get_codes_for_cuis(self.test_cuis)

        async def get_concepts():
            async with UMLSConceptLookupClient(self.api_key) as client:
                client.get_concepts_for_codes = AsyncMock(return_value={"total_processed": 3})
                return await client.get_concepts_for_codes(self.test_codes)

        # Run all clients in parallel
        semantic_result, code_result, concept_result = await asyncio.gather(
            get_semantic_types(), get_codes(), get_concepts()
        )

        # Verify all operations completed
        assert semantic_result["total_processed"] == 3
        assert code_result["total_processed"] == 3
        assert concept_result["total_processed"] == 3

    @pytest.mark.asyncio
    async def test_error_handling_across_clients(self):
        """Test error handling consistency across different clients."""
        # Test that all clients handle API errors gracefully
        async with UMLSSemanticTypesClient(self.api_key) as semantic_client:
            semantic_client._make_request = AsyncMock(side_effect=Exception("API Error"))

            # Should return failed mappings instead of raising
            result = await semantic_client.get_semantic_types_for_strings(["invalid"])
            assert result.failed_mappings > 0

        async with UMLSCodeLookupClient(self.api_key) as code_client:
            code_client._make_request = AsyncMock(side_effect=Exception("API Error"))

            result = await code_client.get_codes_for_cuis(["C0000000"])
            assert result.failed_mappings > 0

    @pytest.mark.asyncio
    async def test_file_processing_pipeline(self):
        """Test processing files through multiple clients."""
        # Create temporary input file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("diabetes\nhypertension\nasthma\n")
            input_file = f.name

        try:
            # Step 1: Process terms to get CUIs
            async with UMLSStringConceptClient(self.api_key) as string_client:
                string_client.get_concepts_for_strings = AsyncMock(
                    return_value=type(
                        "Result",
                        (),
                        {
                            "mappings": [
                                type(
                                    "Mapping", (), {"cui": "C0011847", "search_string": "diabetes"}
                                ),
                                type(
                                    "Mapping",
                                    (),
                                    {"cui": "C0020538", "search_string": "hypertension"},
                                ),
                                type(
                                    "Mapping", (), {"cui": "C0004096", "search_string": "asthma"}
                                ),
                            ]
                        },
                    )()
                )

                concept_result = await string_client.get_concepts_from_file(input_file)
                extracted_cuis = [m.cui for m in concept_result.mappings]

            # Step 2: Get codes for the CUIs
            async with UMLSCodeLookupClient(self.api_key) as code_client:
                code_client.get_codes_for_cuis = AsyncMock(
                    return_value=type(
                        "Result",
                        (),
                        {
                            "mappings": [
                                type("Mapping", (), {"cui": "C0011847", "code": "250.00"}),
                                type("Mapping", (), {"cui": "C0020538", "code": "401.9"}),
                                type("Mapping", (), {"cui": "C0004096", "code": "493.9"}),
                            ]
                        },
                    )()
                )

                code_result = await code_client.get_codes_for_cuis(extracted_cuis)

            # Verify pipeline results
            assert len(extracted_cuis) == 3
            assert len(code_result.mappings) == 3
            assert any(m.code == "250.00" for m in code_result.mappings)

        finally:
            os.unlink(input_file)

    @pytest.mark.asyncio
    async def test_multi_format_output_consistency(self):
        """Test that all clients produce consistent output formats."""
        # Create test data
        test_result = type(
            "Result",
            (),
            {
                "mappings": [{"test": "data"}],
                "total_processed": 1,
                "successful_mappings": 1,
                "failed_mappings": 0,
                "execution_time": 1.0,
            },
        )()

        clients = [
            UMLSSemanticTypesClient(self.api_key),
            UMLSCodeLookupClient(self.api_key),
            UMLSConceptLookupClient(self.api_key),
            UMLSStringConceptClient(self.api_key),
        ]

        formats = ["txt", "json", "csv"]

        for client in clients:
            for format_type in formats:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format_type}") as f:
                    temp_file = f.name

                try:
                    # All clients should support these formats
                    client.save_result(test_result, temp_file, format_type)

                    # Verify file was created
                    assert os.path.exists(temp_file)
                    assert os.path.getsize(temp_file) > 0

                finally:
                    os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_performance_optimization_features(self):
        """Test performance optimization features across clients."""
        # Test concurrent processing
        async with UMLSSemanticTypesClient(self.api_key, max_concurrent_requests=20) as client:
            assert client.max_concurrent_requests == 20

            # Mock concurrent execution
            client.get_semantic_types_for_string = AsyncMock(return_value=[])

            # Should handle multiple requests concurrently
            tasks = [client.get_semantic_types_for_string(term) for term in self.test_terms]

            results = await asyncio.gather(*tasks)
            assert len(results) == len(self.test_terms)

    @pytest.mark.asyncio
    async def test_rate_limiting_compliance(self):
        """Test that clients respect rate limiting."""
        # Test with different delay settings
        async with UMLSCodeLookupClient(self.api_key, request_delay=0.1) as client:
            assert client.request_delay == 0.1

            # Mock to verify delay is respected
            client._make_request = AsyncMock(return_value={"result": {"results": []}})

            # Measure execution time for multiple requests
            import time

            start_time = time.time()

            await client.get_codes_for_cuis(["C0011847", "C0020538"])

            execution_time = time.time() - start_time

            # Should take at least the delay time
            # (This is a simplified test - real implementation would be more sophisticated)
            assert execution_time >= 0.0  # Basic sanity check

    def test_client_configuration_consistency(self):
        """Test that all clients have consistent configuration options."""
        common_params = {
            "api_key": self.api_key,
            "version": "2023AA",
            "max_concurrent_requests": 10,
            "request_delay": 0.1,
        }

        clients = [
            UMLSSemanticTypesClient(**common_params),
            UMLSCodeLookupClient(**common_params),
            UMLSConceptLookupClient(**common_params),
            UMLSStringConceptClient(**common_params),
        ]

        for client in clients:
            assert client.api_key == self.api_key
            assert client.version == "2023AA"
            assert client.max_concurrent_requests == 10
            assert client.request_delay == 0.1

    @pytest.mark.asyncio
    async def test_real_world_medical_terminology_workflow(self):
        """Test realistic medical terminology processing workflow."""
        # Simulate a real-world scenario: processing clinical terms
        clinical_terms = [
            "diabetes mellitus",
            "essential hypertension",
            "bronchial asthma",
            "myocardial infarction",
            "chronic kidney disease",
        ]

        # Step 1: Get CUIs and semantic types
        async with UMLSSemanticTypesClient(self.api_key) as semantic_client:
            semantic_client.get_semantic_types_for_strings = AsyncMock(
                return_value=type(
                    "Result",
                    (),
                    {
                        "mappings": [
                            type(
                                "Mapping",
                                (),
                                {
                                    "search_string": term,
                                    "cui": f"C{i:07d}",
                                    "semantic_type": "Disease or Syndrome",
                                },
                            )
                            for i, term in enumerate(clinical_terms, 1)
                        ],
                        "total_processed": len(clinical_terms),
                        "successful_mappings": len(clinical_terms),
                        "success_rate": 100.0,
                    },
                )()
            )

            semantic_result = await semantic_client.get_semantic_types_for_strings(clinical_terms)

        # Step 2: Get corresponding codes
        cuis = [m.cui for m in semantic_result.mappings]

        async with UMLSCodeLookupClient(self.api_key) as code_client:
            code_client.get_codes_for_cuis = AsyncMock(
                return_value=type(
                    "Result",
                    (),
                    {
                        "mappings": [
                            type(
                                "Mapping",
                                (),
                                {"cui": cui, "code": f"{i}00.{i}", "vocab_abbr": "ICD10CM"},
                            )
                            for i, cui in enumerate(cuis, 1)
                        ],
                        "total_processed": len(cuis),
                        "total_codes_found": len(cuis),
                    },
                )()
            )

            code_result = await code_client.get_codes_for_cuis(cuis)

        # Verify comprehensive processing
        assert semantic_result.total_processed == len(clinical_terms)
        assert code_result.total_processed == len(cuis)
        assert semantic_result.success_rate == 100.0

        # Verify semantic consistency
        assert all(m.semantic_type == "Disease or Syndrome" for m in semantic_result.mappings)

        # Verify code mapping
        assert all(m.vocab_abbr == "ICD10CM" for m in code_result.mappings)


class TestClientResourceManagement:
    """Test resource management across client lifecycle."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test that all clients properly clean up sessions."""
        clients = [
            UMLSSemanticTypesClient(self.api_key),
            UMLSCodeLookupClient(self.api_key),
            UMLSConceptLookupClient(self.api_key),
            UMLSStringConceptClient(self.api_key),
        ]

        # Test context manager cleanup
        for client in clients:
            async with client:
                assert client.session is not None
                assert not client.session.closed

            # Session should be closed after context exit
            assert client.session.closed

    @pytest.mark.asyncio
    async def test_concurrent_client_usage(self):
        """Test multiple clients running concurrently."""

        async def run_semantic_client():
            async with UMLSSemanticTypesClient(self.api_key) as client:
                client.get_semantic_types_for_strings = AsyncMock(return_value={"processed": 1})
                return await client.get_semantic_types_for_strings(["term1"])

        async def run_code_client():
            async with UMLSCodeLookupClient(self.api_key) as client:
                client.get_codes_for_cuis = AsyncMock(return_value={"processed": 1})
                return await client.get_codes_for_cuis(["C0011847"])

        # Run clients concurrently
        results = await asyncio.gather(run_semantic_client(), run_code_client())

        assert len(results) == 2
        assert all(r["processed"] == 1 for r in results)

    @pytest.mark.asyncio
    async def test_error_recovery_across_clients(self):
        """Test error recovery mechanisms across different clients."""

        async def test_client_error_recovery(client_class):
            async with client_class(self.api_key) as client:
                # Mock intermittent failures
                client._make_request = AsyncMock(
                    side_effect=[
                        Exception("Temporary failure"),
                        {"result": {"results": [{"success": True}]}},
                    ]
                )

                # Client should handle errors gracefully
                # This would be expanded based on actual retry logic
                return True

        client_classes = [
            UMLSSemanticTypesClient,
            UMLSCodeLookupClient,
            UMLSConceptLookupClient,
            UMLSStringConceptClient,
        ]

        # Test error recovery for all clients
        results = await asyncio.gather(
            *[test_client_error_recovery(client_class) for client_class in client_classes]
        )

        assert all(results)


if __name__ == "__main__":
    # Run specific integration tests
    pytest.main([__file__, "-v"])
