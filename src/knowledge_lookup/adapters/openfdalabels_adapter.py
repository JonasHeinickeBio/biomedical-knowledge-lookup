"""
openFDA drug labels (DailyMed SPL) Knowledge Source Adapter

Adapter for the openFDA drug label endpoint (https://api.fda.gov/drug/label.json), which
mirrors the structured product labels (SPL) published on DailyMed: indications, boxed
warnings, contraindications, adverse reactions, drug interactions, dosage ... as text
sections, plus an ``openfda`` block that harmonises names, UNII, RxCUI, NDC and
pharmacologic classes. Contrast: openFDA *events* (FAERS) are spontaneous reports of what
happened to patients; this endpoint is what the manufacturer's approved label *says*.

What the API serves (live-verified, October 2026):

- Keyless. Documented limits: 240 requests/min and 1,000/day per IP without a key, 240/min
  and 120,000/day per key. A key (``OPENFDA_API_KEY`` or ``api_keys["openfda"]``) is sent as
  the ``api_key`` parameter; requests are spaced at ~3.5/s here. No match is ``404`` with
  ``{"error": {"code": "NOT_FOUND"}}`` (treated as "no results", not as a failure).
- One result is one label (SPL version) identified by ``set_id`` (stable across label
  versions; used as the concept id) and ``id`` (this version only). ``effective_time`` and
  ``version`` give the label date and revision. There is NO field selection: every hit
  returns the whole label (18 KB for a short OTC label, ~170 KB for a prescription label), so
  a 20-label search transfers 1-2 MB. Sections are lists of strings; ``*_table`` keys carry
  HTML tables.
- Search syntax: ``field:"phrase"`` with ``AND`` / ``OR``; ``openfda.generic_name``,
  ``openfda.brand_name``, ``openfda.substance_name`` and any section name
  (``indications_and_usage:"fatigue"``) are searchable; the API tokenises and stems text, so
  phrase queries match anywhere in a field. Results are not ranked by relevance.
- Some labels (homeopathic, unapproved, old) have no ``openfda`` block: their label is taken
  from ``spl_product_data_elements``.
- ``openfda.substance_name`` and ``openfda.unii`` are NOT index-aligned (an ibuprofen /
  acetaminophen label lists the names and UNIIs in different orders), so UNIIs are never
  paired with names unless a label has exactly one of each. ``openfda.rxcui`` holds
  product-level RxCUIs (SCD/SBD, e.g. 308416), not the ingredient's (use the RxNorm adapter).
- The data is not validated by FDA; the disclaimer is "Do not rely on openFDA to make
  decisions regarding medical care". Terms: https://open.fda.gov/terms/, licence CC0 for the
  openFDA contribution (https://open.fda.gov/license/); label text is public FDA data.

Identifiers: SPL set ids (UUIDs, e.g. ``0058175f-3474-40c3-a046-6cfaec86d84b``); a
``DAILYMED:`` / ``SETID:`` prefix is accepted. Full section text: :meth:`get_label_section`.
"""

import asyncio
import logging
import os
import re
import time
from typing import Any, cast

from ..base import KnowledgeSourceAdapter, _is_not_found
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
OPENFDA_SOURCE_NAME = "openFDA"
DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={}"

# 240 requests/min documented; stay below with ~3.5 requests/s.
_MIN_INTERVAL = 0.3
# The API allows up to 1000 hits per call; labels are big, so cap what one search pulls.
_MAX_HITS = 100
# Characters kept per section in a concept (the full text stays reachable by set id).
_SECTION_CHARS = 1500
_DEFINITION_CHARS = 500
_TITLE_CHARS = 60
# Cap on package NDCs mapped for one label (large unit-of-sale lists exist).
_MAX_PACKAGE_NDCS = 25

_SET_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_PREFIX_RE = re.compile(r"^(DAILYMED|SETID|SET_ID|SPL)\s*:\s*", re.IGNORECASE)

