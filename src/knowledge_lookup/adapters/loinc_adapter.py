"""
LOINC Knowledge Source Adapter

Adapter for the LOINC FHIR R4 terminology server (https://fhir.loinc.org) operated by the
Regenstrief Institute. LOINC codes identify laboratory tests and clinical observations
(e.g. ``2093-3`` Cholesterol [Mass/volume] in Serum or Plasma, ``718-7`` Hemoglobin).

Operations used (standard FHIR terminology operations):

- ``ValueSet/$expand?url=http://loinc.org/vs&filter=<text>&count=<n>`` for search; the
  ``expansion.contains`` list holds ``system`` / ``code`` / ``display``.
- ``CodeSystem/$lookup?system=http://loinc.org&code=<code>&property=...`` for details; the
  ``Parameters`` resource carries ``display``, ``designation`` and ``property`` parameters
  (COMPONENT, PROPERTY, TIME_ASPCT, SYSTEM, SCALE_TYP, METHOD_TYP, CLASS, ...). The six
  axis properties are LOINC parts and are exposed by :meth:`get_relationships` as typed
  edges (``has_component``, ``has_system``, ...).

Authentication: HTTP Basic with a free loinc.org account (``LOINC_USERNAME`` /
``LOINC_PASSWORD``, or ``config.get_api_key("loinc_username"/"loinc_password")``).
``is_available()`` needs both. A 401/403 (or an HTML login page, which the server returns
to unauthenticated browsers) is logged with a hint and degrades to ``[]`` / ``None``.

Licence: LOINC is free to use but under the LOINC licence (https://loinc.org/license/).
Any product or publication that shows LOINC content must carry the copyright notice in
:data:`LOINC_COPYRIGHT_NOTICE`; it is attached to every concept's ``source_data``.

The response handling follows the FHIR R4 ``$lookup`` / ``$expand`` specification and
LOINC's public FHIR documentation (https://loinc.org/fhir/); it is parsed defensively
(parameter order and value types vary) but is not live-verified because the server needs
credentials.
"""

import base64
import logging
import os
import re
from datetime import date
from typing import Any
from urllib.parse import urlencode

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

LOINC_FHIR_BASE = "https://fhir.loinc.org"
LOINC_SYSTEM = "http://loinc.org"
LOINC_ALL_VALUESET = "http://loinc.org/vs"

LOINC_COPYRIGHT_NOTICE = (
    "This material contains content from LOINC (http://loinc.org). LOINC is copyright "
    f"© 1995-{date.today().year}, Regenstrief Institute, Inc. and the Logical Observation "
    "Identifiers Names and Codes (LOINC) Committee and is available at no cost under the "
    "license at http://loinc.org/license. LOINC® is a registered United States "
    "trademark of Regenstrief Institute, Inc."
)

# Properties requested from $lookup. LONG_COMMON_NAME arrives as a designation / display.
LOOKUP_PROPERTIES = (
    "COMPONENT",
    "PROPERTY",
    "TIME_ASPCT",
    "SYSTEM",
    "SCALE_TYP",
    "METHOD_TYP",
    "CLASS",
    "STATUS",
    "DefinitionDescription",
)

# LOINC axis property -> typed relationship label.
PART_RELATIONS: dict[str, str] = {
    "COMPONENT": "has_component",
    "PROPERTY": "has_property",
    "TIME_ASPCT": "has_time_aspect",
    "SYSTEM": "has_system",
    "SCALE_TYP": "has_scale",
    "METHOD_TYP": "has_method",
    "CLASS": "has_class",
}
# FHIR hierarchy convention for code systems that expose them as properties.
HIERARCHY_RELATIONS = {"PARENT": "is_a", "CHILD": "has_subtype"}

_CODE_RE = re.compile(r"^[A-Z]{0,4}\d{1,8}-\d$")
_CURIE_RE = re.compile(r"^LOINC\s*:\s*", re.IGNORECASE)


def _param_value(part: dict[str, Any]) -> Any:
    """Return the ``value[x]`` of a Parameters part (a string, or a Coding dict)."""
    for key, value in part.items():
        if key.startswith("value"):
            return value
    return None


def _coding_text(value: Any) -> tuple[str, str]:
    """``(code, display)`` of a Coding, or ``(str, str)`` for a scalar value."""
    if isinstance(value, dict):
        code = str(value.get("code") or "")
        return code, str(value.get("display") or code)
    text = "" if value is None else str(value)
    return text, text


