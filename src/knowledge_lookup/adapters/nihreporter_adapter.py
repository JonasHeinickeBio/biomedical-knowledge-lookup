"""
NIH RePORTER Knowledge Source Adapter

NIH RePORTER (Research Portfolio Online Reporting Tools Expenditures and Results) lists
the research projects funded by NIH and other US HHS agencies (CDC, AHRQ, FDA, VA, ...)
since 1985, with abstracts, fiscal-year awards, institutes, organisations, RCDC spending
categories, indexing terms and the publications that acknowledge the grant. It is the
natural source for "who funds ME/CFS or Long COVID research and what did it produce".

API v2 (verified live, keyless, JSON; every endpoint is a POST with a JSON body)::

    POST https://api.reporter.nih.gov/v2/projects/search
         {"criteria": {...}, "include_fields": [...], "offset": 0, "limit": 50,
          "sort_field": "fiscal_year", "sort_order": "desc"}
    POST https://api.reporter.nih.gov/v2/publications/search
         {"criteria": {"core_project_nums": ["R01NS131967"]}, "offset": 0, "limit": 100}

Usage policy (from https://api.reporter.nih.gov/): at most **one request per second**; run
large jobs on weekends or 9 pm to 5 am US Eastern; NIH may block clients that ignore this.
This adapter spaces requests at least one second apart (per adapter instance) and fetches
at most a few hundred records per call. The data is a US Government work and is freely
available (no key, no stated licence restriction); acknowledge NIH RePORTER as the source.

Quirks worth knowing (they differ from what the documentation suggests):

* ``projects/search`` returns one record per *application* (one per fiscal year, plus
  supplements such as ``3U54GM104940-08S1``). The stable identity of a grant is the
  **core project number** (``R01NS131967``: activity code + institute + serial); this adapter
  makes it the concept id and merges the fiscal-year records of one grant into one concept.
* The documented ``core_project_nums`` criterion is **silently ignored** by ``projects/search``
  (it returned all 2.98 million projects). Pass the bare core number as ``project_nums``
  instead: it matches every fiscal year of that grant. Wildcards (``*R01...``) match nothing
  and malformed numbers answer HTTP 400 ``["Invalid project number"]``. ``publications/search``
  does honour ``core_project_nums``.
* Without ``include_fields`` every record carries the full ``terms`` string (6-7 KB each),
  so a trimmed field list is always sent. Field names are the CamelCase form of the
  snake_case response keys (``CoreProjectNum`` -> ``core_project_num``).
* ``spending_categories`` (RCDC ids) and ``spending_categories_desc`` (names joined by ``"; "``)
  are null for most records (typically for the running fiscal year: they are assigned after
  it closes, so the newest non-null value of the grant is used); the numeric ids are not
  guaranteed to be in the order of the names, so they are not paired. ``pref_terms`` is the ``;``-joined preferred-term list.
* ``publications/search`` returns only ``{coreproject, pmid, applid}``, no titles.
* A plain-text search combines the words with AND over title, abstract and terms
  (``search_field: "all"``); quotes make an exact phrase.
* Personal data: the API publishes principal-investigator names and organisations. Only the
  names and the contact-PI flag are kept (no profile ids, titles or program officers) and
  nothing is derived from them.
* Python's ``urllib`` stalled for ~2 minutes per request against this host while ``curl``
  and ``aiohttp`` answered in 0.2-2 s; the adapter uses the base class' aiohttp session.
"""

import asyncio
import logging
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.reporter.nih.gov/v2"
PROJECTS_URL = f"{BASE_URL}/projects/search"
PUBLICATIONS_URL = f"{BASE_URL}/publications/search"
MIN_REQUEST_INTERVAL = 1.0  # seconds; NIH asks for no more than one request per second
MAX_FETCH = 300  # records requested per search (API maximum is 500)
OVERFETCH = 3  # fiscal-year records of one grant collapse into one concept
MAX_PROJECT_RECORDS = 100  # fiscal-year/supplement applications of one grant
DEFAULT_PUBLICATION_LIMIT = 100
MAX_PUBLICATION_LIMIT = 500  # API maximum for publications/search
MAX_TERMS = 50  # indexing terms returned as relationships (a record has ~100-300)

