"""
Monarch Initiative Knowledge Source Adapter

Adapter for the Monarch Initiative knowledge graph (API v3), which integrates
gene-disease-phenotype data from HPO, MONDO, OMIM, Orphanet, ClinGen, ClinVar, model
organism databases and more into one Biolink-typed graph.

API documentation: https://api-v3.monarchinitiative.org/docs

Endpoints used (all keyless, JSON, ~0.6-1.5 s per call):

- ``GET /search?q=...&category=...``: Solr search over genes, diseases and phenotypes.
  ``category`` may be repeated.
- ``GET /entity/{id}``: one node with synonyms, xrefs/mappings, hierarchy and
  ``association_counts``. The id must be Monarch's *primary* CURIE (``HGNC:1100``,
  ``MONDO:0005148``, ``HP:0012432``) in canonical prefix case; ``OMIM:``/``Orphanet:``/
  ``UMLS:`` CURIEs and human ``NCBIGene:`` ids answer 404. Those are therefore resolved via
  ``/search`` (which indexes the ``xref`` field) first.
- ``GET /association?subject=|object=&category=...``: typed edges. Qualifier fields on
  an association (verified live): ``frequency_qualifier`` (+ ``_label``), ``has_percentage``,
  ``has_count``, ``has_total``, ``has_quotient`` (fraction), ``onset_qualifier`` (+ ``_label``),
  ``sex_qualifier`` (+ ``_label``), ``negated``, ``has_evidence`` (ECO ids), ``publications``
  and ``primary_knowledge_source`` (``infores:omim``, ``infores:orphanet``, ...).

Licences: Monarch data is CC BY 4.0 in aggregate, but each primary source (OMIM, Orphanet,
ClinVar, ...) keeps its own terms; see https://monarchinitiative.org/about/licensing.
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._pheno_common import (
    CANONICAL_PREFIXES,
    Frequency,
    add_known_identifier,
    frequency_extras,
    parse_frequency,
    split_curie,
)

logger = logging.getLogger(__name__)

_MONARCH_BASE_URL = "https://api-v3.monarchinitiative.org/v3/api"

_GENE = "biolink:Gene"
_DISEASE = "biolink:Disease"
_PHENOTYPE = "biolink:PhenotypicFeature"

_D2P = "biolink:DiseaseToPhenotypicFeatureAssociation"
_G2P = "biolink:GeneToPhenotypicFeatureAssociation"
_CAUSAL = "biolink:CausalGeneToDiseaseAssociation"
_CORRELATED = "biolink:CorrelatedGeneToDiseaseAssociation"
_HOMOLOGY = "biolink:GeneToGeneHomologyAssociation"
_VARIANT = "biolink:VariantToDiseaseAssociation"

_CATEGORY_TO_TYPE: dict[str, ConceptType] = {
    _GENE: ConceptType.GENE,
    _DISEASE: ConceptType.DISEASE,
    _PHENOTYPE: ConceptType.PHENOTYPE,
    "biolink:SequenceVariant": ConceptType.MOLECULAR_ENTITY,
}

# Prefixes whose primary node ids Monarch serves directly from /entity, with the node
# category they imply (lets get_relationships skip the entity lookup for the common cases).
_PREFIX_CATEGORY: dict[str, str] = {
    "HGNC": _GENE,
    "MONDO": _DISEASE,
    "HP": _PHENOTYPE,
}

# Which associations describe each kind of node, as
# (association category, side of the association the query node is on, max rows or None).
# "subject"/"object" refer to the Biolink association, e.g. in a
# DiseaseToPhenotypicFeatureAssociation the disease is the subject.
_RELATIONSHIP_PLANS: dict[str, list[tuple[str, str, int | None]]] = {
    _GENE: [
        (_G2P, "subject", None),
        (_CAUSAL, "subject", None),
        (_CORRELATED, "subject", None),
        (_HOMOLOGY, "subject", None),
    ],
    _DISEASE: [
        (_D2P, "subject", None),
        (_CAUSAL, "object", None),
        (_CORRELATED, "object", None),
        (_VARIANT, "object", 5),  # thousands of ClinVar variants; keep only a sample
    ],
    _PHENOTYPE: [
        (_D2P, "object", None),
        (_G2P, "object", None),
    ],
}

# Predicate name seen from the *object's* side of an edge. Anything not listed keeps its
# own name (symmetric predicates such as ``orthologous_to``).
_INVERSE_PREDICATES: dict[str, str] = {
    "causes": "caused_by",
    "contributes_to": "contributed_to_by",
    "gene_associated_with_condition": "condition_associated_with_gene",
    "has_phenotype": "phenotype_of",
}

_SYNONYM_FIELDS = ("exact_synonym", "broad_synonym", "narrow_synonym", "related_synonym")


class MonarchAdapter(KnowledgeSourceAdapter):
    """Adapter for the Monarch Initiative knowledge graph (API v3)."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = _MONARCH_BASE_URL
        # Monarch indexes every model-organism and livestock gene; for a human-medicine
        # workflow those drown the human gene (BRCA1: 107 genes, 17 human), so
        # search_concepts restricts genes to Homo sapiens unless this is turned off.
        self.human_genes_only = True

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.MONARCH

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_curie(concept_id: str) -> str | None:
        """Return ``concept_id`` with a canonical-case prefix, or ``None`` if it is not a CURIE.

        ``hp:0012432`` -> ``HP:0012432``; ``ORPHA:558`` / ``orphanet:558`` -> ``Orphanet:558``;
        unknown prefixes are upper-cased.
        """
        parts = split_curie(concept_id or "")
        if parts is None:
            return None
        prefix, local = parts
        lowered = prefix.lower()
        if lowered in ("orpha", "orphanet"):
            return f"Orphanet:{local}"
        return f"{CANONICAL_PREFIXES.get(lowered, prefix.upper())}:{local}"

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        return getattr(exc, "status", None) == 404

    async def _fetch_entity(self, curie: str) -> dict[str, Any] | None:
        """GET ``/entity/{curie}``; ``None`` on 404, other errors propagate."""
        try:
            data = await self._make_request(f"{self.base_url}/entity/{curie}")
        except Exception as exc:
            if self._is_not_found(exc):
                return None
            raise
        return data if isinstance(data, dict) and data.get("id") else None

    async def _resolve_via_xref(self, curie: str) -> str | None:
        """Find the Monarch node whose ``xref`` list contains ``curie`` (OMIM/Orphanet/UMLS...).

        /search indexes xrefs, so ``q=OMIM:113705`` finds ``HGNC:1100``. The hit is only
        accepted when the xref really matches, so a text hit on something else is ignored.
        """
        data = await self._make_request(f"{self.base_url}/search", {"q": curie, "limit": 5})
        wanted = curie.lower()
        items = data.get("items") if isinstance(data, dict) else None
        for item in items or []:
            xrefs = [str(x).lower() for x in item.get("xref") or []]
            if wanted in xrefs or str(item.get("id", "")).lower() == wanted:
                return item.get("id")
        return None

    async def _get_entity(self, concept_id: str) -> dict[str, Any] | None:
        """Resolve any supported identifier to the full Monarch entity document."""
        curie = self._normalize_curie(concept_id)
        if curie is None:
            return None
        prefix = curie.split(":", 1)[0]
        # OMIM/Orphanet/UMLS are never primary node ids, so skip the guaranteed 404.
        if prefix not in ("OMIM", "Orphanet", "UMLS", "MESH", "DOID", "EFO", "NCIT"):
            entity = await self._fetch_entity(curie)
            if entity is not None:
                return entity
        primary = await self._resolve_via_xref(curie)
        if primary and primary != curie:
            return await self._fetch_entity(primary)
        return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def _search(
        self, query: str, limit: int, categories: list[str], human_only: bool = False
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"q": query, "limit": limit, "category": categories}
        if human_only:
            params["in_taxon_label"] = "Homo sapiens"
        data = await self._make_request(f"{self.base_url}/search", params)
        items = data.get("items") if isinstance(data, dict) else None
        return [item for item in items or [] if isinstance(item, dict)]

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Monarch for diseases, phenotypes and genes matching ``query``.

        Diseases and phenotypic features come from one request, genes (human only, see
        ``human_genes_only``) from a second one; results are merged by Monarch's search
        score. ``confidence_score`` is the score relative to the best hit.
        """
        needle = (query or "").strip()
        if not needle or limit <= 0:
            return []
        try:
            hits = await self._search(needle, limit, [_DISEASE, _PHENOTYPE])
            hits += await self._search(needle, limit, [_GENE], human_only=self.human_genes_only)

            hits.sort(key=lambda item: item.get("score") or 0.0, reverse=True)
            top = max((item.get("score") or 0.0 for item in hits), default=0.0)
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in hits:
                if item.get("id") in seen:
                    continue
                concept = self._convert_node(item)
                if concept is None:
                    continue
                seen.add(item["id"])
                score = item.get("score") or 0.0
                concept.confidence_score = round(score / top, 3) if top else 0.5
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"Monarch search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"Monarch search failed for '{query}': {e}")
            return []

    # ------------------------------------------------------------------
    # Details
    # ------------------------------------------------------------------

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Fetch a node via ``/entity`` (HGNC/MONDO/HP/NCBIGene primary ids, or OMIM/Orphanet
        /UMLS xrefs resolved through search)."""
        try:
            entity = await self._get_entity(concept_id)
            if entity is None:
                return None
            concept = self._convert_node(entity, detailed=True)
            if concept is not None:
                concept.confidence_score = 1.0
            return concept
        except Exception as e:
            logger.error(f"Monarch get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the node's cross-references (``xref`` plus ``mappings``/``external_links``).

        Same ``{fromId, toId, fromSource, toSource, mappingType, confidence}`` shape as the
        other adapters; ``toSource`` is the CURIE prefix (``OMIM``, ``MESH``, ``SCTID`` ...).
        """
        try:
            entity = await self._get_entity(concept_id)
            if entity is None:
                return []
            from_id = entity["id"]
            targets: list[str] = [str(x) for x in entity.get("xref") or []]
            for key in ("mappings", "external_links"):
                targets.extend(str(m.get("id")) for m in entity.get(key) or [] if m.get("id"))
            if entity.get("same_as"):
                targets.extend(str(x) for x in entity["same_as"])

            mappings: list[dict[str, Any]] = []
            seen: set[str] = set()
            for target in targets:
                parts = split_curie(target)
                if parts is None or target in seen or target == from_id:
                    continue
                seen.add(target)
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": target,
                        "fromSource": "MONARCH",
                        "toSource": parts[0],
                        "mappingType": "xref",
                        "confidence": 0.9,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"Monarch get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return typed edges for a gene, disease or phenotype (up to ``limit`` per category).

        What is returned depends on the node's Biolink category:

        - gene: ``has_phenotype``, ``causes`` / ``gene_associated_with_condition``
          (diseases), ``orthologous_to`` (other species, with ``species``)
        - disease: ``has_phenotype`` *with* ``frequency`` / ``onset`` / ``sex`` qualifiers when
          Monarch has them, genes (``caused_by`` / ``condition_associated_with_gene``) and a
          small sample (5) of linked ClinVar variants
        - phenotype: diseases and genes it is a phenotype of (``phenotype_of``)

        Edges use ``{relation_label, related_id, related_name, source}`` plus, when known,
        ``frequency`` (fraction), ``frequency_label``, ``frequency_count``/``_total``,
        ``onset``, ``sex``, ``evidence`` (ECO ids), ``publications``, ``primary_source``,
        ``related_category``, ``species``, ``direction`` and ``association_category``. A
        negated association gets a ``not_`` prefix on its label.
        """
        if limit <= 0:
            return []
        try:
            curie = self._normalize_curie(concept_id)
            if curie is None:
                return []
            category = _PREFIX_CATEGORY.get(curie.split(":", 1)[0])
            node_id = curie
            if category is None:
                entity = await self._get_entity(curie)
                if entity is None:
                    return []
                node_id, category = entity["id"], entity.get("category", "")
            plan = _RELATIONSHIP_PLANS.get(category)
            if plan is None:
                return []

            relationships: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for assoc_category, side, cap in plan:
                params = {
                    side: node_id,
                    "category": assoc_category,
                    "limit": min(cap, limit) if cap else limit,
                }
                data = await self._make_request(f"{self.base_url}/association", params)
                items = data.get("items") if isinstance(data, dict) else None
                for item in items or []:
                    edge = self._convert_association(item, side)
                    if edge is None:
                        continue
                    key = (edge["relation_label"], edge["related_id"])
                    if key in seen:  # e.g. one gene-disease pair asserted by OMIM and ClinGen
                        continue
                    seen.add(key)
                    relationships.append(edge)
            return relationships
        except Exception as e:
            logger.warning(f"Monarch get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _association_frequency(item: dict[str, Any]) -> Frequency | None:
        """Best frequency for an association: observed n/m, else percentage, else HP term."""
        quotient = item.get("has_quotient")
        percentage = item.get("has_percentage")
        term_id = item.get("frequency_qualifier")
        term = parse_frequency(term_id) if term_id else None
        if quotient is not None or percentage is not None:
            fraction = float(quotient) if quotient is not None else float(percentage or 0) / 100.0
            count, total = item.get("has_count"), item.get("has_total")
            label = f"{count}/{total}" if count is not None and total else f"{fraction:.0%}"
            return Frequency(fraction, label, label, term.term if term else None)
        if term is not None:
            term_label = item.get("frequency_qualifier_label") or term.label
            return Frequency(term.fraction, term_label, str(term_id), term.term)
        return None

    def _convert_association(self, item: dict[str, Any], query_side: str) -> dict[str, Any] | None:
        """Turn a Monarch association document into a relationship dict."""
        other = "object" if query_side == "subject" else "subject"
        related_id = item.get(other)
        if not related_id:
            return None
        predicate = str(item.get("predicate") or "biolink:related_to").split(":", 1)[-1]
        label = (
            predicate if query_side == "subject" else _INVERSE_PREDICATES.get(predicate, predicate)
        )
        if item.get("negated"):
            label = f"not_{label}"

        edge: dict[str, Any] = {
            "relation_label": label,
            "related_id": related_id,
            "related_name": item.get(f"{other}_label") or related_id,
            "source": "MONARCH",
            "direction": "outgoing" if query_side == "subject" else "incoming",
            "association_category": item.get("category"),
        }
        optional: dict[str, Any] = {
            "related_category": item.get(f"{other}_category"),
            "species": item.get(f"{other}_taxon_label"),
            "primary_source": item.get("primary_knowledge_source"),
            "evidence": item.get("has_evidence"),
            "publications": item.get("publications"),
            "onset": item.get("onset_qualifier_label"),
            "onset_id": item.get("onset_qualifier"),
            "sex": item.get("sex_qualifier_label"),
            "frequency_count": item.get("has_count"),
            "frequency_total": item.get("has_total"),
        }
        edge.update({k: v for k, v in optional.items() if v not in (None, [], "")})
        edge.update(frequency_extras(self._association_frequency(item)))
        return edge

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_node(self, node: dict[str, Any], detailed: bool = False) -> UnifiedConcept | None:
        """Convert a search hit or ``/entity`` document into a UnifiedConcept."""
        try:
            node_id = node.get("id", "")
            label = node.get("name") or node.get("symbol") or ""
            if not node_id or not label:
                return None
            category = node.get("category", "")
            concept = self._create_concept(
                node_id, label, _CATEGORY_TO_TYPE.get(category, ConceptType.UNKNOWN)
            )

            synonyms: list[str] = []
            synonyms.extend(v for v in (node.get("symbol"), node.get("full_name")) if v)
            for key in ("synonym", *_SYNONYM_FIELDS):
                synonyms.extend(node.get(key) or [])
            seen = {label}
            if concept.synonyms is not None:
                for synonym in synonyms:
                    if synonym and synonym not in seen:
                        seen.add(synonym)
                        concept.synonyms.append(synonym)

            description = node.get("description")
            if description and concept.definitions is not None:
                concept.definitions.append(description[:1000])

            if concept.categories is not None:
                if category:
                    concept.categories.append(category)
                if node.get("in_taxon_label"):
                    concept.categories.append(f"taxon:{node['in_taxon_label']}")
                concept.categories.extend(node.get("subsets") or [])
            if concept.semantic_types is not None and category:
                concept.semantic_types.append(category.split(":", 1)[-1])

            for xref in node.get("xref") or []:
                add_known_identifier(concept, str(xref))
            for mapping in node.get("mappings") or []:
                add_known_identifier(concept, str(mapping.get("id", "")), url=mapping.get("url"))

            if detailed:
                hierarchy = node.get("node_hierarchy") or {}
                if concept.parents is not None:
                    concept.parents.extend(c["id"] for c in hierarchy.get("super_classes") or [])
                if concept.children is not None:
                    concept.children.extend(c["id"] for c in hierarchy.get("sub_classes") or [])

            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.MONARCH] = self._compact(node)
            return concept
        except Exception as e:
            logger.error(f"Error converting Monarch node: {e}")
            return None

    @staticmethod
    def _compact(node: dict[str, Any]) -> dict[str, Any]:
        """Drop the bulky closure lists and highlighting from a node before storing it."""
        skip = re.compile(r"(_closure(_label)?|highlighting|node_hierarchy|external_links)$")
        compact = {k: v for k, v in node.items() if v is not None and not skip.search(k)}
        if node.get("association_counts"):
            compact["association_counts"] = {
                a["category"].split(":", 1)[-1]: a.get("count")
                for a in node["association_counts"]
                if a.get("count")
            }
        return compact
