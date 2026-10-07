"""
NCBI MedGen adapter.

MedGen is NCBI's portal for medical genetics concepts: conditions, phenotypes and findings
organised around UMLS concept unique identifiers (CUIs such as ``C0015674`` for
myalgic encephalomyelitis / chronic fatigue syndrome). Its main value for this library is
**ID linking**: one MedGen concept lists the MeSH, OMIM, Orphanet, MONDO, HPO, SNOMED CT, NCI
Thesaurus, GTR and GeneReviews identifiers that denote the same condition.

Served by the NCBI E-utilities (``db=medgen``), verified live 2026-10:

* ``esearch`` (``sort=relevance``; the default sort is by recency and returns newly added
  obscure concepts first) returns MedGen UIDs. A bare CUI is a valid query term.
* ``esummary`` (``retmode=json``) returns, per UID, ``conceptid`` (the CUI, or a MedGen ``CN``
  id for concepts without a UMLS CUI), ``title``, ``definition``, ``semanticid`` (UMLS TUI)
  and ``conceptmeta``: **a string holding an XML fragment** (several root elements) with
  ``Names`` (every synonym with its source vocabulary ``SAB`` and code), ``Definitions``,
  ``OMIM``, ``ClinicalFeatures`` (HPO terms), ``ModesOfInheritance``, ``RelatedDisorders``,
  ``PharmacologicResponse``, ``AssociatedGenes`` (NCBI Gene id + symbol) and more.
  It is parsed with ``xml.etree``. Rich concepts are big (30 - 170 KB per concept).
* ``efetch`` only returns the id list for ``db=medgen`` (``rettype=full`` is rejected) and is
  not used. ``elink`` only exposes counts-style links to ClinVar, Gene, GTR, PubMed ...; the
  concept record already carries genes and clinical features with names, so one ``esummary``
  call answers details, mappings and relationships.
* ICD codes are not part of the concept record (``SAB`` values seen: MSH, OMIM, SNOMEDCT_US,
  NCI, HPO, MONDO, ORDO, GTR, GENEREVIEWS); unknown vocabularies would be passed through under
  their own ``SAB`` name, so ICD codes would appear if NCBI starts exporting them.
* MedGen has no usable hierarchy through E-utilities: ``parents``/``children`` stay empty.

Rate limit: 3 requests/s without a key, 10/s with one (``NCBI_API_KEY`` or ``ncbi`` in the
config's ``api_keys``); requests are spaced accordingly. An optional contact address
(``NCBI_EMAIL`` / ``ncbi_email``) is sent only if configured. MedGen data are US-government
work in the public domain; NCBI asks users to cite it.
"""

import asyncio
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MEDGEN_DB = "medgen"
TOOL_NAME = "knowledge-lookup"

_CUI_RE = re.compile(r"^(C\d{7}|CN\d{4,})$", re.IGNORECASE)
_UID_RE = re.compile(r"^\d{1,12}$")
_PREFIX_RE = re.compile(r"^(?:umls_cui|umls|medgen|cui)\s*[:_]\s*", re.IGNORECASE)

# esummary of rich concepts is large; keep search pages modest.
_MAX_SEARCH = 50
_MAX_SYNONYMS = 50
_MIN_INTERVAL_KEYLESS = 0.34  # 3 requests/s
_MIN_INTERVAL_KEYED = 0.11  # 10 requests/s

# UMLS semantic type id (TUI) -> ConceptType; anything else is treated as a disease concept.
_SYMPTOM_TUIS = {"T184"}
_PHENOTYPE_TUIS = {"T033", "T019", "T020", "T190", "T017", "T029", "T031", "T080"}

# Source vocabulary (``SAB``) -> prefix used in mapping CURIEs.
_SAB_PREFIX = {
    "MSH": "MESH",
    "OMIM": "OMIM",
    "SNOMEDCT_US": "SNOMEDCT_US",
    "NCI": "NCIT",
    "HPO": "HP",
    "MONDO": "MONDO",
    "ORDO": "Orphanet",
    "GTR": "GTR",
    "GENEREVIEWS": "GeneReviews",
}
# ``SAB`` values whose preferred code is the source-concept id rather than the descriptor id
_SCUI_FIRST = {"SNOMEDCT_US", "NCI"}


