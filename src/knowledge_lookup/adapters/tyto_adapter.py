"""
Tyto Knowledge Source Adapter

Integrates with Tyto library for ontology lookup.
"""

import logging
from typing import List, Optional, Dict, Any
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)

try:
    import tyto
except ImportError:
    tyto = None
    logger.warning("Tyto library not available. Install with: pip install tyto")


class TytoAdapter(KnowledgeSourceAdapter):
    """Adapter for Tyto."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.TYTO
    
    def is_available(self) -> bool:
        return tyto is not None
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Tyto doesn't have a broad search across all ontologies easily."""
        return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get details for a URI using tyto."""
        if not tyto:
            return None
            
        try:
            # Tyto usually works with URIs
            if not concept_id.startswith('http'):
                return None
                
            # Use tyto to get label
            label = tyto.get_label(concept_id)
            if not label:
                return None
                
            concept = UnifiedConcept(
                primary_id=concept_id,
                primary_label=label,
                concept_type=ConceptType.UNKNOWN
            )
            
            concept.add_identifier(
                KnowledgeSource.TYTO,
                concept_id,
                label,
                concept_id
            )
            
            concept.confidence_score = 1.0
            return concept
            
        except Exception as e:
            logger.error(f"Tyto lookup failed for '{concept_id}': {e}")
            return None
