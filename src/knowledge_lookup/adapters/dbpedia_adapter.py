"""
Adapter for DBpedia knowledge base.
"""

import logging
import re
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Full property IRIs as returned in SPARQL JSON results
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
DBO_ABSTRACT = "http://dbpedia.org/ontology/abstract"
DBO_ICD10 = "http://dbpedia.org/ontology/icd10"

# Characters that may not appear inside a SPARQL <IRI> reference
_IRI_FORBIDDEN = re.compile(r'[<>"{}|^`\\\s]')


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


def _free_text_phrase(query: str) -> str:
    """Reduce *query* to plain words for Virtuoso's ``bif:contains``.

    ``bif:contains`` has its own expression syntax (quotes, AND/OR, wildcards)
    inside the SPARQL literal; keeping only word characters makes the phrase
    safe for both layers.
    """
    return " ".join(re.findall(r"\w+", query))


def _binding_value(binding: Any, key: str) -> str:
    """The ``value`` of *key* in a SPARQL JSON result row, or ``""``."""
    cell = binding.get(key) if isinstance(binding, dict) else None
    return cell.get("value", "") if isinstance(cell, dict) else ""


class DBpediaAdapter(KnowledgeSourceAdapter):
    """Adapter for DBpedia knowledge base."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.sparql_endpoint = "https://dbpedia.org/sparql"
        self.base_url = "https://dbpedia.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DBPEDIA

    def is_available(self) -> bool:
        return True  # DBpedia is publicly available

    async def _make_request(
        self,
        url: str,
        params: dict[Any, Any] | None = None,
        headers: dict[Any, Any] | None = None,
        json_data: dict[Any, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an async HTTP request to DBpedia, logging URL, params, and errors.
        """
        logger.debug(f"DBpedia API Request URL: {url}")
        logger.debug(f"DBpedia API Request Params: {params}")
        if headers:
            logger.debug(f"DBpedia API Request Headers: {headers}")
        try:
            return await super()._make_request(url, params, headers)
        except Exception as e:
            logger.error(f"DBpedia _make_request failed for URL {url}: {e}", exc_info=True)
            return {}

    async def run_sparql_query(self, sparql_query: str, limit: int | None = None) -> Any:
        """
        Run a generic SPARQL query against DBpedia and return the raw results.
        """
        if limit is not None and "LIMIT" not in sparql_query:
            sparql_query += f"\nLIMIT {limit}"
        params = {"query": sparql_query, "format": "json"}
        return await self._make_request(self.sparql_endpoint, params)

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search DBpedia for concepts matching the query string.

        Each resource is returned once. The ``rdf:type`` join yields one row per
        type, so ``LIMIT`` is applied to resources in a subquery and the rows are
        merged by resource, combining their types into ``categories``.
        """
        try:
            phrase = _free_text_phrase(query)
            if not phrase:
                return []
            exact_label = _sparql_string_literal(query.lower())
            contains_expr = _sparql_string_literal(f"'{phrase}'")
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT ?resource ?label ?abstract ?type ?exactMatch WHERE {{
              {{
                SELECT DISTINCT ?resource ?label (IF(LCASE(STR(?label)) = {exact_label}, 1, 0) AS ?exactMatch) WHERE {{
                  ?resource rdfs:label ?label .
                  ?label bif:contains {contains_expr} .
                  FILTER (lang(?label) = 'en')
                }}
                ORDER BY DESC(?exactMatch)
                LIMIT {min(int(limit), 50)}
              }}
              OPTIONAL {{ ?resource dbo:abstract ?abstract . FILTER (lang(?abstract) = 'en') }}
              OPTIONAL {{ ?resource rdf:type ?type }}
            }}
            ORDER BY DESC(?exactMatch)
            """  # noqa: E501
            data = await self.run_sparql_query(sparql_query)
            concepts: list[UnifiedConcept] = []
            by_resource: dict[str, UnifiedConcept] = {}
            if "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"]:
                    resource_uri = _binding_value(binding, "resource")
                    if resource_uri in by_resource:
                        self._merge_dbpedia_row(by_resource[resource_uri], binding)
                        continue
                    if len(concepts) >= limit:
                        continue
                    concept = self._convert_dbpedia_result_to_concept(binding)
                    if concept:
                        concepts.append(concept)
                        by_resource[resource_uri] = concept
            logger.info(f"DBpedia search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"DBpedia search failed for '{query}': {e}")
            return []

    @staticmethod
    def _merge_dbpedia_row(concept: UnifiedConcept, row: dict[str, Any]) -> None:
        """Fold another search row for the same resource into *concept*.

        Adds the row's type to ``categories`` (each once) and its abstract when
        the concept has no definition yet.
        """
        type_uri = _binding_value(row, "type")
        if type_uri and concept.categories is not None:
            category = type_uri.split("/")[-1]
            if category not in concept.categories:
                concept.categories.append(category)
        abstract = _binding_value(row, "abstract")
        if abstract and concept.definitions is not None and not concept.definitions:
            concept.definitions.append(abstract[:500] + "..." if len(abstract) > 500 else abstract)

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get details for a specific DBpedia concept/entity.
        """
        try:
            if not concept_id.startswith("http://dbpedia.org/resource/"):
                concept_id = f"http://dbpedia.org/resource/{concept_id.strip().replace(' ', '_')}"
            # Percent-encode characters that would end the <IRI> and inject SPARQL
            concept_id = _IRI_FORBIDDEN.sub(lambda m: quote(m.group(0)), concept_id)
            # Only English (or language-less) literals, so labels in other
            # languages do not use up the LIMIT before the abstract is reached.
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT ?property ?value WHERE {{
              <{concept_id}> ?property ?value .
              FILTER (?property IN (rdfs:label, dbo:abstract, rdf:type, dbo:icd10))
              FILTER (!isLiteral(?value) || lang(?value) = "" || langMatches(lang(?value), "en"))
            }}
            """
            data = await self.run_sparql_query(sparql_query, limit=100)
            # No bindings means DBpedia has no such resource
            if "results" in data and data["results"].get("bindings"):
                concept = self._convert_dbpedia_entity_to_unified(
                    concept_id, data["results"]["bindings"]
                )
                return concept
            return None
        except Exception as e:
            logger.error(f"Failed to get DBpedia concept details for '{concept_id}': {e}")
            return None

    def _convert_dbpedia_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        try:
            if "resource" not in result or "label" not in result:
                return None
            resource_uri = result["resource"]["value"]
            label = result["label"]["value"]
            resource_id = resource_uri.split("/")[-1]
            concept = UnifiedConcept(
                primary_id=resource_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )
            concept.add_identifier(KnowledgeSource.DBPEDIA, resource_id, label, resource_uri)
            if "abstract" in result:
                abstract = result["abstract"]["value"]
                if concept.definitions is not None:
                    concept.definitions.append(
                        abstract[:500] + "..." if len(abstract) > 500 else abstract
                    )
            if "type" in result:
                type_uri = result["type"]["value"]
                if concept.categories is not None:
                    concept.categories.append(type_uri.split("/")[-1])
            concept.confidence_score = 0.6
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.DBPEDIA] = result
            return concept
        except Exception as e:
            logger.error(f"Error converting DBpedia result: {e}")
            return None

    def _convert_dbpedia_entity_to_unified(
        self, entity_uri: str, properties: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        try:
            entity_id = entity_uri.split("/")[-1]

            # Find label first to initialize concept
            label = ""
            for prop in properties:
                if (
                    prop["property"]["value"] == RDFS_LABEL
                    and prop["value"].get("xml:lang") == "en"
                ):
                    label = prop["value"]["value"]
                    break

            if not label:
                label = entity_id.replace("_", " ")

            concept = UnifiedConcept(
                primary_id=entity_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )
            concept.add_identifier(KnowledgeSource.DBPEDIA, entity_id, label, entity_uri)

            def _add_category(category: str) -> None:
                # DBpedia repeats rdf:type rows (one per named graph)
                if concept.categories is not None and category not in concept.categories:
                    concept.categories.append(category)

            abstract = ""
            for prop in properties:
                property_uri = prop["property"]["value"]
                value = prop["value"]["value"]
                if property_uri == DBO_ABSTRACT and prop["value"].get("xml:lang") == "en":
                    abstract = value
                elif property_uri == RDF_TYPE:
                    _add_category(value.split("/")[-1])
                elif property_uri == DBO_ICD10:
                    _add_category(f"ICD-10: {value}")

            if abstract and concept.definitions is not None:
                concept.definitions.append(
                    abstract[:1000] + "..." if len(abstract) > 1000 else abstract
                )

            concept.confidence_score = 0.65
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.DBPEDIA] = properties
            return concept
        except Exception as e:
            logger.error(f"Error converting DBpedia entity: {e}")
            return None
