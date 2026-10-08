"""
NCI Thesaurus (EVS) adapter.

STUB: registered so the source exists in ``KnowledgeSource``, ``ADAPTER_CLASSES`` and the
MCP catalog, but not implemented yet. ``is_available()`` is ``False`` so
``CentralKnowledgeLookup`` skips it until it is.
"""

from ..base import KnowledgeSourceAdapter
from ..models import KnowledgeSource, UnifiedConcept


class NCIEVSAdapter(KnowledgeSourceAdapter):
    """NCI Thesaurus (EVS) (not implemented yet)."""

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.NCIEVS

    def is_available(self) -> bool:
        return False

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        return None
