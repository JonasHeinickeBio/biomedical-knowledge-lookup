"""
UMLS concept operations.

This module handles concept-specific functionality including detailed lookups,
relationships, and hierarchy navigation.
"""

import logging
from typing import List, Optional, Dict, Any, Protocol
from .models import UMLSConcept

logger = logging.getLogger(__name__)


class APIClient(Protocol):
    """Protocol for API client interface."""
    def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an API request."""
        ...


class UMLSConceptService:
    """Service for UMLS concept operations."""

    def __init__(self, api_client: APIClient, version: str = "current"):
        self.api_client = api_client
        self.version = version

    def get_concept_details(self, cui: str) -> Optional[UMLSConcept]:
        """
        Get detailed information about a specific concept.

        Args:
            cui: Concept Unique Identifier

        Returns:
            UMLSConcept object or None if not found
        """
        endpoint = f"/content/{self.version}/CUI/{cui}"

        try:
            result = self.api_client.make_request(endpoint)

            # Additional safety check - ensure result is a dictionary
            if not result or not isinstance(result, dict):
                logger.warning(f"No valid data returned for CUI {cui}: received {type(result)}")
                return None

            # Additional check for string result (API error)
            if isinstance(result, str):
                logger.error(f"API returned error message for CUI {cui}: {result}")
                return None

            # Get semantic types
            semantic_types = []
            if 'semanticTypes' in result:
                try:
                    semantic_types_data = result['semanticTypes']
                    if isinstance(semantic_types_data, list):
                        semantic_types = [st.get('name', '') for st in semantic_types_data]
                    elif isinstance(semantic_types_data, str):
                        # semanticTypes is a URL, we might need to make a separate API call
                        logger.debug(f"Semantic types field is a URL: {semantic_types_data}")
                        # For now, just log and leave empty
                        semantic_types = []
                except Exception as e:
                    logger.error(f"Error processing semantic types for CUI {cui}: {e}")
                    semantic_types = []

            # Get definitions
            definitions = []
            if 'definitions' in result:
                try:
                    definitions_data = result['definitions']
                    if isinstance(definitions_data, str):
                        # definitions is a URL, we need to make a separate API call
                        logger.debug(f"Definitions field is a URL: {definitions_data}")
                        try:
                            # Extract the endpoint from the URL
                            definitions_endpoint = f"/content/{self.version}/CUI/{cui}/definitions"
                            definitions_result = self.api_client.make_request(definitions_endpoint)
                            if isinstance(definitions_result, dict) and 'results' in definitions_result:
                                definitions = [defn.get('value', '') for defn in definitions_result['results']]
                        except Exception as e:
                            logger.warning(f"Failed to fetch definitions from API: {e}")
                    elif isinstance(definitions_data, list):
                        # definitions is already a list of definition objects
                        definitions = [defn.get('value', '') for defn in definitions_data]
                except Exception as e:
                    logger.error(f"Error processing definitions for CUI {cui}: {e}")
                    definitions = []

            # Get atoms (terms/synonyms)
            atoms = []
            synonyms = []
            sources = []

            atoms_endpoint = f"/content/{self.version}/CUI/{cui}/atoms"
            try:
                # Add pageSize parameter to improve performance
                atoms_result = self.api_client.make_request(atoms_endpoint, {'pageSize': '25'})

                if 'results' in atoms_result:
                    atoms = atoms_result['results']
                    for atom in atoms:
                        try:
                            # Ensure atom is a dictionary before calling .get()
                            if not isinstance(atom, dict):
                                logger.warning(f"Unexpected atom type for CUI {cui}: {type(atom)}")
                                continue
                            if atom.get('name') and atom['name'] not in synonyms:
                                synonyms.append(atom['name'])
                            if atom.get('rootSource') and atom['rootSource'] not in sources:
                                sources.append(atom['rootSource'])
                        except Exception as e:
                            logger.error(f"Error processing atom for CUI {cui}: {e}")
                            continue
            except Exception as e:
                logger.error(f"Failed to get atoms for CUI {cui}: {e}")

            # Get relationships
            relationships = []
            rel_endpoint = f"/content/{self.version}/CUI/{cui}/relations"
            try:
                rel_result = self.api_client.make_request(rel_endpoint)

                if 'results' in rel_result:
                    relationships = rel_result['results']
            except Exception as e:
                logger.error(f"Failed to get relationships for CUI {cui}: {e}")

            try:
                concept = UMLSConcept(
                    cui=cui,
                    name=result.get('name', ''),
                    semantic_types=semantic_types,
                    definitions=definitions,
                    synonyms=synonyms,
                    sources=sources,
                    atoms=atoms,
                    relationships=relationships
                )
            except Exception as e:
                logger.error(f"Error creating UMLSConcept for CUI {cui}: {e}")
                return None

            logger.info(f"Retrieved concept details for CUI {cui}")
            return concept

        except Exception as e:
            logger.error(f"Failed to get concept details for CUI {cui}: {e}")
            return None

    def get_concept_atoms(self, cui: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all atoms (terms) for a concept.

        Args:
            cui: Concept Unique Identifier
            source: Optional source vocabulary filter

        Returns:
            List of atom dictionaries
        """
        endpoint = f"/content/{self.version}/CUI/{cui}/atoms"
        params = {
            'pageSize': '25'  # Add pagination to improve performance
        }

        if source:
            params['sabs'] = source

        try:
            result = self.api_client.make_request(endpoint, params)
            atoms = result.get('results', [])

            logger.info(f"Retrieved {len(atoms)} atoms for CUI {cui}")
            return atoms

        except Exception as e:
            logger.error(f"Failed to get atoms for CUI {cui}: {e}")
            return []

    def get_concept_relationships(self, cui: str, include_related: bool = True) -> List[Dict[str, Any]]:
        """
        Get all relationships for a concept.

        Args:
            cui: Concept Unique Identifier
            include_related: Whether to include related concepts

        Returns:
            List of relationship dictionaries
        """
        endpoint = f"/content/{self.version}/CUI/{cui}/relations"
        params = {}

        if include_related:
            params['includeRelated'] = 'true'

        try:
            result = self.api_client.make_request(endpoint, params)
            relationships = result.get('results', [])

            logger.info(f"Retrieved {len(relationships)} relationships for CUI {cui}")
            return relationships

        except Exception as e:
            logger.error(f"Failed to get relationships for CUI {cui}: {e}")
            return []

    def get_concept_hierarchy(self, cui: str, levels: int = 1) -> Dict[str, Any]:
        """
        Get concept hierarchy (parents and children).

        Args:
            cui: Concept Unique Identifier
            levels: Number of hierarchy levels to retrieve

        Returns:
            Dictionary with parents and children
        """
        result = {
            'cui': cui,
            'parents': [],
            'children': []
        }

        try:
            relationships = self.get_concept_relationships(cui)

            for rel in relationships:
                if rel.get('additionalRelationLabel') in ['PAR', 'parent']:
                    result['parents'].append({
                        'cui': rel.get('relatedId', ''),
                        'name': rel.get('relatedIdName', ''),
                        'relationship': rel.get('relationLabel', '')
                    })
                elif rel.get('additionalRelationLabel') in ['CHD', 'child']:
                    result['children'].append({
                        'cui': rel.get('relatedId', ''),
                        'name': rel.get('relatedIdName', ''),
                        'relationship': rel.get('relationLabel', '')
                    })

            logger.info(f"Retrieved hierarchy for CUI {cui}: {len(result['parents'])} parents, {len(result['children'])} children")
            return result

        except Exception as e:
            logger.error(f"Failed to get hierarchy for CUI {cui}: {e}")
            return result

    def get_cui_from_code(self, code: str, source: str) -> Optional[str]:
        """
        Get CUI from a source-specific code.

        Args:
            code: Source-specific code
            source: Source vocabulary (e.g., 'SNOMEDCT_US')

        Returns:
            CUI string or None if not found
        """
        endpoint = f"/content/{self.version}/source/{source}/{code}"

        try:
            result = self.api_client.make_request(endpoint)

            if 'results' in result and result['results']:
                concept = result['results'][0]
                cui = concept.get('concept', '').split('/')[-1]

                logger.info(f"Found CUI {cui} for code {code} in source {source}")
                return cui

            return None

        except Exception as e:
            logger.error(f"Failed to get CUI for code {code} in source {source}: {e}")
            return None
