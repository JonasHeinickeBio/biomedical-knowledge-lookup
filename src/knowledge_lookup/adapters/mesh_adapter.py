"""
MeSH (Medical Subject Headings) Knowledge Source Adapter

Adapter for the NLM MeSH RDF service (https://id.nlm.nih.gov/mesh/), keyless and
free to use. MeSH is the vocabulary behind PubMed indexing, so it is the join key
for literature-mined records.

Live-verified behaviour that shapes this adapter:

- ``/lookup/descriptor`` and ``/lookup/term`` are fast (~0.7 s) label look-ups but
  return only ``{resource, label}`` pairs, in *alphabetical* order (not by
  relevance) and only match the descriptor's *preferred* label (``/lookup/term``
  matches entry terms but returns term IDs ``T...``, not descriptors). We therefore
  over-fetch and rank locally.
- The SPARQL endpoint (``/mesh/sparql``) returns everything in one round trip
  (~1 s): label, record type, scope note, tree numbers, entry terms, broader /
  narrower descriptors, allowable qualifiers and supplementary-concept mappings. It
  also resolves entry-term IDs (``T...``) to their descriptor/supplementary
  concept. Free-text ``FILTER(CONTAINS(...))`` scans over all terms take ~17 s, so
  searches never use them; they combine the two REST look-ups with one batched
  SPARQL query instead.
- MeSH RDF carries no UMLS CUI or other vocabulary cross-references, so
  :meth:`get_mappings` only reports what MeSH itself states (supplementary concept
  -> mapped heading, "see also" headings). Use the UMLS adapter for CUIs.

Record types: descriptors (``D...``), supplementary concept records (``C...``)
and qualifiers (``Q...``). ``MESH:D003920``, ``MeSH:D003920`` and ``D003920``
are all accepted.

API documentation: https://hhs.github.io/meshrdf/
"""

import asyncio
import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

MESH_BASE_URL = "https://id.nlm.nih.gov/mesh"
MESH_LOOKUP_URL = f"{MESH_BASE_URL}/lookup"
MESH_SPARQL_URL = f"{MESH_BASE_URL}/sparql"

_ID_RE = re.compile(r"^[DCQ]\d{3,9}$")
_TERM_ID_RE = re.compile(r"^T\d{3,9}$")
_PREFIX_RE = re.compile(r"^(?:https?://id\.nlm\.nih\.gov/mesh/|mesh:)", re.IGNORECASE)

