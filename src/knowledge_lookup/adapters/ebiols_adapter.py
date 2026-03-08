"""
EBI OLS Knowledge Source Adapter

Integrates with EMBL-EBI Ontology Lookup Service.
This is a specialized version of the OLS adapter.
"""

from .ols_adapter import OLSAdapter
from ..models import KnowledgeSource


class EBIOLSAdapter(OLSAdapter):
    """Adapter for EMBL-EBI OLS."""
    
    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.EBIOLS
