"""
NCBI Gene Expression Omnibus (GEO) adapter: dataset discovery, metadata and URLs only.

GEO is the public archive for functional-genomics studies (expression, methylation,
ChIP-/ATAC-seq, ...). The adapter exists to *find* datasets (for example for ME/CFS or Long
COVID); it never downloads data files. Served by the NCBI E-utilities with ``db=gds``
(verified live 2026-10):

* ``esearch`` returns GEO UIDs. UIDs encode the entry type: ``200xxxxxx`` = GSE series,
  ``300xxxxxx`` = GSM sample, ``100xxxxxx`` = GPL platform, small numbers (``5435``) = GDS
  curated dataset; the accession number is the UID minus the type offset, so an accession is
  turned into its UID **without a search call**. The default result order is newest first;
  ``sort=relevance`` is accepted but changes nothing, so no sort is sent.
* ``esummary`` (``retmode=json``) per UID: ``accession``, ``title``, ``summary``, ``taxon``
  (``;``-separated when a study spans several organisms), ``entrytype``, ``gdstype``
  (e.g. "Expression profiling by high throughput sequencing"), ``gpl`` (``;``-separated
  platform numbers), ``gse`` (parent series number on GSM/GDS; series list on GPL),
  ``n_samples``, ``pubmedids``, ``bioproject``, ``extrelations`` (SRA study accession),
  ``suppfile`` (supplementary file *types* only, e.g. "CSV, IDAT"), ``ftplink`` and
  ``samples`` (``{accession, title}`` for **every** sample: a series with 800 samples is a
  ~50 KB response, one with thousands is correspondingly larger).
* ``elink`` ``gds -> taxonomy`` yields NCBI taxonomy ids (the esummary only has the name).
* Other fields usable in search terms (``einfo``): ``[ETYP]`` entry type (``gse``, ``gds``,
  ``gpl``, ``gsm``), ``[ORGN]`` organism, ``[GTYP]`` dataset type, ``[PTYP]`` platform
  technology, ``[PDAT]`` publication date (``2024/01:2026/12[PDAT]``), ``[NSAM]`` number of
  samples (``50:1000[NSAM]``), ``[MESH]``, ``[ACCN]`` accession (also matches the sample
  and platform entries of a series), ``[AUTH]``, ``[SRC]``. ``[GPL]``, ``[PMID]`` and
  ``[TaxID]`` are **not** fields (they are silently treated as plain words).

Search scope: a query matches series (GSE) and curated datasets (GDS) unless it already
names an entry type (``... AND gsm[ETYP]``) or the caller passes ``entry_type=``; samples
alone would flood the result (202 GSM versus 30 GSE for "chronic fatigue syndrome").

Usage guidelines (https://www.ncbi.nlm.nih.gov/books/NBK25497/): at most 3 requests/s
without an API key, 10/s with ``NCBI_API_KEY`` (or ``ncbi`` in the config's ``api_keys``);
calls are spaced accordingly. ``tool=knowledge-lookup`` is always sent; a contact address
(``NCBI_EMAIL`` / ``ncbi_email``) only if configured. NCBI asks for large jobs to run
outside US peak hours. GEO records are public domain, but individual submitters may
claim rights over their data; cite the GEO accession and the associated publication.
"""

import asyncio
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GEO_DB = "gds"
TOOL_NAME = "knowledge-lookup"
GEO_RECORD_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}"

_ACCESSION_RE = re.compile(r"^(?:geo\s*[:_]\s*)?(GSE|GPL|GSM|GDS)\s*0*(\d{1,9})$", re.IGNORECASE)

