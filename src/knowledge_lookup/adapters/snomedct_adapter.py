"""
SNOMED CT (Snowstorm) Knowledge Source Adapter

Adapter for a Snowstorm terminology server, the open-source SNOMED CT server that
SNOMED International runs behind its public browser and that national release centres
and hospitals self-host.

LICENCE -- read this before using the adapter at scale
------------------------------------------------------
SNOMED CT is *not* open data. It is owned by SNOMED International and distributed
under the SNOMED CT Affiliate Licence:

- Free for use in SNOMED International member countries under their national licence
  (Germany is a member; the German edition and licence are handled by BfArM). Check
  your own country's terms.
- Elsewhere an Affiliate Licence (usually free for research, but you must register
  and accept the terms) is required.
- The default endpoint, SNOMED International's public browser instance, is a
  demonstration server: rate-limited, no SLA and *not for bulk or production use*.
  Point ``SNOMED_SNOWSTORM_URL`` at a national or self-hosted server for real
  workloads. This adapter spaces requests ~1 s apart on the public instance.
- Do not redistribute SNOMED CT content (labels, hierarchies) with your dataset
  without checking the licence for your jurisdiction.

Configuration (environment variables)
-------------------------------------
``SNOMED_SNOWSTORM_URL``
    Server base URL (default ``https://browser.ihtsdotools.org/snowstorm/snomed-ct``).
``SNOMED_SNOWSTORM_BRANCH``
    Code-system branch (default ``MAIN`` = latest International Edition). National
    extensions live under their own branch, e.g. ``MAIN/SNOMEDCT-DE``; dated releases
    under ``MAIN/<yyyy-mm-dd>``. ``GET {base}/codesystems`` lists the branch paths.

STATUS: NOT LIVE-VERIFIED
-------------------------
The public instance refused every connection from the development network
(``Connection refused`` from ``browser.ihtsdotools.org`` and ``snowstorm.ihtsdotools.org``
on port 443), so the response parsing follows Snowstorm's documented REST/JSON schema
and is covered by unit tests against fixtures that mirror that schema, not against
captured responses. Verify with ``knowledge-lookup check SNOMEDCT`` from a network that
can reach the server before relying on it.

Endpoints used (Snowstorm REST API, ``{base}/swagger-ui``):

- ``GET /{branch}/descriptions?term=&active=true&conceptActive=true&groupByConcept=true``
  -- description search; each item embeds its concept (``conceptId``, ``fsn.term``,
  ``pt.term``).
- ``GET /browser/{branch}/concepts/{id}`` -- concept with all descriptions and
  relationships (is-a and attributes).
- ``GET /{branch}/concepts/{id}/children?form=inferred`` / ``.../parents`` -- is-a
  neighbours as concept minis.
- ``GET /{branch}/members?referenceSet=447562003&referencedComponentId=`` -- ICD-10
  complex map members (mappings).

Identifiers: SCTIDs. ``SNOMEDCT:84229001``, ``SNOMED:84229001`` and ``84229001`` are
accepted. Examples: 84229001 (fatigue), 52448006 (dementia).
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

DEFAULT_SNOWSTORM_URL = "https://browser.ihtsdotools.org/snowstorm/snomed-ct"
DEFAULT_BRANCH = "MAIN"
ENV_URL = "SNOMED_SNOWSTORM_URL"
ENV_BRANCH = "SNOMED_SNOWSTORM_BRANCH"
USER_AGENT = (
    "AID-PAIS-Knowledge-Lookup/1.0 (biomedical-knowledge-lookup; research use; "
    "low-volume SNOMED CT lookups)"
)

IS_A_TYPE_ID = "116680003"
ICD10_MAP_REFSET = "447562003"  # ICD-10 complex map reference set

_SCTID_RE = re.compile(r"^\d{6,18}$")
_PREFIX_RE = re.compile(r"^(?:SNOMEDCT(?:_US)?|SNOMED(?:CT)?|SCTID)\s*:\s*", re.IGNORECASE)
_SEMANTIC_TAG_RE = re.compile(r"\(([^()]+)\)\s*$")

# Seconds between requests: gentle on the public demo server, relaxed on private ones.
_PUBLIC_INTERVAL = 1.0
_PRIVATE_INTERVAL = 0.1

_TAG_TYPES: dict[str, ConceptType] = {
    "disorder": ConceptType.DISEASE,
    "finding": ConceptType.PHENOTYPE,
    "morphologic abnormality": ConceptType.PHENOTYPE,
    "procedure": ConceptType.PROCEDURE,
    "regime/therapy": ConceptType.TREATMENT,
    "body structure": ConceptType.ANATOMICAL_ENTITY,
    "cell": ConceptType.CELL_TYPE,
    "cell structure": ConceptType.CELLULAR_COMPONENT,
    "organism": ConceptType.ORGANISM,
    "substance": ConceptType.CHEMICAL,
    "medicinal product": ConceptType.DRUG,
    "medicinal product form": ConceptType.DRUG,
    "clinical drug": ConceptType.DRUG,
    "product": ConceptType.DRUG,
    "observable entity": ConceptType.OBSERVATION,
}


def _term(node: Any) -> str:
    """``{"term": "..."}`` (Snowstorm's fsn/pt objects) -> the term, tolerating plain strings."""
    if isinstance(node, dict):
        return str(node.get("term") or "")
    return str(node) if isinstance(node, str) else ""


def _semantic_tag(fsn: str) -> str | None:
    match = _SEMANTIC_TAG_RE.search(fsn)
    return match.group(1).strip().lower() if match else None


def _label_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


class SnomedCTAdapter(KnowledgeSourceAdapter):
    """Adapter for SNOMED CT through a Snowstorm server (see module docstring for the licence).

    SNOMED CT is distributed under the SNOMED International Affiliate Licence (national
    licences apply in member countries such as Germany). The default public browser
    instance is rate-limited and not meant for bulk use; set ``SNOMED_SNOWSTORM_URL``
    to a national or self-hosted server for anything beyond occasional lookups.
    """

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._concept_cache: dict[str, dict[str, Any]] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.SNOMEDCT

    def is_available(self) -> bool:
        return True  # needs no key; availability of the server is discovered per request

    # ------------------------------------------------------------------
    # Configuration / identifiers
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """Server base URL, re-read each time so tests/users can change the env var."""
        return (os.getenv(ENV_URL) or DEFAULT_SNOWSTORM_URL).strip().rstrip("/")

    @property
    def branch(self) -> str:
        return (os.getenv(ENV_BRANCH) or DEFAULT_BRANCH).strip().strip("/")

    @staticmethod
    def normalize_id(concept_id: str) -> str | None:
        """Return the bare SCTID or ``None`` if the input is not one."""
        if not isinstance(concept_id, str):
            return None
        bare = _PREFIX_RE.sub("", concept_id.strip()).strip()
        return bare if _SCTID_RE.match(bare) else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search active descriptions (any term) and return their active concepts.

        Results are grouped by concept (a concept matching on several synonyms appears
        once) in Snowstorm's relevance order. A bare SCTID query returns that concept.
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            direct = self.normalize_id(query)
            if direct:
                concept = await self.get_concept_details(direct)
                return [concept] if concept else []

            data = await self._get(
                f"{self.base_url}/{self.branch}/descriptions",
                {
                    "term": query,
                    "active": "true",
                    "conceptActive": "true",
                    "groupByConcept": "true",
                    "limit": min(max(limit * 2, 10), 100),
                },
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in data.get("items") or []:
                mini = item.get("concept") or {}
                ident = str(mini.get("conceptId") or item.get("conceptId") or "")
                if not ident or ident in seen:
                    continue
                seen.add(ident)
                concept = self._concept_from_mini(ident, mini, matched_term=item.get("term"))
                if concept:
                    concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"SNOMED CT search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"SNOMED CT search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full concept (descriptions, synonyms, FSN, module, status) via the browser API."""
        ident = self.normalize_id(concept_id)
        if not ident:
            logger.warning(f"SNOMED CT: '{concept_id}' is not an SCTID")
            return None
        try:
            data = await self._browser_concept(ident)
            return self._concept_from_browser(ident, data) if data else None
        except Exception as e:
            logger.error(f"SNOMED CT get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Is-a neighbours and attribute relationships (inferred form).

        - ``is_a`` -- the related concept is a parent of the queried concept.
        - ``has_subtype`` -- the related concept is a child (needs one extra request;
          capped by ``limit``, large hierarchies such as *Clinical finding* have
          thousands of children).
        - attribute edges named after the attribute, lower-cased and underscored
          (``finding_site``, ``associated_morphology``, ``causative_agent`` ...); the
          SNOMED role group is reported as ``group``.
        """
        ident = self.normalize_id(concept_id)
        if not ident or limit <= 0:
            return []
        try:
            data = await self._browser_concept(ident)
            if not data:
                return []
            parents: list[dict[str, Any]] = []
            attributes: list[dict[str, Any]] = []
            for rel in data.get("relationships") or []:
                if not rel.get("active", True) or not self._is_inferred(rel):
                    continue
                target = rel.get("target") or {}
                target_id = str(target.get("conceptId") or rel.get("destinationId") or "")
                if not target_id:
                    continue
                type_id = str((rel.get("type") or {}).get("conceptId") or rel.get("typeId") or "")
                name = _term(target.get("pt")) or self._strip_tag(_term(target.get("fsn")))
                if type_id == IS_A_TYPE_ID:
                    parents.append(self._edge("is_a", target_id, name))
                else:
                    attr = (rel.get("type") or {}).get("pt") or (rel.get("type") or {}).get("fsn")
                    label = _label_key(self._strip_tag(_term(attr))) or f"attribute_{type_id}"
                    edge = self._edge(label, target_id, name)
                    edge["group"] = rel.get("groupId", 0)
                    edge["attribute_id"] = type_id
                    attributes.append(edge)

            children = await self._children(ident)
            # Children last: they are the unbounded part, so `limit` trims them first.
            edges = parents + attributes
            edges += [self._edge("has_subtype", c[0], c[1]) for c in children]
            return self._dedupe(edges)[:limit]
        except Exception as e:
            logger.warning(f"SNOMED CT get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """ICD-10 mappings from the International Edition's complex map reference set.

        Not live-verified (see module docstring). Returns ``[]`` when the server's
        edition carries no map members (national extensions often use their own maps).
        """
        ident = self.normalize_id(concept_id)
        if not ident:
            return []
        try:
            data = await self._get(
                f"{self.base_url}/{self.branch}/members",
                {
                    "referenceSet": ICD10_MAP_REFSET,
                    "referencedComponentId": ident,
                    "active": "true",
                    "limit": 50,
                },
            )
            mappings: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in data.get("items") or []:
                fields = item.get("additionalFields") or {}
                target = str(fields.get("mapTarget") or "").strip()
                if not target or target in seen:
                    continue
                seen.add(target)
                mappings.append(
                    {
                        "fromId": ident,
                        "toId": target,
                        "fromSource": "SNOMEDCT",
                        "toSource": "ICD10",
                        "mappingType": "icd10_complex_map",
                        "confidence": 0.8,
                        "mapGroup": fields.get("mapGroup"),
                        "mapPriority": fields.get("mapPriority"),
                        "mapRule": fields.get("mapRule"),
                        "mapAdvice": fields.get("mapAdvice"),
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"SNOMED CT get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Throttled GET with the Snowstorm headers; returns JSON (list wrapped as ``items``)."""
        interval = (
            _PUBLIC_INTERVAL if self.base_url == DEFAULT_SNOWSTORM_URL else _PRIVATE_INTERVAL
        )
        async with self._throttle_lock:
            wait = self._last_request + interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(
            url,
            params,
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
                "User-Agent": USER_AGENT,
            },
        )
        if isinstance(data, list):
            return {"items": data}
        return data if isinstance(data, dict) else {}

    async def _browser_concept(self, ident: str) -> dict[str, Any] | None:
        """Browser concept view (descriptions + relationships), cached per adapter."""
        key = f"{self.base_url}|{self.branch}|{ident}"
        if key in self._concept_cache:
            return self._concept_cache[key]
        data = await self._get(f"{self.base_url}/browser/{self.branch}/concepts/{ident}")
        if not data.get("conceptId"):
            return None
        if len(self._concept_cache) >= 64:
            self._concept_cache.pop(next(iter(self._concept_cache)))
        self._concept_cache[key] = data
        return data

    async def _children(self, ident: str) -> list[tuple[str, str]]:
        data = await self._get(
            f"{self.base_url}/{self.branch}/concepts/{ident}/children", {"form": "inferred"}
        )
        out: list[tuple[str, str]] = []
        for item in data.get("items") or []:
            cid = str(item.get("conceptId") or "")
            if cid:
                name = _term(item.get("pt")) or self._strip_tag(_term(item.get("fsn")))
                out.append((cid, name))
        return out

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_tag(fsn: str) -> str:
        return _SEMANTIC_TAG_RE.sub("", fsn).strip()

    @staticmethod
    def _is_inferred(rel: dict[str, Any]) -> bool:
        char = str(rel.get("characteristicType") or "INFERRED_RELATIONSHIP")
        return char.upper().startswith("INFERRED")

    @staticmethod
    def _edge(label: str, related_id: str, name: str) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": related_id,
            "related_name": name or related_id,
            "source": "SNOMEDCT",
        }

    @staticmethod
    def _dedupe(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, Any]] = set()
        out: list[dict[str, Any]] = []
        for e in edges:
            key = (e["relation_label"], e["related_id"], e.get("group"))
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out

    def _base_concept(
        self, ident: str, label: str, fsn: str, active: Any, extra: dict[str, Any]
    ) -> UnifiedConcept:
        tag = _semantic_tag(fsn)
        concept = self._create_concept(
            ident, label, _TAG_TYPES.get(tag or "", ConceptType.UNKNOWN)
        )
        if concept.identifiers:
            concept.identifiers[
                0
            ].url = f"https://browser.ihtsdotools.org/?perspective=full&conceptId1={ident}"
        if tag:
            concept.semantic_types = [tag]
        concept.source_data[KnowledgeSource.SNOMEDCT] = {  # type: ignore[index]
            "sctid": ident,
            "fsn": fsn,
            "semantic_tag": tag,
            "active": active,
            "branch": self.branch,
            **extra,
        }
        return concept

    def _concept_from_mini(
        self, ident: str, mini: dict[str, Any], matched_term: str | None = None
    ) -> UnifiedConcept | None:
        """Concept from a Snowstorm ``ConceptMini`` (search hit)."""
        fsn = _term(mini.get("fsn"))
        label = _term(mini.get("pt")) or self._strip_tag(fsn) or (matched_term or "")
        if not label:
            return None
        concept = self._base_concept(ident, label, fsn, mini.get("active"), {})
        if matched_term and matched_term.lower() != label.lower():
            concept.synonyms = [matched_term]
        return concept

    def _concept_from_browser(self, ident: str, data: dict[str, Any]) -> UnifiedConcept | None:
        """Concept from the browser view: PT, FSN, synonyms and text definitions."""
        fsn = _term(data.get("fsn"))
        label = _term(data.get("pt")) or self._strip_tag(fsn)
        if not label:
            return None
        concept = self._base_concept(
            ident,
            label,
            fsn,
            data.get("active"),
            {
                "definition_status": data.get("definitionStatus"),
                "module_id": data.get("moduleId"),
                "effective_time": data.get("effectiveTime"),
            },
        )
        seen = {label.lower(), self._strip_tag(fsn).lower()}
        for desc in data.get("descriptions") or []:
            if not desc.get("active", True):
                continue
            lang = desc.get("lang") or desc.get("languageCode")
            if lang and lang != "en":
                continue
            term = str(desc.get("term") or "").strip()
            dtype = str(desc.get("type") or "").upper()
            if not term:
                continue
            if dtype == "TEXT_DEFINITION":
                concept.definitions.append(term)  # type: ignore[union-attr]
            elif dtype == "SYNONYM" and term.lower() not in seen:
                seen.add(term.lower())
                concept.synonyms.append(term)  # type: ignore[union-attr]
        return concept
