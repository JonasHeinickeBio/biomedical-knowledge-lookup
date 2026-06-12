"""
Open Targets Knowledge Source Adapter

Integrates with Open Targets GraphQL API for drug target and disease lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class OpenTargetsAdapter(KnowledgeSourceAdapter):
    """Adapter for Open Targets."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://api.platform.opentargets.org/api/v4/graphql"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OPENTARGETS

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Open Targets for targets and diseases."""
        try:
            # GraphQL query for search
            graphql_query = {
                "query": """
                query Search($queryString: String!) {
                  search(queryString: $queryString, entityNames: ["target", "disease"]) {
                    hits {
                      id
                      name
                      entity
                      description
                    }
                  }
                }
                """,
                "variables": {"queryString": query},
            }

            data = await self._make_request(self.base_url, json_data=graphql_query)

            concepts = []
            if "data" in data and "search" in data["data"] and "hits" in data["data"]["search"]:
                for hit in data["data"]["search"]["hits"][:limit]:
                    concept = self._convert_opentargets_result_to_concept(hit)
                    if concept:
                        concepts.append(concept)

            logger.info(f"Open Targets search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Open Targets search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information from Open Targets."""
        try:
            # We need to know if it's a target or a disease
            # Usually EFO/MONDO/ORPHA IDs are diseases, ENSG are targets
            entity_type = (
                "disease"
                if concept_id.startswith("EFO_")
                or concept_id.startswith("MONDO_")
                or concept_id.startswith("ORPHA")
                else "target"
            )

            # Build GraphQL query based on entity type
            # Target uses ensemblId, disease uses id
            if entity_type == "target":
                graphql_query_str = """
                query Details($ensemblId: String!) {
                  target(ensemblId: $ensemblId) {
                    id
                    approvedSymbol
                    biotype
                  }
                }
                """
                graphql_query = {
                    "query": graphql_query_str,
                    "variables": {"ensemblId": concept_id},
                }
            else:
                graphql_query_str = """
                query Details($id: String!) {
                  disease(id: $id) {
                    id
                    name
                    definition
                  }
                }
                """
                graphql_query = {
                    "query": graphql_query_str,
                    "variables": {"id": concept_id},
                }

            data = await self._make_request(self.base_url, json_data=graphql_query)

            if "data" in data and entity_type in data["data"] and data["data"][entity_type]:
                concept = self._convert_opentargets_result_to_concept(
                    data["data"][entity_type], entity_type
                )
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Open Targets concept details for '{concept_id}': {e}")
            return None

    def _convert_opentargets_result_to_concept(
        self, result: dict[str, Any], entity_type: str | None = None
    ) -> UnifiedConcept | None:
        """Convert Open Targets API result to unified concept."""
        try:
            ot_id = result.get("id", "")

            # Get label based on entity type
            # For diseases: use 'name' if available, otherwise use 'id'
            # For targets: use 'approvedSymbol' as label, fallback to 'id'
            if entity_type == "disease":
                label = result.get("name", ot_id)
                concept_type = ConceptType.DISEASE
            else:
                label = result.get("approvedSymbol", ot_id)
                concept_type = ConceptType.GENE

            concept = UnifiedConcept(
                primary_id=ot_id, primary_label=label, concept_type=concept_type
            )

            # entity is the folder name for the URL
            entity = (
                entity_type
                if entity_type
                else ("disease" if concept_type == ConceptType.DISEASE else "target")
            )

            concept.add_identifier(
                KnowledgeSource.OPENTARGETS,
                ot_id,
                label,
                f"https://platform.opentargets.org/{entity}/{ot_id}",
            )

            # Add definition based on entity type
            if entity_type == "disease":
                if "definition" in result and result["definition"]:
                    concept.definitions.append(result["definition"])
            else:
                # For targets, there's no description - use biotype as additional info
                if "biotype" in result:
                    concept.definitions.append(f"Biotype: {result['biotype']}")

            if "approvedSymbol" in result:
                concept.synonyms.append(result["approvedSymbol"])

            concept.confidence_score = 0.9
            concept.source_data[KnowledgeSource.OPENTARGETS] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Open Targets result: {e}")
            return None
