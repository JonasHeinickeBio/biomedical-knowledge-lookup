"""
IMPC adapter (International Mouse Phenotyping Consortium).

The IMPC knocks out one gene at a time in mice and runs a standardised phenotyping
pipeline; a statistical test per parameter decides which phenotypes are *significant*.
These are **knockout-mouse phenotypes**: translational evidence for what a gene does in a
mammal, not human clinical findings. Human relevance comes only through the orthology that
the gene core carries (``human_gene_symbol``).

Data come from the public, keyless Solr cores behind the IMPC portal, verified live
2026-10 (``https://www.ebi.ac.uk/mi/impc/solr/<core>/select``, ``wt=json``):

* ``gene``: one document per mouse gene (``mgi_accession_id``, ``marker_symbol``,
  ``marker_name``, ``human_gene_symbol`` (list), synonyms, location, production and
  phenotyping status). Documents also hold a large base64 blob (``datasets_raw_data``), so
  every query restricts ``fl``. It carries **no Ensembl or HGNC identifier**; the human
  ortholog is a symbol only.
* ``genotype-phenotype``: one document per *significant* gene/phenotype call (67k in total)
  with ``mp_term_id``/``mp_term_name``, ``p_value``, ``effect_size``, ``zygosity``, ``sex``,
  ``life_stage_name``, ``parameter_name``, ``allele_symbol`` and the MP ancestors in
  ``intermediate_mp_term_id`` / ``top_level_mp_term_id``.
* ``mp``: the Mammalian Phenotype ontology (1,857 terms) with definitions, synonyms,
  parents and a ``mixSynQf`` text field for searching label and synonyms.

Quirks worth knowing:

* Symbol fields are case-sensitive strings. The ``*_lowercase`` twins
  (``marker_symbol_lowercase``, ``human_gene_symbol_lowercase``, ``marker_synonym_lowercase``,
  ``human_symbol_synonym_lowercase``) make lookups case-insensitive, so ``BRCA1`` (human)
  and ``Brca1`` (mouse) both work. This is how human gene symbols map to mouse genes.
* A gene can exist in the ``gene`` core with ``phenotyping_data_available: false`` (Brca1:
  embryonic lethal, no phenotyping), so a valid gene may legitimately have no phenotypes.
* ``p_value`` can be exactly ``0.0`` (underflow of an extremely small value, or the viability
  screen). It is the strongest possible call, so ranking sorts ascending and keeps it first.
* The MP-to-HP mapping is not exposed by these cores, so ``get_mappings`` cannot offer it.
* Phenotype lookups include annotations to *descendant* MP terms, so ``abnormal spleen
  morphology`` also lists genes annotated to ``increased spleen weight``; each edge names
  the term that was actually annotated.

Latency: 0.2 - 0.5 s per request; relationships need 1 - 2. Requests are spaced 0.3 s apart.
IMPC data are open (Creative Commons Attribution 4.0 per the IMPC data release terms:
cite the IMPC and the release; check https://www.mousephenotype.org/about-impc/ for the
current wording).
"""

import asyncio
import json
import logging
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

IMPC_SOLR_URL = "https://www.ebi.ac.uk/mi/impc/solr"
_PORTAL_GENE_URL = "https://www.mousephenotype.org/data/genes/{}"
_PORTAL_PHENOTYPE_URL = "https://www.mousephenotype.org/data/phenotypes/{}"

_MIN_INTERVAL = 0.3  # seconds between requests: no published limit, stay polite
_MAX_SEARCH = 50
_MAX_PHENOTYPE_EDGES = 25  # gene -> phenotype edges (best p-value first)
_MAX_GENE_EDGES = 25  # phenotype -> gene edges (best p-value first)
_CALLS_PER_PHENOTYPE = 5  # documents kept per phenotype to collect zygosity / sex

