"""
PRIDE Knowledge Source Adapter

PRIDE Archive (EMBL-EBI) is the ProteomeXchange member for mass-spectrometry proteomics:
every project has a ``PXD`` accession (``PAD`` for affinity-proteomics projects), species,
tissues ("organism parts"), diseases, instruments, identified modifications and the
publication that describes it. The adapter lets you *find* proteomics datasets, for example
cerebrospinal-fluid or plasma proteomes of ME/CFS and Long COVID patients, and returns
project **metadata and URLs only**: raw/result files are never downloaded, only their count
is reported.

Licence / terms: metadata is open under the EMBL-EBI terms of use; each project states its
data licence (``license`` field, often CC0 or "EBI terms of use"). No key and no documented
rate limit; the adapter stays below 2 requests per second.

API (verified live 2026-10-09, keyless, JSON, Swagger at
``https://www.ebi.ac.uk/pride/ws/archive/v2/swagger-ui.html``)::

    GET /pride/ws/archive/v2/search/projects?keyword=&pageSize=&page=&sortConditions=&sortDirection=&filter=
    GET /pride/ws/archive/v2/projects/<accession>
    GET /pride/ws/archive/v2/projects/<accession>/files?pageSize=1&page=0   (count only)

Quirks worth knowing:

* **``projects?keyword=`` ignores the keyword**: it just lists projects (``keyword=zzzqqq``
  returns the same 5 as ``keyword=fatigue``). The working keyword search is
  ``search/projects`` (a nonsense keyword answers ``[ ]``). ``page`` is 0-based.
* ``search/projects`` returns a bare JSON array; the total is in the ``total_records``
  response header. Terms are plain strings there (``"organisms": ["Homo sapiens (human)"]``),
  while ``projects/<accession>`` returns CV terms with ontology accessions
  (``NEWT:9606``, ``BTO:0000237``, ``DOID:8544``, ``MS:1001911``, ``MOD:00394``). Taxonomy
  ids and CV ids in relationships/mappings therefore need the detail call.
* ``filter`` takes ``field==value`` pairs joined by commas; the field names that work are
  ``organisms``, ``diseases`` and ``organismsPart`` (``diseases==Chronic fatigue syndrome``,
  value case-sensitive as shown by the results). The documented ``*_facet`` names are silently
  ignored (the filter then does nothing).
* ``sortConditions`` accepts ``submissionDate`` or ``publicationDate`` with
  ``sortDirection=ASC|DESC``; other values (``downloadCount``) are ignored. Without it the
  newest projects come first. ``publicationDate`` can fall months after ``submissionDate``
  (embargo-style release dates), so it is not the day the data were submitted.
* Search hits include ``references`` as ``"<citation>--pubMed:<id>--doi: <doi>"`` strings
  (``pubMed:0`` = none); details give ``{"pubmedID", "doi"}`` objects.
* The raw project record contains submitter and lab-head names, e-mail addresses and ORCIDs.
  They are deliberately **not** copied into concepts, fixtures or relationships; only the
  institutional ``affiliations`` and ``countries`` are kept.
* A missing accession answers HTTP 404 with a plain-text message.
"""

from __future__ import annotations

import json
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

BASE_URL = "https://www.ebi.ac.uk/pride/ws/archive/v2"
SEARCH_URL = f"{BASE_URL}/search/projects"
PROJECT_URL = f"{BASE_URL}/projects/{{accession}}"
FILES_URL = f"{BASE_URL}/projects/{{accession}}/files"
WEB_URL = "https://www.ebi.ac.uk/pride/archive/projects/{accession}"
SOURCE_NAME = "PRIDE"

PAGE_SIZE = 100
MAX_RESULTS = 100
ENTITY_CAP = 50

_ACCESSION_RE = re.compile(r"^(?:PRIDE:)?((?:R?PXD|PAD)\d{4,})$", re.IGNORECASE)
_PMID_IN_REF_RE = re.compile(r"pubMed:(\d+)", re.IGNORECASE)
_DOI_IN_REF_RE = re.compile(r"doi:\s*(10\.\S+)", re.IGNORECASE)
SORT_FIELDS = {"submission_date": "submissionDate", "publication_date": "publicationDate"}
#: ``filters`` keys for :meth:`search_projects` -> PRIDE filter field (verified live).
FILTER_FIELDS = {
    "species": "organisms",
    "organism": "organisms",
    "organisms": "organisms",
    "disease": "diseases",
    "diseases": "diseases",
    "tissue": "organismsPart",
    "organism_part": "organismsPart",
    "organismspart": "organismsPart",
}


