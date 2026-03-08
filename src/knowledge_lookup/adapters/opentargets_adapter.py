"""
Open Targets Knowledge Source Adapter

Integrates with Open Targets GraphQL API for drug target and disease lookup.
"""

import logging
from typing import List, Optional, Dict, Any
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

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
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
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
                "variables": {
                    "queryString": query
                }
            }
            
            data = await self._make_request(self.base_url, json_data=graphql_query)
            
            concepts = []
            if 'data' in data and 'search' in data['data'] and 'hits' in data['data']['search']:
                for hit in data['data']['search']['hits'][:limit]:
                    concept = self._convert_opentargets_result_to_concept(hit)
                    if concept:
                        concepts.append(concept)
            
            logger.info(f"Open Targets search for '{query}' returned {len(concepts)} concepts")
            return concepts
            
        except Exception as e:
            logger.error(f"Open Targets search failed for '{query}': {e}")
            return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed information from Open Targets."""
        try:
            # We need to know if it's a target or a disease
            # Usually EFO IDs are diseases, ENSG are targets
            entity_type = "disease" if concept_id.startswith('EFO_') or concept_id.startswith('MONDO_') or concept_id.startswith('ORPHA') else "target"
            
            graphql_query = {
                "query": f"""
                query Details($id: String!) {{
                  {entity_type}(id: $id) {{
                    id
                    name
                    description
                    {"approvedSymbol" if entity_type == "target" else ""}
                  }}
                }}
                """,
                "variables": {
                    "id": concept_id
                }
            }
            
            data = await self._make_request(self.base_url, json_data=graphql_query)
            
            if 'data' in data and entity_type in data['data'] and data['data'][entity_type]:
                concept = self._convert_opentargets_result_to_concept(data['data'][entity_type])
                return concept
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Open Targets concept details for '{concept_id}': {e}")
            return None
    
    def _convert_opentargets_result_to_concept(self, result: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert Open Targets API result to unified concept."""
        try:
            ot_id = result.get('id', '')
            label = result.get('name', ot_id)
            entity = result.get('entity', 'unknown')
            
            concept_type = ConceptType.DISEASE if entity == 'disease' else ConceptType.GENE
            
            concept = UnifiedConcept(
                primary_id=ot_id,
                primary_label=label,
                concept_type=concept_type
            )
            
            concept.add_identifier(
                KnowledgeSource.OPENTARGETS,
                ot_id,
                label,
                f"https://platform.opentargets.org/{entity}/{ot_id}"
            )
            
            if 'description' in result and result['description']:
                concept.definitions.append(result['description'])
            
            if 'approvedSymbol' in result:
                concept.synonyms.append(result['approvedSymbol'])
            
            concept.confidence_score = 0.9
            concept.source_data[KnowledgeSource.OPEN_TARGETS] = result
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting Open Targets result: {e}")
            return None
