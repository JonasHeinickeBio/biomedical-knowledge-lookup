"""
Factory function for creating CentralKnowledgeLookup instances.
"""

from typing import Optional, List, Dict
from .models import KnowledgeSource, LookupConfig
from .central_lookup import CentralKnowledgeLookup

def create_knowledge_lookup(
    api_keys: Optional[Dict[str, str]] = None,
    enabled_sources: Optional[List[KnowledgeSource]] = None,
    fast_mode: bool = True,
    **kwargs
) -> CentralKnowledgeLookup:
    """
    Factory function to create a CentralKnowledgeLookup instance with provided configuration.
    """
    config = LookupConfig(
        api_keys=api_keys or {},
        enabled_sources=enabled_sources if enabled_sources is not None else list(KnowledgeSource),
        **kwargs
    )
    return CentralKnowledgeLookup(config)
