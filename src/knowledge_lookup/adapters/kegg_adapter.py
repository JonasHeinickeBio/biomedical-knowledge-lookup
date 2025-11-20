"""
KEGG Knowledge Source Adapter

Adapter for querying KEGG pathway and disease database.
KEGG provides comprehensive pathway maps, disease information, and molecular interactions.
Particularly valuable for ME/CFS research due to extensive pathway coverage.
"""

import logging
from typing import List

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class KEGGAdapter(KnowledgeSourceAdapter):
    """Adapter for KEGG pathway and disease database."""

    def get_source(self):
        return KnowledgeSource.KEGG

    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """
        Search KEGG for pathways, diseases, and compounds.

        KEGG contains:
        - Pathways (metabolic, signaling, disease pathways)
        - Diseases (human diseases with pathway associations)
        - Compounds (chemical compounds and drugs)
        - Genes (KEGG orthologs)
        """
        try:
            from bioservices import KEGG
        except ImportError:
            logger.error("bioservices not available for KEGG adapter")
            return []

        kegg = KEGG()
        results = []

        try:
            # Search pathways
            pathway_results = kegg.find("pathway", query)
            if (
                pathway_results
                and isinstance(pathway_results, str)
                and not pathway_results.startswith("None")
            ):
                for line in pathway_results.strip().split("\n")[: limit // 3]:
                    if line.strip():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            pathway_id = parts[0]
                            pathway_name = parts[1]
                            concept = UnifiedConcept(
                                primary_id=pathway_id,
                                primary_label=pathway_name,
                                concept_type=ConceptType.BIOLOGICAL_PROCESS,
                            )
                            concept.sources.add(self.source)
                            concept.source_data[self.source] = {
                                "kegg_type": "pathway",
                                "description": f"KEGG Pathway: {pathway_name}",
                            }
                            results.append(concept)

            # Search diseases
            disease_results = kegg.find("disease", query)
            if (
                disease_results
                and isinstance(disease_results, str)
                and not disease_results.startswith("None")
            ):
                for line in disease_results.strip().split("\n")[: limit // 3]:
                    if line.strip():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            disease_id = parts[0]
                            disease_name = parts[1]
                            concept = UnifiedConcept(
                                primary_id=disease_id,
                                primary_label=disease_name,
                                concept_type=ConceptType.DISEASE,
                            )
                            concept.sources.add(self.source)
                            concept.source_data[self.source] = {
                                "kegg_type": "disease",
                                "description": f"KEGG Disease: {disease_name}",
                            }
                            results.append(concept)

            # Search compounds
            compound_results = kegg.find("compound", query)
            if (
                compound_results
                and isinstance(compound_results, str)
                and not compound_results.startswith("None")
            ):
                for line in compound_results.strip().split("\n")[: limit // 3]:
                    if line.strip():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            compound_id = parts[0]
                            compound_name = parts[1]
                            concept = UnifiedConcept(
                                primary_id=compound_id,
                                primary_label=compound_name,
                                concept_type=ConceptType.CHEMICAL,
                            )
                            concept.sources.add(self.source)
                            concept.source_data[self.source] = {
                                "kegg_type": "compound",
                                "description": f"KEGG Compound: {compound_name}",
                            }
                            results.append(concept)

        except Exception as e:
            logger.error(f"Error searching KEGG: {e}")

        return results[:limit]

    async def get_concept_details(self, concept_id: str):
        """
        Get detailed information about a KEGG entry.

        Returns pathway maps, disease descriptions, compound structures, etc.
        """
        try:
            from bioservices import KEGG
        except ImportError:
            logger.error("bioservices not available for KEGG adapter")
            return None

        kegg = KEGG()

        try:
            # Get entry details
            entry_data = kegg.get(concept_id)

            if not entry_data or (isinstance(entry_data, str) and entry_data.startswith("None")):
                return None

            # Parse the entry
            lines = entry_data.split("\n")
            entry_info = {}

            for line in lines:
                if line.startswith("NAME"):
                    entry_info["name"] = line.replace("NAME", "").strip()
                elif line.startswith("DESCRIPTION"):
                    entry_info["description"] = line.replace("DESCRIPTION", "").strip()
                elif line.startswith("CLASS"):
                    entry_info["class"] = line.replace("CLASS", "").strip()
                elif line.startswith("PATHWAY"):
                    # Extract pathway associations
                    pathways = []
                    for pline in lines[lines.index(line) :]:
                        if pline.startswith(" ") and pline.strip():
                            pathways.append(pline.strip())
                        elif not pline.startswith(" ") and pline.strip():
                            break
                    entry_info["pathways"] = pathways

            # Determine concept type based on ID prefix
            if concept_id.startswith("hsa"):
                concept_type = ConceptType.GENE
            elif concept_id.startswith("path:"):
                concept_type = ConceptType.BIOLOGICAL_PROCESS
            elif concept_id.startswith("ds:"):
                concept_type = ConceptType.DISEASE
            elif concept_id.startswith("cpd:"):
                concept_type = ConceptType.CHEMICAL
            elif concept_id.startswith("dr:"):
                concept_type = ConceptType.DRUG
            else:
                concept_type = ConceptType.MOLECULAR_ENTITY

            concept = UnifiedConcept(
                primary_id=concept_id,
                primary_label=entry_info.get("name", concept_id),
                concept_type=concept_type,
            )
            concept.sources.add(self.source)
            concept.source_data[self.source] = {
                "description": entry_info.get("description", ""),
                "class": entry_info.get("class", ""),
                "pathways": entry_info.get("pathways", []),
                "kegg_data": entry_data,
            }

            return concept

        except Exception as e:
            logger.error(f"Error getting KEGG concept details for {concept_id}: {e}")
            return None
