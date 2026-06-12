"""
Additional Knowledge Source Adapters

This module contains adapters for additional knowledge sources like DBpedia, OxO, etc.
"""

import logging
from typing import Any

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

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search DBpedia for concepts using SPARQL."""
        try:
            # SPARQL query to search for resources by label
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            PREFIX dbr: <http://dbpedia.org/resource/>

            SELECT DISTINCT ?resource ?label ?abstract ?type WHERE {{
              ?resource rdfs:label ?label .
              FILTER(CONTAINS(LCASE(?label), LCASE("{query}")))
              FILTER(LANG(?label) = "en")
              OPTIONAL {{ ?resource dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
              OPTIONAL {{ ?resource rdf:type ?type }}
            }}
            LIMIT {min(limit, 50)}
            """

            params = {"query": sparql_query, "format": "json"}

            data = await self._make_request(self.sparql_endpoint, params)

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

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed concept information from DBpedia."""
        try:
            # For DBpedia, concept_id should be a DBpedia URI
            if not concept_id.startswith("http://dbpedia.org/resource/"):
                concept_id = f"http://dbpedia.org/resource/{concept_id}"

            # SPARQL query to get all properties of the resource
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>

            SELECT ?property ?value WHERE {{
              <{concept_id}> ?property ?value .
            }}
            LIMIT 100
            """

            params = {"query": sparql_query, "format": "json"}

            data = await self._make_request(self.sparql_endpoint, params)

            if "results" in data and "bindings" in data["results"]:
                concept = self._convert_dbpedia_entity_to_unified(
                    concept_id, data["results"]["bindings"]
                )
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get DBpedia concept details for '{concept_id}': {e}")
            return None

    def _convert_dbpedia_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert DBpedia SPARQL result to unified concept."""
        try:
            if "resource" not in result or "label" not in result:
                return None

            resource_uri = result["resource"]["value"]
            label = result["label"]["value"]

            # Extract DBpedia ID from URI
            resource_id = resource_uri.split("/")[-1]

            concept = UnifiedConcept(
                primary_id=resource_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            # Add DBpedia identifier
            concept.add_identifier(KnowledgeSource.DBPEDIA, resource_id, label, resource_uri)

            # Add abstract as definition if available
            if "abstract" in result:
                abstract = result["abstract"]["value"]
                concept.definitions.append(
                    abstract[:500] + "..." if len(abstract) > 500 else abstract
                )

            # Add type information
            if "type" in result:
                type_uri = result["type"]["value"]
                concept.categories.append(type_uri.split("/")[-1])

            concept.confidence_score = 0.6  # DBpedia may be less precise for biological concepts
            concept.source_data[KnowledgeSource.DBPEDIA] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting DBpedia result: {e}")
            return None

    def _convert_dbpedia_entity_to_unified(
        self, entity_uri: str, properties: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        """Convert detailed DBpedia entity to unified concept."""
        try:
            entity_id = entity_uri.split("/")[-1]

            # Extract label and other properties
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

            # Add DBpedia identifier
            concept.add_identifier(KnowledgeSource.DBPEDIA, entity_id, label, entity_uri)

            # Add abstract as definition
            if abstract:
                concept.definitions.append(
                    abstract[:1000] + "..." if len(abstract) > 1000 else abstract
                )

            # Add type information
            for type_uri in types:
                concept.categories.append(type_uri.split("/")[-1])

            concept.confidence_score = 0.65
            concept.source_data[KnowledgeSource.DBPEDIA] = properties

            return concept

        except Exception as e:
            logger.error(f"Error converting DBpedia entity: {e}")
            return None


class OxOAdapter(KnowledgeSourceAdapter):
    """
    Adapter for OxO (Ontology Cross-reference Service).
    OxO provides mappings between ontology terms.
    """

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/spot/oxo/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OXO

    def is_available(self) -> bool:
        return True  # OxO is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """OxO is primarily for mappings, not direct search. Return empty list."""
        logger.info("OxO adapter is primarily for mappings, not direct concept search")
        return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get concept details is not the primary use case for OxO."""
        return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """
        Get cross-reference mappings for a concept from OxO.
        This is the primary functionality of OxO.
        """
        try:
            url = f"{self.base_url}/mappings"
            params = {"fromId": concept_id, "size": 100}

            data = await self._make_request(url, params)

            mappings = []
            if "_embedded" in data and "mappings" in data["_embedded"]:
                for mapping in data["_embedded"]["mappings"]:
                    mappings.append(
                        {
                            "fromId": mapping.get("fromTerm", {}).get("curie", ""),
                            "toId": mapping.get("toTerm", {}).get("curie", ""),
                            "fromSource": mapping.get("fromTerm", {})
                            .get("datasource", {})
                            .get("name", ""),
                            "toSource": mapping.get("toTerm", {})
                            .get("datasource", {})
                            .get("name", ""),
                            "mappingType": mapping.get("scope", "related"),
                            "confidence": 1.0,  # OxO doesn't provide confidence scores
                        }
                    )

            logger.info(f"OxO found {len(mappings)} mappings for '{concept_id}'")
            return mappings

        except Exception as e:
            logger.error(f"OxO mapping lookup failed for '{concept_id}': {e}")
            return []


class BioOntologyAdapter(KnowledgeSourceAdapter):
    """
    Adapter for BioOntology.org (now part of BioPortal).
    This is essentially an alias for BioPortal functionality.
    """

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        # Use the same base URL as BioPortal
        self.base_url = "https://data.bioontology.org"
        self.api_key = config.get_api_key("bioontology") or config.get_api_key("bioportal")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.BIOONTOLOGY

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search BioOntology (via BioPortal API) for concepts."""
        if not self.api_key:
            logger.warning("BioOntology API key not available")
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
                    concept = self._convert_bioontology_result_to_concept(item)
                    if concept:
                        concepts.append(concept)

            logger.info(f"BioOntology search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"BioOntology search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed concept information from BioOntology."""
        # Similar implementation to BioPortal adapter
        # Implementation details would be similar to BioPortalAdapter
        return None

    def _convert_bioontology_result_to_concept(
        self, result: dict[str, Any]
    ) -> UnifiedConcept | None:
        """Convert BioOntology search result to unified concept."""
        try:
            concept_id = result.get("@id", "")
            label = result.get("prefLabel", "")

            if not concept_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            # Add BioOntology identifier
            concept.add_identifier(
                KnowledgeSource.BIOONTOLOGY, concept_id, label, result.get("@id", "")
            )

            concept.confidence_score = 0.8
            concept.source_data[KnowledgeSource.BIOONTOLOGY] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting BioOntology result: {e}")
            return None
