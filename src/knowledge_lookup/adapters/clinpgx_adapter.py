"""
ClinPGx (PharmGKB) Knowledge Source Adapter

Adapter for the ClinPGx REST API (https://api.clinpgx.org/v1/data/, keyless), the successor
of the PharmGKB API: pharmacogenomic genes, drugs, variants and star-allele haplotypes with
their clinical annotations, CPIC/DPWG dosing guidelines and drug labels.

LICENCE AND CITATION (read before redistributing results): ClinPGx data is licensed
CC BY-SA 4.0. You must give appropriate credit to ClinPGx/PharmGKB, link the licence and
indicate changes; derived data you distribute must carry the same licence; the data may not
be sold. The data usage policy is https://www.clinpgx.org/page/dataUsagePolicy and the
licence summary https://blog.clinpgx.org/changes-to-pharmgkb-data-licensing/. Cite e.g.
Whirl-Carrillo M et al., Clin Pharmacol Ther 2012;92(4):414-417 (PharmGKB) and
https://www.clinpgx.org/. Every concept carries a ``license`` note in its ``source_data``.

What the API serves (live-verified, October 2026):

- Rate limit: 2 requests per second (``429`` when exceeded); requests are spaced at ~1.8/s
  here. The API is declared "not final" (parameters may change). ``api.pharmgkb.org`` no
  longer resolves, use ``api.clinpgx.org``. Cloudflare rejects python-urllib's default
  User-Agent (error 1010); the base class's own User-Agent is fine.
- ``data/gene?symbol=CYP2D6``, ``data/chemical?name=codeine``, ``data/variant?symbol=rs3892097``,
  ``data/haplotype?symbol=CYP2D6*4`` are EXACT and CASE-SENSITIVE lookups (``cyp2d6`` and
  ``CODEINE`` give 404; chemical names are lower case; trade names/synonyms such as
  "paracetamol" do not match, "acetaminophen" does). There is no free-text or prefix search.
- Unknown names answer ``404``; ids are ``PA`` numbers (gene ``PA128`` = CYP2D6, chemical
  ``PA449088`` = codeine, variant ``PA166156104`` = rs3892097, haplotype ``PA165816579`` =
  CYP2D6*4) and are fetched with ``data/<type>/<id>``; the type of an id is not encoded, so a
  bare id is probed against gene, chemical, variant and haplotype (the type is remembered).
- Responses are ``{"status": "success", "data": [...]}`` (``data`` is an object for fetches by
  id). ``view=max`` adds cross-references; ``view=min`` returns a few fields only. There is no
  paging: filtered collections come back whole (all CYP2D6 clinical annotations: 122 items,
  223 KB with ``view=min``, 1.3 MB without; all CYP2D6 guidelines: 71 items, 0.9 MB). The
  guideline call for a gene is therefore the expensive one (about 3 s).

Identifiers: PA ids (``PA128``); ``CLINPGX:PA128`` and ``PHARMGKB:PA128`` are accepted too.
"""

import asyncio
import html
import logging
import re
import time
from typing import Any, cast

from ..base import KnowledgeSourceAdapter, _is_not_found
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

CLINPGX_BASE_URL = "https://api.clinpgx.org/v1/data"
CLINPGX_SOURCE_NAME = "ClinPGx"
CLINPGX_LICENSE = "CC BY-SA 4.0: credit ClinPGx/PharmGKB, link licence, indicate changes"

# Documented limit is 2 requests/s; stay just under it.
_MIN_INTERVAL = 0.55

_PA_ID_RE = re.compile(r"^PA\d+$", re.IGNORECASE)
_PREFIX_RE = re.compile(r"^(CLINPGX|PHARMGKB|PGKB)\s*:\s*", re.IGNORECASE)
_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

# Evidence level order (best first) for the clinical annotation summary per drug.
_EVIDENCE_ORDER = ["1A", "1B", "2A", "2B", "3", "4"]
_SUMMARY_CHARS = 600

# objCls -> (API path segment, concept type)
_KINDS: dict[str, tuple[str, ConceptType]] = {
    "gene": ("gene", ConceptType.GENE),
    "chemical": ("chemical", ConceptType.DRUG),
    "variant": ("variant", ConceptType.MOLECULAR_ENTITY),
    "haplotype": ("haplotype", ConceptType.MOLECULAR_ENTITY),
}

