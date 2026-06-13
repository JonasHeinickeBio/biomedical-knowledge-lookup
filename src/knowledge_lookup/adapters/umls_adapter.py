"""
UMLS Knowledge Source Adapter

Integrates with the ``umls-python-client`` library to provide unified concept lookup.
"""

from __future__ import annotations

import logging

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class UMLSAdapter(KnowledgeSourceAdapter):
    """Adapter for UMLS (Unified Medical Language System).

    Uses ``umls-python-client`` (v1.2.0+) as its backend — an actively maintained,
    officially NLM-listed library with typed sync/async clients.
    """

    # Minimum confidence for exact name match vs query
    _EXACT_MATCH_CONFIDENCE = 0.95
    _PARTIAL_MATCH_CONFIDENCE = 0.75
    _DETAILS_CONFIDENCE = 0.95

    # Map UMLS root-source abbreviations to concept types.
    # Keys are checked from longest to shortest so that specific entries
    # (e.g. ``icd10pcs``) take priority over general ones (e.g. ``icd10``).
    SOURCE_TYPE_MAP: dict[str, ConceptType] = {
        # Diseases & Disorders
        "snomedct": ConceptType.DISEASE,
        "icd10cm": ConceptType.DISEASE,
        "icd10pcs": ConceptType.PROCEDURE,
        "icd10": ConceptType.DISEASE,
        "icd9cm": ConceptType.DISEASE,
        "icd9": ConceptType.DISEASE,
        "icpc2": ConceptType.DISEASE,
        "icpc": ConceptType.DISEASE,
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
        "msh": ConceptType.CHEMICAL,
        # Genes & Proteins
        "hgnc.symbol": ConceptType.GENE,
        "hgnc": ConceptType.GENE,
        "uniprot": ConceptType.GENE,
        "ensembl": ConceptType.GENE,
        "refseq": ConceptType.GENE,
        "genbank": ConceptType.GENE,
        # Phenotypes
        "hpo": ConceptType.PHENOTYPE,
        # Anatomy
        "fma": ConceptType.ANATOMICAL_ENTITY,
        "uberon": ConceptType.ANATOMICAL_ENTITY,
        # Biological processes
        "go": ConceptType.BIOLOGICAL_PROCESS,
        "kegg": ConceptType.PATHWAY,
        "reactome": ConceptType.PATHWAY,
        # Procedures
        "cpt": ConceptType.PROCEDURE,
        "loinc": ConceptType.PROCEDURE,
    }

    # Maps UMLS semantic-type TUIs to AID-PAIS concept types.
    # Used when full concept details are available.
    SEMANTIC_TYPE_MAP: dict[str, ConceptType] = {
        "T047": ConceptType.DISEASE,  # Disease or Syndrome
        "T019": ConceptType.DISEASE,  # Congenital Abnormality
        "T020": ConceptType.DISEASE,  # Acquired Abnormality
        "T190": ConceptType.DISEASE,  # Anatomical Abnormality
        "T048": ConceptType.DISEASE,  # Mental or Behavioral Dysfunction
        "T184": ConceptType.DISEASE,  # Sign or Symptom
        "T184": ConceptType.SYMPTOM,
        "T082": ConceptType.PROCEDURE,  # Therapeutic or Preventive Procedure
        "T061": ConceptType.PROCEDURE,  # Therapeutic or Preventive Procedure
        "T059": ConceptType.PROCEDURE,  # Laboratory Procedure
        "T060": ConceptType.PROCEDURE,  # Diagnostic Procedure
        "T200": ConceptType.DRUG,  # Clinical Drug
        "T121": ConceptType.DRUG,  # Pharmacologic Substance
        "T195": ConceptType.DRUG,  # Antibiotic
        "T110": ConceptType.CHEMICAL,  # Steroid
        "T104": ConceptType.CHEMICAL,  # Chemical Viewed Structurally
        "T103": ConceptType.CHEMICAL,  # Chemical
        "T028": ConceptType.GENE,  # Gene or Genome
        "T192": ConceptType.GENE,  # Receptor
        "T087": ConceptType.GENE,  # Amino Acid, Peptide, or Protein
        "T116": ConceptType.GENE,  # Amino Acid, Peptide, or Protein
        "T026": ConceptType.CELL_TYPE,  # Cell
        "T025": ConceptType.ANATOMICAL_ENTITY,  # Body Part, Organ, or Organ Component
        "T018": ConceptType.ANATOMICAL_ENTITY,  # Embryonic Structure
        "T021": ConceptType.ANATOMICAL_ENTITY,  # Body System
        "T022": ConceptType.ANATOMICAL_ENTITY,  # Body System
        "T023": ConceptType.TISSUE,  # Tissue
        "T024": ConceptType.TISSUE,  # Tissue
        "T169": ConceptType.PATHWAY,  # Functional Concept (often pathways)
        "T044": ConceptType.BIOLOGICAL_PROCESS,  # Molecular Function
        "T043": ConceptType.BIOLOGICAL_PROCESS,  # Cell Function
        "T045": ConceptType.BIOLOGICAL_PROCESS,  # Genetic Function
        "T046": ConceptType.BIOLOGICAL_PROCESS,  # Pathologic Function
        "T038": ConceptType.BIOLOGICAL_PROCESS,  # Biologic Function
        "T170": ConceptType.PHENOTYPE,  # Intellectual Product (often HPO)
        "T033": ConceptType.PHENOTYPE,  # Finding
        "T184": ConceptType.SYMPTOM,  # Sign or Symptom
    }

    def __init__(self, config: LookupConfig) -> None:
        super().__init__(config)
        self.client: Any | None = None  # AsyncUMLSClient
        self._initialize_client()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_class():
        """Lazy-import and return the ``AsyncUMLSClient`` class.

        Returns ``None`` if the optional dependency is missing.
        """
        try:
            from umls_python_client import AsyncUMLSClient  # noqa: F811

            return AsyncUMLSClient
        except ImportError:
            return None

    def _initialize_client(self) -> None:
        """Initialise the ``AsyncUMLSClient`` with an API key."""
        client_cls = self._get_client_class()
        if client_cls is None:
            logger.warning("umls-python-client is not installed; UMLS adapter unavailable")
            return

        try:
            api_key = (
                self.config.get_api_key("umls")
                or self.config.get_api_key("UMLS_API_KEY_TU")
            )
            if not api_key:
                logger.warning("No UMLS API key configured; adapter unavailable")
                return
            self.client = client_cls(api_key=api_key)
            logger.info("UMLS client initialised successfully")
        except Exception as exc:
            logger.error("Failed to initialise UMLS client: %s", exc)
            self.client = None

    # ------------------------------------------------------------------
    # KnowledgeSourceAdapter interface
    # ------------------------------------------------------------------

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.UMLS

    def is_available(self) -> bool:
        return self.client is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search UMLS for concepts matching *query*."""
        if not self.client:
            logger.warning("UMLS client not available")
            return []

        try:
            response = await self.client.search_api.search(
                search_string=query,
                page_size=min(limit, 100),
                return_id_type="concept",
            )
            results: list = response.result  # list of SearchResult
        except Exception as exc:
            logger.error("UMLS search failed for '%s': %s", query, exc)
            return []

        concepts: list[UnifiedConcept] = []
        for result in results[:limit]:
            concept = self._convert_search_result(result, query)
            concepts.append(concept)

        logger.info("UMLS search for '%s' returned %d concepts", query, len(concepts))
        return concepts

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed UMLS concept information (definitions, relations, atoms)."""
        if not self.client:
            return None

        try:
            # Basic info (name, semantic types)
            cui_resp = await self.client.cui_api.get_cui_info(concept_id)
            concept_info = cui_resp.result

            # Full profile (definitions, relations, atoms)
            profile_resp = await self.client.cui_api.get_concept_profile(
                concept_id,
                include_definitions=True,
                include_relations=True,
                include_atoms=True,
            )
            profile = profile_resp.result
        except Exception as exc:
            logger.error("Failed to get UMLS concept details for '%s': %s", concept_id, exc)
            return None

        return self._convert_profile(concept_id, concept_info, profile)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _convert_search_result(self, result, query: str) -> UnifiedConcept:
        """Convert an ``umls_python_client.models.SearchResult`` to ``UnifiedConcept``.

        Parameters
        ----------
        result :
            A ``SearchResult`` instance with ``.ui`` (CUI), ``.name``,
            ``.root_source``, ``.uri``, and ``.raw`` fields.
        query :
            The original search query, used for confidence scoring.
        """
        cui: str = result.ui or ""
        name: str = result.name or ""
        root_source: str = result.root_source or ""

        concept_type = self._determine_concept_type_from_source(root_source)

        concept = UnifiedConcept(
            primary_id=cui,
            primary_label=name,
            concept_type=concept_type,
        )

        # UMLS-level identifier
        concept.add_identifier(
            KnowledgeSource.UMLS,
            cui,
            name,
            f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
        )

        if root_source:
            concept.categories.append(root_source)

        # Confidence scoring based on name-vs-query match
        query_lower = query.strip().lower()
        name_lower = name.strip().lower()
        if name_lower == query_lower:
            concept.confidence_score = self._EXACT_MATCH_CONFIDENCE
        elif query_lower in name_lower or name_lower in query_lower:
            concept.confidence_score = self._PARTIAL_MATCH_CONFIDENCE + 0.1
        else:
            concept.confidence_score = self._PARTIAL_MATCH_CONFIDENCE

        concept.source_data[KnowledgeSource.UMLS] = {
            "root_source": root_source,
            "uri": result.uri,
        }

        return concept

    def _convert_profile(self, cui: str, concept_info, profile) -> UnifiedConcept:
        """Convert a ``Concept`` + ``ConceptProfile`` pair to ``UnifiedConcept``."""
        name: str = concept_info.name or ""
        semantic_types: list[dict] = concept_info.semantic_types or []

        concept_type = self._determine_concept_type(profile) or self._determine_concept_type_from_semantic_types(semantic_types)

        concept = UnifiedConcept(
            primary_id=cui,
            primary_label=name,
            concept_type=concept_type,
        )
        concept.confidence_score = self._DETAILS_CONFIDENCE

        concept.add_identifier(
            KnowledgeSource.UMLS,
            cui,
            name,
            f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
        )

        # Semantic types
        concept.semantic_types = [st.get("name", "") for st in semantic_types]

        # Definitions
        concept.definitions = [
            d.value for d in (profile.definitions or []) if d.value
        ]

        # Synonyms — from preferred atom name + other atoms
        synonyms: list[str] = []
        if profile.preferred_atom and profile.preferred_atom.name:
            synonyms.append(profile.preferred_atom.name)
        for atom in (profile.atoms or []):
            if atom.name and atom.name != name and atom.name not in synonyms:
                synonyms.append(atom.name)
        concept.synonyms = synonyms

        # Source vocabularies
        concept.categories = list({
            atom.root_source for atom in (profile.atoms or []) if atom.root_source
        })

        # Relations
        for rel in (profile.relations or []):
            related_id = rel.related_id or ""
            rel_label = (rel.relation_label or "").lower()
            if rel_label in {"par", "parent", "isa"}:
                concept.parents.append(related_id)
            elif rel_label in {"chd", "child"}:
                concept.children.append(related_id)
            else:
                concept.related.append(related_id)

        # Store raw data
        concept.source_data[KnowledgeSource.UMLS] = {
            "semantic_types": semantic_types,
            "definitions": concept.definitions,
            "synonyms": concept.synonyms,
            "sources": concept.categories,
            "atoms": [a.to_dict() for a in (profile.atoms or [])],
            "relations": [r.to_dict() for r in (profile.relations or [])],
        }

        return concept

    # ------------------------------------------------------------------
    # Type determination
    # ------------------------------------------------------------------

    def _determine_concept_type(self, profile) -> ConceptType:
        """Infer concept type from a ``ConceptProfile``, preferring available data."""
        # If there's a preferred atom with a term type, use that
        if profile.preferred_atom and profile.preferred_atom.root_source:
            return self._determine_concept_type_from_source(profile.preferred_atom.root_source)
        # Fall back to concept-level root source from raw
        root_source = (profile.concept.raw or {}).get("rootSource", "") if profile.concept else ""
        if root_source:
            return self._determine_concept_type_from_source(root_source)
        # Fall back to semantic types
        if profile.concept and profile.concept.semantic_types:
            return self._determine_concept_type_from_semantic_types(profile.concept.semantic_types)
        return ConceptType.UNKNOWN

    def _determine_concept_type_from_semantic_types(
        self, semantic_types: list[dict],
    ) -> ConceptType:
        """Map UMLS semantic types (by TUI) to a ``ConceptType``."""
        for st in semantic_types:
            tui = (st.get("uri") or "").rsplit("/", 1)[-1]  # e.g. …/T047
            mapped = self.SEMANTIC_TYPE_MAP.get(tui)
            if mapped is not None:
                return mapped
        return ConceptType.UNKNOWN

    def _determine_concept_type_from_source(self, source: str) -> ConceptType:
        """Map a UMLS root-source abbreviation to ``ConceptType``.

        Keys are sorted by length (descending) so that more specific entries
        (e.g. ``icd10pcs``) take priority over more general ones (e.g. ``icd10``).
        """
        source_lower = source.lower()
        for key in sorted(self.SOURCE_TYPE_MAP, key=len, reverse=True):
            if key in source_lower:
                return self.SOURCE_TYPE_MAP[key]
        return ConceptType.UNKNOWN
