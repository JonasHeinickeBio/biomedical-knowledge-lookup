"""
Cell Ontology (CL) adapter.

The Cell Ontology describes cell types across species (T cell ``CL:0000084``, natural
killer cell ``CL:0000623``, B cell ``CL:0000236``, monocyte ``CL:0000576`` ...) and links
them to anatomy (UBERON), processes (GO) and other cell-type resources via cross-references.
It is the identifier space used by CellMarker, CellxGene and most single-cell atlases.

Served from the EBI OLS4 REST API (``ontology=cl``), no key required. Endpoint quirks:

* OLS4 addresses a term by its IRI **double URL-encoded** in the path
  (``/ontologies/cl/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FCL_0000084``);
  the global ``/terms?iri=`` variant returns the same IRI from every ontology that imports
  it, so the ontology-scoped path is used here.
* ``/terms/{iri}/graph`` returns the term's neighbourhood in one request: ``is_a`` edges
  (``subClassOf``) in both directions plus typed relations (``develops from``,
  ``capable of``, ``has part`` ...). The per-relation ``_links`` hrefs on the term are *not*
  used: they mix the targets of several relations together. The graph is capped by OLS at
  roughly 50 nodes for very broad terms (e.g. ``CL:0000000`` "cell").
* Responses can be slow (0.4 - 6 s); ``min_request_timeout`` is raised accordingly.
* CL itself is CC BY 4.0.
"""

import logging
import re
import urllib.parse
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

OLS_BASE_URL = "https://www.ebi.ac.uk/ols4/api"
CL_ONTOLOGY = "cl"
OBO_IRI_PREFIX = "http://purl.obolibrary.org/obo/"

_CL_ID_RE = re.compile(r"^(?:CL[:_])?(\d{7})$", re.IGNORECASE)
_SEARCH_FIELDS = "iri,obo_id,short_form,label,description,synonym"
# OLS pages hierarchy lists; one page of this size is plenty for a lookup client.
_MAX_PAGE = 100


