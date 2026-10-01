"""
Ensembl Genome Database Adapter

Integrates with the Ensembl REST API (https://rest.ensembl.org).

Lookup-interface coverage (consumed by ``CentralKnowledgeLookup``):

- ``lookup/symbol/:species/:symbol`` and ``xrefs/symbol/:species/:symbol``
  ("Lookup" / "Cross References") for :meth:`search_concepts`.
- ``lookup/id/:id`` ("Lookup") for :meth:`get_concept_details`.
- ``homology/id/:species/:id`` ("Comparative Genomics") for
  :meth:`get_relationships` (orthologous genes).
- ``xrefs/id/:id`` ("Cross References") for :meth:`get_mappings`
  (cross-database identifiers).

In addition, every family of the Ensembl REST catalog is exposed as a thin
async wrapper returning the raw parsed JSON. Unlike the interface methods
above, these propagate errors so the shared retry / circuit-breaker
machinery in :mod:`knowledge_lookup.base` handles transient failures:

- Archive: ``archive/id``
- Comparative genomics: ``cafe/genetree``, ``genetree``, ``alignment/region``,
  ``homology/symbol``
- Cross references: ``xrefs/name``
- Information: ``info/*`` (analysis, assembly, biotypes, compara, data,
  divisions, genomes, populations, ping, rest, software, species, variation)
- Linkage disequilibrium: ``ld/:species/:region``
- Lookup (batch): ``lookup/id``, ``lookup/symbol``
- Mapping: ``map/cdna``, ``map/cds``, ``map/:species``, ``map/translation``
- Ontologies: ``ontology`` hierarchy / parents / id
- Taxonomy: ``taxonomy`` id / name / common / root
- Overlap: ``overlap/id``, ``overlap/region``, ``overlap/translation``
- Phenotype: ``phenotype`` accession / gene / region / term
- Regulation: ``species/:species/binding_matrix``
- Sequence: ``sequence/id``, ``sequence/region``
- Transcript haplotypes: ``transcript/:id/haplotypes``
- VEP: ``vep/:species`` hgvs / id / region
- Variation: ``variation``, ``variation/pmcid``, ``variation/pmid``,
  ``variant_recoder``
- GA4GH: ``ga4gh`` beacon / callsets / datasets / features / featuresets /
  references / referencesets / searches / variants / variantsets
"""

import asyncio
import logging
from typing import Any

import aiohttp

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Ensembl's REST service has been observed taking well over the shared
# default per-request timeout (``LookupConfig.timeout_per_source``, 30s) to
# answer even successful requests under load. Without a longer budget here, a
# legitimately slow-but-succeeding response is cut off by aiohttp and then
# retried by the shared retry logic, compounding the delay instead of helping.
_MIN_TIMEOUT_SECONDS = 60.0