# ClinPGx ``resource`` name -> (toSource, mapping type). Resources not listed (GenBank,
# ClinicalTrials.gov, ClinPGx tags, URLs ...) are not identifiers of the same entity.
_RESOURCE_MAP: dict[str, tuple[str, str]] = {
    "HGNC": ("HGNC", "exact"),
    "Ensembl": ("ENSEMBL", "exact"),
    "NCBI Gene": ("NCBI", "exact"),
    "UniProtKB": ("UNIPROT", "exact"),
    "OMIM": ("OMIM", "exact"),
    "Comparative Toxicogenomics Database": ("CTD", "exact"),
    "GeneCard": ("GeneCards", "xref"),
    "PharmVar Gene": ("PharmVar", "xref"),
    "DrugBank": ("DRUGBANK", "exact"),
    "PubChem Compound": ("PUBCHEM", "exact"),
    "ChEBI": ("CHEBI", "exact"),
    "MeSH": ("MESH", "exact"),
    "RxNorm": ("RXNORM", "exact"),
    "UMLS": ("UMLS", "exact"),
    "KEGG Compound": ("KEGG", "exact"),
    "ChemSpider": ("ChemSpider", "xref"),
    "IUPHAR Ligand": ("GuideToPharmacology", "xref"),
    "NDF-RT": ("NDF-RT", "xref"),
    "ATC": ("ATC", "atc_code"),
    "dbSNP": ("DBSNP", "exact"),
    "ClinVar": ("CLINVAR", "exact"),
}
# Sources that exist in ``KnowledgeSource`` also become concept identifiers.
_IDENTIFIER_SOURCES = {
    "HGNC",
    "ENSEMBL",
    "NCBI",
    "UNIPROT",
    "OMIM",
    "CTD",
    "DRUGBANK",
    "PUBCHEM",
    "CHEBI",
    "MESH",
    "RXNORM",
    "UMLS",
    "KEGG",
    "DBSNP",
    "CLINVAR",
}


def _evidence_rank(level: str) -> int:
    return _EVIDENCE_ORDER.index(level) if level in _EVIDENCE_ORDER else len(_EVIDENCE_ORDER)


