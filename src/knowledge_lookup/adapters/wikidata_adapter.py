"""
Wikidata Knowledge Base Adapter

Integrates with Wikidata SPARQL endpoint for general biomedical knowledge lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class WikidataAdapter(KnowledgeSourceAdapter):
    """Adapter for Wikidata."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.sparql_endpoint = "https://query.wikidata.org/sparql"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.WIKIDATA

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Wikidata for concepts."""
        try:
            # SPARQL query to search for items by label
            sparql_query = f"""
            SELECT DISTINCT ?item ?itemLabel ?itemDescription ?instanceOfLabel WHERE {{
              SERVICE wikibase:mwapi {{
                bd:serviceParam wikibase:api "EntitySearch" .
                bd:serviceParam wikibase:endpoint "www.wikidata.org" .
                bd:serviceParam mwapi:search "{query}" .
                bd:serviceParam mwapi:language "en" .
                ?item wikibase:apiOutputItem mwapi:item .
              }}
              OPTIONAL {{ ?item wdt:P31 ?instanceOf . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            LIMIT {limit}
            """

            params = {"query": sparql_query, "format": "json"}

            headers = {
                "Accept": "application/sparql-results+json",
                "User-Agent": "AID-PAIS-Knowledge-Lookup/1.0",
            }

            data = await self._make_request(self.sparql_endpoint, params, headers=headers)

            concepts = []
            if "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"]:
                    concept = self._convert_wikidata_result_to_concept(binding)
                    if concept:
                        concepts.append(concept)

            logger.info(f"Wikidata search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Wikidata search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information from Wikidata."""
        try:
            # concept_id should be Wikidata Q-ID (e.g., Q12136)
            if not concept_id.startswith("Q"):
                # Try to search for it first?
                return None

            sparql_query = f"""
            SELECT ?item ?itemLabel ?itemDescription ?instanceOfLabel ?umlsCui ?meshId ?ncbiTaxonId ?icd10 WHERE {{  # noqa: E501
              BIND(wd:{concept_id} AS ?item)
              OPTIONAL {{ ?item wdt:P31 ?instanceOf . }}
              OPTIONAL {{ ?item wdt:P2892 ?umlsCui . }}
              OPTIONAL {{ ?item wdt:P486 ?meshId . }}
              OPTIONAL {{ ?item wdt:P685 ?ncbiTaxonId . }}
              OPTIONAL {{ ?item wdt:P494 ?icd10 . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            """  # noqa: E501

            params = {"query": sparql_query, "format": "json"}

            headers = {
                "Accept": "application/sparql-results+json",
                "User-Agent": "AID-PAIS-Knowledge-Lookup/1.0",
            }

            data = await self._make_request(self.sparql_endpoint, params, headers=headers)

            if "results" in data and "bindings" in data["results"]:
                concept = self._convert_wikidata_details_to_concept(
                    concept_id, data["results"]["bindings"]
                )
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Wikidata concept details for '{concept_id}': {e}")
            return None

    def _convert_wikidata_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Wikidata search result to unified concept."""
        try:
            item_uri = result["item"]["value"]
            item_id = item_uri.split("/")[-1]
            label = result["itemLabel"]["value"]

            instance_of = result.get("instanceOfLabel", {}).get("value", "")
            concept_type = self._determine_concept_type_from_instance_of(instance_of)

            concept = UnifiedConcept(
                primary_id=item_id, primary_label=label, concept_type=concept_type
            )

            concept.add_identifier(KnowledgeSource.WIKIDATA, item_id, label, item_uri)

            if "itemDescription" in result:
                concept.definitions.append(result["itemDescription"]["value"])

            if instance_of:
                concept.categories.append(instance_of)

            concept.confidence_score = 0.7
            concept.source_data[KnowledgeSource.WIKIDATA] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Wikidata result: {e}")
            return None

    def _convert_wikidata_details_to_concept(
        self, item_id: str, bindings: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        """Convert Wikidata detailed concept to unified concept."""
        try:
            if not bindings:
                return None

            first = bindings[0]
            label = first["itemLabel"]["value"]

            instance_of = first.get("instanceOfLabel", {}).get("value", "")
            concept_type = self._determine_concept_type_from_instance_of(instance_of)

            concept = UnifiedConcept(
                primary_id=item_id, primary_label=label, concept_type=concept_type
            )

            concept.add_identifier(
                KnowledgeSource.WIKIDATA,
                item_id,
                label,
                f"http://www.wikidata.org/entity/{item_id}",
            )

            if "itemDescription" in first:
                concept.definitions.append(first["itemDescription"]["value"])

            # Extract all identifiers and categories from bindings
            for b in bindings:
                if "umlsCui" in b:
                    concept.add_identifier(KnowledgeSource.UMLS, b["umlsCui"]["value"], label)
                if "meshId" in b:
                    concept.add_identifier(
                        KnowledgeSource.UMLS, b["meshId"]["value"], label
                    )  # MeSH is often in UMLS
                if "icd10" in b:
                    concept.categories.append(f"ICD-10: {b['icd10']['value']}")
                if "ncbiTaxonId" in b:
                    concept.categories.append(f"NCBI Taxon: {b['ncbiTaxonId']['value']}")
                if "instanceOfLabel" in b:
                    cat = b["instanceOfLabel"]["value"]
                    if cat not in concept.categories:
                        concept.categories.append(cat)

            concept.confidence_score = 0.8
            concept.source_data[KnowledgeSource.WIKIDATA] = bindings

            return concept

        except Exception as e:
            logger.error(f"Error converting Wikidata details: {e}")
            return None

    def _determine_concept_type_from_instance_of(self, instance_of: str) -> ConceptType:
        """Determine concept type from Wikidata 'instance of' label."""
        io_lower = instance_of.lower()

        if any(t in io_lower for t in ["disease", "disorder", "syndrome"]):
            return ConceptType.DISEASE
        elif any(t in io_lower for t in ["drug", "pharmaceutical", "medication"]):
            return ConceptType.DRUG
        elif any(t in io_lower for t in ["gene", "genetic"]):
            return ConceptType.GENE
        elif any(t in io_lower for t in ["protein"]):
            return ConceptType.PROTEIN
        elif any(t in io_lower for t in ["chemical", "compound"]):
            return ConceptType.CHEMICAL
        elif any(t in io_lower for t in ["taxon", "species", "organism"]):
            return ConceptType.ORGANISM

        return ConceptType.UNKNOWN
