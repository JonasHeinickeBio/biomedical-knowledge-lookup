"""
RxNorm Knowledge Source Adapter

Adapter for NLM RxNorm through the keyless RxNav REST service
(https://rxnav.nlm.nih.gov/REST/). Main use: harmonise registry medications (free-text
drug names, brand names, clinical drug strings) to RxCUIs and from there to ATC, DrugBank,
SNOMED CT, UNII and VUID codes. For ATC *classes* see :mod:`rxclass_adapter`.

What RxNav serves (live-verified):

- Concepts are RxCUIs with a term type (``tty``): ``IN`` ingredient (``1191`` aspirin),
  ``PIN`` precise ingredient, ``MIN`` multiple ingredients, ``BN`` brand name (``153010``
  Advil), ``SCD`` / ``SBD`` semantic clinical / branded drug (``243670`` aspirin 81 MG Oral
  Tablet), ``DF`` dose form (``317541`` Oral Tablet) and the pack / component types.
- ``rxcui.json?name=`` is an exact (normalised) match and also resolves brand names;
  ``drugs.json?name=`` returns everything that contains the name, grouped by term type
  (aspirin: ~37 KB); ``approximateTerm.json`` is the fuzzy fallback for misspellings.
- Every path must end in ``.json``: RxNav answers XML otherwise, whatever ``Accept`` says.
  Unknown RxCUIs answer ``{}`` with HTTP 200, not 404.
- ``rxcui/{id}/related.json?tty=A+B`` returns the directly related concepts of the given
  term types. For an ingredient it spans several hops (aspirin -> 111 SCD, 46 SBD), so
  relationships are capped per relation label.
- ``rxcui/{id}/allProperties.json?prop=codes`` lists the other vocabularies' codes (ATC,
  DrugBank, SNOMED CT, UNII, VUID ...). It also lists every SPL set id (ibuprofen: ~1,000,
  150 KB), which is why that response is cached on the adapter and SPL ids are not mapped
  (use the openFDA labels adapter for labels). MeSH is not among the code types RxNav
  exposes (``idtypes.json``), so there is no MeSH mapping.
- NDCs (``rxcui/{id}/ndcs.json``) exist only for product-level concepts (SCD/SBD/packs); an
  ingredient answers an empty list.
- RxNav asks for at most 20 requests/s per IP; calls are spaced to ~16/s. The service is
  sometimes slow (1-9 s per call was measured), so the request timeout floor is raised.

Licence: RxNorm is a public NLM product; the RxNav API needs no key. Some RxNorm content
derives from licensed sources (e.g. First Databank / Gold Standard / Micromedex terms are
not redistributed, only RxNorm's own names); see https://www.nlm.nih.gov/research/umls/rxnorm/.

Identifiers: RxCUI (``1191``, ``RXCUI:1191``, ``RxNorm:1191``).
"""

import asyncio
import logging
import re
import time
from typing import Any, cast

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
RXNORM_SOURCE_NAME = "RxNorm"

# RxNav asks for at most 20 requests/s per IP; stay clearly below that.
_MIN_INTERVAL = 0.06
# Minimum approximateTerm score accepted as "probably the same drug" (same as RxClass).
_MIN_APPROX_SCORE = 10.0
# Fuzzy matching resolves at most this many candidates (one properties call each).
_MAX_APPROX_CANDIDATES = 5
# Distinct (hashable) allProperties responses kept per adapter instance.
_CODES_CACHE_SIZE = 64

_PREFIX_RE = re.compile(r"^(RXCUI|RXNORM)\s*:\s*", re.IGNORECASE)

TTY_LABELS = {
    "IN": "ingredient",
    "PIN": "precise ingredient",
    "MIN": "multiple ingredients",
    "BN": "brand name",
    "SCD": "clinical drug",
    "SBD": "branded drug",
    "SCDC": "clinical drug component",
    "SBDC": "branded drug component",
    "SCDF": "clinical drug form",
    "SBDF": "branded drug form",
    "SCDG": "clinical drug group",
    "SBDG": "branded drug group",
    "DF": "dose form",
    "DFG": "dose form group",
    "GPCK": "generic pack",
    "BPCK": "branded pack",
}
# Search result order: ingredients and brands before products, products before parts.
_TTY_RANK = {t: i for i, t in enumerate(TTY_LABELS)}

