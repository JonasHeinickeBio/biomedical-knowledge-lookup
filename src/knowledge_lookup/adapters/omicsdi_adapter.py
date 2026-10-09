"""
OmicsDI Knowledge Source Adapter

OmicsDI (Omics Discovery Index, EMBL-EBI) is a metadata index over ~29 public omics
repositories (4.9 million datasets in 2026-10): GEO, ArrayExpress / BioStudies, ENA,
PRIDE, MassIVE, jPOST, iProX, PeptideAtlas, MetaboLights, Metabolomics Workbench, GNPS,
EGA, dbGaP, BioModels and more. It lets a researcher *find* transcriptomics, proteomics,
metabolomics and microbiome (ENA) datasets for a disease such as ME/CFS or Long COVID
with one query. This adapter returns dataset **metadata and URLs only**; it never
downloads data files.

Licence / terms: OmicsDI is a free EMBL-EBI service, the index metadata is open (EMBL-EBI
terms of use apply); each dataset keeps the licence of its source repository, which is
what the returned ``full_dataset_link`` leads to. Credit the original repository.

API (verified live 2026-10-09, keyless, JSON)::

    GET /ws/dataset/search?query=<lucene>&size=<n>&start=<offset>
    GET /ws/dataset/get?accession=<acc>&database=<source>
    GET /ws/dataset/getSimilar?accession=<acc>&database=<source>
    GET /ws/database/all           (the 29 repositories and their ``source`` keys)

Quirks worth knowing (several differ from the public Swagger / the older docs):

* ``dataset/get`` and ``getSimilar`` take ``accession=`` (not ``acc=``, which answers HTTP
  400 "Required parameter 'accession' is not present"). ``database`` is the ``source`` string
  of a search hit (``geo``, ``pride``, ``biostudies-arrayexpress``, ``metabolights_dataset``,
  ``metabolomics_workbench``, ``massive``...), case-insensitive.
* The query is Lucene. Unquoted words are OR-ed (``chronic fatigue`` finds 3,315 datasets,
  most only mention one word) so multi-word text is sent as a quoted phrase by default.
  Facet filters are plain ``AND`` clauses and *do* filter: ``omics_type:"Proteomics"``,
  ``TAXONOMY:9606``, ``repository:"pride"``, ``disease:"..."``, ``tissue:"..."``.
  ``repository`` uses facet spellings that differ from ``source`` (``MetaboLights`` vs
  ``metabolights_dataset``).
* ``sortfield`` is unusable: ``sortfield=publication_date`` answers 404 and ``sortfield=id``
  silently switches to AND semantics (92 instead of 3,315 hits), so results stay in
  relevance order.
* The service is flaky. A slow request (30-40 s seen) ends in HTTP 404 ``Not Found``
  and the same URL then keeps answering 404 for a while; a query with no hit can also
  answer 404 instead of ``count: 0``. The adapter therefore treats a 404 from ``search`` as
  "no result" and sets a 60 s timeout floor; typical latency is 0.1-1 s.
* ``dataset/get`` cannot resolve ENA records (``source: project``, accession ``PRJ...``): it
  answers 404 although search lists them. :meth:`get_concept_details` then falls back to the
  search hit for the accession.
* ``publicationDate`` mixes ``20150608``, ``2015-06-08``, ``2009/05/12`` and a
  ``Date.toString()`` form; the adapter normalises to ``YYYY-MM-DD``.
* For ArrayExpress (``biostudies-arrayexpress``) records the detail's ``omics_type`` lists
  all five types (a catch-all); the adapter then reports no omics type rather than a wrong
  one (search hits carry the correct single type).
* The detail record contains submitter names and e-mail addresses (``submitterMail``,
  ``labHeadMail``). They are deliberately **not** copied into concepts.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._omics_common import (
    RequestThrottle,
    dedupe,
    iso_date,
    mapping,
    relationship,
    strip_html,
    taxon_id,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.omicsdi.org/ws"
SEARCH_URL = f"{BASE_URL}/dataset/search"
GET_URL = f"{BASE_URL}/dataset/get"
SIMILAR_URL = f"{BASE_URL}/dataset/getSimilar"
WEB_URL = "https://www.omicsdi.org/dataset/{database}/{accession}"
SOURCE_NAME = "OMICSDI"

PAGE_SIZE = 100  # the server accepts up to 500 per page; 100 keeps responses ~100 KB
MAX_RESULTS = 100  # cap for one search call
SIMILAR_CAP = 10  # getSimilar returns ~14 scored datasets, mirrors included
ENTITY_CAP = 50

#: ``source`` keys of ``/ws/database/all`` (2026-10-09) plus ``iprox``, which search hits use.
KNOWN_DATABASES: frozenset[str] = frozenset(
    {
        "peptide_atlas",
        "node",
        "metabolomics_workbench",
        "ncbi",
        "gnps",
        "paxdb",
        "project",
        "lincs",
        "pride",
        "geo",
        "jpost",
        "dbgap",
        "cellcollective",
        "metabolights_dataset",
        "eva",
        "atlas-experiments",
        "ega",
        "massive",
        "physiome",
        "fairdomhub",
        "iprox",
        "ecrin-mdr-crc",
        "biostudies-literature",
        "bioimages",
        "biostudies-arrayexpress",
        "biostudies-other",
        "biomodels",
        "panorama",
        "gpmdb",
    }
)
#: Friendly spellings accepted in identifiers and the ``repository`` filter.
DATABASE_ALIASES: dict[str, str] = {
    "arrayexpress": "biostudies-arrayexpress",
    "biostudies": "biostudies-arrayexpress",
    "metabolights": "metabolights_dataset",
    "metabolomicsworkbench": "metabolomics_workbench",
    "ena": "project",
    "expressionatlas": "atlas-experiments",
    "peptideatlas": "peptide_atlas",
    "gse": "geo",
}
#: ``source`` -> spelling of the ``repository`` facet (only where it differs; verified live).
REPOSITORY_FACET: dict[str, str] = {
    "metabolights_dataset": "MetaboLights",
    "metabolomics_workbench": "MetabolomicsWorkbench",
    "massive": "MassIVE",
    "project": "ENA",
    "ega": "EGA",
    "dbgap": "dbGaP",
    "gnps": "GNPS",
    "biomodels": "BioModels",
}
#: Accession shapes of bare identifiers -> ``source``.
_ACCESSION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^GSE\d+$", re.IGNORECASE), "geo"),
    (re.compile(r"^(?:PXD|PAD|RPXD)\d+$", re.IGNORECASE), "pride"),
    (re.compile(r"^MSV\d+$", re.IGNORECASE), "massive"),
    (re.compile(r"^MTBLS\d+$", re.IGNORECASE), "metabolights_dataset"),
    (re.compile(r"^ST\d{6}$", re.IGNORECASE), "metabolomics_workbench"),
    (re.compile(r"^E-[A-Z0-9]+-\d+$", re.IGNORECASE), "biostudies-arrayexpress"),
    (re.compile(r"^S-EPMC\d+$", re.IGNORECASE), "biostudies-literature"),
    (re.compile(r"^EGAS\d+$", re.IGNORECASE), "ega"),
    (re.compile(r"^phs\d+(?:\.v\d+\.p\d+)?$", re.IGNORECASE), "dbgap"),
    (re.compile(r"^JPST\d+$", re.IGNORECASE), "jpost"),
    (re.compile(r"^PASS\d+$", re.IGNORECASE), "peptide_atlas"),
    (re.compile(r"^(?:BIOMD|MODEL)\d+$", re.IGNORECASE), "biomodels"),
    (re.compile(r"^PRJ[EDN][A-Z]\d+$", re.IGNORECASE), "project"),
)
_REPOSITORY_BY_PREFIX: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^PRJ[EDN][A-Z]\d+$", re.IGNORECASE), "BioProject"),
    (re.compile(r"^(?:PXD|PAD)\d+$", re.IGNORECASE), "PRIDE"),
    (re.compile(r"^GSE\d+$", re.IGNORECASE), "GEO"),
    (re.compile(r"^E-[A-Z0-9]+-\d+$", re.IGNORECASE), "ArrayExpress"),
)
#: ``omics_type`` facet spellings (case-insensitive input is canonicalised).
OMICS_TYPES: tuple[str, ...] = (
    "Genomics",
    "Transcriptomics",
    "Proteomics",
    "Metabolomics",
    "Multiomics",
    "Methylation profiling",
    "Clinical",
    "Models",
    "Microarray",
    "Other",
    "Unknown",
)
_OMICS_BY_KEY = {t.lower(): t for t in OMICS_TYPES}

#: ``filters`` keys accepted by :meth:`search_datasets` -> Lucene field.
FILTER_FIELDS: dict[str, str] = {
    "omics_type": "omics_type",
    "omics": "omics_type",
    "organism": "TAXONOMY",
    "taxonomy": "TAXONOMY",
    "repository": "repository",
    "database": "repository",
    "disease": "disease",
    "tissue": "tissue",
}
_LUCENE_SYNTAX_RE = re.compile(r'["():]|\b(?:AND|OR|NOT)\b')
_PMID_RE = re.compile(r"^\d{1,9}$")
#: ``getSimilar`` returns ``(count, datasets)`` hits shaped like search hits.
_COUNT_KEYS = (
    ("citations", "citationsCount"),
    ("connections", "connectionsCount"),
    ("reanalyses", "reanalysisCount"),
    ("views", "viewsCount"),
    ("downloads", "downloadCount"),
)


def _names(value: Any) -> list[str]:
    """Names from ``["a"]`` or ``[{"acc": "", "name": "a"}]``; anything else gives ``[]``."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return dedupe(out)


