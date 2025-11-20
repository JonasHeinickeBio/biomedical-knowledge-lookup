"""
Tyto Adapter for Central Knowledge Lookup

Provides access to hundreds of ontologies through Tyto library which interfaces
with Ontobee and EBI Ontology Lookup Service.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from ..base import KnowledgeSourceAdapter
from ..models import (
    UnifiedConcept, ConceptIdentifier, KnowledgeSource, 
    ConceptType, LookupConfig
)

logger = logging.getLogger(__name__)

try:
    import tyto  # type: ignore
    TYTO_AVAILABLE = True
except ImportError:
    tyto = None  # type: ignore
    TYTO_AVAILABLE = False
    logger.warning("Tyto library not available. Install with: pip install tyto")


class TytoAdapter(KnowledgeSourceAdapter):
    """
    Adapter for Tyto library providing access to hundreds of ontologies.
    
    Tyto provides access to:
    - Sequence Ontology (SO)
    - Systems Biology Ontology (SBO) 
    - NCBI Taxonomy
    - National Cancer Institute Thesaurus (NCIT)
    - Ontology of Units of Measure (OM)
    - EDAM (bioinformatics operations and data types)
    - PubChem
    - And hundreds more through Ontobee and EBI OLS
    """
    
    def __init__(self, config: LookupConfig):
        """Initialize Tyto adapter."""
        super().__init__(config)
        
        # Built-in ontologies provided by Tyto
        self.builtin_ontologies = {
            'SO': None,     # Sequence Ontology
            'SBO': None,    # Systems Biology Ontology
            'NCBITaxon': None,  # NCBI Taxonomy
            'NCIT': None,   # National Cancer Institute Thesaurus
            'OM': None,     # Ontology of Units of Measure
            'EDAM': None,   # EDAM bioinformatics ontology
            'PubChem': None # PubChem
        }
        
        # Additional ontologies (will be loaded on demand)
        self.custom_ontologies: Dict[str, Any] = {}
        
        # Cache for available ontologies from EBI OLS
        self.available_ontologies: Optional[Dict[str, str]] = None
        
        # Pre-built cache of common biological terms for ultra-fast lookup
        self.term_cache = self._build_term_cache()
        
        if TYTO_AVAILABLE:
            self._initialize_builtin_ontologies()
    
    def _build_term_cache(self) -> Dict[str, Dict[str, str]]:
        """Build a comprehensive cache of biological terms for ultra-fast lookup."""
        cache = {
            'SO': {  # Sequence Ontology - DNA/RNA/Gene terms
                'gene': 'https://identifiers.org/SO:0000704',
                'promoter': 'https://identifiers.org/SO:0000167', 
                'exon': 'https://identifiers.org/SO:0000147',
                'intron': 'https://identifiers.org/SO:0000188',
                'dna': 'https://identifiers.org/SO:0000352',
                'rna': 'https://identifiers.org/SO:0000356',
                'mrna': 'https://identifiers.org/SO:0000234',
                'protein_coding_gene': 'https://identifiers.org/SO:0001217',
                'transcription': 'https://identifiers.org/SO:0000673',
                'translation': 'https://identifiers.org/SO:0000109',
                'chromosome': 'https://identifiers.org/SO:0000340',
                'plasmid': 'https://identifiers.org/SO:0000155',
                'sequence': 'https://identifiers.org/SO:0000001',
                'mutation': 'https://identifiers.org/SO:0001059',
                'insertion': 'https://identifiers.org/SO:0000667',
                'deletion': 'https://identifiers.org/SO:0000159'
            },
            'SBO': {  # Systems Biology Ontology - Processes/Reactions/Entities
                'enzyme': 'https://identifiers.org/SBO:0000014',
                'protein': 'https://identifiers.org/SBO:0000252',
                'metabolite': 'https://identifiers.org/SBO:0000247',
                'reaction': 'https://identifiers.org/SBO:0000176',
                'pathway': 'https://identifiers.org/SBO:0000375',
                'complex': 'https://identifiers.org/SBO:0000253',
                'metabolism': 'https://identifiers.org/SBO:0000375',
                'binding': 'https://identifiers.org/SBO:0000177',
                'transport': 'https://identifiers.org/SBO:0000185',
                'regulation': 'https://identifiers.org/SBO:0000168',
                'inhibition': 'https://identifiers.org/SBO:0000169',
                'activation': 'https://identifiers.org/SBO:0000170',
                'signal': 'https://identifiers.org/SBO:0000633',
                'process': 'https://identifiers.org/SBO:0000375'
            },
            'NCIT': {  # National Cancer Institute Thesaurus - Medical/Disease terms
                'disease': 'https://identifiers.org/ncit:C2991',
                'cancer': 'https://identifiers.org/ncit:C9305',
                'protein': 'https://identifiers.org/ncit:C17021',
                'pathway': 'https://identifiers.org/ncit:C54214',
                'cell': 'https://identifiers.org/ncit:C12508',
                'tissue': 'https://identifiers.org/ncit:C12801',
                'organism': 'https://identifiers.org/ncit:C14250',
                'drug': 'https://identifiers.org/ncit:C1908',
                'therapy': 'https://identifiers.org/ncit:C49236',
                'diagnosis': 'https://identifiers.org/ncit:C15220',
                'symptom': 'https://identifiers.org/ncit:C100104',
                'syndrome': 'https://identifiers.org/ncit:C84442',
                'tumor': 'https://identifiers.org/ncit:C3262',
                'metastasis': 'https://identifiers.org/ncit:C3261',
                'malignant': 'https://identifiers.org/ncit:C14174',
                'benign': 'https://identifiers.org/ncit:C14175'
            },
            'EDAM': {  # EDAM bioinformatics ontology - Computational biology
                'sequence': 'https://identifiers.org/edam:data_2044',
                'protein': 'https://identifiers.org/edam:data_1467',
                'dna': 'https://identifiers.org/edam:data_2977',
                'alignment': 'https://identifiers.org/edam:data_1383',
                'structure': 'https://identifiers.org/edam:data_0883',
                'annotation': 'https://identifiers.org/edam:data_0928',
                'expression': 'https://identifiers.org/edam:data_2603',
                'phylogeny': 'https://identifiers.org/edam:data_0872',
                'genome': 'https://identifiers.org/edam:data_2711',
                'database': 'https://identifiers.org/edam:data_0006',
                'analysis': 'https://identifiers.org/edam:operation_2945'
            }
        }
        
        # Add common biological term variations
        expanded_cache = {}
        for ontology, terms in cache.items():
            expanded_cache[ontology] = dict(terms)  # Copy original
            
            # Add common variations
            for term, uri in terms.items():
                # Add plural forms
                if not term.endswith('s'):
                    expanded_cache[ontology][f"{term}s"] = uri
                
                # Add underscore versions
                if ' ' in term:
                    expanded_cache[ontology][term.replace(' ', '_')] = uri
                
                # Add hyphen versions  
                if '_' in term:
                    expanded_cache[ontology][term.replace('_', '-')] = uri
        
        return expanded_cache
    
    def get_source(self) -> KnowledgeSource:
        """Return the knowledge source this adapter handles."""
        return KnowledgeSource.TYTO

    def _initialize_builtin_ontologies(self):
        """Initialize built-in Tyto ontologies."""
        if not TYTO_AVAILABLE or not tyto:
            return
            
        try:
            # Initialize available ontologies safely
            available_ontologies = []
            
            # Check each ontology individually
            ontology_checks = [
                ('SO', 'tyto.SO'),
                ('SBO', 'tyto.SBO'),
                ('NCBITaxon', 'tyto.NCBITaxon'),
                ('NCIT', 'tyto.NCIT'),
                ('OM', 'tyto.OM'),
                ('EDAM', 'tyto.EDAM'),
                ('PubChem', 'tyto.PubChem')
            ]
            
            for onto_name, onto_attr in ontology_checks:
                try:
                    # Try to access the ontology attribute
                    ontology = getattr(tyto, onto_name, None)
                    if ontology is not None:
                        self.builtin_ontologies[onto_name] = ontology
                        available_ontologies.append(onto_name)
                    else:
                        logger.warning(f"Tyto ontology {onto_name} not available")
                        self.builtin_ontologies[onto_name] = None
                except AttributeError:
                    logger.warning(f"Tyto ontology {onto_name} not accessible")
                    self.builtin_ontologies[onto_name] = None
                except Exception as e:
                    logger.warning(f"Error accessing Tyto ontology {onto_name}: {e}")
                    self.builtin_ontologies[onto_name] = None
            
            logger.info(f"Initialized Tyto ontologies: {available_ontologies}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Tyto ontologies: {e}")
    
    def is_available(self) -> bool:
        """Check if Tyto adapter is available."""
        return TYTO_AVAILABLE
    
    def get_rate_limit(self) -> float:
        """Get rate limit for Tyto queries (requests per second)."""
        return 10.0  # Increased rate limit for faster concurrent processing
    
    async def search_concepts(self, query: str, limit: int = 50) -> List[UnifiedConcept]:
        """
        Search for concepts across Tyto ontologies with ultra-fast caching.
        
        Args:
            query: Search term
            limit: Maximum number of results
            
        Returns:
            List of unified concepts
        """
        if not TYTO_AVAILABLE:
            return []
        
        # Use pure cache-based search for maximum speed
        concepts = self._search_from_cache_only(query, limit)
        
        # If cache search found results, return immediately
        if concepts:
            return concepts
        
        # Only fall back to ontology access if absolutely no cache hits
        # and we really need to find something
        if len(concepts) < limit // 2:  # Only if we really need more results
            fallback_concepts = await self._search_ontology_fallback(query, limit - len(concepts))
            concepts.extend(fallback_concepts)
        
        return concepts[:limit]
    
    def _search_from_cache_only(self, query: str, limit: int) -> List[UnifiedConcept]:
        """Ultra-fast search using only cached terms - no network calls."""
        concepts = []
        query_variations = self._generate_query_variations(query)
        
        # Search all ontology caches
        for ontology_name, cache in self.term_cache.items():
            for variation in query_variations:
                clean_var = variation.lower().replace(' ', '_').replace('-', '_')
                if clean_var in cache:
                    uri = cache[clean_var]
                    concept = self._create_concept_from_cache(uri, variation, ontology_name)
                    if concept:
                        concepts.append(concept)
                        if len(concepts) >= limit:
                            return concepts
        
        return concepts
    
    async def _search_ontology_fallback(self, query: str, limit: int) -> List[UnifiedConcept]:
        """Fallback search with minimal ontology access."""
        concepts = []
        query_variations = self._generate_query_variations(query)[:2]  # Limit variations
        
        # Only check a few ontologies to avoid too many network calls
        priority_ontologies = ['SO', 'SBO', 'NCIT']  # Most commonly useful
        
        for ontology_name in priority_ontologies:
            if ontology_name in self.builtin_ontologies and len(concepts) < limit:
                try:
                    ontology_concepts = await self._search_ontology_fast(
                        self.builtin_ontologies[ontology_name], 
                        query_variations, 
                        ontology_name, 
                        1  # Just 1 result per ontology for speed
                    )
                    concepts.extend(ontology_concepts)
                except Exception as e:
                    logger.debug(f"Fallback search failed for {ontology_name}: {e}")
                    continue
        
        return concepts

    def _generate_query_variations(self, query: str) -> List[str]:
        """Generate common query variations for efficient searching."""
        variations = [query]
        
        # Common transformations
        if ' ' in query:
            variations.append(query.replace(' ', '_'))
        if '_' in query:
            variations.append(query.replace('_', ' '))
        
        # Case variations
        variations.extend([
            query.lower(),
            query.upper(), 
            query.title(),
            query.lower().replace(' ', '_'),
            query.upper().replace(' ', '_')
        ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for var in variations:
            if var not in seen:
                seen.add(var)
                unique_variations.append(var)
        
        return unique_variations
    
    async def _search_ontology_fast(self, ontology: Any, query_variations: List[str], 
                                   ontology_name: str, max_results: int) -> List[UnifiedConcept]:
        """Ultra-fast search using cached terms first, then ontology access."""
        concepts = []
        
        # First, check our pre-built cache (fastest path)
        if ontology_name in self.term_cache:
            cache = self.term_cache[ontology_name]
            for variation in query_variations[:3]:
                clean_var = variation.lower().replace(' ', '_').replace('-', '_')
                if clean_var in cache:
                    uri = cache[clean_var]
                    concept = self._create_concept_from_cache(uri, variation, ontology_name)
                    if concept:
                        concepts.append(concept)
                        if len(concepts) >= max_results:
                            return concepts
        
        # If not in cache, try direct ontology access (but limit to avoid network calls)
        for variation in query_variations[:2]:  # Limit to top 2 variations
            try:
                clean_var = variation.lower().replace(' ', '_').replace('-', '_')
                
                # Only check if attribute exists (don't access it to avoid network)
                if hasattr(ontology, clean_var):
                    # Generate expected URI pattern
                    if ontology_name == 'SO':
                        uri = f"https://identifiers.org/SO:{clean_var}"
                    elif ontology_name == 'SBO':
                        uri = f"https://identifiers.org/SBO:{clean_var}" 
                    elif ontology_name == 'NCIT':
                        uri = f"https://identifiers.org/ncit:{clean_var}"
                    elif ontology_name == 'EDAM':
                        uri = f"https://identifiers.org/edam:{clean_var}"
                    else:
                        uri = f"https://identifiers.org/{ontology_name.lower()}:{clean_var}"
                    
                    concept = self._create_concept_from_cache(uri, variation, ontology_name)
                    if concept:
                        concepts.append(concept)
                        if len(concepts) >= max_results:
                            break
            except Exception:
                continue
        
        return concepts
    
    def _create_concept_from_cache(self, uri: str, label: str, ontology_name: str) -> Optional[UnifiedConcept]:
        """Ultra-fast concept creation without network calls."""
        if not uri or not isinstance(uri, str):
            return None
        
        # Use cached type inference only
        concept_type = self._infer_type_from_label(label)
        
        concept = UnifiedConcept(
            primary_id=uri,
            primary_label=label,
            concept_type=concept_type,
            confidence_score=0.9  # High confidence for direct ontology matches
        )
        
        # Add source data without expensive lookups
        concept.source_data[KnowledgeSource.TYTO] = {
            'ontology': ontology_name,
            'namespace': ontology_name,
            'source_uri': uri,
            'match_type': 'cached'
        }
        
        concept.add_identifier(KnowledgeSource.TYTO, uri, label)
        return concept
    
    async def _create_concept_from_uri_fast(self, uri: str, label: str, ontology_name: str) -> Optional[UnifiedConcept]:
        """Fast concept creation with minimal processing."""
        if not uri or not isinstance(uri, str):
            return None
        
        # Skip expensive API calls for faster response
        concept_type = self._infer_type_from_label(label)
        
        concept = UnifiedConcept(
            primary_id=uri,
            primary_label=label,
            concept_type=concept_type,
            confidence_score=0.9  # High confidence for direct ontology matches
        )
        
        # Add source data
        concept.source_data[KnowledgeSource.TYTO] = {
            'ontology': ontology_name,
            'namespace': ontology_name,
            'source_uri': uri,
            'match_type': 'direct'
        }
        
        concept.add_identifier(KnowledgeSource.TYTO, uri, label)
        return concept
    
    def _infer_type_from_label(self, label: str) -> ConceptType:
        """Fast type inference from label without external API calls."""
        label_lower = label.lower()
        
        # Quick pattern matching for common biological terms
        if any(term in label_lower for term in ['gene', 'genetic', 'dna', 'rna']):
            return ConceptType.GENE
        elif any(term in label_lower for term in ['protein', 'enzyme', 'peptide']):
            return ConceptType.PROTEIN
        elif any(term in label_lower for term in ['disease', 'cancer', 'syndrome', 'disorder']):
            return ConceptType.DISEASE
        elif any(term in label_lower for term in ['pathway', 'process', 'regulation']):
            return ConceptType.PATHWAY
        elif any(term in label_lower for term in ['cell', 'tissue', 'organ', 'anatomy']):
            return ConceptType.ANATOMY
        elif any(term in label_lower for term in ['drug', 'compound', 'chemical', 'molecule']):
            return ConceptType.CHEMICAL
        elif any(term in label_lower for term in ['procedure', 'method', 'technique', 'assay']):
            return ConceptType.PROCEDURE
        else:
            return ConceptType.UNKNOWN

    async def _search_in_ontology(self, ontology: Any, term: str, ontology_name: str) -> Optional[str]:
        """Search for a term in a specific ontology."""
        try:
            # Try as attribute (most common case)
            if hasattr(ontology, term.lower().replace(' ', '_')):
                return getattr(ontology, term.lower().replace(' ', '_'))
            
            # Try as subscript (for special characters)
            try:
                return ontology[term]
            except (KeyError, TypeError):
                pass
            
            # Try case variations
            for variation in [term.upper(), term.lower(), term.title()]:
                try:
                    clean_variation = variation.replace(' ', '_').replace('-', '_')
                    if hasattr(ontology, clean_variation):
                        return getattr(ontology, clean_variation)
                except AttributeError:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to search term '{term}' in {ontology_name}: {e}")
            return None
    
    async def _search_partial_matches(self, ontology: Any, query: str, ontology_name: str) -> List[UnifiedConcept]:
        """Search for partial matches using common biological term patterns."""
        concepts = []
        
        # Common biological term patterns to try
        patterns = [
            f"{query}_activity",
            f"{query}_binding",
            f"{query}_gene",
            f"{query}_protein",
            f"{query}_process",
            f"{query}_pathway",
            f"{query}_regulation",
            f"regulation_of_{query}",
            f"{query}_development",
            f"{query}_metabolism",
            f"{query}_transport",
            f"{query}_receptor",
            f"{query}_complex"
        ]
        
        for pattern in patterns:
            try:
                uri = await self._search_in_ontology(ontology, pattern, ontology_name)
                if uri:
                    concept = await self._create_concept_from_uri(uri, pattern, ontology_name, ontology)
                    if concept:
                        concepts.append(concept)
                        if len(concepts) >= 5:  # Limit partial matches per ontology
                            break
            except Exception:
                continue
        
        return concepts
    
    async def _create_concept_from_uri(self, uri: str, term: str, ontology_name: str, ontology: Any) -> Optional[UnifiedConcept]:
        """Create a UnifiedConcept from a URI."""
        try:
            # Get term label from URI if possible
            label = term
            try:
                if hasattr(ontology, 'get_term_by_uri'):
                    label = ontology.get_term_by_uri(uri) or term
            except Exception:
                pass
            
            # Determine concept type based on ontology and term
            concept_type = self._tyto_determine_concept_type(ontology_name, term, label)
            
            # Create identifiers
            identifiers = [
                ConceptIdentifier(
                    source=self.source,
                    identifier=uri,
                    label=label,
                    url=uri
                )
            ]
            
            # Extract additional info from URI  
            description = f"Term from {ontology_name} ontology"
            if 'identifiers.org' in uri:
                description += f". Standardized identifier: {uri}"
            
            concept = UnifiedConcept(
                primary_id=uri,
                primary_label=label,
                concept_type=concept_type,
                identifiers=identifiers,
                definitions=[description],
                confidence_score=0.9,  # High confidence for exact matches
                source_data={
                    self.source: {
                        'ontology': ontology_name,
                        'source_term': term,
                        'uri': uri,
                        'namespace': self._extract_namespace(uri)
                    }
                }
            )
            
            # Add hierarchical relationships if available
            await self._add_hierarchical_relationships(concept, uri, ontology)
            
            return concept
            
        except Exception as e:
            logger.debug(f"Failed to create concept from URI {uri}: {e}")
            return None
    
    def _tyto_determine_concept_type(self, ontology_name: str, term: str, label: str) -> ConceptType:
        """Determine concept type based on ontology and term."""
        term_lower = term.lower()
        # Remove unused variable that was causing lint error
        
        # Ontology-based type determination
        if ontology_name == 'NCBITaxon':
            return ConceptType.ORGANISM
        elif ontology_name == 'NCIT':
            if any(word in term_lower for word in ['cancer', 'tumor', 'carcinoma', 'disease']):
                return ConceptType.DISEASE
            elif any(word in term_lower for word in ['drug', 'therapy', 'treatment']):
                return ConceptType.DRUG
            elif any(word in term_lower for word in ['gene', 'protein']):
                return ConceptType.GENE
        elif ontology_name == 'SO':
            if any(word in term_lower for word in ['gene', 'promoter', 'exon']):
                return ConceptType.GENE
        elif ontology_name == 'SBO':
            if any(word in term_lower for word in ['pathway', 'process']):
                return ConceptType.PATHWAY
        elif ontology_name == 'PubChem':
            return ConceptType.CHEMICAL
        elif ontology_name == 'EDAM':
            if any(word in term_lower for word in ['data', 'format', 'operation']):
                return ConceptType.PROCEDURE
        
        # Term-based type determination
        if any(word in term_lower for word in ['disease', 'disorder', 'syndrome']):
            return ConceptType.DISEASE
        elif any(word in term_lower for word in ['symptom', 'sign']):
            return ConceptType.SYMPTOM
        elif any(word in term_lower for word in ['drug', 'compound', 'chemical']):
            return ConceptType.CHEMICAL
        elif any(word in term_lower for word in ['gene', 'dna', 'rna']):
            return ConceptType.GENE
        elif any(word in term_lower for word in ['protein', 'enzyme']):
            return ConceptType.PROTEIN
        elif any(word in term_lower for word in ['pathway', 'process']):
            return ConceptType.PATHWAY
        elif any(word in term_lower for word in ['anatomy', 'organ', 'tissue']):
            return ConceptType.ANATOMY
        
        return ConceptType.UNKNOWN
    
    def _extract_namespace(self, uri: str) -> Optional[str]:
        """Extract namespace from URI."""
        try:
            if 'identifiers.org' in uri:
                parts = uri.split('/')
                if len(parts) >= 4:
                    return parts[3]  # e.g., SO, SBO, etc.
            elif 'purl.obolibrary.org' in uri:
                parts = uri.split('/')
                for part in parts:
                    if part.startswith('obo'):
                        continue
                    if '_' in part and len(part) < 20:
                        return part.split('_')[0]
            return None
        except Exception:
            return None
    
    async def _add_hierarchical_relationships(self, concept: UnifiedConcept, uri: str, ontology: Any):
        """Add hierarchical relationships to concept if available."""
        if not TYTO_AVAILABLE or not tyto:
            return
            
        try:
            # Create URI object for inference
            if hasattr(tyto, 'URI'):
                tyto_uri = tyto.URI(uri)  # type: ignore
                tyto_uri.ontology = ontology  # type: ignore
                
                # Get parents
                try:
                    parents = tyto_uri.get_parents()  # type: ignore
                    if parents:
                        concept.parents = [str(p) for p in parents[:5]]  # Limit to 5
                except Exception:
                    pass
                
                # Get children
                try:
                    children = tyto_uri.get_children()  # type: ignore
                    if children:
                        concept.children = [str(c) for c in children[:5]]  # Limit to 5
                except Exception:
                    pass
                
        except Exception as e:
            logger.debug(f"Failed to add hierarchical relationships for {uri}: {e}")
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """
        Get detailed information about a specific concept.
        
        Args:
            concept_id: Concept identifier (URI)
            
        Returns:
            Unified concept with detailed information
        """
        if not TYTO_AVAILABLE:
            return None
        
        try:
            # Try to find which ontology this URI belongs to
            ontology_name = self._identify_ontology_from_uri(concept_id)
            if not ontology_name:
                return None
            
            ontology = self.builtin_ontologies.get(ontology_name)
            if not ontology:
                return None
            
            # Get term label
            label = concept_id  # Fallback
            try:
                if hasattr(ontology, 'get_term_by_uri'):
                    label = ontology.get_term_by_uri(concept_id) or concept_id
            except Exception:
                pass
            
            # Create detailed concept
            concept = await self._create_concept_from_uri(concept_id, label, ontology_name, ontology)
            if concept:
                concept.confidence_score = 1.0  # High confidence for direct lookup
            
            return concept
            
        except Exception as e:
            logger.error(f"Failed to get concept details for {concept_id}: {e}")
            return None
    
    def _identify_ontology_from_uri(self, uri: str) -> Optional[str]:
        """Identify which ontology a URI belongs to."""
        uri_lower = uri.lower()
        
        if 'so:' in uri_lower or 'sequenceontology.org' in uri_lower:
            return 'SO'
        elif 'sbo:' in uri_lower or 'biomodels.net' in uri_lower:
            return 'SBO'
        elif 'taxonomy:' in uri_lower or 'ncbi' in uri_lower:
            return 'NCBITaxon'
        elif 'ncit:' in uri_lower or 'nci.nih.gov' in uri_lower:
            return 'NCIT'
        elif 'om:' in uri_lower or 'ontology-of-units-of-measure' in uri_lower:
            return 'OM'
        elif 'edam:' in uri_lower or 'edamontology.org' in uri_lower:
            return 'EDAM'
        elif 'pubchem' in uri_lower:
            return 'PubChem'
        
        return None
    
    async def get_available_ontologies(self) -> Dict[str, str]:
        """Get list of available ontologies."""
        if not TYTO_AVAILABLE:
            return {}
        
        if self.available_ontologies is None:
            ontologies = {}
            
            # Add built-in ontologies
            for name in self.builtin_ontologies.keys():
                ontologies[name] = f"Built-in {name} ontology via Tyto"
            
            # Try to get additional ontologies from EBI OLS
            try:
                if TYTO_AVAILABLE and tyto and hasattr(tyto, 'EBIOntologyLookupService'):
                    additional = tyto.EBIOntologyLookupService.get_ontologies()  # type: ignore
                    for uri, abbrev in additional.items():
                        if abbrev not in ontologies:
                            ontologies[abbrev] = f"Available via EBI OLS: {uri}"
            except Exception as e:
                logger.debug(f"Failed to get additional ontologies: {e}")
            
            self.available_ontologies = ontologies
        
        return self.available_ontologies
    
    async def close(self):
        """Close the adapter and cleanup resources."""
        # Tyto doesn't require explicit cleanup
        logger.debug("Tyto adapter closed")


# Utility functions for working with Tyto

def get_ontology_by_name(name: str) -> Optional[Any]:
    """Get a Tyto ontology instance by name."""
    if not TYTO_AVAILABLE or not tyto:
        return None
    
    try:
        # Try to get the ontology dynamically
        ontology = getattr(tyto, name, None)
        if ontology is not None:
            return ontology
        
        # Try uppercase version
        ontology = getattr(tyto, name.upper(), None)
        if ontology is not None:
            return ontology
            
        # Check common alternative names
        name_mappings = {
            'NCBITAXON': 'NCBITaxon',
            'NCBI_TAXON': 'NCBITaxon',
            'NCBI': 'NCBITaxon',
            'TAXONOMY': 'NCBITaxon'
        }
        
        alt_name = name_mappings.get(name.upper())
        if alt_name:
            ontology = getattr(tyto, alt_name, None)
            if ontology is not None:
                return ontology
        
        logger.warning(f"Tyto ontology '{name}' not found")
        return None
        
    except Exception as e:
        logger.error(f"Error accessing Tyto ontology '{name}': {e}")
        return None

def create_custom_ontology(uri: str, name: str) -> Optional[Any]:
    """Create a custom Tyto ontology instance."""
    if not TYTO_AVAILABLE or not tyto:
        return None
    
    try:
        return tyto.Ontology(  # type: ignore
            uri=uri, 
            endpoints=[tyto.EBIOntologyLookupService]  # type: ignore
        )
    except Exception as e:
        logger.error(f"Failed to create custom ontology {name}: {e}")
        return None

def check_term_relationship(term1_uri: str, term2_uri: str, relationship: str = "is_a") -> Optional[bool]:
    """Check relationship between two ontology terms."""
    if not TYTO_AVAILABLE or not tyto:
        return None
    
    try:
        uri1 = tyto.URI(term1_uri)  # type: ignore
        uri2 = tyto.URI(term2_uri)  # type: ignore
        
        if relationship == "is_a":
            return uri1.is_a(uri2)  # type: ignore
        elif relationship == "is_descendant_of":
            return uri1.is_descendant_of(uri2)  # type: ignore
        elif relationship == "is_ancestor_of":
            return uri1.is_ancestor_of(uri2)  # type: ignore
        elif relationship == "is_child_of":
            return uri1.is_child_of(uri2)  # type: ignore
        elif relationship == "is_parent_of":
            return uri1.is_parent_of(uri2)  # type: ignore
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to check relationship between {term1_uri} and {term2_uri}: {e}")
        return None
