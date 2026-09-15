"""
DrugBank Knowledge Source Adapter

Looks up DrugBank drug identifiers, names and synonyms without an API key.
DrugBank's own API is licensed, and the former EBI OLS ``drugbank`` ontology no
longer exists, so the adapter queries MyChem.info (BioThings), which serves the
DrugBank open-data fields (ID, name, synonyms, CAS, UNII, InChIKey).

DrugBank data is licensed CC BY-NC 4.0 (see https://go.drugbank.com/legal).
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Characters with a meaning in the Lucene query syntax used by MyChem.info
_LUCENE_SPECIAL_RE = re.compile(r'([+\-=&|><!(){}\[\]^"~*?:\\/])')

_DRUGBANK_FIELDS = (
    "drugbank.id,drugbank.name,drugbank.synonyms,drugbank.cas,drugbank.unii,drugbank.inchi_key"
)


def _escape_query(text: str) -> str:
    """Escape Lucene query-syntax characters so user input is searched literally."""
    return _LUCENE_SPECIAL_RE.sub(r"\\\1", text)


class DrugBankAdapter(KnowledgeSourceAdapter):
    """Adapter for DrugBank (served through MyChem.info)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        # Used for identifier URLs
        self.base_url = "https://go.drugbank.com"
        # Keyless BioThings API that serves DrugBank open data
        self.api_url = "https://mychem.info/v1"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DRUGBANK

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search DrugBank drugs by name, synonym or DrugBank ID (via MyChem.info)."""
        try:
            query = query.strip()
            if not query:
                return []

            url = f"{self.api_url}/query"
            params = {
                # Escape the user query and only keep records with DrugBank data
                "q": f"({_escape_query(query)}) AND _exists_:drugbank",
                "fields": _DRUGBANK_FIELDS,
                "size": max(1, min(limit, 100)),
            }

            data = await self._make_request(url, params)

            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for hit in (data or {}).get("hits", []) or []:
                for record in self._drugbank_records(hit):
                    concept = self._convert_drugbank_result_to_concept(record)
                    if concept and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
                if len(concepts) >= limit:
                    break

            logger.info(f"DrugBank search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]

        except Exception as e:
            logger.error(f"DrugBank search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get drug information for a DrugBank ID (e.g. ``DB00945``) via MyChem.info."""
        try:
            db_id = concept_id.strip()
            if ":" in db_id:  # DRUGBANK:DB00945 / drugbank:DB00945
                db_id = db_id.split(":", 1)[1].strip()
            if not db_id:
                return None

            url = f"{self.api_url}/query"
            params = {
                "q": f'drugbank.id:"{_escape_query(db_id)}"',
                "fields": "drugbank",
                "size": 5,
            }

            data = await self._make_request(url, params)

            for hit in (data or {}).get("hits", []) or []:
                for record in self._drugbank_records(hit):
                    if str(record.get("id", "")).upper() == db_id.upper():
                        return self._convert_drugbank_details_to_concept(record)

            return None

        except Exception as e:
            logger.error(f"Failed to get DrugBank concept details for '{concept_id}': {e}")
            return None

    @staticmethod
    def _drugbank_records(hit: Any) -> list[dict[str, Any]]:
        """Return the DrugBank record(s) of a MyChem.info hit (object or list)."""
        if not isinstance(hit, dict):
            return []
        drugbank = hit.get("drugbank")
        if isinstance(drugbank, dict):
            return [drugbank]
        if isinstance(drugbank, list):
            return [record for record in drugbank if isinstance(record, dict)]
        return []

    def _build_concept(self, record: dict[str, Any], confidence: float) -> UnifiedConcept | None:
        """Build a DRUG concept from a MyChem.info ``drugbank`` record."""
        db_id = record.get("id", "")
        label = record.get("name", "")

        if not db_id or not label:
            return None

        concept = UnifiedConcept(
            primary_id=db_id, primary_label=label, concept_type=ConceptType.DRUG
        )

        concept.add_identifier(
            KnowledgeSource.DRUGBANK, db_id, label, f"{self.base_url}/drugs/{db_id}"
        )
        concept.sources = [KnowledgeSource.DRUGBANK]

        synonyms = record.get("synonyms") or []
        if isinstance(synonyms, str):
            synonyms = [synonyms]
        if concept.synonyms is not None:
            for synonym in synonyms:
                if synonym and synonym != label and synonym not in concept.synonyms:
                    concept.synonyms.append(synonym)

        description = record.get("description")
        if description and concept.definitions is not None:
            if isinstance(description, list):
                concept.definitions.extend(d for d in description if d)
            else:
                concept.definitions.append(description)

        if concept.categories is not None:
            for key in ("cas", "unii", "inchi_key"):
                value = record.get(key)
                if isinstance(value, str) and value:
                    concept.categories.append(f"{key}:{value}")

        concept.confidence_score = confidence
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.DRUGBANK] = record

        return concept

    def _convert_drugbank_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a MyChem.info ``drugbank`` search record to a unified concept."""
        try:
            return self._build_concept(result, 0.9)
        except Exception as e:
            logger.error(f"Error converting DrugBank result: {e}")
            return None

    def _convert_drugbank_details_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a MyChem.info ``drugbank`` record to a detailed unified concept."""
        try:
            return self._build_concept(data, 0.95)
        except Exception as e:
            logger.error(f"Error converting DrugBank details: {e}")
            return None