# Related term types to fetch per source term type (one ``related.json`` call).
_RELATED_TTYS: dict[str, tuple[str, ...]] = {
    "IN": ("BN", "PIN", "SCD", "SBD"),
    "MIN": ("BN", "SCD", "SBD"),
    "PIN": ("IN",),
    "BN": ("IN", "SBD"),
    "SCD": ("IN", "DF", "SBD"),
    "SBD": ("IN", "DF", "BN", "SCD"),
}
# (source tty, target tty) -> relation label. Labels follow RxNorm's RELA names where one
# was verified live (has_tradename, ingredient_of, has_dose_form, tradename_of, form_of).
_REL_LABELS: dict[tuple[str, str], str] = {
    ("IN", "BN"): "has_tradename",
    ("IN", "PIN"): "has_form",
    ("IN", "SCD"): "ingredient_of",
    ("IN", "SBD"): "ingredient_of",
    ("MIN", "BN"): "has_tradename",
    ("MIN", "SCD"): "ingredient_of",
    ("MIN", "SBD"): "ingredient_of",
    ("PIN", "IN"): "form_of",
    ("BN", "IN"): "tradename_of",
    ("BN", "SBD"): "has_branded_drug",
    ("SCD", "IN"): "has_ingredient",
    ("SCD", "DF"): "has_dose_form",
    ("SCD", "SBD"): "has_tradename",
    ("SBD", "IN"): "has_ingredient",
    ("SBD", "DF"): "has_dose_form",
    ("SBD", "BN"): "has_brand_name",
    ("SBD", "SCD"): "tradename_of",
}

# RxNav code type (``propName``) -> (label used as toSource, mapping type).
_CODE_TYPES: dict[str, tuple[str, str]] = {
    "DRUGBANK": ("DrugBank", "xref"),
    "UNII_CODE": ("UNII", "xref"),
    "SNOMEDCT": ("SNOMEDCT", "xref"),
    "ATC": ("ATC", "atc_code"),
    "VUID": ("VUID", "xref"),
    "USP": ("USP", "xref"),
    "HCPCS": ("HCPCS", "xref"),
    "GFC": ("GFC", "xref"),
    "GCN_SEQNO": ("GCN_SEQNO", "xref"),
    "HIC_SEQN": ("HIC_SEQN", "xref"),
    "CVX": ("CVX", "xref"),
}


