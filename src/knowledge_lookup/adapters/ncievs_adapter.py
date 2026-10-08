"""
NCI Thesaurus / NCI Metathesaurus adapter (NCI Enterprise Vocabulary Services REST API).

``https://api-evsrest.nci.nih.gov/api/v1`` is the keyless public API of the National Cancer
Institute's EVS. It serves NCI Thesaurus (``ncit``, codes like ``C3036`` for Fatigue), the
NCI Metathesaurus (``ncim``, UMLS-style CUIs like ``C0015672`` plus ``CL...`` local ids) and
about two dozen further terminologies (``snomedct_us``, ``icd10cm``, ``icd10``, ``lnc``
(LOINC), ``mdr`` (MedDRA), ``hgnc``, ``go``, ``chebi``, ...; list them with
``GET /metadata/terminologies``). The terminology defaults to ``ncit`` and is selectable per
call (``terminology=`` or a ``<TERMINOLOGY>:<code>`` id such as ``NCIM:C0015672``).

Response shapes learnt live (2026-10-08, NCIt 26.09d / NCIM 202608):

- ``concept/<t>/search?term=..&include=summary`` -> ``{"total", "concepts": [...]}`` with
  ``synonyms`` (``name``, ``termType``, ``source``, ``code``), ``definitions`` and
  ``properties`` (``Semantic_Type``, ``UMLS_CUI`` on NCIt; ``NCI_META_CUI`` on the others).
  ``include`` values the API accepts include ``minimal``, ``summary``, ``full``, ``parents``,
  ``children``, ``maps``, ``roles``, ``inverseRoles``, ``associations``,
  ``inverseAssociations``, ``synonyms``, ``properties``; anything else is a 400.
- NCIt ``maps`` are concept-to-code maps (``targetCode`` / ``targetTerminology``, mostly
  MedDRA and GDC). The NCI Metathesaurus ``maps`` are the SNOMED CT to ICD-10-CM/ICD-10
  rule maps of its constituent concepts (``sourceCode`` -> ``targetCode`` with ``rank`` and
  ``rule``). NCIM ``synonyms`` carry the per-source codes (MSH, SNOMEDCT_US, ICD10CM, LNC,
  OMIM, HPO, MEDLINEPLUS, ...), which is where the MeSH, SNOMED and ICD cross-references
  come from; NCIt itself exposes the UMLS CUI, so :meth:`get_mappings` follows an NCIt CUI
  into NCIM with one extra request.
- NCIM ``definitions`` include whole MedlinePlus pages as HTML; they are converted to text.

Usage terms: the API is open and keyless. Its terminology metadata (``/metadata/
terminologies``) carries licence texts for three of them: the NCI Metathesaurus "includes
various sources, some of which are proprietary and included, by permission, for
non-commercial use only", SNOMED CT is allowed inside EVS but "requires licensing for other
purposes", and MedDRA is licensed for NCI work only. The NCI Thesaurus entry has no licence
text there. Treat everything outside ``ncit`` as non-commercial / research use and check the
source licences before redistributing. EVS publishes no hard rate limit; requests are spaced
by 0.1 s and the relationship lists of very large NCIM concepts are capped (see
:data:`MAX_INVERSE`).
"""

import logging
import re
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._vocab_common import Spacer, html_to_text

logger = logging.getLogger(__name__)

BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"
DEFAULT_TERMINOLOGY = "ncit"
MAX_PAGE = 100  # page size cap for one search call
MAX_INVERSE = 100  # per inverseRoles / inverseAssociations list (Fatigue has 93)
_MIN_INTERVAL = 0.1
SEARCH_TYPES = ("contains", "match", "startsWith", "phrase", "AND", "OR", "fuzzy")

_TERMINOLOGY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
_NCIM_BARE_RE = re.compile(r"^(?:C\d{7}|CL\d+)$", re.IGNORECASE)
_NCIT_CODE_RE = re.compile(r"^C\d+$", re.IGNORECASE)
_TERMINOLOGY_ALIASES = {
    "nci": "ncit",
    "nci_thesaurus": "ncit",
    "ncimeta": "ncim",
    "snomedct": "snomedct_us",
    "snomed": "snomedct_us",
    "snomedct_us": "snomedct_us",
    "loinc": "lnc",
    "meddra": "mdr",
}

