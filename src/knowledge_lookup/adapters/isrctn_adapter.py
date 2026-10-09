"""
ISRCTN Knowledge Source Adapter

Adapter for the ISRCTN registry (International Standard Randomised Controlled Trial Number),
the UK-based primary registry for clinical studies of any design (the PACE trial for ME/CFS
and many Long COVID studies are registered here). A registered *study* is the concept
(id ``ISRCTN12345678``, label = public title); conditions, interventions, sponsors and
funders are exposed as relationships.

API: ``https://www.isrctn.com/api/query/format/default?q=<query>&limit=<n>`` returns XML in
the ``http://www.67bricks.com/isrctn`` namespace (``allTrials/fullTrial``). The API is keyless;
no rate limit is documented, so requests are spaced at 2 per second. Data come from a
UK charity-run registry and are free to use with attribution to ISRCTN.

Quirks verified live (see the docs page):

* ``q`` is a Lucene-style query: plain words are OR-ed (``long covid`` matches 1,200 records),
  quotes make a phrase, and ``title:``, ``condition:``, ``intervention:`` and
  ``primaryStudyDesign:`` select a field, with ``AND``/``OR``. Other registry numbers work as
  plain queries (``NCT05057013`` finds the record that lists it).
* Only ``q`` and ``limit`` are honoured: ``offset``, ``page``, ``start`` and ``sort`` are silently
  ignored, so there is no paging and results are ordered by the server. Records are large
  (11-30 KB of XML each), so ``limit`` is capped at 100 (about 1.8 MB).
* ``api/trial/<id>/format/default`` answers HTTP 500 (an HTML error page) for a well-formed id
  that does not exist, which would trigger the shared retry loop. The adapter therefore
  fetches a record with ``q=<id>``, which returns an empty ``allTrials`` instead.
* The default format has no status field. The ``format/who`` format has ``recruitment_status``;
  the adapter derives it from the recruitment dates (and the ``...StatusOverride`` fields
  when a registrant set one), which matched the WHO value for 100 of 100 records checked.
* Records include contact persons with e-mail addresses and phone numbers. The adapter
  deliberately does not extract them.
"""

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

ISRCTN_BASE_URL = "https://www.isrctn.com"
QUERY_PATH = "/api/query/format/default"
RECORD_URL = "https://www.isrctn.com/{id}"

_NS = {"i": "http://www.67bricks.com/isrctn"}
_MAX_LIMIT = 100  # 100 records are already ~1.8 MB of XML
_MIN_INTERVAL = 0.5  # 2 requests/s; the API documents no limit
_MAX_TEXT = 1000
_MAX_ITEMS = 20

_ID_RE = re.compile(r"^ISRCTN[\s:_-]*(\d{8})$", re.IGNORECASE)
_NOT_PROVIDED = re.compile(r"^not provided|^not applicable$", re.IGNORECASE)

#: ``secondaryNumber/@numberType`` values that identify the same study in another registry.
#: value: (toSource, mappingType, confidence)
_REGISTRY_NUMBERS: dict[str, tuple[str, str, float]] = {
    "nct": ("CLINICALTRIALS", "same_study", 1.0),
    "euctr": ("EudraCT", "same_study", 1.0),
    "ctis": ("CTIS", "same_study", 1.0),
    "chictr": ("ChiCTR", "same_study", 1.0),
    "iras": ("IRAS", "secondary_id", 0.9),
    "cpms": ("CPMS", "secondary_id", 0.9),
}


def _text(node: ET.Element | None, path: str) -> str:
    """Stripped text of the first ``path`` match under ``node`` ('' if absent or empty)."""
    if node is None:
        return ""
    return (node.findtext(path, default="", namespaces=_NS) or "").strip()


def _texts(node: ET.Element | None, path: str) -> list[str]:
    if node is None:
        return []
    return [t for e in node.findall(path, _NS) if (t := (e.text or "").strip())]


def _clip(text: str, size: int = _MAX_TEXT) -> str:
    return text if len(text) <= size else text[: size - 3].rstrip() + "..."


