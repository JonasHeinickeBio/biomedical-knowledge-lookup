"""
OLS (Ontology Lookup Service) Adapter

Integrates with EMBL-EBI Ontology Lookup Service for concept lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class OLSAdapter(KnowledgeSourceAdapter):
    """Adapter for EMBL-EBI Ontology Lookup Service."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/ols4/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OLS

    def is_available(self) -> bool:
        return True  # OLS is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search OLS for concepts."""
        try:
            url = f"{self.base_url}/search"
            params = {"q": query, "rows": min(limit, 100), "format": "json"}

            data = await self._make_request(url, params)

            concepts = []
            if "response" in data and "docs" in data["response"]:
                for doc in data["response"]["docs"][:limit]:
                    concept = self._convert_ols_result_to_concept(doc)
                    if concept:
                        concepts.append(concept)

            logger.info(f"OLS search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"OLS search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed concept information from OLS."""
        try:
            # If it's an IRI, use the terms endpoint
            if "http" in concept_id:
                url = f"{self.base_url}/terms"
                params = {"iri": concept_id}
                data = await self._make_request(url, params)

                if (
                    "_embedded" in data
                    and "terms" in data["_embedded"]
                    and len(data["_embedded"]["terms"]) > 0
                ):
                    # Get the first match
                    term_data = data["_embedded"]["terms"][0]
                    concept = self._convert_ols_concept_to_unified(term_data)
                    return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get OLS concept details for '{concept_id}': {e}")
            return None

    def _convert_ols_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert OLS search result to unified concept."""
        try:
            concept_id = result.get("iri", "")
            label = result.get("label", "")

            if not concept_id or not label:
                return None

            # Determine concept type from ontology
            ontology = result.get("ontology_name", "")
            concept_type = self._determine_concept_type_from_ontology(ontology)

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=concept_type
            )

            # Add OLS identifier
            concept.add_identifier(KnowledgeSource.OLS, concept_id, label, concept_id)

            # Add synonyms
            if "synonym" in result:
                synonyms = result["synonym"]
                if isinstance(synonyms, list):
                    if concept.synonyms is not None:
                        concept.synonyms.extend(synonyms)
                else:
                    if concept.synonyms is not None:
                        concept.synonyms.append(synonyms)

            # Add description
            if "description" in result:
                descriptions = result["description"]
                if isinstance(descriptions, list):
                    if concept.definitions is not None:
                        concept.definitions.extend(descriptions)
                else:
                    if concept.definitions is not None:
                        concept.definitions.append(descriptions)

            # Add ontology information
            if "ontology_name" in result:
                if concept.categories is not None:
                    concept.categories.append(result["ontology_name"])

            # Add short form (often more readable ID)
            if "short_form" in result:
                concept.add_identifier(KnowledgeSource.OLS, result["short_form"], label)

            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OLS] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting OLS result: {e}")
            return None

    def _convert_ols_concept_to_unified(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert detailed OLS concept to unified concept."""
        try:
            concept_id = data.get("iri", "")
            label = data.get("label", "")

            if not concept_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            # Add OLS identifier
            concept.add_identifier(KnowledgeSource.OLS, concept_id, label, concept_id)

            # Add synonyms
            if "synonyms" in data:
                if concept.synonyms is not None:
                    concept.synonyms.extend(data["synonyms"])

            # Add definitions
            if "description" in data:
                descriptions = data["description"]
                if isinstance(descriptions, list):
                    if concept.definitions is not None:
                        concept.definitions.extend(descriptions)
                else:
                    if concept.definitions is not None:
                        concept.definitions.append(descriptions)

            # Extract cross-references
            if "annotation" in data:
                xrefs = data["annotation"].get("database_cross_reference", [])
                if isinstance(xrefs, str):
                    xrefs = [xrefs]
                for xref in xrefs:
                    if concept.categories is not None:
                        concept.categories.append(f"Xref: {xref}")

            if "obo_xref" in data:
                xrefs = data["obo_xref"]
                if isinstance(xrefs, list):
                    for xref in xrefs:
                        db = xref.get("database", "")
                        id = xref.get("id", "")
                        if db and id:
                            if concept.categories is not None:
                                concept.categories.append(f"Xref: {db}:{id}")

            # Add hierarchical relationships from _links if available
            if "_links" in data:
                links = data["_links"]
                if "parents" in links:
                    # Would need to make additional requests to get parent IRIs
                    pass
                if "children" in links:
                    # Would need to make additional requests to get children IRIs
                    pass

            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OLS] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting OLS concept: {e}")
            return None

    def _determine_concept_type_from_ontology(self, ontology: str) -> ConceptType:
        """Determine concept type from OLS ontology name."""
        ontology_lower = ontology.lower()

        # Map OLS ontologies to concept types
        if ontology_lower in ["doid", "mondo", "ordo", "hp"]:
            return ConceptType.DISEASE
        elif ontology_lower in ["chebi", "drugbank"]:
            return ConceptType.DRUG
        elif ontology_lower in ["go", "so", "pr"]:
            return ConceptType.GENE
        elif ontology_lower in ["uberon", "fma", "ma"]:
            return ConceptType.ANATOMY
        elif ontology_lower in ["hp", "mp", "zp"]:
            return ConceptType.PHENOTYPE
        elif ontology_lower in ["chebi"]:
            return ConceptType.CHEMICAL
        elif ontology_lower in ["ncbitaxon"]:
            return ConceptType.ORGANISM

        return ConceptType.UNKNOWN