def _quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


def _is_not_found(exc: Exception) -> bool:
    return getattr(exc, "status", None) == 404


class OmicsDIAdapter(KnowledgeSourceAdapter):
    """Adapter for OmicsDI omics dataset discovery (keyless, metadata only)."""

    #: a slow request runs 30-40 s before the server gives up; do not cut it off and retry.
    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self._throttle = RequestThrottle()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OMICSDI

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier and query helpers
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_database(name: str) -> str | None:
        """``GEO`` / ``arrayexpress`` / ``metabolights`` -> the ``source`` key, else ``None``."""
        key = (name or "").strip().lower()
        key = DATABASE_ALIASES.get(key, key)
        return key if key in KNOWN_DATABASES else None

    @classmethod
    def normalize_id(cls, concept_id: str) -> tuple[str, str] | None:
        """``geo:GSE16059`` / ``OMICSDI:pride:PXD076216`` / bare ``MTBLS161`` -> (database, accession).

        A bare accession is mapped to its repository by shape (GSE, PXD, MSV, MTBLS, ST######,
        E-XXXX-n, PRJ...). ``None`` for anything else (e.g. ``PMID:123``).
        """
        text = (concept_id or "").strip()
        if text.upper().startswith("OMICSDI:"):
            text = text[len("OMICSDI:") :]
        if ":" in text:
            left, right = text.split(":", 1)
            database = cls.resolve_database(left)
            if database and right.strip():
                return database, right.strip()
        for pattern, database in _ACCESSION_PATTERNS:
            if pattern.match(text):
                return database, text
        return None

    @staticmethod
    def build_query(query: str, filters: dict[str, Any] | None = None, phrase: bool = True) -> str:
        """Turn free text plus ``filters`` into OmicsDI's Lucene syntax.

        With ``phrase=True`` (default) multi-word text, or text with ``/`` or ``-``
        (``ME/CFS``), is sent as one quoted phrase because the server otherwise ORs the
        words. Text that already uses quotes, ``AND``/``OR``/``NOT``, parentheses or
        ``field:value`` is passed through unchanged. ``filters`` accepts ``omics_type``,
        ``organism`` (taxonomy id or common name), ``repository``, ``disease`` and ``tissue``
        (string or list, OR-ed); unknown keys are ignored.
        """
        text = (query or "").strip()
        if text and phrase and not _LUCENE_SYNTAX_RE.search(text):
            if re.search(r"[\s/\-]", text):
                text = _quote(text)
        parts = [text] if text else []
        for key, value in (filters or {}).items():
            field = FILTER_FIELDS.get(str(key).lower())
            if field is None or value in (None, "", []):
                continue
            values = [value] if isinstance(value, str) else list(value)
            clauses = []
            for item in values:
                item_text = str(item).strip() if item is not None else ""
                if not item_text:
                    continue
                if field == "omics_type":
                    item_text = _OMICS_BY_KEY.get(item_text.lower(), item_text)
                elif field == "TAXONOMY":
                    tax = taxon_id(item_text)
                    if tax is None:
                        continue
                    clauses.append(f"TAXONOMY:{tax}")
                    continue
                elif field == "repository":
                    database = OmicsDIAdapter.resolve_database(item_text)
                    item_text = REPOSITORY_FACET.get(database or "", database or item_text)
                clauses.append(f"{field}:{_quote(item_text)}")
            if clauses:
                parts.append(f"({' OR '.join(clauses)})" if len(clauses) > 1 else clauses[0])
        return " AND ".join(parts)

    async def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Throttled GET; ``None`` on any failure. A 404 means "no hit" here (see module doc)."""
        await self._throttle.wait()
        try:
            data = await self._make_request(url, params=params)
        except Exception as e:
            if _is_not_found(e):
                logger.info(f"OmicsDI {url} answered 404 for {params} (no hit or backend timeout)")
            else:
                logger.warning(f"OmicsDI request failed for {url} {params}: {e}")
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_datasets(
        self,
        query: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        phrase: bool = True,
    ) -> list[UnifiedConcept]:
        """Search datasets (relevance order, at most 100 per call).

        ``filters`` narrow the result by ``omics_type`` (``Transcriptomics``, ``Proteomics``,
        ``Metabolomics``, ``Genomics``...), ``organism`` (``9606`` or ``human``),
        ``repository`` (``geo``, ``pride``, ``arrayexpress``...), ``disease`` and ``tissue``.
        Microbiome studies live under ``Genomics`` (ENA, ``repository="ena"``).
        """
        try:
            limit = max(0, min(int(limit), MAX_RESULTS))
            text = self.build_query(query, filters, phrase)
            if not text or limit == 0:
                return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            start = 0
            while len(concepts) < limit:
                size = min(PAGE_SIZE, limit - len(concepts))
                data = await self._request(
                    SEARCH_URL, {"query": text, "size": size, "start": start}
                )
                hits = data.get("datasets") if data else None
                if not isinstance(hits, list) or not hits:
                    break
                added = 0
                for hit in hits:
                    concept = self._hit_to_concept(hit)
                    if concept is not None and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
                        added += 1
                start += len(hits)
                if not added or len(hits) < size:
                    break
            logger.info(f"OmicsDI search for '{text}' returned {len(concepts[:limit])} datasets")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"OmicsDI search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Free-text dataset search; a dataset accession (``geo:GSE16059``, ``PXD076216``)
        resolves to that one dataset."""
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.normalize_id(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            return await self.search_datasets(query, limit)
        except Exception as e:
            logger.error(f"OmicsDI search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Dataset by ``<database>:<accession>`` or a bare accession.

        Uses ``dataset/get``; ENA projects (not served by that endpoint) are rebuilt from
        the search hit for the accession, so they carry fewer fields (no PMIDs/tissues).
        """
        try:
            parsed = self.normalize_id(concept_id)
            if parsed is None:
                return None
            record = await self._load_record(*parsed)
            return self._record_to_concept(record) if record else None
        except Exception as e:
            logger.error(f"OmicsDI get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Dataset -> publications, organisms, diseases, tissues, omics types, instruments
        and similar datasets.

        Labels: ``has_publication`` (``PMID:n``), ``has_organism`` (``NCBITaxon:n`` when the
        id is known), ``has_disease``, ``has_tissue``, ``has_omics_type``, ``uses_instrument``
        (each capped at 50) and ``similar_to`` (at most 10, with the OmicsDI similarity
        ``score``; mirror records of the same study in another repository appear here).
        """
        try:
            parsed = self.normalize_id(concept_id)
            if parsed is None:
                return []
            record = await self._load_record(*parsed)
            if record is None:
                return []
            relations = self._record_relationships(record)
            data = await self._request(
                SIMILAR_URL, {"accession": record["accession"], "database": record["database"]}
            )
            hits = data.get("datasets") if data else None
            self_id = record["primary_id"]
            seen: set[str] = set()
            for hit in hits if isinstance(hits, list) else []:
                norm = self._normalise(hit)
                if norm is None or norm["primary_id"] in (self_id, *seen):
                    continue
                if len(seen) >= SIMILAR_CAP:
                    break
                seen.add(norm["primary_id"])
                score = hit.get("score")
                try:
                    score = round(float(score), 3) if score is not None else None
                except (TypeError, ValueError):
                    score = None
                relations.append(
                    relationship(
                        "similar_to",
                        norm["primary_id"],
                        norm["title"],
                        SOURCE_NAME,
                        score=score,
                        repository=norm["database"],
                    )
                )
            return relations
        except Exception as e:
            logger.warning(f"OmicsDI get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Dataset -> repository accession, secondary accessions (BioProject...), PMIDs and
        NCBI Taxonomy ids."""
        try:
            parsed = self.normalize_id(concept_id)
            if parsed is None:
                return []
            record = await self._load_record(*parsed)
            if record is None:
                return []
            from_id = record["primary_id"]
            mappings = [
                mapping(from_id, record["accession"], SOURCE_NAME, record["repository"], "exact")
            ]
            for acc in record["secondary_accessions"]:
                mappings.append(
                    mapping(from_id, acc, SOURCE_NAME, self._accession_source(acc), "related", 0.9)
                )
            for pmid in record["pmids"]:
                mappings.append(mapping(from_id, pmid, SOURCE_NAME, "PubMed", "related", 0.9))
            for tax in dedupe(record["taxon_ids"]):
                mappings.append(mapping(from_id, tax, SOURCE_NAME, "NCBITaxon", "related", 0.9))
            return mappings
        except Exception as e:
            logger.warning(f"OmicsDI get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    async def _load_record(self, database: str, accession: str) -> dict[str, Any] | None:
        """Normalised record from ``dataset/get``, or from a search hit when get has none."""
        data = await self._request(GET_URL, {"accession": accession, "database": database})
        if data and data.get("id"):
            record = self._normalise(data)
            if record is not None:
                return record
        found = await self._request(
            SEARCH_URL, {"query": _quote(accession), "size": 5, "start": 0}
        )
        for hit in (found or {}).get("datasets") or []:
            if (
                isinstance(hit, dict)
                and str(hit.get("id", "")).upper() == accession.upper()
                and (hit.get("source") or "").lower() == database
            ):
                return self._normalise(hit)
        return None

    @staticmethod
    def _accession_source(accession: str) -> str:
        for pattern, name in _REPOSITORY_BY_PREFIX:
            if pattern.match(accession):
                return name
        return "secondary_accession"

    @staticmethod
    def _normalise(item: dict[str, Any]) -> dict[str, Any] | None:
        """Common shape for search hits and ``dataset/get`` records (no personal data)."""
        accession = str(item.get("id") or "").strip()
        database = str(item.get("source") or "").strip().lower()
        if not accession or not database:
            return None
        title = strip_html(item.get("title") or item.get("name")) or accession
        organisms = _names(item.get("organisms"))
        omics = _names(item.get("omics_type") or item.get("omicsType"))
        omics_raw: list[str] = []
        if database.startswith("biostudies-") and len(omics) >= 4:
            omics_raw, omics = omics, []  # catch-all list on ArrayExpress details
        dates = item.get("dates") if isinstance(item.get("dates"), dict) else {}
        published = iso_date(item.get("publicationDate"))
        if published is None:
            for key in ("publication", "release"):
                for value in (dates or {}).get(key) or []:
                    published = iso_date(value)
                    if published:
                        break
                if published:
                    break
        repositories = _names(item.get("repositories"))
        counts = {label: item[key] for label, key in _COUNT_KEYS if isinstance(item.get(key), int)}
        pmids = [
            str(p).strip()
            for p in item.get("publicationIds") or []
            if _PMID_RE.match(str(p).strip())
        ]
        return {
            "primary_id": f"{database}:{accession}",
            "accession": accession,
            "database": database,
            "repository": repositories[0] if repositories else database,
            "title": title,
            "description": strip_html(item.get("description")),
            "organisms": organisms,
            "taxon_ids": dedupe([t for t in (taxon_id(o) for o in organisms) if t]),
            "omics_types": omics,
            "omics_types_raw": omics_raw,
            "publication_date": published,
            "pmids": dedupe(pmids),
            "instruments": _names(item.get("instruments")),
            "experiment_types": _names(item.get("experimentType")),
            "tissues": _names(item.get("tissues")),
            "diseases": _names(item.get("diseases")),
            "organizations": _names(item.get("organization")),
            "secondary_accessions": _names(item.get("secondary_accession")),
            "status": item.get("currentStatus"),
            "url": item.get("full_dataset_link")
            or WEB_URL.format(database=database, accession=accession),
            "omicsdi_url": WEB_URL.format(database=database, accession=accession),
            "counts": counts,
        }

    def _hit_to_concept(self, hit: Any) -> UnifiedConcept | None:
        if not isinstance(hit, dict):
            return None
        record = self._normalise(hit)
        return self._record_to_concept(record) if record else None

    def _record_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a normalised record to a ``UnifiedConcept`` (type STUDY)."""
        try:
            concept = self._create_concept(
                record["primary_id"], record["title"], ConceptType.STUDY
            )
            if record["description"]:
                concept.definitions = [record["description"]]
            categories = [f"repository:{record['repository']}"]
            categories += [f"omics:{t}" for t in record["omics_types"]]
            categories += [f"organism:{o}" for o in record["organisms"]]
            categories += [f"disease:{d}" for d in record["diseases"]]
            categories += [f"tissue:{t}" for t in record["tissues"]]
            if record["publication_date"]:
                categories.append(f"year:{record['publication_date'][:4]}")
            concept.categories = dedupe(categories)
            concept.semantic_types = list(record["omics_types"])
            # the same accession is a record in the sibling adapter's source
            if record["database"] == "pride":
                concept.add_identifier(
                    KnowledgeSource.PRIDE,
                    record["accession"],
                    record["title"],
                    f"https://www.ebi.ac.uk/pride/archive/projects/{record['accession']}",
                )
            elif record["database"] == "biostudies-arrayexpress":
                concept.add_identifier(
                    KnowledgeSource.BIOSTUDIES,
                    record["accession"],
                    record["title"],
                    f"https://www.ebi.ac.uk/biostudies/studies/{record['accession']}",
                )
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OMICSDI] = {
                    key: record[key]
                    for key in (
                        "accession",
                        "database",
                        "repository",
                        "title",
                        "organisms",
                        "taxon_ids",
                        "omics_types",
                        "omics_types_raw",
                        "publication_date",
                        "pmids",
                        "instruments",
                        "experiment_types",
                        "tissues",
                        "diseases",
                        "organizations",
                        "secondary_accessions",
                        "status",
                        "url",
                        "omicsdi_url",
                        "counts",
                    )
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting OmicsDI record: {e}")
            return None

    @staticmethod
    def _record_relationships(record: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for pmid in record["pmids"][:ENTITY_CAP]:
            out.append(
                relationship("has_publication", f"PMID:{pmid}", f"PubMed {pmid}", SOURCE_NAME)
            )
        for name in record["organisms"][:ENTITY_CAP]:
            tax = taxon_id(name)
            out.append(
                relationship(
                    "has_organism",
                    f"NCBITaxon:{tax}" if tax else f"OMICSDI:ORGANISM:{name}",
                    name,
                    SOURCE_NAME,
                )
            )
        for label, key, prefix in (
            ("has_disease", "diseases", "DISEASE"),
            ("has_tissue", "tissues", "TISSUE"),
            ("has_omics_type", "omics_types", "OMICS_TYPE"),
            ("uses_instrument", "instruments", "INSTRUMENT"),
        ):
            for name in record[key][:ENTITY_CAP]:
                out.append(relationship(label, f"OMICSDI:{prefix}:{name}", name, SOURCE_NAME))
        return out