def _terms(value: Any) -> list[dict[str, str | None]]:
    """Normalise CV terms: ``["a"]`` (search) or ``[{"name","accession"}]`` (detail)."""
    out: list[dict[str, str | None]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict):
            name = item.get("name")
            acc = item.get("accession")
        else:
            name, acc = item, None
        if isinstance(name, str) and name.strip():
            out.append({"name": name.strip(), "id": str(acc).strip() if acc else None})
    seen: set[str] = set()
    unique = []
    for term in out:
        key = str(term["name"]).lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return unique


def _strings(value: Any) -> list[str]:
    return (
        dedupe([v.strip() for v in value if isinstance(v, str)]) if isinstance(value, list) else []
    )


def _cv_id(term: dict[str, str | None]) -> str | None:
    """``NEWT:9606`` -> ``NCBITaxon:9606``; other CV accessions are kept as given."""
    acc = term["id"]
    if acc and acc.upper().startswith("NEWT:"):
        return "NCBITaxon:" + acc.split(":", 1)[1]
    return acc


class PRIDEAdapter(KnowledgeSourceAdapter):
    """Adapter for the PRIDE Archive proteomics projects (keyless, metadata only)."""

    def __init__(self, config):
        super().__init__(config)
        self._throttle = RequestThrottle()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.PRIDE

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier and request helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_accession(concept_id: str) -> str | None:
        """``PXD076216`` / ``PRIDE:PXD076216`` / ``pxd076216`` / ``PAD000026`` -> upper case."""
        match = _ACCESSION_RE.match((concept_id or "").strip())
        return match.group(1).upper() if match else None

    @staticmethod
    def build_filter(filters: dict[str, Any] | None) -> str | None:
        """``{"disease": "Chronic fatigue syndrome"}`` -> ``diseases==Chronic fatigue syndrome``.

        Keys: ``species``, ``disease``, ``tissue``. Several keys are AND-ed by PRIDE;
        a list value uses its first entry (the API has no OR syntax). Unknown keys are ignored.
        """
        parts = []
        for key, value in (filters or {}).items():
            field = FILTER_FIELDS.get(str(key).lower())
            if isinstance(value, list | tuple):
                value = value[0] if value else None
            if field and value not in (None, ""):
                parts.append(f"{field}=={str(value).strip()}")
        return ",".join(parts) or None

    async def _request(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any] | None:
        """Throttled GET; ``None`` on any failure (404 = unknown project).

        The body is parsed here rather than by ``_make_request``: ``projects/<acc>`` answers
        ``Content-Type: text/plain`` (valid JSON inside), which aiohttp's ``json()`` refuses.
        """
        await self._throttle.wait()
        try:
            text = await self._make_request_text(
                url, params=params, headers={"Accept": "application/json"}
            )
            data = json.loads(text)
        except Exception as e:
            if getattr(e, "status", None) == 404:
                logger.info(f"PRIDE {url} answered 404")
            else:
                logger.warning(f"PRIDE request failed for {url}: {e}")
            return None
        return data

    async def _file_count(self, accession: str) -> int | None:
        """Number of project files from the ``total_records`` header of a 1-row listing.

        Only the count is read; the single returned row (a file name and FTP location,
        ~1 KB) is discarded and no file is downloaded.
        """

        async def _do() -> int | None:
            session = await self._get_session()
            async with session.get(
                FILES_URL.format(accession=accession),
                params={"pageSize": 1, "page": 0},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "AID-PAIS-Knowledge-Lookup/1.0",
                },
            ) as response:
                response.raise_for_status()
                total = response.headers.get("total_records", "")
                return int(total) if total.isdigit() else None

        await self._throttle.wait()
        try:
            result = await self._call_with_retry("pride_file_count", _do)
            return result if isinstance(result, int) else None
        except Exception as e:
            logger.info(f"PRIDE file count unavailable for {accession}: {e}")
            return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_projects(
        self,
        query: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        sort: str = "relevance",
        descending: bool = True,
    ) -> list[UnifiedConcept]:
        """Keyword search over PRIDE projects (0-based pages of up to 100, at most 100 results).

        ``filters`` accepts ``species``, ``disease`` and ``tissue`` (exact values as they
        appear in results, e.g. ``"Chronic fatigue syndrome"``, ``"Blood plasma"``).
        ``sort`` is ``relevance`` (newest first when scores tie), ``submission_date`` or
        ``publication_date``.
        """
        try:
            limit = max(0, min(int(limit), MAX_RESULTS))
            keyword = (query or "").strip()
            if not keyword or limit == 0:
                return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            page = 0
            while len(concepts) < limit:
                size = min(PAGE_SIZE, limit)  # constant: ``page`` is a page number, not an offset
                params: dict[str, Any] = {"keyword": keyword, "pageSize": size, "page": page}
                flt = self.build_filter(filters)
                if flt:
                    params["filter"] = flt
                if sort in SORT_FIELDS:
                    params["sortConditions"] = SORT_FIELDS[sort]
                    params["sortDirection"] = "DESC" if descending else "ASC"
                data = await self._request(SEARCH_URL, params)
                if not isinstance(data, list) or not data:
                    break
                added = 0
                for item in data:
                    concept = self._hit_to_concept(item)
                    if concept is not None and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
                        added += 1
                if not added or len(data) < size:
                    break
                page += 1
            logger.info(f"PRIDE search for '{keyword}' returned {len(concepts[:limit])} projects")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"PRIDE search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Keyword search; a PXD/PAD accession resolves to that one project."""
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.normalize_accession(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            return await self.search_projects(query, limit)
        except Exception as e:
            logger.error(f"PRIDE search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Project by accession: CV-annotated species/tissues/diseases/instruments/modifications,
        publications, licence and file count (one extra 1-row request)."""
        try:
            record = await self._load_record(concept_id)
            if record is None:
                return None
            record["files_count"] = await self._file_count(record["accession"])
            return self._record_to_concept(record)
        except Exception as e:
            logger.error(f"PRIDE get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Project -> species, tissues, diseases, instruments, modifications, experiment types
        and publications.

        Labels: ``has_species`` (``NCBITaxon:n``), ``has_tissue`` (``BTO:n``), ``has_disease``
        (``DOID:n``), ``uses_instrument`` (``MS:n``), ``has_modification`` (``MOD:n``),
        ``has_experiment_type`` (``PRIDE:n``) and ``has_publication`` (``PMID:n``, ``doi`` as
        extra key). Each list is capped at 50.
        """
        try:
            record = await self._load_record(concept_id)
            return self._record_relationships(record) if record else []
        except Exception as e:
            logger.warning(f"PRIDE get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Project -> own PXD accession, dataset DOI, publication PMIDs/DOIs and taxonomy ids."""
        try:
            record = await self._load_record(concept_id)
            if record is None:
                return []
            acc = record["accession"]
            mappings = [mapping(acc, acc, SOURCE_NAME, "PRIDE", "exact")]
            if record["dataset_doi"]:
                mappings.append(mapping(acc, record["dataset_doi"], SOURCE_NAME, "DOI", "exact"))
            for pmid in record["pmids"]:
                mappings.append(mapping(acc, pmid, SOURCE_NAME, "PubMed", "related", 0.9))
            for doi in record["dois"]:
                mappings.append(mapping(acc, doi, SOURCE_NAME, "DOI", "related", 0.9))
            for tax in record["taxon_ids"]:
                mappings.append(mapping(acc, tax, SOURCE_NAME, "NCBITaxon", "related", 0.9))
            return mappings
        except Exception as e:
            logger.warning(f"PRIDE get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Record loading and conversion
    # ------------------------------------------------------------------

    async def _load_record(self, concept_id: str) -> dict[str, Any] | None:
        accession = self.normalize_accession(concept_id)
        if accession is None:
            return None
        data = await self._request(PROJECT_URL.format(accession=accession))
        if not isinstance(data, dict) or not data.get("accession"):
            return None
        return self._normalise(data)

    @staticmethod
    def _normalise(item: dict[str, Any]) -> dict[str, Any] | None:
        """Common shape for ``search/projects`` hits and ``projects/<acc>`` details.

        Never reads ``submitters`` / ``labPIs`` (names, e-mails, ORCIDs).
        """
        accession = str(item.get("accession") or "").strip().upper()
        if not accession:
            return None
        publications: list[dict[str, str | None]] = []
        for ref in item.get("references") or []:
            pmid: str | None = None
            doi: str | None = None
            if isinstance(ref, dict):
                pmid = str(ref["pubmedID"]) if ref.get("pubmedID") else None
                doi = str(ref["doi"]).strip() if ref.get("doi") else None
            elif isinstance(ref, str):
                found_pmid = _PMID_IN_REF_RE.search(ref)
                found_doi = _DOI_IN_REF_RE.search(ref)
                pmid = found_pmid.group(1) if found_pmid else None
                doi = found_doi.group(1).rstrip(".,;") if found_doi else None
            pmid = None if pmid in (None, "0") else pmid
            if pmid or doi:
                publications.append({"pmid": pmid, "doi": doi})
        species = _terms(item.get("organisms"))
        taxon_ids = dedupe(
            [t for t in (taxon_id(s["id"]) or taxon_id(s["name"]) for s in species) if t]
        )
        files = item.get("projectFileNames")
        return {
            "accession": accession,
            "title": strip_html(item.get("title")) or accession,
            "description": strip_html(item.get("projectDescription")),
            "keywords": _strings(item.get("keywords")),
            "tags": _strings(item.get("projectTags")),
            "species": species,
            "taxon_ids": taxon_ids,
            "tissues": _terms(item.get("organismParts") or item.get("organismsPart")),
            "diseases": _terms(item.get("diseases")),
            "instruments": _terms(item.get("instruments")),
            "modifications": _terms(item.get("identifiedPTMStrings")),
            "experiment_types": _terms(item.get("experimentTypes")),
            "software": [t["name"] for t in _terms(item.get("softwares"))],
            "quantification": [t["name"] for t in _terms(item.get("quantificationMethods"))],
            "submission_date": iso_date(item.get("submissionDate")),
            "publication_date": iso_date(item.get("publicationDate")),
            "publications": publications,
            "pmids": dedupe([p["pmid"] for p in publications if p["pmid"]]),
            "dois": dedupe([p["doi"] for p in publications if p["doi"]]),
            "dataset_doi": (str(item["doi"]).strip() if item.get("doi") else None),
            "license": item.get("license") or None,
            "submission_type": item.get("submissionType") or None,
            "affiliations": _strings(item.get("affiliations")),
            "countries": _strings(item.get("countries")),
            "files_count": len(files) if isinstance(files, list) else None,
            "url": WEB_URL.format(accession=accession),
        }

    def _hit_to_concept(self, item: Any) -> UnifiedConcept | None:
        if not isinstance(item, dict):
            return None
        record = self._normalise(item)
        return self._record_to_concept(record) if record else None

    def _record_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a normalised record to a ``UnifiedConcept`` (type STUDY)."""
        try:
            accession = record["accession"]
            concept = self._create_concept(accession, record["title"], ConceptType.STUDY)
            if record["description"]:
                concept.definitions = [record["description"]]
            concept.synonyms = [
                k for k in record["keywords"] if k.lower() != record["title"].lower()
            ]

            def names(key: str) -> list[str]:
                return [str(t["name"]) for t in record[key]]

            categories = [f"species:{n}" for n in names("species")]
            categories += [f"tissue:{n}" for n in names("tissues")]
            categories += [f"disease:{n}" for n in names("diseases")]
            categories += [f"instrument:{n}" for n in names("instruments")]
            categories += [f"experiment_type:{n}" for n in names("experiment_types")]
            if record["publication_date"] or record["submission_date"]:
                year = (record["publication_date"] or record["submission_date"])[:4]
                categories.append(f"year:{year}")
            concept.categories = dedupe(categories)
            concept.semantic_types = dedupe(names("experiment_types"))
            concept.add_identifier(
                KnowledgeSource.OMICSDI, f"pride:{accession}", record["title"], None
            )
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.PRIDE] = {
                    key: value
                    for key, value in record.items()
                    if key != "description" and value not in (None, [], {})
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting PRIDE record: {e}")
            return None

    @staticmethod
    def _record_relationships(record: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for label, key, prefix in (
            ("has_species", "species", "SPECIES"),
            ("has_tissue", "tissues", "TISSUE"),
            ("has_disease", "diseases", "DISEASE"),
            ("uses_instrument", "instruments", "INSTRUMENT"),
            ("has_modification", "modifications", "MODIFICATION"),
            ("has_experiment_type", "experiment_types", "EXPERIMENT_TYPE"),
        ):
            for term in record[key][:ENTITY_CAP]:
                related = _cv_id(term) or f"PRIDE:{prefix}:{term['name']}"
                if label == "has_species" and not term["id"]:
                    tax = taxon_id(term["name"])
                    related = f"NCBITaxon:{tax}" if tax else related
                out.append(relationship(label, related, str(term["name"]), SOURCE_NAME))
        for pub in record["publications"][:ENTITY_CAP]:
            if pub["pmid"]:
                related, name = f"PMID:{pub['pmid']}", f"PubMed {pub['pmid']}"
            else:
                related, name = f"DOI:{pub['doi']}", str(pub["doi"])
            out.append(relationship("has_publication", related, name, SOURCE_NAME, doi=pub["doi"]))
        return out
