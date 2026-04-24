"""
EBI OLS Knowledge Source Adapter

Integrates with EMBL-EBI Ontology Lookup Service.
This is a specialized version of the OLS adapter.
"""

from ..models import KnowledgeSource
from .ols_adapter import OLSAdapter


class EBIOLSAdapter(OLSAdapter):
    """Adapter for EMBL-EBI OLS."""

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.EBIOLS
