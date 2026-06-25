"""
HGNC Knowledge Source Adapter

Adapter for querying HGNC (HUGO Gene Nomenclature Committee) database.
Provides official gene symbols, names, and cross-references for human genes.

API documentation: https://www.genenames.org/help/rest/
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class HGNCAdapter(KnowledgeSourceAdapter):
    """Adapter for HGNC (HUGO Gene Nomenclature Committee) database."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://rest.genenames.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.HGNC

    def is_available(self) -> bool:
        return True  # HGNC REST API is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search HGNC for gene symbols and names."""
        try:
            url = f"{self.base_url}/search/{query}"
            headers = {"Accept": "application/json"}

            data = await self._make_request(url, headers=headers)
            concepts = []

            response_data = data.get("response", {})
            docs = response_data.get("docs", [])

            for item in docs[:limit]:
                concept = self._convert_result_to_concept(item)
                if concept:
                    concepts.append(concept)

            logger.info(f"HGNC search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"HGNC search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information about a specific HGNC gene entry."""
        try:
            # Support HGNC IDs (e.g. "HGNC:1100") or gene symbols
            if concept_id.upper().startswith("HGNC:"):
                url = f"{self.base_url}/fetch/hgnc_id/{concept_id}"
            else:
                url = f"{self.base_url}/fetch/symbol/{concept_id}"

            headers = {"Accept": "application/json"}
            data = await self._make_request(url, headers=headers)

            docs = data.get("response", {}).get("docs", [])
            if not docs:
                return None

            return self._convert_result_to_concept(docs[0])

        except Exception as e:
            logger.error(f"HGNC get_concept_details failed for '{concept_id}': {e}")
            return None

    def _convert_result_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert an HGNC result item to a UnifiedConcept."""
        try:
            hgnc_id = item.get("hgnc_id", "")
            symbol = item.get("symbol", "")
            name = item.get("name", symbol)

            if not hgnc_id or not symbol:
                return None

            concept = self._create_concept(hgnc_id, name, ConceptType.GENE)
            if concept.synonyms is not None:
                concept.synonyms.append(symbol)

            # Alias symbols
            for alias in item.get("alias_symbol", []):
                if alias:
                    if concept.synonyms is not None:
                        concept.synonyms.append(alias)

            # Previous symbols
            for prev in item.get("prev_symbol", []):
                if prev:
                    if concept.synonyms is not None:
                        concept.synonyms.append(prev)

            # Location / locus
            location = item.get("location", "")
            if location:
                if concept.categories is not None:
                    concept.categories.append(f"locus:{location}")

            # Gene group
            gene_group = item.get("gene_group", [])
            if isinstance(gene_group, list):
                if concept.categories is not None:
                    concept.categories.extend(gene_group)
            elif gene_group:
                if concept.categories is not None:
                    concept.categories.append(str(gene_group))

            # Locus type
            locus_type = item.get("locus_type", "")
            if locus_type:
                if concept.semantic_types is not None:
                    concept.semantic_types.append(locus_type)

            # Cross-references
            entrez_id = item.get("entrez_id", "")
            if entrez_id:
                concept.add_identifier(
                    KnowledgeSource.NCBI,
                    str(entrez_id),
                    symbol,
                    f"https://www.ncbi.nlm.nih.gov/gene/{entrez_id}",
                )

            uniprot_ids = item.get("uniprot_ids", [])
            for uid in uniprot_ids:
                if uid:
                    concept.add_identifier(
                        KnowledgeSource.UNIPROT,
                        uid,
                        symbol,
                        f"https://www.uniprot.org/uniprot/{uid}",
                    )

            ensembl_id = item.get("ensembl_gene_id", "")
            if ensembl_id:
                concept.add_identifier(
                    KnowledgeSource.ENSEMBL,
                    ensembl_id,
                    symbol,
                    f"https://www.ensembl.org/id/{ensembl_id}",
                )

            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.HGNC] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting HGNC result: {e}")
            return None