# NCIM synonym sources -> system name used in mappings.
_SYNONYM_SOURCES: dict[str, str] = {
    "MSH": "MESH",
    "SNOMEDCT_US": "SNOMEDCT",
    "ICD10CM": "ICD10CM",
    "ICD10": "ICD10",
    "MTHICD9": "ICD9CM",
    "LNC": "LOINC",
    "OMIM": "OMIM",
    "HPO": "HPO",
    "MEDLINEPLUS": "MEDLINEPLUS",
    "MDR": "MEDDRA",
    "RXNORM": "RXNORM",
    "NCI": "NCIT",
    "ORDO": "ORPHANET",
}
# Systems that are also KnowledgeSource members: those become ``identifiers`` on the concept.
_IDENTIFIER_SYSTEMS = {
    "UMLS",
    "MESH",
    "SNOMEDCT",
    "LOINC",
    "OMIM",
    "HPO",
    "MEDLINEPLUS",
    "RXNORM",
    "ORPHANET",
    "HGNC",
}
# NCIt property types that are identifiers in other databases -> system name.
_PROPERTY_XREFS = {
    "UMLS_CUI": "UMLS",
    "NCI_META_CUI": "UMLS",
    "OMIM_Number": "OMIM",
    "CAS_Registry": "CAS",
    "FDA_UNII_Code": "UNII",
    "EntrezGene_ID": "NCBIGENE",
    "CHEBI_ID": "CHEBI",
    "HGNC_ID": "HGNC",
    "Swiss_Prot": "UNIPROT",
    "NCBI_Taxon_ID": "NCBITAXON",
    "KEGG_ID": "KEGG",
    "ClinVar_Variation_ID": "CLINVAR",
}

_SEMANTIC_TYPES: dict[str, ConceptType] = {
    "Disease or Syndrome": ConceptType.DISEASE,
    "Neoplastic Process": ConceptType.DISEASE,
    "Mental or Behavioral Dysfunction": ConceptType.DISEASE,
    "Injury or Poisoning": ConceptType.DISEASE,
    "Pathologic Function": ConceptType.DISEASE,
    "Congenital Abnormality": ConceptType.DISEASE,
    "Acquired Abnormality": ConceptType.DISEASE,
    "Sign or Symptom": ConceptType.SYMPTOM,
    "Finding": ConceptType.OBSERVATION,
    "Laboratory or Test Result": ConceptType.OBSERVATION,
    "Clinical Attribute": ConceptType.OBSERVATION,
    "Gene or Genome": ConceptType.GENE,
    "Amino Acid, Peptide, or Protein": ConceptType.PROTEIN,
    "Enzyme": ConceptType.PROTEIN,
    "Receptor": ConceptType.PROTEIN,
    "Immunologic Factor": ConceptType.PROTEIN,
    "Pharmacologic Substance": ConceptType.DRUG,
    "Clinical Drug": ConceptType.DRUG,
    "Antibiotic": ConceptType.DRUG,
    "Organic Chemical": ConceptType.CHEMICAL,
    "Inorganic Chemical": ConceptType.CHEMICAL,
    "Element, Ion, or Isotope": ConceptType.CHEMICAL,
    "Biologically Active Substance": ConceptType.MOLECULAR_ENTITY,
    "Therapeutic or Preventive Procedure": ConceptType.PROCEDURE,
    "Diagnostic Procedure": ConceptType.PROCEDURE,
    "Laboratory Procedure": ConceptType.ASSAY,
    "Research Activity": ConceptType.STUDY,
    "Body Part, Organ, or Organ Component": ConceptType.ANATOMICAL_ENTITY,
    "Body Location or Region": ConceptType.ANATOMICAL_ENTITY,
    "Body System": ConceptType.ORGAN_SYSTEM,
    "Tissue": ConceptType.TISSUE,
    "Cell": ConceptType.CELL_TYPE,
    "Cell Component": ConceptType.CELLULAR_COMPONENT,
    "Cell Function": ConceptType.BIOLOGICAL_PROCESS,
    "Organ or Tissue Function": ConceptType.PHYSIOLOGICAL_PROCESS,
    "Molecular Function": ConceptType.MOLECULAR_FUNCTION,
    "Organism": ConceptType.ORGANISM,
    "Bacterium": ConceptType.ORGANISM,
    "Virus": ConceptType.ORGANISM,
    "Human": ConceptType.ORGANISM,
    "Population Group": ConceptType.DEMOGRAPHIC,
}
_NCIM_RELATION_TYPES = {
    "RO": "related_to",
    "RQ": "possibly_related_to",
    "RB": "broader_than",
    "RN": "narrower_than",
}


