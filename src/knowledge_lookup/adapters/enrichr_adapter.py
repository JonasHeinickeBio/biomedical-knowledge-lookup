"""
Enrichr adapter (gene-set enrichment, a TOOL-LIKE source).

Unlike the other adapters, Enrichr does not look a concept up: it takes a **list of genes**
and says which pathways, GO terms, phenotypes or diseases they are over-represented in.
``search_concepts("IL6 TNF IL1B CXCL8")`` therefore treats the query as a gene list
(split on commas, semicolons and whitespace), runs enrichment against the configured
libraries and returns the top terms as concepts. :meth:`enrich` returns the same result as
structured rows.

PRIVACY: the genes are **uploaded to maayanlab.cloud** (Icahn School of Medicine at Mount
Sinai) via ``POST /Enrichr/addList`` and Enrichr **stores uploaded lists** (they are
retrievable by the returned ``userListId``/``shortId``). Do not send gene lists from
identifiable or restricted cohorts. The adapter caps the list at 500 genes, sends only a
constant description (never the genes or the query in it), reuses an upload for repeated
identical lists within one adapter instance, and never logs gene symbols at INFO.
Contrast with g:Profiler (not implemented here), which is a stateless POST that returns
results without a stored list.

Endpoints, verified live 2026-10 (``https://maayanlab.cloud/Enrichr``):

* ``GET datasetStatistics``: 228 libraries (69 KB), each with ``libraryName``, ``numTerms``,
  ``genesPerTerm``.
* ``POST addList``: multipart form with ``list`` (newline-separated symbols) and
  ``description``; answers ``{"shortId", "userListId"}`` with content type ``text/html``,
  so the body is parsed as JSON by hand.
* ``GET enrich?userListId=&backgroundType=<library>``: one library per call, all terms with at
  least one overlapping gene (KEGG: ~90 rows, 12 KB), each row
  ``[rank, term, p-value, odds ratio, combined score, overlapping genes, adjusted p-value,
  old p, old adjusted p]``. The odds ratio column is called "z-score" in the older API
  docs; the values observed are large positive numbers matching the web UI's odds ratio.
  An unknown library answers ``{}``; an unknown ``userListId`` answers HTTP 400.
* ``GET geneSetLibrary?mode=text&libraryName=``: the whole library as tab-separated text
  (no range support: KEGG 0.2 MB, HPO 0.4 MB, Reactome 0.9 MB, GO BP 1.4 MB, MGI MP 1.3 MB;
  1 - 6 s). Used by :meth:`get_concept_details`; parsed libraries are kept in memory.
* ``GET genemap?gene=&json=true&setup=false``: every term of all 231 libraries containing a
  gene (~0.9 MB, 1.7 s). Used by :meth:`get_relationships` and filtered to the configured
  libraries. It is not cheap, so results are cached per gene.

Libraries: ``ENRICHR_LIBRARIES`` (comma-separated names) overrides the default set of seven
current libraries. Names carry a year (``KEGG_2026``) and are retired over time: a name that
no longer exists yields no rows, silently. :meth:`list_libraries` returns the live names.

Enrichr is a web resource of the Ma'ayan Lab; cite Chen 2013 / Kuleshov 2016 / Xie 2021 and
follow https://maayanlab.cloud/Enrichr/help#terms. No rate limit is published; requests are
spaced 0.3 s apart.
"""

import asyncio
import json
import logging
import math
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

ENRICHR_BASE_URL = "https://maayanlab.cloud/Enrichr"
_TERM_URL = "https://maayanlab.cloud/Enrichr/"

#: Libraries used when ``ENRICHR_LIBRARIES`` is unset; names verified in ``datasetStatistics``.
DEFAULT_LIBRARIES = (
    "GO_Biological_Process_2025",
    "KEGG_2026",
    "Reactome_Pathways_2024",
    "WikiPathways_2024_Human",
    "MGI_Mammalian_Phenotype_Level_4_2024",
    "Human_Phenotype_Ontology",
    "Jensen_DISEASES_Curated_2025",
)

MAX_GENES = 500  # larger lists are truncated; also bounds what is uploaded to a third party
_MIN_INTERVAL = 0.3  # seconds between requests
_ID_SEP = "::"  # concept id = "<library>::<term>"; terms may contain ":" (HP:0001697)
_MAX_MEMBERS = 500  # genes returned by get_concept_details / has_member edges
_MAX_MEMBER_EDGES = 100
_MAX_TERMS_PER_LIBRARY = 25  # member_of edges per library
_MAX_CACHED_LIBRARIES = 3
_UPLOAD_DESCRIPTION = "knowledge-lookup enrichment query"

_GENE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@/-]{0,30}$")
_LIBRARY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")
_SPLIT_RE = re.compile(r"[,;\s]+")
_TERM_ID_RE = re.compile(r"(GO:\d{7}|HP:\d{7}|MP:\d{7}|WP\d+|R-[A-Z]{3}-\d+|hsa\d{5})")


