"""
FHIR terminology server adapter.

A generic client for HL7 FHIR R4 terminology servers (``CodeSystem/$lookup``,
``ValueSet/$expand``, ``CodeSystem/$validate-code``, ``ConceptMap/$translate``). One adapter
therefore reaches whatever code systems the configured server hosts: SNOMED CT, LOINC,
ICD-10 / ICD-10-CM / ICD-11, ATC, RxNorm, UCUM, HPO ... on the public servers, and ICD-10-GM,
OPS, LOINC, SNOMED CT and ATC on a German MII terminology server (same API, usually behind
authentication).

Configuration (all optional):

* ``FHIR_TERMINOLOGY_URL``: base URL, default ``https://tx.fhir.org/r4`` (public, keyless).
  ``https://r4.ontoserver.csiro.au/fhir`` (CSIRO Ontoserver, SNOMED CT AU) is also keyless.
* ``FHIR_TERMINOLOGY_SYSTEMS``: comma-separated code systems searched by default, as an alias
  (``snomed``, ``loinc``, ``icd10gm``, ...) or a full system URI. ``alias@version`` pins a
  version (``atc@2025.0.0``). Without it ``search_concepts`` queries SNOMED CT, ICD-10-CM
  and LOINC. ``search_concepts(..., systems=[...])`` overrides it per call.
* ``FHIR_TERMINOLOGY_TOKEN``: sent as ``Authorization: Bearer`` when set.
  ``FHIR_TERMINOLOGY_USER`` + ``FHIR_TERMINOLOGY_PASSWORD``: HTTP Basic, only when both are
  set (a token wins). Nothing is ever sent by default, and credentials are refused for plain
  ``http://`` servers other than localhost.

Identifiers: concepts are addressed as ``<system>|<code>``, where ``<system>`` is an alias or
a URI: ``loinc|2093-3``, ``http://snomed.info/sct|84229001``, ``icd10gm|G93.3``. A third
segment pins the code-system version (``atc|N02BA01|2025.0.0``), which servers hosting
several versions need (Ontoserver answers 422 "more than one Resource" for unpinned ATC).
Results use the alias form where the system is known.

Quirks verified live (see the docs page): servers disagree on which code systems exist
(tx.fhir.org has no ICD-10-GM, OPS or HPO; Ontoserver has no WHO ICD-10 or MONDO), report
an unknown system as 422 (tx.fhir.org) or 404 (Ontoserver), and support implicit value sets
(``url=<system>?fhir_vs``) only for some systems. The documented fallback for that is an
inline ``ValueSet`` with ``compose.include.system`` posted to ``$expand``, which both servers
accept for every system they host. ``$translate`` is only implemented with real mappings on
Ontoserver (SNOMED CT to ICD-10-AM, MedDRA, Read); tx.fhir.org answers "no ConceptMap".

Licences: the servers are public services, but SNOMED CT, LOINC, ICD-11 and similar content
they return is licensed by its owner (SNOMED International / national release centres,
Regenstrief, WHO, BfArM for ICD-10-GM and OPS); using it outside what your own licence
covers is your responsibility. Requests are spaced at 2 per second.
"""

import asyncio
import base64
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://tx.fhir.org/r4"
DEFAULT_SEARCH_SYSTEMS = ("snomed", "icd10cm", "loinc")

_MIN_INTERVAL = 0.5  # 2 requests/s, polite towards the free public servers
_MAX_SEARCH = 200
_MAX_SYNONYMS = 50
_MAX_LIST = 100
_LOOKUP_PROPERTIES = ("*", "parent", "child")  # servers differ: '*' alone omits children
_SKIP_PROPERTIES = {"RELATEDNAMES2", "normalForm", "normalFormTerse"}
_SNOMED_DEFINITION_USE = "900000000000550004"
_SNOMED_FSN_USE = "900000000000003001"
_SYNONYM_LANGUAGES = ("en", "de")

