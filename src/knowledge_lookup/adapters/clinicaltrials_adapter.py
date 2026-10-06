"""
ClinicalTrials.gov Knowledge Source Adapter

Adapter for the ClinicalTrials.gov REST API v2, the US registry of clinical studies. A
registered *study* is the concept here (id ``NCT...``, label = brief title), not a disease
or drug: conditions and interventions are exposed as relationships so a trial can be
linked to the diseases it studies and the interventions it tests.

API documentation: https://clinicaltrials.gov/data-api/api

The API is keyless. ClinicalTrials.gov documents a soft limit of about 50 requests per
minute per IP, which the adapter respects by spacing requests (see ``_min_interval``).

ConceptType choice: the enum has no registry-record type, so ``studyType`` decides
``INTERVENTIONAL`` -> ``CLINICAL_TRIAL``, ``OBSERVATIONAL`` -> ``OBSERVATIONAL_STUDY`` and
anything else (expanded access) -> ``CLINICAL_STUDY``.

Quirks: free-text search (``query.term``) is relevance-ranked over many fields, so
broad terms such as "long covid" also return COVID-era studies that merely mention it;
use ``search_by_condition`` for precision. ``Phase`` is absent for observational studies.
MeSH terms under ``derivedSection`` are assigned algorithmically by the registry.
"""

import asyncio
import logging
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

_CT_BASE_URL = "https://clinicaltrials.gov/api/v2"

#: Fields requested for search results; the same names give the same JSON structure as a
#: full study record, so one parser serves both endpoints while payloads stay small.
_SEARCH_FIELDS = ",".join(
    [
        "NCTId",
        "BriefTitle",
        "OfficialTitle",
        "Acronym",
        "BriefSummary",
        "OverallStatus",
        "Phase",
        "StudyType",
        "Condition",
        "Keyword",
        "InterventionName",
        "InterventionType",
        "InterventionDescription",
        "EnrollmentCount",
        "EnrollmentType",
        "StartDate",
        "CompletionDate",
        "LeadSponsorName",
        "ConditionMeshId",
        "ConditionMeshTerm",
        "InterventionMeshId",
        "InterventionMeshTerm",
        "HasResults",
        "LastUpdatePostDate",
    ]
)

_NCT_RE = re.compile(r"^(?:CLINICALTRIALS|CLINICALTRIALS\.GOV|NCT|CTGOV):?\s*(NCT\d{8})$", re.I)
_BARE_NCT_RE = re.compile(r"^NCT\d{8}$", re.IGNORECASE)

_MAX_PAGE_SIZE = 100  # per-request cap; larger limits page with nextPageToken
_MAX_PAGES = 5

_STUDY_TYPES: dict[str, ConceptType] = {
    "INTERVENTIONAL": ConceptType.CLINICAL_TRIAL,
    "OBSERVATIONAL": ConceptType.OBSERVATIONAL_STUDY,
}


