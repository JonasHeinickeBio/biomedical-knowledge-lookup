"""
Open Targets Knowledge Source Adapter

Integrates with Open Targets GraphQL API for drug target and disease lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Open Targets ontology prefixes that differ from common CURIE prefixes
_DISEASE_PREFIX_ALIASES = {"ORPHA": "Orphanet", "ORPHANET": "Orphanet"}


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
                query Search($queryString: String!, $size: Int!) {
                  search(
                    queryString: $queryString
                    entityNames: ["target", "disease"]
                    page: {index: 0, size: $size}
                  ) {
                    hits {
                      id
                      name
                      entity
                      description
                      category
                    }
                  }
                }
                """,
                "variables": {"queryString": query, "size": max(1, min(limit, 100))},
            }

            data = await self._make_request(self.base_url, json_data=graphql_query)
            self._log_graphql_errors(data, f"search '{query}'")

            concepts = []
            search = (data.get("data") or {}).get("search") or {}
            for hit in (search.get("hits") or [])[:limit]:
                # Each hit carries its entity type ("target" or "disease")
                concept = self._convert_opentargets_result_to_concept(hit, hit.get("entity"))
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
            concept_id = concept_id.strip()
            # Targets are Ensembl gene IDs (ENSG...); everything else is a disease
            # or phenotype ID (EFO_, MONDO_, Orphanet_, HP_, OTAR_, ...)
            entity_type = "target" if concept_id.upper().startswith("ENSG") else "disease"

            # Build GraphQL query based on entity type
            # Target uses ensemblId, disease uses efoId
            if entity_type == "target":
                graphql_query_str = """
                query Details($ensemblId: String!) {
                  target(ensemblId: $ensemblId) {
                    id
                    approvedSymbol
                    approvedName
                    biotype
                    functionDescriptions
                    synonyms {
                      label
                      source
                    }
                  }
                }
                """
                graphql_query = {
                    "query": graphql_query_str,
                    "variables": {"ensemblId": concept_id},
                }
            else:
                graphql_query_str = """
                query Details($efoId: String!) {
                  disease(efoId: $efoId) {
                    id
                    name
                    description
                    synonyms {
                      relation
                      terms
                    }
                    dbXRefs
                    therapeuticAreas {
                      id
                      name
                    }
                  }
                }
                """
                graphql_query = {
                    "query": graphql_query_str,
                    "variables": {"efoId": self._normalize_disease_id(concept_id)},
                }

            data = await self._make_request(self.base_url, json_data=graphql_query)
            self._log_graphql_errors(data, f"details '{concept_id}'")

            if data.get("data") and data["data"].get(entity_type):
                concept = self._convert_opentargets_result_to_concept(
                    data["data"][entity_type], entity_type
                )
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Open Targets concept details for '{concept_id}': {e}")
            return None

    @staticmethod
    def _normalize_disease_id(concept_id: str) -> str:
        """Turn CURIE-style disease IDs (``MONDO:0004979``) into Open Targets IDs."""
        if ":" not in concept_id:
            return concept_id
        prefix, local_id = concept_id.split(":", 1)
        prefix = _DISEASE_PREFIX_ALIASES.get(prefix.upper(), prefix)
        return f"{prefix}_{local_id}"

    @staticmethod
    def _log_graphql_errors(data: Any, operation: str) -> None:
        """GraphQL errors arrive with HTTP 200; log them so they are not silent."""
        if isinstance(data, dict) and data.get("errors"):
            messages = "; ".join(
                str(err.get("message", err)) if isinstance(err, dict) else str(err)
                for err in data["errors"]
            )
            logger.warning(f"Open Targets GraphQL errors for {operation}: {messages}")

    def _convert_opentargets_result_to_concept(
        self, result: dict[str, Any], entity_type: str | None = None
    ) -> UnifiedConcept | None:
        """Convert Open Targets API result to unified concept."""
        try:
            ot_id = result.get("id", "")

            # Get label based on entity type
            # For diseases: use 'name' if available, otherwise use 'id'
            # For targets: use 'approvedSymbol' (details) or 'name' (search hit),
            # fallback to 'id'
            if entity_type == "disease":
                label = result.get("name") or ot_id
                concept_type = ConceptType.DISEASE
            elif entity_type in (None, "target"):
                label = result.get("approvedSymbol") or result.get("name") or ot_id
                concept_type = ConceptType.GENE
            else:
                label = result.get("name") or ot_id
                concept_type = ConceptType.UNKNOWN

            concept = UnifiedConcept(
                primary_id=ot_id, primary_label=label, concept_type=concept_type
            )

            # entity is the folder name for the URL
            entity = entity_type or "target"

            concept.add_identifier(
                KnowledgeSource.OPENTARGETS,
                ot_id,
                label,
                f"https://platform.opentargets.org/{entity}/{ot_id}",
            )

            # Add definition based on entity type
            if concept.definitions is not None:
                if entity_type == "disease":
                    # Current schema uses 'description'; 'definition' kept for old payloads
                    definition = result.get("description") or result.get("definition")
                    if definition:
                        concept.definitions.append(definition)
                else:
                    function_descriptions = result.get("functionDescriptions") or []
                    if function_descriptions:
                        concept.definitions.append(function_descriptions[0])
                    elif result.get("description"):
                        concept.definitions.append(result["description"])
                    # Biotype as additional info
                    if result.get("biotype"):
                        concept.definitions.append(f"Biotype: {result['biotype']}")

            if concept.synonyms is not None:
                candidates: list[str] = []
                if "approvedSymbol" in result:
                    candidates.append(result["approvedSymbol"])
                if result.get("approvedName"):
                    candidates.append(result["approvedName"])
                for synonym in result.get("synonyms") or []:
                    if not isinstance(synonym, dict):
                        continue
                    if synonym.get("label"):  # target synonyms
                        candidates.append(synonym["label"])
                    candidates.extend(synonym.get("terms") or [])  # disease synonyms
                for candidate in candidates:
                    if candidate and candidate not in concept.synonyms:
                        concept.synonyms.append(candidate)

            if concept.categories is not None:
                for category in result.get("category") or []:  # search hits
                    if category and category not in concept.categories:
                        concept.categories.append(category)
                for area in result.get("therapeuticAreas") or []:  # disease details
                    name = area.get("name") if isinstance(area, dict) else None
                    if name and name not in concept.categories:
                        concept.categories.append(name)

            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OPENTARGETS] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Open Targets result: {e}")
            return None