class ISRCTNAdapter(KnowledgeSourceAdapter):
    """Adapter for the ISRCTN clinical trial registry (keyless XML API)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = ISRCTN_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._min_interval = _MIN_INTERVAL

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ISRCTN

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # HTTP / parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_id(concept_id: str) -> str | None:
        """``ISRCTN54285094`` from ``ISRCTN54285094`` / ``ISRCTN:54285094`` / ``isrctn 54285094``."""
        match = _ID_RE.match((concept_id or "").strip())
        return f"ISRCTN{match.group(1)}" if match else None

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).date().isoformat()

    async def _query(self, query: str, limit: int) -> tuple[int, list[dict[str, Any]]]:
        """Run a registry query; returns ``(totalCount, parsed trials)``."""
        async with self._throttle_lock:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        text = await self._make_request_text(
            f"{self.base_url}{QUERY_PATH}",
            {"q": query, "limit": min(limit, _MAX_LIMIT)},
            {"Accept": "application/xml"},
        )
        root = ET.fromstring(text)
        total = int(root.get("totalCount") or 0)
        trials = []
        for full in root.iter(f"{{{_NS['i']}}}fullTrial"):
            parsed = self._parse_full_trial(full, self._today())
            if parsed:
                trials.append(parsed)
        return total, trials

    async def _fetch(self, concept_id: str) -> dict[str, Any] | None:
        isrctn = self._normalize_id(concept_id)
        if not isrctn:
            return None
        try:
            _, trials = await self._query(isrctn, 3)
        except Exception as e:
            logger.warning(f"ISRCTN lookup failed for '{concept_id}': {e}")
            return None
        return next((t for t in trials if t["isrctn"] == isrctn), None)

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search registered studies with a Lucene-style query (see the module docstring:
        ``condition:fatigue``, ``"long covid"``, ``title:pacing AND intervention:exercise``).
        ``limit`` is capped at 100; the API has no paging."""
        if not query or not query.strip() or limit <= 0:
            return []
        try:
            total, trials = await self._query(query.strip(), limit)
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for trial in trials:
                concept = self._convert_trial_to_concept(trial)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
            logger.info(f"ISRCTN search for '{query}' returned {len(concepts)} of {total} studies")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"ISRCTN search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Fetch one study by id (``ISRCTN54285094`` or ``ISRCTN:54285094``)."""
        trial = await self._fetch(concept_id)
        return self._convert_trial_to_concept(trial) if trial else None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the study's conditions, interventions, sponsors and funders as edges.

        - ``studies_condition``: the registered condition text (``related_type``
          ``condition``), the registrant-chosen specific disease (``diseaseClass2``) and the
          broad disease category (``condition_category``, e.g. "Infections and Infestations").
        - ``tests_intervention``: one edge per named drug when the record lists drug names,
          otherwise one per intervention (``related_id`` is the start of its description;
          ``related_type`` its registry type such as ``Drug``, ``Behavioural``, ``Supplement``).
        - ``has_sponsor`` / ``funded_by``: organisations; ``related_id`` is the ROR id
          (``ROR:...``) when the registry has one, else the organisation name.
        """
        trial = await self._fetch(concept_id)
        if not trial:
            return []
        try:
            edges: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(label: str, rid: str, name: str, rtype: str, **extra: Any) -> None:
                if not rid or (label, rid) in seen:
                    return
                seen.add((label, rid))
                edges.append(
                    {
                        "relation_label": label,
                        "related_id": rid,
                        "related_name": name,
                        "related_type": rtype,
                        "source": "ISRCTN",
                        **extra,
                    }
                )

            for cond in trial["conditions"]:
                for name in cond["names"]:
                    add("studies_condition", name, name, "condition")
                if cond["disease_class2"]:
                    add(
                        "studies_condition",
                        cond["disease_class2"],
                        cond["disease_class2"],
                        "condition",
                        derived=True,
                    )
                if cond["disease_class1"]:
                    add(
                        "studies_condition",
                        cond["disease_class1"],
                        cond["disease_class1"],
                        "condition_category",
                        derived=True,
                    )
            for iv in trial["interventions"]:
                extra: dict[str, Any] = {"description": _clip(iv["description"], 500)}
                if iv["phase"]:
                    extra["phase"] = iv["phase"]
                rtype = iv["type"] or "Other"
                names = iv["drug_names"] or (
                    [_clip(" ".join(iv["description"].split()), 120)] if iv["description"] else []
                )
                for name in names:
                    add("tests_intervention", name, name, rtype, **extra)
            for org in trial["sponsors"]:
                add(
                    "has_sponsor",
                    org["id"],
                    org["name"],
                    "organisation",
                    commercial_status=org["commercial_status"],
                )
            for org in trial["funders"]:
                add("funded_by", org["id"], org["name"], "organisation")
            return edges
        except Exception as e:
            logger.warning(f"ISRCTN get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the other registry and protocol numbers the record lists.

        Registry numbers that identify the *same study* (ClinicalTrials.gov ``NCT``, EudraCT,
        CTIS, ChiCTR) have ``mappingType`` ``same_study``; IRAS/CPMS numbers, the DOI
        (``10.1186/ISRCTN...``) and sponsor or funder protocol codes are ``secondary_id``,
        ``doi`` and ``protocol_number``.
        """
        trial = await self._fetch(concept_id)
        if not trial:
            return []
        try:
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(to_source: str, to_id: str, mapping_type: str, confidence: float) -> None:
                if not to_id or (to_source, to_id) in seen:
                    return
                seen.add((to_source, to_id))
                mappings.append(
                    {
                        "fromId": trial["isrctn"],
                        "toId": to_id,
                        "fromSource": "ISRCTN",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": confidence,
                    }
                )

            refs = trial["external_refs"]
            add("CLINICALTRIALS", refs["nct"], "same_study", 1.0)
            add("EudraCT", refs["eudract"], "same_study", 1.0)
            for number in trial["secondary_numbers"]:
                kind = number["type"].lower()
                if kind in _REGISTRY_NUMBERS:
                    source, mapping_type, confidence = _REGISTRY_NUMBERS[kind]
                    value = number["value"]
                    if kind == "ctis":  # the canonical form adds the "-00" part suffix
                        value = re.sub(r"^CTIS", "", number["canonical"], flags=re.IGNORECASE)
                    elif kind in ("iras", "cpms"):
                        value = f"{source}:{value}"
                    add(source, value, mapping_type, confidence)
                else:
                    add(number["type"], number["value"], "protocol_number", 0.9)
            add("IRAS", f"IRAS:{refs['iras']}" if refs["iras"] else "", "secondary_id", 0.9)
            add("DOI", refs["doi"], "doi", 1.0)
            if not trial["secondary_numbers"]:
                add("Protocol", refs["protocol"], "protocol_number", 0.9)
            return mappings
        except Exception as e:
            logger.warning(f"ISRCTN get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Parsing / conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_status(
        start: str, end: str, start_override: str, status_override: str, today: str
    ) -> tuple[str | None, bool]:
        """``(status, derived)``: a registrant override wins, otherwise the status follows
        the recruitment dates (``YYYY-MM-DD`` strings compare correctly as text)."""
        if status_override:
            return status_override, False
        if start_override:
            return start_override, False
        if start and start > today:
            return "Not yet recruiting", True
        if end and end < today:
            return "No longer recruiting", True
        if start:
            return "Recruiting", True
        return None, True

    @classmethod
    def _parse_full_trial(cls, full: ET.Element, today: str) -> dict[str, Any] | None:
        """Flatten one ``fullTrial`` element (trial + referenced sponsors/funders)."""
        trial = full.find("i:trial", _NS)
        if trial is None:
            return None
        isrctn = trial.get("publicIdentifierCanonical") or ""
        if not isrctn and _text(trial, "i:isrctn"):
            isrctn = f"ISRCTN{_text(trial, 'i:isrctn')}"
        desc = trial.find("i:trialDescription", _NS)
        title = _text(desc, "i:title")
        if not isrctn or not title:
            return None
        design = trial.find("i:trialDesign", _NS)
        part = trial.find("i:participants", _NS)
        refs = trial.find("i:externalRefs", _NS)
        results = trial.find("i:results", _NS)

        def dates(path: str) -> str:
            return _text(part, path)[:10]

        start, end = dates("i:recruitmentStart"), dates("i:recruitmentEnd")
        status, derived = cls._derive_status(
            start,
            end,
            _text(part, "i:recruitmentStartStatusOverride"),
            _text(part, "i:recruitmentStatusOverride"),
            today,
        )

        def outcomes(kind: str) -> list[dict[str, str]]:
            items = [
                {
                    "measure": _clip(_text(m, "i:variable"), 500),
                    "method": _clip(_text(m, "i:method"), 500),
                    "timepoints": _text(m, "i:timepoints"),
                }
                for m in (
                    desc.findall(f"i:{kind}Outcomes/i:outcomeMeasure", _NS)
                    if desc is not None
                    else []
                )
            ]
            legacy = _text(desc, f"i:{kind}Outcome")  # records from before structured outcomes
            if legacy:
                items.append({"measure": _clip(legacy, 500), "method": "", "timepoints": ""})
            return items[:_MAX_ITEMS]

        interventional = (
            design.find("i:interventionalTrialDesign", _NS) if design is not None else None
        )
        study_design = {
            "primary": _text(design, "i:primaryStudyDesign"),
            "secondary": _text(design, "i:secondaryStudyDesign"),
            "description": _text(design, "i:studyDesign"),
            "allocation": _text(interventional, "i:allocation"),
            "masking": _text(interventional, "i:masking"),
            "control": _text(interventional, "i:control"),
            "assignment": _text(interventional, "i:assignment"),
            "purposes": _texts(interventional, "i:purposes/i:purpose")
            or _texts(design, "i:trialTypes/i:trialType"),
        }

        def orgs(tag: str, ids_path: str, name_path: str) -> list[dict[str, str]]:
            by_id = {e.get("id"): e for e in full.findall(f"i:{tag}", _NS)}
            wanted = _texts(trial, ids_path)
            elements = [by_id[i] for i in wanted if i in by_id] or list(by_id.values())
            out = []
            for el in elements:
                name = _text(el, name_path)
                if not name:
                    continue
                ror = _text(el, "i:rorId")
                fundref = _text(el, "i:fundRef")
                ror_id = "ROR:" + ror.rsplit("/", 1)[-1] if ror else ""
                out.append(
                    {
                        "name": name,
                        "id": ror_id or name,
                        "ror": ror,
                        "fundref": fundref,
                        "type": _text(el, "i:sponsorType"),
                        "commercial_status": _text(el, "i:commercialStatus"),
                    }
                )
            return out

        conditions = [
            {
                "description": _text(c, "i:description"),
                # registrants often list several conditions, one per line
                "names": [
                    ln.strip() for ln in _text(c, "i:description").splitlines() if ln.strip()
                ],
                "disease_class1": _text(c, "i:diseaseClass1"),
                "disease_class2": _text(c, "i:diseaseClass2"),
            }
            for c in trial.findall("i:conditions/i:condition", _NS)
            if _text(c, "i:description")
        ]
        interventions = [
            {
                "description": _text(iv, "i:description"),
                "type": _text(iv, "i:interventionType"),
                "phase": _text(iv, "i:phase"),
                "drug_names": [
                    d.strip() for d in re.split(r"[;,]", _text(iv, "i:drugNames")) if d.strip()
                ],
            }
            for iv in trial.findall("i:interventions/i:intervention", _NS)
        ]
        secondary_numbers = [
            {
                "type": n.get("numberType") or "",
                "value": (n.text or "").strip(),
                "canonical": n.get("canonicalSecondaryNumber") or (n.text or "").strip(),
            }
            for n in trial.findall("i:externalRefs/i:secondaryNumbers/i:secondaryNumber", _NS)
            if (n.text or "").strip()
        ]
        summary = _text(desc, "i:plainEnglishSummary")
        hypothesis = _text(desc, "i:studyHypothesis")
        return {
            "isrctn": isrctn,
            "title": title,
            "scientific_title": _text(desc, "i:scientificTitle"),
            "acronym": _text(desc, "i:acronym"),
            "summary": "" if _NOT_PROVIDED.match(summary) else summary,
            "hypothesis": "" if _NOT_PROVIDED.match(hypothesis) else hypothesis,
            "primary_outcomes": outcomes("primary"),
            "secondary_outcomes": outcomes("secondary"),
            "study_design": study_design,
            "status": status,
            "status_derived": derived,
            "recruitment_start": start,
            "recruitment_end": end,
            "overall_end": _text(design, "i:overallEndDate")[:10],
            "target_enrolment": _text(part, "i:targetEnrolment"),
            "final_enrolment": _text(part, "i:totalFinalEnrolment"),
            "countries": _texts(part, "i:recruitmentCountries/i:country"),
            "centres": _texts(part, "i:trialCentres/i:trialCentre/i:name")[:_MAX_ITEMS],
            "gender": _text(part, "i:gender"),
            "age_range": _text(part, "i:ageRange"),
            "healthy_volunteers": _text(part, "i:healthyVolunteersAllowed"),
            "conditions": conditions,
            "interventions": interventions,
            "sponsors": orgs("sponsor", "i:parties/i:sponsorId", "i:organisation"),
            "funders": orgs("funder", "i:parties/i:funderId", "i:name"),
            "external_refs": {
                "doi": _text(refs, "i:doi"),
                "nct": _text(refs, "i:clinicalTrialsGovNumber"),
                "eudract": _text(refs, "i:eudraCTNumber"),
                "iras": _text(refs, "i:irasNumber"),
                "protocol": _text(refs, "i:protocolSerialNumber"),
            },
            "secondary_numbers": secondary_numbers,
            "publication_stage": _text(results, "i:publicationStage"),
            "publication_details": _clip(_text(results, "i:publicationDetails")),
            "date_assigned": (trial.get("publicIdentifierDateAssigned") or "")[:10],
            "last_updated": (trial.get("lastUpdated") or "")[:10],
            "version": trial.get("version"),
        }

    def _convert_trial_to_concept(self, trial: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a parsed trial to a UnifiedConcept (``source_data`` keeps all fields)."""
        try:
            isrctn, title = trial["isrctn"], trial["title"]
            primary = trial["study_design"]["primary"].lower()
            concept_type = {
                "interventional": ConceptType.CLINICAL_TRIAL,
                "observational": ConceptType.OBSERVATIONAL_STUDY,
            }.get(primary, ConceptType.CLINICAL_STUDY)
            concept = self._create_concept(isrctn, title, concept_type)

            summary = trial["summary"] or trial["hypothesis"]
            if summary and concept.definitions is not None:
                concept.definitions.append(_clip(summary))
            if concept.synonyms is not None:
                for alt in (trial["scientific_title"], trial["acronym"]):
                    if alt and alt != title and alt not in concept.synonyms:
                        concept.synonyms.append(alt)
            if concept.categories is not None:
                if trial["status"]:
                    concept.categories.append(f"status:{trial['status']}")
                for iv in trial["interventions"]:
                    if iv["phase"] and f"phase:{iv['phase']}" not in concept.categories:
                        concept.categories.append(f"phase:{iv['phase']}")
                concept.categories.extend(
                    f"condition:{name}" for c in trial["conditions"] for name in c["names"]
                )
            if concept.semantic_types is not None:
                concept.semantic_types.extend(
                    s
                    for s in (trial["study_design"]["primary"], trial["study_design"]["secondary"])
                    if s
                )
            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.ISRCTN] = {
                    **trial,
                    "url": RECORD_URL.format(id=isrctn),
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting ISRCTN trial: {e}")
            return None