def _library_type(library: str) -> ConceptType:
    name = library.casefold()
    if "go_biological" in name:
        return ConceptType.BIOLOGICAL_PROCESS
    if "go_molecular" in name:
        return ConceptType.MOLECULAR_FUNCTION
    if "go_cellular" in name:
        return ConceptType.CELLULAR_COMPONENT
    if any(k in name for k in ("kegg", "reactome", "wikipath", "biocarta", "panther", "msigdb")):
        return ConceptType.PATHWAY
    if any(k in name for k in ("phenotype", "hpo", "komp2", "mgi_mammalian")):
        return ConceptType.PHENOTYPE
    if any(k in name for k in ("disease", "disgenet", "omim", "orphanet", "clinvar", "gwas")):
        return ConceptType.DISEASE
    return ConceptType.UNKNOWN


class EnrichrAdapter(KnowledgeSourceAdapter):
    """Adapter for Enrichr gene-set enrichment (uploads gene lists to maayanlab.cloud)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = ENRICHR_BASE_URL
        raw = os.getenv("ENRICHR_LIBRARIES", "")
        names = [n.strip() for n in raw.split(",") if _LIBRARY_RE.match(n.strip())]
        self.libraries: tuple[str, ...] = tuple(dict.fromkeys(names)) or DEFAULT_LIBRARIES
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._list_ids: dict[tuple[str, ...], int] = {}
        self._library_cache: dict[str, dict[str, list[str]]] = {}
        self._gene_terms: dict[str, dict[str, list[str]]] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ENRICHR

    def is_available(self) -> bool:
        return True  # public web service, no key

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _throttle(self) -> None:
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _get_text(self, path: str, params: dict[str, Any]) -> str:
        await self._throttle()
        return await self._make_request_text(f"{self.base_url}/{path}", params)

    async def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        # Enrichr does not reliably send a JSON content type, so parse the text by hand.
        return json.loads(await self._get_text(path, params))

    async def _upload(self, genes: list[str]) -> int | None:
        """Upload a gene list and return its ``userListId`` (reused for identical lists)."""
        key = tuple(genes)
        if key in self._list_ids:
            return self._list_ids[key]
        await self._throttle()
        url = f"{self.base_url}/addList"
        payload = "\n".join(genes)

        async def _do() -> Any:
            import aiohttp  # deferred like the base class: heavy import, HTTP adapters only

            # Enrichr rejects the urlencoded form (HTTP 400); it needs multipart/form-data.
            form = aiohttp.FormData(default_to_multipart=True)
            form.add_field("list", payload)
            form.add_field("description", _UPLOAD_DESCRIPTION)
            session = await self._get_session()
            async with session.post(url, data=form) as response:
                response.raise_for_status()
                return json.loads(await response.text())

        data = await self._call_with_retry("enrichr_add_list", _do)
        list_id = data.get("userListId") if isinstance(data, dict) else None
        if not isinstance(list_id, int):
            return None
        self._list_ids[key] = list_id
        return list_id

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_genes(query: str) -> list[str] | None:
        """Gene symbols from a query, or ``None`` if it does not look like a gene list.

        Symbols are split on commas, semicolons and whitespace, upper-cased (Enrichr matches
        case-insensitively) and de-duplicated; the list is truncated to ``MAX_GENES``. A
        token that is not symbol-shaped, or a query made only of plain lower-case words
        (``long covid``), marks the query as free text: nothing is then sent to Enrichr.
        """
        tokens = [t for t in _SPLIT_RE.split((query or "").strip()) if t]
        if not tokens:
            return None
        if not all(_GENE_RE.match(t) for t in tokens):
            return None
        # "long covid" is words, "IL6 il10" or "BRCA1" are genes: at least one token must have
        # a capital, a digit or a hyphen.
        if not any(any(c.isupper() or c.isdigit() or c == "-" for c in t) for t in tokens):
            return None
        genes = list(dict.fromkeys(t.upper() for t in tokens))
        if len(genes) > MAX_GENES:
            logger.warning(f"Enrichr gene list truncated from {len(genes)} to {MAX_GENES}")
            genes = genes[:MAX_GENES]
        return genes

    @staticmethod
    def _parse_row(library: str, row: Any, n_input: int) -> dict[str, Any] | None:
        if not isinstance(row, list) or len(row) < 7 or not isinstance(row[1], str):
            return None
        overlap = [str(g) for g in row[5]] if isinstance(row[5], list) else []
        term = row[1]
        match = _TERM_ID_RE.search(term)
        return {
            "library": library,
            "rank": row[0],
            "term": term,
            "term_id": match.group(1) if match else None,
            "p_value": row[2],
            "odds_ratio": row[3],
            "combined_score": row[4],
            "overlapping_genes": overlap,
            "n_overlap": len(overlap),
            "n_input_genes": n_input,
            "adjusted_p_value": row[6],
        }

    @staticmethod
    def _split_id(concept_id: str) -> tuple[str, str] | None:
        library, sep, term = (concept_id or "").partition(_ID_SEP)
        library, term = library.strip(), term.strip()
        if not sep or not term or not _LIBRARY_RE.match(library):
            return None
        return library, term

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    async def list_libraries(self) -> list[dict[str, Any]]:
        """Live library catalogue (``libraryName``, ``numTerms``, ``genesPerTerm``)."""
        try:
            data = await self._get_json("datasetStatistics", {})
        except Exception as e:
            logger.error(f"Enrichr list_libraries failed: {type(e).__name__}")
            return []
        stats = data.get("statistics") if isinstance(data, dict) else None
        return [s for s in stats or [] if isinstance(s, dict) and s.get("libraryName")]

    async def enrich(
        self, genes: list[str] | str, libraries: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Enrichment rows for a gene list: the top ``limit`` terms *per library*.

        Rows are sorted by adjusted p-value within each library and carry ``library``,
        ``term``, ``term_id``, ``p_value``, ``adjusted_p_value``, ``odds_ratio``,
        ``combined_score``, ``overlapping_genes``, ``n_overlap`` and ``n_input_genes``.
        ``genes`` is a list or a string in the ``search_concepts`` format. Failures (a
        library that errors, an upload that fails) are logged without the genes and skipped.
        """
        parsed = (
            self._parse_genes(genes)
            if isinstance(genes, str)
            else self._parse_genes(" ".join(str(g) for g in genes or []))
        )
        if not parsed or limit < 1:
            return []
        wanted = [lib for lib in (libraries or self.libraries) if _LIBRARY_RE.match(lib)]
        try:
            list_id = await self._upload(parsed)
        except Exception as e:
            logger.error(f"Enrichr upload failed: {type(e).__name__}")
            return []
        if list_id is None:
            logger.error("Enrichr upload returned no userListId")
            return []
        logger.info(f"Enrichr: uploaded a list of {len(parsed)} genes, {len(wanted)} libraries")
        rows: list[dict[str, Any]] = []
        for library in dict.fromkeys(wanted):
            try:
                data = await self._get_json(
                    "enrich", {"userListId": list_id, "backgroundType": library}
                )
            except Exception as e:
                logger.warning(f"Enrichr enrich failed for {library}: {type(e).__name__}")
                continue
            parsed_rows = [
                r
                for r in (
                    self._parse_row(library, row, len(parsed))
                    for row in (data.get(library) if isinstance(data, dict) else None) or []
                )
                if r
            ]
            parsed_rows.sort(key=lambda r: (r["adjusted_p_value"], r["p_value"]))
            rows.extend(parsed_rows[:limit])
        return rows

    # ------------------------------------------------------------------
    # Concept conversion
    # ------------------------------------------------------------------

    def _row_to_concept(self, row: dict[str, Any]) -> UnifiedConcept:
        library, term = row["library"], row["term"]
        concept = self._create_concept(f"{library}{_ID_SEP}{term}", term, _library_type(library))
        concept.categories = [library]
        concept.semantic_types = ["gene set"]
        adjusted = row["adjusted_p_value"]
        significant = isinstance(adjusted, (int, float)) and adjusted < 0.05
        concept.confidence_score = 0.9 if significant else 0.4
        concept.definitions = [
            f"{library} term enriched in the input genes: adjusted p = {adjusted:.3g}, "
            f"odds ratio = {row['odds_ratio']:.3g}, {row['n_overlap']} overlapping genes."
        ]
        for identifier in (concept.identifiers or [])[:1]:
            identifier.url = _TERM_URL
        if isinstance(concept.source_data, dict):
            concept.source_data[self.source] = {
                **{k: v for k, v in row.items() if k != "library"},
                "library": library,
                "evidence_note": "over-representation of the input genes, not per-gene evidence",
            }
        return concept

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Run enrichment for the genes in ``query`` and return the best terms as concepts.

        The query is a gene symbol or a list separated by commas / whitespace (see
        :meth:`_parse_genes`). Terms are taken from every configured library in turn (best
        adjusted p-value first, ``ceil(limit / n_libraries)`` per library) so that pathways,
        phenotypes and diseases all appear, then cut to ``limit``. A single gene gives
        weak statistics (every term containing it); use two or more genes for enrichment.
        """
        genes = self._parse_genes(query)
        if genes is None or limit < 1:
            return []
        per_library = max(1, math.ceil(limit / max(1, len(self.libraries))))
        rows = await self.enrich(genes, None, per_library)
        by_library: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_library.setdefault(row["library"], []).append(row)
        ordered: list[dict[str, Any]] = []
        depth = 0
        while len(ordered) < limit and any(depth < len(v) for v in by_library.values()):
            for library_rows in by_library.values():
                if depth < len(library_rows) and len(ordered) < limit:
                    ordered.append(library_rows[depth])
            depth += 1
        concepts = [self._row_to_concept(r) for r in ordered]
        logger.info(f"Enrichr search returned {len(concepts)} concepts for {len(genes)} genes")
        return concepts

    # ------------------------------------------------------------------
    # Library members
    # ------------------------------------------------------------------

    async def _library_terms(self, library: str) -> dict[str, list[str]]:
        """``{term: [genes]}`` of one library, parsed from the text download and cached."""
        if library in self._library_cache:
            return self._library_cache[library]
        text = await self._get_text("geneSetLibrary", {"mode": "text", "libraryName": library})
        terms: dict[str, list[str]] = {}
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 3 or not parts[0].strip():
                continue
            # Weighted libraries write "GENE,weight"; keep the symbol only.
            genes = [g.split(",")[0].strip() for g in parts[2:] if g.strip()]
            terms[parts[0].strip()] = genes
        if len(self._library_cache) >= _MAX_CACHED_LIBRARIES:
            self._library_cache.pop(next(iter(self._library_cache)))
        self._library_cache[library] = terms
        return terms

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Gene members of a term. ``concept_id`` is ``<library>::<term>`` as returned by search.

        Downloads the whole library once (0.2 - 1.4 MB, cached in memory).
        """
        parsed = self._split_id(concept_id)
        if parsed is None:
            return None
        library, term = parsed
        try:
            terms = await self._library_terms(library)
        except Exception as e:
            logger.error(f"Enrichr get_concept_details failed: {type(e).__name__}")
            return None
        members = terms.get(term)
        if members is None:
            lowered = {t.casefold(): t for t in terms}
            matched = lowered.get(term.casefold())
            if matched is None:
                return None
            term, members = matched, terms[matched]
        concept = self._create_concept(f"{library}{_ID_SEP}{term}", term, _library_type(library))
        concept.categories = [library]
        concept.semantic_types = ["gene set"]
        concept.definitions = [f"{library} gene set with {len(members)} genes."]
        for identifier in (concept.identifiers or [])[:1]:
            identifier.url = _TERM_URL
        concept.confidence_score = 0.9
        match = _TERM_ID_RE.search(term)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.source] = {
                "library": library,
                "term_id": match.group(1) if match else None,
                "n_genes": len(members),
                "genes": members[:_MAX_MEMBERS],
                "truncated": len(members) > _MAX_MEMBERS,
            }
        return concept

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Gene -> ``member_of`` terms; term (``<library>::<term>``) -> ``has_member`` genes.

        Membership, not enrichment: for a gene it lists the terms of the configured libraries
        that contain it (``genemap``, ~0.9 MB, cached per gene), at most 25 per library; for
        a term it lists up to 100 member genes from the cached library.
        """
        text = (concept_id or "").strip()
        try:
            parsed = self._split_id(text)
            if parsed is not None:
                return await self._term_members(*parsed)
            if not _GENE_RE.match(text):
                return []
            return await self._gene_memberships(text.upper())
        except Exception as e:
            logger.warning(f"Enrichr get_relationships failed: {type(e).__name__}")
            return []

    async def _gene_memberships(self, gene: str) -> list[dict[str, Any]]:
        if gene not in self._gene_terms:
            data = await self._get_json(
                "genemap", {"gene": gene, "json": "true", "setup": "false"}
            )
            raw = data.get("gene") if isinstance(data, dict) else None
            self._gene_terms[gene] = (
                {k: [str(t) for t in v] for k, v in raw.items() if isinstance(v, list)}
                if isinstance(raw, dict)
                else {}
            )
        edges = []
        for library in self.libraries:
            terms = self._gene_terms[gene].get(library, [])
            for term in terms[:_MAX_TERMS_PER_LIBRARY]:
                edges.append(
                    {
                        "relation_label": "member_of",
                        "related_id": f"{library}{_ID_SEP}{term}",
                        "related_name": term,
                        "source": "ENRICHR",
                        "library": library,
                        "terms_in_library": len(terms),
                    }
                )
        return edges

    async def _term_members(self, library: str, term: str) -> list[dict[str, Any]]:
        terms = await self._library_terms(library)
        members = terms.get(term)
        if members is None:
            members = next((v for k, v in terms.items() if k.casefold() == term.casefold()), None)
        if not members:
            return []
        return [
            {
                "relation_label": "has_member",
                "related_id": gene,
                "related_name": gene,
                "source": "ENRICHR",
                "library": library,
                "n_members": len(members),
            }
            for gene in members[:_MAX_MEMBER_EDGES]
        ]
