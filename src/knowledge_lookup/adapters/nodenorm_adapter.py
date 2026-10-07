"""
NCATS Node Normalizer and Name Resolver Knowledge Source Adapter

Adapter for two companion NCATS Translator services (both keyless, JSON, ~0.6 s):

- **Node Normalizer** (https://nodenormalization-sri.renci.org): maps any CURIE to its
  "clique" of equivalent identifiers, picks a preferred identifier and label, and returns the
  Biolink types and an information-content score. ``GET /get_normalized_nodes?curie=...`` for
  one or a few ids, ``POST /get_normalized_nodes`` with ``{"curies": [...]}`` for batches.
  Prefixes are matched case-insensitively (``mesh:D015673`` and ``hgnc:1100`` work), which
  is why this is the cheap fix for low identifier-linking rates caused by prefix-case and
  CURIE-style differences between sources.
- **Name Resolver** (https://name-resolution-sri.renci.org): free-text -> CURIE.
  ``GET /lookup?string=...&limit=...`` (also ``/bulk-lookup`` via POST).

Quirks worth knowing:

- With ``conflate=true`` (the default here) genes and their proteins are merged and
  drugs/chemicals are merged, so ``HGNC:1100`` normalizes to ``NCBIGene:672``: the *preferred*
  id may use a different prefix than the one queried.
- Unknown CURIEs come back as ``null`` for that key rather than an error.
- The preferred label comes from the preferred identifier and can be odd (MONDO's
  "myalgic encephalomeyelitis/chronic fatigue syndrome" spelling).
- Name Resolver scores are unbounded Solr scores (hundreds to thousands); they are exposed
  relative to the best hit as ``confidence_score``.

No registration or API key is needed; the services are run by the Translator project on a
best-effort basis, so expect occasional slowness.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._pheno_common import CANONICAL_PREFIXES, add_known_identifier, split_curie

logger = logging.getLogger(__name__)

_NODENORM_URL = "https://nodenormalization-sri.renci.org"
_NAMERES_URL = "https://name-resolution-sri.renci.org"

# Maximum CURIEs per POST to get_normalized_nodes, to keep requests small and quick.
_BATCH_SIZE = 100
# Cap on synonyms copied onto a concept; Name Resolver returns up to ~100 per clique.
_MAX_SYNONYMS = 30

# Biolink type (local name) -> ConceptType. Both services list a clique's types from the most
# specific to the most general, so the first type found here wins.
_BIOLINK_TO_CONCEPT_TYPE: dict[str, ConceptType] = {
    "Disease": ConceptType.DISEASE,
    "PhenotypicFeature": ConceptType.PHENOTYPE,
    "Gene": ConceptType.GENE,
    "Protein": ConceptType.PROTEIN,
    "Polypeptide": ConceptType.PROTEIN,
    "Pathway": ConceptType.PATHWAY,
    "Drug": ConceptType.DRUG,
    "SmallMolecule": ConceptType.CHEMICAL,
    "MolecularMixture": ConceptType.CHEMICAL,
    "ChemicalEntity": ConceptType.CHEMICAL,
    "BiologicalProcess": ConceptType.BIOLOGICAL_PROCESS,
    "MolecularActivity": ConceptType.MOLECULAR_FUNCTION,
    "CellularComponent": ConceptType.CELLULAR_COMPONENT,
    "Cell": ConceptType.CELL_TYPE,
    "AnatomicalEntity": ConceptType.ANATOMICAL_ENTITY,
    "OrganismTaxon": ConceptType.ORGANISM,
    "Procedure": ConceptType.PROCEDURE,
    "SequenceVariant": ConceptType.MOLECULAR_ENTITY,
    "GeneOrGeneProduct": ConceptType.GENE,
    "DiseaseOrPhenotypicFeature": ConceptType.DISEASE,
}


def _concept_type(types: list[str]) -> ConceptType:
    for biolink_type in types:
        mapped = _BIOLINK_TO_CONCEPT_TYPE.get(biolink_type.split(":", 1)[-1])
        if mapped is not None:
            return mapped
    return ConceptType.UNKNOWN


def canonical_curie(identifier: str) -> str | None:
    """Return ``identifier`` as ``Prefix:local`` with the canonical prefix case, or ``None``.

    ``hgnc:1100`` -> ``HGNC:1100``, ``ncbigene:672`` -> ``NCBIGene:672``. Prefixes this
    package does not know are passed through unchanged (the services are case-insensitive).
    """
    parts = split_curie(identifier or "")
    if parts is None:
        return None
    prefix, local = parts
    return f"{CANONICAL_PREFIXES.get(prefix.lower(), prefix)}:{local}"


class NodeNormAdapter(KnowledgeSourceAdapter):
    """Adapter for the NCATS Translator Node Normalizer and Name Resolver."""

    def __init__(self, config):
        super().__init__(config)
        self.nodenorm_url = _NODENORM_URL
        self.nameres_url = _NAMERES_URL
        # Merge gene/protein and drug/chemical cliques (the services' own default).
        self.conflate = True

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.NODENORM

    def is_available(self) -> bool:
        return True  # public, keyless services

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten_node(node: dict[str, Any]) -> dict[str, Any]:
        """Flatten a ``get_normalized_nodes`` entry into a compact, stable record."""
        preferred = node.get("id") or {}
        types = list(node.get("type") or [])
        record: dict[str, Any] = {
            "id": preferred.get("identifier"),
            "label": preferred.get("label"),
            "type": types[0] if types else None,
            "types": types,
            "equivalent_identifiers": [
                {k: v for k, v in eq.items() if k in ("identifier", "label") and v}
                for eq in node.get("equivalent_identifiers") or []
            ],
            "information_content": node.get("information_content"),
        }
        descriptions = list(node.get("descriptions") or [])
        if not descriptions and preferred.get("description"):
            descriptions = [preferred["description"]]
        if descriptions:
            record["descriptions"] = descriptions
        if node.get("taxa"):
            record["taxa"] = list(node["taxa"])
        return record

    async def normalize_curies(
        self, curies: list[str], description: bool = False
    ) -> dict[str, dict[str, Any] | None]:
        """Normalize many CURIEs at once (the cheap way to link identifiers across sources).

        Returns ``{input curie: record or None}`` with one entry per distinct input exactly as
        passed in. ``None`` means the id is unknown to Node Normalizer, is not a CURIE, or its
        batch failed (the failure is logged). A record has ``id`` and ``label`` (preferred),
        ``type`` (most specific Biolink type), ``types``, ``equivalent_identifiers``
        (``[{"identifier", "label"}]``), ``information_content`` and, with
        ``description=True``, ``descriptions``. Prefix case is irrelevant; requests are sent
        in batches of 100 as POSTs.
        """
        results: dict[str, dict[str, Any] | None] = {}
        by_canonical: dict[str, list[str]] = {}
        for original in dict.fromkeys(c for c in curies if isinstance(c, str)):
            canonical = canonical_curie(original.strip())
            results[original] = None
            if canonical is not None:
                by_canonical.setdefault(canonical, []).append(original)

        wanted = list(by_canonical)
        for start in range(0, len(wanted), _BATCH_SIZE):
            batch = wanted[start : start + _BATCH_SIZE]
            try:
                payload = {"curies": batch, "conflate": self.conflate, "description": description}
                data = await self._make_request(
                    f"{self.nodenorm_url}/get_normalized_nodes", json_data=payload
                )
            except Exception as e:
                logger.warning(f"NodeNorm normalize_curies batch failed: {e}")
                continue
            if not isinstance(data, dict):
                continue
            for canonical in batch:
                node = data.get(canonical)
                if isinstance(node, dict) and node.get("id"):
                    record = self._flatten_node(node)
                    for original in by_canonical[canonical]:
                        results[original] = record
        return results

    async def _normalize_one(self, concept_id: str, description: bool = False) -> dict | None:
        canonical = canonical_curie((concept_id or "").strip())
        if canonical is None:
            return None
        data = await self._make_request(
            f"{self.nodenorm_url}/get_normalized_nodes",
            {
                "curie": canonical,
                "conflate": str(self.conflate).lower(),
                "description": str(description).lower(),
            },
        )
        node = data.get(canonical) if isinstance(data, dict) else None
        return self._flatten_node(node) if isinstance(node, dict) and node.get("id") else None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Normalize one CURIE: preferred id/label, Biolink types, equivalent identifiers and
        information content. The concept's ``primary_id`` is the *preferred* identifier, which
        may carry a different prefix than the one queried (see module docstring)."""
        try:
            record = await self._normalize_one(concept_id, description=True)
            if record is None:
                return None
            preferred = record["id"]
            label = record.get("label") or preferred
            concept = self._create_concept(preferred, label, _concept_type(record["types"]))

            if concept.semantic_types is not None:
                concept.semantic_types.extend(t.split(":", 1)[-1] for t in record["types"])
            if concept.definitions is not None:
                for text in dict.fromkeys(record.get("descriptions", [])):
                    concept.definitions.append(text[:500])
                    if len(concept.definitions) >= 3:
                        break
            if concept.synonyms is not None:
                for eq in record["equivalent_identifiers"]:
                    name = eq.get("label")
                    if name and name != label and name not in concept.synonyms:
                        concept.synonyms.append(name)
            for eq in record["equivalent_identifiers"]:
                add_known_identifier(concept, eq["identifier"], eq.get("label"))

            concept.confidence_score = 1.0
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.NODENORM] = record
            return concept
        except Exception as e:
            logger.error(f"NodeNorm get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the clique's equivalent identifiers as ``mappingType == "equivalent"``.

        ``fromId`` is the queried CURIE (canonical prefix case), ``toSource`` the prefix of
        the equivalent id and ``toLabel`` its label when the clique has one.
        """
        try:
            record = await self._normalize_one(concept_id)
            if record is None:
                return []
            from_id = canonical_curie(concept_id.strip()) or concept_id
            mappings: list[dict[str, Any]] = []
            for eq in record["equivalent_identifiers"]:
                target = eq.get("identifier")
                parts = split_curie(target or "")
                if parts is None or target.lower() == from_id.lower():
                    continue
                mapping: dict[str, Any] = {
                    "fromId": from_id,
                    "toId": target,
                    "fromSource": "NODENORM",
                    "toSource": parts[0],
                    "mappingType": "equivalent",
                    "confidence": 1.0,
                }
                if eq.get("label"):
                    mapping["toLabel"] = eq["label"]
                mappings.append(mapping)
            return mappings
        except Exception as e:
            logger.warning(f"NodeNorm get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Name Resolver
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Resolve a free-text name to CURIEs with the Name Resolver (``/lookup``).

        Each hit is one equivalence clique: ``primary_id`` is its preferred CURIE, ``synonyms``
        the clique's names (capped at 30), ``confidence_score`` the Solr score relative to the
        best hit. Use :meth:`normalize_curies` / :meth:`get_mappings` for the other ids.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            data = await self._make_request(
                f"{self.nameres_url}/lookup", {"string": text, "limit": min(limit, 100)}
            )
            hits: list[dict[str, Any]] = (
                [h for h in data if isinstance(h, dict)] if isinstance(data, list) else []
            )
            top = max((h.get("score") or 0.0 for h in hits), default=0.0)
            concepts: list[UnifiedConcept] = []
            for hit in hits[:limit]:
                concept = self._convert_hit(hit, top)
                if concept is not None:
                    concepts.append(concept)
            logger.info(f"NodeNorm search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"NodeNorm search failed for '{query}': {e}")
            return []

    async def bulk_lookup(
        self, names: list[str], limit: int = 5
    ) -> dict[str, list[dict[str, Any]]]:
        """Resolve many names in one Name Resolver ``/bulk-lookup`` POST.

        Returns ``{name: [{"curie", "label", "types", "score"}, ...]}`` (empty list for names
        without hits); ``{}`` if the request fails.
        """
        unique = list(dict.fromkeys(n.strip() for n in names if isinstance(n, str) and n.strip()))
        if not unique or limit <= 0:
            return {}
        try:
            data = await self._make_request(
                f"{self.nameres_url}/bulk-lookup",
                json_data={"strings": unique, "limit": min(limit, 100)},
            )
            if not isinstance(data, dict):
                return {}
            return {
                name: [
                    {
                        "curie": hit.get("curie"),
                        "label": hit.get("label"),
                        "types": hit.get("types") or [],
                        "score": hit.get("score"),
                    }
                    for hit in data.get(name) or []
                    if isinstance(hit, dict) and hit.get("curie")
                ]
                for name in unique
            }
        except Exception as e:
            logger.warning(f"NodeNorm bulk_lookup failed: {e}")
            return {}

    def _convert_hit(self, hit: dict[str, Any], top_score: float) -> UnifiedConcept | None:
        curie = hit.get("curie")
        if not curie:
            return None
        label = hit.get("label") or curie
        types = list(hit.get("types") or [])
        concept = self._create_concept(curie, label, _concept_type(types))
        if concept.synonyms is not None:
            for synonym in hit.get("synonyms") or []:
                if synonym and synonym != label and synonym not in concept.synonyms:
                    concept.synonyms.append(synonym)
                    if len(concept.synonyms) >= _MAX_SYNONYMS:
                        break
        if concept.semantic_types is not None:
            concept.semantic_types.extend(t.split(":", 1)[-1] for t in types)
        if concept.categories is not None:
            concept.categories.extend(f"taxon:{t}" for t in hit.get("taxa") or [])
        add_known_identifier(concept, curie, label)
        score = hit.get("score") or 0.0
        concept.confidence_score = round(score / top_score, 3) if top_score else 0.5
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.NODENORM] = {
                "curie": curie,
                "score": hit.get("score"),
                "clique_identifier_count": hit.get("clique_identifier_count"),
                "types": types,
            }
        return concept