_SPARQL_PREFIXES = """PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# Leading letter of a MeSH tree number -> concept type. Checked in this order, so a
# descriptor filed under both "Diseases" (C) and "Chemicals and Drugs" (D) is a disease.
_TREE_TYPES: list[tuple[str, ConceptType]] = [
    ("C23.888", ConceptType.SYMPTOM),  # Signs and Symptoms
    ("C", ConceptType.DISEASE),
    ("D12.776", ConceptType.PROTEIN),  # Proteins
    ("D", ConceptType.CHEMICAL),
    ("A", ConceptType.ANATOMICAL_ENTITY),
    ("B", ConceptType.ORGANISM),
    ("E", ConceptType.PROCEDURE),
    ("G", ConceptType.BIOLOGICAL_PROCESS),
]
_SCR_TYPES = {
    "SCR_Disease": ConceptType.DISEASE,
    "SCR_Chemical": ConceptType.CHEMICAL,
    "SCR_Organism": ConceptType.ORGANISM,
    "SCR_Anatomy": ConceptType.ANATOMICAL_ENTITY,
    "SCR_Protocol": ConceptType.PROCEDURE,
}


class MeSHAdapter(KnowledgeSourceAdapter):
    """Adapter for NLM MeSH descriptors, supplementary concepts and qualifiers."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = MESH_BASE_URL

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.MESH

    def is_available(self) -> bool:
        return True  # keyless public service

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_id(concept_id: str) -> str | None:
        """Return the bare MeSH UI (``D003920``) or ``None`` if it is not one.

        Accepts ``MESH:D003920``, ``MeSH:D003920``, ``D003920`` and the full
        ``http(s)://id.nlm.nih.gov/mesh/D003920`` URI.
        """
        if not isinstance(concept_id, str):
            return None
        bare = _PREFIX_RE.sub("", concept_id.strip()).upper()
        return bare if _ID_RE.match(bare) else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search MeSH headings and entry terms.

        Runs the three cheap REST look-ups in parallel (exact descriptor label,
        descriptor label contains, entry term contains), ranks locally (exact label
        or entry term, then prefix, then substring) and enriches the survivors with a
        single batched SPARQL query. A query that is already a MeSH UI short-circuits
        to :meth:`get_concept_details`.
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            direct = self.normalize_id(query)
            if direct:
                concept = await self.get_concept_details(direct)
                return [concept] if concept else []

            over = max(limit * 3, 20)
            exact, contains, terms = await asyncio.gather(
                self._lookup("descriptor", query, "exact", 5),
                self._lookup("descriptor", query, "contains", over),
                self._lookup("term", query, "contains", over),
                return_exceptions=True,
            )
            candidates = self._rank_candidates(query, exact, contains, terms)
            if not candidates:
                return []
            ids = [c[0] for c in candidates][: max(limit * 2, limit)]
            infos = await self._fetch_details(ids)

            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for ident in self._order_by_rank(ids, infos):
                if ident in seen:
                    continue
                seen.add(ident)
                concept = self._build_concept(ident, infos[ident])
                if concept:
                    concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"MeSH search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"MeSH search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Fetch one descriptor / supplementary concept / qualifier (one SPARQL call)."""
        ident = self.normalize_id(concept_id)
        if not ident:
            logger.warning(f"MeSH: '{concept_id}' is not a MeSH identifier")
            return None
        try:
            infos = await self._fetch_details([ident])
            info = infos.get(ident)
            return self._build_concept(ident, info) if info else None
        except Exception as e:
            logger.error(f"MeSH get_concept_details failed for '{concept_id}': {e}")
            return None

    async def lookup_descriptor(self, label: str) -> UnifiedConcept | None:
        """Fast exact-label lookup of a MeSH heading (no SPARQL, ~0.7 s).

        Meant for annotating corpora whose records already carry MeSH heading
        strings: one REST call, matching the preferred descriptor label
        case-insensitively. Returns a minimal concept (id + label; no scope note,
        entry terms or tree numbers) -- call :meth:`get_concept_details` when those
        are needed. Entry terms are deliberately not tried here; use
        :meth:`search_concepts` for that.
        """
        label = (label or "").strip()
        if not label:
            return None
        try:
            hits = await self._lookup("descriptor", label, "exact", 5)
            for ident, hit_label in hits:
                if hit_label.lower() == label.lower():
                    return self._create_concept(ident, hit_label, ConceptType.UNKNOWN)
            return None
        except Exception as e:
            logger.warning(f"MeSH lookup_descriptor failed for '{label}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return typed MeSH relationships for a descriptor / supplementary concept.

        ``relation_label`` is one of:

        - ``broader_than`` / ``narrower_than`` -- describe the *related* heading relative
          to the queried one: ``broader_than`` rows are its broader (parent) headings,
          ``narrower_than`` rows its narrower (child) headings. MeSH tree links are
          direct, one level only.
        - ``allowed_qualifier`` -- permitted subheadings (``Q...``), descriptors only.
        - ``see_also`` -- related headings suggested by MeSH.
        - ``mapped_to`` -- supplementary concept -> the headings it is indexed under.

        ``limit`` caps each relation kind separately.
        """
        ident = self.normalize_id(concept_id)
        if not ident or limit <= 0:
            return []
        try:
            query = (
                _SPARQL_PREFIXES
                + f"""SELECT ?kind ?r ?l WHERE {{
  {{ mesh:{ident} meshv:broaderDescriptor ?r . ?r rdfs:label ?l . BIND("broader" AS ?kind) }}
  UNION {{ ?r meshv:broaderDescriptor mesh:{ident} . ?r rdfs:label ?l . BIND("narrower" AS ?kind) }}
  UNION {{ mesh:{ident} meshv:allowableQualifier ?r . ?r rdfs:label ?l .
          BIND("qualifier" AS ?kind) }}
  UNION {{ mesh:{ident} meshv:seeAlso ?r . ?r rdfs:label ?l . BIND("see_also" AS ?kind) }}
  UNION {{ mesh:{ident} (meshv:preferredMappedTo|meshv:mappedTo) ?r . ?r rdfs:label ?l .
          BIND("mapped" AS ?kind) }}
}}"""
            )
            rows = await self._sparql(query)
            label_for = {
                "broader": "broader_than",
                "narrower": "narrower_than",
                "qualifier": "allowed_qualifier",
                "see_also": "see_also",
                "mapped": "mapped_to",
            }
            counts: dict[str, int] = {}
            seen: set[tuple[str, str]] = set()
            relationships: list[dict[str, Any]] = []
            for row in sorted(rows, key=lambda r: (r["kind"], r["l"].lower())):
                kind = row["kind"]
                related_id = row["r"].rsplit("/", 1)[-1]
                key = (kind, related_id)
                if kind not in label_for or key in seen or counts.get(kind, 0) >= limit:
                    continue
                seen.add(key)
                counts[kind] = counts.get(kind, 0) + 1
                relationships.append(
                    {
                        "relation_label": label_for[kind],
                        "related_id": f"MESH:{related_id}",
                        "related_name": row["l"],
                        "source": "MeSH",
                    }
                )
            return relationships
        except Exception as e:
            logger.warning(f"MeSH get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return mappings MeSH itself states (it exposes no UMLS/ICD cross-references).

        Supplementary concept records map to the descriptors they are indexed
        under (``mappingType`` ``preferred_mapped_to`` / ``mapped_to``), and
        descriptors list "see also" headings. Same dict shape as the other adapters.
        """
        ident = self.normalize_id(concept_id)
        if not ident:
            return []
        try:
            query = (
                _SPARQL_PREFIXES
                + f"""SELECT ?kind ?r WHERE {{
  {{ mesh:{ident} meshv:preferredMappedTo ?r . BIND("preferred_mapped_to" AS ?kind) }}
  UNION {{ mesh:{ident} meshv:mappedTo ?r . BIND("mapped_to" AS ?kind) }}
}}"""
            )
            rows = await self._sparql(query)
            mappings: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                target = row["r"].rsplit("/", 1)[-1]
                if target in seen:
                    continue
                seen.add(target)
                mappings.append(
                    {
                        "fromId": f"MESH:{ident}",
                        "toId": f"MESH:{target}",
                        "fromSource": "MeSH",
                        "toSource": "MeSH",
                        "mappingType": row["kind"],
                        "confidence": 1.0 if row["kind"] == "preferred_mapped_to" else 0.8,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"MeSH get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _lookup(
        self, kind: str, label: str, match: str, limit: int
    ) -> list[tuple[str, str]]:
        """REST label look-up -> ``[(UI, label)]`` (UI is ``D...`` or ``T...``)."""
        data = await self._make_request(
            f"{MESH_LOOKUP_URL}/{kind}",
            params={"label": label, "match": match, "limit": limit},
            headers={"Accept": "application/json"},
        )
        out: list[tuple[str, str]] = []
        if isinstance(data, list):
            for item in data:
                resource = item.get("resource", "") if isinstance(item, dict) else ""
                lab = item.get("label", "") if isinstance(item, dict) else ""
                if resource and lab:
                    out.append((resource.rsplit("/", 1)[-1], lab))
        return out

    async def _sparql(self, query: str) -> list[dict[str, str]]:
        """Run a SPARQL SELECT and return rows as ``{var: value}`` dicts."""
        data = await self._make_request(
            MESH_SPARQL_URL,
            params={"query": query, "format": "JSON", "limit": 1000, "offset": 0},
            headers={"Accept": "application/sparql-results+json"},
        )
        if not isinstance(data, dict):
            return []
        bindings = (data.get("results") or {}).get("bindings") or []
        return [{k: v.get("value", "") for k, v in row.items()} for row in bindings]

    # ------------------------------------------------------------------
    # Ranking / parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _rank_candidates(
        query: str, exact: Any, contains: Any, terms: Any
    ) -> list[tuple[str, int]]:
        """Merge REST hits into ``[(UI, rank)]`` (lower rank = better), de-duplicated.

        Failed look-ups arrive as exceptions (``gather(return_exceptions=True)``) and
        are skipped, so one flaky endpoint does not empty the result.
        """
        q = query.lower()
        best: dict[str, int] = {}

        def add(ident: str, rank: int) -> None:
            if ident not in best or rank < best[ident]:
                best[ident] = rank

        for ident, _ in exact if isinstance(exact, list) else []:
            add(ident, 0)
        for ident, label in contains if isinstance(contains, list) else []:
            low = label.lower()
            add(ident, 0 if low == q else 2 if low.startswith(q) else 3)
        for ident, label in terms if isinstance(terms, list) else []:
            low = label.lower()
            add(ident, 1 if low == q else 2 if low.startswith(q) else 4)
        if not best:
            for failure in (exact, contains, terms):
                if isinstance(failure, BaseException):
                    raise failure  # nothing usable and a call failed: let the caller log it
        return sorted(best.items(), key=lambda kv: (kv[1], kv[0]))

    def _order_by_rank(self, ids: list[str], infos: dict[str, dict[str, Any]]) -> list[str]:
        """Candidate order is already ranked; term IDs resolve to their heading in place."""
        ordered: list[str] = []
        for ident in ids:
            if _TERM_ID_RE.match(ident):
                ordered.extend(
                    resolved for resolved, i in infos.items() if ident in i.get("via_terms", ())
                )
            elif ident in infos:
                ordered.append(ident)
        return ordered

    async def _fetch_details(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        """Batched SPARQL detail fetch for descriptor/SCR/qualifier UIs and ``T`` term UIs.

        Returns ``{UI: info}`` where ``info`` collects label, record types, scope note
        (or SCR ``note``), tree numbers, entry terms and the term IDs that led here.
        """
        direct = [i for i in dict.fromkeys(ids) if _ID_RE.match(i)]
        via = [i for i in dict.fromkeys(ids) if _TERM_ID_RE.match(i)]
        if not direct and not via:
            return {}
        branches = []
        if direct:
            values = " ".join(f"mesh:{i}" for i in direct)
            branches.append(f"{{ VALUES ?d {{ {values} }} ?d rdfs:label ?l0 }}")
        if via:
            values = " ".join(f"mesh:{i}" for i in via)
            branches.append(
                f"{{ VALUES ?src {{ {values} }} ?c meshv:term ?src . "
                "?d (meshv:preferredConcept|meshv:concept) ?c . BIND(STRAFTER(STR(?src), "
                '"mesh/") AS ?via) }'
            )
        query = (
            _SPARQL_PREFIXES
            + f"""SELECT ?d ?kind ?v ?via WHERE {{
  {{ SELECT DISTINCT ?d ?via WHERE {{ {" UNION ".join(branches)} }} }}
  {{ ?d rdfs:label ?v . BIND("label" AS ?kind) }}
  UNION {{ ?d a ?ty . BIND(REPLACE(STR(?ty), "^.*#", "") AS ?v) BIND("type" AS ?kind) }}
  UNION {{ ?d meshv:preferredConcept/meshv:scopeNote ?v . BIND("scope" AS ?kind) }}
  UNION {{ ?d meshv:note ?v . BIND("note" AS ?kind) }}
  UNION {{ ?d meshv:treeNumber ?t . BIND(REPLACE(STR(?t), "^.*/", "") AS ?v)
          BIND("tree" AS ?kind) }}
  UNION {{ ?d meshv:preferredConcept/meshv:term/meshv:prefLabel ?v . BIND("term" AS ?kind) }}
  UNION {{ ?d meshv:active ?v . BIND("active" AS ?kind) }}
}}"""
        )
        rows = await self._sparql(query)
        infos: dict[str, dict[str, Any]] = {}
        for row in rows:
            ident = row["d"].rsplit("/", 1)[-1]
            info = infos.setdefault(
                ident,
                {
                    "label": "",
                    "types": [],
                    "scope": "",
                    "trees": [],
                    "terms": [],
                    "active": True,
                    "via_terms": [],
                },
            )
            kind, value = row.get("kind", ""), row.get("v", "")
            if row.get("via") and row["via"] not in info["via_terms"]:
                info["via_terms"].append(row["via"])
            if kind == "label":
                info["label"] = value
            elif kind == "type" and value not in info["types"]:
                info["types"].append(value)
            elif kind in ("scope", "note") and not info["scope"]:
                info["scope"] = value
            elif kind == "tree" and value not in info["trees"]:
                info["trees"].append(value)
            elif kind == "term" and value not in info["terms"]:
                info["terms"].append(value)
            elif kind == "active":
                info["active"] = value.lower() != "false"
        return infos

    def _build_concept(self, ident: str, info: dict[str, Any] | None) -> UnifiedConcept | None:
        """Turn a parsed SPARQL info dict into a :class:`UnifiedConcept`."""
        if not info or not info.get("label"):
            return None
        label = info["label"]
        concept = self._create_concept(ident, label, self._concept_type(ident, info))
        if concept.identifiers:
            concept.identifiers[0].url = f"https://meshb.nlm.nih.gov/record/ui?ui={ident}"
        if info["scope"]:
            concept.definitions = [info["scope"]]
        seen = {label.lower()}
        for term in info["terms"]:
            if term.lower() not in seen:
                seen.add(term.lower())
                concept.synonyms.append(term)  # type: ignore[union-attr]
        concept.semantic_types = list(info["types"])
        concept.categories = list(dict.fromkeys(t[0] for t in info["trees"] if t))
        concept.source_data[KnowledgeSource.MESH] = {  # type: ignore[index]
            "ui": ident,
            "record_type": info["types"][0] if info["types"] else None,
            "tree_numbers": info["trees"],
            "active": info["active"],
        }
        return concept

    @staticmethod
    def _concept_type(ident: str, info: dict[str, Any]) -> ConceptType:
        for record_type in info["types"]:
            if record_type in _SCR_TYPES:
                return _SCR_TYPES[record_type]
        if ident.startswith("C"):
            return ConceptType.UNKNOWN
        for prefix, ctype in _TREE_TYPES:
            if any(t.startswith(prefix) for t in info["trees"]):
                return ctype
        return ConceptType.UNKNOWN
