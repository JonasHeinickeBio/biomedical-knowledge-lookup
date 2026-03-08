"""
KEGG Knowledge Source Adapter

Integrates with KEGG API for biological pathways, diseases, and drugs lookup.
"""

import logging
from typing import List, Optional, Dict, Any
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)


class KEGGAdapter(KnowledgeSourceAdapter):
    """Adapter for KEGG."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.kegg.jp"
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.KEGG
    
    def is_available(self) -> bool:
        return True
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search KEGG for diseases or drugs."""
        try:
            # We'll search diseases first, then drugs
            concepts = []
            
            # Disease search
            ds_data = await self._make_request_text(f"{self.base_url}/find/disease/{query}")
            if ds_data:
                lines = ds_data.strip().split('\n')
                for line in lines[:limit]:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        kegg_id = parts[0].replace('ds:', '')
                        label = parts[1].split(';')[0]
                        concept = UnifiedConcept(
                            primary_id=kegg_id,
                            primary_label=label,
                            concept_type=ConceptType.DISEASE
                        )
                        concept.add_identifier(KnowledgeSource.KEGG, kegg_id, label)
                        concept.confidence_score = 0.8
                        concepts.append(concept)
            
            # Drug search (if we have space)
            if len(concepts) < limit:
                dr_data = await self._make_request_text(f"{self.base_url}/find/drug/{query}")
                if dr_data:
                    lines = dr_data.strip().split('\n')
                    for line in lines[:limit - len(concepts)]:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            kegg_id = parts[0].replace('dr:', '')
                            label = parts[1].split(';')[0]
                            concept = UnifiedConcept(
                                primary_id=kegg_id,
                                primary_label=label,
                                concept_type=ConceptType.DRUG
                            )
                            concept.add_identifier(KnowledgeSource.KEGG, kegg_id, label)
                            concept.confidence_score = 0.8
                            concepts.append(concept)
            
            logger.info(f"KEGG search for '{query}' returned {len(concepts)} concepts")
            return concepts
            
        except Exception as e:
            logger.error(f"KEGG search failed for '{query}': {e}")
            return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed information from KEGG."""
        try:
            # concept_id could be KEGG ID (e.g., H00001 for disease, D00001 for drug)
            prefix = "ds" if concept_id.startswith('H') else "dr"
            url = f"{self.base_url}/get/{prefix}:{concept_id}"
            data = await self._make_request_text(url)
            
            if data:
                # KEGG returns flat text, needs parsing
                concept = self._parse_kegg_text(concept_id, data)
                return concept
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get KEGG concept details for '{concept_id}': {e}")
            return None
            
    # Removed _make_request_raw as it's replaced by _make_request_text in base class

    def _parse_kegg_text(self, kegg_id: str, text: str) -> Optional[UnifiedConcept]:
        """Parse KEGG flat text format."""
        try:
            lines = text.strip().split('\n')
            label = ""
            description = ""
            concept_type = ConceptType.UNKNOWN
            
            if kegg_id.startswith('H'):
                concept_type = ConceptType.DISEASE
            elif kegg_id.startswith('D'):
                concept_type = ConceptType.DRUG
                
            for line in lines:
                if line.startswith('NAME'):
                    label = line[12:].split(';')[0].strip()
                elif line.startswith('DESCRIPTION'):
                    description = line[12:].strip()
            
            if not label:
                label = kegg_id
                
            concept = UnifiedConcept(
                primary_id=kegg_id,
                primary_label=label,
                concept_type=concept_type
            )
            
            concept.add_identifier(
                KnowledgeSource.KEGG,
                kegg_id,
                label,
                f"https://www.kegg.jp/dbget-bin/www_bget?{kegg_id}"
            )
            
            if description:
                concept.definitions.append(description)
                
            concept.confidence_score = 1.0
            concept.source_data[KnowledgeSource.KEGG] = text
            
            return concept
            
        except Exception as e:
            logger.error(f"Error parsing KEGG text: {e}")
            return None
