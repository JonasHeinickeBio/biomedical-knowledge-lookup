"""
UMLS Knowledge Source Adapter

Integrates with the existing UMLS client to provide unified concept lookup.
"""

import logging

from knowledge_lookup.umls.client import OptimizedUMLSClient, create_umls_client

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class UMLSAdapter(KnowledgeSourceAdapter):
    """Adapter for UMLS (Unified Medical Language System)."""

    # Minimum confidence for exact name match vs query
    _EXACT_MATCH_CONFIDENCE = 0.95
    _PARTIAL_MATCH_CONFIDENCE = 0.75
    _DETAILS_CONFIDENCE = 0.95  # UMLS is authoritative for detailed lookups

    # Map UMLS source abbreviations to concept types
    SOURCE_TYPE_MAP: dict[str, ConceptType] = {
        # Diseases & Disorders
        "snomedct": ConceptType.DISEASE,
        "icd10cm": ConceptType.DISEASE,
        "icd10": ConceptType.DISEASE,
        "icd9cm": ConceptType.DISEASE,
        "icd9": ConceptType.DISEASE,
        "icpc": ConceptType.DISEASE,
        "icpc2": ConceptType.DISEASE,
        "omim": ConceptType.DISEASE,
        "ordo": ConceptType.DISEASE,
        "nci": ConceptType.DISEASE,
        "meddra": ConceptType.DISEASE,
        # Drugs & Chemicals
        "rxnorm": ConceptType.DRUG,
        "nddf": ConceptType.DRUG,
        "drugbank": ConceptType.DRUG,
        "chembl": ConceptType.CHEMICAL,
        "pubchem": ConceptType.CHEMICAL,
        "mesh": ConceptType.CHEMICAL,
        "msh": ConceptType.CHEMICAL,  # UMLS abbreviation for MeSH
        # Genes & Proteins
        "hgnc": ConceptType.GENE,
        "hgnc.symbol": ConceptType.GENE,
        "uniprot": ConceptType.GENE,
        "ensembl": ConceptType.GENE,
        "refseq": ConceptType.GENE,
        "genbank": ConceptType.GENE,
        # Phenotypes
        "hpo": ConceptType.PHENOTYPE,
        "phenonet": ConceptType.PHENOTYPE,
        # Anatomy
        "fma": ConceptType.ANATOMICAL_ENTITY,
        "uberon": ConceptType.ANATOMICAL_ENTITY,
        # Biological Processes
        "go": ConceptType.BIOLOGICAL_PROCESS,
        "kegg": ConceptType.PATHWAY,
        "reactome": ConceptType.PATHWAY,
        # Procedures & Interventions
        "cpt": ConceptType.PROCEDURE,
        "icd10pcs": ConceptType.PROCEDURE,
        "loinc": ConceptType.PROCEDURE,
    }

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.client: OptimizedUMLSClient | None = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize UMLS client with API key from config."""
        try:
            api_key = self.config.get_api_key("umls") or self.config.get_api_key("UMLS_API_KEY_TU")
            self.client = create_umls_client(api_key=api_key)
            logger.info("UMLS client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize UMLS client: {e}")
            self.client = None

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.UMLS

    def is_available(self) -> bool:
        return self.client is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search UMLS for concepts matching the query."""
        if not self.client:
            logger.warning("UMLS client not available")
            return []

        try:
            # Use UMLS client search
            results = self.client.search_concepts(query, page_size=min(limit, 100))

            concepts = []
            for result in results[:limit]:
                concept = self._convert_search_result_to_concept(result, query)
                concepts.append(concept)

            logger.info(f"UMLS search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"UMLS search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed UMLS concept information."""
        if not self.client:
            return None

        try:
            # Get concept details from UMLS
            umls_concept = self.client.get_concept_details(concept_id)
            if not umls_concept:
                return None

            # Convert to unified concept
            concept = self._convert_umls_concept_to_unified(umls_concept)
            return concept

        except Exception as e:
            logger.error(f"Failed to get UMLS concept details for '{concept_id}': {e}")
            return None

    def _convert_search_result_to_concept(self, result, query: str) -> UnifiedConcept:
        """Convert UMLS search result to unified concept.

        Args:
            result: UMLSSearchResult object from the UMLS client.
            query: The original search query used for confidence scoring.

        Returns:
            UnifiedConcept with available metadata.
        """
        # Determine concept type from source
        concept_type = self._determine_concept_type_from_source(result.source)

        concept = UnifiedConcept(
            primary_id=result.cui, primary_label=result.name, concept_type=concept_type
        )

        # Add UMLS identifier
        concept.add_identifier(
            KnowledgeSource.UMLS,
            result.cui,
            result.name,
            f"https://uts.nlm.nih.gov/uts/umls/concept/{result.cui}",
        )

        # Add source-specific information
        if hasattr(result, "source") and result.source:
            concept.categories.append(result.source)

        # Set confidence based on exact match against the query
        query_lower = query.strip().lower()
        name_lower = result.name.strip().lower()
        if name_lower == query_lower:
            concept.confidence_score = self._EXACT_MATCH_CONFIDENCE
        elif query_lower in name_lower or name_lower in query_lower:
            concept.confidence_score = self._PARTIAL_MATCH_CONFIDENCE + 0.1
        else:
            concept.confidence_score = self._PARTIAL_MATCH_CONFIDENCE

        concept.source_data[KnowledgeSource.UMLS] = {
            "ui": result.ui,
            "source": result.source,
            "source_concept_id": result.source_concept_id,
            "root_source": result.root_source,
        }

        return concept

    def _convert_umls_concept_to_unified(self, umls_concept) -> UnifiedConcept:
        """Convert UMLS concept to unified concept with full details."""
        # Determine concept type from semantic types
        concept_type = self._determine_concept_type(umls_concept.semantic_types)

        concept = UnifiedConcept(
            primary_id=umls_concept.cui, primary_label=umls_concept.name, concept_type=concept_type
        )

        # Add UMLS identifier
        concept.add_identifier(
            KnowledgeSource.UMLS,
            umls_concept.cui,
            umls_concept.name,
            f"https://uts.nlm.nih.gov/uts/umls/concept/{umls_concept.cui}",
        )

        # Add semantic information
        concept.semantic_types = umls_concept.semantic_types
        concept.definitions = umls_concept.definitions
        concept.synonyms = umls_concept.synonyms
        concept.categories = umls_concept.sources

        # Add relationships
        for relationship in umls_concept.relationships:
            related_cui = relationship.get("relatedId", "")
            rel_type = relationship.get("relationLabel", "")

            if rel_type.lower() in ["par", "parent", "isa"]:
                concept.parents.append(related_cui)
            elif rel_type.lower() in ["chd", "child"]:
                concept.children.append(related_cui)
            else:
                concept.related.append(related_cui)

        # Set confidence score
        concept.confidence_score = self._DETAILS_CONFIDENCE  # UMLS is authoritative

        # Store raw UMLS data
        concept.source_data[KnowledgeSource.UMLS] = {
            "semantic_types": umls_concept.semantic_types,
            "definitions": umls_concept.definitions,
            "synonyms": umls_concept.synonyms,
            "sources": umls_concept.sources,
            "atoms": umls_concept.atoms,
            "relationships": umls_concept.relationships,
        }

        return concept

    def _determine_concept_type_from_source(self, source: str) -> ConceptType:
        """Determine concept type from UMLS source vocabulary.

        Uses SOURCE_TYPE_MAP to map known UMLS source abbreviations to concept types.
        Keys are sorted by length (descending) so that more specific matches (e.g.
        ``icd10pcs``) take priority over more general ones (e.g. ``icd10``).
        Falls back to UNKNOWN for unmapped sources.
        """
        source_lower = source.lower()

        # Check from most-specific (longest) to least-specific (shortest)
        for key in sorted(self.SOURCE_TYPE_MAP, key=len, reverse=True):
            if key in source_lower:
                return self.SOURCE_TYPE_MAP[key]

        return ConceptType.UNKNOWN
