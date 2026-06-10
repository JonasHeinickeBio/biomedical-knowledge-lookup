"""
Factory function for creating CentralKnowledgeLookup instances.
"""

from .central_lookup import CentralKnowledgeLookup
from .models import KnowledgeSource, LookupConfig


def create_knowledge_lookup(
    api_keys: dict[str, str] | None = None,
    enabled_sources: list[KnowledgeSource] | None = None,
    fast_mode: bool = True,
    **kwargs,
) -> CentralKnowledgeLookup:
    """
    Factory function to create a CentralKnowledgeLookup instance with provided configuration.
    """
    config = LookupConfig(
        api_keys=api_keys or {},
        enabled_sources=enabled_sources if enabled_sources is not None else list(KnowledgeSource),
        **kwargs,
    )
    return CentralKnowledgeLookup(config)
