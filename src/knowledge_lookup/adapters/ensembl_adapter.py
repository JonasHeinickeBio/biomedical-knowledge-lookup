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
  ``homology/id``, ``homology/symbol``
- Cross references: ``xrefs/name``
- Information: ``info/*`` (analysis, assembly, biotypes, compara, consequence
  types, data, divisions, eg_version, external_dbs, genomes, populations,
  ping, rest, software, species, variation)
- Linkage disequilibrium: ``ld/:species/:id/:population``,
  ``ld/:species/pairwise/:id1/:id2``, ``ld/:species/region/:region/:population``
- Lookup (batch): ``lookup/id``, ``lookup/symbol``
- Mapping: ``map/cdna``, ``map/cds``, ``map/translation``
- Ontologies: ``ontology`` ancestors / ancestors/chart / descendants / id /
  name
- Taxonomy: ``taxonomy`` id / name / classification
- Overlap: ``overlap/id``, ``overlap/region``, ``overlap/translation``
- Phenotype: ``phenotype`` accession / gene / region / term
- Regulation: ``species/:species/binding_matrix/:stable_id``
- Sequence: ``sequence/id``, ``sequence/region``
- Transcript haplotypes: ``transcript_haplotypes/:species/:id``
- VEP: ``vep/:species`` hgvs / id / region (single GET and batch POST)
- Variation: ``variation/:species/:id`` (GET and batch POST),
  ``variation/:species/pmcid``, ``variation/:species/pmid``,
  ``variant_recoder/:species/:id`` (GET and batch POST)
- GA4GH: ``ga4gh`` beacon / beacon/query / callsets / datasets / features /
  featuresets / references / variants / variantsets — single-item GETs plus
  the POST ``<resource>/search`` endpoints (15.12 has no list GETs,
  referencesets or searches)
"""

import asyncio
import logging
from typing import Any
from urllib.parse import quote

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

    min_request_timeout = _MIN_TIMEOUT_SECONDS

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.ensembl.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ENSEMBL

    def is_available(self) -> bool:
        return True

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

    async def get_cafe_genetree(self, gene_id: str) -> Any:
        """Copy-number events (CAFE) on the gene tree of a gene:
        ``GET /cafe/genetree/id/:id``."""
        return await self._make_request(
            f"{self.base_url}/cafe/genetree/id/{gene_id}", params=self._params()
        )

    async def get_cafe_genetree_by_symbol(self, species: str, symbol: str) -> Any:
        """CAFE gene tree via a gene symbol:
        ``GET /cafe/genetree/member/symbol/:species/:symbol``."""
        return await self._make_request(
            f"{self.base_url}/cafe/genetree/member/symbol/{species}/{symbol}",
            params=self._params(),
        )

    async def get_genetree(self, gene_id: str) -> Any:
        """Gene tree containing a gene: ``GET /genetree/id/:id``."""
        return await self._make_request(
            f"{self.base_url}/genetree/id/{gene_id}", params=self._params()
        )

    async def get_genetree_by_symbol(self, species: str, symbol: str) -> Any:
        """Gene tree via a gene symbol:
        ``GET /genetree/member/symbol/:species/:symbol``."""
        return await self._make_request(
            f"{self.base_url}/genetree/member/symbol/{species}/{symbol}",
            params=self._params(),
        )

    async def get_alignment(
        self,
        species: str,
        region: str,
        method: str | None = None,
        alignment: str | None = None,
        data: str | None = None,
        type_: str | None = None,
    ) -> Any:
        """Conserved alignment over a region:
        ``GET /alignment/region/:species/:region``.

        ``region`` is a coordinate string such as ``"11:2159779-2159779:1"``;
        ``type_``: dna | pep.
        """
        return await self._make_request(
            f"{self.base_url}/alignment/region/{species}/{region}",
            params=self._params(alignment=alignment, method=method, data=data, type=type_),
        )

    async def get_homology_by_id(
        self,
        species: str,
        gene_id: str,
        homology_type: str | None = None,
        target_species: str | None = None,
    ) -> Any:
        """Homologies for an Ensembl gene ID: ``GET /homology/id/:species/:id``.

        ``homology_type``: all | orthologues | paralogues | reciprocal |
        nonreciprocal | one2one | one2many | many2one | many2many.
        """
        return await self._make_request(
            f"{self.base_url}/homology/id/{species}/{gene_id}",
            params=self._params(type=homology_type, target_species=target_species),
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

    async def get_xrefs_by_name(self, species: str, name: str, dbname: str | None = None) -> Any:
        """Cross-references for a name: ``GET /xrefs/name/:species/:name``.

        ``dbname`` is now an optional query filter rather than a path segment.
        """
        return await self._make_request(
            f"{self.base_url}/xrefs/name/{species}/{name}", params=self._params(dbname=dbname)
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

    async def get_info_variation(self, species: str) -> Any:
        """Variation databases for a species: ``GET /info/variation/:species``."""
        return await self._make_request(
            f"{self.base_url}/info/variation/{species}", params=self._params()
        )

    async def get_info_consequence_types(self) -> Any:
        """All known consequence types: ``GET /info/variation/consequence_types``."""
        return await self._make_request(
            f"{self.base_url}/info/variation/consequence_types", params=self._params()
        )

    async def get_info_assembly(self, species: str, region_name: str | None = None) -> Any:
        """Assembly for a species, optionally one region:
        ``GET /info/assembly/:species`` or ``GET /info/assembly/:species/:region_name``."""
        path = f"/info/assembly/{species}"
        if region_name is not None:
            path += f"/{region_name}"
        return await self._make_request(f"{self.base_url}{path}", params=self._params())

    async def get_info_divisions(self) -> Any:
        """Available divisions: ``GET /info/divisions``."""
        return await self._make_request(f"{self.base_url}/info/divisions", params=self._params())

    async def get_info_biotypes(self, species: str, type_: str | None = None) -> Any:
        """Biotypes for a species: ``GET /info/biotypes/:species``.

        ``type_``: e.g. gene | regulatory.
        """
        return await self._make_request(
            f"{self.base_url}/info/biotypes/{species}", params=self._params(type=type_)
        )

    async def get_info_biotypes_by_name(self, name: str, object_type: str) -> Any:
        """Biotype by name: ``GET /info/biotypes/name/:name/:object_type``."""
        return await self._make_request(
            f"{self.base_url}/info/biotypes/name/{name}/{object_type}", params=self._params()
        )

    async def get_info_biotypes_by_group(self, group: str, object_type: str) -> Any:
        """Biotypes by group: ``GET /info/biotypes/groups/:group/:object_type``."""
        return await self._make_request(
            f"{self.base_url}/info/biotypes/groups/{group}/{object_type}", params=self._params()
        )

    async def get_info_external_dbs(self, species: str) -> Any:
        """External databases used by a species: ``GET /info/external_dbs/:species``."""
        return await self._make_request(
            f"{self.base_url}/info/external_dbs/{species}", params=self._params()
        )

    async def get_info_eg_version(self) -> Any:
        """Ensembl Genomes release: ``GET /info/eg_version``."""
        return await self._make_request(f"{self.base_url}/info/eg_version", params=self._params())

    async def get_info_genome(self, genome_name: str) -> Any:
        """Genome by name: ``GET /info/genomes/:genome_name``."""
        return await self._make_request(
            f"{self.base_url}/info/genomes/{genome_name}", params=self._params()
        )

    async def get_info_genomes_by_accession(self, accession: str) -> Any:
        """Genomes by assembly accession: ``GET /info/genomes/accession/:accession``."""
        return await self._make_request(
            f"{self.base_url}/info/genomes/accession/{accession}", params=self._params()
        )

    async def get_info_genomes_by_assembly(self, assembly_id: str) -> Any:
        """Genomes by assembly ID: ``GET /info/genomes/assembly/:assembly_id``."""
        return await self._make_request(
            f"{self.base_url}/info/genomes/assembly/{assembly_id}", params=self._params()
        )

    async def get_info_genomes_by_division(self, division_name: str) -> Any:
        """Genomes by division: ``GET /info/genomes/division/:division_name``."""
        return await self._make_request(
            f"{self.base_url}/info/genomes/division/{division_name}", params=self._params()
        )

    async def get_info_genomes_by_taxonomy(self, taxon_name: str) -> Any:
        """Genomes by taxon name: ``GET /info/genomes/taxonomy/:taxon_name``."""
        return await self._make_request(
            f"{self.base_url}/info/genomes/taxonomy/{taxon_name}", params=self._params()
        )

    async def get_info_populations(self, species: str, population_name: str | None = None) -> Any:
        """Populations for a species: ``GET /info/variation/populations/:species``
        (optionally ``/:population_name``)."""
        path = f"/info/variation/populations/{species}"
        if population_name is not None:
            path += f"/{population_name}"
        return await self._make_request(f"{self.base_url}{path}", params=self._params())

    async def get_info_comparas(self) -> Any:
        """Compara database releases: ``GET /info/comparas``."""
        return await self._make_request(f"{self.base_url}/info/comparas", params=self._params())

    async def get_info_compara_methods(self) -> Any:
        """Compara analysis methods: ``GET /info/compara/methods``."""
        return await self._make_request(
            f"{self.base_url}/info/compara/methods", params=self._params()
        )

    async def get_info_compara_species_sets(self, method: str) -> Any:
        """Species sets for a Compara method:
        ``GET /info/compara/species_sets/:method``."""
        return await self._make_request(
            f"{self.base_url}/info/compara/species_sets/{method}", params=self._params()
        )

    async def get_info_analysis(self, species: str) -> Any:
        """Analyses for a species: ``GET /info/analysis/:species``."""
        return await self._make_request(
            f"{self.base_url}/info/analysis/{species}", params=self._params()
        )

    # -- Linkage disequilibrium --------------------------------------------------

    async def get_ld_by_id(
        self,
        species: str,
        id_: str,
        population_name: str,
        window_size: int | None = None,
        d_prime: float | None = None,
        r2: float | None = None,
    ) -> Any:
        """LD around a variant: ``GET /ld/:species/:id/:population_name``."""
        return await self._make_request(
            f"{self.base_url}/ld/{species}/{id_}/{population_name}",
            params=self._params(window_size=window_size, d_prime=d_prime, r2=r2),
        )

    async def get_ld_pairwise(
        self,
        species: str,
        id1: str,
        id2: str,
        population_name: str | None = None,
        d_prime: float | None = None,
        r2: float | None = None,
    ) -> Any:
        """LD between two variants: ``GET /ld/:species/pairwise/:id1/:id2``.

        Without ``population_name`` the server returns one record per
        population; with it, only that population's record.
        """
        return await self._make_request(
            f"{self.base_url}/ld/{species}/pairwise/{id1}/{id2}",
            params=self._params(population_name=population_name, d_prime=d_prime, r2=r2),
        )

    async def get_ld_region(
        self,
        species: str,
        region: str,
        population_name: str,
        window_size: int | None = None,
        d_prime: float | None = None,
        r2: float | None = None,
    ) -> Any:
        """LD in a region: ``GET /ld/:species/region/:region/:population_name``."""
        return await self._make_request(
            f"{self.base_url}/ld/{species}/region/{region}/{population_name}",
            params=self._params(window_size=window_size, d_prime=d_prime, r2=r2),
        )

    # -- Lookup (batch) -----------------------------------------------------------

    async def lookup_ids(self, ids: list[str], expand: int = 0, all_: int = 0) -> Any:
        """Batch object lookup: ``POST /lookup/id`` with body ``{"ids": [...]}``.

        (A bare JSON array is rejected by the server with a 500.)

        ``all_``: 1 to include objects from all databases, not just the
        matching species.
        """
        return await self._make_request(
            f"{self.base_url}/lookup/id",
            params=self._params(expand=expand, all=all_),
            json_data={"ids": list(ids)},
        )

    async def lookup_symbols(
        self,
        species: str,
        symbols: list[str],
        expand: int = 0,
        all_: int = 0,
    ) -> Any:
        """Batch symbol lookup: ``POST /lookup/symbol/:species`` with body
        ``{"symbols": [...]}``."""
        return await self._make_request(
            f"{self.base_url}/lookup/symbol/{species}",
            params=self._params(expand=expand, all=all_),
            json_data={"symbols": list(symbols)},
        )

    # -- Mapping ----------------------------------------------------------------------

    async def map_cdna(self, cdna_id: str, region: str) -> Any:
        """Map a cDNA coordinate range to genomic features:
        ``GET /map/cdna/:id/:region`` (``region`` like ``100..200``)."""
        return await self._make_request(
            f"{self.base_url}/map/cdna/{cdna_id}/{region}", params=self._params()
        )

    async def map_cds(self, cds_id: str, region: str) -> Any:
        """Map a CDS coordinate range to genomic features:
        ``GET /map/cds/:id/:region``."""
        return await self._make_request(
            f"{self.base_url}/map/cds/{cds_id}/{region}", params=self._params()
        )

    async def map_translation(self, translation_id: str, region: str) -> Any:
        """Map translation (protein) coordinates onto genomic features:
        ``GET /map/translation/:id/:region``."""
        return await self._make_request(
            f"{self.base_url}/map/translation/{translation_id}/{region}", params=self._params()
        )

    # -- Ontologies -----------------------------------------------------------------------

    async def get_ontology_by_name(self, name: str) -> Any:
        """Terms for an ontology by name: ``GET /ontology/name/:name``."""
        return await self._make_request(
            f"{self.base_url}/ontology/name/{name}", params=self._params()
        )

    async def get_ontology_ancestors(self, term_id: str) -> Any:
        """Ancestor terms: ``GET /ontology/ancestors/:id``."""
        return await self._make_request(
            f"{self.base_url}/ontology/ancestors/{term_id}", params=self._params()
        )

    async def get_ontology_ancestors_chart(self, term_id: str) -> Any:
        """Ancestor chart: ``GET /ontology/ancestors/chart/:id``."""
        return await self._make_request(
            f"{self.base_url}/ontology/ancestors/chart/{term_id}", params=self._params()
        )

    async def get_ontology_descendants(self, term_id: str) -> Any:
        """Descendant terms: ``GET /ontology/descendants/:id``."""
        return await self._make_request(
            f"{self.base_url}/ontology/descendants/{term_id}", params=self._params()
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

    async def get_taxonomy_classification(self, tax_id: str) -> Any:
        """Full lineage of a taxon: ``GET /taxonomy/classification/:id``."""
        return await self._make_request(
            f"{self.base_url}/taxonomy/classification/{tax_id}", params=self._params()
        )

    # -- Overlap ------------------------------------------------------------------------------

    async def get_overlap_id(
        self,
        id_: str,
        feature: str | None = None,
        all_: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        """Objects overlapping an Ensembl ID: ``GET /overlap/id/:id``.

        ``feature``: e.g. gene | transcript | variation.
        """
        return await self._make_request(
            f"{self.base_url}/overlap/id/{id_}",
            params=self._params(feature=feature, all=all_, limit=limit, offset=offset),
        )

    async def get_overlap_region(
        self,
        species: str,
        region: str,
        feature: str | None = None,
        all_: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        """Objects overlapping a region: ``GET /overlap/region/:species/:region``.

        ``region`` is a coordinate string like ``X:1000000..1001000``;
        ``feature``: e.g. gene | transcript | regulatory.
        """
        return await self._make_request(
            f"{self.base_url}/overlap/region/{species}/{region}",
            params=self._params(feature=feature, all=all_, limit=limit, offset=offset),
        )

    async def get_overlap_translation(
        self,
        translation_id: str,
        feature: str | None = None,
        all_: int | None = None,
    ) -> Any:
        """Domain features overlapping a translation:
        ``GET /overlap/translation/:id``."""
        return await self._make_request(
            f"{self.base_url}/overlap/translation/{translation_id}",
            params=self._params(feature=feature, all=all_),
        )

    # -- Phenotype --------------------------------------------------------------------------------

    async def get_phenotypes_by_gene(
        self, species: str, id_: str, limit: int = 100, offset: int = 1
    ) -> Any:
        """Phenotypes annotated to a gene: ``GET /phenotype/gene/:species/:id``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/gene/{species}/{id_}",
            params=self._params(limit=limit, offset=offset),
        )

    async def get_phenotype_by_accession(
        self, species: str, accession: str, limit: int = 100, offset: int = 1
    ) -> Any:
        """Phenotypes by accession:
        ``GET /phenotype/accession/:species/:accession``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/accession/{species}/{accession}",
            params=self._params(limit=limit, offset=offset),
        )

    async def get_phenotypes_by_region(
        self, species: str, region: str, limit: int = 100, offset: int = 1
    ) -> Any:
        """Phenotypes in a region: ``GET /phenotype/region/:species/:region``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/region/{species}/{region}",
            params=self._params(limit=limit, offset=offset),
        )

    async def get_phenotypes_by_term(
        self, species: str, term: str, limit: int = 100, offset: int = 1
    ) -> Any:
        """Phenotypes matching a description:
        ``GET /phenotype/term/:species/:term``."""
        return await self._make_request(
            f"{self.base_url}/phenotype/term/{species}/{term}",
            params=self._params(limit=limit, offset=offset),
        )

    # -- Regulation -----------------------------------------------------------------------------------

    async def get_binding_matrix(
        self,
        species: str,
        stable_id: str,
        feature: str = "protein_coding",
        matrix_type: str = "all",
        limit: int = 100,
        offset: int = 1,
        min_: int | None = None,
        max_: int | None = None,
    ) -> Any:
        """Regulatory binding sites for a PFM:
        ``GET /species/:species/binding_matrix/:stable_id``.

        ``stable_id``: e.g. ``ENSPFM0001``; ``matrix_type``: all | motif |
        domain; ``min_``/``max_``: matrix-score bounds.
        """
        return await self._make_request(
            f"{self.base_url}/species/{species}/binding_matrix/{stable_id}",
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
        """Sequences by Ensembl ID: ``POST /sequence/id`` with body
        ``{"ids": [...]}``.

        ``type_``: dna | cdna | pep.
        """
        params = self._params(type=type_)
        if class_ is not None:
            params["class"] = class_
        return await self._make_request(
            f"{self.base_url}/sequence/id",
            params=params,
            json_data={"ids": list(ids)},
        )

    async def get_sequence_by_id(
        self,
        id_: str,
        type_: str = "dna",
        class_: str | None = None,
    ) -> Any:
        """Sequence of one object: ``GET /sequence/id/:id``.

        ``type_``: dna | cdna | pep.
        """
        params = self._params(type=type_)
        if class_ is not None:
            params["class"] = class_
        return await self._make_request(f"{self.base_url}/sequence/id/{id_}", params=params)

    async def get_sequence(
        self,
        species: str,
        region: str,
        type_: str = "dna",
        class_: str | None = None,
    ) -> Any:
        """Sequence of a region: ``GET /sequence/region/:species/:region``.

        ``region`` is a coordinate string like ``11:2159990-2160000``;
        ``type_``: dna | cdna | pep.
        """
        params = self._params(type=type_)
        if class_ is not None:
            params["class"] = class_
        return await self._make_request(
            f"{self.base_url}/sequence/region/{species}/{region}", params=params
        )

    # -- Transcript haplotypes ------------------------------------------------------------------------------

    async def get_transcript_haplotypes(
        self,
        species: str,
        transcript_id: str,
        assembly: str | None = None,
        population: str | None = None,
        type_: str | None = None,
        min_: float | None = None,
        max_: float | None = None,
    ) -> Any:
        """Haplotype coverage of a transcript:
        ``GET /transcript_haplotypes/:species/:id``.

        ``type_``: ref | alt; ``min_``/``max_``: frequency bounds.
        """
        return await self._make_request(
            f"{self.base_url}/transcript_haplotypes/{species}/{transcript_id}",
            params=self._params(
                assembly=assembly, population=population, type=type_, min=min_, max=max_
            ),
        )

    # -- VEP -----------------------------------------------------------------------------------------------------

    async def get_vep_id(self, species: str, id_: str, **params: Any) -> Any:
        """VEP consequences for one variant id: ``GET /vep/:species/id/:id``.

        Extra VEP options (``canonical``, ``hgvs``, ``numbers``, ``domains``,
        ``updown``, ``distance``, ...) pass through as query params, same as
        the batch POST wrappers below.
        """
        return await self._make_request(
            f"{self.base_url}/vep/{species}/id/{id_}", params=self._params(**params)
        )

    async def get_vep_hgvs(self, species: str, hgvs_notation: str, **params: Any) -> Any:
        """VEP consequences for one HGVS string:
        ``GET /vep/:species/hgvs/:hgvs_notation``."""
        return await self._make_request(
            f"{self.base_url}/vep/{species}/hgvs/{quote(hgvs_notation, safe='')}",
            params=self._params(**params),
        )

    async def get_vep_region(self, species: str, region: str, allele: str, **params: Any) -> Any:
        """VEP consequences for one region/allele pair:
        ``GET /vep/:species/region/:region/:allele``."""
        return await self._make_request(
            f"{self.base_url}/vep/{species}/region/{region}/{allele}",
            params=self._params(**params),
        )

    async def vep_hgvs(self, species: str, hgvs: list[str], **params: Any) -> Any:
        """VEP over HGVS variant strings: ``POST /vep/:species/hgvs`` with body
        ``{"hgvs_notations": [...]}``.

        Extra VEP options (``cache``, ``dir``, ``canonical``, ``extra``,
        ``population``, ``hgvs``, ``limit``, ``offset``) pass through as
        query params.
        """
        return await self._make_request(
            f"{self.base_url}/vep/{species}/hgvs",
            params=self._params(**params),
            json_data={"hgvs_notations": list(hgvs)},
        )

    async def vep_ids(self, species: str, ids: list[str], **params: Any) -> Any:
        """VEP over Ensembl variation IDs: ``POST /vep/:species/id`` with body
        ``{"ids": [...]}`` (extra VEP options as in :meth:`vep_hgvs`)."""
        return await self._make_request(
            f"{self.base_url}/vep/{species}/id",
            params=self._params(**params),
            json_data={"ids": list(ids)},
        )

    async def vep_regions(
        self,
        species: str,
        regions: list[str],
        **params: Any,
    ) -> Any:
        """VEP over genomic variants: ``POST /vep/:species/region`` with body
        ``{"variants": [...]}``.

        Each entry is a VEP default-format line, e.g. ``"11 2159779 2159779
        G/A 1"`` (chrom, start, end, ref/alt, strand). Extra VEP options as in
        :meth:`vep_hgvs`."""
        return await self._make_request(
            f"{self.base_url}/vep/{species}/region",
            params=self._params(**params),
            json_data={"variants": list(regions)},
        )

    # -- Variation ---------------------------------------------------------------------------------------------

    async def get_variation(self, species: str, id_: str, **params: Any) -> Any:
        """A single variation: ``GET /variation/:species/:id``.

        ``params``: ``pops`` | ``population_genotypes`` | ``genotypes``.
        """
        return await self._make_request(
            f"{self.base_url}/variation/{species}/{id_}",
            params=self._params(**params),
        )

    async def get_variations_by_ids(self, species: str, ids: list[str], **params: Any) -> Any:
        """Batch variations: ``POST /variation/:species`` with ``{"ids": [...]}``."""
        return await self._make_request(
            f"{self.base_url}/variation/{species}",
            params=self._params(**params),
            json_data={"ids": list(ids)},
        )

    async def get_variations_by_pmcid(
        self, species: str, pmcid: str, limit: int = 10, offset: int = 1
    ) -> Any:
        """Variations in a PMC article: ``GET /variation/:species/pmcid/:pmcid``."""
        return await self._make_request(
            f"{self.base_url}/variation/{species}/pmcid/{pmcid}",
            params=self._params(limit=limit, offset=offset),
        )

    async def get_variations_by_pmid(
        self, species: str, pmid: str, limit: int = 10, offset: int = 1
    ) -> Any:
        """Variations in a PubMed article: ``GET /variation/:species/pmid/:pmid``."""
        return await self._make_request(
            f"{self.base_url}/variation/{species}/pmid/{pmid}",
            params=self._params(limit=limit, offset=offset),
        )

    async def get_variant_recoder(self, species: str, id_: str, **params: Any) -> Any:
        """Recodes for one variant: ``GET /variant_recoder/:species/:id``."""
        return await self._make_request(
            f"{self.base_url}/variant_recoder/{species}/{id_}",
            params=self._params(**params),
        )

    async def variant_recoder(self, species: str, ids: list[str], **params: Any) -> Any:
        """Batch recoding: ``POST /variant_recoder/:species`` with ``{"ids": [...]}``."""
        return await self._make_request(
            f"{self.base_url}/variant_recoder/{species}",
            params=self._params(**params),
            json_data={"ids": list(ids)},
        )

    # -- GA4GH --------------------------------------------------------------------------------------------------------

    async def _ga4gh(self, resource: str, resource_id: str, **params: Any) -> Any:
        """``GET /ga4gh/<resource>/:id`` — in 15.12 single GA4GH resources are
        only addressable by id; collection listing happens through the POST
        ``<resource>/search`` helpers below (there are no list GETs, no
        referencesets and no searches resource anymore)."""
        return await self._make_request(
            f"{self.base_url}/ga4gh/{resource}/{resource_id}",
            params=self._params(**params),
        )

    async def _ga4gh_search(self, resource: str, body: dict[str, Any]) -> Any:
        """``POST /ga4gh/<resource>/search`` with a GA4GH SearchRequest body.

        An empty body is normalised to ``{"pageSize": 1}`` — every search
        needs a page size in practice, and the base client only issues a POST
        for a truthy JSON body.
        """
        return await self._make_request(
            f"{self.base_url}/ga4gh/{resource}/search",
            params=self._params(),
            json_data=body or {"pageSize": 1},
        )

    async def ga4gh_beacon(self, **params: Any) -> Any:
        """Beacon service info: ``GET /ga4gh/beacon``."""
        return await self._make_request(
            f"{self.base_url}/ga4gh/beacon", params=self._params(**params)
        )

    async def ga4gh_beacon_query(
        self,
        reference_name: str,
        start: int,
        reference_bases: str,
        alternate_bases: str,
        assembly_id: str = "GRCh38",
        **params: Any,
    ) -> Any:
        """Beacon v2 query (GET form): ``GET /ga4gh/beacon/query``.

        ``start`` is 0-based. Do not pass ``datasetIds``: the server rejects
        every dataset id it advertises ("Invalid datasetId"), while omitting
        it queries the default dataset. The legacy ``chrom`` / ``allele`` /
        ``assembly`` params are not understood: the server answers HTTP 200
        with an embedded ``error`` object instead of failing.
        """
        return await self._make_request(
            f"{self.base_url}/ga4gh/beacon/query",
            params=self._params(
                referenceName=reference_name,
                start=start,
                referenceBases=reference_bases,
                alternateBases=alternate_bases,
                assemblyId=assembly_id,
                **params,
            ),
        )

    async def ga4gh_beacon_query_post(self, request: dict[str, Any]) -> Any:
        """Beacon query (GA4GH body): ``POST /ga4gh/beacon/query``.

        ``request`` keys (Beacon v2, as in :meth:`ga4gh_beacon_query`):
        ``referenceName`` | ``start`` | ``referenceBases`` | ``alternateBases`` |
        ``assemblyId``. Omit ``datasetIds`` (a list is stringified
        server-side to ``ARRAY(0x...)`` and rejected).
        """
        return await self._make_request(
            f"{self.base_url}/ga4gh/beacon/query",
            params=self._params(),
            json_data=request,
        )

    async def ga4gh_callsets(self, callset_id: str, **params: Any) -> Any:
        """A single callset: ``GET /ga4gh/callsets/:id``.

        15.12 has no callset search endpoint — ids come from the ``calls``
        arrays embedded in variant responses.
        """
        return await self._ga4gh("callsets", callset_id, **params)

    async def ga4gh_get_dataset(self, dataset_id: str, **params: Any) -> Any:
        """A single dataset: ``GET /ga4gh/datasets/:id``."""
        return await self._ga4gh("datasets", dataset_id, **params)

    async def ga4gh_search_datasets(self, **body: Any) -> Any:
        """``POST /ga4gh/datasets/search`` (body keys: ``pageSize``)."""
        return await self._ga4gh_search("datasets", dict(body))

    async def ga4gh_get_feature(self, feature_id: str, **params: Any) -> Any:
        """A single feature: ``GET /ga4gh/features/:id``."""
        return await self._ga4gh("features", feature_id, **params)

    async def ga4gh_search_features(self, **body: Any) -> Any:
        """``POST /ga4gh/features/search``.

        Body needs ``featureSetId`` (singular, e.g. ``"Ensembl.116.GRCh38"``)
        plus ``referenceName`` / ``start`` / ``end``. Slow: ~50 s for a 1.4 kb
        window."""
        return await self._ga4gh_search("features", dict(body))

    async def ga4gh_get_featureset(self, featureset_id: str, **params: Any) -> Any:
        """A single feature set: ``GET /ga4gh/featuresets/:id``."""
        return await self._ga4gh("featuresets", featureset_id, **params)

    async def ga4gh_search_featuresets(self, **body: Any) -> Any:
        """``POST /ga4gh/featuresets/search``.

        ``datasetId`` must be the literal ``"Ensembl"``; the 1000 Genomes id
        returned by :meth:`ga4gh_search_datasets` gives a 400."""
        return await self._ga4gh_search("featuresets", dict(body))

    async def ga4gh_get_reference(self, reference_id: str, **params: Any) -> Any:
        """A single reference: ``GET /ga4gh/references/:id``."""
        return await self._ga4gh("references", reference_id, **params)

    async def ga4gh_search_references(self, **body: Any) -> Any:
        """``POST /ga4gh/references/search`` (body needs ``referenceSetId``,
        e.g. ``"GRCh38"``)."""
        return await self._ga4gh_search("references", dict(body))

    async def ga4gh_search_variant_annotations(self, **body: Any) -> Any:
        """``POST /ga4gh/variantannotations/search``.

        Body needs ``variantAnnotationSetId`` (e.g. ``"Ensembl"``) plus
        ``referenceName`` / ``start`` / ``end``. Unlike the other collections
        this one has no single-item GET.
        """
        return await self._ga4gh_search("variantannotations", dict(body))

    async def ga4gh_get_variant(self, variant_id: str, **params: Any) -> Any:
        """A single variant: ``GET /ga4gh/variants/:id``."""
        return await self._ga4gh("variants", variant_id, **params)

    async def ga4gh_search_variants(self, **body: Any) -> Any:
        """``POST /ga4gh/variants/search``.

        Body needs ``variantSetId`` plus ``referenceName`` / ``start`` /
        ``end``."""
        return await self._ga4gh_search("variants", dict(body))

    async def ga4gh_get_variantset(self, variantset_id: str, **params: Any) -> Any:
        """A single variant set: ``GET /ga4gh/variantsets/:id``."""
        return await self._ga4gh("variantsets", variantset_id, **params)

    async def ga4gh_search_variantsets(self, **body: Any) -> Any:
        """``POST /ga4gh/variantsets/search`` (body needs ``datasetId``)."""
        return await self._ga4gh_search("variantsets", dict(body))

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
