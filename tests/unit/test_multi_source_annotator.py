from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.core.multi_source_annotator import (
    AnnotationConfidence,
    ConceptAgreement,
    MultiSourceAnnotationResult,
    MultiSourceAnnotator,
    SourceAnnotation,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept


class TestMultiSourceAnnotator:
    """Tests for MultiSourceAnnotator."""

    @pytest.fixture
    def annotator(self):
        """Create MultiSourceAnnotator instance."""
        with patch(
            "knowledge_lookup.core.multi_source_annotator.CentralKnowledgeLookup"
        ) as mock_lookup_class:
            mock_lookup = MagicMock()
            mock_lookup.adapters = {}
            mock_lookup.close = AsyncMock()
            mock_lookup_class.return_value = mock_lookup
            return MultiSourceAnnotator()

    def test_initialization(self):
        """Test MultiSourceAnnotator initialization."""
        with patch(
            "knowledge_lookup.core.multi_source_annotator.CentralKnowledgeLookup"
        ) as mock_lookup_class:
            annotator = MultiSourceAnnotator()
            assert isinstance(annotator.config, LookupConfig)
            mock_lookup_class.assert_called_once_with(annotator.config)
            assert len(annotator.annotation_sources) > 0

    def test_initialization_custom_config(self):
        """Test MultiSourceAnnotator initialization with custom config."""
        config = LookupConfig(max_results_per_source=50)
        with patch(
            "knowledge_lookup.core.multi_source_annotator.CentralKnowledgeLookup"
        ):
            annotator = MultiSourceAnnotator(config=config)
            assert annotator.config.max_results_per_source == 50

    @pytest.mark.asyncio
    async def test_annotate_sentence_basic(self, annotator):
        """Test basic sentence annotation with mocked internal methods."""
        sentence = "test sentence"
        mock_source_ann = SourceAnnotation(
            source=KnowledgeSource.BIOPORTAL,
            concepts=[],
            surface_forms=[],
            positions=[],
            processing_time=0.1,
        )

        with patch.object(
            annotator, "_get_source_annotations", AsyncMock(return_value=[mock_source_ann])
        ), patch.object(annotator, "_analyze_consensus", AsyncMock(return_value=[])), patch.object(
            annotator, "_identify_discrepancies", return_value=[]
        ), patch.object(
            annotator, "_calculate_overall_confidence", return_value=0.5
        ), patch.object(
            annotator, "_generate_annotation_stats", return_value={}
        ):
            result = await annotator.annotate_sentence(sentence)
            assert isinstance(result, MultiSourceAnnotationResult)
            assert result.sentence == sentence
            assert result.overall_confidence == 0.5
            assert result.source_annotations == [mock_source_ann]

    @pytest.mark.asyncio
    async def test_annotate_text(self, annotator):
        """Test annotate_text (the underlying method)."""
        sentence = "test text"
        mock_source_ann = SourceAnnotation(
            source=KnowledgeSource.OLS,
            concepts=[],
            surface_forms=[],
            positions=[],
            processing_time=0.1,
        )

        with patch.object(
            annotator, "_get_source_annotations", AsyncMock(return_value=[mock_source_ann])
        ), patch.object(annotator, "_analyze_consensus", AsyncMock(return_value=[])), patch.object(
            annotator, "_identify_discrepancies", return_value=[]
        ), patch.object(
            annotator, "_calculate_overall_confidence", return_value=0.6
        ), patch.object(
            annotator, "_generate_annotation_stats", return_value={"total_sources": 1}
        ):
            result = await annotator.annotate_text(sentence)
            assert result.sentence == sentence

    def test_get_consensus_annotations(self, annotator):
        """Test get_consensus_annotations accessor."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreement = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources=set(),
            confidence_level=AnnotationConfidence.HIGH,
            consensus_score=0.9,
        )
        result = MultiSourceAnnotationResult(
            sentence="test",
            source_annotations=[],
            consensus_concepts=[agreement],
            discrepancies=[],
            overall_confidence=0.9,
            processing_time=0.1,
            annotation_stats={},
        )
        consensus = annotator.get_consensus_annotations(result)
        assert len(consensus) == 1
        assert consensus[0] == agreement

    @pytest.mark.asyncio
    async def test_get_source_annotations(self, annotator):
        """Test _get_source_annotations processes results from all sources."""
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test")
        source_ann = SourceAnnotation(
            source=KnowledgeSource.OLS,
            concepts=[concept],
            surface_forms=["Test"],
            positions=[{}],
            processing_time=0.1,
        )

        with patch.object(
            annotator,
            "_annotate_with_source",
            AsyncMock(return_value=source_ann),
        ):
            annotations = await annotator._get_source_annotations(
                "test sentence", [KnowledgeSource.OLS]
            )
            assert len(annotations) == 1
            assert annotations[0].source == KnowledgeSource.OLS

    @pytest.mark.asyncio
    async def test_get_source_annotations_with_exception(self, annotator):
        """Test _get_source_annotations handles exceptions from gather."""
        with patch.object(
            annotator,
            "_annotate_with_source",
            AsyncMock(side_effect=Exception("API error")),
        ):
            annotations = await annotator._get_source_annotations(
                "test sentence", [KnowledgeSource.OLS]
            )
            assert len(annotations) == 1
            assert annotations[0].error is not None

    @pytest.mark.asyncio
    async def test_annotate_with_source_standard(self, annotator):
        """Test _annotate_with_source for a standard source."""
        concept = UnifiedConcept(primary_id="ID1", primary_label="Diabetes")
        adapter = MagicMock()
        adapter.search_concepts = AsyncMock(return_value=[concept])
        annotator.central_lookup.adapters = {KnowledgeSource.OLS: adapter}

        result = await annotator._annotate_with_source("diabetes", KnowledgeSource.OLS)
        assert isinstance(result, SourceAnnotation)
        assert result.source == KnowledgeSource.OLS
        assert len(result.concepts) == 1

    @pytest.mark.asyncio
    async def test_annotate_with_source_adds_adapter(self, annotator):
        """Test _annotate_with_source calls add_source if adapter missing."""
        adapter = MagicMock()
        adapter.search_concepts = AsyncMock(return_value=[])
        annotator.central_lookup.adapters = {}

        annotator.central_lookup.add_source = AsyncMock()
        annotator.central_lookup.adapters[KnowledgeSource.OLS] = adapter
        result = await annotator._annotate_with_source("test", KnowledgeSource.OLS)
        assert isinstance(result, SourceAnnotation)

    @pytest.mark.asyncio
    async def test_annotate_with_source_biolinker_with_annotate(self, annotator):
        """Test _annotate_with_source for BIOLINKER with annotate_sentence."""
        adapter = MagicMock()
        adapter.annotate_sentence = AsyncMock(
            return_value={
                "entities": [
                    {
                        "id": "ID1",
                        "label": "Diabetes",
                        "type": "disease",
                        "surface_form": "Diabetes",
                        "position": {"start": 0, "end": 8},
                        "confidence": 0.9,
                        "definition": "A disease",
                        "semantic_types": ["Disease"],
                    }
                ],
                "predicates": [],
            }
        )
        annotator.central_lookup.adapters = {KnowledgeSource.BIOLINKER: adapter}

        result = await annotator._annotate_with_source(
            "Diabetes is a disease", KnowledgeSource.BIOLINKER
        )
        assert len(result.concepts) == 1
        assert result.surface_forms == ["Diabetes"]

    @pytest.mark.asyncio
    async def test_annotate_with_source_biolinker_predicates(self, annotator):
        """Test _annotate_with_source for BIOLINKER with predicates."""
        adapter = MagicMock()
        adapter.annotate_sentence = AsyncMock(
            return_value={
                "entities": [],
                "predicates": [
                    {
                        "id": "P1",
                        "label": "treats",
                        "type": "predicate",
                        "surface_form": "treats",
                        "position": {"start": 10, "end": 16},
                        "confidence": 0.8,
                    }
                ],
            }
        )
        annotator.central_lookup.adapters = {KnowledgeSource.BIOLINKER: adapter}

        result = await annotator._annotate_with_source(
            "Drug treats disease", KnowledgeSource.BIOLINKER
        )
        assert len(result.concepts) == 1

    @pytest.mark.asyncio
    async def test_annotate_with_source_biolinker_fallback(self, annotator):
        """Test _annotate_with_source BIOLINKER fallback without annotate_sentence."""
        adapter = MagicMock()
        adapter.search_concepts = AsyncMock(
            return_value=[UnifiedConcept(primary_id="ID1", primary_label="Test")]
        )
        del adapter.annotate_sentence
        annotator.central_lookup.adapters = {KnowledgeSource.BIOLINKER: adapter}

        result = await annotator._annotate_with_source("test", KnowledgeSource.BIOLINKER)
        assert len(result.concepts) == 1

    @pytest.mark.asyncio
    async def test_annotate_with_source_exception(self, annotator):
        """Test _annotate_with_source handles exceptions."""
        adapter = MagicMock()
        adapter.search_concepts = AsyncMock(side_effect=Exception("API error"))
        annotator.central_lookup.adapters[KnowledgeSource.OLS] = adapter

        result = await annotator._annotate_with_source("test", KnowledgeSource.OLS)
        assert result.error is not None
        assert len(result.concepts) == 0

    @pytest.mark.asyncio
    async def test_entity_to_concept(self, annotator):
        """Test _entity_to_concept conversion."""
        entity = {
            "id": "HP:0000819",
            "label": "Diabetes mellitus",
            "type": "disease",
            "confidence": 0.9,
            "definition": "A metabolic disease",
            "semantic_types": ["Disease or Syndrome"],
        }
        concept = await annotator._entity_to_concept(entity, KnowledgeSource.OLS)
        assert concept is not None
        assert concept.primary_id == "HP:0000819"
        assert concept.primary_label == "Diabetes mellitus"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.confidence_score == 0.9
        assert concept.definitions == ["A metabolic disease"]

    @pytest.mark.asyncio
    async def test_entity_to_concept_minimal(self, annotator):
        """Test _entity_to_concept with minimal entity dict."""
        entity = {"id": "ID1", "label": "Test"}
        concept = await annotator._entity_to_concept(entity, KnowledgeSource.OLS)
        assert concept is not None
        assert concept.primary_id == "ID1"
        assert concept.concept_type == ConceptType.UNKNOWN

    @pytest.mark.asyncio
    async def test_entity_to_concept_gene_type(self, annotator):
        """Test _entity_to_concept maps gene type."""
        entity = {"id": "G1", "label": "BRCA1", "type": "gene"}
        concept = await annotator._entity_to_concept(entity, KnowledgeSource.OLS)
        assert concept.concept_type == ConceptType.GENE

    @pytest.mark.asyncio
    async def test_entity_to_concept_protein_type(self, annotator):
        """Test _entity_to_concept maps protein type."""
        entity = {"id": "P1", "label": "Insulin", "type": "protein"}
        concept = await annotator._entity_to_concept(entity, KnowledgeSource.OLS)
        assert concept.concept_type == ConceptType.PROTEIN

    @pytest.mark.asyncio
    async def test_entity_to_concept_drug_type(self, annotator):
        """Test _entity_to_concept maps drug type."""
        entity = {"id": "D1", "label": "Aspirin", "type": "drug"}
        concept = await annotator._entity_to_concept(entity, KnowledgeSource.OLS)
        assert concept.concept_type == ConceptType.DRUG

    @pytest.mark.asyncio
    async def test_entity_to_concept_no_definition(self, annotator):
        """Test _entity_to_concept with no definition."""
        entity = {"id": "ID1", "label": "Test", "type": ""}
        concept = await annotator._entity_to_concept(entity, KnowledgeSource.OLS)
        assert concept is not None
        assert concept.definitions == []

    @pytest.mark.asyncio
    async def test_entity_to_concept_exception(self, annotator):
        """Test _entity_to_concept returns None on error."""
        with patch(
            "knowledge_lookup.models.ConceptIdentifier",
            side_effect=Exception("fail"),
        ):
            result = await annotator._entity_to_concept(
                {"id": "X"}, KnowledgeSource.OLS
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_consensus(self, annotator):
        """Test _analyze_consensus full flow."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.9)
        c2 = UnifiedConcept(primary_id="ID2", primary_label="B", confidence_score=0.7)

        ann1 = SourceAnnotation(KnowledgeSource.OLS, [c1], ["A"], [{}], 0.1)
        ann2 = SourceAnnotation(KnowledgeSource.BIOPORTAL, [c2], ["B"], [{}], 0.1)

        result = await annotator._analyze_consensus(
            [ann1, ann2], enable_cross_reference=True, majority_vote_threshold=0.5
        )
        assert len(result) == 2
        assert result[0].consensus_score >= result[1].consensus_score

    def test_calculate_string_similarity(self, annotator):
        """Test Levenshtein-based string similarity."""
        assert annotator._calculate_string_similarity("diabetes", "diabetes") == 1.0
        assert annotator._calculate_string_similarity("diabetes", "diabete") > 0.8
        assert annotator._calculate_string_similarity("diabetes", "cancer") < 0.3
        assert annotator._calculate_string_similarity("", "test") == 0.0
        assert annotator._calculate_string_similarity("test", "") == 0.0
        assert annotator._calculate_string_similarity("", "") == 0.0

    def test_calculate_string_similarity_same(self, annotator):
        """Test string similarity with identical strings."""
        assert annotator._calculate_string_similarity("same", "same") == 1.0

    def test_calculate_string_similarity_different_lengths(self, annotator):
        """Test string similarity with different length strings."""
        sim = annotator._calculate_string_similarity("short", "much longer string")
        assert 0.0 <= sim <= 1.0

    def test_are_concepts_similar(self, annotator):
        """Test concept similarity detection."""
        concept1 = UnifiedConcept(primary_id="ID1", primary_label="Diabetes")
        concept2 = UnifiedConcept(primary_id="ID1", primary_label="Mellitus")
        concept3 = UnifiedConcept(primary_id="ID2", primary_label="Diabetes")
        concept4 = UnifiedConcept(primary_id="ID3", primary_label="Cancer")

        assert annotator._are_concepts_similar(concept1, concept2) is True
        assert annotator._are_concepts_similar(concept1, concept3) is True
        assert annotator._are_concepts_similar(concept1, concept4) is False

    def test_are_concepts_similar_by_synonym(self, annotator):
        """Test concept similarity via synonym matching."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="Diabetes")
        c2 = UnifiedConcept(
            primary_id="ID2",
            primary_label="Mellitus",
            synonyms=["diabetes"],
        )
        assert annotator._are_concepts_similar(c1, c2) is True

    def test_are_concepts_similar_no_match(self, annotator):
        """Test concept similarity with no match at all."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="Alpha")
        c2 = UnifiedConcept(primary_id="ID2", primary_label="Beta", synonyms=["gamma"])
        assert annotator._are_concepts_similar(c1, c2) is False

    @pytest.mark.asyncio
    async def test_group_similar_concepts(self, annotator):
        """Test grouping of similar concepts across sources."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="Concept A")
        c2 = UnifiedConcept(primary_id="ID1", primary_label="Concept A")
        c3 = UnifiedConcept(primary_id="ID2", primary_label="Xylophone")

        source_anns = [
            SourceAnnotation(KnowledgeSource.OLS, [c1], ["A"], [{}], 0.1),
            SourceAnnotation(KnowledgeSource.BIOPORTAL, [c2, c3], ["A", "B"], [{}, {}], 0.1),
        ]

        groups = await annotator._group_similar_concepts(source_anns)
        assert len(groups) == 2
        group_lens = sorted([len(g) for g in groups])
        assert group_lens == [1, 2]

    @pytest.mark.asyncio
    async def test_group_similar_concepts_empty(self, annotator):
        """Test grouping with no concepts."""
        source_anns = [
            SourceAnnotation(KnowledgeSource.OLS, [], [], [], 0.1),
        ]
        groups = await annotator._group_similar_concepts(source_anns)
        assert len(groups) == 0

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement(self, annotator):
        """Test agreement calculation for a group of concepts."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.9)
        group = [(c1, KnowledgeSource.OLS), (c1, KnowledgeSource.BIOPORTAL)]

        agreement = await annotator._calculate_concept_agreement(
            group, total_sources=2, majority_threshold=0.5
        )

        assert agreement.primary_concept == c1
        assert KnowledgeSource.OLS in agreement.agreeing_sources
        assert KnowledgeSource.BIOPORTAL in agreement.agreeing_sources
        assert agreement.confidence_level == AnnotationConfidence.HIGH
        assert agreement.consensus_score > 0.8

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement_empty(self, annotator):
        """Test agreement for empty group returns placeholder."""
        agreement = await annotator._calculate_concept_agreement(
            [], total_sources=3, majority_threshold=0.5
        )
        assert agreement.primary_concept.primary_id == "unknown"
        assert agreement.confidence_level == AnnotationConfidence.DISPUTED
        assert len(agreement.agreeing_sources) == 0

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement_medium(self, annotator):
        """Test agreement with medium confidence (60-79% agreement ratio)."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.8)
        group = [(c1, KnowledgeSource.OLS), (c1, KnowledgeSource.BIOPORTAL)]

        agreement = await annotator._calculate_concept_agreement(
            group, total_sources=3, majority_threshold=0.5
        )
        assert agreement.confidence_level == AnnotationConfidence.MEDIUM

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement_low(self, annotator):
        """Test agreement with low confidence (40-59% agreement ratio)."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.7)
        group = [(c1, KnowledgeSource.OLS)]

        agreement = await annotator._calculate_concept_agreement(
            group, total_sources=2, majority_threshold=0.5
        )
        assert agreement.confidence_level == AnnotationConfidence.LOW

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement_disputed(self, annotator):
        """Test agreement with disputed confidence (<40%)."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.5)
        group = [(c1, KnowledgeSource.OLS)]

        agreement = await annotator._calculate_concept_agreement(
            group, total_sources=10, majority_threshold=0.5
        )
        assert agreement.confidence_level == AnnotationConfidence.DISPUTED

    @pytest.mark.asyncio
    async def test_calculate_concept_agreement_alternatives(self, annotator):
        """Test agreement tracks alternative concepts."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", confidence_score=0.9)
        c2 = UnifiedConcept(primary_id="ID2", primary_label="B", confidence_score=0.6)
        group = [(c1, KnowledgeSource.OLS), (c2, KnowledgeSource.BIOPORTAL)]

        agreement = await annotator._calculate_concept_agreement(
            group, total_sources=2, majority_threshold=0.5
        )
        assert len(agreement.alternative_concepts) > 0

    def test_identify_discrepancies(self, annotator):
        """Test identification of discrepancies."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreement = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources={KnowledgeSource.BIOPORTAL},
            confidence_level=AnnotationConfidence.DISPUTED,
        )

        source_ann = SourceAnnotation(KnowledgeSource.BIOPORTAL, [], [], [], 0.1, error="Timeout")

        discrepancies = annotator._identify_discrepancies([source_ann], [agreement])

        assert len(discrepancies) > 0
        types = [d["type"] for d in discrepancies]
        assert "single_source_concepts" in types
        assert "disputed_concepts" in types
        assert "source_errors" in types

    def test_identify_discrepancies_none(self, annotator):
        """Test no discrepancies when all sources agree."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreement = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS, KnowledgeSource.BIOPORTAL},
            disagreeing_sources=set(),
            confidence_level=AnnotationConfidence.HIGH,
        )

        source_ann1 = SourceAnnotation(KnowledgeSource.OLS, [], [], [], 0.1)
        source_ann2 = SourceAnnotation(KnowledgeSource.BIOPORTAL, [], [], [], 0.1)

        discrepancies = annotator._identify_discrepancies(
            [source_ann1, source_ann2], [agreement]
        )
        assert len(discrepancies) == 0

    def test_calculate_overall_confidence(self, annotator):
        """Test overall confidence calculation."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreement1 = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources=set(),
            confidence_level=AnnotationConfidence.HIGH,
            consensus_score=0.9,
        )

        conf = annotator._calculate_overall_confidence([agreement1])
        assert conf > 0.8
        assert annotator._calculate_overall_confidence([]) == 0.0

    def test_calculate_overall_confidence_mixed(self, annotator):
        """Test overall confidence with mixed confidence levels."""
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A")
        agreements = [
            ConceptAgreement(
                primary_concept=c1,
                agreeing_sources=set(),
                disagreeing_sources=set(),
                confidence_level=AnnotationConfidence.HIGH,
                consensus_score=0.9,
            ),
            ConceptAgreement(
                primary_concept=c1,
                agreeing_sources=set(),
                disagreeing_sources=set(),
                confidence_level=AnnotationConfidence.LOW,
                consensus_score=0.3,
            ),
            ConceptAgreement(
                primary_concept=c1,
                agreeing_sources=set(),
                disagreeing_sources=set(),
                confidence_level=AnnotationConfidence.DISPUTED,
                consensus_score=0.1,
            ),
        ]
        conf = annotator._calculate_overall_confidence(agreements)
        assert 0.0 <= conf <= 1.0

    def test_generate_annotation_stats(self, annotator):
        """Test generation of annotation statistics."""
        source_ann = SourceAnnotation(KnowledgeSource.OLS, [], [], [], 0.1)
        c1 = UnifiedConcept(primary_id="ID1", primary_label="A", concept_type=ConceptType.DISEASE)
        agreement = ConceptAgreement(
            primary_concept=c1,
            agreeing_sources={KnowledgeSource.OLS},
            disagreeing_sources=set(),
            confidence_level=AnnotationConfidence.HIGH,
        )

        stats = annotator._generate_annotation_stats([source_ann], [agreement])
        assert stats["total_sources"] == 1
        assert stats["total_consensus_concepts"] == 1
        assert stats["concept_type_distribution"]["DISEASE"] == 1

    def test_generate_annotation_stats_empty(self, annotator):
        """Test stats generation with empty inputs."""
        stats = annotator._generate_annotation_stats([], [])
        assert stats["total_sources"] == 0
        assert stats["total_consensus_concepts"] == 0
        assert stats["fastest_source"] is None
        assert stats["slowest_source"] is None

    def test_generate_annotation_stats_with_errors(self, annotator):
        """Test stats generation with failed sources."""
        ann_ok = SourceAnnotation(KnowledgeSource.OLS, [], [], [], 0.1)
        ann_err = SourceAnnotation(
            KnowledgeSource.BIOPORTAL, [], [], [], 0.2, error="timeout"
        )
        stats = annotator._generate_annotation_stats([ann_ok, ann_err], [])
        assert stats["failed_sources"] == 1
        assert stats["successful_sources"] == 1

    @pytest.mark.asyncio
    async def test_annotate_multiple_sentences(self, annotator):
        """Test batch annotation of multiple sentences."""
        sentences = ["S1", "S2"]
        mock_result = MultiSourceAnnotationResult("S", [], [], [], 0.5, 0.1, {})

        with patch.object(annotator, "annotate_sentence", AsyncMock(return_value=mock_result)):
            results = await annotator.annotate_multiple_sentences(sentences, batch_delay=0.01)
            assert len(results) == 2
            assert results[0] == mock_result

    @pytest.mark.asyncio
    async def test_cross_reference_concepts(self, annotator):
        """Test _cross_reference_concepts returns input as-is."""
        groups = [[(UnifiedConcept(primary_id="ID1", primary_label="A"), KnowledgeSource.OLS)]]
        result = await annotator._cross_reference_concepts(groups)
        assert result == groups

    @pytest.mark.asyncio
    async def test_close(self, annotator):
        """Test close method cleans up central lookup."""
        await annotator.close()
        annotator.central_lookup.close.assert_called_once()