#: Fields requested for search hits (``terms`` is left out on purpose: 6-7 KB per record).
SEARCH_FIELDS = [
    "ApplId",
    "ProjectNum",
    "CoreProjectNum",
    "ProjectTitle",
    "AbstractText",
    "FiscalYear",
    "AwardAmount",
    "Organization",
    "PrincipalInvestigators",
    "AgencyIcAdmin",
    "SpendingCategoriesDesc",
    "ProjectStartDate",
    "ProjectEndDate",
    "ProjectDetailUrl",
    "ActivityCode",
    "IsActive",
    "CovidResponse",
]
#: Detail lookups additionally fetch the structured indexing and co-funding data.
DETAIL_FIELDS = SEARCH_FIELDS + [
    "PhrText",
    "PrefTerms",
    "SpendingCategories",
    "AgencyIcFundings",
]

#: ``5R01NS131967-03`` (full) or ``R01NS131967`` (core): optional application-type digit,
#: three-character activity code, two-letter institute code, six-digit serial number and an
#: optional ``-<year><suffix>`` part (``-01A1``, ``-08S1``).
_PROJECT_RE = re.compile(r"^(\d)?([A-Z][A-Z0-9]{2})([A-Z]{2})(\d{6})(-\d{2}[A-Z0-9]*)?$")
_APPL_RE = re.compile(r"^(?:APPL(?:ID)?:?)?\s*(\d{1,9})$", re.IGNORECASE)
_FILL_FIELDS = (
    "abstract_text",
    "phr_text",
    "pref_terms",
    "spending_categories",
    "spending_categories_desc",
)
_PREFIX_RE = re.compile(r"^(?:NIHREPORTER|NIH|RePORTER):\s*", re.IGNORECASE)
_PMID_RE = re.compile(r"^(?:PMID:?)?\s*(\d{1,9})$", re.IGNORECASE)


def _clean_date(value: Any) -> str | None:
    """``2024-01-02T00:00:00`` -> ``2024-01-02``."""
    return str(value)[:10] if value else None