class EnsemblAdapter(KnowledgeSourceAdapter):
    """Adapter for Ensembl."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.ensembl.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ENSEMBL

    def is_available(self) -> bool:
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """Like the base implementation, but with a longer floor on the
        per-request timeout (see ``_MIN_TIMEOUT_SECONDS``)."""
        if self.session is None or self.session.closed:
            configured = self.config.timeout_per_source or 0.0
            timeout = aiohttp.ClientTimeout(total=max(configured, _MIN_TIMEOUT_SECONDS))
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Ensembl for genes.

        Ensembl has no free-text "search all" endpoint. This tries
        ``lookup/symbol`` first: a single round trip that resolves an exact
        canonical gene symbol (e.g. ``BRCA1``) directly to its record. Only
        when that doesn't match (a synonym, display name, or other external
        cross-reference rather than the canonical symbol) does it fall back
        to ``xrefs/symbol`` + ``lookup/id`` for the broader synonym-aware
        lookup, expanding any resulting hits concurrently rather than
        one-by-one: Ensembl's REST service can take several seconds per
        request under load, and a symbol can resolve to more than one object
        (e.g. a gene plus an LRG record), so running them sequentially
        multiplies that latency.
        """
        try:
            exact = await self._lookup_by_symbol(query)
            if exact is not None:
                logger.info(f"Ensembl search for '{query}' returned 1 concept (exact symbol)")
                return [exact]

            # Fallback: xrefs/symbol resolves synonyms/display names to one or
            # more Ensembl objects, each expanded via lookup/id.
            url = f"{self.base_url}/xrefs/symbol/homo_sapiens/{query}"
            params = {"content-type": "application/json"}

            data = await self._make_request(url, params)

            concepts: list[UnifiedConcept] = []
            if isinstance(data, list) and data:
                ids = [result.get("id", "") for result in data[:limit] if result.get("id")]
                details = await asyncio.gather(
                    *(self.get_concept_details(gene_id) for gene_id in ids),
                    return_exceptions=True,
                )
                for detail in details:
                    if isinstance(detail, BaseException):
                        logger.warning(f"Ensembl detail lookup failed during search: {detail}")
                    elif detail:
                        concepts.append(detail)

            logger.info(f"Ensembl search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Ensembl search failed for '{query}': {e}")
            return []

    async def _lookup_by_symbol(self, symbol: str) -> UnifiedConcept | None:
        """Exact-match gene symbol lookup via ``lookup/symbol`` — one fast
        round trip covering the common case of searching by a canonical gene
        symbol. Returns ``None`` for anything that isn't an exact match
        (including synonyms) or on any request failure, so callers fall back
        to ``xrefs/symbol``."""
        try:
            url = f"{self.base_url}/lookup/symbol/homo_sapiens/{symbol}"
            params = {"content-type": "application/json", "expand": 1}
            data = await self._make_request(url, params)
            if data and "id" in data:
                return self._convert_ensembl_result_to_concept(data)
            return None
        except Exception:
            return None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed gene information from Ensembl."""
        try:
            # concept_id should be Ensembl ID (e.g., ENSG00000139618)
            url = f"{self.base_url}/lookup/id/{concept_id}"
            params = {"content-type": "application/json", "expand": 1}

            data = await self._make_request(url, params)

            if data and "id" in data:
                concept = self._convert_ensembl_result_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Ensembl concept details for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return orthologous genes as edges, via the ``homology/id`` endpoint.

        ``concept_id`` must be an Ensembl gene ID (e.g. ``ENSG00000012048``).
        Returns the same ``{relation_label, related_id, related_name, source}``
        shape as the KEGG/STRING/WikiPathways adapters so the shared
        relationship-expansion source can consume it; degrades to ``[]`` on
        any failure. Ensembl's homology records name the target only by its
        own stable ID (no gene symbol), so ``related_name`` falls back to
        that ID.
        """
        gene_id = concept_id.strip()
        if not gene_id:
            return []
        try:
            url = f"{self.base_url}/homology/id/homo_sapiens/{gene_id}"
            params = {"content-type": "application/json", "type": "orthologues"}
            data = await self._make_request(url, params)

            entries = data.get("data") if isinstance(data, dict) else None
            if not entries:
                return []
            homologies = entries[0].get("homologies") or []

            relationships: list[dict[str, Any]] = []
            for homology in homologies[:limit]:
                target = homology.get("target") or {}
                related_id = (target.get("id") or "").strip()
                if not related_id:
                    continue
                relationships.append(
                    {
                        "relation_label": "ortholog",
                        "related_id": related_id,
                        "related_name": related_id,
                        "source": "Ensembl",
                        "species": target.get("species"),
                        "homology_type": homology.get("type"),
                    }
                )
            return relationships
        except Exception as e:
            logger.warning(f"Ensembl get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return cross-database references for an Ensembl ID via ``xrefs/id``.

        Uses the same ``{fromId, toId, fromSource, toSource, mappingType,
        confidence}`` shape as :meth:`KEGGAdapter.get_mappings`. Degrades to
        ``[]`` on any failure.
        """
        gene_id = concept_id.strip()
        if not gene_id:
            return []
        try:
            url = f"{self.base_url}/xrefs/id/{gene_id}"
            params = {"content-type": "application/json"}
            data = await self._make_request(url, params)
            if not isinstance(data, list):
                return []

            mappings: list[dict[str, Any]] = []
            for xref in data:
                db_name = xref.get("dbname", "")
                primary_id = xref.get("primary_id", "")
                if not db_name or not primary_id:
                    continue
                mappings.append(
                    {
                        "fromId": gene_id,
                        "toId": primary_id,
                        "fromSource": "Ensembl",
                        "toSource": db_name,
                        "mappingType": "xref",
                        "confidence": 0.9,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"Ensembl get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Full Ensembl REST catalog
    # ------------------------------------------------------------------
    #
    # Thin async wrappers over the entire Ensembl REST catalog (families
    # listed in the module docstring). All of them:
    #
    # - return the raw parsed JSON (``Any``) rather than a ``UnifiedConcept``;
    # - *propagate* exceptions so the shared retry / circuit-breaker
    #   machinery in :mod:`knowledge_lookup.base` handles transient failures
    #   (in deliberate contrast to the interface methods above, which
    #   degrade to empty results).

    def _params(self, **extra: Any) -> dict[str, Any]:
        """Query params for the REST wrappers below.

        Always includes the JSON ``content-type`` param Ensembl expects and
        drops any extra whose value is ``None`` so optional query params are
        only sent when set.
        """
        params: dict[str, Any] = {"content-type": "application/json"}
        for key, value in extra.items():
            if value is not None:
                params[key] = value
        return params

    # -- Archive ----------------------------------------------------------

    async def get_archive(self, archive_id: str) -> Any:
        """Fetch a stored REST response: ``GET /archive/id/:id``.

        ``archive_id`` is the archive identifier captured from the header of
        a previous Ensembl REST response.
        """
        return await self._make_request(
            f"{self.base_url}/archive/id/{archive_id}", params=self._params()
        )

    # -- Comparative genomics ----------------------------------------------

    async def get_cafes(
        self,
        species: str,
        limit: int = 50,
        offset: int = 0,
        cafe_type: str | None = None,
        tax_id: int | None = None,
        min_count: int | None = None,
        max_count: int | None = None,
    ) -> Any:
        """Copy-number changes (CAFE) on a species' gene tree:
        ``GET /cafe/genetree/:species``.

        ``cafe_type``: expansion | contraction.
        """
        return await self._make_request(
            f"{self.base_url}/cafe/genetree/{species}",
            params=self._params(
                limit=limit,
                offset=offset,
                type=cafe_type,
                tax_id=tax_id,
                min=min_count,
                max=max_count,
            ),
        )

    async def get_genetree(self, tax_id: int) -> Any:
        """Species tree rooted at a taxon: ``GET /genetree/:taxid``."""
        return await self._make_request(
            f"{self.base_url}/genetree/{tax_id}", params=self._params()
        )

    async def get_alignment(
        self,
        species: str,
        seq_region: str,
        start: int,
        end: int,
        upstream: int,
        downstream: int,
        alignment: str | None = None,
        method: str | None = None,
        data: str | None = None,
        type_: str | None = None,
    ) -> Any:
        """Conserved alignment over a region:
        ``GET /alignment/region/:species/:seqregion/:start/:end/:upstream/:downstream``.

        ``type_``: dna | pep.
        """
        url = (
            f"{self.base_url}/alignment/region/{species}/{seq_region}/{start}/{end}"
            f"/{upstream}/{downstream}"
        )
        return await self._make_request(
            url, params=self._params(alignment=alignment, method=method, data=data, type=type_)
        )

    async def get_homology_by_symbol(
        self,
        species: str,
        symbol: str,
        homology_type: str | None = None,
        target_species: str | None = None,
    ) -> Any:
        """Homologies for a gene symbol: ``GET /homology/symbol/:species/:symbol``.

        ``homology_type``: all | orthologues | paralogues | reciprocal |
        nonreciprocal | one2one | one2many | many2one | many2many.
        """
        return await self._make_request(
            f"{self.base_url}/homology/symbol/{species}/{symbol}",
            params=self._params(type=homology_type, target_species=target_species),
        )

    # -- Cross references ----------------------------------------------------

    async def get_xrefs_by_name(self, species: str, name: str, dbname: str) -> Any:
        """Cross-references for a name: ``GET /xrefs/name/:species/:name/:dbname``."""
        return await self._make_request(
            f"{self.base_url}/xrefs/name/{species}/{name}/{dbname}", params=self._params()
        )

    # -- Information ------------------------------------------------------------

    async def get_info_rest(self) -> Any:
        """REST service metadata: ``GET /info/rest``."""
        return await self._make_request(f"{self.base_url}/info/rest", params=self._params())

    async def get_info_ping(self) -> Any:
        """Service liveness check: ``GET /info/ping``."""
        return await self._make_request(f"{self.base_url}/info/ping", params=self._params())

    async def get_info_software(self) -> Any:
        """Installed software versions: ``GET /info/software``."""
        return await self._make_request(f"{self.base_url}/info/software", params=self._params())

    async def get_info_data(self, database: str | None = None) -> Any:
        """Database version info: ``GET /info/data`` or ``GET /info/data/:database``."""
        path = "/info/data" if database is None else f"/info/data/{database}"
        return await self._make_request(f"{self.base_url}{path}", params=self._params())

    async def get_info_species(
        self,
        species: str | None = None,
        tax_id: str | None = None,
        format_: str | None = None,
    ) -> Any:
        """Species and division info: ``GET /info/species``.

        ``format_``: list | hash.
        """
        return await self._make_request(
            f"{self.base_url}/info/species",
            params=self._params(species=species, tax_id=tax_id, format=format_),
        )

    async def get_info_variation(self) -> Any:
        """Variation database info: ``GET /info/variation``."""
        return await self._make_request(f"{self.base_url}/info/variation", params=self._params())

    async def get_info_assembly(
        self,
        species: str | None = None,
        tax_id: str | None = None,
        format_: str | None = None,
    ) -> Any:
        """Available assemblies: ``GET /info/assembly``.

        ``format_``: list | hash.
        """
        return await self._make_request(
            f"{self.base_url}/info/assembly",
            params=self._params(species=species, tax_id=tax_id, format=format_),
        )

    async def get_info_divisions(self) -> Any:
        """Available divisions: ``GET /info/divisions``."""
        return await self._make_request(f"{self.base_url}/info/divisions", params=self._params())

    async def get_info_biotypes(
        self,
        type_: str | None = None,
        species: str | None = None,
        tax_id: str | None = None,
    ) -> Any:
        """Available biotypes: ``GET /info/biotypes``.

        ``type_``: e.g. gene | regulatory.
        """
        return await self._make_request(
            f"{self.base_url}/info/biotypes",
            params=self._params(type=type_, species=species, tax_id=tax_id),
        )

    async def get_info_genomes(self, tax_id: int | None = None, format_: str | None = None) -> Any:
        """Available genome assemblies: ``GET /info/genomes``.

        ``format_``: list | hash.
        """
        return await self._make_request(
            f"{self.base_url}/info/genomes", params=self._params(tax_id=tax_id, format=format_)
        )

    async def get_info_populations(
        self, tax_id: int | None = None, format_: str | None = None
    ) -> Any:
        """Available populations: ``GET /info/populations``.

        ``format_``: list | hash.
        """
        return await self._make_request(
            f"{self.base_url}/info/populations", params=self._params(tax_id=tax_id, format=format_)
        )

    async def get_info_compara(self) -> Any:
        """Compara database info: ``GET /info/compara``."""
        return await self._make_request(f"{self.base_url}/info/compara", params=self._params())

    async def get_info_analysis(self, species: str | None = None) -> Any:
        """Genome analyses: ``GET /info/analysis``."""
        return await self._make_request(
            f"{self.base_url}/info/analysis", params=self._params(species=species)
        )

    # -- Linkage disequilibrium --------------------------------------------------

    async def get_ld(
        self,
        species: str,
        seq_region: str | None = None,
        seq_id: str | None = None,
        window: int = 2000,
        ld_measure: str = "r",
        limit: int = 2000,
        offset: int = 1,
    ) -> Any:
        """Linkage disequilibrium: ``GET /ld/:species/:seqregion``.

        ``seq_id`` is an alternative to ``seq_region``; ``ld_measure``:
        r | dprime.
        """
        region = seq_region or seq_id
        if not region:
            raise ValueError("get_ld requires either seq_region or seq_id")
        return await self._make_request(
            f"{self.base_url}/ld/{species}/{region}",
            params=self._params(window=window, ld=ld_measure, limit=limit, offset=offset),
        )

    # -- Lookup (batch) -----------------------------------------------------------

    async def lookup_ids(self, ids: list[str], expand: int = 0, all_: int = 0) -> Any:
        """Batch object lookup: ``POST /lookup/id`` with a JSON array of IDs.

        ``all_``: 1 to include objects from all databases, not just the
        matching species.
        """
        return await self._make_request(
            f"{self.base_url}/lookup/id",
            params=self._params(expand=expand, all=all_),
            json_data=list(ids),
        )

    async def lookup_symbols(
        self,
        species: str,
        symbols: list[str],
        expand: int = 0,
        all_: int = 0,
    ) -> Any:
        """Batch symbol lookup: ``POST /lookup/symbol`` with a JSON array of
        symbols (``species`` is a query param on this endpoint)."""
        return await self._make_request(
            f"{self.base_url}/lookup/symbol",
            params=self._params(species=species, expand=expand, all=all_),
            json_data=list(symbols),
        )

    # -- Mapping ----------------------------------------------------------------------

    async def map_cdna(
        self,
        cdna_id: str,
        types: list[str] | None = None,
        type_: str | None = None,
    ) -> Any:
        """Map a cDNA to features: ``GET/POST /map/cdna/:cdna_id``.

        Pass ``types`` for a POST with a JSON array of feature types (e.g.
        ``["exon", "transcript"]``) or ``type_`` for a GET with a single
        comma-separated ``type`` param.
        """
        url = f"{self.base_url}/map/cdna/{cdna_id}"
        if types:
            return await self._make_request(url, params=self._params(), json_data=list(types))
        return await self._make_request(url, params=self._params(type=type_))

    async def map_cds(
        self,
        cds_id: str,
        types: list[str] | None = None,
        type_: str | None = None,
    ) -> Any:
        """Map a CDS to features: ``GET/POST /map/cds/:cds_id`` (see
        :meth:`map_cdna` for the ``types``/``type_`` contract)."""
        url = f"{self.base_url}/map/cds/{cds_id}"
        if types:
            return await self._make_request(url, params=self._params(), json_data=list(types))
        return await self._make_request(url, params=self._params(type=type_))

    async def map_translation(
        self,
        translation_id: str,
        types: list[str] | None = None,
        type_: str | None = None,
    ) -> Any:
        """Map a translation to features: ``GET/POST /map/translation/:id`` (see
        :meth:`map_cdna` for the ``types``/``type_`` contract)."""
        url = f"{self.base_url}/map/translation/{translation_id}"
        if types:
            return await self._make_request(url, params=self._params(), json_data=list(types))
        return await self._make_request(url, params=self._params(type=type_))

    async def map_ids(self, species: str, ids: list[str], target: str) -> Any:
        """Map a batch of IDs between feature types: ``POST /map/:species``.

        Body: ``{"id": [...], "target": ...}`` with ``target`` one of
        cdna | cds | exon | genomic | protein (all ``id`` entries must be
        the same type).
        """
        return await self._make_request(
            f"{self.base_url}/map/{species}",
            params=self._params(),
            json_data={"id": list(ids), "target": target},
        )

    # -- Ontologies -----------------------------------------------------------------------

    async def get_ontology(
        self,
        ontology_type: str,
        term: str | None = None,
        type_: str | None = None,
        id_: str | None = None,
    ) -> Any:
        """Search an ontology: ``GET /ontology/:ontology_type`` (e.g. ``go``).

        ``type_``: e.g. molecular_function | biological_process |
        cellular_component (ontology-dependent); ``id_`` filters to a single
        term ID.
        """
        return await self._make_request(
            f"{self.base_url}/ontology/{ontology_type}",
            params=self._params(term=term, type=type_, id=id_),
        )

    async def get_ontology_parents(self, term_id: str) -> Any:
        """Parent terms: ``GET /ontology/parents/:id``."""
        return await self._make_request(
            f"{self.base_url}/ontology/parents/{term_id}", params=self._params()
        )

    async def get_ontology_id(self, term_id: str) -> Any:
        """A single term: ``GET /ontology/id/:term_id``."""
        return await self._make_request(
            f"{self.base_url}/ontology/id/{term_id}", params=self._params()
        )

    # -- Taxonomy ----------------------------------------------------------------------------

    async def get_taxonomy_id(self, tax_id: int) -> Any:
        """Species by NCBI taxon ID: ``GET /taxonomy/id/:tax_id``."""
        return await self._make_request(
            f"{self.base_url}/taxonomy/id/{tax_id}", params=self._params()
        )

    async def get_taxonomy_name(self, name: str) -> Any:
        """Species by scientific name: ``GET /taxonomy/name/:name``."""
        return await self._make_request(
            f"{self.base_url}/taxonomy/name/{name}", params=self._params()
        )

    async def get_taxonomy_common(self, common_name: str) -> Any:
        """Species by common name: ``GET /taxonomy/common/:common_name``."""
        return await self._make_request(
            f"{self.base_url}/taxonomy/common/{common_name}", params=self._params()
        )

    async def get_taxonomy_root(self) -> Any:
        """Root of the taxonomy: ``GET /taxonomy/root``."""
        return await self._make_request(f"{self.base_url}/taxonomy/root", params=self._params())

    # -- Overlap ------------------------------------------------------------------------------

    async def overlap_ids(
        self,
        ids: list[str],
        feature: str | None = None,
        all_: int | None = None,
    ) -> Any:
        """Objects overlapping Ensembl IDs: ``POST /overlap/id`` with a JSON
        array of IDs."""
        return await self._make_request(
            f"{self.base_url}/overlap/id",
            params=self._params(feature=feature, all=all_),
            json_data=list(ids),
        )

    async def get_overlap_region(
        self,
        species: str,
        seq_region: str,
        start: int,
        end: int,
        up: int = 0,
        down: int = 0,
        feature: str | None = None,
        all_: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        """Objects overlapping a region:
        ``GET /overlap/region/:species/:seq_region/:start/:end``.

        ``feature``: e.g. gene | transcript | regulatory; ``all_``: 1 to
        include all overlapping objects.
        """
        return await self._make_request(
            f"{self.base_url}/overlap/region/{species}/{seq_region}/{start}/{end}",
            params=self._params(
                up=up, down=down, feature=feature, all=all_, limit=limit, offset=offset
            ),
        )

    async def overlap_translations(
        self,
        translation_ids: list[str],
        feature: str | None = None,
        all_: int | None = None,
    ) -> Any:
        """Objects overlapping protein translations: ``POST /overlap/translation``
        with a JSON array of IDs."""
        return await self._make_request(
            f"{self.base_url}/overlap/translation",
            params=self._params(feature=feature, all=all_),
            json_data=list(translation_ids),
        )

    # -- Phenotype --------------------------------------------------------------------------------

    async def get_phenotypes(
        self,
        species: str | None = None,
        term: str | None = None,
        accession: str | None = None,
        gene: str | None = None,
        region: str | None = None,
        limit: int = 100,
        offset: int = 1,
    ) -> Any:
        """Search phenotypes: ``GET /phenotype``.

        ``region``: ``species:seq_region:start-end``.
        """
        return await self._make_request(
            f"{self.base_url}/phenotype",
            params=self._params(
                species=species,
                term=term,
                accession=accession,
                gene=gene,
                region=region,
                limit=limit,
                offset=offset,
            ),
        )

    async def get_phenotype(self, accession: str) -> Any:
        """A single phenotype: ``GET /phenotype/:accession``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/{accession}", params=self._params()
        )

    async def get_phenotype_by_accession(self, accession: str) -> Any:
        """Phenotypes by accession: ``GET /phenotype/accession/:accession``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/accession/{accession}", params=self._params()
        )

    async def get_phenotypes_by_gene(self, gene: str, species: str | None = None) -> Any:
        """Phenotypes for a gene: ``GET /phenotype/gene/:gene``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/gene/{gene}", params=self._params(species=species)
        )

    async def get_phenotypes_by_region(
        self, species: str, seq_region: str, start: int, end: int
    ) -> Any:
        """Phenotypes in a region:
        ``GET /phenotype/region/:species/:seq_region/:start/:end``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/region/{species}/{seq_region}/{start}/{end}",
            params=self._params(),
        )

    async def get_phenotypes_by_term(self, term: str) -> Any:
        """Phenotypes for a term: ``GET /phenotype/term/:term``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/term/{term}", params=self._params()
        )

    # -- Regulation -----------------------------------------------------------------------------------

    async def get_binding_matrix(
        self,
        species: str,
        feature: str = "protein_coding",
        matrix_type: str = "all",
        limit: int = 100,
        offset: int = 1,
        min_: int | None = None,
        max_: int | None = None,
    ) -> Any:
        """Regulatory binding sites: ``GET /species/:species/binding_matrix``.

        ``matrix_type``: all | motif | domain; ``min_``/``max_``:
        matrix-score bounds.
        """
        return await self._make_request(
            f"{self.base_url}/species/{species}/binding_matrix",
            params=self._params(
                feature=feature,
                type=matrix_type,
                limit=limit,
                offset=offset,
                min=min_,
                max=max_,
            ),
        )

    # -- Sequence ---------------------------------------------------------------------------------------

    async def get_sequences(
        self,
        ids: list[str],
        type_: str = "dna",
        class_: str | None = None,
    ) -> Any:
        """Sequences by Ensembl ID: ``POST /sequence/id`` with a JSON array.

        ``type_``: dna | cdna | pep.
        """
        params = self._params(type=type_)
        if class_ is not None:
            params["class"] = class_
        return await self._make_request(
            f"{self.base_url}/sequence/id",
            params=params,
            json_data=list(ids),
        )

    async def get_sequence(
        self,
        species: str,
        seq_region: str,
        start: int,
        end: int,
        type_: str = "dna",
        class_: str | None = None,
    ) -> Any:
        """Sequence of a region:
        ``GET /sequence/region/:species/:seq_region/:start/:end``.

        ``type_``: dna | cdna | pep.
        """
        params = self._params(type=type_)
        if class_ is not None:
            params["class"] = class_
        return await self._make_request(
            f"{self.base_url}/sequence/region/{species}/{seq_region}/{start}/{end}",
            params=params,
        )

    # -- Transcript haplotypes ------------------------------------------------------------------------------

    async def get_transcript_haplotypes(
        self,
        transcript_id: str,
        assembly: str | None = None,
        population: str | None = None,
        type_: str | None = None,
        min_: float | None = None,
        max_: float | None = None,
    ) -> Any:
        """Haplotype coverage of a transcript: ``GET /transcript/:id/haplotypes``.

        ``type_``: ref | alt; ``min_``/``max_``: frequency bounds.
        """
        return await self._make_request(
            f"{self.base_url}/transcript/{transcript_id}/haplotypes",
            params=self._params(
                assembly=assembly, population=population, type=type_, min=min_, max=max_
            ),
        )

    # -- VEP -----------------------------------------------------------------------------------------------------

    async def vep_hgvs(self, species: str, hgvs: list[str], **params: Any) -> Any:
        """VEP over HGVS variant strings: ``POST /vep/:species/hgvs`` with a JSON
        array.

        Extra VEP options (``cache``, ``dir``, ``canonical``, ``extra``,
        ``population``, ``hgvs``, ``limit``, ``offset``) pass through as
        query params.
        """
        return await self._make_request(
            f"{self.base_url}/vep/{species}/hgvs",
            params=self._params(**params),
            json_data=list(hgvs),
        )

    async def vep_ids(self, species: str, ids: list[str], **params: Any) -> Any:
        """VEP over Ensembl variation IDs: ``POST /vep/:species/id`` with a JSON
        array (extra VEP options as in :meth:`vep_hgvs`)."""
        return await self._make_request(
            f"{self.base_url}/vep/{species}/id",
            params=self._params(**params),
            json_data=list(ids),
        )

    async def vep_regions(
        self,
        species: str,
        regions: list[str | dict[str, Any]],
        **params: Any,
    ) -> Any:
        """VEP over genomic regions: ``POST /vep/:species/region`` with a JSON
        array of region strings or dicts (extra VEP options as in
        :meth:`vep_hgvs`)."""
        return await self._make_request(
            f"{self.base_url}/vep/{species}/region",
            params=self._params(**params),
            json_data=list(regions),
        )

    # -- Variation ---------------------------------------------------------------------------------------------

    async def get_variations(
        self,
        spid: str,
        type_: str | None = None,
        feature_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Any:
        """Variations for species: ``GET /variation``.

        ``spid``: one or more ``|``-separated species; ``type_``: snp | mnv |
        ins | del | ...
        """
        return await self._make_request(
            f"{self.base_url}/variation",
            params=self._params(
                spid=spid, type=type_, feature_type=feature_type, limit=limit, offset=offset
            ),
        )

    async def get_variations_by_pmcid(self, pmcid: str, limit: int = 10, offset: int = 1) -> Any:
        """Variations in a PMC article: ``GET /variation/pmcid/:pmcid``."""
        return await self._make_request(
            f"{self.base_url}/variation/pmcid/{pmcid}",
            params=self._params(limit=limit, offset=offset),
        )

    async def get_variations_by_pmid(self, pmid: str, limit: int = 10, offset: int = 1) -> Any:
        """Variations in a PubMed article: ``GET /variation/pmid/:pmid``."""
        return await self._make_request(
            f"{self.base_url}/variation/pmid/{pmid}",
            params=self._params(limit=limit, offset=offset),
        )

    async def variant_recoder(
        self,
        spid: str,
        type_: str | None = None,
        feature_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Any:
        """Variant recoding between reference genomes: ``GET /variant_recoder``."""
        return await self._make_request(
            f"{self.base_url}/variant_recoder",
            params=self._params(
                spid=spid, type=type_, feature_type=feature_type, limit=limit, offset=offset
            ),
        )

    # -- GA4GH --------------------------------------------------------------------------------------------------------

    async def _ga4gh(self, resource: str, resource_id: str | None = None, **params: Any) -> Any:
        """Shared helper for the GA4GH v0.7 endpoints under ``/ga4gh``.

        Each resource has a list form (``/ga4gh/<resource>``) and, where the
        API supports it, a single-item form (``/ga4gh/<resource>/:id``).
        """
        path = f"/ga4gh/{resource}"
        if resource_id is not None:
            path += f"/{resource_id}"
        return await self._make_request(f"{self.base_url}{path}", params=self._params(**params))

    async def ga4gh_beacon(self, **params: Any) -> Any:
        """Beacon search: ``GET /ga4gh/beacon`` (``study``, ``dataset``,
        ``variant``)."""
        return await self._ga4gh("beacon", **params)

    async def ga4gh_callsets(self, callset_id: str | None = None, **params: Any) -> Any:
        """Callsets: ``GET /ga4gh/callsets`` or ``GET /ga4gh/callsets/:id``."""
        return await self._ga4gh("callsets", callset_id, **params)

    async def ga4gh_datasets(self, dataset_id: str | None = None, **params: Any) -> Any:
        """Datasets: ``GET /ga4gh/datasets`` or ``GET /ga4gh/datasets/:id``."""
        return await self._ga4gh("datasets", dataset_id, **params)

    async def ga4gh_features(self, featureset: str | None = None, **params: Any) -> Any:
        """Features: ``GET /ga4gh/features`` (``featureset`` query param)."""
        if featureset is not None:
            params["featureset"] = featureset
        return await self._ga4gh("features", **params)

    async def ga4gh_featuresets(self, featureset_id: str | None = None, **params: Any) -> Any:
        """Feature sets: ``GET /ga4gh/featuresets`` or ``GET /ga4gh/featuresets/:id``."""
        return await self._ga4gh("featuresets", featureset_id, **params)

    async def ga4gh_references(self, reference_id: str | None = None, **params: Any) -> Any:
        """References: ``GET /ga4gh/references`` or ``GET /ga4gh/references/:id``."""
        return await self._ga4gh("references", reference_id, **params)

    async def ga4gh_referencesets(self, referenceset_id: str | None = None, **params: Any) -> Any:
        """Reference sets: ``GET /ga4gh/referencesets`` or
        ``GET /ga4gh/referencesets/:id``."""
        return await self._ga4gh("referencesets", referenceset_id, **params)

    async def ga4gh_searches(self, search_id: str | None = None, **params: Any) -> Any:
        """Searches: ``GET /ga4gh/searches`` or ``GET /ga4gh/searches/:id``."""
        return await self._ga4gh("searches", search_id, **params)

    async def ga4gh_variants(self, variant_id: str | None = None, **params: Any) -> Any:
        """Variants: ``GET /ga4gh/variants`` or ``GET /ga4gh/variants/:id``."""
        return await self._ga4gh("variants", variant_id, **params)

    async def ga4gh_variantsets(self, variantset_id: str | None = None, **params: Any) -> Any:
        """Variant sets: ``GET /ga4gh/variantsets`` or ``GET /ga4gh/variantsets/:id``."""
        return await self._ga4gh("variantsets", variantset_id, **params)

    def _convert_ensembl_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Ensembl API result to unified concept."""
        try:
            ensembl_id = result.get("id", "")
            label = result.get("display_name", ensembl_id)

            concept = UnifiedConcept(
                primary_id=ensembl_id, primary_label=label, concept_type=ConceptType.GENE
            )

            concept.add_identifier(
                KnowledgeSource.ENSEMBL,
                ensembl_id,
                label,
                f"https://www.ensembl.org/id/{ensembl_id}",
            )

            if "description" in result:
                if concept.definitions is not None:
                    concept.definitions.append(result["description"])

            if "biotype" in result:
                if concept.categories is not None:
                    concept.categories.append(f"Biotype: {result['biotype']}")

            if "species" in result:
                if concept.categories is not None:
                    concept.categories.append(f"Species: {result['species']}")

            concept.confidence_score = 1.0
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.ENSEMBL] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Ensembl result: {e}")
            return None
