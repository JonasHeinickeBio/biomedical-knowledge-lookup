"""
OLS (Ontology Lookup Service) Adapter

Integrates with EMBL-EBI Ontology Lookup Service for concept lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class OLSAdapter(KnowledgeSourceAdapter):
    """Adapter for EMBL-EBI Ontology Lookup Service."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/ols4/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OLS

    def is_available(self) -> bool:
        return True  # OLS is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search OLS for concepts."""
        try:
            url = f"{self.base_url}/search"
            params = {"q": query, "rows": min(limit, 100), "format": "json"}

            data = await self._make_request(url, params)

            concepts = []
            if "response" in data and "docs" in data["response"]:
                for doc in data["response"]["docs"][:limit]:
                    concept = self._convert_ols_result_to_concept(doc)
                    if concept:
                        concepts.append(concept)

            logger.info(f"OLS search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"OLS search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed concept information from OLS."""
        try:
            # If it's an IRI, use the terms endpoint
            if "http" in concept_id:
                url = f"{self.base_url}/terms"
                params = {"iri": concept_id}
                data = await self._make_request(url, params)

                if (
                    "_embedded" in data
                    and "terms" in data["_embedded"]
                    and len(data["_embedded"]["terms"]) > 0
                ):
                    # Get the first match
                    term_data = data["_embedded"]["terms"][0]
                    concept = self._convert_ols_concept_to_unified(term_data)
                    if concept is not None:
                        links = term_data.get("_links", {}) or {}
                        child_labels = [
                            label
                            for _iri, label in await self._fetch_linked_terms(
                                (links.get("children") or {}).get("href")
                            )
                            if label
                        ]
                        parent_labels = [
                            label
                            for _iri, label in await self._fetch_linked_terms(
                                (links.get("parents") or {}).get("href")
                            )
                            if label
                        ]
                        if child_labels:
                            concept.children = child_labels
                        if parent_labels:
                            concept.parents = parent_labels
                    return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get OLS concept details for '{concept_id}': {e}")
            return None

    async def _fetch_linked_terms(
        self, href: str | None, limit: int = 20
    ) -> list[tuple[str, str]]:
        """Follow an OLS ``_links`` hierarchy href (children/parents/...) and
        return ``(iri, label)`` pairs. Any failure degrades to ``[]``."""
        if not href:
            return []
        try:
            base = href.split("?", 1)[0]
            data = await self._make_request(base, {"size": max(1, min(limit, 200)), "page": 0})
        except Exception as e:
            logger.debug(f"OLS linked-terms request failed for {href}: {e}")
            return []
        terms = (data.get("_embedded") or {}).get("terms") or []
        return [(t.get("iri", ""), t.get("label", "")) for t in terms if t.get("iri")]

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return direct hierarchy neighbours of an OLS term as relationship
        edges.

        Resolves the term's ``_links.children``/``_links.parents`` (the API
        supplies ready-to-follow hrefs, so no endpoint guessing) and returns
        them in the adapter relationship shape. Narrower terms become
        ``has_narrower`` (a class->member edge for class terms), broader terms
        ``has_broader``. Non-IRI ids and any failure return ``[]``.
        """
        if not concept_id or "http" not in concept_id:
            return []
        try:
            data = await self._make_request(f"{self.base_url}/terms", {"iri": concept_id})
            terms = (data.get("_embedded") or {}).get("terms") or []
            if not terms:
                return []
            links = terms[0].get("_links", {}) or {}
        except Exception as e:
            logger.error(f"OLS get_relationships failed for '{concept_id}': {e}")
            return []

        rels: list[dict[str, Any]] = []
        for key, label in (("children", "has_narrower"), ("parents", "has_broader")):
            href = (links.get(key) or {}).get("href")
            for iri, name in await self._fetch_linked_terms(href, limit=limit):
                if not name:
                    continue
                rels.append(
                    {
                        "relation_label": label,
                        "related_id": iri,
                        "related_name": name,
                        "source": "OLS",
                    }
                )
                if len(rels) >= limit:
                    return rels
        return rels

    def _convert_ols_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert OLS search result to unified concept."""
        try:
            concept_id = result.get("iri", "")
            label = result.get("label", "")

            if not concept_id or not label:
                return None

            # Determine concept type from ontology
            ontology = result.get("ontology_name", "")
            concept_type = self._determine_concept_type_from_ontology(ontology)

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=concept_type
            )

            # Add OLS identifier
            concept.add_identifier(self.get_source(), concept_id, label, concept_id)

            # Add synonyms
            if "synonym" in result:
                synonyms = result["synonym"]
                if isinstance(synonyms, list):
                    if concept.synonyms is not None:
                        concept.synonyms.extend(synonyms)
                else:
                    if concept.synonyms is not None:
                        concept.synonyms.append(synonyms)

            # Add description
            if "description" in result:
                descriptions = result["description"]
                if isinstance(descriptions, list):
                    if concept.definitions is not None:
                        concept.definitions.extend(descriptions)
                else:
                    if concept.definitions is not None:
                        concept.definitions.append(descriptions)

            # Add ontology information
            if "ontology_name" in result:
                if concept.categories is not None:
                    concept.categories.append(result["ontology_name"])

            # Add short form (often more readable ID)
            if "short_form" in result:
                concept.add_identifier(self.get_source(), result["short_form"], label)

            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
                concept.source_data[self.get_source()] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting OLS result: {e}")
            return None

    def _convert_ols_concept_to_unified(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert detailed OLS concept to unified concept."""
        try:
            concept_id = data.get("iri", "")
            label = data.get("label", "")

            if not concept_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            # Add OLS identifier
            concept.add_identifier(self.get_source(), concept_id, label, concept_id)

            # Add synonyms
            if "synonyms" in data:
                if concept.synonyms is not None:
                    concept.synonyms.extend(data["synonyms"])

            # Add definitions
            if "description" in data:
                descriptions = data["description"]
                if isinstance(descriptions, list):
                    if concept.definitions is not None:
                        concept.definitions.extend(descriptions)
                else:
                    if concept.definitions is not None:
                        concept.definitions.append(descriptions)

            # Extract cross-references
            if "annotation" in data:
                xrefs = data["annotation"].get("database_cross_reference", [])
                if isinstance(xrefs, str):
                    xrefs = [xrefs]
                for xref in xrefs:
                    if concept.categories is not None:
                        concept.categories.append(f"Xref: {xref}")

            if "obo_xref" in data:
                xrefs = data["obo_xref"]
                if isinstance(xrefs, list):
                    for xref in xrefs:
                        db = xref.get("database", "")
                        id = xref.get("id", "")
                        if db and id:
                            if concept.categories is not None:
                                concept.categories.append(f"Xref: {db}:{id}")

            # Add hierarchical relationships from _links if available
            if "_links" in data:
                links = data["_links"]
                if "parents" in links:
                    # Would need to make additional requests to get parent IRIs
                    pass
                if "children" in links:
                    # Would need to make additional requests to get children IRIs
                    pass

            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[self.get_source()] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting OLS concept: {e}")
            return None

    def _determine_concept_type_from_ontology(self, ontology: str) -> ConceptType:
        """Determine concept type from OLS ontology name."""
        ontology_lower = ontology.lower()

        # Map OLS ontologies to concept types. Order matters: an ontology
        # name must appear in exactly one branch, or an earlier branch
        # silently shadows a later one (chebi -> DRUG used to shadow the
        # chebi -> CHEMICAL branch below it, so CentralKnowledgeLookup's
        # concept_types=[ConceptType.CHEMICAL] filter never matched any OLS
        # result). ChEBI ("Chemical Entities of Biological Interest") is the
        # chemical-structure ontology; DrugBank is the drug-specific one —
        # they're related but not interchangeable.
        if ontology_lower in ["doid", "mondo", "ordo"]:
            return ConceptType.DISEASE
        elif ontology_lower == "drugbank":
            return ConceptType.DRUG
        elif ontology_lower == "chebi":
            return ConceptType.CHEMICAL
        elif ontology_lower in ["go", "so", "pr"]:
            return ConceptType.GENE
        elif ontology_lower in ["uberon", "fma", "ma"]:
            # ANATOMICAL_ENTITY, not the separate (differently-scoped)
            # ConceptType.ANATOMY member — CentralKnowledgeLookup's
            # concept_types filter compares by exact enum value, so the
            # wrong member here means zero matches, not a near miss.
            return ConceptType.ANATOMICAL_ENTITY
        elif ontology_lower in ["hp", "mp", "zp"]:
            return ConceptType.PHENOTYPE
        elif ontology_lower in ["ncbitaxon"]:
            return ConceptType.ORGANISM

        return ConceptType.UNKNOWN