#: Alias -> (system URI, default concept type). Keys are normalised (lower case, letters and
#: digits only), so ``ICD-10-GM`` and ``icd10gm`` are the same alias.
_SYSTEMS: dict[str, tuple[str, ConceptType]] = {
    "loinc": ("http://loinc.org", ConceptType.OBSERVATION),
    "snomed": ("http://snomed.info/sct", ConceptType.UNKNOWN),
    "snomedct": ("http://snomed.info/sct", ConceptType.UNKNOWN),
    "sct": ("http://snomed.info/sct", ConceptType.UNKNOWN),
    "icd10": ("http://hl7.org/fhir/sid/icd-10", ConceptType.DISEASE),
    "icd10cm": ("http://hl7.org/fhir/sid/icd-10-cm", ConceptType.DISEASE),
    "icd10gm": ("http://fhir.de/CodeSystem/bfarm/icd-10-gm", ConceptType.DISEASE),
    "icd11": ("http://id.who.int/icd/release/11/mms", ConceptType.DISEASE),
    "ops": ("http://fhir.de/CodeSystem/bfarm/ops", ConceptType.PROCEDURE),
    "atc": ("http://www.whocc.no/atc", ConceptType.DRUG),
    "rxnorm": ("http://www.nlm.nih.gov/research/umls/rxnorm", ConceptType.DRUG),
    "ucum": ("http://unitsofmeasure.org", ConceptType.UNKNOWN),
    "hpo": ("http://purl.obolibrary.org/obo/hp.owl", ConceptType.PHENOTYPE),
    "hp": ("http://purl.obolibrary.org/obo/hp.owl", ConceptType.PHENOTYPE),
    "mondo": ("http://purl.obolibrary.org/obo/mondo.owl", ConceptType.DISEASE),
    "cvx": ("http://hl7.org/fhir/sid/cvx", ConceptType.DRUG),
}

#: Preferred alias per URI (first match), used when formatting identifiers.
_URI_ALIAS: dict[str, str] = {}
for _alias, (_uri, _ctype) in _SYSTEMS.items():
    _URI_ALIAS.setdefault(_uri, _alias)

#: System URI -> the library's native source, so concepts also carry e.g. a LOINC identifier.
_URI_SOURCE: dict[str, KnowledgeSource] = {
    "http://loinc.org": KnowledgeSource.LOINC,
    "http://snomed.info/sct": KnowledgeSource.SNOMEDCT,
    "http://fhir.de/CodeSystem/bfarm/icd-10-gm": KnowledgeSource.ICD10GM,
    "http://id.who.int/icd/release/11/mms": KnowledgeSource.ICD11,
    "http://www.nlm.nih.gov/research/umls/rxnorm": KnowledgeSource.RXNORM,
    "http://purl.obolibrary.org/obo/hp.owl": KnowledgeSource.HPO,
    "http://purl.obolibrary.org/obo/mondo.owl": KnowledgeSource.MONDO,
}

#: SNOMED CT semantic tag (from the fully specified name) -> concept type.
_SNOMED_TAGS: dict[str, ConceptType] = {
    "disorder": ConceptType.DISEASE,
    "finding": ConceptType.SYMPTOM,
    "procedure": ConceptType.PROCEDURE,
    "substance": ConceptType.CHEMICAL,
    "medicinal product": ConceptType.DRUG,
    "product": ConceptType.DRUG,
    "body structure": ConceptType.ANATOMICAL_ENTITY,
    "organism": ConceptType.ORGANISM,
    "observable entity": ConceptType.OBSERVATION,
}

#: FHIR ConceptMap equivalence (R4) / relationship (R5) -> (mapping type, confidence).
_EQUIVALENCE: dict[str, tuple[str, float]] = {
    "equal": ("exactMatch", 1.0),
    "equivalent": ("exactMatch", 0.9),
    "wider": ("broadMatch", 0.7),
    "subsumes": ("broadMatch", 0.6),
    "narrower": ("narrowMatch", 0.7),
    "specializes": ("narrowMatch", 0.6),
    "inexact": ("closeMatch", 0.6),
    "relatedto": ("relatedMatch", 0.5),
    "related-to": ("relatedMatch", 0.5),
    "source-is-narrower-than-target": ("broadMatch", 0.7),
    "source-is-broader-than-target": ("narrowMatch", 0.7),
}

_URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_TAG_RE = re.compile(r"\(([^()]+)\)\s*$")


@dataclass(frozen=True)
class SystemSpec:
    """A code system to query: its URI and an optionally pinned version."""

    uri: str
    version: str | None = None


def _norm_alias(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def resolve_system(token: str) -> SystemSpec | None:
    """Resolve ``loinc``, ``ICD-10-GM``, ``icd10gm@2020`` or a system URI to a spec.

    A ``@version`` suffix pins the code-system version. Unknown aliases return ``None``.
    """
    text = (token or "").strip()
    if not text:
        return None
    left, _, version = text.partition("@")
    left = left.strip()
    entry = _SYSTEMS.get(_norm_alias(left))
    if entry is not None and not _URI_RE.match(left):
        uri = entry[0]
    elif _URI_RE.match(left):
        uri = left
    else:
        return None
    return SystemSpec(uri, version.strip() or None)


def _value(part: dict[str, Any]) -> Any:
    """The ``value[x]`` of a FHIR Parameters entry, whichever type it is."""
    for key, val in part.items():
        if key.startswith("value"):
            return val
    return None


class FHIRTerminologyAdapter(KnowledgeSourceAdapter):
    """Generic HL7 FHIR R4 terminology server client (tx.fhir.org by default)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        base = (os.getenv("FHIR_TERMINOLOGY_URL") or "").strip() or DEFAULT_BASE_URL
        self.base_url = base.rstrip("/")
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._min_interval = _MIN_INTERVAL
        # per (system, version): True once the implicit value set failed and the inline
        # fallback is needed, so later searches skip the doomed first request
        self._inline_expand: dict[tuple[str, str | None], bool] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.FHIRTERMINOLOGY

    def is_available(self) -> bool:
        return True  # public default server; the URL and credentials are optional

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Authorization header from the optional env vars; empty when unset or unsafe."""
        token = (
            os.getenv("FHIR_TERMINOLOGY_TOKEN")
            or self.config.get_api_key("fhir_terminology_token")
            or ""
        ).strip()
        user = os.getenv("FHIR_TERMINOLOGY_USER") or ""
        password = os.getenv("FHIR_TERMINOLOGY_PASSWORD") or ""
        if token:
            header = f"Bearer {token}"
        elif user and password:
            raw = f"{user}:{password}".encode()
            header = "Basic " + base64.b64encode(raw).decode("ascii")
        else:
            return {}
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            logger.warning(
                "FHIR terminology credentials are set but the server URL is not https; "
                "not sending them"
            )
            return {}
        return {"Authorization": header}

    def _configured_systems(self) -> list[SystemSpec]:
        raw = os.getenv("FHIR_TERMINOLOGY_SYSTEMS") or ""
        return self._parse_systems(raw.split(",")) if raw.strip() else []

    @staticmethod
    def _parse_systems(tokens: list[str]) -> list[SystemSpec]:
        specs: list[SystemSpec] = []
        for token in tokens:
            spec = resolve_system(token)
            if spec is None:
                if token.strip():
                    logger.warning(f"FHIR terminology: unknown code system '{token.strip()}'")
                continue
            if spec not in specs:
                specs.append(spec)
        return specs

    def _search_systems(self, systems: str | list[str] | None) -> list[SystemSpec]:
        if isinstance(systems, str):
            systems = systems.split(",")
        if systems:
            return self._parse_systems(list(systems))
        return self._configured_systems() or self._parse_systems(list(DEFAULT_SEARCH_SYSTEMS))

    def _pin(self, spec: SystemSpec) -> SystemSpec:
        """Apply the version pinned for this system in FHIR_TERMINOLOGY_SYSTEMS, if any."""
        if spec.version is not None:
            return spec
        for configured in self._configured_systems():
            if configured.uri == spec.uri and configured.version:
                return configured
        return spec

    def _parse_concept_id(self, concept_id: str) -> tuple[SystemSpec, str] | None:
        """``<system>|<code>[|<version>]`` -> (spec, code); a bare code needs one default
        system configured."""
        cid = (concept_id or "").strip()
        if not cid:
            return None
        parts = [p.strip() for p in cid.split("|")]
        if len(parts) == 1:
            configured = self._configured_systems()
            if len(configured) != 1:
                return None
            spec, code = configured[0], parts[0]
        elif len(parts) in (2, 3):
            resolved = resolve_system(parts[0])
            if resolved is None:
                return None
            version = parts[2] if len(parts) == 3 and parts[2] else resolved.version
            spec, code = SystemSpec(resolved.uri, version), parts[1]
        else:
            return None
        if not code:
            return None
        return self._pin(spec), code

    @staticmethod
    def _format_id(system: str, code: str) -> str:
        return f"{_URI_ALIAS.get(system, system)}|{code}"

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _throttle(self) -> None:
        async with self._throttle_lock:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _request(
        self,
        method: str,
        path: str,
        params: list[tuple[str, str]] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        """Call the FHIR server and return ``(status, json)`` without raising on 4xx.

        FHIR servers explain failures in an ``OperationOutcome`` body and use 404/422 for
        "unknown code" and "unknown code system" alike, so callers need the status. Only
        429 and 5xx are raised, so the shared retry and circuit breaker handle those. The
        body is parsed regardless of its content type (``application/fhir+json``).
        """
        url = f"{self.base_url}/{path}"
        headers = {"Accept": "application/fhir+json", **self._auth_headers()}

        async def _do() -> tuple[int, dict[str, Any] | None]:
            await self._throttle()
            session = await self._get_session()
            async with session.request(
                method, url, params=params, headers=headers, json=body
            ) as response:
                if response.status >= 500 or response.status == 429:
                    response.raise_for_status()
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    data = None
                return response.status, data if isinstance(data, dict) else None

        return await self._call_with_retry("fhir_request", _do)

    @staticmethod
    def _outcome_text(data: dict[str, Any] | None) -> str:
        """First message of an ``OperationOutcome`` (for logs)."""
        if not data:
            return ""
        for issue in data.get("issue") or []:
            text = (issue.get("details") or {}).get("text") or issue.get("diagnostics")
            if text:
                return str(text)[:200]
        return ""

    def _log_failure(self, what: str, status: int, data: dict[str, Any] | None) -> None:
        if status in (401, 403):
            logger.warning(
                f"FHIR terminology {what}: HTTP {status}, the server requires authentication "
                "(set FHIR_TERMINOLOGY_TOKEN or FHIR_TERMINOLOGY_USER/PASSWORD)"
            )
        else:
            logger.info(f"FHIR terminology {what}: HTTP {status} {self._outcome_text(data)}")

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def get_capabilities(self) -> dict[str, Any]:
        """Server software, FHIR version and the resource types it serves
        (``metadata?_summary=true``); ``{}`` if unreachable."""
        try:
            status, data = await self._request("GET", "metadata", [("_summary", "true")])
        except Exception as e:
            logger.warning(f"FHIR terminology capabilities failed: {e}")
            return {}
        if status != 200 or not data or data.get("resourceType") != "CapabilityStatement":
            self._log_failure("capabilities", status, data)
            return {}
        software = data.get("software") or {}
        resources = [
            r.get("type")
            for rest in data.get("rest") or []
            for r in rest.get("resource") or []
            if r.get("type")
        ]
        return {
            "server": (data.get("implementation") or {}).get("description"),
            "software": software.get("name"),
            "software_version": software.get("version"),
            "fhir_version": data.get("fhirVersion"),
            "resources": resources,
        }

    async def list_code_systems(
        self, title: str | None = None, url: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List code systems the server hosts (``CodeSystem?...``), optionally by title
        substring or exact URL. SNOMED CT and LOINC are built in on some servers and then
        do not appear here even though ``$lookup`` works."""
        if limit <= 0:
            return []
        params = [
            ("_elements", "url,version,name,title,status,content"),
            ("_count", str(min(limit, _MAX_LIST))),
        ]
        if title:
            params.append(("title", title.strip()))
        if url:
            params.append(("url", url.strip()))
        try:
            status, data = await self._request("GET", "CodeSystem", params)
        except Exception as e:
            logger.warning(f"FHIR terminology code system listing failed: {e}")
            return []
        if status != 200 or not data or data.get("resourceType") != "Bundle":
            self._log_failure("code system listing", status, data)
            return []
        systems = []
        for entry in data.get("entry") or []:
            res = entry.get("resource") or {}
            if res.get("url"):
                systems.append({k: res.get(k) for k in ("url", "version", "name", "title")})
        return systems[:limit]

    async def validate_code(
        self, concept_id: str, display: str | None = None
    ) -> dict[str, Any] | None:
        """``CodeSystem/$validate-code`` for ``<system>|<code>``: ``{"valid": bool,
        "display": ..., "message": ...}``, or ``None`` if the server could not say."""
        parsed = self._parse_concept_id(concept_id)
        if parsed is None:
            return None
        spec, code = parsed
        params = [("url", spec.uri), ("code", code)]
        if spec.version:
            params.append(("version", spec.version))
        if display:
            params.append(("display", display))
        try:
            status, data = await self._request("GET", "CodeSystem/$validate-code", params)
        except Exception as e:
            logger.warning(f"FHIR terminology validate-code failed for '{concept_id}': {e}")
            return None
        if status != 200 or not data or data.get("resourceType") != "Parameters":
            self._log_failure("validate-code", status, data)
            return None
        values = {p.get("name"): _value(p) for p in data.get("parameter") or []}
        if "result" not in values:
            return None
        return {
            "valid": bool(values["result"]),
            "display": values.get("display"),
            "message": values.get("message"),
        }

    async def _lookup(self, spec: SystemSpec, code: str) -> dict[str, Any] | None:
        """``CodeSystem/$lookup`` Parameters for a code, or ``None`` (unknown/unreachable)."""
        params = [("system", spec.uri), ("code", code)]
        if spec.version:
            params.append(("version", spec.version))
        params.extend(("property", name) for name in _LOOKUP_PROPERTIES)
        try:
            status, data = await self._request("GET", "CodeSystem/$lookup", params)
        except Exception as e:
            logger.warning(f"FHIR terminology lookup failed for '{spec.uri}|{code}': {e}")
            return None
        if status != 200 or not data or data.get("resourceType") != "Parameters":
            self._log_failure(f"lookup of {spec.uri}|{code}", status, data)
            return None
        return data

    async def _expand(self, spec: SystemSpec, query: str, limit: int) -> list[dict[str, Any]]:
        """``ValueSet/$expand`` with a text filter over one code system.

        Tries the implicit value set (``url=<system>?fhir_vs``) first, which tx.fhir.org
        supports only for SNOMED CT; on any failure (or when a version is pinned) posts an
        inline ``ValueSet`` with ``compose.include.system``, which both servers accept for
        every system they host. The mode that worked is remembered per system.
        """
        key = (spec.uri, spec.version)
        count = str(min(limit, _MAX_SEARCH))
        if spec.version is None and not self._inline_expand.get(key):
            params = [("url", f"{spec.uri}?fhir_vs"), ("filter", query), ("count", count)]
            try:
                status, data = await self._request("GET", "ValueSet/$expand", params)
            except Exception as e:
                logger.warning(f"FHIR terminology expand failed for '{spec.uri}': {e}")
                return []
            if status == 200 and data and data.get("resourceType") == "ValueSet":
                return list((data.get("expansion") or {}).get("contains") or [])
            if status in (401, 403):
                self._log_failure("expand", status, data)
                return []
            self._inline_expand[key] = True
        include: dict[str, Any] = {"system": spec.uri}
        if spec.version:
            include["version"] = spec.version
        body = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "valueSet",
                    "resource": {
                        "resourceType": "ValueSet",
                        "status": "active",
                        "compose": {"include": [include]},
                    },
                },
                {"name": "filter", "valueString": query},
                {"name": "count", "valueInteger": int(count)},
            ],
        }
        try:
            status, data = await self._request("POST", "ValueSet/$expand", body=body)
        except Exception as e:
            logger.warning(f"FHIR terminology expand failed for '{spec.uri}': {e}")
            return []
        if status == 200 and data and data.get("resourceType") == "ValueSet":
            return list((data.get("expansion") or {}).get("contains") or [])
        self._log_failure(f"expand of {spec.uri}", status, data)
        return []

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(
        self, query: str, limit: int = 20, systems: str | list[str] | None = None
    ) -> list[UnifiedConcept]:
        """Text search over code systems with ``$expand`` and its ``filter`` parameter.

        ``systems`` takes aliases or URIs (``["snomed", "icd10gm@2020"]`` or
        ``"loinc,atc"``); default is ``FHIR_TERMINOLOGY_SYSTEMS``, else SNOMED CT, ICD-10-CM
        and LOINC. Systems the server does not host are skipped (logged), and results from
        the systems are interleaved so each is represented within ``limit``. A query of the
        form ``<system>|<code>`` returns that one concept.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            if "|" in text:
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            per_system: list[list[UnifiedConcept]] = []
            for spec in self._search_systems(systems):
                spec = self._pin(spec)
                concepts = []
                for item in await self._expand(spec, text, limit):
                    concept = self._convert_expansion_item(item, spec)
                    if concept is not None:
                        concepts.append(concept)
                per_system.append(concepts)
            merged: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank in range(max((len(c) for c in per_system), default=0)):
                for concepts in per_system:
                    if rank < len(concepts) and concepts[rank].primary_id not in seen:
                        seen.add(concepts[rank].primary_id)
                        merged.append(concepts[rank])
            logger.info(f"FHIR terminology search for '{text}' returned {len(merged)} concepts")
            return merged[:limit]
        except Exception as e:
            logger.error(f"FHIR terminology search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """``$lookup`` of ``<system>|<code>`` (``loinc|2093-3``, ``icd10gm|G93.3``): display,
        definition, designations (synonyms, incl. German), properties, parents, children."""
        parsed = self._parse_concept_id(concept_id)
        if parsed is None:
            return None
        spec, code = parsed
        data = await self._lookup(spec, code)
        if data is None:
            return None
        try:
            return self._convert_lookup(data, spec, code)
        except Exception as e:
            logger.error(f"Error converting FHIR lookup for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Hierarchy edges from the ``parent`` / ``child`` properties of ``$lookup``:
        ``is_a`` (concept -> parent) and ``has_subtype`` (concept -> child). Servers that
        do not expose a property (Ontoserver gives no children for ICD-10-GM) yield fewer
        edges; names are included only where the server returns them (tx.fhir.org does)."""
        parsed = self._parse_concept_id(concept_id)
        if parsed is None:
            return []
        spec, code = parsed
        data = await self._lookup(spec, code)
        if data is None:
            return []
        try:
            info = self._parse_lookup(data)
            system = info["system"] or spec.uri
            edges: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for label, key in (("is_a", "parents"), ("has_subtype", "children")):
                for related_code, name in info[key]:
                    related_id = self._format_id(system, related_code)
                    if (label, related_id) in seen:
                        continue
                    seen.add((label, related_id))
                    edges.append(
                        {
                            "relation_label": label,
                            "related_id": related_id,
                            "related_name": name or related_code,
                            "source": "FHIR terminology",
                        }
                    )
            return edges
        except Exception as e:
            logger.warning(f"FHIR terminology get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(
        self, concept_id: str, target_system: str | None = None
    ) -> list[dict[str, Any]]:
        """Mappings from ``ConceptMap/$translate`` (all maps the server has for the code,
        or only to ``target_system``). Ontoserver maps SNOMED CT to ICD-10-AM, MedDRA and
        Read; tx.fhir.org usually has no applicable ConceptMap and returns ``[]``."""
        parsed = self._parse_concept_id(concept_id)
        if parsed is None:
            return []
        spec, code = parsed
        params = [("system", spec.uri), ("code", code)]
        if spec.version:
            params.append(("version", spec.version))
        if target_system:
            target = resolve_system(target_system)
            if target is None:
                return []
            params.append(("targetsystem", target.uri))
        try:
            status, data = await self._request("GET", "ConceptMap/$translate", params)
        except Exception as e:
            logger.warning(f"FHIR terminology translate failed for '{concept_id}': {e}")
            return []
        if status != 200 or not data or data.get("resourceType") != "Parameters":
            self._log_failure("translate", status, data)
            return []
        try:
            from_id = self._format_id(spec.uri, code)
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for param in data.get("parameter") or []:
                if param.get("name") != "match":
                    continue
                parts = {p.get("name"): p for p in param.get("part") or []}
                coding = (parts.get("concept") or {}).get("valueCoding") or {}
                if not coding.get("code"):
                    continue
                relation = _value(parts.get("equivalence") or parts.get("relationship") or {})
                if relation in ("disjoint", "unmatched", "not-related-to"):
                    continue
                mapping_type, confidence = _EQUIVALENCE.get(str(relation), ("relatedMatch", 0.5))
                system = coding.get("system") or ""
                to_id = self._format_id(system, coding["code"]) if system else coding["code"]
                map_url = _value(parts.get("source") or {})
                if (to_id, str(map_url)) in seen:
                    continue
                seen.add((to_id, str(map_url)))
                mapping: dict[str, Any] = {
                    "fromId": from_id,
                    "toId": to_id,
                    "fromSource": self._source_name(spec.uri),
                    "toSource": self._source_name(system),
                    "mappingType": mapping_type,
                    "confidence": confidence,
                }
                if coding.get("display"):
                    mapping["toLabel"] = coding["display"]
                if map_url:
                    mapping["conceptMap"] = map_url
                mappings.append(mapping)
            return mappings
        except Exception as e:
            logger.warning(f"FHIR terminology get_mappings failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _source_name(system: str) -> str:
        source = _URI_SOURCE.get(system)
        if source is not None:
            return source.value
        return _URI_ALIAS[system].upper() if system in _URI_ALIAS else system

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_lookup(data: dict[str, Any]) -> dict[str, Any]:
        """Flatten a ``$lookup`` Parameters resource."""
        info: dict[str, Any] = {
            "system": None,
            "version": None,
            "name": None,
            "display": None,
            "definition": None,
            "abstract": None,
            "designations": [],
            "properties": {},
            "parents": [],
            "children": [],
        }
        for param in data.get("parameter") or []:
            name = param.get("name")
            if name == "designation":
                parts = {p.get("name"): p for p in param.get("part") or []}
                use = (parts.get("use") or {}).get("valueCoding") or {}
                value = (parts.get("value") or {}).get("valueString")
                if value:
                    info["designations"].append(
                        {
                            "language": _value(parts.get("language") or {}),
                            "use": use.get("code"),
                            "status": _value(parts.get("status") or {}),
                            "value": value,
                        }
                    )
            elif name == "property":
                parts = {p.get("name"): p for p in param.get("part") or []}
                code = _value(parts.get("code") or {})
                value = _value(parts.get("value") or {})
                if not code or value is None:
                    continue  # e.g. Ontoserver 'subproperty' groups carry no plain value
                if code in ("parent", "child"):
                    desc = _value(parts.get("description") or {})
                    key = "parents" if code == "parent" else "children"
                    info[key].append((str(value), str(desc) if desc else ""))
                elif code not in _SKIP_PROPERTIES:
                    info["properties"].setdefault(code, []).append(value)
            elif name in ("system", "version", "name", "display", "definition", "abstract"):
                info[name] = _value(param)
        return info

    @staticmethod
    def _snomed_tag(designations: list[dict[str, Any]]) -> str | None:
        for des in designations:
            if des["use"] == _SNOMED_FSN_USE:
                match = _TAG_RE.search(des["value"])
                return match.group(1).lower() if match else None
        return None

    def _make_concept(
        self, system: str, code: str, label: str, concept_type: ConceptType
    ) -> UnifiedConcept:
        concept = self._create_concept(self._format_id(system, code), label, concept_type)
        native = _URI_SOURCE.get(system)
        if native is not None:
            concept.add_identifier(native, code, label)
        if concept.categories is not None:
            concept.categories.append(f"system:{_URI_ALIAS.get(system, system)}")
        concept.confidence_score = 0.9
        return concept

    @staticmethod
    def _default_type(system: str) -> ConceptType:
        alias = _URI_ALIAS.get(system)
        return _SYSTEMS[alias][1] if alias else ConceptType.UNKNOWN

    def _convert_expansion_item(
        self, item: dict[str, Any], spec: SystemSpec
    ) -> UnifiedConcept | None:
        """Thin concept from one ``expansion.contains`` entry (details come via $lookup)."""
        try:
            code = item.get("code")
            if not code:
                return None
            system = item.get("system") or spec.uri
            label = item.get("display") or str(code)
            concept = self._make_concept(system, str(code), label, self._default_type(system))
            if item.get("inactive") and concept.categories is not None:
                concept.categories.append("inactive")
            if concept.synonyms is not None:
                for des in item.get("designation") or []:
                    value = des.get("value")
                    if value and value != label and value not in concept.synonyms:
                        concept.synonyms.append(value)
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.FHIRTERMINOLOGY] = {
                    "server": self.base_url,
                    "system": system,
                    "code": str(code),
                    "inactive": bool(item.get("inactive")),
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting FHIR expansion entry: {e}")
            return None

    def _convert_lookup(self, data: dict[str, Any], spec: SystemSpec, code: str) -> UnifiedConcept:
        info = self._parse_lookup(data)
        system = info["system"] or spec.uri
        label = info["display"] or code
        designations = info["designations"]

        concept_type = self._default_type(system)
        tag = self._snomed_tag(designations) if system == "http://snomed.info/sct" else None
        if tag:
            concept_type = _SNOMED_TAGS.get(tag, concept_type)
        concept = self._make_concept(system, code, label, concept_type)

        definitions = [info["definition"]] if info["definition"] else []
        for des in designations:
            if des["use"] == _SNOMED_DEFINITION_USE and des["value"] not in definitions:
                definitions.append(des["value"])
        if concept.definitions is not None:
            concept.definitions.extend(d for d in definitions if d and d != label)

        if concept.synonyms is not None:
            for des in designations:
                lang = (des["language"] or "").lower()
                if (
                    des["use"] == _SNOMED_DEFINITION_USE
                    or des["status"] == "inactive"
                    or (lang and not lang.startswith(_SYNONYM_LANGUAGES))
                ):
                    continue
                value = des["value"]
                if value != label and value not in concept.synonyms:
                    concept.synonyms.append(value)
            del concept.synonyms[_MAX_SYNONYMS:]

        if concept.categories is not None:
            if info["version"]:
                concept.categories.append(f"version:{info['version']}")
            if info["properties"].get("inactive") == [True]:
                concept.categories.append("inactive")
        if tag and concept.semantic_types is not None:
            concept.semantic_types.append(tag)
        if concept.parents is not None:
            concept.parents.extend(self._format_id(system, c) for c, _ in info["parents"])
        if concept.children is not None:
            concept.children.extend(self._format_id(system, c) for c, _ in info["children"])

        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.FHIRTERMINOLOGY] = {
                "server": self.base_url,
                "system": system,
                "code": code,
                "version": info["version"],
                "name": info["name"],
                "abstract": info["abstract"],
                "properties": info["properties"],
                "designations": designations,
                "parents": [{"code": c, "display": d} for c, d in info["parents"]],
                "children": [{"code": c, "display": d} for c, d in info["children"]],
            }
        return concept
