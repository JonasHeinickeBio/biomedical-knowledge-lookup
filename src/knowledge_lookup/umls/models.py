"""
UMLS data models and classes.

This module contains data classes and models used throughout the UMLS client.
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class UMLSConcept:
    """Represents a UMLS concept with its properties."""
    cui: str
    name: str
    semantic_types: List[str]
    definitions: List[str]
    synonyms: List[str]
    sources: List[str]
    atoms: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
    def __post_init__(self):
        """Ensure all fields are properly initialized."""
        if not isinstance(self.semantic_types, list):
            self.semantic_types = []
        if not isinstance(self.definitions, list):
            self.definitions = []
        if not isinstance(self.synonyms, list):
            self.synonyms = []
        if not isinstance(self.sources, list):
            self.sources = []
        if not isinstance(self.atoms, list):
            self.atoms = []
        if not isinstance(self.relationships, list):
            self.relationships = []


@dataclass
class UMLSSearchResult:
    """Represents a search result from UMLS."""
    cui: str
    name: str
    ui: str
    source: str
    source_concept_id: str
    root_source: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cui': self.cui,
            'name': self.name,
            'ui': self.ui,
            'source': self.source,
            'source_concept_id': self.source_concept_id,
            'root_source': self.root_source
        }
