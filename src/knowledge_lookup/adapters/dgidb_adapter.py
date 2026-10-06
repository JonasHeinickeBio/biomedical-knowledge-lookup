"""
DGIdb adapter (Drug-Gene Interaction database, v5 GraphQL API).

DGIdb aggregates drug-gene interactions from 45 sources (2026-10: PharmGKB, CIViC, OncoKB,
ChEMBL, GuideToPharmacology, DTC, TTD, DrugBank, ...). The v5 service is a single keyless
GraphQL endpoint, ``POST https://dgidb.org/api/graphql`` with ``{"query": ..., "variables": ...}``
(documentation: https://dgidb.org/api, schema browsable via introspection).

Licence: DGIdb itself is open, but every source keeps its own licence, exposed per source in
the API (``sources { sourceDbName license licenseLink }``). Among the 45 are sources marked
"restrictive / non-commercial" (OncoKB, COSMIC, DrugBank, CancerCommons, MyCancerGenome) and
one "Unknown"; check them (and cite DGIdb) before commercial use or redistribution. Edges list
their ``sources`` so results can be filtered.

Verified behaviour that shapes this adapter:

* ``genes(names: [...])`` matches gene symbols *exactly* (case-insensitive); ``drugs(names:
  [...])`` is a *substring* match (``aspirin`` also returns ``ASPIRIN-TRIGGERED RESOLVIN D1``),
  so results are ranked exact-first.
* ``genes(conceptIds: [...])`` / ``drugs(conceptIds: [...])`` only know each record's *primary*
  concept id (``hgnc:1100``, ``rxcui:1191``, ``chembl:CHEMBL1703``). A drug's other ids
  (``chembl:CHEMBL25`` for aspirin) are aliases and do not resolve.
* The top-level ``interactions(geneConceptIds: ...)`` filter returned nothing in testing, so
  interactions are read nested under the gene/drug node and capped client-side.
* Interactions carry no inherent order; they are ranked here by ``interactionScore``.
* GraphQL errors arrive with HTTP 200 and an ``errors`` array; those are treated as failures.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

DGIDB_GRAPHQL_URL = "https://dgidb.org/api/graphql"
MAX_PMIDS = 25  # per relationship; some interactions cite hundreds of papers

_GENE_FIELDS = "name conceptId longName geneAliases { alias }"
_DRUG_FIELDS = "name conceptId approved drugAliases { alias }"
_GENE_DETAIL_FIELDS = _GENE_FIELDS + " geneCategories { name } interactions { id }"
_DRUG_DETAIL_FIELDS = _DRUG_FIELDS + " drugAttributes { name value } interactions { id }"
_INTERACTION_FIELDS = (
    "interactionScore evidenceScore interactionTypes { type directionality } "
    "sources { sourceDbName } publications { pmid }"
)
_GENE_EDGE_FIELDS = (
    "name conceptId longName interactions { drug { name conceptId approved } "
    + _INTERACTION_FIELDS
    + " }"
)
_DRUG_EDGE_FIELDS = (
    "name conceptId approved interactions { gene { name conceptId longName } "
    + _INTERACTION_FIELDS
    + " }"
)

# DGIdb alias/concept-id prefix (lower case) -> KnowledgeSource-style label used in mappings
_XREF_SOURCES = {
    "hgnc": "HGNC",
    "ensembl": "ENSEMBL",
    "ncbigene": "NCBI",
    "ncbi.gene": "NCBI",
    "uniprot": "UNIPROT",
    "omim": "OMIM",
    "orphanet": "ORPHANET",
    "chembl": "CHEMBL",
    "drugbank": "DRUGBANK",
    "pubchem.substance": "PUBCHEM",
    "pubchem.compound": "PUBCHEM",
    "rxcui": "RXNORM",
    "ncit": "NCIT",
    "wikidata": "WIKIDATA",
    "iuphar.ligand": "GUIDETOPHARMACOLOGY",
    "pharmgkb.gene": "PHARMGKB",
    "pharmgkb.drug": "PHARMGKB",
    "ttd.drug": "TTD",
    "civic.gid": "CIVIC",
    "civic.tid": "CIVIC",
    "cosmic": "COSMIC",
}


def _normalize_concept_id(concept_id: str) -> str | None:
    """Lower-case the prefix of ``HGNC:1100`` / ``RXCUI:1191`` (DGIdb ids are ``prefix:local``).

    Returns ``None`` for input without a prefix (bare symbol or drug name).
    """
    cleaned = (concept_id or "").strip()
    if cleaned.upper().startswith("DGIDB:"):
        cleaned = cleaned.split(":", 1)[1]
    prefix, sep, local = cleaned.partition(":")
    if not sep or not prefix or not local:
        return None
    return f"{prefix.lower()}:{local}"


class DGIdbAdapter(KnowledgeSourceAdapter):
    """Adapter for DGIdb v5 (keyless GraphQL): genes, drugs and their interactions.

    Source licences vary (some are non-commercial); see the module docstring.
    """

    def __init__(self, config):
        super().__init__(config)
        self.base_url = DGIDB_GRAPHQL_URL

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DGIDB

    def is_available(self) -> bool:
        return True  # public, keyless

    # ------------------------------------------------------------------
    # GraphQL plumbing
    # ------------------------------------------------------------------

    async def _gql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL document and return ``data``; raises on transport or GraphQL errors."""
        payload = await self._make_request(
            self.base_url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json_data={"query": query, "variables": variables},
        )
        if not isinstance(payload, dict):
            raise ValueError("unexpected DGIdb response")
        errors = payload.get("errors")
        if errors:
            message = errors[0].get("message") if isinstance(errors[0], dict) else errors[0]
            raise ValueError(f"DGIdb GraphQL error: {message}")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _nodes(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
        block = data.get(key) or {}
        return [n for n in (block.get("nodes") or []) if isinstance(n, dict)]

    async def _find(
        self,
        ident: str,
        gene_fields: str,
        drug_fields: str,
        *,
        many: bool = False,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Resolve ``ident`` to ``(kind, node)`` pairs (``kind`` is ``gene`` or ``drug``).

        A ``prefix:local`` id is looked up by ``conceptIds`` (``hgnc:`` -> genes, anything else
        -> drugs, which is how DGIdb prefixes its records). Anything else is a name: genes
        are tried first (exact symbol), then drugs. With ``many=False`` only exact name matches
        are kept; search passes ``many=True`` to keep DGIdb's substring matches too.
        """
        normalized = _normalize_concept_id(ident)
        name = (ident or "").strip()
        if normalized:
            kinds = ["gene"] if normalized.startswith("hgnc:") else ["drug"]
            arg, value = "conceptIds", normalized
        elif name:
            kinds, arg, value = ["gene", "drug"], "names", name
        else:
            return []
        for kind in kinds:
            field, fields = ("genes", gene_fields) if kind == "gene" else ("drugs", drug_fields)
            query = f"query($v: [String!]) {{ {field}({arg}: $v) {{ nodes {{ {fields} }} }} }}"
            nodes = self._nodes(await self._gql(query, {"v": [value]}), field)
            if arg == "names":
                nodes = self._rank(nodes, name)
                if not many:
                    nodes = [n for n in nodes if (n.get("name") or "").lower() == name.lower()]
            if nodes:
                return [(kind, n) for n in nodes]
        return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _split_aliases(item: dict[str, Any], key: str) -> tuple[list[str], list[tuple[str, str]]]:
        """Split aliases into free-text synonyms and ``(prefix, local)`` cross references.

        Aliases that look like CURIEs but are not useful cross references (``PUBMED:``,
        ``CCDS:`` ...) are dropped rather than listed as synonyms.
        """
        synonyms: list[str] = []
        xrefs: list[tuple[str, str]] = []
        for entry in item.get(key) or []:
            alias = (entry or {}).get("alias") or ""
            prefix, sep, local = alias.partition(":")
            if sep and " " not in prefix and "," not in prefix:
                if prefix.lower() in _XREF_SOURCES and local:
                    xrefs.append((prefix.lower(), local))
            elif alias and alias not in synonyms:
                synonyms.append(alias)
        return synonyms, xrefs

    def _gene_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        concept_id, name = item.get("conceptId"), item.get("name")
        if not concept_id or not name:
            return None
        concept = self._create_concept(concept_id, name, ConceptType.GENE)
        synonyms, _ = self._split_aliases(item, "geneAliases")
        if concept.synonyms is not None:
            concept.synonyms.extend(s for s in synonyms[:50] if s != name)
        long_name = item.get("longName")
        if long_name and concept.definitions is not None:
            concept.definitions.append(long_name)
        for category in item.get("geneCategories") or []:
            if category.get("name") and concept.categories is not None:
                concept.categories.append(category["name"])
        self._add_count(concept, item, "gene")
        concept.confidence_score = 0.85
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.DGIDB] = item
        return concept

    def _drug_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        concept_id, name = item.get("conceptId"), item.get("name")
        if not concept_id or not name:
            return None
        concept = self._create_concept(concept_id, name, ConceptType.CHEMICAL)
        synonyms, xrefs = self._split_aliases(item, "drugAliases")
        if concept.synonyms is not None:
            concept.synonyms.extend(s for s in synonyms[:50] if s != name)
        for prefix, local in xrefs:
            if prefix == "chembl":
                concept.add_identifier(KnowledgeSource.CHEMBL, local, name)
            elif prefix == "drugbank":
                concept.add_identifier(KnowledgeSource.DRUGBANK, local, name)
        if item.get("approved") and concept.categories is not None:
            concept.categories.append("approved")
        for attr in item.get("drugAttributes") or []:
            value = attr.get("value")
            if not value:
                continue
            if attr.get("name") == "Indication" and concept.definitions is not None:
                concept.definitions.append(f"Indication: {value}")
            elif attr.get("name") == "Drug Class" and concept.categories is not None:
                if value not in concept.categories:
                    concept.categories.append(value)
        self._add_count(concept, item, "drug")
        concept.confidence_score = 0.85
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.DGIDB] = item
        return concept

    @staticmethod
    def _add_count(concept: UnifiedConcept, item: dict[str, Any], kind: str) -> None:
        interactions = item.get("interactions")
        if isinstance(interactions, list) and concept.definitions is not None:
            partner = "drugs" if kind == "gene" else "genes"
            concept.definitions.append(f"{len(interactions)} DGIdb interactions with {partner}")

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    @staticmethod
    def _rank(nodes: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """Exact name first, then shorter (closer) names."""
        lowered = query.lower()
        return sorted(
            nodes,
            key=lambda n: ((n.get("name") or "").lower() != lowered, len(n.get("name") or "")),
        )

    def _to_concept(self, kind: str, node: dict[str, Any]) -> UnifiedConcept | None:
        return self._gene_to_concept(node) if kind == "gene" else self._drug_to_concept(node)

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search genes first (exact symbol), then drugs (substring on name).

        A gene hit answers the query; drug name matches are only returned when no gene
        matches, so ``BRCA1`` yields the gene and ``aspirin`` the drugs.
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            if _normalize_concept_id(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            found = await self._find(query, _GENE_FIELDS, _DRUG_FIELDS, many=True)
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for kind, node in found:
                concept = self._to_concept(kind, node)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
            logger.info(f"DGIdb search for '{query}' returned {len(concepts[:limit])} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"DGIdb search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for a gene (``hgnc:1100`` or symbol) or drug (``rxcui:1191`` or exact name)."""
        try:
            found = await self._find(concept_id, _GENE_DETAIL_FIELDS, _DRUG_DETAIL_FIELDS)
            return self._to_concept(*found[0]) if found else None
        except Exception as e:
            logger.warning(f"DGIdb get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Gene <-> drug interactions, strongest ``interactionScore`` first.

        ``relation_label`` is the DGIdb interaction type (``inhibitor``, ``agonist``,
        ``binder``, ... lower-cased, spaces -> ``_``), ``interacts_with`` when the sources give
        none; one edge per (partner, type). Extra keys: ``score``, ``evidence_score``,
        ``directionality``, ``interaction_types``, ``sources``, ``pmids`` (<= 25),
        ``approved`` (drug partners), ``related_type``. Degrades to ``[]``.
        """
        if limit <= 0:
            return []
        try:
            found = await self._find(concept_id, _GENE_EDGE_FIELDS, _DRUG_EDGE_FIELDS)
            return self._edges(*found[0], limit) if found else []
        except Exception as e:
            logger.warning(f"DGIdb get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _edges(kind: str, node: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        partner_key = "drug" if kind == "gene" else "gene"
        interactions = [i for i in node.get("interactions") or [] if isinstance(i, dict)]
        interactions.sort(key=lambda i: i.get("interactionScore") or 0.0, reverse=True)
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for inter in interactions:
            partner = inter.get(partner_key) or {}
            partner_id, partner_name = partner.get("conceptId"), partner.get("name")
            if not partner_id or not partner_name:
                continue
            types = [t for t in inter.get("interactionTypes") or [] if t.get("type")]
            labelled = types or [{"type": "interacts_with", "directionality": None}]
            pmids = [p["pmid"] for p in inter.get("publications") or [] if p.get("pmid")]
            for itype in labelled:
                label = str(itype["type"]).strip().lower().replace(" ", "_").replace("-", "_")
                if (partner_id, label) in seen:
                    continue
                seen.add((partner_id, label))
                edge: dict[str, Any] = {
                    "relation_label": label,
                    "related_id": partner_id,
                    "related_name": partner_name,
                    "source": "DGIDB",
                    "related_type": partner_key,
                    "score": inter.get("interactionScore"),
                    "evidence_score": inter.get("evidenceScore"),
                    "directionality": itype.get("directionality"),
                    "interaction_types": [t["type"] for t in types],
                    "sources": [s["sourceDbName"] for s in inter.get("sources") or []],
                    "pmids": pmids[:MAX_PMIDS],
                }
                if partner_key == "drug":
                    edge["approved"] = partner.get("approved")
                edges.append(edge)
                if len(edges) >= limit:
                    return edges
        return edges

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Identifier forms DGIdb lists for a gene/drug.

        Uses the record's primary concept id (``hgnc:1100``, ``rxcui:1191``) and its
        ``ENSEMBL:``, ``NCBIGENE:``, ``UNIPROT:``, ``CHEMBL:``, ``DRUGBANK:`` ... aliases.
        """
        try:
            found = await self._find(concept_id, _GENE_FIELDS, _DRUG_FIELDS)
            if not found:
                return []
            kind, node = found[0]
            from_id = node.get("conceptId") or concept_id
            prefix, _, local = str(from_id).partition(":")
            xrefs = [(prefix.lower(), local)] if local else []
            alias_key = "geneAliases" if kind == "gene" else "drugAliases"
            xrefs.extend(self._split_aliases(node, alias_key)[1])
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for pfx, value in xrefs:
                to_source = _XREF_SOURCES.get(pfx)
                if not to_source or (to_source, value) in seen:
                    continue
                seen.add((to_source, value))
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": f"{pfx.upper()}:{value}",
                        "fromSource": "DGIDB",
                        "toSource": to_source,
                        "mappingType": "xref",
                        "confidence": 0.9,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"DGIdb get_mappings failed for '{concept_id}': {e}")
            return []
