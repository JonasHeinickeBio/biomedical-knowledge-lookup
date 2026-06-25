"""
UMLS Knowledge Source Adapter

Integrates with the ``umls-python-client`` library to provide unified concept lookup.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class UMLSAdapter(KnowledgeSourceAdapter):
    """Adapter for UMLS (Unified Medical Language System).

    Uses ``umls-python-client`` (v1.2.0+) as its backend — an actively maintained,
    officially NLM-listed library with typed sync/async clients.

    **Implemented features**
        * ``search_concepts`` — keyword search with optional source (``sabs``)
          and semantic-group (``semantic_groups``) filters
        * ``get_concept_details`` — full profile (definitions, relations, atoms)
        * ``get_mappings`` — crosswalk CUIs to source-specific identifiers
        * ``get_relationships`` — paginated relations (parent/child/related)
        * ``bulk_search`` — multiple queries in one API call
        * ``iter_definitions`` / ``iter_relations`` — streaming iterators for
          large result sets
    """

    # ── Confidence constants ──────────────────────────────────────────
    _EXACT_MATCH_CONFIDENCE = 0.95
    _PARTIAL_MATCH_CONFIDENCE = 0.75
    _DETAILS_CONFIDENCE = 0.95

    # ── Source → ConceptType maps ───────────────────────────────────
    # Keys are checked longest-first so "icd10pcs" wins over "icd10".
    SOURCE_TYPE_MAP: dict[str, ConceptType] = {
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
        "rxnorm": ConceptType.DRUG,
        "nddf": ConceptType.DRUG,
        "drugbank": ConceptType.DRUG,
        "chembl": ConceptType.CHEMICAL,
        "pubchem": ConceptType.CHEMICAL,
        "mesh": ConceptType.CHEMICAL,
        "msh": ConceptType.CHEMICAL,
        "hgnc.symbol": ConceptType.GENE,
        "hgnc": ConceptType.GENE,
        "uniprot": ConceptType.GENE,
        "ensembl": ConceptType.GENE,
        "refseq": ConceptType.GENE,
        "genbank": ConceptType.GENE,
        "hpo": ConceptType.PHENOTYPE,
        "fma": ConceptType.ANATOMICAL_ENTITY,
        "uberon": ConceptType.ANATOMICAL_ENTITY,
        "go": ConceptType.BIOLOGICAL_PROCESS,
        "kegg": ConceptType.PATHWAY,
        "reactome": ConceptType.PATHWAY,
        "cpt": ConceptType.PROCEDURE,
        "loinc": ConceptType.PROCEDURE,
    }

    # Semantic-type *names* (from ``SearchResult.raw.semanticTypes``)
    SEMANTIC_TYPE_NAME_MAP: dict[str, ConceptType] = {
        "Disease or Syndrome": ConceptType.DISEASE,
        "Congenital Abnormality": ConceptType.DISEASE,
        "Acquired Abnormality": ConceptType.DISEASE,
        "Anatomical Abnormality": ConceptType.DISEASE,
        "Mental or Behavioral Dysfunction": ConceptType.DISEASE,
        "Neoplastic Process": ConceptType.DISEASE,
        "Sign or Symptom": ConceptType.SYMPTOM,
        "Therapeutic or Preventive Procedure": ConceptType.PROCEDURE,
        "Laboratory Procedure": ConceptType.PROCEDURE,
        "Diagnostic Procedure": ConceptType.PROCEDURE,
        "Clinical Drug": ConceptType.DRUG,
        "Pharmacologic Substance": ConceptType.DRUG,
        "Antibiotic": ConceptType.DRUG,
        "Organic Chemical": ConceptType.CHEMICAL,
        "Chemical": ConceptType.CHEMICAL,
        "Chemical Viewed Structurally": ConceptType.CHEMICAL,
        "Gene or Genome": ConceptType.GENE,
        "Amino Acid, Peptide, or Protein": ConceptType.GENE,
        "Receptor": ConceptType.GENE,
        "Cell": ConceptType.CELL_TYPE,
        "Cell Component": ConceptType.CELLULAR_COMPONENT,
        "Body Part, Organ, or Organ Component": ConceptType.ANATOMICAL_ENTITY,
        "Body System": ConceptType.ANATOMICAL_ENTITY,
        "Embryonic Structure": ConceptType.ANATOMICAL_ENTITY,
        "Tissue": ConceptType.TISSUE,
        "Finding": ConceptType.PHENOTYPE,
        "Pathologic Function": ConceptType.BIOLOGICAL_PROCESS,
        "Genetic Function": ConceptType.BIOLOGICAL_PROCESS,
        "Biologic Function": ConceptType.BIOLOGICAL_PROCESS,
        "Molecular Function": ConceptType.BIOLOGICAL_PROCESS,
        "Cell Function": ConceptType.BIOLOGICAL_PROCESS,
        "Functional Concept": ConceptType.PATHWAY,
    }

    # Semantic-type TUIs (from ``Concept.semantic_types``)
    SEMANTIC_TYPE_TUI_MAP: dict[str, ConceptType] = {
        "T047": ConceptType.DISEASE,
        "T019": ConceptType.DISEASE,
        "T020": ConceptType.DISEASE,
        "T190": ConceptType.DISEASE,
        "T048": ConceptType.DISEASE,
        "T191": ConceptType.DISEASE,
        "T184": ConceptType.SYMPTOM,
        "T082": ConceptType.PROCEDURE,
        "T061": ConceptType.PROCEDURE,
        "T059": ConceptType.PROCEDURE,
        "T060": ConceptType.PROCEDURE,
        "T200": ConceptType.DRUG,
        "T121": ConceptType.DRUG,
        "T195": ConceptType.DRUG,
        "T110": ConceptType.CHEMICAL,
        "T104": ConceptType.CHEMICAL,
        "T103": ConceptType.CHEMICAL,
        "T028": ConceptType.GENE,
        "T192": ConceptType.GENE,
        "T087": ConceptType.GENE,
        "T116": ConceptType.GENE,
        "T026": ConceptType.CELL_TYPE,
        "T025": ConceptType.ANATOMICAL_ENTITY,
        "T018": ConceptType.ANATOMICAL_ENTITY,
        "T021": ConceptType.ANATOMICAL_ENTITY,
        "T022": ConceptType.ANATOMICAL_ENTITY,
        "T023": ConceptType.TISSUE,
        "T024": ConceptType.TISSUE,
        "T169": ConceptType.PATHWAY,
        "T044": ConceptType.BIOLOGICAL_PROCESS,
        "T043": ConceptType.BIOLOGICAL_PROCESS,
        "T045": ConceptType.BIOLOGICAL_PROCESS,
        "T046": ConceptType.BIOLOGICAL_PROCESS,
        "T038": ConceptType.BIOLOGICAL_PROCESS,
        "T170": ConceptType.PHENOTYPE,
        "T033": ConceptType.PHENOTYPE,
    }

    # ── Lifecycle ──────────────────────────────────────────────────

    def __init__(self, config: LookupConfig) -> None:
        super().__init__(config)
        self.client: Any | None = None  # AsyncUMLSClient
        self._initialize_client()

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self.client is not None:
            try:
                await self.client.aclose()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_class():
        """Lazy-import and return ``AsyncUMLSClient``.

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
            logger.warning("umls-python-client not installed; UMLS adapter unavailable")
            return

        try:
            api_key = self.config.get_api_key("umls") or self.config.get_api_key("UMLS_API_KEY_TU")
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

    # ── 1. SEARCH ──────────────────────────────────────────────────

    async def search_concepts(
        self,
        query: str,
        limit: int = 20,
        *,
        sabs: str | None = None,
        semantic_groups: str | None = None,
        semantic_types: str | None = None,
        search_type: str = "words",
        partial_search: bool = False,
    ) -> list[UnifiedConcept]:
        """Search UMLS for concepts matching *query*.

        Parameters
        ----------
        query :
            The search string.
        limit :
            Maximum number of results.
        sabs :
            Restrict to specific source vocabularies (e.g. ``\"SNOMEDCT_US\"``,
            ``\"RXNORM\"``).  Multiple sources can be comma-separated.
        semantic_groups :
            Filter by UMLS semantic group abbreviation
            (e.g. ``\"DISO\"``, ``\"CHEM\"``, ``\"GENE\"``).
            .. note::
               As of the 2026AA release this parameter may return zero
               results; use ``semantic_types`` instead for reliable
               semantic filtering.
        semantic_types :
            Filter by UMLS semantic-type TUI
            (e.g. ``\"T047\"`` for disease, ``\"T121\"`` for drugs).
            Multiple TUIs can be comma-separated.
        search_type :
            ``\"words\"`` (default), ``\"exact\"``, ``\"leftTruncation\"``,
            ``\"normalizedString\"``, etc.
        partial_search :
            Allow partial matches.
        """
        if not self.client:
            logger.warning("UMLS client not available")
            return []

        try:
            response = await self.client.search_api.search(
                search_string=query,
                page_size=min(limit, 100),
                return_id_type="concept",
                sabs=sabs,
                semantic_groups=semantic_groups,
                semantic_types=semantic_types,
                search_type=search_type,
                partial_search=partial_search,
            )
            results: list = response.result
        except Exception as exc:
            logger.error("UMLS search failed for '%s': %s", query, exc)
            return []

        concepts: list[UnifiedConcept] = []
        for result in results[:limit]:
            concepts.append(self._convert_search_result(result, query))

        logger.info(
            "UMLS search for '%s' returned %d concepts (sabs=%s, group=%s, types=%s)",
            query,
            len(concepts),
            sabs,
            semantic_groups,
            semantic_types,
        )
        return concepts

    # ── 2. BULK SEARCH ─────────────────────────────────────────────

    async def bulk_search(
        self,
        queries: list[str],
        limit: int = 5,
        *,
        sabs: str | None = None,
        semantic_groups: str | None = None,
    ) -> dict[str, list[UnifiedConcept]]:
        """Run multiple search queries in a single API call.

        Parameters
        ----------
        queries :
            List of search strings.
        limit :
            Maximum results *per query*.
        sabs, semantic_groups :
            Filters applied to *all* queries (see ``search_concepts``).

        Returns
        -------
        ``{query: [UnifiedConcept, ...], ...}``
        """
        if not self.client:
            logger.warning("UMLS client not available")
            return {}

        try:
            raw = await self.client.search_api.bulk_search(
                queries,
                page_size=limit,
                return_id_type="concept",
                sabs=sabs,
                semantic_groups=semantic_groups,
            )
        except Exception as exc:
            logger.error("UMLS bulk search failed: %s", exc)
            return {}

        result: dict[str, list[UnifiedConcept]] = {}
        for query_str, response in raw.items():
            concepts: list[UnifiedConcept] = []
            if response and response.result:
                for r in response.result[:limit]:
                    concepts.append(self._convert_search_result(r, query_str))
            result[query_str] = concepts

        return result

    # ── 3. CONCEPT DETAILS ─────────────────────────────────────────

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed UMLS concept information (definitions, relations, atoms).

        Returns a :class:`UnifiedConcept` with populated ``definitions``,
        ``synonyms``, ``semantic_types``, ``parents``, ``children``,
        ``related``, and ``categories`` fields.
        """
        if not self.client:
            return None

        try:
            cui_resp = await self.client.cui_api.get_cui_info(concept_id)
            concept_info = cui_resp.result

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

    # ── 4. MAPPINGS / CROSSWALK ────────────────────────────────────

    async def get_mappings(
        self,
        concept_id: str,
        *,
        target_source: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve source-specific identifiers for a UMLS CUI.

        Uses ``get_atoms`` to map a concept to identifiers across all
        source vocabularies in UMLS.  When *target_source* is set, only
        atoms from that source are returned.

        Parameters
        ----------
        concept_id :
            UMLS CUI (e.g. ``\"C0025598\"``).
        target_source :
            Optional source abbreviation (e.g. ``\"SNOMEDCT\"``,
            ``\"RXNORM\"``, ``\"MSH\"``).
        limit :
            Maximum number of mappings.

        Returns
        -------
        ``[{source, source_id, source_name, term_type, language, cui}, ...]``
        """
        if not self.client:
            logger.warning("UMLS client not available")
            return []

        try:
            resp = await self.client.cui_api.get_atoms(
                concept_id,
                sabs=target_source,
                page_size=min(limit, 200),
            )
            atoms: list = resp.result or []
        except Exception as exc:
            logger.error(
                "UMLS get_atoms failed for '%s' (source=%s): %s",
                concept_id,
                target_source or "ALL",
                exc,
            )
            return []

        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for atom in atoms[:limit]:
            key = (atom.root_source or "", atom.code or atom.ui or "")
            if key in seen:
                continue
            seen.add(key)

            source_id = (
                atom.code.rsplit("/", 1)[-1] if atom.code else (atom.ui or "").rsplit("/", 1)[-1]
            )

            mappings.append(
                {
                    "source": atom.root_source,
                    "source_id": source_id,
                    "source_name": atom.name,
                    "term_type": atom.term_type,
                    "language": atom.language,
                    "cui": concept_id,
                }
            )

        return mappings

    # ── 5. RELATIONSHIPS ───────────────────────────────────────────

    async def get_relationships(
        self,
        concept_id: str,
        *,
        relation_labels: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve relationships for a UMLS concept.

        Parameters
        ----------
        concept_id :
            UMLS CUI.
        relation_labels :
            Optional comma-separated list to filter by relation label
            (e.g. ``\"PAR,CHD\"`` for parent/child only).
        limit :
            Maximum number of relations to return.

        Returns
        -------
        ``[{relation_label, related_id, related_name, source}, ...]``
        """
        if not self.client:
            logger.warning("UMLS client not available")
            return []

        try:
            resp = await self.client.cui_api.get_relations(
                concept_id,
                include_relation_labels=relation_labels,
                page_size=min(limit, 100),
            )
            relations = resp.result or []
        except Exception as exc:
            logger.error("UMLS get_relationships failed for '%s': %s", concept_id, exc)
            return []

        return [
            {
                "relation_label": r.relation_label,
                "additional_label": r.additional_relation_label,
                "related_id": r.related_id,
                "related_name": r.related_id_name,
                "related_id_name": r.related_id_name,
                "source": r.root_source,
                "uri": r.ui,
            }
            for r in relations[:limit]
        ]

    # ── 6. STREAMING ITERATORS ─────────────────────────────────────

    async def iter_definitions(
        self,
        concept_id: str,
        page_size: int = 25,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream *all* definitions for a concept using paginated requests.

        Yields ``{value, root_source, source_originated}`` dicts.
        """
        if not self.client:
            return

        try:
            async for defn in self.client.cui_api.iter_definitions(
                concept_id, page_size=page_size
            ):
                yield {
                    "value": defn.value,
                    "root_source": defn.root_source,
                    "source_originated": defn.source_originated,
                }
        except Exception as exc:
            logger.error("UMLS iter_definitions failed for '%s': %s", concept_id, exc)

    async def iter_relations(
        self,
        concept_id: str,
        page_size: int = 200,
        *,
        relation_labels: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream *all* relations for a concept using paginated requests.

        Yields ``{relation_label, related_id, related_name, source}`` dicts.
        """
        if not self.client:
            return

        try:
            async for rel in self.client.cui_api.iter_relations(
                concept_id,
                page_size=page_size,
                include_relation_labels=relation_labels,
            ):
                yield {
                    "relation_label": rel.relation_label,
                    "additional_label": rel.additional_relation_label,
                    "related_id": rel.related_id,
                    "related_name": rel.related_id_name,
                    "related_id_name": rel.related_id_name,
                    "source": rel.root_source,
                    "uri": rel.ui,
                }
        except Exception as exc:
            logger.error("UMLS iter_relations failed for '%s': %s", concept_id, exc)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _convert_search_result(self, result, query: str) -> UnifiedConcept:
        """Convert a ``SearchResult`` to ``UnifiedConcept``."""
        cui: str = result.ui or ""
        name: str = result.name or ""
        root_source: str = result.root_source or ""

        concept_type = self._determine_concept_type_from_source(root_source)
        if concept_type is ConceptType.UNKNOWN or root_source.upper() == "MTH":
            semantic_type_names: list[str] = (result.raw or {}).get("semanticTypes", [])
            concept_type = self._determine_concept_type_from_semantic_type_names(
                semantic_type_names
            )

        concept = UnifiedConcept(
            primary_id=cui,
            primary_label=name,
            concept_type=concept_type,
        )

        concept.add_identifier(
            KnowledgeSource.UMLS,
            cui,
            name,
            f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
        )

        if root_source:
            concept.categories.append(root_source)

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

        concept_type = self._determine_concept_type(
            profile
        ) or self._determine_concept_type_from_semantic_types(semantic_types)

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

        concept.semantic_types = [st.get("name", "") for st in semantic_types]
        concept.definitions = [d.value for d in (profile.definitions or []) if d.value]

        synonyms: list[str] = []
        if profile.preferred_atom and profile.preferred_atom.name:
            synonyms.append(profile.preferred_atom.name)
        for atom in profile.atoms or []:
            if atom.name and atom.name != name and atom.name not in synonyms:
                synonyms.append(atom.name)
        concept.synonyms = synonyms

        concept.categories = list(
            {atom.root_source for atom in (profile.atoms or []) if atom.root_source}
        )

        for rel in profile.relations or []:
            related_id = rel.related_id or ""
            rel_label = (rel.relation_label or "").lower()
            if rel_label in {"par", "parent", "isa"}:
                concept.parents.append(related_id)
            elif rel_label in {"chd", "child"}:
                concept.children.append(related_id)
            else:
                concept.related.append(related_id)

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
        """Infer concept type from a ``ConceptProfile``."""
        if profile.preferred_atom and profile.preferred_atom.root_source:
            mapped = self._determine_concept_type_from_source(profile.preferred_atom.root_source)
            if mapped is not ConceptType.UNKNOWN:
                return mapped
        root_source = (profile.concept.raw or {}).get("rootSource", "") if profile.concept else ""
        if root_source:
            mapped = self._determine_concept_type_from_source(root_source)
            if mapped is not ConceptType.UNKNOWN:
                return mapped
        if profile.concept and profile.concept.semantic_types:
            mapped = self._determine_concept_type_from_semantic_types(
                profile.concept.semantic_types
            )
            if mapped is not ConceptType.UNKNOWN:
                return mapped
        return ConceptType.UNKNOWN

    def _determine_concept_type_from_semantic_type_names(
        self,
        type_names: list[str],
    ) -> ConceptType:
        for name in type_names:
            mapped = self.SEMANTIC_TYPE_NAME_MAP.get(name)
            if mapped is not None:
                return mapped
        return ConceptType.UNKNOWN

    def _determine_concept_type_from_semantic_types(
        self,
        semantic_types: list[dict],
    ) -> ConceptType:
        for st in semantic_types:
            tui = (st.get("uri") or "").rsplit("/", 1)[-1]
            mapped = self.SEMANTIC_TYPE_TUI_MAP.get(tui)
            if mapped is not None:
                return mapped
        return ConceptType.UNKNOWN

    def _determine_concept_type_from_source(self, source: str) -> ConceptType:
        source_lower = source.lower()
        for key in sorted(self.SOURCE_TYPE_MAP, key=len, reverse=True):
            if key in source_lower:
                return self.SOURCE_TYPE_MAP[key]
        return ConceptType.UNKNOWN
