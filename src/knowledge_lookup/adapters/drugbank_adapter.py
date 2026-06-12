"""
DrugBank Knowledge Source Adapter

Integrates with DrugBank for drug and pharmaceutical information lookup.
Note: Full access may require an API key.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class DrugBankAdapter(KnowledgeSourceAdapter):
    """Adapter for DrugBank."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://go.drugbank.com"
        # Often used via BioPortal or OLS if no direct API key is available
        self.ols_url = "https://www.ebi.ac.uk/ols4/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DRUGBANK

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search DrugBank for drugs (via OLS)."""
        try:
            url = f"{self.ols_url}/search"
            params = {
                "q": query,
                "ontology": "drugbank",
                "rows": min(limit, 100),
                "format": "json",
            }

            data = await self._make_request(url, params)

            concepts = []
            if "response" in data and "docs" in data["response"]:
                for doc in data["response"]["docs"]:
                    concept = self._convert_drugbank_result_to_concept(doc)
                    if concept:
                        concepts.append(concept)

            logger.info(f"DrugBank search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"DrugBank search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed drug information from DrugBank (via OLS)."""
        try:
            # concept_id should be DrugBank ID (e.g., DB00001)  # noqa: E501
            url = f"{self.ols_url}/ontologies/drugbank/terms/http%253A%252F%252Fpurl.bioontology.org%252Fontology%252FDRUGBANK%252F{concept_id}"  # noqa: E501

            data = await self._make_request(url)

            if data:
                concept = self._convert_drugbank_details_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get DrugBank concept details for '{concept_id}': {e}")
            return None

    def _convert_drugbank_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert DrugBank OLS search result to unified concept."""
        try:
            db_id = result.get("short_form", "")
            label = result.get("label", "")

            if not db_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=db_id, primary_label=label, concept_type=ConceptType.DRUG
            )

            concept.add_identifier(KnowledgeSource.DRUGBANK, db_id, label, result.get("iri", ""))

            if "synonym" in result:
                concept.synonyms.extend(result["synonym"])

            if "description" in result:
                concept.definitions.extend(result["description"])

            concept.confidence_score = 0.9
            concept.source_data[KnowledgeSource.DRUGBANK] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting DrugBank result: {e}")
            return None

    def _convert_drugbank_details_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert DrugBank OLS detailed concept to unified concept."""
        try:
            db_id = data.get("short_form", "")
            label = data.get("label", "")

            if not db_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=db_id, primary_label=label, concept_type=ConceptType.DRUG
            )

            concept.add_identifier(KnowledgeSource.DRUGBANK, db_id, label, data.get("iri", ""))

            if "synonyms" in data:
                concept.synonyms.extend(data["synonyms"])

            if "description" in data:
                concept.definitions.extend(data["description"])

            concept.confidence_score = 0.95
            concept.source_data[KnowledgeSource.DRUGBANK] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting DrugBank details: {e}")
            return None
