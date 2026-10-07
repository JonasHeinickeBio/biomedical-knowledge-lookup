"""
RxClass (ATC) Knowledge Source Adapter

Adapter for the NLM RxNav services (https://rxnav.nlm.nih.gov/REST/), keyless: RxClass
for the WHO ATC drug classification and RxNorm for turning a drug name into an RxCUI.
Main use: harmonise registry medications to ATC.

What RxClass actually serves (live-verified):

- Class type ``ATC1-4`` only: the five ATC levels exist as classes down to level 4
  (``N``, ``N02``, ``N02B``, ``N02BA`` ...). Level 5 codes (``N02BA01``, one per
  substance) are *not* classes; RxClass exposes them as the ``SourceId`` attribute of a
  class member, so they are reachable from ``classMembers`` and used here for drug
  mappings.
- ``allClasses?classTypes=ATC1-4`` returns every ATC class (~1,300, 113 KB, ~1.4 s) in
  one call. The hierarchy follows the code (``N02BA`` -> ``N02B`` -> ``N02`` -> ``N``), so
  class search, parent and children are all served from that one cached response.
- ``class/byDrugName`` resolves a drug *or brand* name ("Advil") straight to ingredient
  RxCUIs plus their ATC classes. It also returns combination products that contain the
  ingredient ("aspirin / codeine"), each as its own RxCUI. When it finds nothing the
  adapter falls back to RxNorm ``approximateTerm`` for misspellings.
- Responses are XML unless the path ends in ``.json`` (``Accept`` is not enough for every
  endpoint), so every call uses the ``.json`` form.
- RxNav allows 20 requests/s per IP; calls are spaced out at ~16/s and the adapter
  normally issues one to three requests per method call.

Identifiers: RxCUI (``1191``, ``RXCUI:1191``, ``RxNorm:1191``) for drugs; ATC codes
(``N02BA``, ``ATC:N02BA``) for classes; ``N02BA01``-style level 5 codes resolve to the
drug that carries them.
"""

import asyncio
import logging
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
RXCLASS_URL = f"{RXNAV_BASE_URL}/rxclass"
ATC_SOURCE = "ATC"
ATC_CLASS_TYPES = "ATC1-4"

# ATC code shapes: level 1 "N", 2 "N02", 3 "N02B", 4 "N02BA", 5 "N02BA01".
_ATC_RE = re.compile(r"^[A-Z](?:\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?)?$")
_PREFIX_RE = re.compile(r"^(RXCUI|RXNORM|ATC|RXCLASS)\s*:\s*", re.IGNORECASE)
_LEVEL_BY_LENGTH = {1: 1, 3: 2, 4: 3, 5: 4, 7: 5}

# RxNav asks for at most 20 requests/s per IP; stay clearly below that.
_MIN_INTERVAL = 0.06
# Minimum RxNorm approximateTerm score accepted as "probably the same drug".
_MIN_APPROX_SCORE = 10.0
# Cap on classMembers calls made when expanding a drug to its level-5 ATC codes.
_MAX_CLASSES_FOR_ATC5 = 8


def atc_level(code: str) -> int | None:
    """ATC level (1-5) of a well-formed code, else ``None``."""
    return _LEVEL_BY_LENGTH.get(len(code)) if _ATC_RE.match(code) else None


def _parent_code(code: str) -> str | None:
    """Parent ATC class (level 5 -> 4 -> 3 -> 2 -> 1); ``None`` for level 1."""
    level = atc_level(code)
    if level is None or level == 1:
        return None
    return code[: {5: 5, 4: 4, 3: 3, 2: 1}[level]]