class CellOntologyAdapter(KnowledgeSourceAdapter):
    """Adapter for the Cell Ontology (CL) served by EBI OLS4."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = OLS_BASE_URL

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CELLONTOLOGY

    def is_available(self) -> bool:
        return True  # OLS4 is public, no key required

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_iri(concept_id: str) -> str | None:
        """Accept ``CL:0000084``, ``CL_0000084``, ``0000084`` or a full IRI."""
        text = (concept_id or "").strip()
        if not text:
            return None
        if text.lower().startswith(("http://", "https://")):
            return text
        match = _CL_ID_RE.match(text)
        if match:
            return f"{OBO_IRI_PREFIX}CL_{match.group(1)}"
        return None

    @staticmethod
    def _to_curie(iri_or_short: str) -> str:
        """``http://purl.obolibrary.org/obo/CL_0000084`` -> ``CL:0000084`` (any OBO prefix)."""
        tail = iri_or_short.rsplit("/", 1)[-1]
        if "_" in tail and not tail.startswith("_"):
            prefix, local = tail.split("_", 1)
            return f"{prefix}:{local}"
        return tail

    def _term_url(self, iri: str, suffix: str = "") -> str:
        double = urllib.parse.quote(urllib.parse.quote(iri, safe=""), safe="")
        return f"{self.base_url}/ontologies/{CL_ONTOLOGY}/terms/{double}{suffix}"

    async def _fetch_term(self, concept_id: str) -> dict[str, Any] | None:
        iri = self._to_iri(concept_id)
        if iri is None:
            return None
        data = await self._make_request(self._term_url(iri))
        if isinstance(data, dict) and data.get("iri"):
            return data
        return None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search CL by label, synonym or definition text.

        A CL identifier (``CL:0000084``) short-circuits to a direct term lookup.
        Obsolete terms are excluded.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            if self._to_iri(text) is not None:
                concept = await self.get_concept_details(text)
                return [concept] if concept else []

            params = {
                "q": text,
                "ontology": CL_ONTOLOGY,
                "type": "class",
                "obsoletes": "false",
                "rows": min(limit, _MAX_PAGE),
                "fieldList": _SEARCH_FIELDS,
            }
            data = await self._make_request(f"{self.base_url}/search", params)
            docs = ((data or {}).get("response") or {}).get("docs") or []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank, doc in enumerate(docs):
                obo_id = doc.get("obo_id") or ""
                # CL imports terms from UBERON/GO/...; keep only real CL classes.
                if not obo_id.startswith("CL:") or obo_id in seen:
                    continue
                concept = self._doc_to_concept(doc)
                if concept is None:
                    continue
                seen.add(obo_id)
                concept.confidence_score = max(0.5, 0.95 - 0.02 * rank)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"CellOntology search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"CellOntology search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full CL term: definition, synonyms, xrefs, direct parents and children."""
        try:
            term = await self._fetch_term(concept_id)
            if term is None:
                return None
            concept = self._term_to_concept(term)
            if concept is None:
                return None
            links = term.get("_links") or {}
            parents = await self._linked_labels(links.get("parents"))
            children = await self._linked_labels(links.get("children"))
            concept.parents = parents
            concept.children = children
            return concept
        except Exception as e:
            logger.error(f"CellOntology get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _linked_labels(self, link: dict[str, Any] | None, limit: int = 25) -> list[str]:
        """Labels behind an OLS hierarchy ``_links`` entry; failures degrade to ``[]``."""
        href = (link or {}).get("href")
        if not href:
            return []
        try:
            data = await self._make_request(href.split("?", 1)[0], {"size": limit})
        except Exception as e:
            logger.debug(f"CellOntology hierarchy request failed for {href}: {e}")
            return []
        terms = ((data or {}).get("_embedded") or {}).get("terms") or []
        return [t["label"] for t in terms if t.get("label")]

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Typed edges around a cell type, from the OLS ``graph`` endpoint.

        ``relation_label`` values: ``is_a`` (parents), ``has_subclass`` (children), the
        term's own relations in snake_case (``develops_from``, ``capable_of``, ``part_of`` ...)
        and ``inverse_<relation>`` for relations that other terms hold *towards* this one
        (e.g. ``inverse_occurs_in`` for GO processes occurring in this cell). Every item
        carries ``direction`` (``outgoing``/``incoming``) and the related term's CURIE.
        Ordered parents, own relations, children, inverse relations; capped by ``limit``.
        """
        if limit <= 0:
            return []
        iri = self._to_iri(concept_id)
        if iri is None:
            return []
        try:
            graph = await self._make_request(self._term_url(iri, "/graph"))
        except Exception as e:
            logger.error(f"CellOntology get_relationships failed for '{concept_id}': {e}")
            return []
        if not isinstance(graph, dict):
            return []

        names = {n.get("iri"): n.get("label", "") for n in graph.get("nodes") or []}
        buckets: dict[int, list[dict[str, Any]]] = {0: [], 1: [], 2: [], 3: []}
        seen: set[tuple[str, str, str]] = set()
        for edge in graph.get("edges") or []:
            source, target = edge.get("source"), edge.get("target")
            raw_label = edge.get("label") or ""
            if iri not in (source, target) or not raw_label or source == target:
                continue
            is_a = raw_label == "subClassOf"
            outgoing = source == iri
            other = target if outgoing else source
            relation = (
                "is_a" if is_a else re.sub(r"\W+", "_", raw_label.strip()).strip("_").lower()
            )
            if is_a:
                label, bucket = ("is_a", 0) if outgoing else ("has_subclass", 2)
            elif outgoing:
                label, bucket = relation, 1
            else:
                label, bucket = f"inverse_{relation}", 3
            key = (label, other, "")
            if key in seen:
                continue
            seen.add(key)
            buckets[bucket].append(
                {
                    "relation_label": label,
                    "related_id": self._to_curie(other),
                    "related_name": names.get(other, ""),
                    "source": "CL",
                    "direction": "outgoing" if outgoing else "incoming",
                    "relation_iri": edge.get("uri", ""),
                }
            )
        ordered = [item for b in sorted(buckets) for item in buckets[b]]
        return ordered[:limit]

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references declared on the CL term (UBERON, MESH, FMA, BTO, ZFA ...)."""
        try:
            term = await self._fetch_term(concept_id)
        except Exception as e:
            logger.error(f"CellOntology get_mappings failed for '{concept_id}': {e}")
            return []
        if term is None:
            return []
        from_id = term.get("obo_id") or self._to_curie(term.get("iri", ""))
        seen: set[tuple[str, str]] = set()
        mappings: list[dict[str, Any]] = []
        for database, local in self._iter_xrefs(term):
            if (database, local) in seen:
                continue
            seen.add((database, local))
            mappings.append(
                {
                    "fromId": from_id,
                    "toId": f"{database}:{local}",
                    "fromSource": "CL",
                    "toSource": database,
                    "mappingType": "xref",
                    "confidence": 0.9,
                }
            )
        return mappings

    @staticmethod
    def _iter_xrefs(term: dict[str, Any]) -> list[tuple[str, str]]:
        """``(database, local id)`` pairs from ``obo_xref``, falling back to the annotation."""
        pairs: list[tuple[str, str]] = []
        for xref in term.get("obo_xref") or []:
            if xref.get("database") and xref.get("id"):
                pairs.append((str(xref["database"]), str(xref["id"])))
        if not pairs:
            raw = (term.get("annotation") or {}).get("database_cross_reference") or []
            for item in [raw] if isinstance(raw, str) else raw:
                database, _, local = str(item).partition(":")
                if database and local:
                    pairs.append((database, local))
        return pairs

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _doc_to_concept(self, doc: dict[str, Any]) -> UnifiedConcept | None:
        obo_id, label = doc.get("obo_id"), doc.get("label")
        if not obo_id or not label:
            return None
        concept = self._create_concept(obo_id, label, ConceptType.CELL_TYPE)
        iri = doc.get("iri")
        if iri:
            concept.add_identifier(self.get_source(), iri, label, iri)
        self._add_unique(concept.definitions, doc.get("description"))
        self._add_unique(concept.synonyms, doc.get("synonym"))
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = doc
        return concept

    def _term_to_concept(self, term: dict[str, Any]) -> UnifiedConcept | None:
        obo_id = term.get("obo_id") or self._to_curie(term.get("short_form") or "")
        label = term.get("label")
        if not obo_id or not label:
            return None
        concept = self._create_concept(obo_id, label, ConceptType.CELL_TYPE)
        iri = term.get("iri")
        if iri:
            concept.add_identifier(self.get_source(), iri, label, iri)
        self._add_unique(concept.definitions, term.get("description"))
        self._add_unique(concept.synonyms, term.get("synonyms"))
        for database, local in self._iter_xrefs(term):
            self._add_unique(concept.categories, f"Xref: {database}:{local}")
        if term.get("is_obsolete") and concept.categories is not None:
            concept.categories.append("obsolete")
        concept.confidence_score = 0.95
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                key: term.get(key)
                for key in (
                    "iri",
                    "obo_id",
                    "label",
                    "in_subset",
                    "is_obsolete",
                    "term_replaced_by",
                    "annotation",
                )
                if key in term
            }
        return concept

    @staticmethod
    def _add_unique(target: list[str] | None, values: Any) -> None:
        """Append str/list ``values`` to ``target`` skipping blanks and duplicates."""
        if target is None or not values:
            return
        for value in [values] if isinstance(values, str) else values:
            if isinstance(value, str) and value.strip() and value not in target:
                target.append(value)
