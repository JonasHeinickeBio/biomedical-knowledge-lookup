"""
BioStudies / ArrayExpress Knowledge Source Adapter

EMBL-EBI BioStudies stores studies that do not fit a specialised archive; since 2021 it is
also the home of **ArrayExpress** (functional genomics: microarray, RNA-seq, spatial
transcriptomics, methylation, ChIP-seq). ArrayExpress accessions (``E-MTAB-``, ``E-GEOD-``,
``E-MEXP-``...) are BioStudies accessions, and BioStudies also holds the Europe PMC
supplementary-data studies (``S-EPMC``), BioImages (``S-BIAD``) and others. The adapter
returns study **metadata and URLs only**; file lists are never fetched or listed, only
their count (and the link of the study's file directory) is reported.

Licence / terms: EMBL-EBI terms of use; metadata is open (CC0 for the index), each study
keeps the licence given by its submitters. No key, no documented rate limit.

API (verified live 2026-10-09, keyless, JSON)::

    GET /biostudies/api/v1/[<collection>/]search?query=&pageSize=&page=&type=study
    GET /biostudies/api/v1/studies/<accession>
    GET /biostudies/api/v1/studies/<accession>/info

Quirks worth knowing:

* Without a collection the search covers everything and is dominated by the 100k+ Europe PMC
  ``S-EPMC`` records (``chronic fatigue`` -> 116,508 hits, mostly literature supplements).
  A study search for omics data therefore **defaults to the ``arrayexpress`` collection**
  (2,412 hits for ``chronic fatigue``). Pass ``collection="all"`` for the whole archive or
  another collection name; an unknown collection answers 200 with zero hits. The
  ``?collection=`` query parameter and the ``/<collection>/search`` path behave alike.
* ``page`` starts at 1; ``pageSize`` up to 100 was verified. ``totalHits`` is flagged
  ``isTotalHitsExact: false``. ``sortBy=release_date`` with ``sortOrder=descending`` is
  honoured (``relevance`` is the default).
* The query engine expands words with EFO synonyms (``chronic fatigue`` also matches
  ``tiredness`` and ``exhaustion``), so unquoted text is broad; ``phrase=True`` quotes it.
* Search hits carry only accession, title, an author-name string, release date and the number
  of files and links. Organism, study type, technology, publications and links need the full
  study record (``studies/<acc>``), which is a nested "section" tree. For studies with many
  files it embeds the per-file metadata (159 KB for E-GEOD-16059's 178 files); nothing is
  downloaded beyond that JSON. ``studies/<acc>/info`` is small and gives the file count.
* The full record's ``Author`` sections contain e-mail addresses for some submitters. The
  adapter only counts authors and never copies names or e-mails into concepts.
* An unknown accession answers HTTP 404 ``{"errorMessage": "Study not found"}``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
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

BASE_URL = "https://www.ebi.ac.uk/biostudies/api/v1"
STUDY_URL = "https://www.ebi.ac.uk/biostudies/studies/{accession}"
SOURCE_NAME = "BIOSTUDIES"

DEFAULT_COLLECTION = "arrayexpress"
ALL_COLLECTIONS = frozenset({"", "all", "*", "biostudies"})
PAGE_SIZE = 100
MAX_RESULTS = 100
ENTITY_CAP = 50

COLLECTION_LABELS = {"arrayexpress": "ArrayExpress"}  # spelling of a study's ``AttachTo``
SORT_FIELDS = {"relevance", "release_date", "files", "links", "views"}
_ACCESSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9][A-Za-z0-9-]*$")
_ID_PREFIX_RE = re.compile(r"^(?:BIOSTUDIES|ARRAYEXPRESS|BST)[:_]", re.IGNORECASE)
_COLLECTION_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_LUCENE_SYNTAX_RE = re.compile(r'["():]|\b(?:AND|OR|NOT)\b')
_PMID_RE = re.compile(r"^\d{1,9}$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")

#: link ``Type`` -> relation label (anything else becomes ``has_external_record``).
LINK_RELATIONS: dict[str, str] = {
    "geo": "has_geo_series",
    "ena": "has_ena_project",
    "biosamples": "has_biosample",
    "sra": "has_ena_project",
}
#: link ``Type`` -> spelling used for ``toSource`` in mappings.
LINK_SOURCES: dict[str, str] = {
    "geo": "GEO",
    "ena": "ENA",
    "biosamples": "BioSamples",
    "sra": "SRA",
    "bioproject": "BioProject",
    "pride": "PRIDE",
    "metabolights": "MetaboLights",
}
_STUDY_TYPE_NAMES = ("study type", "experiment type", "experiment_type")
_ORGANISM_NAMES = ("organism", "species")
_DISEASE_NAMES = ("disease", "disease state")


def _quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


def _attr_list(attributes: Any) -> list[tuple[str, str, str | None]]:
    """``[{"name","value","valqual"}]`` -> ``[(name, value, term_id)]``; skips junk entries."""
    out: list[tuple[str, str, str | None]] = []
    for attr in attributes if isinstance(attributes, list) else []:
        if not isinstance(attr, dict):
            continue
        name, value = attr.get("name"), attr.get("value")
        if not isinstance(name, str) or value in (None, ""):
            continue
        term = None
        for qual in attr.get("valqual") or []:
            if isinstance(qual, dict) and str(qual.get("name", "")).lower() == "termid":
                term = str(qual.get("value") or "") or None
        out.append((name, str(value).strip(), term))
    return out


def _flatten(value: Any) -> Iterator[dict[str, Any]]:
    """BioStudies nests sections/links/files as dicts *or* lists of dicts (or lists of lists)."""
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _flatten(item)


class BioStudiesAdapter(KnowledgeSourceAdapter):
    """Adapter for EMBL-EBI BioStudies / ArrayExpress (keyless, metadata only)."""

    def __init__(self, config):
        super().__init__(config)
        self._throttle = RequestThrottle()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.BIOSTUDIES

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier and request helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_accession(concept_id: str) -> str | None:
        """``E-GEOD-16059`` / ``BIOSTUDIES:E-MTAB-14669`` / ``S-EPMC7260435`` -> accession."""
        text = _ID_PREFIX_RE.sub("", (concept_id or "").strip())
        return text if _ACCESSION_RE.match(text) else None

    async def _request(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Throttled GET; ``None`` on any failure (404 = unknown study / empty)."""
        await self._throttle.wait()
        try:
            data = await self._make_request(url, params=params)
        except Exception as e:
            if getattr(e, "status", None) == 404:
                logger.info(f"BioStudies {url} answered 404")
            else:
                logger.warning(f"BioStudies request failed for {url}: {e}")
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_studies(
        self,
        query: str,
        limit: int = 20,
        collection: str | None = DEFAULT_COLLECTION,
        sort: str = "relevance",
        descending: bool = True,
        phrase: bool = False,
    ) -> list[UnifiedConcept]:
        """Search studies (``page`` is 1-based, at most 100 results per call).

        ``collection`` defaults to ``arrayexpress`` (see module docstring); use ``"all"`` for
        the whole archive. ``sort`` is one of ``relevance``, ``release_date``, ``files``,
        ``links``, ``views``. ``phrase=True`` quotes multi-word text so synonym expansion
        does not widen it.
        """
        try:
            limit = max(0, min(int(limit), MAX_RESULTS))
            text = (query or "").strip()
            if not text or limit == 0:
                return []
            if phrase and " " in text and not _LUCENE_SYNTAX_RE.search(text):
                text = _quote(text)
            name = (collection or "").strip()
            if name.lower() in ALL_COLLECTIONS:
                url = f"{BASE_URL}/search"
            elif _COLLECTION_RE.match(name):
                url = f"{BASE_URL}/{name.lower()}/search"
            else:
                logger.warning(f"BioStudies: invalid collection '{collection}'")
                return []
            sort_by = sort if sort in SORT_FIELDS else "relevance"
            label = (
                None
                if name.lower() in ALL_COLLECTIONS
                else COLLECTION_LABELS.get(name.lower(), name)
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            page = 1
            while len(concepts) < limit:
                size = min(PAGE_SIZE, limit)  # constant: ``page`` is a page number, not an offset
                params = {
                    "query": text,
                    "pageSize": size,
                    "page": page,
                    "type": "study",
                    "sortBy": sort_by,
                    "sortOrder": "descending" if descending else "ascending",
                }
                data = await self._request(url, params)
                hits = data.get("hits") if data else None
                if not isinstance(hits, list) or not hits:
                    break
                added = 0
                for hit in hits:
                    concept = self._hit_to_concept(hit, label)
                    if concept is not None and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
                        added += 1
                if not added or len(hits) < size:
                    break
                page += 1
            logger.info(f"BioStudies search for '{text}' returned {len(concepts[:limit])} studies")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"BioStudies search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search ArrayExpress studies; an accession query resolves to that study."""
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.normalize_accession(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            return await self.search_studies(query, limit)
        except Exception as e:
            logger.error(f"BioStudies search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full study record plus file count (``studies/<acc>`` and ``.../info``)."""
        try:
            record = await self._load_record(concept_id)
            return self._record_to_concept(record) if record else None
        except Exception as e:
            logger.error(f"BioStudies get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Study -> publications, organism, study (experiment) type, technology and links.

        Labels: ``has_publication`` (``PMID:n``, or ``DOI:...`` when only a DOI is recorded,
        with ``doi`` as extra key), ``has_organism``, ``has_experiment_type`` (``EFO:...``
        when the submitter gave a term), ``uses_technology``, ``has_assay_molecule``,
        ``linked_study`` (another BioStudies accession) and ``has_geo_series`` /
        ``has_ena_project`` / ``has_biosample`` / ``has_external_record`` for other links.
        """
        try:
            record = await self._load_record(concept_id)
            return self._record_relationships(record) if record else []
        except Exception as e:
            logger.warning(f"BioStudies get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Study -> own accession, PMIDs, DOIs and recorded external accessions (GEO, ENA...)."""
        try:
            record = await self._load_record(concept_id)
            if record is None:
                return []
            acc = record["accession"]
            home = "ArrayExpress" if record["collection"] == "ArrayExpress" else "BioStudies"
            mappings = [mapping(acc, acc, SOURCE_NAME, home, "exact")]
            for pub in record["publications"]:
                if pub["pmid"]:
                    mappings.append(
                        mapping(acc, pub["pmid"], SOURCE_NAME, "PubMed", "related", 0.9)
                    )
                if pub["doi"]:
                    mappings.append(mapping(acc, pub["doi"], SOURCE_NAME, "DOI", "related", 0.9))
            for link in record["links"]:
                source = LINK_SOURCES.get(link["type"].lower())
                if source:
                    mappings.append(
                        mapping(
                            acc,
                            link["url"],
                            SOURCE_NAME,
                            source or link["type"],
                            "exact" if source == "GEO" else "related",
                            1.0 if source == "GEO" else 0.9,
                        )
                    )
            return mappings
        except Exception as e:
            logger.warning(f"BioStudies get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Record loading and conversion
    # ------------------------------------------------------------------

    async def _load_record(self, concept_id: str) -> dict[str, Any] | None:
        accession = self.normalize_accession(concept_id)
        if accession is None:
            return None
        study = await self._request(f"{BASE_URL}/studies/{accession}")
        if not study or not study.get("accno"):
            return None
        info = await self._request(f"{BASE_URL}/studies/{accession}/info")
        return self._parse_study(study, info or {})

    @staticmethod
    def _parse_study(study: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
        """Flatten the nested section tree into the fields the adapter exposes."""
        accession = str(study.get("accno") or "")
        top = {n.lower(): v for n, v, _ in _attr_list(study.get("attributes"))}
        section: dict[str, Any] = (
            study["section"] if isinstance(study.get("section"), dict) else {}
        )
        sec_attrs = _attr_list(section.get("attributes"))

        def values(names: tuple[str, ...]) -> list[tuple[str, str | None]]:
            return [(v, t) for n, v, t in sec_attrs if n.lower() in names]

        subs = list(_flatten(section.get("subsections")))
        by_type: dict[str, list[dict[str, Any]]] = {}
        for sub in subs:
            by_type.setdefault(str(sub.get("type") or ""), []).append(sub)

        technologies: list[str] = []
        molecules: list[str] = []
        sample_count: int | None = None
        for sub in by_type.get("Assays and Data", []):
            for n, v, _ in _attr_list(sub.get("attributes")):
                if n.lower() == "technology":
                    technologies.append(v)
                elif n.lower() == "assay by molecule":
                    molecules.append(v)
        for sub in by_type.get("Samples", []):
            for n, v, _ in _attr_list(sub.get("attributes")):
                if n.lower() == "sample count" and v.isdigit():
                    sample_count = int(v)

        publications: list[dict[str, str | None]] = []
        for sub in by_type.get("Publication", []):
            attrs = {n.lower(): v for n, v, _ in _attr_list(sub.get("attributes"))}
            accno = str(sub.get("accno") or "").strip()
            doi = attrs.get("doi")
            for link in _flatten(sub.get("links")):
                kinds = {n.lower(): v for n, v, _ in _attr_list(link.get("attributes"))}
                if kinds.get("type", "").lower() == "doi" and not doi:
                    doi = str(link.get("url") or "") or None
            pmid = accno if _PMID_RE.match(accno) else None
            doi = doi if doi and _DOI_RE.match(doi) else None
            if pmid or doi:
                publications.append({"pmid": pmid, "doi": doi, "title": attrs.get("title")})

        links: list[dict[str, str]] = []
        for link in _flatten(section.get("links")):
            kinds = {n.lower(): v for n, v, _ in _attr_list(link.get("attributes"))}
            url = str(link.get("url") or "").strip()
            if url:
                links.append({"url": url, "type": kinds.get("type", "")})

        organisms = dedupe([v for v, _ in values(_ORGANISM_NAMES)])
        title = strip_html(
            top.get("title") or next((v for n, v, _ in sec_attrs if n == "Title"), "")
        )
        collection = top.get("attachto") or ""
        release = iso_date(top.get("releasedate")) or iso_date(info.get("released"))
        extra = {
            n: v
            for n, v, _ in sec_attrs
            if n.lower() not in (*_STUDY_TYPE_NAMES, *_ORGANISM_NAMES, "title", "description")
        }
        return {
            "accession": accession,
            "title": title or accession,
            "description": strip_html(
                next((v for n, v, _ in sec_attrs if n.lower() == "description"), "")
            ),
            "collection": collection,
            "release_date": release,
            "organisms": organisms,
            "taxon_ids": dedupe([t for t in (taxon_id(o) for o in organisms) if t]),
            "study_types": [{"name": v, "term_id": t} for v, t in values(_STUDY_TYPE_NAMES)],
            "diseases": dedupe([v for v, _ in values(_DISEASE_NAMES)]),
            "technologies": dedupe(technologies),
            "assay_molecules": dedupe(molecules),
            "sample_count": sample_count,
            "authors_count": len(by_type.get("Author", [])),
            "organizations": dedupe(
                [
                    v
                    for sub in by_type.get("Organization", [])
                    for n, v, _ in _attr_list(sub.get("attributes"))
                    if n.lower() == "name"
                ]
            ),
            "publications": publications,
            "links": links,
            "files_count": info.get("files") if isinstance(info.get("files"), int) else None,
            "files_url": info.get("httpLink") or None,
            "other_attributes": extra,
            "url": STUDY_URL.format(accession=accession),
        }

    def _hit_to_concept(self, hit: Any, collection: str | None = None) -> UnifiedConcept | None:
        """Concept from a search hit (no organism/publication data; see module docstring)."""
        if not isinstance(hit, dict):
            return None
        accession = str(hit.get("accession") or "").strip()
        if not accession:
            return None
        record: dict[str, Any] = {
            "accession": accession,
            "title": strip_html(hit.get("title")) or accession,
            "description": "",
            "collection": collection or "",
            "release_date": iso_date(hit.get("release_date")),
            "organisms": [],
            "taxon_ids": [],
            "study_types": [],
            "diseases": [],
            "technologies": [],
            "assay_molecules": [],
            "sample_count": None,
            "authors_count": None,
            "organizations": [],
            "publications": [],
            "links": [],
            "files_count": hit.get("files") if isinstance(hit.get("files"), int) else None,
            "files_url": None,
            "other_attributes": {},
            "url": STUDY_URL.format(accession=accession),
            "links_count": hit.get("links") if isinstance(hit.get("links"), int) else None,
            "views": hit.get("views") if isinstance(hit.get("views"), int) else None,
        }
        return self._record_to_concept(record)

    def _record_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a parsed record to a ``UnifiedConcept`` (type STUDY)."""
        try:
            accession = record["accession"]
            concept = self._create_concept(accession, record["title"], ConceptType.STUDY)
            if record["description"]:
                concept.definitions = [record["description"]]
            study_types = [s["name"] for s in record["study_types"]]
            categories = []
            if record["collection"]:
                categories.append(f"collection:{record['collection']}")
            categories += [f"organism:{o}" for o in record["organisms"]]
            categories += [f"study_type:{t}" for t in study_types]
            categories += [f"technology:{t}" for t in record["technologies"]]
            categories += [f"disease:{d}" for d in record["diseases"]]
            if record["release_date"]:
                categories.append(f"year:{record['release_date'][:4]}")
            concept.categories = dedupe(categories)
            concept.semantic_types = dedupe(study_types)
            if accession.upper().startswith("E-"):
                concept.add_identifier(
                    KnowledgeSource.OMICSDI,
                    f"biostudies-arrayexpress:{accession}",
                    record["title"],
                    f"https://www.omicsdi.org/dataset/biostudies-arrayexpress/{accession}",
                )
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.BIOSTUDIES] = {
                    key: value
                    for key, value in record.items()
                    if key != "description" and value not in (None, [], {})
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting BioStudies record: {e}")
            return None

    @staticmethod
    def _record_relationships(record: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for pub in record["publications"][:ENTITY_CAP]:
            if pub["pmid"]:
                out.append(
                    relationship(
                        "has_publication",
                        f"PMID:{pub['pmid']}",
                        pub["title"] or f"PubMed {pub['pmid']}",
                        SOURCE_NAME,
                        doi=pub["doi"],
                    )
                )
            elif pub["doi"]:
                out.append(
                    relationship(
                        "has_publication",
                        f"DOI:{pub['doi']}",
                        pub["title"] or pub["doi"],
                        SOURCE_NAME,
                        doi=pub["doi"],
                    )
                )
        for name in record["organisms"][:ENTITY_CAP]:
            tax = taxon_id(name)
            out.append(
                relationship(
                    "has_organism",
                    f"NCBITaxon:{tax}" if tax else f"BIOSTUDIES:ORGANISM:{name}",
                    name,
                    SOURCE_NAME,
                )
            )
        for study_type in record["study_types"][:ENTITY_CAP]:
            name, term = study_type["name"], study_type["term_id"]
            out.append(
                relationship(
                    "has_experiment_type",
                    term.replace("_", ":") if term else f"BIOSTUDIES:EXPERIMENT_TYPE:{name}",
                    name,
                    SOURCE_NAME,
                )
            )
        for label, key, prefix in (
            ("uses_technology", "technologies", "TECHNOLOGY"),
            ("has_assay_molecule", "assay_molecules", "ASSAY_MOLECULE"),
        ):
            for name in record[key][:ENTITY_CAP]:
                out.append(relationship(label, f"BIOSTUDIES:{prefix}:{name}", name, SOURCE_NAME))
        for link in record["links"][:ENTITY_CAP]:
            kind = link["type"] or "link"
            if _ACCESSION_RE.match(link["url"]) and kind.lower() in ("", "link", "biostudies"):
                label, related = "linked_study", link["url"]
            else:
                label = LINK_RELATIONS.get(kind.lower(), "has_external_record")
                related = f"{LINK_SOURCES.get(kind.lower(), kind)}:{link['url']}"
            out.append(relationship(label, related, link["url"], SOURCE_NAME, link_type=kind))
        return out