class MedGenAdapter(KnowledgeSourceAdapter):
    """Adapter for NCBI MedGen (conditions and phenotypes keyed by UMLS CUI)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = EUTILS_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.MEDGEN

    def is_available(self) -> bool:
        return True  # E-utilities are public; a key only raises the rate limit

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _api_key(self) -> str | None:
        return self.config.get_api_key("ncbi") or os.getenv("NCBI_API_KEY") or None

    async def _eutils(self, endpoint: str, params: dict[str, Any]) -> Any:
        """GET ``{endpoint}.fcgi`` on E-utilities, spacing calls to NCBI's rate limit."""
        api_key = self._api_key()
        interval = _MIN_INTERVAL_KEYED if api_key else _MIN_INTERVAL_KEYLESS
        query = {"db": MEDGEN_DB, "retmode": "json", "tool": TOOL_NAME, **params}
        if api_key:
            query["api_key"] = api_key
        email = self.config.get_api_key("ncbi_email") or os.getenv("NCBI_EMAIL")
        if email:
            query["email"] = email
        async with self._throttle_lock:
            wait = interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        return await self._make_request(f"{self.base_url}/{endpoint}.fcgi", query)

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("cui", "C0015674")`` or ``("uid", "5130")``.

        Accepts ``C0015674``, ``UMLS:C0015674``, ``MedGen:C0015674``, ``CUI:C0015674`` and
        MedGen UIDs (``5130``, ``MedGen:5130``). Returns ``None`` for anything else.
        """
        text = _PREFIX_RE.sub("", (concept_id or "").strip())
        if _CUI_RE.match(text):
            return "cui", text.upper()
        if _UID_RE.match(text):
            return "uid", text
        return None

    async def _summaries(self, uids: list[str]) -> list[dict[str, Any]]:
        """esummary documents for ``uids`` (error documents are dropped)."""
        if not uids:
            return []
        data = await self._eutils("esummary", {"id": ",".join(uids)})
        result = (data or {}).get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            return []
        docs = []
        for uid in result.get("uids") or []:
            doc = result.get(uid)
            if isinstance(doc, dict) and not doc.get("error") and doc.get("title"):
                docs.append(doc)
        return docs

    async def _search_uids(self, term: str, retmax: int) -> list[str]:
        data = await self._eutils("esearch", {"term": term, "retmax": retmax, "sort": "relevance"})
        result = (data or {}).get("esearchresult") if isinstance(data, dict) else None
        return [str(u) for u in (result or {}).get("idlist") or []]

    async def _fetch_summary(self, concept_id: str) -> dict[str, Any] | None:
        """The esummary document for a CUI or MedGen UID, or ``None``."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        kind, value = parsed
        if kind == "uid":
            docs = await self._summaries([value])
            return docs[0] if docs else None
        # A CUI is a plain search term; confirm the hit really has this CUI.
        uids = await self._search_uids(value, 5)
        for doc in await self._summaries(uids):
            if str(doc.get("conceptid", "")).upper() == value:
                return doc
        return None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search MedGen (all fields, relevance order); CUIs and UIDs go straight to details."""
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            if self._parse_id(text) is not None:
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            size = min(limit, _MAX_SEARCH)
            docs = await self._summaries(await self._search_uids(text, size))
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank, doc in enumerate(docs):
                concept = self._doc_to_concept(doc)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concept.confidence_score = max(0.5, 0.95 - 0.02 * rank)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"MedGen search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"MedGen search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full MedGen concept: definition, synonyms, semantic type, genes, vocabularies."""
        try:
            doc = await self._fetch_summary(concept_id)
            if doc is None:
                return None
            concept = self._doc_to_concept(doc)
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"MedGen get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Mappings / relationships
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references to MeSH, OMIM, Orphanet, MONDO, HPO, SNOMED CT, NCIT, GTR ...

        Each item also carries ``label`` (the vocabulary's preferred name for the target) and
        ``source_vocabulary`` (the MedGen ``SAB``). These are UMLS-style synonym clusters,
        i.e. "same concept", but the vocabularies disagree on granularity (a SNOMED CT code
        for the broader or narrower term may be listed), so ``confidence`` is 0.9.
        """
        try:
            doc = await self._fetch_summary(concept_id)
        except Exception as e:
            logger.error(f"MedGen get_mappings failed for '{concept_id}': {e}")
            return []
        if doc is None:
            return []
        from_id = str(doc.get("conceptid") or doc.get("uid"))
        mappings: list[dict[str, Any]] = []
        for prefix, code, sab, label in self._iter_xrefs(self._parse_meta(doc)):
            mappings.append(
                {
                    "fromId": from_id,
                    "toId": f"{prefix}:{code}",
                    "fromSource": "MEDGEN",
                    "toSource": prefix,
                    "mappingType": "xref",
                    "confidence": 0.9,
                    "label": label,
                    "source_vocabulary": sab,
                }
            )
        return mappings

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Gene, clinical-feature, inheritance and related-disorder links of a concept.

        ``relation_label`` values: ``has_associated_gene`` (``NCBIGene:<id>`` + symbol, with
        ``chromosome``/``cytogenetic_location``), ``has_clinical_feature`` (HPO id where
        MedGen has one, else the feature's CUI; ``cui``, ``semantic_type``),
        ``has_mode_of_inheritance``, ``related_disorder`` and ``has_pharmacologic_response``
        (drug concepts of a "... response" finding). Ordered in that sequence and capped by
        ``limit`` (a diabetes concept lists hundreds of clinical features).
        """
        if limit <= 0:
            return []
        try:
            doc = await self._fetch_summary(concept_id)
        except Exception as e:
            logger.error(f"MedGen get_relationships failed for '{concept_id}': {e}")
            return []
        if doc is None:
            return []
        meta = self._parse_meta(doc)
        relationships: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(label: str, related_id: str, name: str, **extra: Any) -> None:
            if not related_id or (label, related_id) in seen:
                return
            seen.add((label, related_id))
            relationships.append(
                {
                    "relation_label": label,
                    "related_id": related_id,
                    "related_name": name,
                    "source": "MEDGEN",
                    **{k: v for k, v in extra.items() if v},
                }
            )

        for gene in self._children(meta, "AssociatedGenes", "Gene"):
            gene_id = gene.get("gene_id")
            add(
                "has_associated_gene",
                f"NCBIGene:{gene_id}" if gene_id else "",
                (gene.text or "").strip(),
                chromosome=gene.get("chromosome"),
                cytogenetic_location=gene.get("cytogen_loc"),
            )
        for section, element, label in (
            ("ClinicalFeatures", "ClinicalFeature", "has_clinical_feature"),
            ("ModesOfInheritance", "ModeOfInheritance", "has_mode_of_inheritance"),
            ("RelatedDisorders", "RelatedDisorder", "related_disorder"),
            ("PharmacologicResponse", "Drug", "has_pharmacologic_response"),
        ):
            for node in self._children(meta, section, element):
                add(
                    label,
                    node.get("SDUI") or node.get("CUI") or "",
                    (node.findtext("Name") or "").strip(),
                    cui=node.get("CUI"),
                    semantic_type=(node.findtext("SemanticType") or "").strip(),
                    medgen_uid=node.get("uid"),
                )
        return relationships[:limit]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_meta(doc: dict[str, Any]) -> ET.Element | None:
        """Parse the ``conceptmeta`` XML fragment (several roots) under a synthetic root."""
        raw = doc.get("conceptmeta")
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            return ET.fromstring(f"<meta>{raw}</meta>")
        except ET.ParseError as e:
            logger.warning(f"MedGen conceptmeta of {doc.get('uid')} is not valid XML: {e}")
            return None

    @staticmethod
    def _children(meta: ET.Element | None, section: str, element: str) -> list[ET.Element]:
        if meta is None:
            return []
        node = meta.find(section)
        return [] if node is None else node.findall(element)

    @classmethod
    def _iter_xrefs(cls, meta: ET.Element | None) -> list[tuple[str, str, str, str]]:
        """Unique ``(CURIE prefix, code, SAB, label)`` from ``Names`` and the ``OMIM`` list."""
        if meta is None:
            return []
        found: dict[tuple[str, str], tuple[str, str, str, str]] = {}
        names = meta.find("Names")
        for name in [] if names is None else names.findall("Name"):
            sab = name.get("SAB") or ""
            code = cls._code_for(sab, name)
            if not sab or not code:
                continue
            prefix = _SAB_PREFIX.get(sab, sab)
            code = code.removeprefix(f"{prefix}:")  # MONDO/HPO ids already carry their prefix
            label = (name.text or "").strip()
            key = (prefix, code)
            # keep the first label, but prefer a preferred term (PT/MH) when one shows up
            if key not in found or (name.get("TTY") in {"PT", "MH"} and label):
                found[key] = (prefix, code, sab, label)
        for mim in cls._children(meta, "OMIM", "MIM"):
            code = (mim.text or "").strip()
            if code.isdigit() and ("OMIM", code) not in found:
                found[("OMIM", code)] = ("OMIM", code, "OMIM", "")
        return list(found.values())

    @staticmethod
    def _code_for(sab: str, name: ET.Element) -> str:
        """The identifier a vocabulary entry denotes (descriptor id, or source concept id)."""
        sdui, scui, code = name.get("SDUI"), name.get("SCUI"), name.get("CODE")
        if sab in _SCUI_FIRST:
            value = scui or code or sdui
        else:
            value = sdui or code or scui
        value = (value or "").strip()
        if sab == "ORDO":
            value = value.removeprefix("Orphanet_")
        elif sab == "OMIM" and not value.isdigit():
            return ""  # e.g. UMLS-internal ``MTHU...`` ids filed under OMIM
        elif sab == "MSH" and not value:
            return ""
        return value

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _doc_to_concept(self, doc: dict[str, Any]) -> UnifiedConcept | None:
        cui, label, uid = doc.get("conceptid"), doc.get("title"), doc.get("uid")
        if not label or not (cui or uid):
            return None
        tui = str(doc.get("semanticid") or "")
        concept = self._create_concept(str(cui or uid), str(label), self._concept_type(tui))
        if uid:
            concept.add_identifier(
                self.get_source(),
                f"MedGen:{uid}",
                str(label),
                f"https://www.ncbi.nlm.nih.gov/medgen/{uid}",
            )

        semantic = (doc.get("semantictype") or {}).get("value")
        if semantic and concept.semantic_types is not None:
            concept.semantic_types.append(str(semantic))
        self._add_unique(concept.definitions, (doc.get("definition") or {}).get("value"))

        meta = self._parse_meta(doc)
        definition_sources: list[str] = []
        for node in self._children(meta, "Definitions", "Definition"):
            self._add_unique(concept.definitions, (node.text or "").strip())
            if node.get("source"):
                definition_sources.append(node.get("source", ""))
        names = None if meta is None else meta.find("Names")
        vocabularies: list[str] = []
        label_key = str(label).casefold()
        for name in [] if names is None else names.findall("Name"):
            sab = name.get("SAB")
            if sab and sab not in vocabularies:
                vocabularies.append(sab)
            text = (name.text or "").strip()
            if (
                text
                and text.casefold() != label_key
                and concept.synonyms is not None
                and len(concept.synonyms) < _MAX_SYNONYMS
                and text.casefold() not in {s.casefold() for s in concept.synonyms}
            ):
                concept.synonyms.append(text)

        genes = [
            {"gene_id": g.get("gene_id"), "symbol": (g.text or "").strip()}
            for g in self._children(meta, "AssociatedGenes", "Gene")
        ]
        omim = [(m.text or "").strip() for m in self._children(meta, "OMIM", "MIM")]
        if doc.get("suppressed") and concept.categories is not None:
            concept.categories.append("suppressed")
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "uid": uid,
                "conceptid": cui,
                "semantic_type": semantic,
                "semantic_type_id": tui or None,
                "definition_sources": definition_sources,
                "source_vocabularies": vocabularies,
                "omim": [m for m in omim if m],
                "associated_genes": genes,
                "suppressed": doc.get("suppressed") or None,
                "merged": doc.get("merged") or None,
            }
        return concept

    @staticmethod
    def _concept_type(tui: str) -> ConceptType:
        if tui in _SYMPTOM_TUIS:
            return ConceptType.SYMPTOM
        if tui in _PHENOTYPE_TUIS:
            return ConceptType.PHENOTYPE
        return ConceptType.DISEASE

    @staticmethod
    def _add_unique(target: list[str] | None, value: Any) -> None:
        if target is None or not isinstance(value, str):
            return
        value = value.strip().replace("''", "'")
        if value and value not in target:
            target.append(value)
