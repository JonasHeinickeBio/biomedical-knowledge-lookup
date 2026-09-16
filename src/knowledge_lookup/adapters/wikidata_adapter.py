"""
Wikidata Knowledge Base Adapter

Integrates with Wikidata SPARQL endpoint for general biomedical knowledge lookup.
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Wikidata item IDs are "Q" followed by digits; anything else could inject SPARQL.
_QID_PATTERN = re.compile(r"Q\d+")


def _sparql_string_literal(value: str) -> str:
    """Return *value* as a double-quoted SPARQL string literal.

    Escapes every character that could end the literal or break the query
    (backslash, double quote, line breaks), so user input cannot inject SPARQL.
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
    )
    return f'"{escaped}"'


def _binding_value(binding: Any, key: str) -> str:
    """The ``value`` of *key* in a SPARQL JSON result row, or ``""``."""
    cell = binding.get(key) if isinstance(binding, dict) else None
    return cell.get("value", "") if isinstance(cell, dict) else ""


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
        """Search Wikidata for concepts.

        Each item is returned once. The "instance of" (P31) join yields one row
        per value, so ``LIMIT`` is applied to items in a subquery and the rows are
        merged by item, combining their instance-of labels into ``categories``.
        """
        try:
            # SPARQL query to search for items by label. The search text is passed
            # as an escaped literal; ?ordinal keeps the EntitySearch ranking.
            sparql_query = f"""
            SELECT ?item ?itemLabel ?itemDescription ?instanceOfLabel ?ordinal WHERE {{
              {{
                SELECT ?item ?ordinal WHERE {{
                  SERVICE wikibase:mwapi {{
                    bd:serviceParam wikibase:api "EntitySearch" .
                    bd:serviceParam wikibase:endpoint "www.wikidata.org" .
                    bd:serviceParam mwapi:search {_sparql_string_literal(query)} .
                    bd:serviceParam mwapi:language "en" .
                    ?item wikibase:apiOutputItem mwapi:item .
                    ?ordinal wikibase:apiOrdinal true .
                  }}
                }}
                ORDER BY ?ordinal
                LIMIT {int(limit)}
              }}
              OPTIONAL {{ ?item wdt:P31 ?instanceOf . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            ORDER BY ?ordinal
            """

            params = {"query": sparql_query, "format": "json"}

            headers = {
                "Accept": "application/sparql-results+json",
                "User-Agent": "AID-PAIS-Knowledge-Lookup/1.0",
            }

            data = await self._make_request(self.sparql_endpoint, params, headers=headers)

            concepts: list[UnifiedConcept] = []
            by_item: dict[str, UnifiedConcept] = {}
            if "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"]:
                    item_uri = _binding_value(binding, "item")
                    if item_uri in by_item:
                        self._merge_instance_of(by_item[item_uri], binding)
                        continue
                    if len(concepts) >= limit:
                        continue
                    concept = self._convert_wikidata_result_to_concept(binding)
                    if concept:
                        concepts.append(concept)
                        if item_uri:
                            by_item[item_uri] = concept

            logger.info(f"Wikidata search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Wikidata search failed for '{query}': {e}")
            return []

    def _merge_instance_of(self, concept: UnifiedConcept, binding: dict[str, Any]) -> None:
        """Fold another search row for the same item into *concept*.

        Adds the row's instance-of label to ``categories`` and, while the concept
        type is still ``UNKNOWN``, derives the type from it.
        """
        instance_of = _binding_value(binding, "instanceOfLabel")
        if not instance_of:
            return
        if concept.categories is not None and instance_of not in concept.categories:
            concept.categories.append(instance_of)
        current_type = getattr(concept.concept_type, "value", concept.concept_type)
        if current_type == ConceptType.UNKNOWN.value:
            concept.concept_type = self._determine_concept_type_from_instance_of(instance_of)

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information from Wikidata."""
        try:
            # concept_id must be a Wikidata Q-ID (e.g., Q12136); it is inserted
            # into the query as wd:<id>, so reject anything else.
            if not _QID_PATTERN.fullmatch(concept_id):
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
                if concept.definitions is not None:
                    concept.definitions.append(result["itemDescription"]["value"])

            if instance_of:
                if concept.categories is not None:
                    concept.categories.append(instance_of)

            concept.confidence_score = 0.7
            if isinstance(concept.source_data, dict):
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
                if concept.definitions is not None:
                    concept.definitions.append(first["itemDescription"]["value"])

            def _add_category(category: str) -> None:
                if concept.categories is not None and category not in concept.categories:
                    concept.categories.append(category)

            # Extract all identifiers and categories from bindings. The OPTIONAL
            # joins repeat values across rows, so de-duplicate as we go.
            umls_cuis: set[str] = set()
            for b in bindings:
                if "umlsCui" in b and b["umlsCui"]["value"] not in umls_cuis:
                    umls_cuis.add(b["umlsCui"]["value"])
                    concept.add_identifier(KnowledgeSource.UMLS, b["umlsCui"]["value"], label)
                if "meshId" in b:
                    # MeSH descriptor IDs are not UMLS CUIs and there is no MeSH
                    # KnowledgeSource, so keep them as a category like ICD-10.
                    _add_category(f"MeSH: {b['meshId']['value']}")
                if "icd10" in b:
                    _add_category(f"ICD-10: {b['icd10']['value']}")
                if "ncbiTaxonId" in b:
                    _add_category(f"NCBI Taxon: {b['ncbiTaxonId']['value']}")
                if "instanceOfLabel" in b:
                    _add_category(b["instanceOfLabel"]["value"])

            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
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
