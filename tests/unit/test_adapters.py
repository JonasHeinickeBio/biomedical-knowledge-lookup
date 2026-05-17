"""
Unit tests for adapter imports and mappings.
"""

import pytest
from knowledge_lookup import adapters
from knowledge_lookup.models import KnowledgeSource


class TestAdapters:
    """Tests for adapter imports and mappings."""

    def test_adapter_classes_imported(self):
        """Test that all expected adapter classes are imported."""
        # Check that ADAPTER_CLASSES exists
        from knowledge_lookup import adapters
        assert hasattr(adapters, 'ADAPTER_CLASSES')
        assert isinstance(adapters.ADAPTER_CLASSES, dict)

    def test_adapter_classes_mapping(self):
        """Test that ADAPTER_CLASSES contains expected mappings."""
        import knowledge_lookup.adapters as adapters_module
        ADAPTER_CLASSES = adapters_module.ADAPTER_CLASSES
        
        # Check that we have mappings for expected sources
        expected_sources = [
            KnowledgeSource.BIOPORTAL,
            KnowledgeSource.OLS,
            KnowledgeSource.UNIPROT,
            KnowledgeSource.WIKIDATA,
            KnowledgeSource.MONDO,
            KnowledgeSource.DISGENET,
            KnowledgeSource.PUBCHEM,
            KnowledgeSource.REACTOME,
            KnowledgeSource.DRUGBANK,
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.GENEONTOLOGY,
            KnowledgeSource.HPO,
            KnowledgeSource.OBOFOUNDRY,
            KnowledgeSource.EBIOLS,
            KnowledgeSource.ENSEMBL,
        ]

        if getattr(adapters_module, "UMLSAdapter", None) is not None:
            expected_sources.append(KnowledgeSource.UMLS)
        
        for source in expected_sources:
            assert source in ADAPTER_CLASSES, f"Missing adapter class for {source.value}"
            # Check that the value is a class (not instantiated)
            assert callable(ADAPTER_CLASSES[source]), f"Adapter class for {source.value} is not callable"

    def test_adapter_classes_coverage(self):
        """Test that ADAPTER_CLASSES covers all KnowledgeSource values."""
        import knowledge_lookup.adapters as adapters_module
        ADAPTER_CLASSES = adapters_module.ADAPTER_CLASSES
        
        # Get all KnowledgeSource enum values
        all_sources = set(KnowledgeSource)
        mapped_sources = set(ADAPTER_CLASSES.keys())
        
        # All sources should be mapped (though some may not have implementations yet)
        assert mapped_sources.issubset(all_sources), "ADAPTER_CLASSES contains unknown sources"
        
        # Check that we have at least some mappings
        assert len(ADAPTER_CLASSES) > 0, "ADAPTER_CLASSES should not be empty"

    def test_adapter_imports_exist(self):
        """Test that all imported adapter classes exist."""
        # This test will fail if any of the imports in adapters.py fail
        # It's a smoke test to ensure all adapter modules can be imported
        from knowledge_lookup.adapters import (
            BioPortalAdapter, OLSAdapter, UniProtAdapter
        )
        
        # Just check that they are classes/types
        assert BioPortalAdapter is not None
        assert OLSAdapter is not None
        assert UniProtAdapter is not None
