"""
Reactome Pathway Database Adapter

Integrates with Reactome Analysis Service for biological pathway lookup.
"""

import html
import logging
import re
from typing import Any

import aiohttp

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(text: Any) -> str:
    """Remove the HTML markup Reactome embeds in search hits (highlighting spans, <BR>)."""
    if not isinstance(text, str):
        return ""
    return html.unescape(_TAG_RE.sub(" ", text)).replace("  ", " ").strip()


# Reactome schema classes (search entry "type", details "schemaClass") -> ConceptType
_EVENT_TYPES: dict[str, ConceptType] = {
    "Pathway": ConceptType.PATHWAY,
    "TopLevelPathway": ConceptType.PATHWAY,
    "Reaction": ConceptType.BIOLOGICAL_PROCESS,
    "BlackBoxEvent": ConceptType.BIOLOGICAL_PROCESS,
    "Depolymerisation": ConceptType.BIOLOGICAL_PROCESS,
    "Polymerisation": ConceptType.BIOLOGICAL_PROCESS,
    "FailedReaction": ConceptType.BIOLOGICAL_PROCESS,
}


def _concept_type(schema_class: Any) -> ConceptType:
    """Map a Reactome schema class to a ConceptType (UNKNOWN when unmapped)."""
    return _EVENT_TYPES.get(schema_class, ConceptType.UNKNOWN)


class ReactomeAdapter(KnowledgeSourceAdapter):
    """Adapter for Reactome."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://reactome.org/ContentService"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.REACTOME

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Reactome for pathways."""
        try:
            url = f"{self.base_url}/search/query"
            params = {"query": query, "rows": min(limit, 100)}

            data = await self._make_request(url, params)

            concepts: list[UnifiedConcept] = []
            # The ContentService groups hits by type:
            # {"results": [{"typeName": "Pathway", "entries": [{"type": "Pathway", ...}]}]}
            for group in data.get("results", []) or []:
                for entry in group.get("entries", []) or []:
                    if len(concepts) >= limit:
                        break
                    # Only include pathways and reactions
                    if entry.get("type") in ["Pathway", "Reaction"]:
                        concept = self._convert_reactome_result_to_concept(entry)
                        if concept:
                            concepts.append(concept)

            logger.info(f"Reactome search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                # Reactome answers 404 when a query has no matches
                logger.info(f"Reactome search for '{query}' returned no matches")
                return []
            logger.error(f"Reactome search failed for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Reactome search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed pathway information from Reactome."""
        try:
            # concept_id should be Reactome ID (e.g., R-HSA-1640170)
            url = f"{self.base_url}/data/query/{concept_id}"
            data = await self._make_request(url)

            if data and "dbId" in data:
                concept = self._convert_reactome_details_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Reactome concept details for '{concept_id}': {e}")
            return None

    def _convert_reactome_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Reactome search result to unified concept."""
        try:
            st_id = result.get("stId", "")
            # Search hits wrap matched words in <span class="highlighting"> markup
            label = _strip_markup(result.get("name", ""))

            if not st_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=st_id,
                primary_label=label,
                concept_type=_concept_type(result.get("type")),
            )

            concept.add_identifier(
                KnowledgeSource.REACTOME,
                st_id,
                label,
                f"https://reactome.org/content/detail/{st_id}",
            )

            if "summation" in result:
                summation = _strip_markup(result["summation"])
                if summation and concept.definitions is not None:
                    concept.definitions.append(summation)

            if "species" in result:
                if concept.categories is not None:
                    concept.categories.extend(result["species"])

            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.REACTOME] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Reactome result: {e}")
            return None

    def _convert_reactome_details_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Reactome detailed concept to unified concept."""
        try:
            st_id = data.get("stId", "")
            label = data.get("displayName", "")

            if not st_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=st_id,
                primary_label=label,
                concept_type=_concept_type(data.get("schemaClass") or data.get("className")),
            )

            concept.add_identifier(
                KnowledgeSource.REACTOME,
                st_id,
                label,
                f"https://reactome.org/content/detail/{st_id}",
            )

            if "summation" in data and data["summation"]:
                if concept.definitions is not None:
                    concept.definitions.append(data["summation"][0].get("text", ""))

            concept.confidence_score = 1.0
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.REACTOME] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting Reactome details: {e}")
            return None
