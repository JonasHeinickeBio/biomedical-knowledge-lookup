"""
BioPortal Knowledge Source Adapter

Integrates with NCBI BioPortal for ontology-based concept lookup.
"""

import logging
import os
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class BioPortalAdapter(KnowledgeSourceAdapter):
    """Adapter for NCBI BioPortal."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://data.bioontology.org"
        # Try to get API key from config first, then from environment
        self.api_key = config.get_api_key("bioportal") or os.getenv("BIOPORTAL_API_KEY")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.BIOPORTAL

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search BioPortal for concepts."""
        if not self.api_key:
            logger.warning("BioPortal API key not available")
            return []

        try:
            url = f"{self.base_url}/search"
            params = {
                "q": query,
                "pagesize": min(limit, 50),
                "apikey": self.api_key,
                "format": "json",
            }

            data = await self._make_request(url, params)

            concepts = []
            if "collection" in data:
                for item in data["collection"][:limit]:
                    concept = self._convert_bioportal_result_to_concept(item)
                    if concept:
                        concepts.append(concept)

            logger.info(f"BioPortal search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"BioPortal search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed concept information from BioPortal."""
        if not self.api_key:
            return None

        try:
            # Extract ontology and concept ID from full URI
            if "/" in concept_id:
                parts = concept_id.split("/")
                if len(parts) >= 2:
                    ontology = parts[-2]
                    concept_uri = concept_id
                else:
                    return None
            else:
                return None

            url = f"{self.base_url}/ontologies/{ontology}/classes/{concept_uri}"
            params = {"apikey": self.api_key, "format": "json"}

            data = await self._make_request(url, params)
            concept = self._convert_bioportal_concept_to_unified(data)
            return concept

        except Exception as e:
            logger.error(f"Failed to get BioPortal concept details for '{concept_id}': {e}")
            return None

    def _convert_bioportal_result_to_concept(
        self, result: dict[str, Any]
    ) -> UnifiedConcept | None:
        """Convert BioPortal search result to unified concept."""
        try:
            concept_id = result.get("@id", "")
            label = result.get("prefLabel", "")

            if not concept_id or not label:
                return None

            # Determine concept type from ontology
            ontology = result.get("links", {}).get("ontology", "")
            concept_type = self._determine_concept_type_from_ontology(ontology)

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=concept_type
            )

            # Add BioPortal identifier
            concept.add_identifier(
                KnowledgeSource.BIOPORTAL, concept_id, label, result.get("@id", "")
            )

            # Add synonyms
            if "synonym" in result:
                synonyms = result["synonym"]
                if isinstance(synonyms, list):
                    if concept.synonyms is not None:
                        concept.synonyms.extend(synonyms)
                else:
                    if concept.synonyms is not None:
                        concept.synonyms.append(synonyms)

            # Add definitions
            if "definition" in result:
                definitions = result["definition"]
                if isinstance(definitions, list):
                    if concept.definitions is not None:
                        concept.definitions.extend(definitions)
                else:
                    if concept.definitions is not None:
                        concept.definitions.append(definitions)

            # Add ontology information
            if "links" in result and "ontology" in result["links"]:
                if concept.categories is not None:
                    concept.categories.append(result["links"]["ontology"])

            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.BIOPORTAL] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting BioPortal result: {e}")
            return None

    def _convert_bioportal_concept_to_unified(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert detailed BioPortal concept to unified concept."""
        try:
            concept_id = data.get("@id", "")
            label = data.get("prefLabel", "")

            if not concept_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            # Add BioPortal identifier
            concept.add_identifier(KnowledgeSource.BIOPORTAL, concept_id, label, concept_id)

            # Add synonyms
            if "synonym" in data:
                synonyms = data["synonym"]
                if isinstance(synonyms, list):
                    if concept.synonyms is not None:
                        concept.synonyms.extend(synonyms)
                else:
                    if concept.synonyms is not None:
                        concept.synonyms.append(synonyms)

            # Add definitions
            if "definition" in data:
                definitions = data["definition"]
                if isinstance(definitions, list):
                    if concept.definitions is not None:
                        concept.definitions.extend(definitions)
                else:
                    if concept.definitions is not None:
                        concept.definitions.append(definitions)

            # Add hierarchical relationships
            if "parents" in data:
                concept.parents = [p.get("@id", "") for p in data["parents"] if "@id" in p]

            if "children" in data:
                concept.children = [c.get("@id", "") for c in data["children"] if "@id" in c]

            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.BIOPORTAL] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting BioPortal concept: {e}")
            return None

    def _determine_concept_type_from_ontology(self, ontology: str) -> ConceptType:
        """Determine concept type from BioPortal ontology."""
        ontology_lower = ontology.lower()

        # Map common BioPortal ontologies to concept types. "chebi" must not
        # appear in the drug branch: it used to be checked before (and so
        # always won over) the later chebi -> CHEMICAL branch below, which
        # was consequently dead code (same bug as ols_adapter.py's identical
        # mapping — ChEBI is the chemical-structure ontology, DrugBank the
        # drug-specific one, and they aren't interchangeable).
        if any(disease_ont in ontology_lower for disease_ont in ["doid", "mondo", "ordo"]):
            return ConceptType.DISEASE
        elif "drugbank" in ontology_lower:
            return ConceptType.DRUG
        elif "chebi" in ontology_lower:
            return ConceptType.CHEMICAL
        elif any(gene_ont in ontology_lower for gene_ont in ["go", "so"]):
            return ConceptType.GENE
        elif any(anatomy_ont in ontology_lower for anatomy_ont in ["uberon", "fma"]):
            # ANATOMICAL_ENTITY, not the separate ConceptType.ANATOMY member
            # — CentralKnowledgeLookup's concept_types filter compares by
            # exact enum value, so the wrong member means zero matches.
            return ConceptType.ANATOMICAL_ENTITY
        elif any(phenotype_ont in ontology_lower for phenotype_ont in ["hp", "mp"]):
            return ConceptType.PHENOTYPE

        return ConceptType.UNKNOWN
