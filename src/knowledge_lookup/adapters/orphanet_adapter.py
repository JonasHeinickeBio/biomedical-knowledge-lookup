"""
Orphanet Knowledge Source Adapter

Orphanet rare-disease nosology (ORPHAcodes): names, synonyms, definitions, disease-gene
associations, HPO phenotype annotations with frequency, prevalence, natural history,
the Orphanet classification hierarchies and cross-references (OMIM, ICD-10, ICD-11, MONDO,
MeSH, UMLS, MedDRA, GARD).

Which API: the official ORPHAcode API (``api.orphacode.org``) answers 401 without a
registration token, so this adapter uses the keyless **Orphadata API**
(``https://api.orphadata.com``, OpenAPI spec at ``/openapi.json``), which serves the same
Orphadata products (nomenclature/cross-references, genes, phenotypes, epidemiology, natural
history, classifications) as JSON. Data are released twice a year (July and December).

Quirks learned live:

* ``/rd-cross-referencing/orphacodes/names/{name}`` returns only the single best fuzzy match
  (never a list), so multi-hit search is done against the list of all 11.6k disorders
  (``/rd-cross-referencing/orphacodes``, ~200 kB gzip, fetched once per adapter instance).
* A disease without data in a product answers HTTP 404 (e.g. genes for ORPHA:558, whose genes
  are attached to its subtypes); this is "no data", not an error.
* Parent/child ORPHAcodes of the classification are bare numbers; labels are resolved from
  the cross-referencing list and, for category nodes missing there, from the classification
  list (``/rd-classification/orphacodes``, ~480 kB gzip, loaded lazily).
* Non-rare or retired entities keep a prefix in their term (``NON RARE IN EUROPE: Chronic
  fatigue syndrome`` is ORPHA:1983); the label is kept verbatim.

Licence: Orphadata is CC BY 4.0, credit "Orphanet" and the release date.
"""

import asyncio
import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._pheno_common import add_known_identifier, frequency_extras, parse_frequency

logger = logging.getLogger(__name__)

ORPHADATA_API = "https://api.orphadata.com"
XREF_PATH = "/rd-cross-referencing/orphacodes"
GENES_PATH = "/rd-associated-genes/orphacodes"
PHENO_PATH = "/rd-phenotypes/orphacodes"
EPI_PATH = "/rd-epidemiology/orphacodes"
HISTORY_PATH = "/rd-natural_history/orphacodes"
CLASS_PATH = "/rd-classification/orphacodes"
ORPHA_URL = "https://www.orpha.net/en/disease/detail/{code}"

_ID_RE = re.compile(
    r"^(?:https?://www\.orpha\.net/ORDO/)?(?:orpha(?:net|code)?[_:\s]*)?(\d+)$", re.IGNORECASE
)

# Orphanet frequency phrases -> HPO frequency term (see _pheno_common.FREQUENCY_TERMS)
_FREQUENCY_TERMS = {
    "obligate": "HP:0040280",
    "very frequent": "HP:0040281",
    "frequent": "HP:0040282",
    "occasional": "HP:0040283",
    "very rare": "HP:0040284",
    "excluded": "HP:0040285",
}

# ExternalReference "Source" -> CURIE prefix used in get_mappings
_MAPPING_PREFIXES = {
    "ICD-10": "ICD10",
    "ICD-11": "ICD11",
    "MONDO": "MONDO",
    "MeSH": "MESH",
    "MedDRA": "MEDDRA",
    "OMIM": "OMIM",
    "UMLS": "UMLS",
    "GARD": "GARD",
}

# Orphanet relation code (first token of DisorderMappingRelation) -> (SKOS type, confidence)
# The code is read from ORPHAcode's perspective: BTNT = ORPHAcode broader than the target.
_MAPPING_RELATIONS = {
    "E": ("exactMatch", 1.0),
    "BTNT": ("narrowMatch", 0.8),
    "NTBT": ("broadMatch", 0.8),
    "BTNT/E": ("narrowMatch", 0.8),
    "NTBT/E": ("broadMatch", 0.8),
    "ND": ("relatedMatch", 0.5),
}


def normalize_orphacode(concept_id: str) -> str | None:
    """``ORPHA:558`` / ``Orphanet_558`` / ``orphanet:558`` / ``ORPHAcode 558`` / ``558`` -> ``"558"``."""
    match = _ID_RE.match((concept_id or "").strip())
    return str(int(match.group(1))) if match else None


def _frequency_for(text: str | None) -> dict[str, Any]:
    """Relationship keys for an Orphanet frequency phrase such as ``Very frequent (99-80%)``."""
    if not text:
        return {}
    head = text.split("(")[0].strip().lower()
    term = _FREQUENCY_TERMS.get(head)
    extras = frequency_extras(parse_frequency(term)) if term else {}
    extras["frequency_raw"] = text
    return extras


