from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from knowledge_lookup.multi_source_annotator import (
    MultiSourceAnnotator,
    SourceAnnotation,
    AnnotationConfidence,
    ConceptAgreement,
    MultiSourceAnnotationResult
)
from knowledge_lookup.models import KnowledgeSource, LookupConfig, UnifiedConcept, ConceptType


class TestMultiSourceAnnotator:
    """Tests for MultiSourceAnnotator."""

    @pytest.fixture
    def annotator(self):
        """Create MultiSourceAnnotator instance with auto_initialize=False for CentralLookup."""
        with patch('knowledge_lookup.multi_source_annotator.CentralKnowledgeLookup') as mock_lookup_class:
            mock_lookup = MagicMock()
            mock_lookup.adapters = {}
            mock_lookup.close = AsyncMock() # Ensure close is awaitable
            mock_lookup_class.return_value = mock_lookup
            return MultiSourceAnnotator()

    def test_initialization(self):
        """Test MultiSourceAnnotator initialization."""
        with patch('knowledge_lookup.multi_source_annotator.CentralKnowledgeLookup') as mock_lookup_class:
            annotator = MultiSourceAnnotator()
            assert isinstance(annotator.config, LookupConfig)
            mock_lookup_class.assert_called_once_with(annotator.config)
            assert len(annotator.annotation_sources) > 0

    @pytest.mark.asyncio
    async def test_annotate_sentence_basic(self, annotator):
        """Test basic sentence annotation with mocked internal methods."""
        sentence = "test sentence"
        mock_source_ann = SourceAnnotation(
            source=KnowledgeSource.BIOPORTAL,
            concepts=[],
            surface_forms=[],
            positions=[],
            processing_time=0.1
        )
        
        with patch.object(annotator, '_get_source_annotations', AsyncMock(return_value=[mock_source_ann])), \
             patch.object(annotator, '_analyze_consensus', AsyncMock(return_value=[])), \
             patch.object(annotator, '_identify_discrepancies', return_value=[]), \
             patch.object(annotator, '_calculate_overall_confidence', return_value=0.5), \
             patch.object(annotator, '_generate_annotation_stats', return_value={}):
            
            result = await annotator.annotate_sentence(sentence)
            
            assert isinstance(result, MultiSourceAnnotationResult)
            assert result.sentence == sentence
            assert result.overall_confidence == 0.5
            assert result.source_annotations == [mock_source_ann]

    def test_calculate_string_similarity(self, annotator):
        """Test Levenshtein-based string similarity."""
        assert annotator._calculate_string_similarity("diabetes", "diabetes") == 1.0
        assert annotator._calculate_string_similarity("diabetes", "diabete") > 0.8
        assert annotator._calculate_string_similarity("diabetes", "cancer") < 0.3
        assert annotator._calculate_string_similarity("", "test") == 0.0
        assert annotator._calculate_string_similarity("test", "") == 0.0

    def test_are_concepts_similar(self, annotator):
        """Test concept similarity detection."""
        concept1 = UnifiedConcept(primary_id="ID1", primary_label="Diabetes")
        concept2 = UnifiedConcept(primary_id="ID1", primary_label="Mellitus") # Same ID
        concept3 = UnifiedConcept(primary_id="ID2", primary_label="Diabetes") # Same Label
        concept4 = UnifiedConcept(primary_id="ID3", primary_label="Cancer")   # Different
        
        assert annotator._are_concepts_similar(concept1, concept2) is True
        assert annotator._are_concepts_similar(concept1, concept3) is True
        assert annotator._are_concepts_similar(concept1, concept4) is False

    @pytest.mark.asyncio
    async def test_group_similar_concepts(self, annotator):
        """Test grouping of similar concepts across sources."""
        # Use unique IDs to ensure they are grouped correctly by ID similarity
        c1 = UnifiedConcept(primary_id="ID1", primary_label="Concept A")
        c2 = UnifiedConcept(primary_id="ID1", primary_label="Concept A")
        c3 = UnifiedConcept(primary_id="ID2", primary_label="Xylophone") # Distinct enough from "Concept A"
        
        source_anns = [
            SourceAnnotation(KnowledgeSource.OLS, [c1], ["A"], [{}], 0.1),
            SourceAnnotation(KnowledgeSource.BIOPORTAL, [c2, c3], ["A", "B"], [{}, {}], 0.1)
        ]
        
        groups = await annotator._group_similar_concepts(source_anns)
        # Should be 2 groups: {ID1 (OLS), ID1 (BIOPORTAL)}, {ID2 (BIOPORTAL)}
        assert len(groups) == 2
        # One group should have 2 concepts (c1 and c2), another 1 concept (c3)
        group_lens = sorted([len(g) for g in groups])
        assert group_lens == [1, 2]

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement(self, annotator):
        """Test agreement calculation for a group of concepts."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.9)
        group = [(c1, KnowledgeSource.OLS), (c1, KnowledgeSource.BIOPORTAL)]
        
        agreement = await annotator._calculate_concept_agreement(group, total_sources=2, majority_threshold=0.5)
        
        assert agreement.primary_concept == c1
        assert KnowledgeSource.OLS in agreement.agreeing_sources
        assert KnowledgeSource.BIOPORTAL in agreement.agreeing_sources
        assert agreement.confidence_level == AnnotationConfidence.HIGH
        assert agreement.consensus_score > 0.8

    def test_identify_discrepancies(self, annotator):
        """Test identification of discrepancies."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreement = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources={KnowledgeSource.BIOPORTAL},
            confidence_level=AnnotationConfidence.DISPUTED
        )
        
        source_ann = SourceAnnotation(KnowledgeSource.BIOPORTAL, [], [], [], 0.1, error="Timeout")
        
        discrepancies = annotator._identify_discrepancies([source_ann], [agreement])
        
        assert len(discrepancies) > 0
        types = [d["type"] for d in discrepancies]
        assert "single_source_concepts" in types
        assert "disputed_concepts" in types
        assert "source_errors" in types

    def test_calculate_overall_confidence(self, annotator):
        """Test overall confidence calculation."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreement1 = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources=set(),
            confidence_level=AnnotationConfidence.HIGH,
            consensus_score=0.9
        )
        
        conf = annotator._calculate_overall_confidence([agreement1])
        assert conf > 0.8
        
        assert annotator._calculate_overall_confidence([]) == 0.0

    def test_generate_annotation_stats(self, annotator):
        """Test generation of annotation statistics."""
        source_ann = SourceAnnotation(KnowledgeSource.OLS, [], [], [], 0.1)
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", concept_type=ConceptType.DISEASE)
        agreement = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources=set(),
            confidence_level=AnnotationConfidence.HIGH
        )
        
        stats = annotator._generate_annotation_stats([source_ann], [agreement])
        assert stats["total_sources"] == 1
        assert stats["total_consensus_concepts"] == 1
        assert stats["concept_type_distribution"]["disease"] == 1

    @pytest.mark.asyncio
    async def test_annotate_multiple_sentences(self, annotator):
        """Test batch annotation of multiple sentences."""
        sentences = ["S1", "S2"]
        mock_result = MultiSourceAnnotationResult("S", [], [], [], 0.5, 0.1, {})
        
        with patch.object(annotator, 'annotate_sentence', AsyncMock(return_value=mock_result)):
            results = await annotator.annotate_multiple_sentences(sentences, batch_delay=0.01)
            assert len(results) == 2
            assert results[0] == mock_result

    @pytest.mark.asyncio
    async def test_close(self, annotator):
        """Test close method cleans up central lookup."""
        await annotator.close()
        annotator.central_lookup.close.assert_called_once()

