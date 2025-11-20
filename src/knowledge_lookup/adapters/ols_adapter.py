"""
OLS (Ontology Lookup Service) Adapter

Integrates with EMBL-EBI Ontology Lookup Service for concept lookup.
"""

import logging
from typing import List, Optional, Dict, Any
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)


class OLSAdapter(KnowledgeSourceAdapter):
    """Adapter for EMBL-EBI Ontology Lookup Service."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/ols/api"
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OLS
    
    def is_available(self) -> bool:
        return True  # OLS is publicly available
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search OLS for concepts."""
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
                for doc in data['response']['docs'][:limit]:
                    concept = self._convert_ols_result_to_concept(doc)
                    if concept:
                        concepts.append(concept)
            
            logger.info(f"OLS search for '{query}' returned {len(concepts)} concepts")
            return concepts
            
        except Exception as e:
            logger.error(f"OLS search failed for '{query}': {e}")
            return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed concept information from OLS."""
        try:
            # Extract ontology and term from IRI
            if 'http' in concept_id:
                # Parse IRI to get ontology and term
                parts = concept_id.split('/')
                if len(parts) >= 2:
                    # This is a simplified approach - real implementation would need proper IRI parsing
                    encoded_iri = concept_id.replace('/', '%2F').replace(':', '%3A')
                    url = f"{self.base_url}/terms/{encoded_iri}"
                else:
                    return None
            else:
                return None
            
            data = await self._make_request(url)
            concept = self._convert_ols_concept_to_unified(data)
            return concept
            
        except Exception as e:
            logger.error(f"Failed to get OLS concept details for '{concept_id}': {e}")
            return None
    
    def _convert_ols_result_to_concept(self, result: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert OLS search result to unified concept."""
        try:
            concept_id = result.get('iri', '')
            label = result.get('label', '')
            
            if not concept_id or not label:
                return None
            
            # Determine concept type from ontology
            ontology = result.get('ontology_name', '')
            concept_type = self._determine_concept_type_from_ontology(ontology)
            
            concept = UnifiedConcept(
                primary_id=concept_id,
                primary_label=label,
                concept_type=concept_type
            )
            
            # Add OLS identifier
            concept.add_identifier(
                KnowledgeSource.OLS,
                concept_id,
                label,
                concept_id
            )
            
            # Add synonyms
            if 'synonym' in result:
                synonyms = result['synonym']
                if isinstance(synonyms, list):
                    concept.synonyms.extend(synonyms)
                else:
                    concept.synonyms.append(synonyms)
            
            # Add description
            if 'description' in result:
                descriptions = result['description']
                if isinstance(descriptions, list):
                    concept.definitions.extend(descriptions)
                else:
                    concept.definitions.append(descriptions)
            
            # Add ontology information
            if 'ontology_name' in result:
                concept.categories.append(result['ontology_name'])
            
            # Add short form (often more readable ID)
            if 'short_form' in result:
                concept.add_identifier(
                    KnowledgeSource.OLS,
                    result['short_form'],
                    label
                )
            
            concept.confidence_score = 0.8
            concept.source_data[KnowledgeSource.OLS] = result
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting OLS result: {e}")
            return None
    
    def _convert_ols_concept_to_unified(self, data: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert detailed OLS concept to unified concept."""
        try:
            concept_id = data.get('iri', '')
            label = data.get('label', '')
            
            if not concept_id or not label:
                return None
            
            concept = UnifiedConcept(
                primary_id=concept_id,
                primary_label=label,
                concept_type=ConceptType.UNKNOWN
            )
            
            # Add OLS identifier
            concept.add_identifier(
                KnowledgeSource.OLS,
                concept_id,
                label,
                concept_id
            )
            
            # Add synonyms
            if 'synonyms' in data:
                concept.synonyms.extend(data['synonyms'])
            
            # Add definitions
            if 'description' in data:
                descriptions = data['description']
                if isinstance(descriptions, list):
                    concept.definitions.extend(descriptions)
                else:
                    concept.definitions.append(descriptions)
            
            # Add hierarchical relationships from _links if available
            if '_links' in data:
                links = data['_links']
                if 'parents' in links:
                    # Would need to make additional requests to get parent IRIs
                    pass
                if 'children' in links:
                    # Would need to make additional requests to get children IRIs
                    pass
            
            concept.confidence_score = 0.85
            concept.source_data[KnowledgeSource.OLS] = data
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting OLS concept: {e}")
            return None
    
    def _determine_concept_type_from_ontology(self, ontology: str) -> ConceptType:
        """Determine concept type from OLS ontology name."""
        ontology_lower = ontology.lower()
        
        # Map OLS ontologies to concept types
        if ontology_lower in ['doid', 'mondo', 'ordo', 'hp']:
            return ConceptType.DISEASE
        elif ontology_lower in ['chebi', 'drugbank']:
            return ConceptType.DRUG
        elif ontology_lower in ['go', 'so', 'pr']:
            return ConceptType.GENE
        elif ontology_lower in ['uberon', 'fma', 'ma']:
            return ConceptType.ANATOMY
        elif ontology_lower in ['hp', 'mp', 'zp']:
            return ConceptType.PHENOTYPE
        elif ontology_lower in ['chebi']:
            return ConceptType.CHEMICAL
        elif ontology_lower in ['ncbitaxon']:
            return ConceptType.ORGANISM
        
        return ConceptType.UNKNOWN