_GENE_FIELDS = ",".join(
    [
        "mgi_accession_id",
        "marker_symbol",
        "marker_name",
        "marker_synonym",
        "marker_type",
        "human_gene_symbol",
        "human_symbol_synonym",
        "chr_name",
        "chr_strand",
        "seq_region_start",
        "seq_region_end",
        "phenotype_status",
        "phenotyping_data_available",
        "mouse_production_status",
        "significant_top_level_mp_terms",
        "not_significant_top_level_mp_terms",
    ]
)
_MP_FIELDS = (
    "mp_id,mp_term,mp_definition,mp_term_synonym,parent_mp_id,parent_mp_term,"
    "top_level_mp_id,top_level_mp_term"
)
_GP_FIELDS = ",".join(
    [
        "marker_symbol",
        "marker_accession_id",
        "mp_term_id",
        "mp_term_name",
        "p_value",
        "effect_size",
        "zygosity",
        "sex",
        "life_stage_name",
        "parameter_name",
        "allele_symbol",
        "top_level_mp_term_name",
        "assertion_type",
    ]
)

_MGI_RE = re.compile(r"^MGI:\s*(\d{1,9})$", re.IGNORECASE)
_MP_RE = re.compile(r"^MP:\s*(\d{1,7})$", re.IGNORECASE)
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@/<>-]{0,40}$")
_SOLR_TEXT_STRIP_RE = re.compile(r"[^\w\s.-]")