class ClinicalTrialsAdapter(KnowledgeSourceAdapter):
    """Adapter for ClinicalTrials.gov registered studies (API v2)."""

    #: Minimum seconds between requests (~48/min, under the documented ~50/min limit).
    _min_interval: float = 1.25

    def __init__(self, config):
        super().__init__(config)
        self.base_url = _CT_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CLINICALTRIALS

    def is_available(self) -> bool:
        return True  # ClinicalTrials.gov API is public and keyless

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """GET a ClinicalTrials.gov endpoint, spacing requests politely."""
        async with self._throttle_lock:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        return await self._make_request(f"{self.base_url}{endpoint}", params)

    @staticmethod
    def _normalize_nct(concept_id: str) -> str | None:
        """Return the upper-case NCT id for ``NCT01234567`` / ``ClinicalTrials:NCT...``."""
        cid = (concept_id or "").strip()
        if _BARE_NCT_RE.match(cid):
            return cid.upper()
        match = _NCT_RE.match(cid)
        return match.group(1).upper() if match else None

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Free-text search over studies (``query.term``: titles, conditions, interventions,
        sponsors, keywords, ...)."""
        return await self._search({"query.term": query}, query, limit)

    async def search_by_condition(
        self, condition: str, limit: int = 20, status: str | list[str] | None = None
    ) -> list[UnifiedConcept]:
        """Search studies by condition/disease (``query.cond``; synonym-aware on the server).

        ``status`` filters on ``overallStatus``, e.g. ``"RECRUITING"`` or
        ``["RECRUITING", "NOT_YET_RECRUITING"]``.
        """
        return await self._search({"query.cond": condition}, condition, limit, status)

    async def search_by_intervention(
        self, intervention: str, limit: int = 20, status: str | list[str] | None = None
    ) -> list[UnifiedConcept]:
        """Search studies by intervention/drug name (``query.intr``)."""
        return await self._search({"query.intr": intervention}, intervention, limit, status)

    async def _search(
        self,
        query_params: dict[str, str],
        query: str,
        limit: int,
        status: str | list[str] | None = None,
    ) -> list[UnifiedConcept]:
        if not query or not query.strip() or limit <= 0:
            return []
        try:
            params: dict[str, Any] = {key: value.strip() for key, value in query_params.items()}
            params["fields"] = _SEARCH_FIELDS
            params["pageSize"] = min(limit, _MAX_PAGE_SIZE)
            if status:
                statuses = [status] if isinstance(status, str) else list(status)
                params["filter.overallStatus"] = ",".join(s.strip().upper() for s in statuses)

            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for _ in range(_MAX_PAGES):
                data = await self._get("/studies", params)
                if not isinstance(data, dict):
                    break
                for study in data.get("studies", []) or []:
                    concept = self._convert_study_to_concept(study)
                    if concept and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
                token = data.get("nextPageToken")
                if len(concepts) >= limit or not token:
                    break
                params = {**params, "pageToken": token}
            logger.info(f"ClinicalTrials search for '{query}' returned {len(concepts)} studies")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"ClinicalTrials search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Fetch one study by NCT id (``NCT07753122`` or ``ClinicalTrials:NCT07753122``)."""
        study = await self._fetch_study(concept_id)
        return self._convert_study_to_concept(study) if study else None

    async def _fetch_study(self, concept_id: str) -> dict[str, Any] | None:
        nct = self._normalize_nct(concept_id)
        if not nct:
            return None
        try:
            data = await self._get(f"/studies/{nct}")
            return data if isinstance(data, dict) and data.get("protocolSection") else None
        except Exception as e:
            logger.warning(f"ClinicalTrials get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the study's conditions and interventions as edges.

        - ``studies_condition``: one edge per listed condition (``related_id`` is the
          condition text as registered) plus one per registry-assigned condition MeSH term
          (``related_id`` = ``MESH:D...``, ``derived=True``).
        - ``tests_intervention``: one edge per intervention (``related_id`` is the
          intervention name, ``related_type`` its registry type such as ``DRUG``,
          ``BEHAVIORAL``, ``DIETARY_SUPPLEMENT``) plus MeSH-derived edges.
        """
        study = await self._fetch_study(concept_id)
        if not study:
            return []
        try:
            data = self._parse_study(study)
            relationships: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(label: str, rid: str, name: str, rtype: str, **extra: Any) -> None:
                if not rid or (label, rid) in seen:
                    return
                seen.add((label, rid))
                relationships.append(
                    {
                        "relation_label": label,
                        "related_id": rid,
                        "related_name": name,
                        "related_type": rtype,
                        "source": "ClinicalTrials.gov",
                        **extra,
                    }
                )

            for condition in data["conditions"]:
                add("studies_condition", condition, condition, "condition")
            for mesh in data["condition_mesh"]:
                add(
                    "studies_condition",
                    f"MESH:{mesh['id']}",
                    mesh["term"],
                    "condition",
                    derived=True,
                )
            for intervention in data["interventions"]:
                extra: dict[str, Any] = {}
                if intervention.get("description"):
                    extra["description"] = intervention["description"]
                if intervention.get("arm_groups"):
                    extra["arm_groups"] = intervention["arm_groups"]
                add(
                    "tests_intervention",
                    intervention["name"],
                    intervention["name"],
                    intervention.get("type") or "OTHER",
                    **extra,
                )
            for mesh in data["intervention_mesh"]:
                add(
                    "tests_intervention",
                    f"MESH:{mesh['id']}",
                    mesh["term"],
                    "intervention",
                    derived=True,
                )
            return relationships
        except Exception as e:
            logger.warning(f"ClinicalTrials get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the MeSH terms the registry assigned to the study's conditions and
        interventions (algorithmic, so confidence is moderate)."""
        study = await self._fetch_study(concept_id)
        if not study:
            return []
        try:
            data = self._parse_study(study)
            nct = data["nct_id"]
            mappings: list[dict[str, Any]] = []
            for kind, key in (
                ("condition", "condition_mesh"),
                ("intervention", "intervention_mesh"),
            ):
                for mesh in data[key]:
                    mappings.append(
                        {
                            "fromId": nct,
                            "toId": f"MESH:{mesh['id']}",
                            "fromSource": "ClinicalTrials.gov",
                            "toSource": "MeSH",
                            "mappingType": f"{kind}_mesh",
                            "confidence": 0.8,
                        }
                    )
            return mappings
        except Exception as e:
            logger.warning(f"ClinicalTrials get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_study(study: dict[str, Any]) -> dict[str, Any]:
        """Flatten a v2 study record (full or field-restricted) into plain values."""
        proto = study.get("protocolSection", {}) or {}
        ident = proto.get("identificationModule", {}) or {}
        status = proto.get("statusModule", {}) or {}
        design = proto.get("designModule", {}) or {}
        desc = proto.get("descriptionModule", {}) or {}
        conds = proto.get("conditionsModule", {}) or {}
        arms = proto.get("armsInterventionsModule", {}) or {}
        sponsor = (proto.get("sponsorCollaboratorsModule", {}) or {}).get("leadSponsor", {}) or {}
        derived = study.get("derivedSection", {}) or {}
        enrollment = design.get("enrollmentInfo", {}) or {}

        interventions = []
        for item in arms.get("interventions", []) or []:
            name = item.get("name")
            if name:
                interventions.append(
                    {
                        "name": name,
                        "type": item.get("type"),
                        "description": item.get("description"),
                        "arm_groups": item.get("armGroupLabels") or [],
                    }
                )

        def meshes(module: str) -> list[dict[str, str]]:
            items = (derived.get(module, {}) or {}).get("meshes", []) or []
            return [{"id": m["id"], "term": m.get("term", "")} for m in items if m.get("id")]

        return {
            "nct_id": ident.get("nctId", ""),
            "brief_title": ident.get("briefTitle", ""),
            "official_title": ident.get("officialTitle"),
            "acronym": ident.get("acronym"),
            "brief_summary": desc.get("briefSummary"),
            "status": status.get("overallStatus"),
            "study_type": design.get("studyType"),
            "phases": design.get("phases") or [],
            "enrollment": enrollment.get("count"),
            "enrollment_type": enrollment.get("type"),
            "start_date": (status.get("startDateStruct") or {}).get("date"),
            "completion_date": (status.get("completionDateStruct") or {}).get("date"),
            "last_update": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
            "sponsor": sponsor.get("name"),
            "conditions": [c for c in conds.get("conditions", []) or [] if c],
            "keywords": conds.get("keywords") or [],
            "interventions": interventions,
            "condition_mesh": meshes("conditionBrowseModule"),
            "intervention_mesh": meshes("interventionBrowseModule"),
            "has_results": study.get("hasResults"),
        }

    def _convert_study_to_concept(self, study: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a v2 study record to a UnifiedConcept (``source_data`` keeps the fields)."""
        try:
            data = self._parse_study(study)
            nct, title = data["nct_id"], data["brief_title"]
            if not nct or not title:
                return None
            concept_type = _STUDY_TYPES.get(data["study_type"] or "", ConceptType.CLINICAL_STUDY)
            concept = self._create_concept(nct, title, concept_type)

            if data["brief_summary"] and concept.definitions is not None:
                concept.definitions.append(data["brief_summary"][:1000])
            if concept.synonyms is not None:
                for alt in (data["official_title"], data["acronym"]):
                    if alt and alt != title and alt not in concept.synonyms:
                        concept.synonyms.append(alt)
            if concept.categories is not None:
                if data["status"]:
                    concept.categories.append(f"status:{data['status']}")
                concept.categories.extend(f"phase:{p}" for p in data["phases"])
                concept.categories.extend(f"condition:{c}" for c in data["conditions"])
            if data["study_type"] and concept.semantic_types is not None:
                concept.semantic_types.append(data["study_type"])

            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.CLINICALTRIALS] = {
                    **data,
                    "url": f"https://clinicaltrials.gov/study/{nct}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting ClinicalTrials study: {e}")
            return None
