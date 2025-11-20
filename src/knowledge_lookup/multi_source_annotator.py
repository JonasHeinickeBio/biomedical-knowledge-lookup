"""
Multi-Source Annotation Platform

Advanced annotation system that uses multiple knowledge sources to annotate full sentences,
performs cross-referencing, majority voting, and identifies discrepancies.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Set, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum

from .central_lookup import CentralKnowledgeLookup
from .models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)


class AnnotationConfidence(Enum):
    """Confidence levels for annotations based on source agreement."""
    HIGH = "high"           # 80%+ sources agree
    MEDIUM = "medium"       # 60-79% sources agree
    LOW = "low"            # 40-59% sources agree
    DISPUTED = "disputed"   # <40% sources agree


@dataclass
class SourceAnnotation:
    """Annotation from a single knowledge source."""
    source: KnowledgeSource
    concepts: List[UnifiedConcept]
    surface_forms: List[str]
    positions: List[Dict[str, int]]
    processing_time: float
    error: Optional[str] = None


@dataclass
class ConceptAgreement:
    """Agreement analysis for a concept across sources."""
    primary_concept: UnifiedConcept
    agreeing_sources: Set[KnowledgeSource]
    disagreeing_sources: Set[KnowledgeSource]
    alternative_concepts: List[UnifiedConcept] = field(default_factory=list)
    confidence_level: AnnotationConfidence = AnnotationConfidence.LOW
    consensus_score: float = 0.0


@dataclass
class MultiSourceAnnotationResult:
    """Complete annotation result from multiple sources."""
    sentence: str
    source_annotations: List[SourceAnnotation]
    consensus_concepts: List[ConceptAgreement]
    discrepancies: List[Dict[str, Any]]
    overall_confidence: float
    processing_time: float
    annotation_stats: Dict[str, Any]


class MultiSourceAnnotator:
    """
    Advanced annotation platform using multiple knowledge sources with consensus analysis.
    """

    def __init__(self, config: Optional[LookupConfig] = None):
        """
        Initialize the multi-source annotator.

        Args:
            config: Configuration for knowledge lookup
        """
        self.config = config or LookupConfig()
        self.central_lookup = CentralKnowledgeLookup(self.config)

        # Define annotation sources (order matters for priority)
        self.annotation_sources = [
            KnowledgeSource.BIOLINKER,
            KnowledgeSource.OLS,
            KnowledgeSource.BIOPORTAL,
            KnowledgeSource.OXO,
            KnowledgeSource.UMLS
        ]

        # Similarity thresholds for concept matching
        self.similarity_threshold = 0.8
        self.surface_form_threshold = 0.9

        logger.info("Multi-source annotator initialized")

    async def annotate_sentence(
        self,
        sentence: str,
        sources: Optional[List[KnowledgeSource]] = None,
        enable_cross_reference: bool = True,
        majority_vote_threshold: float = 0.6
    ) -> MultiSourceAnnotationResult:
        """
        Annotate a sentence using multiple knowledge sources with consensus analysis.

        Args:
            sentence: Text to annotate
            sources: Specific sources to use (defaults to all available)
            enable_cross_reference: Whether to perform cross-referencing
            majority_vote_threshold: Minimum agreement for consensus

        Returns:
            Complete annotation result with consensus and discrepancies
        """
        start_time = asyncio.get_event_loop().time()

        logger.info(f"Starting multi-source annotation for: '{sentence[:50]}...'")

        # Use specified sources or defaults
        if sources is None:
            sources = self.annotation_sources

        # Get annotations from each source
        source_annotations = await self._get_source_annotations(sentence, sources)

        # Perform consensus analysis
        consensus_concepts = await self._analyze_consensus(
            source_annotations,
            enable_cross_reference,
            majority_vote_threshold
        )

        # Identify discrepancies
        discrepancies = self._identify_discrepancies(source_annotations, consensus_concepts)

        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(consensus_concepts)

        # Generate statistics
        stats = self._generate_annotation_stats(source_annotations, consensus_concepts)

        processing_time = asyncio.get_event_loop().time() - start_time

        result = MultiSourceAnnotationResult(
            sentence=sentence,
            source_annotations=source_annotations,
            consensus_concepts=consensus_concepts,
            discrepancies=discrepancies,
            overall_confidence=overall_confidence,
            processing_time=processing_time,
            annotation_stats=stats
        )

        logger.info(f"Multi-source annotation completed in {processing_time:.2f}s: "
                   f"{len(consensus_concepts)} consensus concepts, "
                   f"{len(discrepancies)} discrepancies")

        return result

    async def annotate_multiple_sentences(
        self,
        sentences: List[str],
        sources: Optional[List[KnowledgeSource]] = None,
        enable_cross_reference: bool = True,
        majority_vote_threshold: float = 0.6,
        batch_delay: float = 0.5
    ) -> List[MultiSourceAnnotationResult]:
        """
        Annotate multiple sentences with batch processing.

        Args:
            sentences: List of sentences to annotate
            sources: Specific sources to use
            enable_cross_reference: Whether to perform cross-referencing
            majority_vote_threshold: Minimum agreement for consensus
            batch_delay: Delay between batches to respect API limits

        Returns:
            List of annotation results
        """
        results = []

        for i, sentence in enumerate(sentences):
            logger.info(f"Annotating sentence {i+1}/{len(sentences)}")

            result = await self.annotate_sentence(
                sentence, sources, enable_cross_reference, majority_vote_threshold
            )
            results.append(result)

            # Add delay between sentences to respect API limits
            if i < len(sentences) - 1:
                await asyncio.sleep(batch_delay)

        return results

    async def _get_source_annotations(
        self,
        sentence: str,
        sources: List[KnowledgeSource]
    ) -> List[SourceAnnotation]:
        """Get annotations from all specified sources."""
        annotations = []

        # Process sources concurrently where possible
        tasks = []
        for source in sources:
            task = self._annotate_with_source(sentence, source)
            tasks.append(task)

        # Wait for all annotations to complete
        source_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for source, result in zip(sources, source_results):
            if isinstance(result, Exception):
                logger.error(f"Error annotating with {source.value}: {result}")
                annotations.append(SourceAnnotation(
                    source=source,
                    concepts=[],
                    surface_forms=[],
                    positions=[],
                    processing_time=0.0,
                    error=str(result)
                ))
            else:
                annotations.append(result)

        return annotations

    async def _annotate_with_source(
        self,
        sentence: str,
        source: KnowledgeSource
    ) -> SourceAnnotation:
        """Annotate sentence with a specific source."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Get adapter for the source
            if source not in self.central_lookup.adapters:
                await self.central_lookup.add_source(source)

            adapter = self.central_lookup.adapters[source]

            # Use specialized annotation methods if available
            if source == KnowledgeSource.BIOLINKER:
                # Check if adapter has sentence annotation method
                if hasattr(adapter, 'annotate_sentence'):
                    # BioLinker has sentence annotation
                    result = await getattr(adapter, 'annotate_sentence')(sentence)
                    concepts = []
                    surface_forms = []
                    positions = []

                    # Extract concepts from structured result
                    for entity in result.get('entities', []):
                        # Convert back to UnifiedConcept for consistency
                        concept = await self._entity_to_concept(entity, source)
                        if concept:
                            concepts.append(concept)
                            surface_forms.append(entity.get('surface_form', ''))
                            positions.append(entity.get('position', {}))

                    for predicate in result.get('predicates', []):
                        concept = await self._entity_to_concept(predicate, source)
                        if concept:
                            concepts.append(concept)
                            surface_forms.append(predicate.get('surface_form', ''))
                            positions.append(predicate.get('position', {}))
                else:
                    # Fallback to standard search
                    concepts = await adapter.search_concepts(sentence, limit=50)
                    surface_forms = [concept.primary_label for concept in concepts]
                    positions = [{}] * len(concepts)

            else:
                # Standard concept search
                concepts = await adapter.search_concepts(sentence, limit=50)
                surface_forms = [concept.primary_label for concept in concepts]
                positions = [{}] * len(concepts)  # No position info for standard search

            processing_time = asyncio.get_event_loop().time() - start_time

            return SourceAnnotation(
                source=source,
                concepts=concepts,
                surface_forms=surface_forms,
                positions=positions,
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Error annotating with {source.value}: {e}")

            return SourceAnnotation(
                source=source,
                concepts=[],
                surface_forms=[],
                positions=[],
                processing_time=processing_time,
                error=str(e)
            )

    async def _entity_to_concept(self, entity: Dict[str, Any], source: KnowledgeSource) -> Optional[UnifiedConcept]:
        """Convert entity dict back to UnifiedConcept."""
        try:
            from .models import ConceptIdentifier

            # Create identifier
            identifier = ConceptIdentifier(
                source=source,
                identifier=entity.get('id', ''),
                label=entity.get('label', ''),
                url=None
            )

            # Map type
            concept_type = ConceptType.UNKNOWN
            type_str = entity.get('type', '').lower()
            for ct in ConceptType:
                if ct.value.lower() in type_str:
                    concept_type = ct
                    break

            concept = UnifiedConcept(
                primary_id=entity.get('id', ''),
                primary_label=entity.get('label', ''),
                concept_type=concept_type,
                confidence_score=entity.get('confidence', 0.5),
                sources={source},
                definitions=[entity.get('definition', '')] if entity.get('definition') else [],
                synonyms=[],
                semantic_types=entity.get('semantic_types', []),
                categories=[],
                identifiers=[identifier]
            )

            return concept

        except Exception as e:
            logger.warning(f"Failed to convert entity to concept: {e}")
            return None

    async def _analyze_consensus(
        self,
        source_annotations: List[SourceAnnotation],
        enable_cross_reference: bool,
        majority_vote_threshold: float
    ) -> List[ConceptAgreement]:
        """Analyze consensus across sources."""

        # Group concepts by similarity
        concept_groups = await self._group_similar_concepts(source_annotations)

        # Perform cross-referencing if enabled
        if enable_cross_reference:
            concept_groups = await self._cross_reference_concepts(concept_groups)

        # Calculate consensus for each group
        consensus_concepts = []

        for group in concept_groups:
            agreement = await self._calculate_concept_agreement(
                group, len(source_annotations), majority_vote_threshold
            )
            consensus_concepts.append(agreement)

        # Sort by consensus score
        consensus_concepts.sort(key=lambda x: x.consensus_score, reverse=True)

        return consensus_concepts

    async def _group_similar_concepts(
        self,
        source_annotations: List[SourceAnnotation]
    ) -> List[List[Tuple[UnifiedConcept, KnowledgeSource]]]:
        """Group similar concepts across sources."""
        all_concepts = []

        # Collect all concepts with their sources
        for annotation in source_annotations:
            for concept in annotation.concepts:
                all_concepts.append((concept, annotation.source))

        # Group similar concepts
        groups = []
        used_concepts = set()

        for i, (concept, source) in enumerate(all_concepts):
            if i in used_concepts:
                continue

            # Start new group
            group = [(concept, source)]
            used_concepts.add(i)

            # Find similar concepts
            for j, (other_concept, other_source) in enumerate(all_concepts[i+1:], i+1):
                if j in used_concepts:
                    continue

                if self._are_concepts_similar(concept, other_concept):
                    group.append((other_concept, other_source))
                    used_concepts.add(j)

            groups.append(group)

        return groups

    def _are_concepts_similar(self, concept1: UnifiedConcept, concept2: UnifiedConcept) -> bool:
        """Check if two concepts are similar enough to be considered the same."""

        # Exact ID match
        if concept1.primary_id == concept2.primary_id and concept1.primary_id:
            return True

        # Label similarity
        label_sim = self._calculate_string_similarity(
            concept1.primary_label.lower(),
            concept2.primary_label.lower()
        )

        if label_sim >= self.similarity_threshold:
            return True

        # Check synonyms
        all_labels1 = [concept1.primary_label] + concept1.synonyms
        all_labels2 = [concept2.primary_label] + concept2.synonyms

        for label1 in all_labels1:
            for label2 in all_labels2:
                sim = self._calculate_string_similarity(label1.lower(), label2.lower())
                if sim >= self.similarity_threshold:
                    return True

        return False

    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using Levenshtein distance."""
        if not str1 or not str2:
            return 0.0

        if str1 == str2:
            return 1.0

        # Simple implementation of normalized Levenshtein distance
        len1, len2 = len(str1), len(str2)
        if len1 == 0:
            return 0.0
        if len2 == 0:
            return 0.0

        # Create matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        # Initialize first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j

        # Fill matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if str1[i-1] == str2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )

        # Calculate similarity
        max_len = max(len1, len2)
        distance = matrix[len1][len2]
        similarity = 1.0 - (distance / max_len)

        return max(0.0, similarity)

    async def _cross_reference_concepts(
        self,
        concept_groups: List[List[Tuple[UnifiedConcept, KnowledgeSource]]]
    ) -> List[List[Tuple[UnifiedConcept, KnowledgeSource]]]:
        """Cross-reference concepts using central lookup."""

        # For now, return as-is. Could implement cross-referencing logic here
        # This would involve looking up concepts in other sources to find mappings
        return concept_groups

    async def _calculate_concept_agreement(
        self,
        concept_group: List[Tuple[UnifiedConcept, KnowledgeSource]],
        total_sources: int,
        majority_threshold: float
    ) -> ConceptAgreement:
        """Calculate agreement for a concept group."""

        if not concept_group:
            # Create a placeholder concept for empty groups
            from .models import ConceptIdentifier
            placeholder_concept = UnifiedConcept(
                primary_id="unknown",
                primary_label="Unknown",
                concept_type=ConceptType.UNKNOWN,
                confidence_score=0.0,
                sources=set(),
                definitions=[],
                synonyms=[],
                semantic_types=[],
                categories=[],
                identifiers=[]
            )

            return ConceptAgreement(
                primary_concept=placeholder_concept,
                agreeing_sources=set(),
                disagreeing_sources=set(),
                confidence_level=AnnotationConfidence.DISPUTED
            )

        # Select primary concept (highest confidence or most common)
        concept_scores: Dict[Tuple[str, ConceptType], float] = defaultdict(float)
        concept_map = {}

        for concept, source in concept_group:
            key = (concept.primary_label.lower(), concept.concept_type)
            concept_scores[key] += concept.confidence_score
            if key not in concept_map or concept.confidence_score > concept_map[key][0].confidence_score:
                concept_map[key] = (concept, source)

        # Get the best concept (highest combined score)
        best_key = max(concept_scores.keys(), key=lambda k: concept_scores[k])
        primary_concept, _ = concept_map[best_key]

        # Calculate agreement
        agreeing_sources = {source for _, source in concept_group}
        all_sources = set(KnowledgeSource)  # Could be more specific
        disagreeing_sources = all_sources - agreeing_sources

        # Calculate consensus score
        agreement_ratio = len(agreeing_sources) / total_sources
        consensus_score = agreement_ratio * primary_concept.confidence_score

        # Determine confidence level
        if agreement_ratio >= 0.8:
            confidence_level = AnnotationConfidence.HIGH
        elif agreement_ratio >= 0.6:
            confidence_level = AnnotationConfidence.MEDIUM
        elif agreement_ratio >= 0.4:
            confidence_level = AnnotationConfidence.LOW
        else:
            confidence_level = AnnotationConfidence.DISPUTED

        # Get alternative concepts
        alternative_concepts = []
        for concept, source in concept_group:
            if concept != primary_concept:
                alternative_concepts.append(concept)

        return ConceptAgreement(
            primary_concept=primary_concept,
            agreeing_sources=agreeing_sources,
            disagreeing_sources=disagreeing_sources,
            alternative_concepts=alternative_concepts,
            confidence_level=confidence_level,
            consensus_score=consensus_score
        )

    def _identify_discrepancies(
        self,
        source_annotations: List[SourceAnnotation],
        consensus_concepts: List[ConceptAgreement]
    ) -> List[Dict[str, Any]]:
        """Identify discrepancies between sources."""
        discrepancies = []

        # Find concepts that only appear in one source
        single_source_concepts = []
        for consensus in consensus_concepts:
            if len(consensus.agreeing_sources) == 1:
                single_source_concepts.append(consensus)

        if single_source_concepts:
            discrepancies.append({
                "type": "single_source_concepts",
                "description": "Concepts identified by only one source",
                "count": len(single_source_concepts),
                "concepts": [c.primary_concept.primary_label for c in single_source_concepts],
                "sources": [list(c.agreeing_sources)[0].value for c in single_source_concepts]
            })

        # Find disputed concepts
        disputed_concepts = [c for c in consensus_concepts
                           if c.confidence_level == AnnotationConfidence.DISPUTED]

        if disputed_concepts:
            discrepancies.append({
                "type": "disputed_concepts",
                "description": "Concepts with low source agreement",
                "count": len(disputed_concepts),
                "concepts": [c.primary_concept.primary_label for c in disputed_concepts]
            })

        # Find sources with errors
        error_sources = [ann for ann in source_annotations if ann.error]

        if error_sources:
            discrepancies.append({
                "type": "source_errors",
                "description": "Sources that failed to process",
                "count": len(error_sources),
                "sources": [ann.source.value for ann in error_sources],
                "errors": [ann.error for ann in error_sources]
            })

        return discrepancies

    def _calculate_overall_confidence(self, consensus_concepts: List[ConceptAgreement]) -> float:
        """Calculate overall confidence score for the annotation."""
        if not consensus_concepts:
            return 0.0

        # Weight by consensus score
        total_score = sum(c.consensus_score for c in consensus_concepts)
        avg_score = total_score / len(consensus_concepts)

        # Adjust based on confidence distribution
        high_conf = sum(1 for c in consensus_concepts if c.confidence_level == AnnotationConfidence.HIGH)
        medium_conf = sum(1 for c in consensus_concepts if c.confidence_level == AnnotationConfidence.MEDIUM)
        low_conf = sum(1 for c in consensus_concepts if c.confidence_level == AnnotationConfidence.LOW)
        disputed = sum(1 for c in consensus_concepts if c.confidence_level == AnnotationConfidence.DISPUTED)

        total = len(consensus_concepts)
        confidence_score = (high_conf * 1.0 + medium_conf * 0.7 + low_conf * 0.4 + disputed * 0.1) / total

        # Combine average consensus score with confidence distribution
        overall_confidence = (avg_score + confidence_score) / 2

        return min(1.0, max(0.0, overall_confidence))

    def _generate_annotation_stats(
        self,
        source_annotations: List[SourceAnnotation],
        consensus_concepts: List[ConceptAgreement]
    ) -> Dict[str, Any]:
        """Generate statistics about the annotation process."""

        successful_sources = [ann for ann in source_annotations if not ann.error]
        failed_sources = [ann for ann in source_annotations if ann.error]

        confidence_dist = Counter()
        for concept in consensus_concepts:
            confidence_dist[concept.confidence_level.value] += 1

        concept_types = Counter()
        for concept in consensus_concepts:
            concept_types[concept.primary_concept.concept_type.value] += 1

        source_concept_counts = {}
        for ann in source_annotations:
            source_concept_counts[ann.source.value] = len(ann.concepts)

        stats = {
            "total_sources": len(source_annotations),
            "successful_sources": len(successful_sources),
            "failed_sources": len(failed_sources),
            "total_consensus_concepts": len(consensus_concepts),
            "confidence_distribution": dict(confidence_dist),
            "concept_type_distribution": dict(concept_types),
            "source_concept_counts": source_concept_counts,
            "average_processing_time": sum(ann.processing_time for ann in source_annotations) / len(source_annotations) if source_annotations else 0,
            "fastest_source": min(successful_sources, key=lambda x: x.processing_time).source.value if successful_sources else None,
            "slowest_source": max(successful_sources, key=lambda x: x.processing_time).source.value if successful_sources else None
        }

        return stats

    async def close(self):
        """Close all adapters and cleanup resources."""
        await self.central_lookup.close()
        logger.info("Multi-source annotator closed")
