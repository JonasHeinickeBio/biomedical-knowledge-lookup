"""
Wikidata Knowledge Source Adapter

Integrates with Wikidata SPARQL endpoint for concept lookup.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import quote
from ..base import KnowledgeSourceAdapter
from ..models import UnifiedConcept, KnowledgeSource, ConceptType, LookupConfig

logger = logging.getLogger(__name__)


class WikidataAdapter(KnowledgeSourceAdapter):
    """Adapter for Wikidata."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.sparql_endpoint = "https://query.wikidata.org/sparql"
        self.entity_endpoint = "https://www.wikidata.org/w/api.php"
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.WIKIDATA
    
    def is_available(self) -> bool:
        return True  # Wikidata is publicly available
    
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search Wikidata for concepts using SPARQL with performance optimizations."""
        try:
            # Escape query for SPARQL
            escaped_query = query.replace('"', '\\"').replace("'", "\\'")
            
            # Limit results to improve performance
            optimized_limit = min(limit, 5)  # Reduce limit for faster response
            
            # Use optimized simple query
            return await self._search_with_optimized_query(escaped_query, optimized_limit)
            
        except Exception as e:
            logger.error(f"Wikidata search failed for '{query}': {e}")
            return []
    
    async def _search_with_optimized_query(self, escaped_query: str, limit: int) -> List[UnifiedConcept]:
        """Search with highly optimized SPARQL query for speed."""
        # Ultra-minimal query focused on speed
        sparql_query = f"""
        SELECT ?entity ?entityLabel WHERE {{
          ?entity rdfs:label ?entityLabel .
          FILTER(CONTAINS(LCASE(?entityLabel), LCASE("{escaped_query}")))
          FILTER(LANG(?entityLabel) = "en")
        }}
        LIMIT {limit}
        """
        
        return await self._execute_sparql_query_fast(sparql_query, limit)
    
    async def _search_with_simple_query(self, escaped_query: str, limit: int) -> List[UnifiedConcept]:
        """Search with minimal SPARQL query to avoid timeouts."""
        # Very simple query - just find entities with matching labels
        sparql_query = f"""
        SELECT ?entity ?entityLabel WHERE {{
          ?entity rdfs:label ?entityLabel .
          FILTER(CONTAINS(LCASE(?entityLabel), LCASE("{escaped_query}")))
          FILTER(LANG(?entityLabel) = "en")
        }}
        LIMIT {min(limit, 10)}
        """
        
        return await self._execute_sparql_query(sparql_query, limit)
    
    async def _execute_sparql_query_fast(self, sparql_query: str, limit: int) -> List[UnifiedConcept]:
        """Execute SPARQL query with aggressive timeout and optimizations."""
        params = {
            'query': sparql_query,
            'format': 'json'
        }
        
        headers = {
            'User-Agent': 'AID-PAIS-KnowledgeGraph/1.0 (https://github.com/Jonasjjj96/AID-PAIS-KnowledgeGraph)',
            'Accept': 'application/sparql-results+json',
            'Connection': 'close'  # Don't keep connection alive
        }
        
        # Use very short timeout for fast response
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=5.0)  # 5 second timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(self.sparql_endpoint, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Wikidata SPARQL returned status {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    concepts = []
                    if 'results' in data and 'bindings' in data['results']:
                        # Process only first few results for speed
                        bindings = data['results']['bindings'][:min(limit, 3)]
                        for binding in bindings:
                            concept = self._convert_wikidata_result_to_concept(binding)
                            if concept:
                                concepts.append(concept)
                    
                    logger.info(f"Wikidata fast query returned {len(concepts)} concepts")
                    return concepts
                    
            except asyncio.TimeoutError:
                logger.warning("Wikidata SPARQL query timed out (fast mode)")
                return []
            except Exception as e:
                logger.error(f"Wikidata SPARQL query failed (fast mode): {e}")
                return []
    
    async def _execute_sparql_query(self, sparql_query: str, limit: int) -> List[UnifiedConcept]:
        """Execute SPARQL query and convert results with shorter timeout."""
        params = {
            'query': sparql_query,
            'format': 'json'
        }
        
        headers = {
            'User-Agent': 'AID-PAIS-KnowledgeGraph/1.0 (https://github.com/Jonasjjj96/AID-PAIS-KnowledgeGraph)',
            'Accept': 'application/sparql-results+json'
        }
        
        # Use shorter timeout for Wikidata
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=10.0)  # 10 second timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(self.sparql_endpoint, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Wikidata SPARQL returned status {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    concepts = []
                    if 'results' in data and 'bindings' in data['results']:
                        for binding in data['results']['bindings'][:limit]:
                            concept = self._convert_wikidata_result_to_concept(binding)
                            if concept:
                                concepts.append(concept)
                    
                    logger.info(f"Wikidata SPARQL query returned {len(concepts)} concepts")
                    return concepts
                    
            except asyncio.TimeoutError:
                logger.warning("Wikidata SPARQL query timed out")
                return []
            except Exception as e:
                logger.error(f"Wikidata SPARQL query failed: {e}")
                return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed concept information from Wikidata."""
        try:
            # Extract Q-ID from URI if necessary
            if 'http' in concept_id:
                qid = concept_id.split('/')[-1]
            else:
                qid = concept_id
            
            if not qid.startswith('Q'):
                return None
            
            # Use Wikidata API to get entity details
            params = {
                'action': 'wbgetentities',
                'ids': qid,
                'format': 'json',
                'languages': 'en'
            }
            
            headers = {
                'User-Agent': 'AID-PAIS-KnowledgeGraph/1.0 (https://github.com/Jonasjjj96/AID-PAIS-KnowledgeGraph)',
                'Accept': 'application/json'
            }
            
            data = await self._make_request(self.entity_endpoint, params, headers)
            
            if 'entities' in data and qid in data['entities']:
                entity_data = data['entities'][qid]
                # Check if entity exists and is not missing
                if entity_data.get('missing') != True:
                    concept = self._convert_wikidata_entity_to_unified(entity_data)
                    return concept
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Wikidata concept details for '{concept_id}': {e}")
            return None
    
    def _convert_wikidata_result_to_concept(self, result: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert Wikidata SPARQL result to unified concept."""
        try:
            if 'entity' not in result or 'entityLabel' not in result:
                return None
            
            entity_uri = result['entity']['value']
            entity_id = entity_uri.split('/')[-1]
            label = result['entityLabel']['value']
            
            # For simple queries, we don't have instance type information
            concept_type = ConceptType.UNKNOWN
            
            concept = UnifiedConcept(
                primary_id=entity_id,
                primary_label=label,
                concept_type=concept_type
            )
            
            # Add source to the sources set
            concept.sources.add(KnowledgeSource.WIKIDATA)
            
            # Add description if available (may not be present in simple query)
            if 'entityDescription' in result and result['entityDescription']:
                description = result['entityDescription']['value']
                concept.definitions.append(description)
            
            # Add instance of information if available
            if 'instanceOfLabel' in result and result['instanceOfLabel']:
                instance_of = result['instanceOfLabel']['value']
                concept.categories.append(instance_of)
                # Try to determine concept type from instance
                concept.concept_type = self._determine_concept_type_from_instance_of(instance_of.lower())
            
            concept.confidence_score = 0.6  # Lower confidence for simple queries
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting Wikidata result: {e}")
            return None
    
    def _convert_wikidata_entity_to_unified(self, entity_data: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert detailed Wikidata entity to unified concept."""
        try:
            entity_id = entity_data.get('id', '')
            
            # Get label
            label = ''
            if 'labels' in entity_data and 'en' in entity_data['labels']:
                label = entity_data['labels']['en']['value']
            
            if not entity_id or not label:
                return None
            
            concept = UnifiedConcept(
                primary_id=entity_id,
                primary_label=label,
                concept_type=ConceptType.UNKNOWN
            )
            
            # Add source to the sources set
            concept.sources.add(KnowledgeSource.WIKIDATA)
            
            # Add description
            if 'descriptions' in entity_data and 'en' in entity_data['descriptions']:
                description = entity_data['descriptions']['en']['value']
                concept.definitions.append(description)
            
            # Add aliases as synonyms
            if 'aliases' in entity_data and 'en' in entity_data['aliases']:
                for alias in entity_data['aliases']['en']:
                    concept.synonyms.append(alias['value'])
            
            # Process claims for additional information
            if 'claims' in entity_data:
                self._process_wikidata_claims(concept, entity_data['claims'])
            
            concept.confidence_score = 0.75
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting Wikidata entity: {e}")
            return None
    
    def _process_wikidata_claims(self, concept: UnifiedConcept, claims: Dict[str, Any]):
        """Process Wikidata claims to extract relevant information."""
        try:
            # P31 - instance of
            if 'P31' in claims:
                for claim in claims['P31']:
                    if ('mainsnak' in claim and 
                        'datavalue' in claim['mainsnak'] and 
                        'value' in claim['mainsnak']['datavalue'] and
                        'id' in claim['mainsnak']['datavalue']['value']):
                        instance_of_id = claim['mainsnak']['datavalue']['value']['id']
                        concept.categories.append(instance_of_id)
            
            # P279 - subclass of (parents)
            if 'P279' in claims:
                for claim in claims['P279']:
                    if ('mainsnak' in claim and 
                        'datavalue' in claim['mainsnak'] and 
                        'value' in claim['mainsnak']['datavalue'] and
                        'id' in claim['mainsnak']['datavalue']['value']):
                        parent_id = claim['mainsnak']['datavalue']['value']['id']
                        concept.parents.append(parent_id)
            
            # P486 - MeSH descriptor ID
            if 'P486' in claims:
                for claim in claims['P486']:
                    if ('mainsnak' in claim and 
                        'datavalue' in claim['mainsnak'] and 
                        'value' in claim['mainsnak']['datavalue']):
                        mesh_id = claim['mainsnak']['datavalue']['value']
                        concept.add_identifier(KnowledgeSource.UMLS, mesh_id, concept.primary_label)
            
        except Exception as e:
            logger.error(f"Error processing Wikidata claims: {e}")
    
    def _determine_concept_type_from_instance_of(self, instance_of: str) -> ConceptType:
        """Determine concept type from Wikidata 'instance of' property."""
        instance_lower = instance_of.lower()
        
        # Map Wikidata concepts to biological concept types
        if any(term in instance_lower for term in ['disease', 'disorder', 'syndrome', 'condition']):
            return ConceptType.DISEASE
        elif any(term in instance_lower for term in ['symptom', 'sign']):
            return ConceptType.SYMPTOM
        elif any(term in instance_lower for term in ['drug', 'medication', 'pharmaceutical']):
            return ConceptType.DRUG
        elif any(term in instance_lower for term in ['gene', 'genetic']):
            return ConceptType.GENE
        elif any(term in instance_lower for term in ['protein', 'enzyme']):
            return ConceptType.PROTEIN
        elif any(term in instance_lower for term in ['anatomy', 'organ', 'body part']):
            return ConceptType.ANATOMY
        elif any(term in instance_lower for term in ['chemical', 'compound', 'substance']):
            return ConceptType.CHEMICAL
        elif any(term in instance_lower for term in ['species', 'organism', 'taxon']):
            return ConceptType.ORGANISM
        elif any(term in instance_lower for term in ['procedure', 'therapy', 'treatment']):
            return ConceptType.PROCEDURE
        
        return ConceptType.UNKNOWN
