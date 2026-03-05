"""
Zooma Adapter for Central Knowledge Lookup

Provides access to EBI Zooma ontology annotation service for automatic 
text-to-ontology mapping and concept enrichment.
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Any, Set
from urllib.parse import quote_plus
from ..base import KnowledgeSourceAdapter
from ..models import (
    UnifiedConcept, ConceptIdentifier, KnowledgeSource, 
    ConceptType, LookupConfig
)

logger = logging.getLogger(__name__)


class ZoomaAdapter(KnowledgeSourceAdapter):
    """
    Adapter for EBI Zooma ontology annotation service.
    
    Zooma provides automatic annotation of free text to ontology terms,
    offering high-quality mappings with confidence scores and semantic types.
    
    Features:
    - Free text to ontology mapping
    - Confidence-based annotation scoring
    - Multiple ontology support
    - Filter by data sources and ontologies
    - Semantic type inference
    """
    
    def __init__(self, config: LookupConfig):
        """Initialize Zooma adapter."""
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/spot/zooma/v2/api"
        
        # Zooma confidence levels
        self.confidence_mapping = {
            "HIGH": 0.9,
            "GOOD": 0.8,
            "MEDIUM": 0.7,
            "LOW": 0.5,
            "NOT_FOUND": 0.0
        }
        
        # Common semantic type mappings for biological concepts
        self.semantic_type_mapping = {
            # Gene Ontology
            "GO": ConceptType.PATHWAY,
            # Human Phenotype Ontology
            "HP": ConceptType.PHENOTYPE,
            # Chemical Entities of Biological Interest
            "CHEBI": ConceptType.CHEMICAL,
            # Experimental Factor Ontology
            "EFO": ConceptType.PHENOTYPE,
            # Uberon anatomy ontology
            "UBERON": ConceptType.ANATOMY,
            # Cell Ontology
            "CL": ConceptType.ANATOMY,
            # Disease Ontology
            "DOID": ConceptType.DISEASE,
            # NCBI Taxonomy
            "NCBITaxon": ConceptType.ORGANISM,
            # Protein Ontology
            "PR": ConceptType.PROTEIN,
            # Sequence Ontology
            "SO": ConceptType.GENE,
            # Units of measurement
            "UO": ConceptType.UNKNOWN,
            # BRENDA tissue / enzyme source
            "BTO": ConceptType.ANATOMY,
            # Environment Ontology
            "ENVO": ConceptType.UNKNOWN
        }
    
    def get_source(self) -> KnowledgeSource:
        """Return the knowledge source this adapter handles."""
        return KnowledgeSource.ZOOMA
    
    def get_rate_limit(self) -> float:
        """Get rate limit for Zooma queries (requests per second)."""
        if self.config and self.config.rate_limits and KnowledgeSource.ZOOMA in self.config.rate_limits:
            return self.config.rate_limits[KnowledgeSource.ZOOMA]
        return 10.0  # Zooma doesn't specify strict rate limits, using conservative value
    
    async def search_concepts(self, query: str, limit: int = 20, property_type: Optional[str] = None) -> List[UnifiedConcept]:
        """
        Search for concepts using Zooma annotation service.
        
        Args:
            query: Text to annotate
            limit: Maximum number of results
            property_type: Optional property type (e.g., 'organism', 'disease')
            
        Returns:
            List of unified concepts with confidence scores
        """
        if not query or not query.strip():
            return []
        
        try:
            # Search annotations
            annotations = await self._search_annotations(query.strip(), limit, property_type)
            
            # Convert to unified concepts
            concepts = []
            for annotation in annotations:
                concept = self._convert_annotation_to_concept(annotation, query)
                if concept:
                    concepts.append(concept)
            
            # Sort by confidence score
            concepts.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return concepts[:limit]
            
        except Exception as e:
            logger.error(f"Error searching Zooma for '{query}': {e}")
            return []
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """
        Get detailed information about a specific concept.
        
        Args:
            concept_id: Concept identifier (ontology URI)
            
        Returns:
            Detailed concept information or None
        """
        try:
            # Extract ontology prefix and term ID from URI
            if "/" in concept_id:
                # Try to get additional details from the annotation
                details = await self._get_annotation_details(concept_id)
                if details:
                    return self._convert_annotation_to_concept(details, "")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Zooma concept details for '{concept_id}': {e}")
            return None
    
    async def _search_annotations(self, query: str, limit: int = 20, property_type: Optional[str] = None, 
                                 data_sources: Optional[List[str]] = None, ontologies: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for annotations using Zooma API."""
        # Build search URL with parameters
        url = f"{self.base_url}/services/annotate"
        params = {
            "propertyValue": query
        }
        
        # Add property type if specified
        if property_type:
            params["propertyType"] = property_type
        
        # Build filter parameter
        filter_parts = []
        
        # Handle data sources
        if data_sources:
            filter_parts.append(f"required:[{','.join(data_sources)}]")
        else:
            # Default: search OLS only for broader ontology coverage
            filter_parts.append("required:[none]")
        
        # Handle ontologies filter
        if ontologies:
            filter_parts.append(f"ontologies:[{','.join(ontologies)}]")
        else:
            # Default comprehensive ontology list
            default_ontologies = ["efo", "hp", "chebi", "go", "uberon", "cl", "doid", "ncbitaxon", "pr", "so"]
            filter_parts.append(f"ontologies:[{','.join(default_ontologies)}]")
        
        if filter_parts:
            params["filter"] = ",".join(filter_parts)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Limit results if needed
                    if isinstance(data, list) and len(data) > limit:
                        return data[:limit]
                    return data if isinstance(data, list) else []
                else:
                    logger.warning(f"Zooma API returned status {response.status} for query: {query}")
                    return []
    
    async def _get_annotation_details(self, concept_uri: str) -> Optional[Dict[str, Any]]:
        """Get detailed annotation information for a concept URI."""
        try:
            # Search for annotations that include this URI
            url = f"{self.base_url}/services/annotate"
            params = {
                "semanticTag": concept_uri,
                "limit": 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data[0] if data else None
                    
        except Exception as e:
            logger.error(f"Error getting annotation details for {concept_uri}: {e}")
        
        return None
    
    def _convert_annotation_to_concept(self, annotation: Dict[str, Any], query: str) -> Optional[UnifiedConcept]:
        """Convert Zooma annotation to UnifiedConcept."""
        try:
            # Extract semantic tags (ontology URIs)
            semantic_tags = annotation.get("semanticTags", [])
            if not semantic_tags:
                return None
            
            # Use the first semantic tag as primary ID
            primary_uri = semantic_tags[0]
            
            # Extract label from annotation
            annotated_property = annotation.get("annotatedProperty", {})
            property_value = annotated_property.get("propertyValue", query)
            
            # Extract confidence
            confidence_str = annotation.get("confidence", "MEDIUM")
            confidence_score = self.confidence_mapping.get(confidence_str, 0.7)
            
            # Determine concept type from ontology prefix
            concept_type = self._infer_concept_type(primary_uri)
            
            # Create unified concept
            concept = UnifiedConcept(
                primary_id=primary_uri,
                primary_label=property_value,
                concept_type=concept_type,
                confidence_score=confidence_score
            )
            
            # Add source information
            concept.sources.add(KnowledgeSource.ZOOMA)
            concept.source_data[KnowledgeSource.ZOOMA] = {
                "annotation_id": annotation.get("_links", {}).get("self", {}).get("href", ""),
                "confidence": confidence_str,
                "semantic_tags": semantic_tags,
                "annotated_property": annotated_property,
                "provenance": annotation.get("provenance", {}),
                "generated": annotation.get("generated", None),
                "derivedFrom": annotation.get("derivedFrom", {})
            }
            
            # Add identifiers for all semantic tags
            for i, tag in enumerate(semantic_tags):
                if i == 0:
                    continue  # Skip primary (already set)
                
                ontology_prefix = self._extract_ontology_prefix(tag)
                concept.add_identifier(
                    source=KnowledgeSource.ZOOMA,
                    identifier=tag,
                    label=f"Alternative mapping to {ontology_prefix}",
                    url=tag
                )
            
            # Add provenance information
            provenance = annotation.get("provenance", {})
            if provenance:
                source_info = provenance.get("source", {})
                concept.categories.append(f"Zooma:{source_info.get('name', 'Unknown')}")
                
                # Add evidence information
                evidence = provenance.get("evidence", "")
                if evidence:
                    concept.source_data[KnowledgeSource.ZOOMA]["evidence"] = evidence
            
            return concept
            
        except Exception as e:
            logger.error(f"Error converting Zooma annotation to concept: {e}")
            return None
    
    def _infer_concept_type(self, uri: str) -> ConceptType:
        """Infer concept type from ontology URI."""
        try:
            # Extract ontology prefix from URI
            ontology_prefix = self._extract_ontology_prefix(uri)
            
            # Map to concept type
            return self.semantic_type_mapping.get(ontology_prefix, ConceptType.UNKNOWN)
            
        except Exception:
            return ConceptType.UNKNOWN
    
    def _extract_ontology_prefix(self, uri: str) -> str:
        """Extract ontology prefix from URI."""
        try:
            # Common patterns for extracting ontology prefixes
            if "purl.obolibrary.org/obo/" in uri:
                # OBO format: http://purl.obolibrary.org/obo/GO_0008150
                term_part = uri.split("/obo/")[-1]
                return term_part.split("_")[0]
            elif "identifiers.org/" in uri:
                # Identifiers.org format: https://identifiers.org/go/GO:0008150
                return uri.split("/")[-2].upper()
            elif "ebi.ac.uk/efo/" in uri:
                return "EFO"
            elif "human-phenotype-ontology.org" in uri:
                return "HP"
            elif "ebi.ac.uk/chebi/" in uri:
                return "CHEBI"
            else:
                # Try to extract from path
                parts = uri.split("/")
                for part in reversed(parts):
                    if part and not part.startswith("obo") and "_" in part:
                        return part.split("_")[0]
                
                # Default fallback
                return "UNKNOWN"
                
        except Exception:
            return "UNKNOWN"
    
    async def search_by_ontology(self, query: str, ontologies: List[str], limit: int = 20, 
                                property_type: Optional[str] = None) -> List[UnifiedConcept]:
        """
        Search for concepts filtered by specific ontologies.
        
        Args:
            query: Search term
            ontologies: List of ontology prefixes (e.g., ['go', 'hp', 'chebi'])
            limit: Maximum number of results
            property_type: Optional property type filter
            
        Returns:
            List of unified concepts from specified ontologies
        """
        try:
            # Convert ontology names to lowercase for API
            ontology_filter = [ont.lower() for ont in ontologies]
            
            # Search with ontology filter
            annotations = await self._search_annotations(
                query, limit, property_type, ontologies=ontology_filter
            )
            
            concepts = []
            for annotation in annotations:
                concept = self._convert_annotation_to_concept(annotation, query)
                if concept:
                    concepts.append(concept)
            
            return sorted(concepts, key=lambda x: x.confidence_score, reverse=True)
                        
        except Exception as e:
            logger.error(f"Error searching Zooma by ontology for '{query}': {e}")
            return []
    
    async def get_property_types(self, limit: int = 50) -> List[str]:
        """Get list of available property types in Zooma."""
        try:
            url = f"{self.base_url}/properties/types"
            params = {"limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data if isinstance(data, list) else []
                    else:
                        logger.warning(f"Zooma property types endpoint returned status {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error getting property types from Zooma: {e}")
            return []
    
    async def search_with_data_sources(self, query: str, data_sources: List[str], 
                                     limit: int = 20, property_type: Optional[str] = None,
                                     preferred_sources: Optional[List[str]] = None) -> List[UnifiedConcept]:
        """
        Search for concepts using specific Zooma data sources.
        
        Args:
            query: Search term
            data_sources: List of data source names (e.g., ['atlas', 'gwas', 'cttv'])
            limit: Maximum number of results
            property_type: Optional property type filter
            preferred_sources: Optional list of preferred data sources for ranking
            
        Returns:
            List of unified concepts from specified data sources
        """
        try:
            # Search with data source filter
            annotations = await self._search_annotations(
                query, limit, property_type, data_sources=data_sources
            )
            
            concepts = []
            for annotation in annotations:
                concept = self._convert_annotation_to_concept(annotation, query)
                if concept:
                    # Add data source information
                    provenance = annotation.get("provenance", {})
                    source_info = provenance.get("source", {})
                    if source_info.get("name"):
                        concept.categories.append(f"Zooma-Source:{source_info['name']}")
                    concepts.append(concept)
            
            return sorted(concepts, key=lambda x: x.confidence_score, reverse=True)
                        
        except Exception as e:
            logger.error(f"Error searching Zooma with data sources for '{query}': {e}")
            return []
    
    async def close(self):
        """Clean up resources."""
        if self.session and not self.session.closed:
            await self.session.close()


# Utility functions for external use
async def annotate_text_with_zooma(text: str, ontologies: Optional[List[str]] = None, 
                                  limit: int = 10) -> List[UnifiedConcept]:
    """
    Convenience function to annotate text using Zooma.
    
    Args:
        text: Text to annotate
        ontologies: Optional list of ontologies to restrict search
        limit: Maximum number of annotations
        
    Returns:
        List of annotated concepts
    """
    config = LookupConfig()
    adapter = ZoomaAdapter(config)
    
    if ontologies:
        return await adapter.search_by_ontology(text, ontologies, limit)
    else:
        return await adapter.search_concepts(text, limit)


async def get_zooma_property_types(limit: int = 50) -> List[str]:
    """Get list of available property types in Zooma."""
    config = LookupConfig()
    adapter = ZoomaAdapter(config)
    return await adapter.get_property_types(limit)
