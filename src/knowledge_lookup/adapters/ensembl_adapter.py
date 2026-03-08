"""
Ensembl Genome Database Adapter

Integrates with Ensembl REST API for gene and genomic feature lookup.
"""

import logging
from typing import List, Optional, Dict, Any
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)


class EnsemblAdapter(KnowledgeSourceAdapter):
    """Adapter for Ensembl."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.ensembl.org"
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ENSEMBL
    
    def is_available(self) -> bool:
        return True
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search Ensembl for genes."""
        try:
            # Ensembl doesn't have a direct "search all" by name that's easy to use for all species
            # We'll use the symbol lookup for human as a default or use the xrefs endpoint
            url = f"{self.base_url}/xrefs/symbol/homo_sapiens/{query}"
            params = {
                'content-type': 'application/json'
            }
            
            data = await self._make_request(url, params)
            
            concepts = []
            if isinstance(data, list):
                for result in data[:limit]:
                    concept = await self.get_concept_details(result.get('id', ''))
                    if concept:
                        concepts.append(concept)
            
            logger.info(f"Ensembl search for '{query}' returned {len(concepts)} concepts")
            return concepts
            
        except Exception as e:
            logger.error(f"Ensembl search failed for '{query}': {e}")
            return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed gene information from Ensembl."""
        try:
            # concept_id should be Ensembl ID (e.g., ENSG00000139618)
            url = f"{self.base_url}/lookup/id/{concept_id}"
            params = {
                'content-type': 'application/json',
                'expand': 1
            }
            
            data = await self._make_request(url, params)
            
            if data and 'id' in data:
                concept = self._convert_ensembl_result_to_concept(data)
                return concept
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Ensembl concept details for '{concept_id}': {e}")
            return None
    
    def _convert_ensembl_result_to_concept(self, result: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert Ensembl API result to unified concept."""
        try:
            ensembl_id = result.get('id', '')
            label = result.get('display_name', ensembl_id)
            
            concept = UnifiedConcept(
                primary_id=ensembl_id,
                primary_label=label,
                concept_type=ConceptType.GENE
            )
            
            concept.add_identifier(
                KnowledgeSource.ENSEMBL,
                ensembl_id,
                label,
                f"https://www.ensembl.org/id/{ensembl_id}"
            )
            
            if 'description' in result:
                concept.definitions.append(result['description'])
            
            if 'biotype' in result:
                concept.categories.append(f"Biotype: {result['biotype']}")
            
            if 'species' in result:
                concept.categories.append(f"Species: {result['species']}")
            
            concept.confidence_score = 1.0
            concept.source_data[KnowledgeSource.ENSEMBL] = result
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting Ensembl result: {e}")
            return None
