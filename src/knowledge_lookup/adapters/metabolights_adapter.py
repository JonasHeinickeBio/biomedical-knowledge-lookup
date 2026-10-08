"""
MetaboLights adapter.

MetaboLights (EMBL-EBI) is the reference repository for metabolomics studies (``MTBLS161``) and
a curated database of reference metabolites (``MTBLC16651``, whose number is the ChEBI id of the
compound). Several ME/CFS and Long COVID studies are deposited here (``MTBLS161`` NMR
profiling of serum and urine of ME/CFS patients, ``MTBLS11718`` gut microecology of long COVID).

Two keyless EMBL-EBI services are used, verified live 2026-10:

* **EBI Search** (``https://www.ebi.ac.uk/ebisearch/ws/rest/metabolights``): the MetaboLights
  web service has no text search (``ws/studies`` returns 3,500 bare study ids, 43 KB, and
  ``ws/compounds/list`` 33,000 bare compound ids, 470 KB, so there is nothing to filter locally).
  EBI Search indexes studies *and* compounds in one domain, told apart by id prefix
  (``id:MTBLS*`` / ``id:MTBLC*``). It provides full-text search with AND semantics, the study
  fields used here (``name``, ``description``, ``organism``, ``technology_type``,
  ``study_factor``, ``study_design``, ``publication`` with DOI and ``PMID:``, ``PUBMED``,
  dates, ``instrument_platform``, ``tissue``) and the cross-reference fields ``METABOLIGHTS``
  (the compounds a study reports, up to hundreds) and ``CHEBI`` (searching ``"CHEBI:422"``
  finds the studies that report that compound; the reverse link is not stored on compounds).
  ``entry/{id1,id2,...}`` fetches up to 100 records by id; unknown ids are silently omitted.
  Lucene operators in user text (``/``, ``:``, quotes ...) are replaced by spaces.
* **MetaboLights web service** (``https://www.ebi.ac.uk/metabolights/ws``):
  ``compounds/{MTBLC}`` returns name, description, InChI, InChIKey, ``chebiId``, formula, IUPAC
  names, ``metSpecies`` (organisms with NCBI taxon ids where known) and ``crossReference``.
  KEGG, HMDB and PubChem ids are **not** part of the compound record, so mappings are limited to
  ChEBI and InChIKey. A missing compound answers HTTP 403, a missing study 400; both are treated
  as "not found" without counting against the circuit breaker. The ``ws/v2`` prefix does not exist.

EBI services ask for polite use; calls are spaced 0.2 s apart (5 requests/s). Data are open
(EMBL-EBI terms of use; individual studies state a dataset licence), cite the study accession.

Concept ids: ``MTBLS161`` (study), ``MTBLC16651`` or ``CHEBI:16651`` (reference metabolite).
"""

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

EBI_SEARCH_URL = "https://www.ebi.ac.uk/ebisearch/ws/rest/metabolights"
WS_URL = "https://www.ebi.ac.uk/metabolights/ws"
PAGE_URL = "https://www.ebi.ac.uk/metabolights/"

_MIN_INTERVAL = 0.2
_MAX_SEARCH = 100  # EBI Search returns at most 100 entries per page
_DEFAULT_RELATIONS = 50
_NOT_FOUND_STATUSES = {400, 403, 404}

_STUDY_RE = re.compile(r"^(?:metabolights\s*[:_]\s*)?(MTBLS\d+)$", re.IGNORECASE)
_COMPOUND_RE = re.compile(r"^(?:metabolights\s*[:_]\s*)?MTBLC(\d+)$", re.IGNORECASE)
_CHEBI_RE = re.compile(r"^CHEBI\s*[:_]\s*(\d+)$", re.IGNORECASE)
_LUCENE_SPECIAL_RE = re.compile(r'[+!(){}\[\]^"~*?:\\/&|]')
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s]+?)\.?(?=\s|$)")
_PMID_RE = re.compile(r"PMID:\s*(\d+)", re.IGNORECASE)