def _clean(text: Any) -> str:
    return " ".join(str(text).split()) if text is not None else ""


class NCIEVSAdapter(KnowledgeSourceAdapter):
    """NCI Thesaurus (``ncit``), NCI Metathesaurus (``ncim``) and other EVS terminologies."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = BASE_URL
        self.default_terminology = DEFAULT_TERMINOLOGY
        self._spacer = Spacer(_MIN_INTERVAL)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.NCIEVS

    def is_available(self) -> bool:
        return True  # public, keyless

    # ------------------------------------------------------------------
    # id handling
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_terminology(name: str | None) -> str | None:
        """``NCIT`` -> ``ncit``; ``SNOMEDCT`` -> ``snomedct_us``; ``None`` if malformed."""
        key = (name or "").strip().lower()
        key = _TERMINOLOGY_ALIASES.get(key, key)
        return key if _TERMINOLOGY_RE.match(key) else None

    def _parse_id(self, concept_id: str, terminology: str | None = None) -> tuple[str, str] | None:
        """Split an id into ``(terminology, code)``.

        ``NCIT:C3036``, ``ncim:C0015672`` and ``SNOMEDCT_US:52702003`` name the terminology;
        a bare ``C3036`` uses *terminology* (default ``ncit``), except that a bare CUI
        (``C0015672``) or local NCIM id (``CL...``) goes to ``ncim``.
        """
        raw = (concept_id or "").strip()
        if not raw:
            return None
        if ":" in raw:
            prefix, _, code = raw.partition(":")
            term = self.normalize_terminology(prefix)
            code = code.strip()
        else:
            code = raw
            if terminology:
                term = self.normalize_terminology(terminology)
            elif _NCIM_BARE_RE.match(raw):
                term = "ncim"
            else:
                term = self.default_terminology
        if term is None or not _CODE_RE.match(code):
            return None
        if term in ("ncit", "ncim") and re.match(r"^(?:C|CL)\d+$", code, re.IGNORECASE):
            code = code.upper()
        return term, code

    @staticmethod
    def _curie(terminology: str, code: str) -> str:
        return f"{terminology.upper()}:{code}"

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._spacer.wait()
        return await self._make_request(f"{self.base_url}/{path}", params)

    async def _fetch_concept(self, terminology: str, code: str, include: str) -> dict | None:
        """``concept/<t>/<code>?include=..``; ``None`` for 404, a non-object or an error."""
        try:
            path = f"concept/{terminology}/{quote(code, safe='')}"
            data = await self._get(path, {"include": include})
        except Exception as e:
            if getattr(e, "status", None) == 404:
                logger.info(f"EVS: {terminology}:{code} not found")
            else:
                logger.error(f"EVS fetch of {terminology}:{code} failed: {e}")
            return None
        return data if isinstance(data, dict) and data.get("code") else None

    # ------------------------------------------------------------------
    # unified model conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _properties(data: dict[str, Any], *types: str) -> list[str]:
        out: list[str] = []
        for prop in data.get("properties") or []:
            if isinstance(prop, dict) and prop.get("type") in types and prop.get("value"):
                value = _clean(prop["value"])
                if value not in out:
                    out.append(value)
        return out

    def _concept_type(self, semantic_types: list[str]) -> ConceptType:
        for sty in semantic_types:
            if sty in _SEMANTIC_TYPES:
                return _SEMANTIC_TYPES[sty]
        return ConceptType.UNKNOWN

    def _xref_pairs(self, data: dict[str, Any], terminology: str) -> list[tuple[str, str, str]]:
        """``(system, code, label)`` cross-references found in a concept payload.

        Sources: identifier-like properties (UMLS CUI, OMIM, CAS, UNII, ...), ``oboInOwl``
        xRefs, and - on NCIM - the code-bearing synonyms of whitelisted sources.
        """
        pairs: list[tuple[str, str, str]] = []
        for prop in data.get("properties") or []:
            if not isinstance(prop, dict) or not prop.get("value"):
                continue
            ptype, value = prop.get("type"), _clean(prop["value"])
            if ptype in _PROPERTY_XREFS:
                pairs.append((_PROPERTY_XREFS[ptype], value, ""))
            elif ptype == "xRef" and ":" in value:
                system, _, ident = value.partition(":")
                pairs.append((system.upper(), ident, ""))
        for syn in data.get("synonyms") or []:
            if not isinstance(syn, dict) or not syn.get("code"):
                continue
            source = str(syn.get("source") or "")
            if source not in _SYNONYM_SOURCES or source.lower() == terminology:
                continue
            if source == "NCI" and terminology == "ncit":
                continue
            if str(syn["code"]).startswith("MTHU"):
                continue  # Metathesaurus-generated placeholder, not a code of the source
            pairs.append((_SYNONYM_SOURCES[source], str(syn["code"]), _clean(syn.get("name"))))
        seen: set[tuple[str, str]] = set()
        unique: list[tuple[str, str, str]] = []
        for system, code, label in pairs:
            if (system, code) not in seen:
                seen.add((system, code))
                unique.append((system, code, label))
        return unique

    def _to_concept(self, data: dict[str, Any], terminology: str) -> UnifiedConcept | None:
        code, name = data.get("code"), _clean(data.get("name"))
        if not code or not name:
            return None
        concept = self._create_concept(self._curie(terminology, str(code)), name)

        seen = {name.lower()}
        synonyms: list[str] = []
        for syn in data.get("synonyms") or []:
            text = _clean(syn.get("name")) if isinstance(syn, dict) else ""
            if text and text.lower() not in seen:
                seen.add(text.lower())
                synonyms.append(text)
        concept.synonyms = synonyms

        defs = [d for d in data.get("definitions") or [] if isinstance(d, dict)]
        defs.sort(key=lambda d: d.get("type") != "DEFINITION")  # main definition first
        definitions: list[str] = []
        for d in defs:
            text = html_to_text(d.get("definition"))
            if text and text not in definitions:
                definitions.append(text)
        concept.definitions = definitions

        semantic_types = self._properties(data, "Semantic_Type")
        concept.semantic_types = semantic_types
        concept.concept_type = self._concept_type(semantic_types)
        concept.categories = [terminology]
        concept.parents = [
            self._curie(terminology, str(p["code"]))
            for p in data.get("parents") or []
            if isinstance(p, dict) and p.get("code")
        ]
        concept.children = [
            self._curie(terminology, str(c["code"]))
            for c in data.get("children") or []
            if isinstance(c, dict) and c.get("code")
        ]
        concept.confidence_score = 0.9 if data.get("active", True) else 0.3

        for system, ident, label in self._xref_pairs(data, terminology):
            if system in _IDENTIFIER_SYSTEMS:
                concept.add_identifier(system, ident, label or name)
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.NCIEVS] = {
                "terminology": terminology,
                "code": str(code),
                "version": data.get("version"),
                "active": data.get("active"),
                "leaf": data.get("leaf"),
                "concept_status": data.get("conceptStatus"),
            }
        return concept

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    async def search_concepts(
        self,
        query: str,
        limit: int = 20,
        *,
        terminology: str | None = None,
        search_type: str = "contains",
    ) -> list[UnifiedConcept]:
        """Search one terminology (default ``ncit``) by name/synonym.

        *search_type* is the EVS ``type`` parameter (``contains``, ``match``, ``startsWith``,
        ``phrase``, ``AND``, ``OR``, ``fuzzy``); ``contains`` is the EVS default.
        """
        text = (query or "").strip()
        term = self.normalize_terminology(terminology or self.default_terminology)
        if not text or limit < 1 or term is None:
            return []
        if search_type not in SEARCH_TYPES:
            search_type = "contains"
        params = {
            "term": text,
            "pageSize": min(limit, MAX_PAGE),
            "include": "summary",
            "type": search_type,
        }
        try:
            data = await self._get(f"concept/{term}/search", params)
        except Exception as e:
            logger.error(f"EVS search ({term}) failed for '{text}': {e}")
            return []
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for item in (data.get("concepts") if isinstance(data, dict) else None) or []:
            concept = self._to_concept(item, term) if isinstance(item, dict) else None
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concepts.append(concept)
        logger.info(f"EVS search ({term}) for '{text}' returned {len(concepts[:limit])} concepts")
        return concepts[:limit]

    async def get_concept_details(
        self, concept_id: str, *, terminology: str | None = None
    ) -> UnifiedConcept | None:
        """Fetch a concept with synonyms, definitions, semantic types, parents and children."""
        parsed = self._parse_id(concept_id, terminology)
        if parsed is None:
            logger.warning(f"EVS: unrecognised id '{concept_id}'")
            return None
        term, code = parsed
        data = await self._fetch_concept(term, code, "summary,parents,children")
        return self._to_concept(data, term) if data else None

    async def get_relationships(
        self, concept_id: str, *, terminology: str | None = None
    ) -> list[dict[str, Any]]:
        """Typed relationships of a concept.

        ``parents`` -> ``is_a`` (related = parent), ``children`` -> ``has_subclass``, NCIt
        ``roles`` / ``associations`` keep their EVS type as label (for example
        ``Disease_Has_Primary_Anatomic_Site``, ``Concept_In_Subset``) with
        ``direction="outgoing"``; ``inverseRoles`` / ``inverseAssociations`` have
        ``direction="incoming"`` and are capped at :data:`MAX_INVERSE` each. NCIM
        associations use their ``RELA`` qualifier as label (or ``related_to`` etc. from the
        ``RO``/``RQ``/``RB``/``RN`` relation type) and carry the asserting ``source``.
        """
        parsed = self._parse_id(concept_id, terminology)
        if parsed is None:
            return []
        term, code = parsed
        data = await self._fetch_concept(
            term,
            code,
            "parents,children,roles,inverseRoles,associations,inverseAssociations",
        )
        if not data:
            return []
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        def add(label: str, related: dict[str, Any], direction: str, **extra: Any) -> None:
            rid = related.get("relatedCode") or related.get("code")
            if not rid:
                return
            related_id = self._curie(term, str(rid))
            key = (label, related_id, direction)
            if key in seen:
                return
            seen.add(key)
            entry: dict[str, Any] = {
                "relation_label": label,
                "related_id": related_id,
                "related_name": _clean(related.get("relatedName") or related.get("name")),
                "source": "NCIEVS",
                "direction": direction,
            }
            entry.update({k: v for k, v in extra.items() if v})
            out.append(entry)

        for parent in data.get("parents") or []:
            add("is_a", parent, "outgoing", asserted_by=parent.get("source"))
        for child in data.get("children") or []:
            add("has_subclass", child, "incoming", asserted_by=child.get("source"))
        for key, direction in (
            ("roles", "outgoing"),
            ("associations", "outgoing"),
            ("inverseRoles", "incoming"),
            ("inverseAssociations", "incoming"),
        ):
            items = [i for i in data.get(key) or [] if isinstance(i, dict)]
            if direction == "incoming":
                items = items[:MAX_INVERSE]
            for item in items:
                add(self._relation_label(item), item, direction, asserted_by=item.get("source"))
        return out

    @staticmethod
    def _relation_label(item: dict[str, Any]) -> str:
        """EVS role/association type, or the NCIM ``RELA`` qualifier / ``RO`` code."""
        if item.get("type") not in _NCIM_RELATION_TYPES:
            return str(item.get("type") or "related_to")
        for qualifier in item.get("qualifiers") or []:
            if isinstance(qualifier, dict) and qualifier.get("type") == "RELA":
                return str(qualifier.get("value") or "related_to")
        return _NCIM_RELATION_TYPES[item["type"]]

    async def get_mappings(
        self, concept_id: str, *, terminology: str | None = None
    ) -> list[dict[str, Any]]:
        """Cross-references and maps of a concept.

        Combines (a) the concept's ``maps``, (b) identifier properties (UMLS CUI, OMIM, CAS,
        UNII, xRefs, ...) and (c) code-bearing synonyms (NCIM: MeSH, SNOMED CT, ICD-10-CM,
        LOINC, OMIM, HPO, MedlinePlus, MedDRA, ...). For an NCIt concept with a UMLS CUI the
        NCIM concept is read as well (one extra request) so that the SNOMED/ICD/MeSH codes
        that NCIt itself does not carry are returned, marked with ``via``.
        """
        parsed = self._parse_id(concept_id, terminology)
        if parsed is None:
            return []
        term, code = parsed
        data = await self._fetch_concept(term, code, "synonyms,maps,properties")
        if not data:
            return []
        from_id = self._curie(term, code)
        mappings = self._mappings_from(data, term, from_id)
        cuis = self._properties(data, "UMLS_CUI") if term == "ncit" else []
        if cuis:
            via = self._curie("ncim", cuis[0])
            ncim = await self._fetch_concept("ncim", cuis[0], "synonyms,maps")
            if ncim:
                mappings += self._mappings_from(ncim, "ncim", from_id, via=via)
        seen: set[tuple[str, str, str]] = set()
        unique: list[dict[str, Any]] = []
        for m in mappings:
            key = (m["fromId"], m["toSource"], m["toId"])
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    def _mappings_from(
        self, data: dict[str, Any], terminology: str, from_id: str, via: str | None = None
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        def add(to_source: str, to_id: str, mapping_type: str, confidence: float, **extra: Any):
            entry = {
                "fromId": extra.pop("from_id", from_id),
                "toId": to_id,
                "fromSource": extra.pop("from_source", "NCIEVS"),
                "toSource": to_source,
                "mappingType": mapping_type,
                "confidence": confidence,
            }
            if via:
                entry["via"] = via
            entry.update({k: v for k, v in extra.items() if v})
            out.append(entry)

        for system, ident, label in self._xref_pairs(data, terminology):
            if via is not None and system in ("UMLS", "NCIT"):
                continue  # the CUI / NCIt code is the bridge, already reported by the record
            add(system, ident, "xref", 0.9, target_name=label)
        for m in data.get("maps") or []:
            if not isinstance(m, dict) or not m.get("targetCode"):
                continue
            target = str(m.get("targetTerminology") or m.get("target") or "").upper()
            if "sourceCode" in m:  # NCIM: rule map between constituent source codes
                add(
                    target,
                    str(m["targetCode"]),
                    str(m.get("type") or "map"),
                    0.8 if str(m.get("rank")) == "1" else 0.6,
                    from_id=f"{str(m.get('sourceTerminology') or '').upper()}:{m.get('sourceCode')}",
                    from_source=str(m.get("sourceTerminology") or "").upper(),
                    target_name=_clean(m.get("targetName")),
                    rank=m.get("rank"),
                    rule=m.get("rule"),
                    mapset=m.get("mapsetCode"),
                )
            else:  # NCIt: concept -> code in another terminology
                synonym = m.get("type") == "Has Synonym"
                add(
                    target,
                    str(m["targetCode"]),
                    str(m.get("type") or "map"),
                    0.9 if synonym else 0.6,
                    target_name=_clean(m.get("targetName")),
                    target_version=m.get("targetTerminologyVersion"),
                )
        return out