def _pmids(source: str | None) -> list[str]:
    """``30726024[PMID]_30573797[PMID]`` -> ``["30726024", "30573797"]``."""
    return re.findall(r"(\d+)\[PMID\]", source or "")


def _results(payload: Any) -> list[dict[str, Any]]:
    """Orphadata puts one hit in ``data.results`` as an object and several as a list."""
    results = (payload or {}).get("data", {}).get("results") if isinstance(payload, dict) else None
    if isinstance(results, dict):
        return [results]
    return [r for r in results or [] if isinstance(r, dict)]


class OrphanetAdapter(KnowledgeSourceAdapter):
    """Adapter for Orphanet via the keyless Orphadata API."""

    #: Orphadata answers in 0.2-1.5 s; the two list endpoints are the slowest.
    min_request_timeout = 30.0

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = ORPHADATA_API
        self.lang = "en"
        self._names: dict[str, str] | None = None
        self._class_names: dict[str, str] | None = None
        self._lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ORPHANET

    def is_available(self) -> bool:
        return True  # Orphadata API is keyless

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, lang: bool = True) -> Any | None:
        """GET an Orphadata path; ``None`` for 404 ("no data") and for any failure."""
        try:
            params = {"lang": self.lang} if lang else None
            return await self._make_request(f"{self.base_url}{path}", params=params)
        except Exception as e:
            if getattr(e, "status", None) == 404:
                logger.debug(f"Orphanet: no data at {path}")
            else:
                logger.warning(f"Orphanet request {path} failed: {e}")
            return None

    async def _ensure_names(self) -> dict[str, str]:
        """ORPHAcode -> preferred term for all disorders (loaded once)."""
        if self._names is not None:
            return self._names
        async with self._lock:
            if self._names is None:
                payload = await self._get(XREF_PATH)
                names = {
                    str(r["ORPHAcode"]): str(r.get("Preferred term") or "")
                    for r in _results(payload)
                    if r.get("ORPHAcode") is not None
                }
                if not names:
                    return {}  # failed load: do not cache, retry on the next call
                self._names = names
        return self._names

    async def _label_for(self, codes: set[str]) -> dict[str, str]:
        """Labels for ORPHAcodes (cross-referencing list first, classification list second)."""
        names = await self._ensure_names()
        found = {c: names[c] for c in codes if c in names}
        missing = codes - set(found)
        if missing:
            async with self._lock:
                if self._class_names is None:
                    payload = await self._get(CLASS_PATH, lang=False)
                    loaded = {
                        str(r["ORPHAcode"]): str(r.get("preferredTerm") or "")
                        for r in _results(payload)
                        if r.get("ORPHAcode") is not None
                    }
                    if loaded:
                        self._class_names = loaded
            found.update({c: (self._class_names or {}).get(c, "") for c in missing})
        return found

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _concept_from_name(self, code: str, name: str, score: float) -> UnifiedConcept:
        concept = self._create_concept(f"ORPHA:{code}", name, ConceptType.DISEASE)
        concept.confidence_score = score
        return concept

    def _convert_record(self, record: dict[str, Any], score: float = 1.0) -> UnifiedConcept:
        """Build a concept from a cross-referencing record."""
        code = str(record.get("ORPHAcode"))
        concept = self._create_concept(
            f"ORPHA:{code}", str(record.get("Preferred term") or code), ConceptType.DISEASE
        )
        concept.confidence_score = score
        concept.synonyms = [str(s) for s in record.get("Synonym") or []]
        concept.definitions = [
            str(s["Definition"])
            for s in record.get("SummaryInformation") or []
            if s.get("Definition")
        ]
        flags = [
            str(f["Label"]).lower() for f in record.get("DisorderFlag") or [] if f.get("Label")
        ]
        typology = record.get("Typology")
        group = record.get("DisorderGroup")
        concept.categories = [str(x) for x in (typology, group) if x] + flags
        concept.semantic_types = [str(typology)] if typology else []
        for ref in record.get("ExternalReference") or []:
            curie = self._curie(ref)
            if curie:
                add_known_identifier(concept, curie)
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.ORPHANET] = {
                "orphacode": record.get("ORPHAcode"),
                "typology": typology,
                "disorder_group": group,
                "flags": flags,
                "url": ORPHA_URL.format(code=code),
                "release_date": record.get("Date"),
            }
        return concept

    @staticmethod
    def _curie(ref: dict[str, Any]) -> str | None:
        prefix = _MAPPING_PREFIXES.get(str(ref.get("Source")))
        value = str(ref.get("Reference") or "").strip()
        return f"{prefix}:{value}" if prefix and value else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Find disorders by name (all words must occur, any order) or ORPHAcode.

        Ranking: exact name 1.0, prefix 0.9, whole-phrase substring 0.8, words anywhere 0.7;
        Orphadata's own best fuzzy match is added (0.85) when the list scan did not find it.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            code = normalize_orphacode(text)
            if code:
                concept = await self.get_concept_details(code)
                return [concept] if concept else []

            names = await self._ensure_names()
            needle = text.lower()
            words = needle.split()
            scored: list[tuple[float, str, str]] = []
            for c, name in names.items():
                lowered = name.lower()
                if lowered == needle:
                    score = 1.0
                elif lowered.startswith(needle):
                    score = 0.9
                elif needle in lowered:
                    score = 0.8
                elif all(w in lowered for w in words):
                    score = 0.7
                else:
                    continue
                scored.append((score, name, c))
            scored.sort(key=lambda s: (-s[0], len(s[1]), int(s[2])))
            concepts = [self._concept_from_name(c, n, s) for s, n, c in scored[:limit]]

            if len(concepts) < limit:
                payload = await self._get(f"{XREF_PATH}/names/{text}")
                for record in _results(payload):
                    best = self._convert_record(record, 0.85)
                    if all(c.primary_id != best.primary_id for c in concepts):
                        concepts.append(best)
            logger.info(f"Orphanet search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"Orphanet search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full record: definition, synonyms, typology, cross-reference identifiers,
        parents/children, plus prevalence and natural history in ``source_data``."""
        try:
            code = normalize_orphacode(concept_id)
            if code is None:
                return None
            record_payload, epi_payload, history_payload, class_payload = await asyncio.gather(
                self._get(f"{XREF_PATH}/{code}"),
                self._get(f"{EPI_PATH}/{code}"),
                self._get(f"{HISTORY_PATH}/{code}"),
                self._get(f"{CLASS_PATH}/{code}/hchids", lang=False),
            )
            records = _results(record_payload)
            if not records:
                return None
            concept = self._convert_record(records[0])
            parents, children = self._hierarchy(_results(class_payload))
            concept.parents = [f"ORPHA:{c}" for c in parents]
            concept.children = [f"ORPHA:{c}" for c in children]
            extra: dict[str, Any] = {}
            for epi in _results(epi_payload):
                extra["prevalence"] = epi.get("Prevalence") or []
            for hist in _results(history_payload):
                extra["average_age_of_onset"] = hist.get("AverageAgeOfOnset") or []
                extra["average_age_of_death"] = hist.get("AverageAgeOfDeath") or []
                extra["type_of_inheritance"] = hist.get("TypeOfInheritance") or []
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.ORPHANET].update(extra)
            return concept
        except Exception as e:
            logger.error(f"Orphanet get_concept_details failed for '{concept_id}': {e}")
            return None

    @staticmethod
    def _hierarchy(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        """Union of parents and children over all classifications, order preserved."""
        parents: dict[str, None] = {}
        children: dict[str, None] = {}
        for row in rows:
            parents.update((str(p), None) for p in row.get("parents") or [])
            children.update((str(c), None) for c in row.get("childs") or [])
        return list(parents), list(children)

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Disease -> genes, phenotypes and classification neighbours.

        ``limit`` applies to each kind separately.

        - ``associated_with`` -> ``HGNC:n`` gene, with ``association_type`` (e.g.
          "Disease-causing germline mutation(s) in"), ``association_status``, ``references``.
        - ``has_phenotype`` / ``not_has_phenotype`` (Excluded) -> ``HP:`` term with
          ``frequency`` (midpoint fraction), ``frequency_label``/``frequency_term``/
          ``frequency_raw`` and ``diagnostic_criteria``; most frequent first.
        - ``subclass_of`` / ``has_subclass`` -> ORPHA parents and children, with the names of
          the Orphanet classifications that contain the link in ``classifications``.
        """
        if limit <= 0:
            return []
        try:
            code = normalize_orphacode(concept_id)
            if code is None:
                return []
            genes, pheno, classes = await asyncio.gather(
                self._get(f"{GENES_PATH}/{code}", lang=False),
                self._get(f"{PHENO_PATH}/{code}"),
                self._get(f"{CLASS_PATH}/{code}/hchids", lang=False),
            )
            out: list[dict[str, Any]] = []
            out.extend(self._gene_edges(_results(genes))[:limit])
            out.extend(self._phenotype_edges(_results(pheno))[:limit])
            out.extend(await self._class_edges(_results(classes), limit))
            return out
        except Exception as e:
            logger.warning(f"Orphanet get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _gene_edges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for record in records:
            for assoc in record.get("DisorderGeneAssociation") or []:
                gene = assoc.get("Gene") or {}
                refs = {
                    r.get("Source"): r.get("Reference")
                    for r in gene.get("ExternalReference") or []
                }
                symbol = gene.get("Symbol")
                related = f"HGNC:{refs['HGNC']}" if refs.get("HGNC") else symbol
                kind = assoc.get("DisorderGeneAssociationType")
                if not related or (str(related), str(kind)) in seen:
                    continue
                seen.add((str(related), str(kind)))
                edge: dict[str, Any] = {
                    "relation_label": "associated_with",
                    "related_id": related,
                    "related_name": symbol or gene.get("name"),
                    "source": "ORPHANET",
                    "gene_symbol": symbol,
                    "gene_name": gene.get("name"),
                    "gene_type": gene.get("GeneType"),
                    "association_type": kind,
                    "association_status": assoc.get("DisorderGeneAssociationStatus"),
                    "references": _pmids(assoc.get("SourceOfValidation")),
                }
                for key, name in (
                    ("Ensembl", "ensembl"),
                    ("OMIM", "omim_gene"),
                    ("SwissProt", "uniprot"),
                ):
                    if refs.get(key):
                        edge[name] = refs[key]
                loci = [
                    loc.get("GeneLocus") for loc in gene.get("Locus") or [] if loc.get("GeneLocus")
                ]
                if loci:
                    edge["locus"] = loci[0]
                edges.append(edge)
        return edges

    @staticmethod
    def _phenotype_edges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        for record in records:
            disorder = record.get("Disorder") or {}
            references = _pmids(record.get("Source"))
            for assoc in disorder.get("HPODisorderAssociation") or []:
                hpo = assoc.get("HPO") or {}
                if not hpo.get("HPOId"):
                    continue
                freq = _frequency_for(assoc.get("HPOFrequency"))
                excluded = freq.get("frequency_term") == "HP:0040285"
                edge: dict[str, Any] = {
                    "relation_label": "not_has_phenotype" if excluded else "has_phenotype",
                    "related_id": hpo["HPOId"],
                    "related_name": hpo.get("HPOTerm"),
                    "source": "ORPHANET",
                    **freq,
                    "diagnostic_criteria": assoc.get("DiagnosticCriteria"),
                    "references": references,
                }
                edges.append(edge)

        def rank(edge: dict[str, Any]) -> float:
            fraction = edge.get("frequency")
            return -float(fraction) if fraction is not None else 1.0  # unknown frequency last

        edges.sort(key=rank)
        return edges

    async def _class_edges(self, rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        if not rows:
            return []
        links: dict[tuple[str, str], list[str]] = {}
        for row in rows:
            tag = str(row.get("hch_tag") or row.get("hch_id") or "")
            for p in row.get("parents") or []:
                links.setdefault(("subclass_of", str(p)), []).append(tag)
            for c in row.get("childs") or []:
                links.setdefault(("has_subclass", str(c)), []).append(tag)
        labels = await self._label_for({code for _, code in links})
        edges = [
            {
                "relation_label": relation,
                "related_id": f"ORPHA:{code}",
                "related_name": labels.get(code) or None,
                "source": "ORPHANET",
                "classifications": tags,
            }
            for (relation, code), tags in links.items()
        ]
        parents = [e for e in edges if e["relation_label"] == "subclass_of"][:limit]
        children = [e for e in edges if e["relation_label"] == "has_subclass"][:limit]
        return parents + children

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references (OMIM, ICD-10, ICD-11, MONDO, MeSH, UMLS, MedDRA, GARD).

        ``mappingType`` is the SKOS type seen from the ORPHAcode (``exactMatch``,
        ``narrowMatch`` = ORPHAcode is broader than the target, ``broadMatch``);
        the raw Orphanet relation and validation status are kept as ``relation`` and
        ``validation_status``. Unvalidated rows get confidence 0.6.
        """
        try:
            code = normalize_orphacode(concept_id)
            if code is None:
                return []
            records = _results(await self._get(f"{XREF_PATH}/{code}"))
            if not records:
                return []
            mappings: list[dict[str, Any]] = []
            seen: set[str] = set()
            for ref in records[0].get("ExternalReference") or []:
                curie = self._curie(ref)
                if not curie or curie in seen:
                    continue
                seen.add(curie)
                relation = str(ref.get("DisorderMappingRelation") or "")
                token = relation.split(" ", 1)[0]
                mapping_type, confidence = _MAPPING_RELATIONS.get(token, ("relatedMatch", 0.5))
                status = ref.get("DisorderMappingValidationStatus")
                if status and status != "Validated":
                    confidence = min(confidence, 0.6)
                mappings.append(
                    {
                        "fromId": f"ORPHA:{code}",
                        "toId": curie,
                        "fromSource": "ORPHANET",
                        "toSource": curie.split(":", 1)[0],
                        "mappingType": mapping_type,
                        "confidence": confidence,
                        "relation": relation,
                        "validation_status": status,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"Orphanet get_mappings failed for '{concept_id}': {e}")
            return []
