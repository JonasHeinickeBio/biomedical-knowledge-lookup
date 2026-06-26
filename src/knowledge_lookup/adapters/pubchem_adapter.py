"""
PubChem Knowledge Source Adapter

Integrates with NCBI PubChem for chemical compound and substance lookup.
"""

import logging

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class PubChemAdapter(KnowledgeSourceAdapter):
    """Adapter for NCBI PubChem."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.PUBCHEM

    def is_available(self) -> bool:
        return True  # PubChem is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search PubChem for compounds."""
        try:
            # Skip obviously non-chemical queries
            if not any(c.isalpha() for c in query) or len(query) > 200:
                logger.debug(f"PubChem skipping non-chemical query: '{query}'")
                return []

            # Search by name to get CIDs
            url = f"{self.base_url}/compound/name/{query}/cids/JSON"
            try:
                data = await self._make_request(url)
            except Exception as e:
                err_str = str(e)
                # Expected 404 for non-chemical entities — log at debug level
                if "404" in err_str or "PUGREST.NotFound" in err_str:
                    logger.debug(f"PubChem: no compounds found for '{query}'")
                else:
                    logger.warning(f"PubChem search failed for '{query}': {e}")
                return []

            concepts = []
            if "IdentifierList" in data and "CID" in data["IdentifierList"]:
                cids = data["IdentifierList"]["CID"][:limit]

                # For each CID, get basic details
                for cid in cids:
                    concept = await self.get_concept_details(str(cid))
                    if concept:
                        concepts.append(concept)

            logger.info(f"PubChem search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"PubChem search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed compound information from PubChem."""
        try:
            # concept_id should be a PubChem CID
            url = f"{self.base_url}/compound/cid/{concept_id}/description/JSON"
            data = await self._make_request(url)

            if "InformationList" in data and "Information" in data["InformationList"]:
                info = data["InformationList"]["Information"][0]

                label = info.get("Title", f"PubChem CID {concept_id}")

                concept = UnifiedConcept(
                    primary_id=concept_id, primary_label=label, concept_type=ConceptType.CHEMICAL
                )

                # Add PubChem identifier
                concept.add_identifier(
                    KnowledgeSource.PUBCHEM,
                    concept_id,
                    label,
                    f"https://pubchem.ncbi.nlm.nih.gov/compound/{concept_id}",
                )

                # Add description if available
                if "Description" in info:
                    if concept.definitions is not None:
                        concept.definitions.append(info["Description"])

                # Get more properties (like IUPAC name, formula, etc.)  # noqa: E501
                props_url = f"{self.base_url}/compound/cid/{concept_id}/property/IUPACName,MolecularFormula,InChIKey/JSON"  # noqa: E501
                props_data = await self._make_request(props_url)

                if "PropertyTable" in props_data and "Properties" in props_data["PropertyTable"]:
                    props = props_data["PropertyTable"]["Properties"][0]
                    if "IUPACName" in props:
                        if concept.synonyms is not None:
                            concept.synonyms.append(props["IUPACName"])
                    if "MolecularFormula" in props:
                        if concept.categories is not None:
                            concept.categories.append(f"Formula: {props['MolecularFormula']}")
                    if "InChIKey" in props:
                        concept.add_identifier(KnowledgeSource.PUBCHEM, props["InChIKey"], label)

                concept.confidence_score = 0.9
                if isinstance(concept.source_data, dict):
                    concept.source_data[KnowledgeSource.PUBCHEM] = data

                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get PubChem concept details for '{concept_id}': {e}")
            return None