class RxClassAdapter(KnowledgeSourceAdapter):
    """Adapter for NLM RxClass (ATC) and RxNorm name resolution.

    Public NLM service without a licence requirement for RxNorm/RxClass itself; the ATC
    classification content is WHO's (see https://www.whocc.no/ for their terms).
    """

    def __init__(self, config):
        super().__init__(config)
        self.base_url = RXCLASS_URL
        self._classes: dict[str, str] | None = None  # ATC code -> class name
        self._members: dict[str, list[dict[str, Any]]] = {}
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.RXCLASS

    def is_available(self) -> bool:
        return True  # keyless public service

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str, str] | None:
        """Classify an identifier as ``("rxcui", "1191")`` or ``("atc", "N02BA")``."""
        if not isinstance(concept_id, str):
            return None
        bare = _PREFIX_RE.sub("", concept_id.strip()).strip()
        if bare.isdigit():
            return ("rxcui", bare)
        bare = bare.upper()
        if _ATC_RE.match(bare):
            return ("atc", bare)
        return None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search ATC classes by name or code and drugs by (brand) name.

        Order: exact-name matches, then drugs, then classes. An ATC code query returns
        that class (or, for a level 5 code, the drug that carries it).
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            parsed = self.parse_id(query)
            if parsed and (parsed[0] == "rxcui" or len(parsed[1]) > 1):
                # An identifier, not a name (a lone letter is more likely a word).
                concept = await self.get_concept_details(query)
                return [concept] if concept else []

            classes, drugs = await asyncio.gather(
                self._classes_matching(query, limit),
                self._drugs_by_name(query),
                return_exceptions=True,
            )
            drug_groups = drugs if isinstance(drugs, list) else []
            class_hits = classes if isinstance(classes, list) else []
            if not drug_groups and not class_hits:
                if isinstance(drugs, BaseException):
                    raise drugs
                drug_groups = await self._approximate_drug(query)

            results: list[UnifiedConcept] = [self._drug_concept(g) for g in drug_groups]
            results += [self._class_concept(code, name) for code, name in class_hits]
            q = query.lower()
            results.sort(key=lambda c: 0 if c.primary_label.lower() == q else 1)  # stable
            logger.info(f"RxClass search for '{query}' returned {len(results[:limit])} concepts")
            return results[:limit]
        except Exception as e:
            logger.error(f"RxClass search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for an ATC class (from the cached class list) or an RxCUI drug."""
        parsed = self.parse_id(concept_id)
        if not parsed:
            logger.warning(f"RxClass: '{concept_id}' is neither an RxCUI nor an ATC code")
            return None
        kind, ident = parsed
        try:
            if kind == "rxcui":
                group = await self._drug_group(ident)
                return self._drug_concept(group) if group else None
            level = atc_level(ident)
            if level == 5:
                return await self._atc5_drug(ident)
            classes = await self._all_classes()
            name = classes.get(ident)
            return self._class_concept(ident, name, classes) if name else None
        except Exception as e:
            logger.error(f"RxClass get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Typed relationships.

        - drug (RxCUI): ``has_atc_class`` -> ATC level 4 classes of that exact RxCUI.
        - ATC class: ``has_parent`` / ``has_child`` (from the class list) and
          ``has_member`` -> drugs (RxCUI; ``atc_code`` holds their level 5 code). Member
          drugs are capped by ``limit``; levels 1-3 list ingredients only (``ttys=IN``)
          since a whole organ system otherwise lists hundreds of products.
        """
        parsed = self.parse_id(concept_id)
        if not parsed or limit <= 0:
            return []
        kind, ident = parsed
        try:
            if kind == "rxcui":
                group = await self._drug_group(ident)
                return [self._atc_edge(c) for c in (group or {}).get("classes", [])][:limit]
            level = atc_level(ident)
            if level is None or level == 5:
                return []
            classes = await self._all_classes()
            if ident not in classes:
                return []
            rels: list[dict[str, Any]] = []
            parent = _parent_code(ident)
            if parent and parent in classes:
                rels.append(self._class_edge("has_parent", parent, classes[parent]))
            for child in self._children(ident, classes):
                rels.append(self._class_edge("has_child", child, classes[child]))
            for member in (await self._class_members(ident, level))[:limit]:
                rels.append(
                    {
                        "relation_label": "has_member",
                        "related_id": member["rxcui"],
                        "related_name": member["name"],
                        "source": "RxClass",
                        "tty": member["tty"],
                        "atc_code": member["atc_code"],
                    }
                )
            return rels
        except Exception as e:
            logger.warning(f"RxClass get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """RxCUI <-> ATC mappings.

        - RxCUI -> its ATC level 4 classes (``atc_class``) and level 5 codes (``atc5``,
          needs one ``classMembers`` call per class, capped), plus the UMLS CUI when
          RxNorm lists one (usually empty).
        - ``N02BA01``-style level 5 code -> the RxCUI that carries it.
        - Other ATC classes: ``[]``.
        """
        parsed = self.parse_id(concept_id)
        if not parsed:
            return []
        kind, ident = parsed
        try:
            if kind == "atc":
                if atc_level(ident) != 5:
                    return []
                drug = await self._atc5_member(ident)
                if not drug:
                    return []
                return [self._mapping(ident, "ATC", drug["rxcui"], "RxNorm", "atc5_to_rxcui", 1.0)]

            group = await self._drug_group(ident)
            if not group:
                return []
            mappings = [
                self._mapping(ident, "RxNorm", c["id"], "ATC", "atc_class", 1.0)
                for c in group["classes"]
            ]
            seen: set[str] = set()
            for cls in group["classes"][:_MAX_CLASSES_FOR_ATC5]:
                for member in await self._class_members(cls["id"], 4):
                    code = member["atc_code"]
                    if member["rxcui"] == ident and code and code not in seen:
                        seen.add(code)
                        mappings.append(self._mapping(ident, "RxNorm", code, "ATC", "atc5", 1.0))
            if group.get("umlscui"):
                mappings.append(
                    self._mapping(ident, "RxNorm", group["umlscui"], "UMLS", "umls_cui", 0.9)
                )
            return mappings
        except Exception as e:
            logger.warning(f"RxClass get_mappings failed for '{concept_id}': {e}")
            return []

    async def lookup_rxcui(self, name: str) -> str | None:
        """Drug name -> RxCUI via RxNorm (exact normalised match, then approximate)."""
        name = (name or "").strip()
        if not name:
            return None
        try:
            data = await self._get(f"{RXNAV_BASE_URL}/rxcui.json", {"name": name, "search": 2})
            ids = ((data or {}).get("idGroup") or {}).get("rxnormId") or []
            if ids:
                return str(ids[0])
            groups = await self._approximate_drug(name)
            return groups[0]["rxcui"] if groups else None
        except Exception as e:
            logger.warning(f"RxClass lookup_rxcui failed for '{name}': {e}")
            return None

    async def get_atc_for_drug(self, name: str) -> list[dict[str, Any]]:
        """Registry helper: drug or brand name -> ``[{rxcui, name, tty, atc_classes}]``.

        One request (``class/byDrugName``); includes combination products containing
        the ingredient, ingredient-only RxCUIs sort first.
        """
        try:
            groups = await self._drugs_by_name((name or "").strip())
            return [
                {
                    "rxcui": g["rxcui"],
                    "name": g["name"],
                    "tty": g["tty"],
                    "atc_classes": g["classes"],
                }
                for g in groups
            ]
        except Exception as e:
            logger.warning(f"RxClass get_atc_for_drug failed for '{name}': {e}")
            return []

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Throttled GET returning JSON (RxNav answers ``{}`` for "no match")."""
        async with self._throttle_lock:
            wait = self._last_request + _MIN_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(url, params, headers={"Accept": "application/json"})
        return data if isinstance(data, dict) else {}

    async def _all_classes(self) -> dict[str, str]:
        """ATC code -> class name for all levels 1-4 (one call, cached on the adapter)."""
        if self._classes is None:
            data = await self._get(
                f"{RXCLASS_URL}/allClasses.json", {"classTypes": ATC_CLASS_TYPES}
            )
            items = (data.get("rxclassMinConceptList") or {}).get("rxclassMinConcept") or []
            classes = {
                i["classId"]: i["className"]
                for i in items
                if i.get("classId") and i.get("className") and _ATC_RE.match(i["classId"])
            }
            if classes:  # do not cache an empty/failed answer
                self._classes = classes
            return classes
        return self._classes

    async def _classes_matching(self, query: str, limit: int) -> list[tuple[str, str]]:
        """Class-name matches ranked exact, prefix, substring (by name, then code)."""
        q = query.lower()
        scored: list[tuple[int, str, str]] = []
        for code, name in (await self._all_classes()).items():
            low = name.lower()
            if low == q:
                scored.append((0, code, name))
            elif low.startswith(q):
                scored.append((1, code, name))
            elif q in low:
                scored.append((2, code, name))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [(code, name) for _, code, name in scored[:limit]]

    @staticmethod
    def _children(code: str, classes: dict[str, str]) -> list[str]:
        level = atc_level(code)
        if level is None or level >= 4:
            return []
        child_len = {1: 3, 2: 4, 3: 5}[level]
        return sorted(c for c in classes if len(c) == child_len and c.startswith(code))

    async def _drugs_by_name(self, name: str) -> list[dict[str, Any]]:
        """``class/byDrugName`` grouped per RxCUI, ingredients before combinations."""
        if not name:
            return []
        data = await self._get(
            f"{RXCLASS_URL}/class/byDrugName.json", {"drugName": name, "relaSource": ATC_SOURCE}
        )
        return self._group_drug_info(data)

    @staticmethod
    def _group_drug_info(data: dict[str, Any]) -> list[dict[str, Any]]:
        infos = (data.get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo") or []
        groups: dict[str, dict[str, Any]] = {}
        for info in infos:
            drug = info.get("minConcept") or {}
            klass = info.get("rxclassMinConceptItem") or {}
            rxcui = str(drug.get("rxcui") or "")
            if not rxcui:
                continue
            group = groups.setdefault(
                rxcui,
                {
                    "rxcui": rxcui,
                    "name": drug.get("name", ""),
                    "tty": drug.get("tty", ""),
                    "classes": [],
                },
            )
            cid = klass.get("classId")
            if cid and all(c["id"] != cid for c in group["classes"]):
                group["classes"].append(
                    {"id": cid, "name": klass.get("className", ""), "level": atc_level(cid)}
                )
        return sorted(groups.values(), key=lambda g: (g["tty"] not in ("IN", "PIN"), g["name"]))

    async def _approximate_drug(self, term: str) -> list[dict[str, Any]]:
        """Fuzzy fallback: ``approximateTerm`` -> best RxCUI -> its ATC classes."""
        data = await self._get(
            f"{RXNAV_BASE_URL}/approximateTerm.json", {"term": term, "maxEntries": 3}
        )
        for cand in (data.get("approximateGroup") or {}).get("candidate") or []:
            try:
                score = float(cand.get("score") or 0)
            except (TypeError, ValueError):
                continue
            # Typos of real ingredients score ~12 ("fluoxetin"); weak guesses ~5-9 point
            # at unrelated products ("asprin" -> an acetaminophen tablet), so drop them.
            if score < _MIN_APPROX_SCORE:
                continue
            group = await self._drug_group(str(cand.get("rxcui") or ""))
            return [group] if group else []
        return []

    async def _drug_group(self, rxcui: str) -> dict[str, Any] | None:
        """Name/TTY from RxNorm properties plus the ATC classes of exactly that RxCUI."""
        if not rxcui:
            return None
        props_data = await self._get(f"{RXNAV_BASE_URL}/rxcui/{rxcui}/properties.json")
        props = props_data.get("properties") or {}
        if not props.get("rxcui"):
            return None
        data = await self._get(
            f"{RXCLASS_URL}/class/byRxcui.json", {"rxcui": rxcui, "relaSource": ATC_SOURCE}
        )
        # byRxcui also lists combination products containing the ingredient; keep this RxCUI.
        own = [g for g in self._group_drug_info(data) if g["rxcui"] == rxcui]
        return {
            "rxcui": rxcui,
            "name": props.get("name", ""),
            "tty": props.get("tty", ""),
            "synonym": props.get("synonym", ""),
            "umlscui": props.get("umlscui", ""),
            "classes": own[0]["classes"] if own else [],
        }

    async def _class_members(self, class_id: str, level: int) -> list[dict[str, Any]]:
        """Member drugs of an ATC class with their level 5 code (cached per class)."""
        key = f"{class_id}"
        if key in self._members:
            return self._members[key]
        params: dict[str, Any] = {"classId": class_id, "relaSource": ATC_SOURCE}
        if level < 4:
            params["ttys"] = "IN"
        data = await self._get(f"{RXCLASS_URL}/classMembers.json", params)
        members: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in (data.get("drugMemberGroup") or {}).get("drugMember") or []:
            drug = item.get("minConcept") or {}
            attrs = {a.get("attrName"): a.get("attrValue") for a in item.get("nodeAttr") or []}
            rxcui = str(drug.get("rxcui") or "")
            code = attrs.get("SourceId") or ""
            if not rxcui or (rxcui, code) in seen:
                continue
            seen.add((rxcui, code))
            members.append(
                {
                    "rxcui": rxcui,
                    "name": drug.get("name", ""),
                    "tty": drug.get("tty", ""),
                    "atc_code": code,
                    "atc_name": attrs.get("SourceName", ""),
                    "relation": attrs.get("Relation", ""),
                }
            )
        if members:
            self._members[key] = members
        return members

    async def _atc5_member(self, code: str) -> dict[str, Any] | None:
        for member in await self._class_members(code[:5], 4):
            if member["atc_code"] == code:
                return member
        return None

    async def _atc5_drug(self, code: str) -> UnifiedConcept | None:
        member = await self._atc5_member(code)
        if not member:
            return None
        concept = self._create_concept(member["rxcui"], member["name"], ConceptType.DRUG)
        concept.semantic_types = [member["tty"]] if member["tty"] else []
        concept.categories = [f"ATC {code}"]
        concept.source_data[KnowledgeSource.RXCLASS] = {  # type: ignore[index]
            "kind": "drug",
            "rxcui": member["rxcui"],
            "tty": member["tty"],
            "atc_code": code,
            "atc_name": member["atc_name"],
        }
        return concept

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _class_concept(
        self, code: str, name: str, classes: dict[str, str] | None = None
    ) -> UnifiedConcept:
        level = atc_level(code)
        concept = self._create_concept(code, name, ConceptType.DRUG)
        concept.categories = [f"ATC level {level}"] if level else []
        concept.semantic_types = ["ATC class"]
        data: dict[str, Any] = {
            "kind": "atc_class",
            "class_type": ATC_CLASS_TYPES,
            "atc_level": level,
        }
        if classes is not None:
            parent = _parent_code(code)
            if parent and parent in classes:
                concept.parents = [classes[parent]]
                data["parent_id"] = parent
            concept.children = [classes[c] for c in self._children(code, classes)]
        concept.source_data[KnowledgeSource.RXCLASS] = data  # type: ignore[index]
        return concept

    def _drug_concept(self, group: dict[str, Any]) -> UnifiedConcept:
        concept = self._create_concept(group["rxcui"], group["name"], ConceptType.DRUG)
        concept.semantic_types = [group["tty"]] if group.get("tty") else []
        if group.get("synonym"):
            concept.synonyms = [group["synonym"]]
        concept.categories = [f"ATC {c['id']}" for c in group["classes"]]
        concept.source_data[KnowledgeSource.RXCLASS] = {  # type: ignore[index]
            "kind": "drug",
            "rxcui": group["rxcui"],
            "tty": group.get("tty"),
            "atc_classes": group["classes"],
        }
        return concept

    @staticmethod
    def _atc_edge(cls: dict[str, Any]) -> dict[str, Any]:
        return {
            "relation_label": "has_atc_class",
            "related_id": cls["id"],
            "related_name": cls["name"],
            "source": "RxClass",
            "atc_level": cls.get("level"),
        }

    @staticmethod
    def _class_edge(label: str, code: str, name: str) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": code,
            "related_name": name,
            "source": "RxClass",
            "atc_level": atc_level(code),
        }

    @staticmethod
    def _mapping(
        from_id: str, from_src: str, to_id: str, to_src: str, mtype: str, conf: float
    ) -> dict[str, Any]:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": from_src,
            "toSource": to_src,
            "mappingType": mtype,
            "confidence": conf,
        }