# UID offset per accession prefix (GDS UIDs are the bare dataset number).
_UID_OFFSET = {"GSE": 200_000_000, "GPL": 100_000_000, "GSM": 300_000_000, "GDS": 0}
_ENTRY_TYPE_NAMES = {
    "GSE": "GEO Series",
    "GPL": "GEO Platform",
    "GSM": "GEO Sample",
    "GDS": "GEO DataSet",
}
_CONCEPT_TYPES = {
    "GSE": ConceptType.STUDY,
    "GDS": ConceptType.STUDY,
    "GPL": ConceptType.ASSAY,
    "GSM": ConceptType.OBSERVATION,
}
# user-facing entry-type filter -> ETYP value; ``None`` means "no restriction"
_ENTRY_TYPE_FILTERS: dict[str, str | None] = {
    "gse": "gse",
    "series": "gse",
    "gds": "gds",
    "dataset": "gds",
    "datasets": "gds",
    "gpl": "gpl",
    "platform": "gpl",
    "platforms": "gpl",
    "gsm": "gsm",
    "sample": "gsm",
    "samples": "gsm",
    "any": None,
    "all": None,
}
_DEFAULT_ETYP_CLAUSE = "(gse[ETYP] OR gds[ETYP])"
_ETYP_IN_QUERY_RE = re.compile(r"\[\s*(?:ETYP|Entry\s+Type)\s*\]", re.IGNORECASE)

# esummary documents carry every sample, so keep pages modest.
_MAX_SEARCH = 50
_MAX_QUERY_LENGTH = 500
_MAX_SUMMARY_LENGTH = 6000
_MAX_PLATFORM_LOOKUPS = 10
_MIN_INTERVAL_KEYLESS = 0.34  # 3 requests/s
_MIN_INTERVAL_KEYED = 0.11  # 10 requests/s