_STUDY_FIELDS = (
    "name,description,organism,technology_type,study_factor,study_design,publication,PUBMED,"
    "submission_date,publication_date,study_status,tissue,instrument_platform,TAXONOMY"
)
_SEARCH_STUDY_FIELDS = "name,description,organism,technology_type,study_factor,publication_date"
_NAME_FIELDS = "name,description"


def _values(entry: dict[str, Any], field: str) -> list[str]:
    """Non-empty string values of an EBI Search field (always a list there)."""
    raw = (entry.get("fields") or {}).get(field) or []
    return [str(v).strip() for v in raw if str(v).strip()]


def _first(entry: dict[str, Any], field: str) -> str:
    values = _values(entry, field)
    return values[0] if values else ""


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for value in values:
        if value.casefold() not in seen:
            seen.add(value.casefold())
            out.append(value)
    return out


def _iso(date: str) -> str:
    """``20150123`` -> ``2015-01-23`` (other shapes unchanged)."""
    return f"{date[:4]}-{date[4:6]}-{date[6:]}" if re.fullmatch(r"\d{8}", date) else date


class MetaboLightsAdapter(KnowledgeSourceAdapter):
    """MetaboLights studies and reference metabolites (EBI Search + MetaboLights web service)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.search_url = EBI_SEARCH_URL
        self.ws_url = WS_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.METABOLIGHTS

    def is_available(self) -> bool:
        return True  # public, keyless services

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _request(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET JSON, mapping "does not exist" answers (400/403/404) to ``None``.

        MetaboLights answers a missing compound with HTTP 403 and a missing study with 400.
        These are valid answers of a healthy service, so they must neither be retried nor
        count as failures for the circuit breaker (which :meth:`_make_request` would do).
        """
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

        async def _do() -> Any:
            session = await self._get_session()
            headers = {"Accept": "application/json", "User-Agent": "AID-PAIS-Knowledge-Lookup/1.0"}
            async with session.get(url, params=params, headers=headers) as response:
                if response.status in _NOT_FOUND_STATUSES:
                    return None
                response.raise_for_status()
                return await response.json(content_type=None)

        return await self._call_with_retry("metabolights_request", _do)

    async def _entries(self, ids: list[str], fields: str) -> list[dict[str, Any]]:
        """EBI Search records for up to 100 ids (unknown ids are omitted by the service)."""
        if not ids:
            return []
        data = await self._request(
            f"{self.search_url}/entry/{','.join(ids[:_MAX_SEARCH])}",
            {"format": "json", "fields": fields},
        )
        return [e for e in (data or {}).get("entries") or [] if isinstance(e, dict)]

    async def _search(
        self, query: str, fields: str, size: int
    ) -> tuple[int, list[dict[str, Any]]]:
        data = await self._request(
            self.search_url, {"query": query, "format": "json", "fields": fields, "size": size}
        )
        if not isinstance(data, dict):
            return 0, []
        entries = [e for e in data.get("entries") or [] if isinstance(e, dict)]
        return int(data.get("hitCount") or 0), entries

    async def _compound_record(self, accession: str) -> dict[str, Any] | None:
        data = await self._request(f"{self.ws_url}/compounds/{accession}")
        content = (data or {}).get("content") if isinstance(data, dict) else None
        return content if isinstance(content, dict) and content.get("accession") else None

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("study", "MTBLS161")`` or ``("compound", "MTBLC16651")``; ``CHEBI:16651`` maps to
        the compound with the same number."""
        text = (concept_id or "").strip()
        if match := _STUDY_RE.match(text):
            return "study", match.group(1).upper()
        if match := _COMPOUND_RE.match(text):
            return "compound", f"MTBLC{int(match.group(1))}"
        if match := _CHEBI_RE.match(text):
            return "compound", f"MTBLC{int(match.group(1))}"
        return None

    @staticmethod
    def _clean_query(text: str) -> str:
        """Drop Lucene operators (``ME/CFS`` becomes ``ME CFS``) and stray leading dashes."""
        words = _LUCENE_SPECIAL_RE.sub(" ", text).split()
        return " ".join(w.lstrip("-") for w in words if w.strip("-"))

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Full-text search of studies and reference metabolites.

        All words must match (AND). Studies come newest first, metabolites by name; the result
        keeps up to half of ``limit`` metabolites and fills the rest with studies (and the other
        way round when one side is short). An id goes straight to details.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            if self._parse_id(text) is not None:
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            clean = self._clean_query(text)
            if not clean:
                return []
            size = min(limit, _MAX_SEARCH)
            _, compounds = await self._search(f"({clean}) AND id:MTBLC*", _NAME_FIELDS, size)
            _, studies = await self._search(f"({clean}) AND id:MTBLS*", _SEARCH_STUDY_FIELDS, size)
            n_compounds = min(len(compounds), max((limit + 1) // 2, limit - len(studies)))
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank, entry in enumerate(compounds[:n_compounds] + studies):
                concept = (
                    self._compound_entry_to_concept(entry)
                    if str(entry.get("id", "")).upper().startswith("MTBLC")
                    else self._study_entry_to_concept(entry)
                )
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concept.confidence_score = max(0.5, 0.85 - 0.01 * rank)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"MetaboLights search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"MetaboLights search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """A study (EBI Search record) or a reference metabolite (web service record)."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        kind, accession = parsed
        try:
            if kind == "study":
                entries = await self._entries([accession], f"{_STUDY_FIELDS},METABOLIGHTS")
                concept = (
                    self._study_entry_to_concept(entries[0], detailed=True) if entries else None
                )
            else:
                record = await self._compound_record(accession)
                concept = self._compound_record_to_concept(record) if record else None
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"MetaboLights get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Mappings / relationships
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Metabolite: ChEBI and InChIKey. Study: PubMed id, DOI and NCBI taxonomy ids.

        KEGG, HMDB and PubChem ids are not exposed for reference metabolites by MetaboLights.
        ChEBI is exact by construction (``MTBLC<n>`` is ``CHEBI:<n>``); the InChIKey is the
        record's own. Study taxonomy ids are only present where the submitter annotated them.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return []
        kind, accession = parsed
        mappings: list[dict[str, Any]] = []

        def add(to_id: str, to_source: str, mapping_type: str = "xref") -> None:
            if all(m["toId"] != to_id for m in mappings):
                mappings.append(
                    {
                        "fromId": accession,
                        "toId": to_id,
                        "fromSource": "METABOLIGHTS",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": 1.0,
                    }
                )

        try:
            if kind == "compound":
                record = await self._compound_record(accession)
                if record is None:
                    return []
                add(str(record.get("chebiId") or f"CHEBI:{accession[5:]}"), "CHEBI", "exactMatch")
                if record.get("inchikey"):
                    add(f"INCHIKEY:{record['inchikey']}", "INCHIKEY")
            else:
                entries = await self._entries([accession], _STUDY_FIELDS)
                if not entries:
                    return []
                for pmid in _values(entries[0], "PUBMED"):
                    add(f"PMID:{pmid}", "PUBMED")
                publication = _first(entries[0], "publication")
                for pmid in _PMID_RE.findall(publication):
                    add(f"PMID:{pmid}", "PUBMED")
                for doi in _DOI_RE.findall(publication):
                    add(f"doi:{doi}", "DOI")
                for taxon in _values(entries[0], "TAXONOMY"):
                    add(
                        f"NCBITaxon:{taxon.removeprefix('NCBI:').removeprefix('NEWT:')}",
                        "NCBITAXON",
                    )
        except Exception as e:
            logger.error(f"MetaboLights get_mappings failed for '{concept_id}': {e}")
            return []
        return mappings

    async def get_relationships(
        self, concept_id: str, limit: int = _DEFAULT_RELATIONS
    ) -> list[dict[str, Any]]:
        """Study -> compounds, organisms, publications; metabolite -> studies and organisms.

        ``measures_compound`` (a study's reported reference metabolites, capped at ``limit``;
        studies list up to hundreds), ``studies_organism`` (organism name, or ``NCBITaxon:`` id
        when annotated), ``has_publication`` (``PMID:`` or ``doi:``), ``measured_in_study``
        (studies reporting the metabolite's ChEBI id, newest first, ``total_studies`` gives the
        full count) and ``found_in_organism`` (``metSpecies`` of the compound record, NCBI
        taxon ids where MetaboLights has them).
        """
        parsed = self._parse_id(concept_id)
        if parsed is None or limit <= 0:
            return []
        kind, accession = parsed
        try:
            if kind == "study":
                return await self._study_relationships(accession, min(limit, _MAX_SEARCH))
            return await self._compound_relationships(accession, min(limit, _MAX_SEARCH))
        except Exception as e:
            logger.error(f"MetaboLights get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _relation(label: str, related_id: str, name: str, **extra: Any) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": related_id,
            "related_name": name or related_id,
            "source": "METABOLIGHTS",
            **{k: v for k, v in extra.items() if v},
        }

    async def _study_relationships(self, accession: str, limit: int) -> list[dict[str, Any]]:
        entries = await self._entries([accession], f"{_STUDY_FIELDS},METABOLIGHTS")
        if not entries:
            return []
        entry = entries[0]
        relationships: list[dict[str, Any]] = []
        compound_ids = _unique(_values(entry, "METABOLIGHTS"))
        total = len(compound_ids)
        names = {
            str(e.get("id")): _first(e, "name")
            for e in await self._entries(compound_ids[:limit], "name")
        }
        for compound in compound_ids[:limit]:
            relationships.append(
                self._relation(
                    "measures_compound", compound, names.get(compound, ""), total_compounds=total
                )
            )
        taxa = [t.removeprefix("NCBI:").removeprefix("NEWT:") for t in _values(entry, "TAXONOMY")]
        for index, organism in enumerate(_unique(_values(entry, "organism"))[:limit]):
            taxon = taxa[index] if len(taxa) > index and taxa[index].isdigit() else ""
            relationships.append(
                self._relation(
                    "studies_organism", f"NCBITaxon:{taxon}" if taxon else organism, organism
                )
            )
        publication = _first(entry, "publication")
        pmids = _unique(_values(entry, "PUBMED") + _PMID_RE.findall(publication))
        dois = _unique(_DOI_RE.findall(publication))
        title = re.split(r"\.\s+(?:10\.|PMID)", publication)[0].strip()
        for pmid in pmids:
            relationships.append(self._relation("has_publication", f"PMID:{pmid}", title))
        if not pmids:
            for doi in dois:
                relationships.append(self._relation("has_publication", f"doi:{doi}", title))
        return relationships

    async def _compound_relationships(self, accession: str, limit: int) -> list[dict[str, Any]]:
        number = accession.removeprefix("MTBLC")
        relationships: list[dict[str, Any]] = []
        total, studies = await self._search(f'"CHEBI:{number}" AND id:MTBLS*', "name", limit)
        for entry in studies:
            relationships.append(
                self._relation(
                    "measured_in_study",
                    str(entry.get("id")),
                    _first(entry, "name"),
                    total_studies=total,
                )
            )
        record = await self._compound_record(accession)
        organisms = 0
        for species in (record or {}).get("metSpecies") or []:
            name = str(species.get("species") or "").strip()
            taxon = str(species.get("taxon") or "")
            if not name or name.casefold() == "reference compound" or organisms >= limit:
                continue
            ncbi = re.fullmatch(r"(?:NCBI|NEWT):(\d+)", taxon)
            organisms += 1
            relationships.append(
                self._relation(
                    "found_in_organism",
                    f"NCBITaxon:{ncbi.group(1)}" if ncbi else name,
                    name,
                )
            )
        return relationships

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _study_entry_to_concept(
        self, entry: dict[str, Any], detailed: bool = False
    ) -> UnifiedConcept | None:
        accession, title = str(entry.get("id") or ""), _first(entry, "name")
        if not accession or not title:
            return None
        concept = self._create_concept(accession, title, ConceptType.STUDY)
        if concept.identifiers:
            concept.identifiers[0].url = f"{PAGE_URL}{accession}"
        description = _first(entry, "description")
        if concept.definitions is not None and description:
            concept.definitions.append(description)
        organisms = _unique(_values(entry, "organism"))
        technology = _unique(_values(entry, "technology_type"))
        factors = _unique(_values(entry, "study_factor"))
        if concept.categories is not None:
            concept.categories.extend(_unique(organisms + factors))
        if concept.semantic_types is not None:
            concept.semantic_types.extend(technology)
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {
                "kind": "study",
                "organisms": organisms,
                "technology": technology,
                "factors": factors,
                "release_date": _iso(_first(entry, "publication_date")),
            }
            if detailed:
                publication = _first(entry, "publication")
                compounds = _unique(_values(entry, "METABOLIGHTS"))
                data.update(
                    {
                        "design_descriptors": _unique(_values(entry, "study_design")),
                        "tissues": _unique(_values(entry, "tissue")),
                        "instruments": _unique(_values(entry, "instrument_platform")),
                        "status": _first(entry, "study_status"),
                        "submission_date": _iso(_first(entry, "submission_date")),
                        "publication": publication,
                        "pubmed_ids": _unique(
                            _values(entry, "PUBMED") + _PMID_RE.findall(publication)
                        ),
                        "dois": _unique(_DOI_RE.findall(publication)),
                        "compound_count": len(compounds),
                    }
                )
            concept.source_data[self.get_source()] = data
        return concept

    def _compound_entry_to_concept(self, entry: dict[str, Any]) -> UnifiedConcept | None:
        accession, name = str(entry.get("id") or ""), _first(entry, "name")
        if not accession or not name:
            return None
        concept = self._create_concept(accession, name, ConceptType.METABOLITE)
        if concept.identifiers:
            concept.identifiers[0].url = f"{PAGE_URL}{accession}"
        description = _first(entry, "description")
        if concept.definitions is not None and description:
            concept.definitions.append(description)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {"kind": "metabolite"}
        return concept

    def _compound_record_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        accession, name = str(record.get("accession") or ""), str(record.get("name") or "")
        if not accession or not name:
            return None
        concept = self._create_concept(accession, name, ConceptType.METABOLITE)
        if concept.identifiers:
            concept.identifiers[0].url = f"{PAGE_URL}{accession}"
        if concept.definitions is not None and record.get("description"):
            concept.definitions.append(str(record["description"]))
        if concept.synonyms is not None:
            for iupac in str(record.get("iupacNames") or "").split(";"):
                if iupac.strip() and iupac.strip().casefold() != name.casefold():
                    concept.synonyms.append(iupac.strip())
        chebi = str(record.get("chebiId") or "")
        if chebi:
            concept.add_identifier(
                KnowledgeSource.CHEBI,
                chebi,
                name,
                f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={quote(chebi)}",
            )
        species = _unique(
            [
                str(s.get("species") or "")
                for s in record.get("metSpecies") or []
                if str(s.get("species") or "").casefold() != "reference compound"
            ]
        )
        if concept.categories is not None:
            concept.categories.extend(species)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": "metabolite",
                "formula": record.get("formula"),
                "inchi": record.get("inchi"),
                "inchikey": record.get("inchikey"),
                "chebi_id": chebi,
                "species": species,
                "has_nmr": record.get("hasNMR"),
                "has_ms": record.get("hasMS"),
                "has_literature": record.get("hasLiterature"),
                "has_pathways": record.get("hasPathways"),
                "has_reactions": record.get("hasReactions"),
                "study_accessions": [
                    x.get("accession")
                    for x in record.get("crossReference") or []
                    if str((x.get("db") or {}).get("name")) == "MTBLS"
                ],
            }
        return concept