class ClinPGxAdapter(KnowledgeSourceAdapter):
    """Adapter for ClinPGx / PharmGKB (CC BY-SA 4.0, cite ClinPGx; 2 requests/s)."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = CLINPGX_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._kinds: dict[str, str] = {}  # PA id -> kind, learned from searches / probes

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CLINPGX

    def is_available(self) -> bool:
        return True  # keyless public service

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_id(concept_id: str) -> str | None:
        """``CLINPGX:PA128`` / ``pa128`` -> ``"PA128"``; anything else ``None``."""
        if not isinstance(concept_id, str):
            return None
        bare = _PREFIX_RE.sub("", concept_id.strip()).strip().upper()
        return bare if _PA_ID_RE.match(bare) else None

    @staticmethod
    def _probe_order(pa_id: str) -> list[str]:
        """Most likely object kind first (ids are not typed; this only saves requests)."""
        digits = int(pa_id[2:])
        if digits < 400000:
            return ["gene", "chemical", "variant", "haplotype"]
        if digits < 1_000_000:
            return ["chemical", "gene", "variant", "haplotype"]
        return ["variant", "haplotype", "chemical", "gene"]

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Exact, case-insensitive-by-retry lookup of genes, drugs, variants and haplotypes.

        The API has no free-text search, so the query is tried as an rs number (variant), a
        star allele (``CYP2D6*4`` haplotype) or otherwise as gene symbol and as chemical
        name (upper/lower case variants are tried when the text as typed misses). A PA id
        returns that object. Up to four requests per query.
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            pa_id = self.normalize_id(query)
            if pa_id:
                concept = await self.get_concept_details(pa_id)
                return [concept] if concept else []

            concepts: list[UnifiedConcept] = []
            if _RSID_RE.match(query):
                concepts += await self._search_kind("variant", "symbol", [query.lower()])
            elif "*" in query:
                concepts += await self._search_kind("haplotype", "symbol", [query.upper()])
            else:
                concepts += await self._search_kind("gene", "symbol", [query.upper(), query])
                if not concepts:  # a symbol is never also a drug name in practice
                    concepts += await self._search_kind("chemical", "name", [query.lower(), query])
            logger.info(f"ClinPGx search for '{query}' returned {len(concepts[:limit])} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"ClinPGx search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full record (``view=max``, with cross-references) of a PA id."""
        pa_id = self.normalize_id(concept_id)
        if not pa_id:
            logger.warning(f"ClinPGx: '{concept_id}' is not a PA identifier")
            return None
        try:
            found = await self._fetch(pa_id)
            return self._concept(found[0], found[1]) if found else None
        except Exception as e:
            logger.error(f"ClinPGx get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Typed relationships (``limit`` caps each relation label).

        - gene: ``has_clinical_annotation`` -> drugs (best ``level_of_evidence``,
          ``phenotype_categories`` such as Dosage / Toxicity / Efficacy / Metabolism/PK,
          ``annotation_count``), ``has_guideline`` -> drugs with a CPIC / DPWG / CPNDS /
          RNPGx guideline (``guideline_source``, ``guideline_name``, ``guideline_id``) and
          ``has_haplotype`` -> star alleles. Three requests, the guideline one ~1 MB.
        - drug: ``has_clinical_annotation`` and ``has_guideline`` -> genes (same extra
          keys) and ``has_label`` -> annotated drug labels (``label_source``,
          ``testing_level`` e.g. "Actionable PGx", ``prescribing_genes``).
        - haplotype: ``haplotype_of`` -> gene; variant: ``located_in_gene`` -> gene.
        """
        pa_id = self.normalize_id(concept_id)
        if not pa_id or limit <= 0:
            return []
        try:
            found = await self._fetch(pa_id, view="min")
            if not found:
                return []
            kind, obj = found
            if kind == "gene":
                symbol = obj.get("symbol", "")
                rels = await self._annotation_edges("location.genes.symbol", symbol, "chemicals")
                rels += await self._guideline_edges("relatedGenes.symbol", symbol, "chemicals")
                rels += await self._haplotype_edges(symbol)
            elif kind == "chemical":
                name = obj.get("name", "")
                rels = await self._annotation_edges("relatedChemicals.name", name, "genes")
                rels += await self._guideline_edges("relatedChemicals.name", name, "genes")
                rels += await self._label_edges(name)
            elif kind == "haplotype":
                rels = [self._gene_edge("haplotype_of", obj.get("gene"))]
            else:
                full = await self._fetch(pa_id)
                genes = (full[1] if full else {}).get("relatedGenes") or []
                rels = [self._gene_edge("located_in_gene", g) for g in genes]
            return self._cap_per_label([r for r in rels if r.get("related_id")], limit)
        except Exception as e:
            logger.warning(f"ClinPGx get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """External references of the object (``crossReferences`` and chemical ``linkOuts``).

        Genes: HGNC, Ensembl, NCBI Gene, UniProt, OMIM, CTD, GeneCards, PharmVar. Drugs:
        DrugBank, PubChem, ChEBI, MeSH, RxNorm, UMLS, KEGG, ChemSpider and ATC codes.
        Variants: dbSNP, ClinVar.
        """
        pa_id = self.normalize_id(concept_id)
        if not pa_id:
            return []
        try:
            found = await self._fetch(pa_id)
            if not found:
                return []
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for ref in (found[1].get("crossReferences") or []) + (found[1].get("linkOuts") or []):
                spec = _RESOURCE_MAP.get(ref.get("resource", ""))
                value = ref.get("resourceId")
                if not spec or not value or (spec[0], str(value)) in seen:
                    continue
                seen.add((spec[0], str(value)))
                mappings.append(
                    {
                        "fromId": pa_id,
                        "toId": str(value),
                        "fromSource": CLINPGX_SOURCE_NAME,
                        "toSource": spec[0],
                        "mappingType": spec[1],
                        "confidence": 1.0,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"ClinPGx get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Throttled GET; returns the ``data`` rows (``[]`` for 404 "no results")."""
        async with self._throttle_lock:
            wait = self._last_request + _MIN_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        try:
            resp = await self._make_request(
                f"{CLINPGX_BASE_URL}/{path}", params, headers={"Accept": "application/json"}
            )
        except Exception as e:
            if _is_not_found(e):
                return []
            raise
        if not isinstance(resp, dict) or resp.get("status") == "fail":
            return []  # error bodies ({"status": "fail", "data": {"errors": [...]}})
        data = resp.get("data")
        if isinstance(data, dict):
            return [data]
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    async def _search_kind(
        self, kind: str, field: str, variants: list[str]
    ) -> list[UnifiedConcept]:
        """First of the spelling ``variants`` that matches (exact, case-sensitive API)."""
        seen: set[str] = set()
        for text in variants:
            if text in seen:
                continue
            seen.add(text)
            rows = await self._get(_KINDS[kind][0], {field: text})
            if rows:
                for row in rows:
                    self._kinds[str(row.get("id", ""))] = kind
                return [self._concept(kind, row) for row in rows if row.get("id")]
        return []

    async def _fetch(self, pa_id: str, view: str = "max") -> tuple[str, dict[str, Any]] | None:
        """Fetch an object by PA id, probing the object kinds when it is not yet known."""
        known = self._kinds.get(pa_id)
        order = [known] if known else self._probe_order(pa_id)
        for kind in order:
            rows = await self._get(f"{_KINDS[kind][0]}/{pa_id}", {"view": view})
            if rows:
                self._kinds[pa_id] = kind
                return kind, rows[0]
        self._kinds.pop(pa_id, None)
        return None

    async def _annotation_edges(self, field: str, value: str, side: str) -> list[dict[str, Any]]:
        """Clinical annotations aggregated per counterpart (drug or gene)."""
        if not value:
            return []
        rows = await self._get("clinicalAnnotation", {field: value, "view": "min"})
        agg: dict[str, dict[str, Any]] = {}
        for row in rows:
            level = (row.get("levelOfEvidence") or {}).get("term", "")
            for other in self._counterparts(row, side):
                edge = agg.setdefault(
                    other["id"],
                    {
                        "relation_label": "has_clinical_annotation",
                        "related_id": other["id"],
                        "related_name": other.get("symbol") or other.get("name", ""),
                        "source": CLINPGX_SOURCE_NAME,
                        "level_of_evidence": "",
                        "phenotype_categories": set(),
                        "annotation_count": 0,
                        "annotation_ids": [],
                    },
                )
                edge["annotation_count"] += 1
                edge["phenotype_categories"].update(row.get("types") or [])
                if row.get("accessionId") and len(edge["annotation_ids"]) < 5:
                    edge["annotation_ids"].append(row["accessionId"])
                if not edge["level_of_evidence"] or _evidence_rank(level) < _evidence_rank(
                    edge["level_of_evidence"]
                ):
                    edge["level_of_evidence"] = level
        edges = list(agg.values())
        for edge in edges:
            edge["phenotype_categories"] = sorted(edge["phenotype_categories"])
        edges.sort(key=lambda e: (_evidence_rank(e["level_of_evidence"]), e["related_name"]))
        return edges

    async def _guideline_edges(self, field: str, value: str, side: str) -> list[dict[str, Any]]:
        """CPIC / DPWG / CPNDS / RNPGx guideline annotations, one edge per counterpart."""
        if not value:
            return []
        rows = await self._get("guidelineAnnotation", {field: value})
        edges = []
        for row in rows:
            for other in self._counterparts(row, side):
                edges.append(
                    {
                        "relation_label": "has_guideline",
                        "related_id": other["id"],
                        "related_name": other.get("symbol") or other.get("name", ""),
                        "source": CLINPGX_SOURCE_NAME,
                        "guideline_id": row.get("id", ""),
                        "guideline_name": row.get("name", ""),
                        "guideline_source": row.get("source", ""),
                        "dosing_information": bool(row.get("dosingInformation")),
                    }
                )
        edges.sort(key=lambda e: (e["guideline_source"] != "CPIC", e["related_name"]))
        return edges

    async def _label_edges(self, drug_name: str) -> list[dict[str, Any]]:
        """Drug label annotations of a drug (FDA, EMA, PMDA, Swissmedic, ...)."""
        if not drug_name:
            return []
        rows = await self._get("drugLabel", {"relatedChemicals.name": drug_name})
        edges = []
        for row in rows:
            edges.append(
                {
                    "relation_label": "has_label",
                    "related_id": row.get("id", ""),
                    "related_name": row.get("name", ""),
                    "source": CLINPGX_SOURCE_NAME,
                    "label_source": row.get("source", ""),
                    "testing_level": (row.get("testing") or {}).get("term", ""),
                    "biomarker_status": row.get("biomarkerStatus", ""),
                    "prescribing_genes": [
                        g.get("symbol", "") for g in row.get("prescribingGenes") or []
                    ],
                }
            )
        return edges

    async def _haplotype_edges(self, symbol: str) -> list[dict[str, Any]]:
        if not symbol:
            return []
        rows = await self._get("haplotype", {"gene.symbol": symbol, "view": "min"})
        return [
            {
                "relation_label": "has_haplotype",
                "related_id": row.get("id", ""),
                "related_name": row.get("symbol", ""),
                "source": CLINPGX_SOURCE_NAME,
                "reference_allele": bool(row.get("reference")),
            }
            for row in rows
        ]

    @staticmethod
    def _counterparts(row: dict[str, Any], side: str) -> list[dict[str, Any]]:
        """Drugs (``chemicals``) or genes of an annotation row, with ids."""
        if side == "chemicals":
            items = row.get("relatedChemicals") or []
        else:
            items = row.get("relatedGenes") or (row.get("location") or {}).get("genes") or []
        return [i for i in items if i.get("id")]

    @staticmethod
    def _gene_edge(label: str, gene: dict[str, Any] | None) -> dict[str, Any]:
        gene = gene or {}
        return {
            "relation_label": label,
            "related_id": gene.get("id", ""),
            "related_name": gene.get("symbol", ""),
            "source": CLINPGX_SOURCE_NAME,
        }

    @staticmethod
    def _cap_per_label(rels: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        kept = []
        for rel in rels:
            n = counts.get(rel["relation_label"], 0)
            if n < limit:
                counts[rel["relation_label"]] = n + 1
                kept.append(rel)
        return kept

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _concept(self, kind: str, obj: dict[str, Any]) -> UnifiedConcept:
        """Build a concept from a gene / chemical / variant / haplotype record."""
        pa_id = str(obj["id"])
        label = obj.get("symbol") or obj.get("name") or pa_id
        concept = self._create_concept(pa_id, label, _KINDS[kind][1])
        concept.identifiers = []  # re-added below with a link
        concept.add_identifier(
            self.source, pa_id, label, f"https://www.clinpgx.org/{kind}/{pa_id}"
        )
        synonyms: list[str] = []
        name = obj.get("name")
        if name and name != label:
            synonyms.append(name)
        for group in (obj.get("altNames") or {}).values():
            synonyms.extend(s for s in group if s and s not in synonyms)
        categories = list(obj.get("types") or [])
        if obj.get("cpicGene"):
            categories.append("CPIC gene")
        if obj.get("vipTier"):
            categories.append(f"VIP {obj['vipTier']}")
        summary = ((obj.get("vipSummary") or {}).get("html")) or ""
        text = html.unescape(re.sub(r"\s+", " ", _TAG_RE.sub(" ", summary))).strip()
        for ref in (obj.get("crossReferences") or []) + (obj.get("linkOuts") or []):
            spec = _RESOURCE_MAP.get(ref.get("resource", ""))
            if spec and spec[0] in _IDENTIFIER_SOURCES and ref.get("resourceId"):
                concept.add_identifier(spec[0], str(ref["resourceId"]), label, ref.get("_url"))
        slim = {k: v for k, v in obj.items() if isinstance(v, str | int | float | bool)}
        slim["kind"] = kind
        slim["license"] = CLINPGX_LICENSE
        concept.semantic_types = [kind]
        concept.synonyms = synonyms
        concept.categories = categories
        concept.definitions = [text[:_SUMMARY_CHARS]] if text else []
        concept.confidence_score = 0.95
        cast(dict[Any, Any], concept.source_data)[KnowledgeSource.CLINPGX] = slim
        return concept
