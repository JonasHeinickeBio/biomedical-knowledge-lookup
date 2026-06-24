"""
UMLS Knowledge Source Adapter

Integrates with the ``umls-python-client`` library to provide unified concept lookup.

New in v2.1
-----------
* ``crosswalk_codes`` — direct vocabulary-to-vocabulary code conversion
* ``download_terminology`` — automated RxNorm / SNOMED CT download
* ``UMLSCache`` integration — local SQLite cache with auto-fallback
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Optional local cache — imported lazily to keep startup fast
_UMLS_CACHE: Any = None
_UMLS_CACHE_PATH: str | Path | None = None


def _get_umls_cache(cache_path: str | Path | None = None) -> Any:
    """Lazy-import and return a :class:`UMLSCache` singleton."""
    global _UMLS_CACHE, _UMLS_CACHE_PATH
    if _UMLS_CACHE is None or (cache_path is not None and cache_path != _UMLS_CACHE_PATH):
        from ..umls.cache import UMLSCache as _CacheCls  # noqa: F811

        _UMLS_CACHE_PATH = cache_path
        _UMLS_CACHE = _CacheCls(db_path=cache_path)
    return _UMLS_CACHE


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

    def __init__(
        self, config: LookupConfig, cache: Any | None = None, cache_path: str | Path | None = None
    ) -> None:
        super().__init__(config)
        self.client: Any | None = None  # AsyncUMLSClient
        # If an explicit cache instance is provided, use it.
        # Otherwise, fall back to the module-level singleton (which can be
        # configured via *cache_path* or the default path).
        if cache is not None:
            self._cache = cache
        elif cache_path is not None:
            self._cache = _get_umls_cache(Path(cache_path))
        else:
            self._cache = _get_umls_cache()
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
        use_cache: bool = True,
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
        semantic_types :
            Filter by UMLS semantic-type TUI
            (e.g. ``\"T047\"`` for disease, ``\"T121\"`` for drugs).
            Multiple TUIs can be comma-separated.
        search_type :
            ``\"words\"`` (default), ``\"exact\"``, ``\"leftTruncation\"``,
            ``\"normalizedString\"``, etc.
        partial_search :
            Allow partial matches.  When enabled and the REST API returns
            few results, a local fuzzy fallback (trigram + character overlap)
            is applied to cached concepts.
        use_cache :
            Whether to check the local cache first and cache new results.
        """
        # ── Local cache first ──────────────────────────────────────
        if use_cache and self._cache is not None and not partial_search:
            cached = self._cache.search_concepts(query, limit=limit)
            if cached:
                logger.info("UMLS cache hit for '%s' (%d results)", query, len(cached))
                return [self._cached_to_concept(c, query) for c in cached]

        if not self.client:
            logger.warning("UMLS client not available")
            return []

        # ── REST API call ──────────────────────────────────────────
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
            # ── Fuzzy fallback on cache when API fails ─────────────
            if use_cache and self._cache is not None:
                fallback = self._cache.search_concepts(query, limit=limit, partial=True)
                if fallback:
                    logger.info(
                        "UMLS fuzzy cache fallback for '%s' (%d results)", query, len(fallback)
                    )
                    return [self._cached_to_concept(c, query) for c in fallback]
            return []

        concepts: list[UnifiedConcept] = []
        for result in results[:limit]:
            concept = self._convert_search_result(result, query)
            concepts.append(concept)

            # ── Cache each concept for future lookups ──────────────
            if use_cache and self._cache is not None:
                self._cache_search_result(concept, result)

        logger.info(
            "UMLS search for '%s' returned %d concepts (sabs=%s, group=%s, types=%s)",
            query,
            len(concepts),
            sabs,
            semantic_groups,
            semantic_types,
        )

        # ── Fuzzy fallback if API returned few results ────────────
        if partial_search and len(concepts) < limit and self._cache is not None:
            fuzzy = self._cache.search_concepts(query, limit=limit, partial=True)
            seen = {c.primary_id for c in concepts}
            for fc in fuzzy:
                if fc["cui"] not in seen:
                    concepts.append(self._cached_to_concept(fc, query))
                    seen.add(fc["cui"])
                    if len(concepts) >= limit:
                        break

        return concepts[:limit]

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

    # ── 4b. CROSSWALK CODES (direct vocabulary conversion) ──────────

    async def crosswalk_codes(
        self,
        source: str,
        code: str,
        target_source: str | None = None,
        include_obsolete: bool = False,
        page_size: int = 25,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Convert a code directly between vocabularies using the UMLS crosswalk endpoint.

        Unlike :meth:`get_mappings` (which maps a CUI to atoms), this endpoint
        takes a source + code pair and returns matching concepts across
        target vocabularies *without* requiring a CUI first.

        Parameters
        ----------
        source :
            Source vocabulary abbreviation (e.g. ``\"ICD10CM\"``, ``\"SNOMEDCT_US\"``).
        code :
            Code in the source vocabulary (e.g. ``\"E11.9\"``, ``\"73211009\"``).
        target_source :
            Optional target vocabulary to restrict results
            (e.g. ``\"SNOMEDCT_US\"``).  When ``None``, returns all mappings.
        include_obsolete :
            Whether to include obsolete concepts.
        page_size :
            Results per page.
        use_cache :
            Whether to check and persist results in the local cache.

        Returns
        -------
        ``[{source, source_id, name, cui, root_source, ...}, ...]``
        """
        if not self.client:
            logger.warning("UMLS client not available")
            return []

        # Check cache first (keyed by source+code for simplicity)
        cache_key = f"xw:{source}:{code}:{target_source or '*'}"
        if use_cache and self._cache is not None:
            try:
                cached = self._cache.get_concept(cache_key)
                if cached:
                    return cached.get("crosswalk_results", [])
            except Exception:
                pass

        try:
            resp = await self.client.crosswalk_api.get_crosswalk(
                source=source,
                id=code,
                target_source=target_source,
                include_obsolete=include_obsolete,
                page_size=min(page_size, 100),
            )
            atoms: list = resp.result or []
        except Exception as exc:
            logger.error(
                "UMLS crosswalk failed for %s:%s → %s: %s",
                source,
                code,
                target_source or "ANY",
                exc,
            )
            return []

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for atom in atoms:
            cui = atom.cui or ""
            if cui in seen:
                continue
            seen.add(cui)
            results.append(
                {
                    "cui": cui,
                    "name": atom.name or "",
                    "source": atom.root_source or "",
                    "source_id": atom.code or atom.ui or "",
                    "term_type": atom.term_type,
                    "language": atom.language,
                }
            )

        # Cache results
        if use_cache and self._cache is not None and results:
            try:
                self._cache.cache_search_result(
                    cui=cache_key,
                    name=f"crosswalk {source}:{code}",
                    source=source,
                    semantic_types=[],
                    definitions=[],
                    synonyms=[],
                    categories=[target_source] if target_source else [],
                    confidence=1.0,
                )
            except Exception:
                pass

        return results

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

    # ── 8. RXNorm / SNOMED CT DOWNLOAD ─────────────────────────────

    async def download_terminology(
        self,
        release_name: str | None = None,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Download UMLS terminology files (RxNorm, SNOMED CT, etc.) to local disk.

        Uses the UMLS ``/download`` endpoint (added in the 2022AB release).
        When *release_name* is ``None``, lists available releases and downloads
        the current one.

        Parameters
        ----------
        release_name :
            Release identifier to download (e.g. ``\"2025AA\"``, ``\"RXNORM_2025AA\"``).
            If ``None``, the current (latest) release is downloaded.
        output_dir :
            Directory to save the downloaded files.  Defaults to
            ``~/.cache/knowledge-lookup/terminology/``.
        overwrite :
            Whether to overwrite existing files.

        Returns
        -------
        ``Path`` to the downloaded file or directory.
        """
        if not self.client:
            raise RuntimeError("UMLS client not available — cannot download terminology")

        out = Path(output_dir or (Path.home() / ".cache" / "knowledge-lookup" / "terminology"))
        out.mkdir(parents=True, exist_ok=True)

        try:
            # Resolve release if not specified
            if release_name is None:
                releases_resp = await self.client.release_api.list_releases(current=True)
                releases = releases_resp.result or []
                if not releases:
                    raise ValueError("No current UMLS release found")
                release_name = releases[0].name

            logger.info("Downloading UMLS release '%s' to %s", release_name, out)

            # The download_file method accepts a URL; we get the download
            # URL from the release metadata or construct it from the release name.
            # For simplicity, download the release archive (e.g. umls-2025aa.zip).
            url = (
                f"https://download.nlm.nih.gov/umls/kss/"
                f"{release_name}/umls-{release_name.lower()}-full.zip"
            )

            downloaded = await self.client.release_api.download_file(
                url=url,
                path=str(out),
                overwrite=overwrite,
            )
            result_path = Path(downloaded)
            logger.info("Downloaded UMLS release to %s", result_path)
            return result_path

        except Exception as exc:
            logger.error("Failed to download UMLS release '%s': %s", release_name, exc)
            raise

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_search_result(self, concept: UnifiedConcept, result: Any) -> None:
        """Persist a search result to the local cache."""
        if self._cache is None:
            return
        try:
            self._cache.cache_search_result(
                cui=concept.primary_id,
                name=concept.primary_label,
                source=(result.root_source or ""),
                semantic_types=[],
                definitions=concept.definitions,
                synonyms=concept.synonyms,
                categories=concept.categories,
                confidence=concept.confidence_score,
            )
        except Exception as exc:
            logger.debug("Failed to cache search result %s: %s", concept.primary_id, exc)

    def _cached_to_concept(self, cached: dict, query: str) -> UnifiedConcept:
        """Convert a cached concept dict to a ``UnifiedConcept``."""
        cui = cached.get("cui", "")
        name = cached.get("name", "")
        concept = UnifiedConcept(
            primary_id=cui,
            primary_label=name,
            concept_type=ConceptType.UNKNOWN,
        )
        concept.confidence_score = cached.get("score", 0.0)
        concept.definitions = cached.get("definitions", [])
        concept.synonyms = cached.get("synonyms", [])
        concept.categories = [cached.get("source", "")] if cached.get("source") else []
        concept.add_identifier(
            KnowledgeSource.UMLS,
            cui,
            name,
            f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
        )
        concept.source_data[KnowledgeSource.UMLS] = {
            "source": cached.get("source", ""),
            "cached": True,
        }

        # Confidence scoring
        query_lower = query.strip().lower()
        name_lower = name.strip().lower()
        if name_lower == query_lower:
            concept.confidence_score = max(concept.confidence_score, self._EXACT_MATCH_CONFIDENCE)
        elif query_lower in name_lower or name_lower in query_lower:
            concept.confidence_score = max(
                concept.confidence_score, self._PARTIAL_MATCH_CONFIDENCE + 0.1
            )

        # Determine concept type from saved semantic types
        sem_types = cached.get("semantic_types", [])
        if sem_types:
            mapped = self._determine_concept_type_from_semantic_type_names(sem_types)
            if mapped is not ConceptType.UNKNOWN:
                concept.concept_type = mapped

        return concept

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

        concept_type = self._determine_concept_type_from_profile(
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

    def _determine_concept_type_from_profile(self, profile) -> ConceptType:
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
