"""
Adapter for DBpedia knowledge base.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


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
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Make an async HTTP request to DBpedia, logging URL, params, and errors.
        """
        logger.info(f"DBpedia API Request URL: {url}")
        logger.info(f"DBpedia API Request Params: {params}")
        if headers:
            logger.info(f"DBpedia API Request Headers: {headers}")
        try:
            return await super()._make_request(url, params, headers)
        except Exception as e:
            logger.error(f"DBpedia _make_request failed for URL {url}: {e}", exc_info=True)
            return {}

    async def run_sparql_query(self, sparql_query: str, limit: Optional[int] = None) -> Any:
        """
        Run a generic SPARQL query against DBpedia and return the raw results.
        """
        if limit is not None and "LIMIT" not in sparql_query:
            sparql_query += f"\nLIMIT {limit}"
        params = {"query": sparql_query, "format": "json"}
        return await self._make_request(self.sparql_endpoint, params)

    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """
        Search DBpedia for concepts matching the query string.
        """
        try:
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT DISTINCT ?resource ?label ?abstract ?type WHERE {{
              ?resource rdfs:label ?label .
              ?label bif:contains "'{query}'" .
              FILTER (lang(?label) = 'en')
              OPTIONAL {{ ?resource dbo:abstract ?abstract . FILTER (lang(?abstract) = 'en') }}
              OPTIONAL {{ ?resource rdf:type ?type }}
            }}
            """
            data = await self.run_sparql_query(sparql_query, limit=min(limit, 50))
            concepts = []
            if "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"][:limit]:
                    concept = self._convert_dbpedia_result_to_concept(binding)
                    if concept:
                        concepts.append(concept)
            logger.info(f"DBpedia search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"DBpedia search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """
        Get details for a specific DBpedia concept/entity.
        """
        try:
            if not concept_id.startswith("http://dbpedia.org/resource/"):
                concept_id = f"http://dbpedia.org/resource/{concept_id}"
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT ?property ?value WHERE {{
              <{concept_id}> ?property ?value .
            }}
            """
            data = await self.run_sparql_query(sparql_query, limit=100)
            if "results" in data and "bindings" in data["results"]:
                concept = self._convert_dbpedia_entity_to_unified(
                    concept_id, data["results"]["bindings"]
                )
                return concept
            return None
        except Exception as e:
            logger.error(f"Failed to get DBpedia concept details for '{concept_id}': {e}")
            return None

    def _convert_dbpedia_result_to_concept(
        self, result: Dict[str, Any]
    ) -> Optional[UnifiedConcept]:
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
                concept.definitions.append(
                    abstract[:500] + "..." if len(abstract) > 500 else abstract
                )
            if "type" in result:
                type_uri = result["type"]["value"]
                concept.categories.append(type_uri.split("/")[-1])
            concept.confidence_score = 0.6
            concept.source_data[KnowledgeSource.DBPEDIA] = result
            return concept
        except Exception as e:
            logger.error(f"Error converting DBpedia result: {e}")
            return None

    def _convert_dbpedia_entity_to_unified(
        self, entity_uri: str, properties: List[Dict[str, Any]]
    ) -> Optional[UnifiedConcept]:
        try:
            entity_id = entity_uri.split("/")[-1]
            label = ""
            abstract = ""
            types = []
            for prop in properties:
                property_uri = prop["property"]["value"]
                value = prop["value"]["value"]
                if property_uri.endswith("rdfs#label") and prop["value"].get("xml:lang") == "en":
                    label = value
                elif (
                    property_uri.endswith("dbo:abstract") and prop["value"].get("xml:lang") == "en"
                ):
                    abstract = value
                elif property_uri == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                    types.append(value)
            if not label:
                label = entity_id.replace("_", " ")
            concept = UnifiedConcept(
                primary_id=entity_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )
            concept.add_identifier(KnowledgeSource.DBPEDIA, entity_id, label, entity_uri)
            if abstract:
                concept.definitions.append(
                    abstract[:1000] + "..." if len(abstract) > 1000 else abstract
                )
            for type_uri in types:
                concept.categories.append(type_uri.split("/")[-1])
            concept.confidence_score = 0.65
            concept.source_data[KnowledgeSource.DBPEDIA] = properties
            return concept
        except Exception as e:
            logger.error(f"Error converting DBpedia entity: {e}")
            return None
