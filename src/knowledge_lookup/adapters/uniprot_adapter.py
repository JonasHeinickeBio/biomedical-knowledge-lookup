"""
UniProt Knowledge Source Adapter

Integrates with UniProt for protein information lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class UniProtAdapter(KnowledgeSourceAdapter):
    """Adapter for UniProt."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.uniprot.org/uniprotkb"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.UNIPROT

    def is_available(self) -> bool:
        return True  # UniProt is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search UniProt for proteins."""
        try:
            url = f"{self.base_url}/search"
            params = {"query": query, "format": "json", "size": min(limit, 50)}

            data = await self._make_request(url, params)

            concepts = []
            if "results" in data:
                for result in data["results"]:
                    concept = self._convert_uniprot_result_to_concept(result)
                    if concept:
                        concepts.append(concept)

            logger.info(f"UniProt search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"UniProt search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed protein information from UniProt."""
        try:
            url = f"{self.base_url}/{concept_id}.json"
            data = await self._make_request(url)

            if data:
                concept = self._convert_uniprot_result_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get UniProt concept details for '{concept_id}': {e}")
            return None

    def _convert_uniprot_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert UniProt result to unified concept."""
        try:
            accession = result.get("primaryAccession", "")
            if not accession:
                return None

            # Extract label (common name or gene name)
            label = ""
            gene_names = []
            if "genes" in result and result["genes"]:
                gene_names = [gn.get("geneName", {}).get("value", "") for gn in result["genes"]]
                label = gene_names[0] if gene_names else ""

            protein_description = result.get("proteinDescription", {})
            recommended_name = (
                protein_description.get("recommendedName", {}).get("fullName", {}).get("value", "")
            )

            if not label:
                label = recommended_name or accession

            concept = UnifiedConcept(
                primary_id=accession, primary_label=label, concept_type=ConceptType.PROTEIN
            )

            # Add UniProt identifier
            concept.add_identifier(
                KnowledgeSource.UNIPROT,
                accession,
                label,
                f"https://www.uniprot.org/uniprotkb/{accession}",
            )

            # Add recommended name as synonym if different from label
            if recommended_name and recommended_name != label:
                concept.synonyms.append(recommended_name)

            # Add gene names as synonyms
            for gn in gene_names:
                if gn and gn != label:
                    concept.synonyms.append(gn)

            # Add definitions (comments)
            if "comments" in result:
                for comment in result["comments"]:
                    if comment.get("commentType") == "FUNCTION":
                        for text in comment.get("texts", []):
                            concept.definitions.append(text.get("value", ""))

            # Add organism as category
            organism = result.get("organism", {}).get("scientificName", "")
            if organism:
                concept.categories.append(f"Organism: {organism}")

            concept.confidence_score = 0.95
            concept.source_data[KnowledgeSource.UNIPROT] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting UniProt result: {e}")
            return None
