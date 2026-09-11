"""
Human Phenotype Ontology (HPO) Adapter

Integrates with HPO for phenotype and clinical finding lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class HPOAdapter(KnowledgeSourceAdapter):
    """Adapter for Human Phenotype Ontology."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        # HPO's public API moved from hpo.jax.org/api/ontological to ontology.jax.org/api/hp
        self.base_url = "https://ontology.jax.org/api/hp"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.HPO

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search HPO for phenotypes."""
        try:
            url = f"{self.base_url}/search"
            params = {"q": query, "limit": min(limit, 100)}

            data = await self._make_request(url, params)

            concepts = []
            if isinstance(data, dict) and "terms" in data:
                for term in data["terms"][:limit]:
                    concept = self._convert_hpo_result_to_concept(term)
                    if concept:
                        concepts.append(concept)

            logger.info(f"HPO search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"HPO search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed phenotype information from HPO."""
        try:
            # concept_id should be an HPO ID (e.g., HP:0000118)
            url = f"{self.base_url}/terms/{concept_id}"
            data = await self._make_request(url)

            # The new API returns the term object directly (older API wrapped it
            # in {"details": ...}).
            term = data.get("details", data) if isinstance(data, dict) else None
            if term and term.get("id"):
                return self._convert_hpo_details_to_concept(term)

            return None

        except Exception as e:
            logger.error(f"Failed to get HPO concept details for '{concept_id}': {e}")
            return None

    def _convert_hpo_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert HPO API search result to unified concept."""
        try:
            hpo_id = result.get("id", "")
            label = result.get("name", "")

            if not hpo_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=hpo_id, primary_label=label, concept_type=ConceptType.PHENOTYPE
            )

            concept.add_identifier(
                KnowledgeSource.HPO, hpo_id, label, f"https://hpo.jax.org/browse/term/{hpo_id}"
            )
            self._add_xrefs(concept, result.get("xrefs"))

            if result.get("synonyms") and concept.synonyms is not None:
                concept.synonyms.extend(result["synonyms"])
            if result.get("definition") and concept.definitions is not None:
                concept.definitions.append(result["definition"])

            concept.confidence_score = 0.95
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.HPO] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting HPO result: {e}")
            return None

    def _convert_hpo_details_to_concept(self, details: dict[str, Any]) -> UnifiedConcept | None:
        """Convert HPO API detailed concept to unified concept."""
        try:
            hpo_id = details.get("id", "")
            label = details.get("name", "")

            if not hpo_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=hpo_id, primary_label=label, concept_type=ConceptType.PHENOTYPE
            )

            concept.add_identifier(
                KnowledgeSource.HPO, hpo_id, label, f"https://hpo.jax.org/browse/term/{hpo_id}"
            )
            self._add_xrefs(concept, details.get("xrefs"))

            if details.get("synonyms") and concept.synonyms is not None:
                concept.synonyms.extend(details["synonyms"])
            if details.get("definition") and concept.definitions is not None:
                concept.definitions.append(details["definition"])

            concept.confidence_score = 1.0
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.HPO] = details

            return concept

        except Exception as e:
            logger.error(f"Error converting HPO details: {e}")
            return None

    @staticmethod
    def _add_xrefs(concept: UnifiedConcept, xrefs: Any) -> None:
        """Record HPO cross-references we have a source for (e.g. ``UMLS:C0015672``)."""
        if not isinstance(xrefs, list):
            return
        for xref in xrefs:
            if isinstance(xref, str) and xref.startswith("UMLS:"):
                try:
                    concept.add_identifier(KnowledgeSource.UMLS, xref, concept.primary_label, None)
                except Exception:  # noqa: BLE001 - best-effort identifier bookkeeping
                    pass
