"""
NLM Clinical Tables adapter (Clinical Table Search Service, CTSS).

The Lister Hill Center's CTSS serves many small coding tables behind one uniform, keyless
search API: ``https://clinicaltables.nlm.nih.gov/api/<table>/v3/search?terms=...``. Answers
are positional arrays ``[total, codes, extra_fields, display_rows]`` where ``extra_fields``
is ``{field: [value per returned code]}`` for the ``ef=`` fields (``null`` when none were
asked for). The tables supported here (verified live, see ``docs/adapters/ontologies/
clinicaltables_adapter.md``):

========== ============ ================================================================
table      id prefix    content
========== ============ ================================================================
icd10cm    ICD10CM      ICD-10-CM (US clinical modification, CDC) billable codes
conditions CONDITIONS   ~2,400 consumer conditions (Regenstrief/NLM) with ICD-10-CM and
                        ICD-9-CM codes, synonyms and MedlinePlus links
loinc_items LOINC       LOINC observations, panels, forms and survey questions
hpo        HP           Human Phenotype Ontology terms (definition, synonyms, is_a)
icd11_codes ICD11       WHO ICD-11 MMS stem and extension codes
disease_names DISEASE_NAMES  ClinVar disease names keyed by UMLS/MedGen CUI
========== ============ ================================================================

``ICD-10-GM`` (the German modification used for German registry coding) is **not** this
table and is handled by :mod:`.icd10gm_adapter`; ICD-10-CM codes differ in places (for
example ME/CFS is ``G93.32`` in ICD-10-CM but ``G93.3`` in ICD-10-GM).

Quirks that shaped the code:

- The ICD-10-CM table searches the *code* only by default; names need ``sf=code,name``.
  Multiple words are AND-ed and every word is a prefix match. Dot-less codes (``G9332``)
  do not match, so bare codes are normalised to the dotted form first.
- Search is prefix based, so a code lookup (``terms=G93.3``) returns neighbours too; the
  adapter requests a page and keeps only the exact code.
- Unknown ``ef=`` field names do not fail, they silently come back as ``null``.
- The ``conditions`` table carries no SNOMED CT or MeSH identifiers (only ICD-10-CM, ICD-9-CM
  and MedlinePlus links), and its ICD-10-CM suggestions are curated and older than the
  ``icd10cm`` table (it maps "Chronic fatigue syndrome" to ``R53.82``, not ``G93.32``).
- LOINC content is subject to the LOINC Terms of Use (https://loinc.org/terms-of-use) and
  some items carry an external copyright (``isCopyrighted``).

Usage terms: free, no key or registration; the advised maximum is 25 requests/second (soft
limit, 503 when overloaded). Do not send PHI/PII in queries. The adapter spaces requests
by 0.1 s. The set of searched tables defaults to :data:`DEFAULT_TABLES`, can be set with
the ``CLINICALTABLES_TABLES`` environment variable (comma separated) or per call.
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._vocab_common import Spacer

logger = logging.getLogger(__name__)

BASE_URL = "https://clinicaltables.nlm.nih.gov/api"
TABLES_ENV = "CLINICALTABLES_TABLES"
_MIN_INTERVAL = 0.1  # 10 requests/s, well under the advised 25/s
_MAX_LIST = 500  # service limit for maxList / count
# A page large enough to contain the exact code among its prefix matches (E11 has 87).
_LOOKUP_PAGE = 100

_ICD10CM_RE = re.compile(r"^([A-Z]\d[A-Z0-9])\.?([A-Z0-9]{0,4})$")
_LOINC_RE = re.compile(r"^\d{1,7}-\d$")
_CUI_RE = re.compile(r"^C\d{7}$")
_HPO_RE = re.compile(r"^(?:HPO|HP)[:_]?(\d{7})$", re.IGNORECASE)


@dataclass(frozen=True)
class _Table:
    """How one CTSS table maps onto the unified model."""

    name: str  # API table name
    prefix: str  # CURIE prefix used in concept ids
    concept_type: ConceptType
    code_field: str  # ``cf``: field returned as the code
    label_field: str  # ``df``: field shown as the display string
    extra_fields: tuple[str, ...]  # ``ef``
    lookup_field: str  # ``sf`` for an exact-code lookup
    search_fields: str = ""  # ``sf`` for text search; empty = the service default
    description: str = ""


TABLES: dict[str, _Table] = {
    "icd10cm": _Table(
        name="icd10cm",
        prefix="ICD10CM",
        concept_type=ConceptType.DISEASE,
        code_field="code",
        label_field="name",
        extra_fields=(),
        lookup_field="code",
        search_fields="code,name",  # the default is the code alone
        description="ICD-10-CM",
    ),
    "conditions": _Table(
        name="conditions",
        prefix="CONDITIONS",
        concept_type=ConceptType.DISEASE,
        code_field="key_id",
        label_field="primary_name",
        extra_fields=(
            "consumer_name",
            "icd10cm_codes",
            "icd10cm",
            "term_icd9_code",
            "term_icd9_text",
            "synonyms",
            "info_link_data",
        ),
        lookup_field="key_id",
        description="Consumer medical conditions",
    ),
    "loinc_items": _Table(
        name="loinc_items",
        prefix="LOINC",
        concept_type=ConceptType.OBSERVATION,
        code_field="LOINC_NUM",
        label_field="text",
        extra_fields=(
            "LONG_COMMON_NAME",
            "SHORTNAME",
            "COMPONENT",
            "PROPERTY",
            "METHOD_TYP",
            "CONSUMER_NAME",
            "datatype",
            "isCopyrighted",
        ),
        lookup_field="LOINC_NUM",
        description="LOINC items (observations, panels, forms, survey questions)",
    ),
    "hpo": _Table(
        name="hpo",
        prefix="HP",
        concept_type=ConceptType.PHENOTYPE,
        code_field="id",
        label_field="name",
        extra_fields=(
            "definition",
            "synonym",
            "is_a",
            "xref",
            "alt_id",
            "is_obsolete",
            "comment",
        ),
        lookup_field="id",
        description="Human Phenotype Ontology",
    ),
    "icd11_codes": _Table(
        name="icd11_codes",
        prefix="ICD11",
        concept_type=ConceptType.DISEASE,
        code_field="code",
        label_field="title",
        extra_fields=("definition", "type", "chapter", "source", "indexTerm", "browserUrl"),
        lookup_field="code",
        description="WHO ICD-11 MMS codes",
    ),
    "disease_names": _Table(
        name="disease_names",
        prefix="DISEASE_NAMES",
        concept_type=ConceptType.DISEASE,
        code_field="ConceptID",
        label_field="DiseaseName",
        extra_fields=(),
        lookup_field="ConceptID",
        description="ClinVar disease names (UMLS/MedGen CUIs)",
    ),
}
_BY_PREFIX = {t.prefix: t for t in TABLES.values()}
DEFAULT_TABLES: tuple[str, ...] = ("icd10cm", "conditions", "loinc_items", "hpo")

_LOINC_TERMS = "https://loinc.org/terms-of-use"


def _concept_id(table: _Table, code: str) -> str:
    """``ICD10CM:G93.32``; codes that already are CURIEs (``HP:0012378``) stay as they are."""
    return code if code.upper().startswith(f"{table.prefix}:") else f"{table.prefix}:{code}"


def _first(values: Any, index: int) -> Any:
    """``values[index]`` for the per-code lists in the ``ef`` hash, tolerating gaps."""
    if isinstance(values, list) and 0 <= index < len(values):
        return values[index]
    return None


def _clean(text: Any) -> str:
    return " ".join(str(text).split()) if text is not None else ""


class ClinicalTablesAdapter(KnowledgeSourceAdapter):
    """NLM Clinical Table Search Service: ICD-10-CM, LOINC items, conditions, HPO and more."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = BASE_URL
        self._spacer = Spacer(_MIN_INTERVAL)
        self.tables: tuple[str, ...] = self._tables_from_env()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CLINICALTABLES

    def is_available(self) -> bool:
        return True  # public, keyless

    # ------------------------------------------------------------------
    # configuration / id handling
    # ------------------------------------------------------------------

    @staticmethod
    def _tables_from_env() -> tuple[str, ...]:
        raw = os.getenv(TABLES_ENV, "")
        chosen = ClinicalTablesAdapter._valid_tables(raw.split(",")) if raw.strip() else ()
        return chosen or DEFAULT_TABLES

    @staticmethod
    def _valid_tables(names: Any) -> tuple[str, ...]:
        """Known table names from *names* (ignoring case and blanks), in order, unique."""
        out: list[str] = []
        for name in names:
            key = str(name).strip().lower()
            if not key:
                continue
            if key not in TABLES:
                logger.warning("ClinicalTables: unknown table %r ignored", name)
            elif key not in out:
                out.append(key)
        return tuple(out)

    @staticmethod
    def normalize_icd10cm(code: str) -> str | None:
        """``g9332`` / ``G93.32`` -> ``G93.32``; ``None`` when it is not ICD-10-CM shaped."""
        match = _ICD10CM_RE.match(code.strip().upper())
        if not match:
            return None
        head, tail = match.groups()
        return f"{head}.{tail}" if tail else head

    def _resolve_id(self, concept_id: str) -> tuple[_Table, str] | None:
        """Split ``<PREFIX>:<code>`` (or a recognisable bare code) into (table, code)."""
        raw = (concept_id or "").strip()
        if not raw:
            return None
        hpo = _HPO_RE.match(raw)
        if hpo:
            return TABLES["hpo"], f"HP:{hpo.group(1)}"
        if ":" in raw:
            prefix, _, code = raw.partition(":")
            table = _BY_PREFIX.get(prefix.strip().upper()) or TABLES.get(prefix.strip().lower())
            code = code.strip()
            if table is None or not code:
                return None
            if table.name == "icd10cm":
                code = self.normalize_icd10cm(code) or ""
            return (table, code) if code else None
        if _LOINC_RE.match(raw):
            return TABLES["loinc_items"], raw
        if _CUI_RE.match(raw.upper()):
            return TABLES["disease_names"], raw.upper()
        icd = self.normalize_icd10cm(raw)
        if icd:
            return TABLES["icd10cm"], icd
        return None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _query(self, table: _Table, params: dict[str, Any]) -> list[dict[str, Any]]:
        """One CTSS call, parsed into ``[{"code", "label", "extra": {field: value}}]``.

        Raises on transport errors; a malformed or empty body gives ``[]``.
        """
        await self._spacer.wait()
        query: dict[str, Any] = {
            "cf": table.code_field,
            "df": table.label_field,
            **params,
        }
        if table.extra_fields:
            query["ef"] = ",".join(table.extra_fields)
        payload = await self._make_request(f"{self.base_url}/{table.name}/v3/search", query)
        return self._parse_payload(table, payload)

    @staticmethod
    def _parse_payload(table: _Table, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, list) or len(payload) < 4 or not isinstance(payload[1], list):
            return []
        codes, extras, display = payload[1], payload[2], payload[3]
        extras = extras if isinstance(extras, dict) else {}
        rows: list[dict[str, Any]] = []
        for i, code in enumerate(codes):
            if code in (None, ""):
                continue
            shown = _first(display, i)
            label = _clean(shown[0]) if isinstance(shown, list) and shown else ""
            rows.append(
                {
                    "code": str(code),
                    "label": label,
                    "extra": {k: _first(v, i) for k, v in extras.items()},
                }
            )
        return rows

    # ------------------------------------------------------------------
    # unified model conversion
    # ------------------------------------------------------------------

    def _to_concept(self, table: _Table, row: dict[str, Any]) -> UnifiedConcept | None:
        code, extra = row["code"], row["extra"]
        label = row["label"]
        concept_type = table.concept_type
        synonyms: list[str] = []
        definitions: list[str] = []
        semantic_types: list[str] = []
        parents: list[str] = []
        data: dict[str, Any] = {"table": table.name, "code": code}

        if table.name == "conditions":
            label = label or _clean(extra.get("consumer_name"))
            synonyms = [_clean(extra.get("consumer_name")), *(extra.get("synonyms") or [])]
            data.update(
                icd10cm=self._icd10cm_codes(extra),
                icd9cm=self._icd9_pair(extra),
                info_links=self._info_links(extra),
            )
        elif table.name == "loinc_items":
            label = _clean(extra.get("LONG_COMMON_NAME")) or label
            synonyms = [s for s in (row["label"], extra.get("SHORTNAME")) if s]
            synonyms.append(_clean(extra.get("CONSUMER_NAME")))
            semantic_types = [x for x in (extra.get("PROPERTY"),) if x]
            data.update(
                {k: extra.get(k) for k in ("COMPONENT", "PROPERTY", "METHOD_TYP", "datatype")},
                isCopyrighted=extra.get("isCopyrighted"),
                terms_of_use=_LOINC_TERMS,
            )
        elif table.name == "hpo":
            if extra.get("definition"):
                definitions = [_clean(extra["definition"])]
            synonyms = [
                _clean(s.get("term")) for s in (extra.get("synonym") or []) if isinstance(s, dict)
            ]
            parents = [p["id"] for p in (extra.get("is_a") or []) if isinstance(p, dict)]
            data.update(
                comment=extra.get("comment"),
                is_obsolete=bool(extra.get("is_obsolete")),
                alt_id=extra.get("alt_id"),
            )
        elif table.name == "icd11_codes":
            if extra.get("definition"):
                definitions = [_clean(extra["definition"])]
            synonyms = [s.strip() for s in str(extra.get("indexTerm") or "").split(";")]
            data.update(
                {k: extra.get(k) for k in ("type", "chapter", "source", "browserUrl")},
            )
        elif table.name == "disease_names":
            data["cui"] = code
        if not label:
            return None

        concept = self._create_concept(_concept_id(table, code), label, concept_type)
        seen = {label.lower()}
        unique: list[str] = []
        for syn in synonyms:
            if syn and syn.lower() not in seen:
                seen.add(syn.lower())
                unique.append(syn)
        concept.synonyms = unique
        concept.definitions = definitions
        concept.semantic_types = semantic_types
        concept.parents = parents
        concept.categories = [f"clinicaltables:{table.name}"]
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.CLINICALTABLES] = data
        return concept

    @staticmethod
    def _icd10cm_codes(extra: dict[str, Any]) -> list[dict[str, str]]:
        """``[{"code", "name"}]`` from the ``icd10cm`` objects (``?`` placeholders kept)."""
        out: list[dict[str, str]] = []
        for item in extra.get("icd10cm") or []:
            if isinstance(item, dict) and item.get("code"):
                out.append({"code": str(item["code"]), "name": _clean(item.get("name"))})
        if not out:  # fall back to the comma separated list
            for code in str(extra.get("icd10cm_codes") or "").split(","):
                if code.strip():
                    out.append({"code": code.strip(), "name": ""})
        return out

    @staticmethod
    def _icd9_pair(extra: dict[str, Any]) -> dict[str, str] | None:
        code = _clean(extra.get("term_icd9_code"))
        return {"code": code, "name": _clean(extra.get("term_icd9_text"))} if code else None

    @staticmethod
    def _info_links(extra: dict[str, Any]) -> list[dict[str, str]]:
        """``[{"url", "title"}]`` from ``info_link_data`` (pairs of [url, title])."""
        out: list[dict[str, str]] = []
        for pair in extra.get("info_link_data") or []:
            if isinstance(pair, list) and pair and pair[0]:
                out.append(
                    {"url": str(pair[0]), "title": _clean(pair[1] if len(pair) > 1 else "")}
                )
        return out

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    async def search_concepts(
        self, query: str, limit: int = 20, *, tables: list[str] | tuple[str, ...] | None = None
    ) -> list[UnifiedConcept]:
        """Search the configured tables (default :data:`DEFAULT_TABLES`) in parallel.

        Results from the tables are interleaved so one big table (ICD-10-CM, LOINC) does not
        crowd the others out of *limit*; ids are de-duplicated.
        """
        text = (query or "").strip()
        if not text or limit < 1:
            return []
        chosen = self._valid_tables(tables) if tables else self.tables
        per_table = min(limit, _MAX_LIST)

        async def one(name: str) -> list[UnifiedConcept]:
            table = TABLES[name]
            params: dict[str, Any] = {"terms": text, "maxList": per_table}
            if table.search_fields:
                params["sf"] = table.search_fields
            try:
                rows = await self._query(table, params)
            except Exception as e:
                logger.error(f"ClinicalTables search of {name} failed for '{text}': {e}")
                return []
            return [c for c in (self._to_concept(table, r) for r in rows) if c is not None]

        batches = await asyncio.gather(*(one(name) for name in chosen))
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for rank in range(max((len(b) for b in batches), default=0)):
            for batch in batches:
                if rank < len(batch) and batch[rank].primary_id not in seen:
                    seen.add(batch[rank].primary_id)
                    concepts.append(batch[rank])
        logger.info(
            f"ClinicalTables search for '{text}' returned {len(concepts[:limit])} concepts"
        )
        return concepts[:limit]

    async def _lookup_row(self, concept_id: str) -> tuple[_Table, dict[str, Any]] | None:
        resolved = self._resolve_id(concept_id)
        if resolved is None:
            logger.warning(f"ClinicalTables: unrecognised id '{concept_id}'")
            return None
        table, code = resolved
        rows = await self._query(
            table, {"terms": code, "sf": table.lookup_field, "maxList": _LOOKUP_PAGE}
        )
        for row in rows:  # prefix search: keep only the exact code
            if row["code"].upper() == code.upper():
                return table, row
        return None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Fetch one concept by ``<PREFIX>:<code>`` or a bare ICD-10-CM / LOINC / CUI code."""
        try:
            found = await self._lookup_row(concept_id)
            return self._to_concept(*found) if found else None
        except Exception as e:
            logger.error(f"ClinicalTables get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references carried by the row itself.

        ``conditions`` -> ICD-10-CM and ICD-9-CM codes plus MedlinePlus pages; ``hpo`` ->
        its ``xref`` ids (mostly empty); ``disease_names`` -> the UMLS CUI. Tables without
        cross-reference fields (``icd10cm``, ``loinc_items``, ``icd11_codes``) give ``[]``.
        """
        try:
            found = await self._lookup_row(concept_id)
        except Exception as e:
            logger.error(f"ClinicalTables get_mappings failed for '{concept_id}': {e}")
            return []
        if not found:
            return []
        table, row = found
        from_id = _concept_id(table, row["code"])
        extra = row["extra"]
        targets: list[tuple[str, str, str]] = []  # (toSource, toId, mappingType)
        if table.name == "conditions":
            for item in self._icd10cm_codes(extra):
                targets.append(("ICD10CM", item["code"], "suggested_code"))
            icd9 = self._icd9_pair(extra)
            if icd9:
                targets.append(("ICD9CM", icd9["code"], "suggested_code"))
            for link in self._info_links(extra):
                targets.append(("MEDLINEPLUS", link["url"], "info_link"))
        elif table.name == "hpo":
            for xref in extra.get("xref") or []:
                xid = xref.get("id") if isinstance(xref, dict) else xref
                if xid and ":" in str(xid):
                    targets.append((str(xid).split(":", 1)[0].upper(), str(xid), "xref"))
        elif table.name == "disease_names":
            targets.append(("UMLS", row["code"], "xref"))
        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for to_source, to_id, mapping_type in targets:
            if (to_source, to_id) in seen:
                continue
            seen.add((to_source, to_id))
            mappings.append(
                {
                    "fromId": from_id,
                    "toId": to_id,
                    "fromSource": "CLINICALTABLES",
                    "toSource": to_source,
                    "mappingType": mapping_type,
                    "confidence": 0.9,
                }
            )
        return mappings

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """HPO ``is_a`` parents (the only hierarchy the service exposes)."""
        try:
            found = await self._lookup_row(concept_id)
        except Exception as e:
            logger.error(f"ClinicalTables get_relationships failed for '{concept_id}': {e}")
            return []
        if not found or found[0].name != "hpo":
            return []
        out: list[dict[str, Any]] = []
        for parent in found[1]["extra"].get("is_a") or []:
            if isinstance(parent, dict) and parent.get("id"):
                out.append(
                    {
                        "relation_label": "is_a",
                        "related_id": str(parent["id"]),
                        "related_name": _clean(parent.get("name")),
                        "source": "CLINICALTABLES",
                    }
                )
        return out