class RxNormAdapter(KnowledgeSourceAdapter):
    """Adapter for NLM RxNorm (RxNav REST, keyless)."""

    # RxNav is intermittently slow (several seconds per call): avoid cut-off + retry loops.
    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = RXNAV_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._codes: dict[str, list[tuple[str, str]]] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.RXNORM

    def is_available(self) -> bool:
        return True  # keyless public service

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_id(concept_id: str) -> str | None:
        """``RXCUI:1191`` / ``RxNorm:1191`` / ``1191`` -> ``"1191"``; anything else ``None``."""
        if not isinstance(concept_id, str):
            return None
        bare = _PREFIX_RE.sub("", concept_id.strip()).strip()
        return bare if bare.isdigit() else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search by drug name: exact (also brands), then contains-match, then fuzzy.

        The three steps are tried in that order and the first one that finds anything
        wins, so a misspelling costs up to four requests but a clean name costs one or two.
        An RxCUI query returns that concept.
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            rxcui = self.normalize_id(query)
            if rxcui:
                concept = await self.get_concept_details(rxcui)
                return [concept] if concept else []

            ids = await self._exact_ids(query)
            if ids:
                props = await self._properties_many(ids[:limit])
                concepts = [self._concept(p, 0.95) for p in props]
            else:
                concepts = await self._contains_search(query, limit)
                if not concepts:
                    concepts = await self._approximate_search(query, limit)
            logger.info(f"RxNorm search for '{query}' returned {len(concepts[:limit])} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"RxNorm search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for one RxCUI (name, term type, synonym, UMLS CUI)."""
        rxcui = self.normalize_id(concept_id)
        if not rxcui:
            logger.warning(f"RxNorm: '{concept_id}' is not an RxCUI")
            return None
        try:
            props = await self._properties(rxcui)
            return self._concept(props, 1.0) if props else None
        except Exception as e:
            logger.error(f"RxNorm get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Typed relationships (one ``related.json`` call plus the cached properties call).

        - ingredient: ``has_tradename`` -> brands, ``has_form`` -> precise ingredients,
          ``ingredient_of`` -> clinical (SCD) and branded (SBD) drugs.
        - brand: ``tradename_of`` -> ingredient, ``has_branded_drug`` -> SBD.
        - clinical / branded drug: ``has_ingredient``, ``has_dose_form`` (the dose form),
          ``has_tradename`` (SCD -> SBD), ``tradename_of`` (SBD -> SCD), ``has_brand_name``.
        - precise ingredient: ``form_of`` -> ingredient.

        ``limit`` caps each relation label (an ingredient has hundreds of products). Other
        term types (components, forms, groups, dose forms) return ``[]``: dose forms relate
        to thousands of products and RxNorm's own component graph is rarely what the
        caller wants.
        """
        rxcui = self.normalize_id(concept_id)
        if not rxcui or limit <= 0:
            return []
        try:
            props = await self._properties(rxcui)
            tty = (props or {}).get("tty", "")
            targets = _RELATED_TTYS.get(tty)
            if not targets:
                return []
            data = await self._get(
                f"{RXNAV_BASE_URL}/rxcui/{rxcui}/related.json", {"tty": " ".join(targets)}
            )
            groups = (data.get("relatedGroup") or {}).get("conceptGroup") or []
            rels: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for group in groups:
                target_tty = group.get("tty", "")
                label = _REL_LABELS.get((tty, target_tty))
                if not label:
                    continue
                for item in (group.get("conceptProperties") or [])[:limit]:
                    related_id = str(item.get("rxcui") or "")
                    if not related_id or (label, related_id) in seen:
                        continue
                    seen.add((label, related_id))
                    rels.append(
                        {
                            "relation_label": label,
                            "related_id": related_id,
                            "related_name": item.get("name", ""),
                            "source": RXNORM_SOURCE_NAME,
                            "tty": target_tty,
                        }
                    )
            return rels
        except Exception as e:
            logger.warning(f"RxNorm get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Codes of the same concept in other vocabularies.

        DrugBank, UNII, SNOMED CT, ATC (level 5 codes), VUID, USP, HCPCS and a few legacy
        drug codes come from ``allProperties?prop=codes``; the UMLS CUI comes from the
        concept properties (empty for many drugs). Not every concept has every code:
        ingredients carry most of them, clinical drugs few.
        """
        rxcui = self.normalize_id(concept_id)
        if not rxcui:
            return []
        try:
            props = await self._properties(rxcui)
            if not props:
                return []
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for name, value in await self._code_properties(rxcui):
                spec = _CODE_TYPES.get(name)
                if not spec or (name, value) in seen:
                    continue
                seen.add((name, value))
                mappings.append(self._mapping(rxcui, value, spec[0], spec[1], 1.0))
            if props.get("umlscui"):
                mappings.append(self._mapping(rxcui, props["umlscui"], "UMLS", "umls_cui", 0.9))
            return mappings
        except Exception as e:
            logger.warning(f"RxNorm get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_ndc(self, rxcui: str) -> list[str]:
        """National Drug Codes (11-digit, no hyphens) of a product-level RxCUI.

        Live-verified: ``243670`` (aspirin 81 MG Oral Tablet) returns six NDCs; ingredient
        and brand concepts (``1191``, ``153010``) return ``[]`` because NDCs are attached
        to SCD/SBD/pack concepts only. Registry coding usually wants the product RxCUI
        first (see :meth:`get_relationships`).
        """
        bare = self.normalize_id(rxcui)
        if not bare:
            return []
        try:
            data = await self._get(f"{RXNAV_BASE_URL}/rxcui/{bare}/ndcs.json")
            ndcs = ((data.get("ndcGroup") or {}).get("ndcList") or {}).get("ndc") or []
            return [str(n) for n in ndcs if n]
        except Exception as e:
            logger.warning(f"RxNorm get_ndc failed for '{rxcui}': {e}")
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

    async def _exact_ids(self, name: str) -> list[str]:
        """Normalised exact name match (``search=2``), brand names included."""
        data = await self._get(f"{RXNAV_BASE_URL}/rxcui.json", {"name": name, "search": 2})
        ids = (data.get("idGroup") or {}).get("rxnormId") or []
        return [str(i) for i in ids if i]

    async def _properties(self, rxcui: str) -> dict[str, Any] | None:
        data = await self._get(f"{RXNAV_BASE_URL}/rxcui/{rxcui}/properties.json")
        props = data.get("properties")
        return props if isinstance(props, dict) and props.get("rxcui") else None

    async def _properties_many(self, rxcuis: list[str]) -> list[dict[str, Any]]:
        found = await asyncio.gather(*(self._properties(r) for r in rxcuis))
        return [p for p in found if p]

    async def _contains_search(self, name: str, limit: int) -> list[UnifiedConcept]:
        """``drugs.json``: concepts whose name contains the query, grouped by term type."""
        data = await self._get(f"{RXNAV_BASE_URL}/drugs.json", {"name": name})
        groups = (data.get("drugGroup") or {}).get("conceptGroup") or []
        items = [p for g in groups for p in (g.get("conceptProperties") or [])]
        items.sort(key=lambda p: _TTY_RANK.get(p.get("tty", ""), len(_TTY_RANK)))
        return [self._concept(p, 0.7) for p in items[:limit] if p.get("rxcui")]

    async def _approximate_search(self, name: str, limit: int) -> list[UnifiedConcept]:
        """Fuzzy fallback for misspellings, ignoring weak candidates."""
        data = await self._get(
            f"{RXNAV_BASE_URL}/approximateTerm.json",
            {"term": name, "maxEntries": min(limit, _MAX_APPROX_CANDIDATES) * 2, "option": 1},
        )
        candidates = (data.get("approximateGroup") or {}).get("candidate") or []
        scores: dict[str, float] = {}
        for cand in candidates:
            try:
                score = float(cand.get("score", 0))
            except (TypeError, ValueError):
                continue
            rxcui = str(cand.get("rxcui") or "")
            if rxcui and score >= _MIN_APPROX_SCORE:
                scores.setdefault(rxcui, score)
        ids = list(scores)[: min(limit, _MAX_APPROX_CANDIDATES)]
        concepts = []
        for props in await self._properties_many(ids):
            extra = {"approximate_score": scores[props["rxcui"]]}
            concepts.append(self._concept(props, 0.6, extra))
        return concepts

    async def _code_properties(self, rxcui: str) -> list[tuple[str, str]]:
        """``(code type, code)`` pairs of ``allProperties?prop=codes``, cached per RxCUI."""
        if rxcui in self._codes:
            return self._codes[rxcui]
        data = await self._get(
            f"{RXNAV_BASE_URL}/rxcui/{rxcui}/allProperties.json", {"prop": "codes"}
        )
        items = (data.get("propConceptGroup") or {}).get("propConcept") or []
        pairs = [
            (str(i["propName"]), str(i["propValue"]))
            for i in items
            if i.get("propName") in _CODE_TYPES and i.get("propValue")
        ]
        if len(self._codes) >= _CODES_CACHE_SIZE:
            self._codes.pop(next(iter(self._codes)))
        self._codes[rxcui] = pairs
        return pairs

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _concept(
        self, props: dict[str, Any], confidence: float, extra: dict[str, Any] | None = None
    ) -> UnifiedConcept:
        """Build a concept from RxNav concept properties (``extra`` joins ``source_data``)."""
        rxcui = str(props["rxcui"])
        tty = props.get("tty", "")
        name = props.get("name") or rxcui
        label = TTY_LABELS.get(tty, tty)
        concept = self._create_concept(rxcui, name, ConceptType.DRUG)
        concept.identifiers = []  # re-added below with a link
        concept.add_identifier(
            self.source,
            rxcui,
            name,
            f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}",
        )
        if props.get("umlscui"):
            concept.add_identifier(KnowledgeSource.UMLS, props["umlscui"], name)
        concept.categories = [f"tty:{tty}"] if tty else []
        concept.semantic_types = [label] if label else []
        synonym = props.get("synonym")
        concept.synonyms = [synonym] if synonym and synonym != name else []
        concept.definitions = [f"RxNorm {label or 'concept'} (RxCUI {rxcui}, TTY {tty or '?'})"]
        concept.confidence_score = confidence
        cast(dict[Any, Any], concept.source_data)[KnowledgeSource.RXNORM] = {
            **props,
            **(extra or {}),
        }
        return concept

    @staticmethod
    def _mapping(
        from_id: str, to_id: str, to_source: str, mapping_type: str, confidence: float
    ) -> dict[str, Any]:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": RXNORM_SOURCE_NAME,
            "toSource": to_source,
            "mappingType": mapping_type,
            "confidence": confidence,
        }
