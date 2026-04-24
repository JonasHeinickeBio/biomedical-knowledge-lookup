"""
BioLinker AI Adapter

Integrates with TIB BioLinker AI API for entity and relation extraction.
"""

import asyncio
import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptIdentifier, ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class BioLinkerAdapter(KnowledgeSourceAdapter):
    """Adapter for TIB BioLinker AI API."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://labs.tib.eu/biolinkerai"
        self.process_endpoint = f"{self.base_url}/process-text"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.BIOLINKER

    def is_available(self) -> bool:
        return True  # BioLinker AI is publicly available

    async def _get_session(self):
        """Get or create aiohttp session with extended timeout for BioLinker AI."""
        if self.session is None or self.session.closed:
            import aiohttp

            # Use longer timeout specifically for BioLinker AI (can be slow)
            timeout = aiohttp.ClientTimeout(total=180)  # 2 minute total timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def search_concepts_with_depth(
        self, query: str, limit: int = 20, search_depth: int = 50
    ) -> list[UnifiedConcept]:
        """
        Extract entities and relations from text using BioLinker AI with custom search depth.

        Args:
            query: Input text to process
            limit: Maximum number of results to return
            search_depth: Number of concepts for BioLinker AI to consider (k parameter)

        Returns:
            List of unified concepts extracted from the text
        """
        try:
            # Prepare request payload with custom search depth
            payload = {"input_text": query, "k": search_depth}

            headers = {"Content-Type": "application/json"}

            # Make request to BioLinker AI API with extended timeout
            session = await self._get_session()

            logger.info(
                f"Calling BioLinker AI API for query: '{query}' with search depth: {search_depth}"
            )

            async with session.post(
                self.process_endpoint, json=payload, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    concepts = self._process_biolinker_response(data, limit)
                    logger.info(
                        f"BioLinker AI processed '{query}' and returned {len(concepts)} concepts"
                    )
                    return concepts
                else:
                    error_text = await response.text()
                    logger.error(f"BioLinker AI API error {response.status}: {error_text}")
                    return []

        except asyncio.TimeoutError:
            logger.warning(
                f"BioLinker AI API timeout for query: '{query}' (API may be slow or unavailable)"
            )
            return []
        except Exception as e:
            logger.error(f"Error querying BioLinker AI: {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Extract entities and relations from text using BioLinker AI.

        Args:
            query: Input text to process
            limit: Maximum number of results to return

        Returns:
            List of unified concepts extracted from the text
        """
        # Determine search depth - how many concepts BioLinker AI should consider
        # Default is 50, but can be adjusted based on query complexity
        search_depth = 50

        # For longer queries, consider more concepts
        if len(query.split()) > 10:
            search_depth = 100
        elif len(query.split()) < 3:
            search_depth = 25

        # Use the helper method with calculated search depth
        return await self.search_concepts_with_depth(query, limit, search_depth)

    async def annotate_sentence(self, sentence: str, search_depth: int = 50) -> dict[str, Any]:
        """
        Annotate a complete sentence, providing structured entity and relation extraction.

        Args:
            sentence: Complete sentence to annotate
            search_depth: Number of concepts for BioLinker AI to consider

        Returns:
            Dictionary with structured annotation results
        """
        try:
            # Get raw concepts
            concepts = await self.search_concepts_with_depth(
                sentence, limit=100, search_depth=search_depth
            )

            # Structure the results for sentence annotation
            annotation: dict[str, Any] = {
                "sentence": sentence,
                "search_depth": search_depth,
                "total_concepts": len(concepts),
                "entities": [],
                "predicates": [],
                "relations": [],
                "concept_map": {},
            }

            # Separate entities and predicates
            for concept in concepts:
                bl_data = concept.source_data.get(KnowledgeSource.BIOLINKER, {})
                category = bl_data.get("category", "unknown")
                surface_form = bl_data.get("surface_form", concept.primary_label)
                position = bl_data.get("text_position", {})

                concept_info = {
                    "surface_form": surface_form,
                    "label": concept.primary_label,
                    "id": concept.primary_id,
                    "type": concept.concept_type.value,
                    "semantic_types": concept.semantic_types,
                    "position": position,
                    "confidence": concept.confidence_score,
                    "definition": concept.definitions[0] if concept.definitions else None,
                }

                if category == "entities":
                    annotation["entities"].append(concept_info)
                elif category == "predicates":
                    annotation["predicates"].append(concept_info)

                # Add to concept map for easy lookup
                annotation["concept_map"][surface_form] = concept_info

            # Sort by position for better readability
            annotation["entities"].sort(key=lambda x: x["position"].get("start", 0))
            annotation["predicates"].sort(key=lambda x: x["position"].get("start", 0))

            # Try to identify potential relations based on proximity
            annotation["relations"] = self._identify_sentence_relations(
                annotation["entities"], annotation["predicates"]
            )

            logger.info(
                f"Sentence annotation completed: {len(annotation['entities'])} entities, "
                f"{len(annotation['predicates'])} predicates, {len(annotation['relations'])} relations"
            )

            return annotation

        except Exception as e:
            logger.error(f"Error annotating sentence: {e}")
            return {
                "sentence": sentence,
                "error": str(e),
                "entities": [],
                "predicates": [],
                "relations": [],
            }

    async def annotate_multiple_sentences(
        self, sentences: list[str], search_depth: int = 50
    ) -> list[dict[str, Any]]:
        """
        Annotate multiple sentences efficiently.

        Args:
            sentences: List of sentences to annotate
            search_depth: Number of concepts for BioLinker AI to consider

        Returns:
            List of annotation dictionaries
        """
        annotations = []

        for i, sentence in enumerate(sentences):
            logger.info(f"Annotating sentence {i+1}/{len(sentences)}")
            annotation = await self.annotate_sentence(sentence, search_depth)
            annotations.append(annotation)

            # Small delay between requests to be respectful to the API
            if i < len(sentences) - 1:
                await asyncio.sleep(0.5)

        return annotations

    def _identify_sentence_relations(
        self, entities: list[dict], predicates: list[dict]
    ) -> list[dict[str, Any]]:
        """
        Identify potential relations between entities and predicates in a sentence.

        Args:
            entities: List of entity annotations
            predicates: List of predicate annotations

        Returns:
            List of potential relations
        """
        relations = []

        # Simple relation identification based on position proximity
        for predicate in predicates:
            pred_start = predicate["position"].get("start", 0)
            pred_end = predicate["position"].get("end", 0)

            # Find entities close to this predicate
            nearby_entities = []
            for entity in entities:
                ent_start = entity["position"].get("start", 0)
                ent_end = entity["position"].get("end", 0)

                # Check if entity is within reasonable distance of predicate
                distance = min(abs(ent_start - pred_end), abs(pred_start - ent_end))
                if distance <= 50:  # Within 50 characters
                    nearby_entities.append({"entity": entity, "distance": distance})

            # Sort by proximity
            nearby_entities.sort(key=lambda x: x["distance"])

            # Create relations for close entities
            if len(nearby_entities) >= 2:
                # Try to identify subject-predicate-object patterns
                subject = nearby_entities[0]["entity"]
                object_entity = nearby_entities[1]["entity"]

                relation = {
                    "subject": {
                        "surface_form": subject["surface_form"],
                        "label": subject["label"],
                        "id": subject["id"],
                        "type": subject["type"],
                    },
                    "predicate": {
                        "surface_form": predicate["surface_form"],
                        "label": predicate["label"],
                        "id": predicate["id"],
                        "type": predicate["type"],
                    },
                    "object": {
                        "surface_form": object_entity["surface_form"],
                        "label": object_entity["label"],
                        "id": object_entity["id"],
                        "type": object_entity["type"],
                    },
                    "confidence": min(
                        subject["confidence"], predicate["confidence"], object_entity["confidence"]
                    ),
                }

                relations.append(relation)

        return relations

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get detailed information about a specific concept.

        Note: BioLinker AI doesn't provide direct concept lookup by ID,
        so this implementation is limited.

        Args:
            concept_id: Identifier of the concept

        Returns:
            Unified concept with details or None if not found
        """
        # BioLinker AI doesn't have a direct concept lookup endpoint
        # We could potentially search for the concept ID in text, but this would be limited
        logger.warning(f"BioLinker AI doesn't support direct concept lookup for ID: {concept_id}")
        return None

    def _process_biolinker_response(
        self, response_data: dict[str, Any], limit: int
    ) -> list[UnifiedConcept]:
        """
        Process BioLinker AI API response and convert to UnifiedConcept objects.

        Args:
            response_data: Raw response from BioLinker AI API
            limit: Maximum number of concepts to return

        Returns:
            List of UnifiedConcept objects
        """
        concepts: list[UnifiedConcept] = []

        if "results" not in response_data:
            logger.warning("No 'results' field in BioLinker AI response")
            return concepts

        # Process each result from BioLinker AI
        for result in response_data["results"]:
            try:
                concept = self._convert_biolinker_result_to_concept(result)
                if concept:
                    concepts.append(concept)

                if len(concepts) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Error processing BioLinker AI result: {e}")
                continue

        return concepts

    def _convert_biolinker_result_to_concept(
        self, result: dict[str, Any]
    ) -> UnifiedConcept | None:
        """
        Convert a single BioLinker AI result to a UnifiedConcept.

        Args:
            result: Single result from BioLinker AI API

        Returns:
            UnifiedConcept or None if conversion fails
        """
        try:
            best_candidate = result.get("best_candidate")
            if not best_candidate:
                return None

            # Extract basic information
            concept_id = best_candidate.get("id", "")
            label = best_candidate.get("label", "")
            description = best_candidate.get("description", "")
            semantic_types = best_candidate.get("type", [])

            if not concept_id or not label:
                return None

            # Handle semantic types (can be string or list)
            if isinstance(semantic_types, str):
                semantic_types = [semantic_types]
            elif not isinstance(semantic_types, list):
                semantic_types = []

            # Map semantic types to our ConceptType enum
            concept_type = self._map_semantic_type_to_concept_type(semantic_types)

            # Calculate confidence score based on various factors
            confidence_score = self._calculate_confidence_score(result, best_candidate)

            # Create concept identifier
            identifier = ConceptIdentifier(
                source=KnowledgeSource.BIOLINKER,
                identifier=concept_id,
                label=label,
                url=self._generate_concept_url(concept_id),
            )

            # Create UnifiedConcept
            concept = UnifiedConcept(
                primary_id=concept_id,
                primary_label=label,
                concept_type=concept_type,
                confidence_score=confidence_score,
                sources={KnowledgeSource.BIOLINKER},
                definitions=[description] if description else [],
                synonyms=[],  # BioLinker AI doesn't provide synonyms directly
                semantic_types=semantic_types,
                categories=[result.get("category", "")],
                identifiers=[identifier],
            )

            # Add surface form information as additional synonym
            surface_form = result.get("surface_form", "")
            if surface_form and surface_form != label:
                concept.synonyms.append(surface_form)

            # Store position and category information in source_data
            concept.source_data[KnowledgeSource.BIOLINKER] = {
                "surface_form": surface_form,
                "text_position": {"start": result.get("start", 0), "end": result.get("end", 0)},
                "category": result.get("category", ""),
                "biolinker_source": "TIB BioLinker AI",
            }

            return concept

        except Exception as e:
            logger.error(f"Error converting BioLinker AI result to concept: {e}")
            return None

    def _map_semantic_type_to_concept_type(self, semantic_types: list[str]) -> ConceptType:
        """
        Map BioLinker AI semantic types to our ConceptType enum.

        Args:
            semantic_types: List of semantic type strings from BioLinker AI

        Returns:
            ConceptType enum value
        """
        if not semantic_types:
            return ConceptType.UNKNOWN

        # Convert to lowercase for easier matching
        types_lower = [t.lower() for t in semantic_types]

        # Define mapping rules
        if any("disease" in t or "disorder" in t for t in types_lower):
            return ConceptType.DISEASE
        elif any("symptom" in t or "sign" in t for t in types_lower):
            return ConceptType.SYMPTOM
        elif any("drug" in t or "pharmacologic" in t or "substance" in t for t in types_lower):
            return ConceptType.DRUG
        elif any("gene" in t for t in types_lower):
            return ConceptType.GENE
        elif any("protein" in t or "peptide" in t or "amino acid" in t for t in types_lower):
            return ConceptType.PROTEIN
        elif any("pathway" in t for t in types_lower):
            return ConceptType.PATHWAY
        elif any("anatomy" in t or "body part" in t or "organ" in t for t in types_lower):
            return ConceptType.ANATOMY
        elif any("phenotype" in t for t in types_lower):
            return ConceptType.PHENOTYPE
        elif any("chemical" in t or "compound" in t or "organic" in t for t in types_lower):
            return ConceptType.CHEMICAL
        elif any("organism" in t or "species" in t for t in types_lower):
            return ConceptType.ORGANISM
        elif any("procedure" in t or "therapeutic" in t for t in types_lower):
            return ConceptType.PROCEDURE
        else:
            return ConceptType.UNKNOWN

    def _calculate_confidence_score(
        self, result: dict[str, Any], best_candidate: dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for a BioLinker AI result.

        Args:
            result: Full result object from BioLinker AI
            best_candidate: Best candidate from the result

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with base confidence
        confidence = 0.7

        # Boost confidence if there's a description
        if best_candidate.get("description"):
            confidence += 0.1

        # Boost confidence if there are semantic types
        semantic_types = best_candidate.get("type", [])
        if semantic_types:
            confidence += 0.1

        # Boost confidence for entities vs predicates (entities are usually more reliable)
        category = result.get("category", "")
        if category == "entities":
            confidence += 0.05

        # Boost confidence if surface form matches label exactly
        surface_form = result.get("surface_form", "").lower()
        label = best_candidate.get("label", "").lower()
        if surface_form == label:
            confidence += 0.05

        # Ensure confidence is within bounds
        return min(1.0, max(0.0, confidence))

    def _generate_concept_url(self, concept_id: str) -> str | None:
        """
        Generate a URL for the concept based on its ID.

        Args:
            concept_id: Concept identifier

        Returns:
            URL string or None if not applicable
        """
        # BioLinker AI uses UMLS concept IDs (C-codes)
        if concept_id.startswith("C") and concept_id[1:].isdigit():
            # Return UMLS browser URL
            return f"https://uts.nlm.nih.gov/uts/umls/concept/{concept_id}"

        return None

    async def close(self):
        """Close the adapter and cleanup resources."""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("BioLinker AI adapter closed")
