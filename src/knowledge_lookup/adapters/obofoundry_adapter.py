"""
OBO Foundry Knowledge Source Adapter

Integrates with OBO Foundry via OLS for ontology concept lookup.
"""

import logging
from typing import List, Optional, Dict, Any
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)


class OBOFoundryAdapter(KnowledgeSourceAdapter):
    """Adapter for OBO Foundry ontologies."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/ols/api"
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OBOFOUNDRY
    
    def is_available(self) -> bool:
        return True
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search OBO ontologies via OLS."""
        try:
            url = f"{self.base_url}/search"
            params = {
                'q': query,
                'rows': min(limit, 100),
                'format': 'json'
            }
            
            data = await self._make_request(url, params)
            
            concepts = []
            if 'response' in data and 'docs' in data['response']:
                for doc in data['response']['docs']:
                    # We can't easily filter by OBO Foundry in OLS search, 
                    # but many OBO ontologies are in OLS
                    concept = self._convert_obo_result_to_concept(doc)
                    if concept:
                        concepts.append(concept)
            
            logger.info(f"OBO search for '{query}' returned {len(concepts)} concepts")
            return concepts
            
        except Exception as e:
            logger.error(f"OBO search failed for '{query}': {e}")
            return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed information for OBO concepts."""
        return None
    
    def _convert_obo_result_to_concept(self, result: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert OBO result to unified concept."""
        try:
            obo_id = result.get('short_form', '')
            label = result.get('label', '')
            
            if not obo_id or not label:
                return None
            
            concept = UnifiedConcept(
                primary_id=obo_id,
                primary_label=label,
                concept_type=ConceptType.UNKNOWN
            )
            
            concept.add_identifier(
                KnowledgeSource.OBOFOUNDRY,
                obo_id,
                label,
                result.get('iri', '')
            )
            
            if 'ontology_name' in result:
                concept.categories.append(f"Ontology: {result['ontology_name']}")
            
            concept.confidence_score = 0.8
            concept.source_data[KnowledgeSource.OBOFOUNDRY] = result
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting OBO result: {e}")
            return None