class NIHReporterAdapter(KnowledgeSourceAdapter):
    """Adapter for NIH RePORTER (funded research projects, keyless, ~1 request/second)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.NIHREPORTER

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str, str] | None:
        """Classify an identifier as ``("core", ...)``, ``("project", ...)`` or ``("appl", ...)``.

        Accepts the core project number (``R01NS131967``), a full project number
        (``5R01NS131967-03``), an application id (``11232343`` or ``APPL:11232343``), each
        optionally with a ``NIHREPORTER:`` prefix. Case is ignored; anything else is ``None``.
        """
        text = _PREFIX_RE.sub("", (concept_id or "").strip()).upper()
        if not text:
            return None
        match = _PROJECT_RE.match(text)
        if match:
            return ("project", text) if match.group(5) else ("core", text)
        match = _APPL_RE.match(text)
        if match:
            return ("appl", match.group(1))
        return None

    @staticmethod
    def core_of(project_num: str | None) -> str | None:
        """``5R01NS131967-03`` -> ``R01NS131967``."""
        match = _PROJECT_RE.match((project_num or "").strip().upper())
        return f"{match.group(2)}{match.group(3)}{match.group(4)}" if match else None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        """POST ``body``; ``None`` on failure or an unexpected payload (never raises)."""
        async with self._lock:
            wait = MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        try:
            data = await self._make_request(url, json_data=body)
        except Exception as e:
            logger.warning(f"NIH RePORTER request to {url.rsplit('/', 2)[-2]} failed: {e}")
            return None
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return None
        return data

    async def _search_projects(
        self, criteria: dict[str, Any], fields: list[str], limit: int, **extra: Any
    ) -> list[dict[str, Any]]:
        body = {"criteria": criteria, "include_fields": fields, "offset": 0, "limit": limit}
        body.update(extra)
        data = await self._post(PROJECTS_URL, body)
        return [r for r in data["results"] if isinstance(r, dict)] if data else []

    async def _project_records(self, concept_id: str) -> tuple[str, list[dict[str, Any]]] | None:
        """All fiscal-year records of the grant behind ``concept_id`` as ``(core, records)``.

        A core number needs one request (``project_nums`` matches every fiscal year); a full
        project number or application id needs one more to learn the core number first.
        """
        parsed = self.parse_id(concept_id)
        if parsed is None:
            return None
        kind, value = parsed
        core = value if kind == "core" else None
        if core is None:
            criteria = {"appl_ids": [int(value)]} if kind == "appl" else {"project_nums": [value]}
            first = await self._search_projects(criteria, ["CoreProjectNum", "ProjectNum"], 1)
            if not first:
                return None
            core = first[0].get("core_project_num") or self.core_of(first[0].get("project_num"))
            if not core:
                return None
        records = await self._search_projects(
            {"project_nums": [core]}, DETAIL_FIELDS, MAX_PROJECT_RECORDS
        )
        records = [r for r in records if r.get("core_project_num") == core]
        return (core, records) if records else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_projects(
        self,
        query: str,
        limit: int = 20,
        fiscal_years: list[int] | None = None,
        sort: str = "fiscal_year",
    ) -> list[UnifiedConcept]:
        """Free-text project search; one concept per grant, newest fiscal year first.

        ``query`` is searched in title, abstract and terms (words are AND-ed, quotes make a
        phrase). ``fiscal_years`` restricts to those years. ``sort`` is a RePORTER sort field
        (``fiscal_year``, ``award_amount``, ``project_start_date``...), always descending;
        use ``sort="relevance"`` for the server's own ranking.
        """
        try:
            query = (query or "").strip()
            limit = int(limit)
            if not query or limit <= 0:
                return []
            criteria: dict[str, Any] = {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": "all",
                    "search_text": query,
                }
            }
            if fiscal_years:
                criteria["fiscal_years"] = [int(y) for y in fiscal_years]
            extra: dict[str, Any] = {}
            if sort and sort != "relevance":
                extra = {"sort_field": sort, "sort_order": "desc"}
            records = await self._search_projects(
                criteria, SEARCH_FIELDS, min(max(limit * OVERFETCH, limit), MAX_FETCH), **extra
            )
            grouped: dict[str, list[dict[str, Any]]] = {}
            for record in records:
                core = record.get("core_project_num") or self.core_of(record.get("project_num"))
                if core:
                    grouped.setdefault(core, []).append(record)
            concepts = [
                c
                for core, group in grouped.items()
                if (c := self._project_to_concept(core, group)) is not None
            ]
            logger.info(f"NIH RePORTER search for '{query}' returned {len(concepts[:limit])}")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"NIH RePORTER search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search funded projects; an identifier-shaped query resolves to that project."""
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.parse_id(query) and not re.fullmatch(r"\d{1,9}", query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            return await self.search_projects(query, limit)
        except Exception as e:
            logger.error(f"NIH RePORTER search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Grant by core project number, full project number or application id.

        Lists every fiscal-year application of the grant (``applications`` in the source
        data), the latest one provides title, abstract, institute, organisation and terms.
        """
        try:
            found = await self._project_records(concept_id)
            return self._project_to_concept(*found) if found else None
        except Exception as e:
            logger.error(f"NIH RePORTER get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = DEFAULT_PUBLICATION_LIMIT
    ) -> list[dict[str, Any]]:
        """Grant -> publications, funding institutes, RCDC spending categories, terms, organisation.

        * ``has_publication`` -> ``PMID:<n>`` (``limit`` of them, default 100, from
          ``publications/search``; costs one more request);
        * ``funded_by`` -> ``NIHREPORTER:IC:<code>`` (the administering institute with
          ``administering: True`` plus co-funding institutes of the latest fiscal year);
        * ``has_spending_category`` -> ``NIHREPORTER:RCDC:<name>``;
        * ``has_term`` -> ``NIHREPORTER:TERM:<term>`` (first 50 NIH-preferred indexing terms);
        * ``conducted_at`` -> ``NIHREPORTER:ORG:<id>`` (the awardee organisation).
        """
        try:
            found = await self._project_records(concept_id)
            if not found:
                return []
            core, records = found
            latest = self._latest(records)
            relationships = self._structure_relationships(latest)
            limit = max(0, min(int(limit), MAX_PUBLICATION_LIMIT))
            if limit:
                for pmid in await self._publication_pmids(core, limit):
                    relationships.append(
                        {
                            "relation_label": "has_publication",
                            "related_id": f"PMID:{pmid}",
                            "related_name": f"PMID {pmid}",
                            "source": "NIHREPORTER",
                        }
                    )
            return relationships
        except Exception as e:
            logger.warning(f"NIH RePORTER get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Core project number -> full project numbers, application ids and PMIDs.

        ``mappingType`` is ``exact`` for the project/application numbers and ``related`` for
        publications (a paper acknowledging a grant is not the grant itself).
        """
        try:
            found = await self._project_records(concept_id)
            if not found:
                return []
            core, records = found
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(label: str, value: Any, kind: str) -> None:
                if value in (None, "") or (label, str(value)) in seen:
                    return
                seen.add((label, str(value)))
                mappings.append(
                    {
                        "fromId": core,
                        "toId": str(value),
                        "fromSource": "NIHREPORTER",
                        "toSource": label,
                        "mappingType": kind,
                        "confidence": 1.0,
                    }
                )

            for record in sorted(records, key=lambda r: r.get("fiscal_year") or 0, reverse=True):
                add("NIH_PROJECT_NUMBER", record.get("project_num"), "exact")
                add("NIH_APPLICATION_ID", record.get("appl_id"), "exact")
            for pmid in await self._publication_pmids(core, DEFAULT_PUBLICATION_LIMIT):
                add("PMID", pmid, "related")
            return mappings
        except Exception as e:
            logger.warning(f"NIH RePORTER get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    async def _publication_pmids(self, core: str, limit: int) -> list[str]:
        data = await self._post(
            PUBLICATIONS_URL,
            {"criteria": {"core_project_nums": [core]}, "offset": 0, "limit": limit},
        )
        pmids: dict[str, None] = {}
        for row in (data or {}).get("results", []):
            if isinstance(row, dict) and row.get("pmid") and row.get("coreproject") == core:
                pmids[str(row["pmid"])] = None
        return list(pmids)[:limit]

    @staticmethod
    def _latest(records: list[dict[str, Any]]) -> dict[str, Any]:
        """Representative record: newest fiscal year, the base award rather than a supplement.

        RCDC spending categories (and sometimes terms or abstracts) are filled in only after a
        fiscal year closes, so they are null on the newest record; those fields are taken from
        the newest earlier record that has them.
        """

        def key(record: dict[str, Any]) -> tuple[int, int, int]:
            is_base = not re.search(r"S\d+$", str(record.get("project_num") or ""))
            return (
                int(record.get("fiscal_year") or 0),
                int(is_base),
                int(record.get("appl_id") or 0),
            )

        ordered = sorted(records, key=key, reverse=True)
        merged = dict(ordered[0])
        for field in _FILL_FIELDS:
            if not merged.get(field):
                merged[field] = next((r[field] for r in ordered[1:] if r.get(field)), None)
        return merged

    @staticmethod
    def _categories(record: dict[str, Any]) -> list[str]:
        raw = record.get("spending_categories_desc")
        return (
            list(dict.fromkeys(p.strip() for p in str(raw).split(";") if p.strip())) if raw else []
        )

    @staticmethod
    def _terms(record: dict[str, Any]) -> list[str]:
        raw = record.get("pref_terms")
        return (
            list(dict.fromkeys(p.strip() for p in str(raw).split(";") if p.strip())) if raw else []
        )

    @staticmethod
    def _org_id(org: dict[str, Any]) -> str | None:
        return str(org.get("primary_uei") or org.get("external_org_id") or "") or None

    def _structure_relationships(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        """Edges that come from the project record itself (no extra request)."""
        edges: list[dict[str, Any]] = []
        institutes: dict[str, dict[str, Any]] = {}
        admin = record.get("agency_ic_admin") or {}
        if admin.get("code"):
            institutes[admin["code"]] = {
                "name": admin.get("name") or admin.get("abbreviation") or admin["code"],
                "abbreviation": admin.get("abbreviation"),
                "administering": True,
            }
        for funding in record.get("agency_ic_fundings") or []:
            code = funding.get("code") if isinstance(funding, dict) else None
            if code and code not in institutes:
                institutes[code] = {
                    "name": funding.get("name") or funding.get("abbreviation") or code,
                    "abbreviation": funding.get("abbreviation"),
                    "administering": False,
                }
        for code, info in institutes.items():
            edges.append(
                {
                    "relation_label": "funded_by",
                    "related_id": f"NIHREPORTER:IC:{code}",
                    "related_name": info["name"],
                    "source": "NIHREPORTER",
                    "abbreviation": info["abbreviation"],
                    "administering": info["administering"],
                }
            )
        for name in self._categories(record):
            edges.append(
                {
                    "relation_label": "has_spending_category",
                    "related_id": f"NIHREPORTER:RCDC:{name}",
                    "related_name": name,
                    "source": "NIHREPORTER",
                }
            )
        for term in self._terms(record)[:MAX_TERMS]:
            edges.append(
                {
                    "relation_label": "has_term",
                    "related_id": f"NIHREPORTER:TERM:{term}",
                    "related_name": term,
                    "source": "NIHREPORTER",
                }
            )
        org = record.get("organization") or {}
        org_id = self._org_id(org)
        if org_id and org.get("org_name"):
            edges.append(
                {
                    "relation_label": "conducted_at",
                    "related_id": f"NIHREPORTER:ORG:{org_id}",
                    "related_name": org["org_name"],
                    "source": "NIHREPORTER",
                }
            )
        return edges

    def _project_to_concept(
        self, core: str, records: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        """Merge the fiscal-year records of one grant into a ``UnifiedConcept`` (type STUDY).

        ``STUDY`` is the closest ``ConceptType`` for a funded research project; the grant is
        not itself a clinical study or a publication.
        """
        try:
            if not records:
                return None
            record = self._latest(records)
            title = (record.get("project_title") or "").strip()
            if not title:
                return None
            concept = self._create_concept(core, title, ConceptType.STUDY)
            appl_id = record.get("appl_id")
            url = record.get("project_detail_url")
            if appl_id:
                concept.add_identifier(KnowledgeSource.NIHREPORTER, f"APPL:{appl_id}", title, url)
            for text in (record.get("abstract_text"), record.get("phr_text")):
                if text and concept.definitions is not None and str(text).strip():
                    concept.definitions.append(str(text).strip())
            institute = record.get("agency_ic_admin") or {}
            org = record.get("organization") or {}
            categories = self._categories(record)
            if concept.semantic_types is not None and record.get("activity_code"):
                concept.semantic_types.append(str(record["activity_code"]))
            if concept.categories is not None:
                if record.get("fiscal_year"):
                    concept.categories.append(f"fiscal_year:{record['fiscal_year']}")
                if institute.get("abbreviation"):
                    concept.categories.append(f"institute:{institute['abbreviation']}")
                concept.categories.extend(f"rcdc:{c}" for c in categories)
            concept.confidence_score = 0.85
            applications = [
                {
                    "appl_id": r.get("appl_id"),
                    "project_num": r.get("project_num"),
                    "fiscal_year": r.get("fiscal_year"),
                    "award_amount": r.get("award_amount"),
                }
                for r in sorted(records, key=lambda r: r.get("fiscal_year") or 0, reverse=True)
            ]
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.NIHREPORTER] = {
                    "core_project_num": core,
                    "project_num": record.get("project_num"),
                    "appl_id": appl_id,
                    "fiscal_year": record.get("fiscal_year"),
                    "award_amount": record.get("award_amount"),
                    "is_active": record.get("is_active"),
                    "activity_code": record.get("activity_code"),
                    "project_start_date": _clean_date(record.get("project_start_date")),
                    "project_end_date": _clean_date(record.get("project_end_date")),
                    "institute": {
                        "code": institute.get("code"),
                        "abbreviation": institute.get("abbreviation"),
                        "name": institute.get("name"),
                    },
                    "organization": {
                        "name": org.get("org_name"),
                        "city": org.get("org_city"),
                        "state": org.get("org_state"),
                        "country": org.get("org_country"),
                        "department_type": org.get("dept_type"),
                    },
                    # names as published by RePORTER; no ids, titles or derived data
                    "principal_investigators": [
                        {
                            "name": " ".join(str(p.get("full_name") or "").split()),
                            "is_contact_pi": bool(p.get("is_contact_pi")),
                        }
                        for p in record.get("principal_investigators") or []
                        if isinstance(p, dict) and p.get("full_name")
                    ],
                    "spending_categories": categories,
                    "spending_category_ids": record.get("spending_categories") or [],
                    "terms": self._terms(record),
                    "covid_response": record.get("covid_response"),
                    "applications": applications,
                    "url": url,
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting NIH RePORTER project: {e}")
            return None
