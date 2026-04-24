"""
EuropePMC Knowledge Source Adapter

Adapter for querying Europe PubMed Central (EuropePMC), a literature and
citation database covering life sciences and biomedical research.

API documentation: https://europepmc.org/RestfulWebService
"""

import logging
from typing import Any, Optional

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class EuropePMCAdapter(KnowledgeSourceAdapter):
    """Adapter for Europe PubMed Central (EuropePMC) literature database."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.EUROPEPMC

    def is_available(self) -> bool:
        return True  # EuropePMC is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search EuropePMC for literature and citations."""
        try:
            url = f"{self.base_url}/search"
            params = {
                "query": query,
                "resultType": "core",
                "pageSize": min(limit, 25),
                "format": "json",
            }

            data = await self._make_request(url, params)
            concepts = []

            result_list = data.get("resultList", {})
            for item in result_list.get("result", [])[:limit]:
                concept = self._convert_result_to_concept(item)
                if concept:
                    concepts.append(concept)

            logger.info(f"EuropePMC search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"EuropePMC search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed information about a specific EuropePMC article."""
        try:
            # concept_id expected in form "MED:12345678" or just "12345678"
            if ":" in concept_id:
                source, pmid = concept_id.split(":", 1)
            else:
                source, pmid = "MED", concept_id

            url = f"{self.base_url}/article/{source}/{pmid}"
            params = {"format": "json"}

            data = await self._make_request(url, params)
            result = data.get("result", {})
            if not result:
                return None

            return self._convert_result_to_concept(result)

        except Exception as e:
            logger.error(f"EuropePMC get_concept_details failed for '{concept_id}': {e}")
            return None

    def _convert_result_to_concept(self, item: dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert an EuropePMC result item to a UnifiedConcept."""
        try:
            pmid = item.get("pmid") or item.get("id", "")
            title = item.get("title", "")

            if not pmid or not title:
                return None

            concept_id = f"PMID:{pmid}" if not str(pmid).startswith("PMID:") else str(pmid)
            concept = self._create_concept(concept_id, title, ConceptType.CITATION)

            # Authors
            author_list = item.get("authorList", {})
            if isinstance(author_list, dict):
                authors = author_list.get("author", [])
                if isinstance(authors, list):
                    author_names = [
                        f"{a.get('lastName', '')} {a.get('initials', '')}".strip()
                        for a in authors
                        if isinstance(a, dict)
                    ]
                    if author_names:
                        concept.categories.append(f"authors:{', '.join(author_names)}")

            # Abstract
            abstract_text = item.get("abstractText", "")
            if abstract_text:
                concept.definitions.append(abstract_text[:1000])

            # Journal / source
            journal_title = item.get("journalTitle", "")
            if journal_title:
                concept.categories.append(f"journal:{journal_title}")

            # Publication year
            pub_year = item.get("pubYear", "")
            if pub_year:
                concept.categories.append(f"year:{pub_year}")

            # DOI
            doi = item.get("doi", "")
            if doi:
                concept.add_identifier(
                    KnowledgeSource.EUROPEPMC,
                    f"DOI:{doi}",
                    title,
                    f"https://doi.org/{doi}",
                )

            concept.confidence_score = 0.85
            concept.source_data[KnowledgeSource.EUROPEPMC] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting EuropePMC result: {e}")
            return None