class GEOAdapter(KnowledgeSourceAdapter):
    """Adapter for GEO series, datasets, platforms and samples (metadata and URLs only)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = EUTILS_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.GEO

    def is_available(self) -> bool:
        return True  # E-utilities are public; a key only raises the rate limit

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _api_key(self) -> str | None:
        return self.config.get_api_key("ncbi") or os.getenv("NCBI_API_KEY") or None

    async def _eutils(self, endpoint: str, params: dict[str, Any], db: str = GEO_DB) -> Any:
        """GET ``{endpoint}.fcgi`` on E-utilities, spacing calls to NCBI's rate limit."""
        api_key = self._api_key()
        interval = _MIN_INTERVAL_KEYED if api_key else _MIN_INTERVAL_KEYLESS
        query = {"retmode": "json", "tool": TOOL_NAME, **params}
        # elink names its source database ``dbfrom``; its target ``db`` comes in ``params``
        query["dbfrom" if endpoint == "elink" else "db"] = db
        if api_key:
            query["api_key"] = api_key
        email = self.config.get_api_key("ncbi_email") or os.getenv("NCBI_EMAIL")
        if email:
            query["email"] = email
        async with self._throttle_lock:
            wait = interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        return await self._make_request(f"{self.base_url}/{endpoint}.fcgi", query)

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str, str] | None:
        """``("GSE", "GSE327255", "200327255")`` for ``GSE327255`` (any case, ``GEO:`` prefix).

        Returns ``None`` for anything that is not a GSE/GPL/GSM/GDS accession.
        """
        match = _ACCESSION_RE.match((concept_id or "").strip())
        if not match:
            return None
        prefix, number = match.group(1).upper(), int(match.group(2))
        if number < 1:
            return None
        return prefix, f"{prefix}{number}", str(_UID_OFFSET[prefix] + number)

    @staticmethod
    def _entry_prefix(doc: dict[str, Any]) -> str:
        """``GSE``/``GPL``/``GSM``/``GDS`` of an esummary document."""
        accession = str(doc.get("accession") or "")
        match = re.match(r"^(GSE|GPL|GSM|GDS)", accession.upper())
        return match.group(1) if match else str(doc.get("entrytype") or "").upper()

    # ------------------------------------------------------------------
    # E-utilities wrappers
    # ------------------------------------------------------------------

    async def _summaries(self, uids: list[str]) -> list[dict[str, Any]]:
        """esummary documents for ``uids`` (error documents are dropped), in request order."""
        if not uids:
            return []
        data = await self._eutils("esummary", {"id": ",".join(uids)})
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            return []
        docs = []
        for uid in result.get("uids") or []:
            doc = result.get(uid)
            if isinstance(doc, dict) and not doc.get("error") and doc.get("accession"):
                docs.append(doc)
        return docs

    async def _search_uids(self, term: str, retmax: int) -> list[str]:
        data = await self._eutils("esearch", {"term": term, "retmax": retmax})
        result = data.get("esearchresult") if isinstance(data, dict) else None
        return [str(u) for u in (result or {}).get("idlist") or []]

    async def _fetch_doc(self, concept_id: str) -> dict[str, Any] | None:
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        docs = await self._summaries([parsed[2]])
        return docs[0] if docs else None

    async def _taxa(self, uid: str, names: bool = True) -> list[tuple[str, str]]:
        """``[(taxonomy id, scientific name)]`` for a GEO UID via elink + taxonomy esummary.

        ``names=False`` skips the second call (names come back empty) for callers that only
        need the ids.
        """
        data = await self._eutils("elink", {"id": uid, "db": "taxonomy"})
        tax_ids: list[str] = []
        for linkset in (data or {}).get("linksets") or []:
            for linksetdb in linkset.get("linksetdbs") or []:
                tax_ids.extend(str(t) for t in linksetdb.get("links") or [])
        tax_ids = list(dict.fromkeys(tax_ids))
        if not tax_ids:
            return []
        if not names:
            return [(t, "") for t in tax_ids]
        data = await self._eutils("esummary", {"id": ",".join(tax_ids)}, db="taxonomy")
        result = (data or {}).get("result") or {}
        return [(t, str((result.get(t) or {}).get("scientificname") or "")) for t in tax_ids]

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    @staticmethod
    def build_term(query: str, entry_type: str | None = None) -> str | None:
        """The ``gds`` search term for ``query``; ``None`` when ``entry_type`` is unknown.

        ``query`` may use GEO field syntax (``"long covid" AND "Homo sapiens"[ORGN]``). It is
        wrapped in parentheses so an ``OR`` stays inside the entry-type restriction. Without
        ``entry_type`` (``series``/``dataset``/``platform``/``sample``/``any`` or an ETYP
        value) series and curated datasets are searched, unless the query already contains
        an ``[ETYP]`` clause.
        """
        text = query.strip()[:_MAX_QUERY_LENGTH]
        if entry_type is not None:
            key = entry_type.strip().lower()
            if key not in _ENTRY_TYPE_FILTERS:
                return None
            etyp = _ENTRY_TYPE_FILTERS[key]
            return f"({text}) AND {etyp}[ETYP]" if etyp else text
        if _ETYP_IN_QUERY_RE.search(text):
            return text
        return f"({text}) AND {_DEFAULT_ETYP_CLAUSE}"

    async def search_concepts(
        self, query: str, limit: int = 20, entry_type: str | None = None
    ) -> list[UnifiedConcept]:
        """Search GEO (newest first); a bare accession goes straight to details.

        ``entry_type`` restricts to ``series``, ``dataset`` (GDS), ``platform``, ``sample``
        or ``any``; the default is series plus curated datasets (see :meth:`build_term`).
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            if self._parse_id(text) is not None:
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            term = self.build_term(text, entry_type)
            if term is None:
                logger.warning(f"GEO search: unknown entry_type '{entry_type}'")
                return []
            size = min(limit, _MAX_SEARCH)
            docs = await self._summaries(await self._search_uids(term, size))
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank, doc in enumerate(docs):
                concept = self._doc_to_concept(doc)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concept.confidence_score = max(0.5, 0.9 - 0.02 * rank)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"GEO search for '{text}' returned {len(concepts)} records")
            return concepts
        except Exception as e:
            logger.error(f"GEO search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Metadata of one series/dataset/platform/sample, with URLs but no data files."""
        try:
            doc = await self._fetch_doc(concept_id)
            if doc is None:
                return None
            concept = self._doc_to_concept(doc)
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"GEO get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Typed links of a GEO record.

        ``relation_label`` values: ``uses_platform`` (GSE/GDS/GSM -> ``GPL...``, with the
        platform title), ``has_sample`` (GSE/GDS -> ``GSM...``, capped by ``limit``; every
        item carries ``total_samples``), ``part_of_series`` (GSM -> ``GSE...``),
        ``derived_from_series`` (GDS -> ``GSE...``), ``used_by_series`` (GPL -> ``GSE...``,
        capped), ``has_publication`` (``PMID:<id>``) and ``has_organism``
        (``NCBITaxon:<id>``, resolved with one extra elink call). Never contains data-file
        links.
        """
        if limit <= 0:
            return []
        try:
            doc = await self._fetch_doc(concept_id)
            if doc is None:
                return []
            return await self._relationships_from_doc(doc, limit)
        except Exception as e:
            logger.error(f"GEO get_relationships failed for '{concept_id}': {e}")
            return []

    async def _relationships_from_doc(
        self, doc: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        prefix = self._entry_prefix(doc)
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(label: str, related_id: str, name: str = "", **extra: Any) -> None:
            if not related_id or (label, related_id) in seen:
                return
            seen.add((label, related_id))
            results.append(
                {
                    "relation_label": label,
                    "related_id": related_id,
                    "related_name": name,
                    "source": "GEO",
                    **{k: v for k, v in extra.items() if v not in (None, "")},
                }
            )

        series = self._numbers(doc.get("gse"))
        if prefix == "GSM" and series:
            add("part_of_series", f"GSE{series[0]}")
        elif prefix == "GDS" and series:
            add("derived_from_series", f"GSE{series[0]}", doc.get("seriestitle") or "")
        elif prefix == "GPL":
            for number in series[:limit]:
                add("used_by_series", f"GSE{number}")

        platforms = [f"GPL{n}" for n in self._numbers(doc.get("gpl"))] if prefix != "GPL" else []
        titles = await self._platform_titles(platforms[:_MAX_PLATFORM_LOOKUPS])
        for accession in platforms:
            add("uses_platform", accession, titles.get(accession, ""))

        samples = [s for s in doc.get("samples") or [] if isinstance(s, dict)]
        total = self._to_int(doc.get("n_samples")) or len(samples)
        # esummary lists samples in arbitrary order; sort so the cap is deterministic
        samples.sort(key=lambda s: self._to_int(str(s.get("accession") or "")[3:]) or 0)
        for sample in samples[:limit]:
            add(
                "has_sample",
                str(sample.get("accession") or ""),
                sample.get("title") or "",
                total_samples=total,
            )

        for pmid in doc.get("pubmedids") or []:
            add("has_publication", f"PMID:{pmid}")

        for tax_id, name in await self._taxa(str(doc.get("uid"))):
            add("has_organism", f"NCBITaxon:{tax_id}", name)
        return results

    async def _platform_titles(self, accessions: list[str]) -> dict[str, str]:
        """``{GPL accession: title}`` with one esummary call (empty on failure)."""
        parsed = [self._parse_id(a) for a in accessions]
        uids = [p[2] for p in parsed if p]
        if not uids:
            return {}
        try:
            return {
                str(d["accession"]): str(d.get("title") or "") for d in await self._summaries(uids)
            }
        except Exception as e:  # titles are decoration; keep the relationships
            logger.warning(f"GEO platform title lookup failed: {e}")
            return {}

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Identifiers outside GEO: PubMed ids, NCBI taxonomy ids, BioProject and SRA study.

        BioProject (``PRJNA...``) and SRA study (``SRP...``) come from the record itself, so
        they are present only where GEO exposes them (series and curated datasets with
        sequencing data). The ids point at metadata pages; no data is fetched.
        """
        try:
            doc = await self._fetch_doc(concept_id)
            if doc is None:
                return []
            from_id = str(doc.get("accession"))
            mappings: list[dict[str, Any]] = []

            def add(to_id: str, to_source: str, mapping_type: str) -> None:
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": to_id,
                        "fromSource": "GEO",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": 1.0,
                    }
                )

            for pmid in doc.get("pubmedids") or []:
                add(f"PMID:{pmid}", "PUBMED", "cites")
            for tax_id, _ in await self._taxa(str(doc.get("uid")), names=False):
                add(f"NCBITaxon:{tax_id}", "NCBITAXON", "organism")
            bioproject = str(doc.get("bioproject") or "").strip()
            if bioproject:
                add(f"BioProject:{bioproject}", "BIOPROJECT", "xref")
            for rel in doc.get("extrelations") or []:
                if isinstance(rel, dict) and rel.get("relationtype") == "SRA":
                    target = str(rel.get("targetobject") or "").strip()
                    if target:
                        add(f"SRA:{target}", "SRA", "xref")
            return mappings
        except Exception as e:
            logger.error(f"GEO get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _numbers(value: Any) -> list[str]:
        """Numbers from a ``;``-separated esummary field (``"34284;24676"``)."""
        return [p.strip() for p in str(value or "").split(";") if p.strip().isdigit()]

    @staticmethod
    def _split(value: Any, sep: str) -> list[str]:
        return [p.strip() for p in str(value or "").split(sep) if p.strip()]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _doc_to_concept(self, doc: dict[str, Any]) -> UnifiedConcept | None:
        accession = str(doc.get("accession") or "").upper()
        prefix = self._entry_prefix(doc)
        if prefix not in _CONCEPT_TYPES or not accession:
            return None
        title = str(doc.get("title") or "").strip() or accession
        concept = self._create_concept(accession, title, _CONCEPT_TYPES[prefix])
        url = GEO_RECORD_URL.format(acc=accession)
        if concept.identifiers:
            concept.identifiers[0].url = url

        summary = str(doc.get("summary") or "").strip()
        if summary and concept.definitions is not None:
            concept.definitions.append(summary[:_MAX_SUMMARY_LENGTH])
        gds_types = self._split(doc.get("gdstype"), ";")
        if concept.semantic_types is not None:
            concept.semantic_types.extend([_ENTRY_TYPE_NAMES[prefix], *gds_types])
        taxa = self._split(doc.get("taxon"), ";")
        if concept.categories is not None:
            concept.categories.extend(taxa)

        samples = doc.get("samples") if isinstance(doc.get("samples"), list) else []
        n_samples = self._to_int(doc.get("n_samples"))
        sra = [
            str(r.get("targetobject"))
            for r in doc.get("extrelations") or []
            if isinstance(r, dict) and r.get("relationtype") == "SRA" and r.get("targetobject")
        ]
        ftp = str(doc.get("ftplink") or "").strip()
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "uid": doc.get("uid"),
                "accession": accession,
                "entry_type": prefix,
                "url": url,
                "organisms": taxa,
                "data_type": gds_types,
                "platforms": [f"GPL{n}" for n in self._numbers(doc.get("gpl"))]
                if prefix != "GPL"
                else [],
                "series": [f"GSE{n}" for n in self._numbers(doc.get("gse"))[:50]]
                if prefix in {"GSM", "GDS"}
                else [],
                "n_samples": n_samples if n_samples is not None else (len(samples) or None),
                "pubmed_ids": [str(p) for p in doc.get("pubmedids") or []],
                "bioproject": doc.get("bioproject") or None,
                "sra_studies": sra,
                "publication_date": doc.get("pdat") or None,
                # file *types* only (e.g. "CSV, IDAT"); nothing is downloaded by this adapter
                "supplementary_file_types": self._split(doc.get("suppfile"), ","),
                "ftp_url": ftp or None,
                "geo2r_available": {"yes": True, "no": False}.get(str(doc.get("geo2r") or "")),
                "platform_technology": doc.get("ptechtype") or None,
                "value_type": doc.get("valtype") or None,
                "subset_info": doc.get("subsetinfo") or None,
                "series_title": doc.get("seriestitle") or None,
                "platform_title": doc.get("platformtitle") or None,
                "license_note": (
                    "GEO metadata is public; submitters may assert rights over their data. "
                    "Cite the accession and the linked publication."
                ),
            }
        return concept
