"""
GTEx Portal adapter (tissue gene expression and eQTLs).

The Genotype-Tissue Expression project measured RNA-seq in 54 post-mortem tissues of
~950 donors and mapped expression quantitative trait loci (eQTLs). This adapter answers
"where is gene X expressed, how tissue-specific is it, and which common variants regulate
it" from the keyless GTEx Portal API v2 (``https://gtexportal.org/api/v2``), verified live
2026-10:

* ``/metadata/dataset`` lists releases. The default here is **gtex_v10** (GENCODE v39,
  GRCh38, 50 eQTL tissues); ``GTEX_DATASET_ID=gtex_v8`` (GENCODE v26) selects the older one.
* GTEx addresses genes by **version-qualified GENCODE id** (``ENSG00000012048.23`` in v10,
  ``.20`` in v8); an id with the wrong version silently returns *no data* instead of an error.
  Ids and symbols are therefore always resolved through
  ``/reference/geneSearch?gencodeVersion=...`` first, which accepts an HGNC symbol (prefix
  match: ``BRCA`` also finds BRCA1, BRCA2, BRCA1P1) or an Ensembl id with or without version.
  It does **not** accept Entrez ids, HGNC ids or free text; those resolve to nothing.
* ``/expression/medianGeneExpression`` returns the median TPM per tissue (54 rows, ~10 KB).
* ``/association/singleTissueEqtl`` returns eQTL rows (``snpId``, ``variantId``, ``pValue``,
  ``nes`` = normalised effect size / slope, ``tissueSiteDetailId``). Rows come **ordered by
  tissue, not by significance**, in pages of up to 250; BRCA1 has 1742 rows (7 pages, ~1 s
  each) and strongly regulated genes have far more. The adapter therefore scans at most
  ``eqtl_max_pages`` pages, ranks the scanned rows by p-value and flags the result as
  ``truncated`` when it did not see everything.

Latency: details = 2 requests (0.3 - 1 s each), relationships = 3 - 10 requests (gene
resolution, medians, up to ``eqtl_max_pages`` eQTL pages). Requests are spaced 0.3 s apart.

Contrast with the Human Protein Atlas adapter: HPA reports consensus RNA nTPM across tissues
and immune cell types with curated specificity categories and protein-level data; GTEx has
per-donor, one-assay (bulk RNA-seq) medians and, uniquely, genetic regulation (eQTLs).

Data are open access (GTEx Portal data use policy: cite the GTEx Consortium and the release,
no redistribution of controlled-access individual-level data, which the API does not serve).
"""

import asyncio
import logging
import math
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

GTEX_BASE_URL = "https://gtexportal.org/api/v2"
DEFAULT_DATASET = "gtex_v10"
# dataset -> GENCODE version used for its gene ids
_DATASET_GENCODE = {"gtex_v8": "v26", "gtex_v10": "v39"}
_GENOME_BUILD = "GRCh38/hg38"

_ENSG_RE = re.compile(r"^(ENSG\d{11})(?:\.\d+)?$", re.IGNORECASE)
_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._@-]{0,30}$")
_PREFIX_RE = re.compile(r"^(?:gtex|ensembl|ensg|hgnc\s+symbol)\s*:\s*", re.IGNORECASE)
_HGNC_DESC_RE = re.compile(r"Acc:(HGNC:\d+)")

_MIN_INTERVAL = 0.3  # seconds between requests: GTEx publishes no limit, stay polite
_MAX_SEARCH = 50
_TOP_TISSUES_SUMMARY = 10
_EXPRESSED_TPM = 1.0  # a tissue counts as "expressed" at median TPM >= 1
_EQTL_PAGE_SIZE = 250


def _tau(values: list[float]) -> float | None:
    """Tissue specificity index tau (Yanai 2005): 0 = housekeeping, 1 = one tissue only.

    Computed on log2(1 + TPM): on raw TPM a single dominant tissue (lymphoblastoid cell
    line, testis) pushes almost every gene towards 1 (BRCA1: 0.92 raw, 0.70 on log2).
    """
    if len(values) < 2:
        return None
    logs = [math.log2(1 + max(v, 0.0)) for v in values]
    top = max(logs)
    if top <= 0:
        return None
    return sum(1 - v / top for v in logs) / (len(logs) - 1)


def _specificity_label(tau: float | None) -> str | None:
    if tau is None:
        return None
    if tau >= 0.8:
        return "tissue-specific"
    if tau >= 0.5:
        return "intermediate"
    return "broadly expressed"


