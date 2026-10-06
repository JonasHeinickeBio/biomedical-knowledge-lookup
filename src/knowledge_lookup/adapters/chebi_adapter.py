"""
ChEBI (Chemical Entities of Biological Interest) adapter.

Uses the EBI ChEBI *public REST API* (``https://www.ebi.ac.uk/chebi/backend/api/public/``),
the replacement for the retired SOAP/``ws`` services. No key is needed; ChEBI data is
CC BY 4.0. Live paths this adapter relies on (OpenAPI schema: ``.../chebi/backend/api/schema/``):

* ``es_search/?term=&size=`` - free-text search over names/synonyms/ids. Plain Elasticsearch
  relevance: a query that is only a *synonym* ranks low (``aspirin`` returns "aspirin
  trelamine" and aspirin-triggered resolvins before ``CHEBI:15365`` "acetylsalicylic acid"),
  so exact-name hits are hoisted client-side and the rest keep ES order.
* ``compound/{id}/`` - full record: definition, names by type, formula/mass, structure
  (SMILES/InChI/InChIKey), ontology relations, cross-database accessions and role
  classification. ``{id}`` may be ``15365`` or ``CHEBI:15365``.
* ``ontology/parents/{id}/`` and ``ontology/children/{id}/`` - the compact relation lists
  (``outgoing_relations`` / ``incoming_relations``) used for :meth:`get_relationships`.

Names contain HTML (``coenzyme Q<small><sub>10</sub></small>``); tags are stripped.
ChEBI stars: 3 = fully curated, 2 = preliminary (confidence 0.9 / 0.75).
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

CHEBI_API_BASE = "https://www.ebi.ac.uk/chebi/backend/api/public"
CHEBI_URL = "https://www.ebi.ac.uk/chebi/searchId.do?chebiId={}"

_ID_RE = re.compile(r"^(?:https?://.*/)?(?:CHEBI[:_])?(\d+)$", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SYNONYM_TYPES = ("INN", "SYNONYM", "IUPAC NAME", "BRAND NAME")
_MAX_SYNONYMS = 100
_MAX_ES_PAGE = 50
# Order in which outgoing relation types are listed (roles are the most useful for
# classification, so they come right after the "is a" parents).
_RELATION_PRIORITY = ("is a", "has role", "has functional parent")


def _clean(text: Any) -> str:
    """Strip the HTML markup ChEBI embeds in names and collapse whitespace."""
    return " ".join(_TAG_RE.sub("", str(text or "")).split())


def _snake(relation_type: str) -> str:
    return re.sub(r"\W+", "_", relation_type.strip()).strip("_").lower()


class ChEBIAdapter(KnowledgeSourceAdapter):
    """Adapter for the ChEBI public REST API."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = CHEBI_API_BASE

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CHEBI

    def is_available(self) -> bool:
        return True  # public API, no key required

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _numeric_id(concept_id: str) -> str | None:
        """``CHEBI:15365`` / ``chebi_15365`` / ``15365`` / OBO IRI -> ``"15365"``."""
        text = (concept_id or "").strip()
        match = _ID_RE.search(text)
        if not match:
            return None
        return str(int(match.group(1)))

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Free-text search (names, synonyms, ``CHEBI:`` ids) via ``es_search``."""
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            size = min(max(limit * 3, 15), _MAX_ES_PAGE)
            data = await self._make_request(
                f"{self.base_url}/es_search/", {"term": text, "size": size}
            )
            hits = (data or {}).get("results") or []
            needle = text.lower()
            # Stable sort: exact-name hits first, otherwise Elasticsearch order.
            hits = sorted(
                hits,
                key=lambda h: _clean((h.get("_source") or {}).get("name")).lower() != needle,
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for hit in hits:
                concept = self._hit_to_concept(hit.get("_source") or {})
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"ChEBI search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"ChEBI search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full ChEBI entity from ``compound/{id}/`` (one request)."""
        number = self._numeric_id(concept_id)
        if number is None:
            return None
        try:
            data = await self._make_request(f"{self.base_url}/compound/{number}/")
            if not isinstance(data, dict):
                return None
            return self._compound_to_concept(data)
        except Exception as e:
            logger.error(f"ChEBI get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Ontology edges of a ChEBI entity (``ontology/parents`` + ``ontology/children``).

        Outgoing edges keep ChEBI's relation type in snake_case (``is_a``, ``has_role``,
        ``has_functional_parent``, ``is_conjugate_acid_of``, ``has_part`` ...), ordered
        ``is_a`` -> ``has_role`` -> other. Edges pointing *at* this entity follow, as
        ``has_subclass`` (children via ``is_a``) or ``inverse_<relation>``. Each item has
        ``direction``; the total is capped by ``limit``.
        """
        number = self._numeric_id(concept_id)
        if number is None or limit <= 0:
            return []
        rels: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for endpoint, key, outgoing in (
            ("parents", "outgoing_relations", True),
            ("children", "incoming_relations", False),
        ):
            try:
                data = await self._make_request(f"{self.base_url}/ontology/{endpoint}/{number}/")
            except Exception as e:
                logger.error(
                    f"ChEBI get_relationships ({endpoint}) failed for '{concept_id}': {e}"
                )
                continue
            raw = ((data or {}).get("ontology_relations") or {}).get(key) or []
            if outgoing:
                raw = sorted(raw, key=self._relation_rank)
            for item in raw:
                relation_type = item.get("relation_type") or ""
                other_id = item.get("final_id") if outgoing else item.get("init_id")
                other_name = item.get("final_name") if outgoing else item.get("init_name")
                if not relation_type or other_id is None:
                    continue
                if outgoing:
                    label = _snake(relation_type)
                elif relation_type == "is a":
                    label = "has_subclass"
                else:
                    label = f"inverse_{_snake(relation_type)}"
                dedup = (label, str(other_id))
                if dedup in seen:
                    continue
                seen.add(dedup)
                rels.append(
                    {
                        "relation_label": label,
                        "related_id": f"CHEBI:{other_id}",
                        "related_name": _clean(other_name),
                        "source": "ChEBI",
                        "direction": "outgoing" if outgoing else "incoming",
                    }
                )
                if len(rels) >= limit:
                    return rels
        return rels

    @staticmethod
    def _relation_rank(item: dict[str, Any]) -> int:
        relation_type = item.get("relation_type") or ""
        if relation_type in _RELATION_PRIORITY:
            return _RELATION_PRIORITY.index(relation_type)
        return len(_RELATION_PRIORITY)

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-database accessions (DrugBank, KEGG, HMDB, CAS, DrugCentral, ...).

        Built from ``database_accessions`` of ``compound/{id}/``: manual cross-references,
        CAS numbers and registry numbers. Literature citations (PubMed) are not mappings and
        are skipped. PubChem CIDs only appear when ChEBI curates them for the entity.
        """
        number = self._numeric_id(concept_id)
        if number is None:
            return []
        try:
            data = await self._make_request(f"{self.base_url}/compound/{number}/")
        except Exception as e:
            logger.error(f"ChEBI get_mappings failed for '{concept_id}': {e}")
            return []
        if not isinstance(data, dict):
            return []
        from_id = data.get("chebi_accession") or f"CHEBI:{number}"
        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        accessions = data.get("database_accessions") or {}
        for kind in ("MANUAL_X_REF", "CAS", "REGISTRY_NUMBER"):
            for acc in accessions.get(kind) or []:
                number_text = str(acc.get("accession_number") or "").strip()
                if not number_text:
                    continue
                # CAS numbers are listed once per supplying database; the target is "CAS".
                database = "CAS" if kind == "CAS" else str(acc.get("source_name") or "").strip()
                if not database or (database, number_text) in seen:
                    continue
                seen.add((database, number_text))
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": number_text,
                        "fromSource": "ChEBI",
                        "toSource": database,
                        "mappingType": "xref",
                        "confidence": 0.9,
                    }
                )
        return mappings

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _confidence(stars: Any) -> float:
        return 0.9 if stars == 3 else 0.75

    def _hit_to_concept(self, src: dict[str, Any]) -> UnifiedConcept | None:
        accession, name = src.get("chebi_accession"), _clean(src.get("name"))
        if not accession or not name:
            return None
        concept = self._create_concept(accession, name, ConceptType.CHEMICAL)
        concept.confidence_score = self._confidence(src.get("stars"))
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                k: src.get(k)
                for k in ("stars", "formula", "mass", "smiles", "inchikey", "charge")
                if src.get(k) is not None
            }
        return concept

    def _compound_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        accession, name = data.get("chebi_accession"), _clean(data.get("name"))
        if not accession or not name:
            return None
        concept = self._create_concept(accession, name, ConceptType.CHEMICAL)
        concept.add_identifier(self.get_source(), accession, name, CHEBI_URL.format(accession))
        concept.confidence_score = self._confidence(data.get("stars"))

        definition = _clean(data.get("definition"))
        if definition and concept.definitions is not None:
            concept.definitions.append(definition)

        if concept.synonyms is not None:
            names = data.get("names") or {}
            for kind in _SYNONYM_TYPES:
                for entry in names.get(kind) or []:
                    value = _clean(entry.get("name"))
                    if value and value != name and value not in concept.synonyms:
                        concept.synonyms.append(value)
            del concept.synonyms[_MAX_SYNONYMS:]

        relations = data.get("ontology_relations") or {}
        parents = self._labels(relations.get("outgoing_relations"), "is a", "final_name")
        children = self._labels(relations.get("incoming_relations"), "is a", "init_name")
        concept.parents, concept.children = parents, children

        roles = [_clean(r.get("name")) for r in data.get("roles_classification") or []]
        roles = [r for r in roles if r]
        if concept.categories is not None:
            concept.categories.extend(f"role: {r}" for r in roles)
        if concept.semantic_types is not None:
            concept.semantic_types.append("chemical entity")

        structure = data.get("default_structure") or {}
        chemical = data.get("chemical_data") or {}
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "stars": data.get("stars"),
                "formula": chemical.get("formula"),
                "mass": chemical.get("mass"),
                "monoisotopic_mass": chemical.get("monoisotopic_mass"),
                "charge": chemical.get("charge"),
                "smiles": structure.get("smiles"),
                "inchi": structure.get("standard_inchi"),
                "inchikey": structure.get("standard_inchi_key"),
                "secondary_ids": data.get("secondary_ids") or [],
                "roles": roles,
                "modified_on": data.get("modified_on"),
            }
        return concept

    @staticmethod
    def _labels(items: Any, relation_type: str, name_key: str) -> list[str]:
        labels: list[str] = []
        for item in items or []:
            label = _clean(item.get(name_key))
            if item.get("relation_type") == relation_type and label and label not in labels:
                labels.append(label)
        return labels