def _quote(text: str) -> str:
    """A Solr phrase literal: quoted, with backslashes and quotes escaped."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class IMPCAdapter(KnowledgeSourceAdapter):
    """Adapter for the IMPC Solr cores (knockout-mouse genes and phenotypes)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = IMPC_SOLR_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.IMPC

    def is_available(self) -> bool:
        return True  # public Solr API, no key

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _solr(self, core: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET ``<core>/select`` with ``wt=json``, spacing requests politely."""
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        query = {"wt": "json", **params}
        url = f"{self.base_url}/{core}/select"

        async def _do() -> Any:
            # Solr answers JSON as text/plain, which aiohttp's response.json() refuses, so
            # _make_request cannot be used; retry and circuit breaker still apply.
            session = await self._get_session()
            async with session.get(url, params=query) as response:
                response.raise_for_status()
                return json.loads(await response.text())

        data = await self._call_with_retry("impc_solr", _do)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _docs(data: dict[str, Any]) -> list[dict[str, Any]]:
        response = data.get("response")
        docs = response.get("docs") if isinstance(response, dict) else None
        return [d for d in docs or [] if isinstance(d, dict)]

    @staticmethod
    def _groups(data: dict[str, Any], field: str) -> tuple[list[list[dict[str, Any]]], int]:
        """``(documents per group, number of groups)`` from a grouped Solr response."""
        grouped = (data.get("grouped") or {}).get(field) or {}
        groups = []
        for group in grouped.get("groups") or []:
            docs = [
                d for d in (group.get("doclist") or {}).get("docs") or [] if isinstance(d, dict)
            ]
            if docs:
                groups.append(docs)
        return groups, int(grouped.get("ngroups") or len(groups))

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("mgi", "MGI:95489")``, ``("mp", "MP:0004952")``, ``("symbol", "Fbn1")`` or ``None``.

        MGI and MP ids are case-insensitive; MP numbers are zero-padded to 7 digits. Anything
        else that looks like a gene symbol (mouse or human) is returned as a symbol.
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        match = _MGI_RE.match(text)
        if match:
            return "mgi", f"MGI:{int(match.group(1))}"
        match = _MP_RE.match(text)
        if match:
            return "mp", f"MP:{int(match.group(1)):07d}"
        if _SYMBOL_RE.match(text) and ":" not in text:
            return "symbol", text
        return None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def _find_genes(self, query: str, rows: int) -> list[dict[str, Any]]:
        """Genes by id, symbol (mouse or human, any case), synonym, then by name."""
        parsed = self._parse_id(query)
        if parsed and parsed[0] == "mgi":
            q = f"mgi_accession_id:{_quote(parsed[1])}"
            return self._docs(await self._solr("gene", {"q": q, "rows": rows, "fl": _GENE_FIELDS}))
        if parsed and parsed[0] == "mp":
            return []
        text = query.strip()
        docs: list[dict[str, Any]] = []
        if parsed and parsed[0] == "symbol":
            lowered = _quote(text.lower())
            q = " OR ".join(
                f"{field}:{lowered}"
                for field in (
                    "marker_symbol_lowercase",
                    "human_gene_symbol_lowercase",
                    "marker_synonym_lowercase",
                    "human_symbol_synonym_lowercase",
                )
            )
            data = await self._solr("gene", {"q": q, "rows": rows, "fl": _GENE_FIELDS})
            docs = self._docs(data)
        if not docs and len(text) >= 3:
            q = f"marker_name:{_quote(text)}"
            docs = self._docs(await self._solr("gene", {"q": q, "rows": rows, "fl": _GENE_FIELDS}))
        needle = text.casefold()

        def rank(doc: dict[str, Any]) -> int:
            if str(doc.get("marker_symbol", "")).casefold() == needle:
                return 0
            if needle in (str(s).casefold() for s in _as_list(doc.get("human_gene_symbol"))):
                return 1
            return 2

        return sorted(docs, key=rank)

    async def _find_phenotypes(self, query: str, rows: int) -> list[dict[str, Any]]:
        parsed = self._parse_id(query)
        if parsed and parsed[0] == "mp":
            q = f"mp_id:{_quote(parsed[1])}"
            return self._docs(await self._solr("mp", {"q": q, "rows": rows, "fl": _MP_FIELDS}))
        if parsed and parsed[0] == "mgi":
            return []
        text = _SOLR_TEXT_STRIP_RE.sub(" ", query).strip()
        if len(text) < 3:
            return []
        params = {
            "q": text,
            "defType": "edismax",
            "qf": "mixSynQf",
            "q.op": "AND",
            "rows": rows,
            "fl": _MP_FIELDS,
        }
        return self._docs(await self._solr("mp", params))

    # ------------------------------------------------------------------
    # Concept conversion
    # ------------------------------------------------------------------

    def _gene_to_concept(self, doc: dict[str, Any]) -> UnifiedConcept | None:
        mgi = str(doc.get("mgi_accession_id") or "")
        symbol = str(doc.get("marker_symbol") or "")
        if not mgi or not symbol:
            return None
        name = str(doc.get("marker_name") or "")
        concept = self._create_concept(mgi, symbol, ConceptType.GENE)
        humans = [str(s) for s in _as_list(doc.get("human_gene_symbol")) if s]
        synonyms: list[str] = []
        for value in [name, *humans, *_as_list(doc.get("marker_synonym"))]:
            if value and str(value) not in synonyms and str(value) != symbol:
                synonyms.append(str(value))
        concept.synonyms = synonyms
        ortholog = f" Human ortholog: {', '.join(humans)}." if humans else ""
        concept.definitions = [
            f"Mouse gene {symbol} ({name}).{ortholog}" if name else ortholog.strip()
        ]
        concept.semantic_types = [str(doc["marker_type"])] if doc.get("marker_type") else []
        concept.categories = ["knockout mouse model"]
        for identifier in (concept.identifiers or [])[:1]:
            identifier.url = _PORTAL_GENE_URL.format(mgi)
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[self.source] = {
                "kind": "gene",
                "marker_symbol": symbol,
                "marker_name": name,
                "human_gene_symbol": humans,
                "human_symbol_synonym": [
                    str(s) for s in _as_list(doc.get("human_symbol_synonym"))
                ],
                "chromosome": doc.get("chr_name"),
                "strand": doc.get("chr_strand"),
                "start": doc.get("seq_region_start"),
                "end": doc.get("seq_region_end"),
                "phenotyping_data_available": bool(doc.get("phenotyping_data_available")),
                "phenotype_status": doc.get("phenotype_status"),
                "mouse_production_status": doc.get("mouse_production_status"),
                "significant_top_level_mp_terms": _as_list(
                    doc.get("significant_top_level_mp_terms")
                ),
                "not_significant_top_level_mp_terms": _as_list(
                    doc.get("not_significant_top_level_mp_terms")
                ),
                "evidence_note": "knockout-mouse phenotypes (translational, not human)",
            }
        return concept

    def _phenotype_to_concept(self, doc: dict[str, Any]) -> UnifiedConcept | None:
        mp_id = str(doc.get("mp_id") or "")
        label = str(doc.get("mp_term") or "")
        if not mp_id or not label:
            return None
        concept = self._create_concept(mp_id, label, ConceptType.PHENOTYPE)
        concept.synonyms = [str(s) for s in _as_list(doc.get("mp_term_synonym")) if s]
        definition = doc.get("mp_definition")
        concept.definitions = [str(definition)] if definition else []
        concept.categories = [str(t) for t in _as_list(doc.get("top_level_mp_term")) if t]
        concept.semantic_types = ["Mammalian Phenotype"]
        concept.parents = [str(p) for p in _as_list(doc.get("parent_mp_id")) if p]
        for identifier in (concept.identifiers or [])[:1]:
            identifier.url = _PORTAL_PHENOTYPE_URL.format(mp_id)
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[self.source] = {
                "kind": "phenotype",
                "parent_mp_id": concept.parents,
                "parent_mp_term": _as_list(doc.get("parent_mp_term")),
                "top_level_mp_id": _as_list(doc.get("top_level_mp_id")),
                "top_level_mp_term": concept.categories,
            }
        return concept

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search genes (mouse or human symbol, synonym, name, MGI id), then MP terms.

        Human symbols resolve through the ortholog fields of the gene core. Genes come
        first, phenotypes fill the remaining slots.
        """
        text = (query or "").strip()
        if not text or limit < 1:
            return []
        rows = min(limit, _MAX_SEARCH)
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        try:
            for doc in await self._find_genes(text, rows):
                concept = self._gene_to_concept(doc)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
        except Exception as e:
            logger.error(f"IMPC gene search failed for '{text}': {e}")
        concepts = concepts[:limit]
        if len(concepts) < limit:
            try:
                for doc in await self._find_phenotypes(text, rows):
                    concept = self._phenotype_to_concept(doc)
                    if concept and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
            except Exception as e:
                logger.error(f"IMPC phenotype search failed for '{text}': {e}")
        concepts = concepts[:limit]
        logger.info(f"IMPC search for '{text}' returned {len(concepts)} concepts")
        return concepts

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Gene (``MGI:95489``, ``Fbn1`` or human ``FBN1``) or phenotype (``MP:0004952``)."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        try:
            if parsed[0] == "mp":
                docs = await self._find_phenotypes(parsed[1], 1)
                return self._phenotype_to_concept(docs[0]) if docs else None
            # a human symbol can match several mouse genes (paralogs); ranking puts the exact
            # mouse symbol first, then exact human-ortholog matches
            docs = await self._find_genes(parsed[1], 5)
            return self._gene_to_concept(docs[0]) if docs else None
        except Exception as e:
            logger.error(f"IMPC get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Mouse gene -> human ortholog symbol(s).

        The Solr cores expose the human ortholog as a **symbol only** (no HGNC id, no
        Ensembl id) and no MP-to-HP mapping, so those are not offered.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None or parsed[0] == "mp":
            return []
        try:
            docs = await self._find_genes(parsed[1], 5)
            if not docs:
                return []
            doc = docs[0]
            mgi = str(doc.get("mgi_accession_id") or "")
            mappings = []
            for symbol in dict.fromkeys(str(s) for s in _as_list(doc.get("human_gene_symbol"))):
                mappings.append(
                    {
                        "fromId": mgi,
                        "toId": symbol,
                        "fromSource": "MGI",
                        "toSource": "HGNC",
                        "mappingType": "ortholog",
                        "confidence": 0.9,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"IMPC get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Gene -> ``ortholog_of`` + ``has_phenotype``; phenotype -> ``phenotype_of`` + ``is_a``.

        Phenotype edges are significant IMPC calls, one per distinct MP term (gene -> terms)
        or per distinct gene (term -> genes), ranked by ascending p-value and capped at 25.
        Each carries ``p_value``, ``effect_size``, ``zygosities``, ``sexes``, ``life_stage``,
        ``parameter_name`` and ``n_calls``. These are knockout-mouse results.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return []
        try:
            if parsed[0] == "mp":
                return await self._phenotype_relationships(parsed[1])
            docs = await self._find_genes(parsed[1], 5)
            if not docs:
                return []
            return await self._gene_relationships(docs[0])
        except Exception as e:
            logger.warning(f"IMPC get_relationships failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Relationship builders
    # ------------------------------------------------------------------

    @staticmethod
    def _call_summary(docs: list[dict[str, Any]]) -> dict[str, Any]:
        """Best call (docs are sorted by p-value) plus the zygosities / sexes seen."""
        best = docs[0]
        return {
            "p_value": best.get("p_value"),
            "effect_size": best.get("effect_size"),
            "zygosity": best.get("zygosity"),
            "zygosities": sorted({str(d["zygosity"]) for d in docs if d.get("zygosity")}),
            "sex": best.get("sex"),
            "sexes": sorted({str(d["sex"]) for d in docs if d.get("sex")}),
            "life_stage": best.get("life_stage_name"),
            "parameter_name": best.get("parameter_name"),
            "allele_symbol": best.get("allele_symbol"),
            "n_calls": len(docs),
        }

    async def _gene_relationships(self, gene: dict[str, Any]) -> list[dict[str, Any]]:
        mgi = str(gene.get("mgi_accession_id") or "")
        symbol = str(gene.get("marker_symbol") or "")
        edges: list[dict[str, Any]] = []
        for human in dict.fromkeys(str(s) for s in _as_list(gene.get("human_gene_symbol"))):
            edges.append(
                {
                    "relation_label": "ortholog_of",
                    "related_id": human,
                    "related_name": human,
                    "source": "IMPC",
                    "from_symbol": symbol,
                    "related_species": "Homo sapiens",
                }
            )
        if not mgi:
            return edges
        params = {
            "q": f"marker_accession_id:{_quote(mgi)}",
            "rows": _MAX_PHENOTYPE_EDGES,
            "fl": _GP_FIELDS,
            "sort": "p_value asc",
            "group": "true",
            "group.field": "mp_term_id",
            "group.limit": _CALLS_PER_PHENOTYPE,
            "group.ngroups": "true",
        }
        groups, total = self._groups(await self._solr("genotype-phenotype", params), "mp_term_id")
        for docs in groups[:_MAX_PHENOTYPE_EDGES]:
            best = docs[0]
            if not best.get("mp_term_id"):
                continue
            edge = {
                "relation_label": "has_phenotype",
                "related_id": str(best["mp_term_id"]),
                "related_name": str(best.get("mp_term_name") or ""),
                "source": "IMPC",
                "evidence": "knockout mouse, significant IMPC call",
                "top_level_mp_terms": _as_list(best.get("top_level_mp_term_name")),
                "total_phenotypes": total,
            }
            edge.update(self._call_summary(docs))
            edges.append(edge)
        return edges

    async def _phenotype_relationships(self, mp_id: str) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        term_docs = await self._find_phenotypes(mp_id, 1)
        if term_docs:
            names = _as_list(term_docs[0].get("parent_mp_term"))
            for i, parent in enumerate(_as_list(term_docs[0].get("parent_mp_id"))):
                edges.append(
                    {
                        "relation_label": "is_a",
                        "related_id": str(parent),
                        "related_name": str(names[i]) if i < len(names) else "",
                        "source": "IMPC",
                    }
                )
        quoted = _quote(mp_id)
        params = {
            "q": f"mp_term_id:{quoted} OR intermediate_mp_term_id:{quoted}",
            "rows": _MAX_GENE_EDGES,
            "fl": _GP_FIELDS,
            "sort": "p_value asc",
            "group": "true",
            "group.field": "marker_accession_id",
            "group.limit": _CALLS_PER_PHENOTYPE,
            "group.ngroups": "true",
        }
        groups, total = self._groups(
            await self._solr("genotype-phenotype", params), "marker_accession_id"
        )
        for docs in groups[:_MAX_GENE_EDGES]:
            best = docs[0]
            if not best.get("marker_accession_id"):
                continue
            edge = {
                "relation_label": "phenotype_of",
                "related_id": str(best["marker_accession_id"]),
                "related_name": str(best.get("marker_symbol") or ""),
                "source": "IMPC",
                "evidence": "knockout mouse, significant IMPC call",
                "annotated_term_id": best.get("mp_term_id"),
                "annotated_term_name": best.get("mp_term_name"),
                "total_genes": total,
            }
            edge.update(self._call_summary(docs))
            edges.append(edge)
        return edges