def _flatten_contains(items: Any) -> list[dict[str, Any]]:
    """Flatten ``expansion.contains`` (entries may nest further ``contains``)."""
    out: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        out.append(item)
        out.extend(_flatten_contains(item.get("contains")))
    return out


class LoincAdapter(KnowledgeSourceAdapter):
    """Adapter for LOINC via the Regenstrief FHIR R4 terminology server."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = LOINC_FHIR_BASE
        # code -> parsed $lookup result, so details + relationships cost one request
        self._lookup_cache: dict[str, dict[str, Any]] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.LOINC

    # ------------------------------------------------------------------
    # Configuration / requests
    # ------------------------------------------------------------------

    def _credentials(self) -> tuple[str | None, str | None]:
        user = self.config.get_api_key("loinc_username") or os.getenv("LOINC_USERNAME")
        password = self.config.get_api_key("loinc_password") or os.getenv("LOINC_PASSWORD")
        return user, password

    def is_available(self) -> bool:
        user, password = self._credentials()
        return bool(user and password)

    def _headers(self) -> dict[str, str]:
        user, password = self._credentials()
        token = base64.b64encode(f"{user or ''}:{password or ''}".encode()).decode("ascii")
        return {"Accept": "application/fhir+json", "Authorization": f"Basic {token}"}

    async def _get(self, url: str) -> dict[str, Any]:
        """GET a FHIR URL with Basic auth. The query string is already in ``url`` because
        ``$lookup`` repeats the ``property`` parameter, which ``params=`` dicts cannot."""
        try:
            return await self._make_request(url, None, self._headers())
        except Exception as exc:
            status = getattr(exc, "status", None)
            if status in (401, 403):
                logger.error(
                    "LOINC rejected the credentials (HTTP %s); check LOINC_USERNAME / "
                    "LOINC_PASSWORD (free account at https://loinc.org)",
                    status,
                )
            elif type(exc).__name__ == "ContentTypeError":
                logger.error(
                    "LOINC returned HTML instead of FHIR JSON (login page?); "
                    "check the loinc.org credentials"
                )
            raise

    @staticmethod
    def _normalise_code(concept_id: str) -> str | None:
        code = _CURIE_RE.sub("", (concept_id or "").strip()).upper()
        return code if _CODE_RE.match(code) else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search LOINC term names through ``ValueSet/$expand`` (text ``filter``).

        A query that is itself a LOINC code (``2093-3``) is resolved with ``$lookup``.
        Expansion entries only carry code and display, so use :meth:`get_concept_details`
        for axes, designations and parts.
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            code = self._normalise_code(query)
            if code:
                concept = await self.get_concept_details(code)
                return [concept] if concept else []

            url = f"{self.base_url}/ValueSet/$expand?" + urlencode(
                {"url": LOINC_ALL_VALUESET, "filter": query, "count": limit}
            )
            data = await self._get(url)
            expansion = data.get("expansion") if isinstance(data, dict) else None
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in _flatten_contains((expansion or {}).get("contains")):
                concept = self._convert_expansion_item(item)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"LOINC search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"LOINC search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Look up one LOINC code (``2093-3`` or ``LOINC:2093-3``) with ``$lookup``."""
        try:
            code = self._normalise_code(concept_id)
            if not code:
                return None
            parsed = await self._lookup(code)
            if not parsed:
                return None
            return self._convert_lookup(code, parsed)
        except Exception as e:
            logger.error(f"LOINC get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the LOINC parts of a term as typed edges.

        COMPONENT / PROPERTY / TIME_ASPCT / SYSTEM / SCALE_TYP / METHOD_TYP / CLASS become
        ``has_component`` / ``has_property`` / ``has_time_aspect`` / ``has_system`` /
        ``has_scale`` / ``has_method`` / ``has_class``; ``parent`` / ``child`` properties,
        when the server returns them, become ``is_a`` / ``has_subtype``. ``related_id`` is
        the LOINC part code (``LP...``) when the server supplies a Coding, otherwise the
        plain value.
        """
        try:
            code = self._normalise_code(concept_id)
            if not code:
                return []
            parsed = await self._lookup(code)
            if not parsed:
                return []
            relationships: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for name, value in parsed["property_values"]:
                label = PART_RELATIONS.get(name) or HIERARCHY_RELATIONS.get(name)
                if label is None:
                    continue
                related_id, related_name = _coding_text(value)
                if not related_id or (label, related_id) in seen:
                    continue
                seen.add((label, related_id))
                relationships.append(
                    {
                        "relation_label": label,
                        "related_id": related_id,
                        "related_name": related_name,
                        "source": "LOINC",
                    }
                )
            return relationships
        except Exception as e:
            logger.error(f"LOINC get_relationships failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # $lookup parsing
    # ------------------------------------------------------------------

    async def _lookup(self, code: str) -> dict[str, Any] | None:
        cached = self._lookup_cache.get(code)
        if cached is not None:
            return cached
        query: list[tuple[str, str]] = [("system", LOINC_SYSTEM), ("code", code)]
        query += [("property", name) for name in LOOKUP_PROPERTIES]
        data = await self._get(f"{self.base_url}/CodeSystem/$lookup?" + urlencode(query))
        parsed = self._parse_lookup(data)
        if parsed is not None:
            self._lookup_cache[code] = parsed
        return parsed

    @staticmethod
    def _parse_lookup(data: Any) -> dict[str, Any] | None:
        """Flatten a FHIR ``Parameters`` resource into display/designations/properties."""
        if not isinstance(data, dict):
            return None
        if data.get("resourceType") == "OperationOutcome":
            return None
        result: dict[str, Any] = {
            "display": "",
            "version": "",
            "designations": [],
            "long_common_name": "",
            "property_values": [],  # [(UPPERCASE NAME, value)] preserving repeats
            "properties": {},  # NAME -> first scalar/display text
        }
        for param in data.get("parameter") or []:
            if not isinstance(param, dict):
                continue
            name = param.get("name")
            if name == "display":
                result["display"] = str(param.get("valueString") or "")
            elif name == "version":
                result["version"] = str(param.get("valueString") or "")
            elif name == "designation":
                parts = {p.get("name"): _param_value(p) for p in param.get("part") or []}
                value = str(parts.get("value") or "").strip()
                use_code, _ = _coding_text(parts.get("use"))
                if value:
                    result["designations"].append({"use": use_code, "value": value})
                    if "LONG_COMMON_NAME" in use_code.upper().replace(" ", "_"):
                        result["long_common_name"] = value
            elif name == "property":
                parts = {p.get("name"): _param_value(p) for p in param.get("part") or []}
                prop = str(parts.get("code") or "").strip()
                prop_value = parts.get("value")
                if not prop or prop_value in (None, ""):
                    continue
                key = prop.upper()
                result["property_values"].append((key, prop_value))
                result["properties"].setdefault(key, _coding_text(prop_value)[1])
        if not result["display"] and not result["designations"]:
            return None
        return result

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_expansion_item(self, item: dict[str, Any]) -> UnifiedConcept | None:
        code = str(item.get("code") or "").strip()
        display = str(item.get("display") or "").strip()
        if not code or not display:
            return None
        concept = self._create_concept(code, display, ConceptType.OBSERVATION)
        concept.confidence_score = 0.8
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.LOINC] = {
                **item,
                "copyright": LOINC_COPYRIGHT_NOTICE,
            }
        return concept

    def _convert_lookup(self, code: str, parsed: dict[str, Any]) -> UnifiedConcept:
        label = parsed["long_common_name"] or parsed["display"] or code
        concept = self._create_concept(code, label, ConceptType.OBSERVATION)
        synonyms: list[str] = []
        for designation in parsed["designations"]:
            value = designation["value"]
            if value != label and value not in synonyms:
                synonyms.append(value)
        if parsed["display"] and parsed["display"] != label and parsed["display"] not in synonyms:
            synonyms.append(parsed["display"])
        concept.synonyms = synonyms

        props: dict[str, str] = parsed["properties"]
        definition = props.get("DEFINITIONDESCRIPTION")
        if definition:
            concept.definitions = [definition]
        if concept.categories is not None and props.get("CLASS"):
            concept.categories.append(f"class:{props['CLASS']}")
        if concept.semantic_types is not None and props.get("SYSTEM"):
            concept.semantic_types.append(f"specimen:{props['SYSTEM']}")
        concept.confidence_score = 1.0
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.LOINC] = {
                "code": code,
                "display": parsed["display"],
                "long_common_name": parsed["long_common_name"],
                "version": parsed["version"],
                "properties": props,
                "designations": parsed["designations"],
                "copyright": LOINC_COPYRIGHT_NOTICE,
            }
        return concept