# Label sections kept (trimmed) in a concept's source_data.
CONCEPT_SECTIONS = (
    "indications_and_usage",
    "boxed_warning",
    "contraindications",
    "warnings",
    "warnings_and_cautions",
    "precautions",
    "adverse_reactions",
    "drug_interactions",
    "dosage_and_administration",
)
# Friendly names accepted by get_label_section.
SECTION_ALIASES = {
    "indications": "indications_and_usage",
    "indication": "indications_and_usage",
    "dosage": "dosage_and_administration",
    "dose": "dosage_and_administration",
    "interactions": "drug_interactions",
    "adverse": "adverse_reactions",
    "side_effects": "adverse_reactions",
    "boxed": "boxed_warning",
    "black_box": "boxed_warning",
    "warning": "warnings",
}
# Keys of a label that are metadata, not text sections.
_META_KEYS = {"openfda", "set_id", "id", "effective_time", "version"}
_PHARM_CLASS_FIELDS = {
    "pharm_class_epc": "EPC",
    "pharm_class_moa": "MoA",
    "pharm_class_pe": "PE",
    "pharm_class_cs": "CS",
}
_STRING_LIST_FIELDS = (
    "brand_name",
    "generic_name",
    "substance_name",
    "manufacturer_name",
    "product_type",
    "route",
    "rxcui",
    "unii",
    "product_ndc",
    "package_ndc",
    "application_number",
    "spl_id",
    "nui",
    *_PHARM_CLASS_FIELDS,
)


def _first(values: Any) -> str:
    return str(values[0]) if isinstance(values, list) and values else ""


def _text(value: Any) -> str:
    """Section value (list of strings or string) -> one text."""
    if isinstance(value, list):
        return "\n\n".join(str(v) for v in value if v)
    return str(value) if value else ""


def _quote(text: str) -> str:
    """Escape a phrase for the openFDA query syntax (no quotes/backslashes survive)."""
    return re.sub(r'["\\]', " ", text).strip()