class GTExAdapter(KnowledgeSourceAdapter):
    """Adapter for the GTEx Portal API v2 (gene expression by tissue, eQTLs)."""

    min_request_timeout = 60.0
    #: eQTL pages (250 rows each) scanned per gene; see the module docstring.
    eqtl_max_pages = 8

    def __init__(self, config):
        super().__init__(config)
        self.base_url = GTEX_BASE_URL
        requested = os.getenv("GTEX_DATASET_ID", DEFAULT_DATASET).strip()
        self.dataset_id = requested if requested in _DATASET_GENCODE else DEFAULT_DATASET
        if requested != self.dataset_id:
            logger.warning(f"Unknown GTEX_DATASET_ID '{requested}', using {DEFAULT_DATASET}")
        self.gencode_version = _DATASET_GENCODE[self.dataset_id]
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.GTEX

    def is_available(self) -> bool:
        return True  # public API, no key

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET ``/api/v2/<endpoint>``, spacing requests politely."""
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(f"{self.base_url}/{endpoint}", params)
        return data if isinstance(data, dict) else {}

    async def _gene_search(self, gene_id: str, limit: int = 250) -> list[dict[str, Any]]:
        data = await self._get(
            "reference/geneSearch",
            {
                "geneId": gene_id,
                "gencodeVersion": self.gencode_version,
                "genomeBuild": _GENOME_BUILD,
                "itemsPerPage": limit,
            },
        )
        return [g for g in data.get("data") or [] if isinstance(g, dict) and g.get("gencodeId")]

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_gene_id(concept_id: str) -> tuple[str, str] | None:
        """``("ensembl", "ENSG00000012048")`` or ``("symbol", "BRCA1")``; ``None`` otherwise.

        Accepts Ensembl ids with or without version, ``GTEx:`` / ``ENSEMBL:`` prefixes and
        gene symbols. Entrez ids and HGNC ids are not searchable in GTEx and give ``None``.
        """
        text = _PREFIX_RE.sub("", (concept_id or "").strip())
        match = _ENSG_RE.match(text)
        if match:
            return "ensembl", match.group(1).upper()
        if text.upper().startswith(("HGNC:", "NCBIGENE:", "GENEID:")):
            return None
        if _SYMBOL_RE.match(text):
            return "symbol", text
        return None

    async def _resolve_gene(self, concept_id: str) -> dict[str, Any] | None:
        """The GTEx gene record (symbol, versioned gencodeId, entrez id ...) for an id/symbol."""
        parsed = self._parse_gene_id(concept_id)
        if parsed is None:
            return None
        kind, value = parsed
        genes = await self._gene_search(value)
        for gene in genes:
            if kind == "ensembl" and str(gene["gencodeId"]).split(".")[0].upper() == value:
                return gene
            if kind == "symbol" and str(gene.get("geneSymbol", "")).casefold() == value.casefold():
                return gene
        return None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Genes whose symbol starts with ``query`` (or the gene with that Ensembl id).

        GTEx's gene search is not free text: ``BRCA`` matches ``BRCA1``, ``BRCA2`` ...;
        diseases and descriptions are not searched. An exact symbol is ranked first.
        Results carry no expression data (use :meth:`get_concept_details`).
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            parsed = self._parse_gene_id(text)
            if parsed is None:
                return []
            genes = await self._gene_search(parsed[1], min(limit, _MAX_SEARCH))
            exact = parsed[1].casefold()
            genes.sort(
                key=lambda g: (
                    str(g.get("geneSymbol", "")).casefold() != exact,
                    g.get("geneType") != "protein coding",
                    str(g.get("geneSymbol", "")),
                )
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank, gene in enumerate(genes):
                concept = self._gene_to_concept(gene)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concept.confidence_score = (
                    0.95
                    if str(gene.get("geneSymbol", "")).casefold() == exact
                    else max(0.5, 0.8 - 0.02 * rank)
                )
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"GTEx search for '{text}' returned {len(concepts)} genes")
            return concepts
        except Exception as e:
            logger.error(f"GTEx search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Gene record plus a compact median-TPM summary in ``source_data``.

        ``source_data[GTEX]`` keys: ``dataset``, ``gencode_id``, ``gencode_version``,
        ``top_tissues_tpm`` (top 10 ``{tissue, tpm}``), ``n_tissues`` (tissues measured),
        ``n_tissues_expressed`` (median TPM >= 1), ``max_tpm``, ``tau`` (log2(1+TPM) based; 0 housekeeping ...
        1 single tissue) and ``tissue_specificity`` (``tissue-specific`` >= 0.8,
        ``intermediate`` >= 0.5, else ``broadly expressed``; a heuristic, not a GTEx label).
        """
        try:
            gene = await self._resolve_gene(concept_id)
            if gene is None:
                return None
            concept = self._gene_to_concept(gene)
            if concept is None:
                return None
            medians = await self._median_expression(gene["gencodeId"])
            if medians and isinstance(concept.source_data, dict):
                concept.source_data[self.get_source()].update(self._summarise(medians))
            concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"GTEx get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _median_expression(self, gencode_id: str) -> list[dict[str, Any]]:
        data = await self._get(
            "expression/medianGeneExpression",
            {"gencodeId": gencode_id, "datasetId": self.dataset_id, "itemsPerPage": 100},
        )
        rows = [
            r
            for r in data.get("data") or []
            if isinstance(r, dict)
            and r.get("tissueSiteDetailId")
            and isinstance(r.get("median"), int | float)
        ]
        return sorted(rows, key=lambda r: r["median"], reverse=True)

    @staticmethod
    def _summarise(medians: list[dict[str, Any]]) -> dict[str, Any]:
        values = [float(r["median"]) for r in medians]
        tau = _tau(values)
        return {
            "top_tissues_tpm": [
                {"tissue": r["tissueSiteDetailId"], "tpm": round(float(r["median"]), 3)}
                for r in medians[:_TOP_TISSUES_SUMMARY]
            ],
            "n_tissues": len(values),
            "n_tissues_expressed": sum(v >= _EXPRESSED_TPM for v in values),
            "max_tpm": round(max(values), 3),
            "tau": None if tau is None else round(tau, 3),
            "tissue_specificity": _specificity_label(tau),
        }

    # ------------------------------------------------------------------
    # Mappings / relationships
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Ensembl (versionless and as served), NCBI Gene and HGNC ids of the gene."""
        try:
            gene = await self._resolve_gene(concept_id)
        except Exception as e:
            logger.error(f"GTEx get_mappings failed for '{concept_id}': {e}")
            return []
        if gene is None:
            return []
        gencode_id = str(gene["gencodeId"])
        from_id = gencode_id.split(".")[0]
        targets: list[tuple[str, str]] = []
        if gene.get("entrezGeneId"):
            targets.append(("NCBIGene", str(gene["entrezGeneId"])))
        hgnc = _HGNC_DESC_RE.search(str(gene.get("description") or ""))
        if hgnc:
            targets.append(("HGNC", hgnc.group(1).removeprefix("HGNC:")))
        targets.append(("ENSEMBL", gencode_id))  # version-qualified id as GTEx serves it
        if gene.get("geneSymbol"):
            targets.append(("HGNC.SYMBOL", str(gene["geneSymbol"])))
        return [
            {
                "fromId": from_id,
                "toId": f"{prefix}:{local}",
                "fromSource": "ENSEMBL",
                "toSource": prefix,
                "mappingType": "exact" if prefix != "ENSEMBL" else "version",
                "confidence": 0.95,
            }
            for prefix, local in targets
        ]

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Gene -> tissues and gene -> eQTL variants; ``limit`` applies to each type.

        * ``expressed_in``: the ``limit`` tissues with the highest median TPM (>= 1 TPM
          only). ``related_id`` is the UBERON id GTEx supplies, ``related_name`` the GTEx
          tissue id (``Brain_Cortex``); extras ``median_tpm``, ``unit``, ``rank``,
          ``dataset``.
        * ``has_eqtl_variant``: the ``limit`` most significant gene-variant-tissue eQTLs
          among the scanned rows. ``related_id`` is the rsID (GTEx ``variantId`` when none),
          ``related_name`` the variant id (``chr17_43002200_A_G_b38``); extras ``tissue``,
          ``tissue_ontology_id``, ``p_value``, ``slope`` (normalised effect size),
          ``chromosome``, ``position``, ``rows_scanned``, ``rows_total``, ``truncated``.
        """
        if limit <= 0:
            return []
        try:
            gene = await self._resolve_gene(concept_id)
        except Exception as e:
            logger.error(f"GTEx get_relationships failed for '{concept_id}': {e}")
            return []
        if gene is None:
            return []
        gencode_id = gene["gencodeId"]
        relationships: list[dict[str, Any]] = []
        try:
            medians = await self._median_expression(gencode_id)
        except Exception as e:
            logger.warning(f"GTEx expression request failed for {gencode_id}: {e}")
            medians = []
        expressed = [r for r in medians if float(r["median"]) >= _EXPRESSED_TPM]
        for rank, row in enumerate(expressed[:limit], start=1):
            relationships.append(
                {
                    "relation_label": "expressed_in",
                    "related_id": row.get("ontologyId") or row["tissueSiteDetailId"],
                    "related_name": row["tissueSiteDetailId"],
                    "source": "GTEX",
                    "median_tpm": round(float(row["median"]), 3),
                    "unit": row.get("unit") or "TPM",
                    "rank": rank,
                    "dataset": self.dataset_id,
                }
            )
        try:
            relationships.extend(await self._eqtl_relationships(gencode_id, limit))
        except Exception as e:
            logger.warning(f"GTEx eQTL request failed for {gencode_id}: {e}")
        return relationships

    async def _eqtl_relationships(self, gencode_id: str, limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        total = 0
        pages = 0
        for page in range(max(1, self.eqtl_max_pages)):
            data = await self._get(
                "association/singleTissueEqtl",
                {
                    "gencodeId": gencode_id,
                    "datasetId": self.dataset_id,
                    "itemsPerPage": _EQTL_PAGE_SIZE,
                    "page": page,
                },
            )
            rows.extend(
                r
                for r in data.get("data") or []
                if isinstance(r, dict) and isinstance(r.get("pValue"), int | float)
            )
            paging = data.get("paging_info") or {}
            total = int(paging.get("totalNumberOfItems") or len(rows))
            pages = int(paging.get("numberOfPages") or 1)
            if page + 1 >= pages:
                break
        truncated = len(rows) < total
        ranked = sorted(
            rows,
            key=lambda r: (r["pValue"], str(r.get("variantId")), str(r.get("tissueSiteDetailId"))),
        )
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in ranked:
            variant = str(row.get("variantId") or "")
            related_id = str(row.get("snpId") or variant)
            tissue = str(row.get("tissueSiteDetailId") or "")
            if not related_id or (related_id, tissue) in seen:
                continue
            seen.add((related_id, tissue))
            slope = row.get("nes")
            out.append(
                {
                    "relation_label": "has_eqtl_variant",
                    "related_id": related_id,
                    "related_name": variant,
                    "source": "GTEX",
                    "tissue": tissue,
                    "tissue_ontology_id": row.get("ontologyId"),
                    "p_value": row["pValue"],
                    "slope": slope if isinstance(slope, int | float) else None,
                    "chromosome": row.get("chromosome"),
                    "position": row.get("pos"),
                    "dataset": self.dataset_id,
                    "rows_scanned": len(rows),
                    "rows_total": total,
                    "truncated": truncated,
                }
            )
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _gene_to_concept(self, gene: dict[str, Any]) -> UnifiedConcept | None:
        gencode_id, symbol = gene.get("gencodeId"), gene.get("geneSymbol")
        if not gencode_id or not symbol:
            return None
        base_id = str(gencode_id).split(".")[0]
        concept = self._create_concept(base_id, str(symbol), ConceptType.GENE)
        concept.add_identifier(
            self.get_source(),
            str(gencode_id),
            str(symbol),
            f"https://gtexportal.org/home/gene/{gencode_id}",
        )
        if gene.get("entrezGeneId"):
            concept.add_identifier(
                KnowledgeSource.NCBI, f"NCBIGene:{gene['entrezGeneId']}", str(symbol)
            )
        description = str(gene.get("description") or "").strip()
        # "BRCA1 DNA repair associated [Source:HGNC Symbol;Acc:HGNC:1100]" -> plain name
        name = re.sub(r"\s*\[Source:[^\]]*\]\s*$", "", description)
        if name and concept.definitions is not None:
            concept.definitions.append(name)
        if gene.get("geneType") and concept.categories is not None:
            concept.categories.append(str(gene["geneType"]))
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "dataset": self.dataset_id,
                "gencode_id": gencode_id,
                "gencode_version": gene.get("gencodeVersion") or self.gencode_version,
                "gene_type": gene.get("geneType"),
                "chromosome": gene.get("chromosome"),
                "start": gene.get("start"),
                "end": gene.get("end"),
                "strand": gene.get("strand"),
                "genome_build": gene.get("genomeBuild"),
                "entrez_gene_id": gene.get("entrezGeneId"),
            }
        return concept