class OpenFDALabelsAdapter(KnowledgeSourceAdapter):
    """Adapter for openFDA drug labels (DailyMed SPL); keyless, optional API key."""

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get_api_key("openfda") or os.getenv("OPENFDA_API_KEY")
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OPENFDALABELS

    def is_available(self) -> bool:
        return True  # keyless public service; a key only raises the daily quota

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_id(concept_id: str) -> str | None:
        """``DAILYMED:<uuid>`` / ``<UUID>`` -> lower-case SPL set id; anything else ``None``."""
        if not isinstance(concept_id, str):
            return None
        bare = _PREFIX_RE.sub("", concept_id.strip()).strip().lower()
        return bare if _SET_ID_RE.match(bare) else None

    @staticmethod
    def normalize_section(section: str) -> str | None:
        """``"Boxed Warning"`` / ``"boxed"`` -> ``"boxed_warning"``; invalid -> ``None``."""
        if not isinstance(section, str):
            return None
        key = re.sub(r"[\s\-]+", "_", section.strip().lower())
        key = SECTION_ALIASES.get(key, key)
        return key if re.fullmatch(r"[a-z_]+", key) and key not in _META_KEYS else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Labels by generic, brand or substance name; else by text in the indications.

        ``aspirin`` / ``Advil`` hit the name fields; a query that names no drug
        (``fatigue``) falls back to a phrase search in ``indications_and_usage``. A set id
        returns that label. Each hit carries the whole label from the API, so keep ``limit``
        small (see the module docstring for sizes).
        """
        query = _quote(query or "")
        if not query or limit <= 0:
            return []
        try:
            set_id = self.normalize_id(query)
            if set_id:
                concept = await self.get_concept_details(set_id)
                return [concept] if concept else []

            n = min(limit, _MAX_HITS)
            names = (
                f'openfda.generic_name:"{query}" OR openfda.brand_name:"{query}"'
                f' OR openfda.substance_name:"{query}"'
            )
            labels = await self._search(names, n)
            if not labels:
                labels = await self._search(f'indications_and_usage:"{query}"', n)
            concepts = self._dedupe([self._concept(label) for label in labels])
            logger.info(f"openFDA labels search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"openFDA labels search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """One label by SPL set id."""
        set_id = self.normalize_id(concept_id)
        if not set_id:
            logger.warning(f"openFDA labels: '{concept_id}' is not an SPL set id")
            return None
        try:
            label = await self._label(set_id)
            return self._concept(label) if label else None
        except Exception as e:
            logger.error(f"openFDA labels get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Label -> substances, pharmacologic classes and RxNorm products.

        - ``has_ingredient`` -> one edge per ``substance_name`` (``related_id`` is the
          substance name; ``unii`` is set only when the label has exactly one substance
          and one UNII, because the two lists are not aligned; ``label_uniis`` always
          lists all UNIIs of the label).
        - ``has_pharm_class`` -> established pharmacologic class (EPC), mechanism of
          action (MoA), physiologic effect (PE) and chemical structure (CS) from
          ``openfda``; ``class_type`` says which, ``related_id`` is the class text such as
          "Cyclooxygenase Inhibitors [MoA]".
        - ``has_rxnorm_product`` -> product-level RxCUIs (SCD/SBD); feed them to the RxNorm
          adapter for ingredients and ATC.

        Labels without an ``openfda`` block have no relationships. ``limit`` caps each label.
        """
        set_id = self.normalize_id(concept_id)
        if not set_id or limit <= 0:
            return []
        try:
            label = await self._label(set_id)
            if not label:
                return []
            meta = label.get("openfda") or {}
            rels: list[dict[str, Any]] = []
            substances = self._strings(meta, "substance_name")
            uniis = self._strings(meta, "unii")
            single = len(substances) == 1 and len(uniis) == 1
            for name in substances[:limit]:
                rels.append(
                    {
                        "relation_label": "has_ingredient",
                        "related_id": name,
                        "related_name": name,
                        "source": OPENFDA_SOURCE_NAME,
                        "unii": uniis[0] if single else None,
                        "label_uniis": uniis,
                    }
                )
            count = 0
            for field, class_type in _PHARM_CLASS_FIELDS.items():
                for text in self._strings(meta, field):
                    if count >= limit:
                        break
                    count += 1
                    rels.append(
                        {
                            "relation_label": "has_pharm_class",
                            "related_id": text,
                            "related_name": re.sub(r"\s*\[[^\]]*\]$", "", text),
                            "source": OPENFDA_SOURCE_NAME,
                            "class_type": class_type,
                        }
                    )
            for rxcui in self._strings(meta, "rxcui")[:limit]:
                rels.append(
                    {
                        "relation_label": "has_rxnorm_product",
                        "related_id": rxcui,
                        "related_name": "",
                        "source": OPENFDA_SOURCE_NAME,
                    }
                )
            return rels
        except Exception as e:
            logger.warning(f"openFDA labels get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """RxCUI, UNII, NDC, FDA application number and the DailyMed page of a label.

        RxCUIs are product-level (SCD/SBD); UNIIs are listed unpaired (see
        :meth:`get_relationships`); NDCs are product NDCs plus up to 25 package NDCs.
        """
        set_id = self.normalize_id(concept_id)
        if not set_id:
            return []
        try:
            label = await self._label(set_id)
            if not label:
                return []
            meta = label.get("openfda") or {}
            specs = (
                ("rxcui", "RxNorm", "product_rxcui", None),
                ("unii", "UNII", "xref", None),
                ("product_ndc", "NDC", "product_ndc", None),
                ("package_ndc", "NDC", "package_ndc", _MAX_PACKAGE_NDCS),
                ("application_number", "FDA_APPLICATION", "application_number", None),
            )
            mappings = [self._mapping(set_id, DAILYMED_URL.format(set_id), "DailyMed", "url")]
            seen: set[tuple[str, str]] = set()
            for field, to_source, mapping_type, cap in specs:
                for value in self._strings(meta, field)[:cap]:
                    if (to_source, value) not in seen:
                        seen.add((to_source, value))
                        mappings.append(self._mapping(set_id, value, to_source, mapping_type))
            return mappings
        except Exception as e:
            logger.warning(f"openFDA labels get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_label_section(self, set_id: str, section: str) -> str | None:
        """Full, untrimmed text of one section of a label, fetched live.

        ``section`` is an openFDA field name (``boxed_warning``, ``adverse_reactions``,
        ``drug_interactions``, ``contraindications``, ``dosage_and_administration`` ...) or
        an alias (``boxed``, ``indications``, ``dosage``, ``interactions``). Paragraphs are
        joined by blank lines. Returns ``None`` when the label or the section does not exist
        (the concept's ``section_names`` lists what a label has). Nothing is cached, so long
        sections are not held in memory.
        """
        normalized = self.normalize_id(set_id)
        key = self.normalize_section(section)
        if not normalized or not key:
            return None
        try:
            label = await self._label(normalized)
            text = _text((label or {}).get(key))
            return text or None
        except Exception as e:
            logger.warning(f"openFDA labels get_label_section failed for '{set_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _search(self, search: str, limit: int) -> list[dict[str, Any]]:
        """Throttled label search; ``404 NOT_FOUND`` means no hits."""
        async with self._throttle_lock:
            wait = self._last_request + _MIN_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        params: dict[str, Any] = {"search": search, "limit": limit}
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            data = await self._make_request(
                OPENFDA_LABEL_URL, params, headers={"Accept": "application/json"}
            )
        except Exception as e:
            if _is_not_found(e):
                return []
            raise
        results = data.get("results") if isinstance(data, dict) else None
        return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []

    async def _label(self, set_id: str) -> dict[str, Any] | None:
        labels = await self._search(f'set_id:"{set_id}"', 1)
        return labels[0] if labels else None

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _strings(meta: dict[str, Any], field: str) -> list[str]:
        """De-duplicated non-empty strings of an ``openfda`` list field, order kept."""
        values = meta.get(field)
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(str(v) for v in values if v))

    @staticmethod
    def _title(label: dict[str, Any]) -> str:
        """Fallback name for labels without ``openfda`` names: the start of the SPL product
        text ("<product name> <ingredient names> ..."), cut at a word boundary."""
        text = " ".join(_first(label.get("spl_product_data_elements")).split())
        if len(text) <= _TITLE_CHARS:
            return text
        return text[:_TITLE_CHARS].rsplit(" ", 1)[0]

    @staticmethod
    def _dedupe(concepts: list[UnifiedConcept]) -> list[UnifiedConcept]:
        seen: set[str] = set()
        unique = []
        for concept in concepts:
            if concept.primary_id not in seen:
                seen.add(concept.primary_id)
                unique.append(concept)
        return unique

    def _concept(self, label: dict[str, Any]) -> UnifiedConcept:
        """Build a concept from a label; sections are trimmed, the rest stays in the API."""
        set_id = str(label.get("set_id") or label.get("id") or "")
        meta = label.get("openfda") or {}
        brands = self._strings(meta, "brand_name")
        generics = self._strings(meta, "generic_name")
        name = brands[0] if brands else generics[0] if generics else self._title(label) or set_id

        concept = self._create_concept(set_id, name, ConceptType.DRUG)
        concept.identifiers = []  # re-added below with a link
        concept.add_identifier(self.source, set_id, name, DAILYMED_URL.format(set_id))
        others = brands[1:] + generics + self._strings(meta, "substance_name")
        categories = self._strings(meta, "product_type")
        categories += [f"route:{r}" for r in self._strings(meta, "route")]
        if label.get("boxed_warning"):
            categories.append("boxed warning")
        indications = _text(label.get("indications_and_usage"))
        full = {key: _text(label[key]) for key in CONCEPT_SECTIONS if label.get(key)}
        sections = {key: text[:_SECTION_CHARS] for key, text in full.items()}
        data: dict[str, Any] = {
            "set_id": set_id,
            "spl_id": label.get("id"),
            "version": label.get("version"),
            "effective_time": label.get("effective_time"),
            "openfda": {k: self._strings(meta, k) for k in _STRING_LIST_FIELDS if meta.get(k)},
            "sections": sections,
            "sections_truncated": [k for k, text in full.items() if len(text) > _SECTION_CHARS],
            "section_names": sorted(
                k
                for k, v in label.items()
                if k not in _META_KEYS
                and not k.endswith("_table")
                and k != "spl_product_data_elements"
                and isinstance(v, str | list)
                and v
            ),
        }
        concept.semantic_types = ["drug label"]
        concept.synonyms = [o for o in dict.fromkeys(others) if o != name]
        concept.categories = categories
        concept.definitions = [indications[:_DEFINITION_CHARS]] if indications else []
        cast(dict[Any, Any], concept.source_data)[KnowledgeSource.OPENFDALABELS] = data
        concept.confidence_score = 0.9
        return concept

    @staticmethod
    def _mapping(from_id: str, to_id: str, to_source: str, mapping_type: str) -> dict[str, Any]:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "SPL",
            "toSource": to_source,
            "mappingType": mapping_type,
            "confidence": 1.0,
        }
