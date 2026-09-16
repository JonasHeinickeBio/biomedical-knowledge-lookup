import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Gene symbols: upper-case letters/digits/hyphens starting with a letter (CDK2, BRCA1, HLA-B)
_GENE_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9-]{0,14}$")
# Vocabularies DisGeNET writes as <VOCAB>_<code> (UMLS_C0004096, MONDO_0004979, ...)
_DISEASE_VOCABULARIES = {"UMLS", "MONDO", "MESH", "DO", "EFO", "ICD10", "ICD9CM", "NCI", "OMIM"}
_UMLS_CUI_RE = re.compile(r"^C\d{7}$")


class DisGeNETAdapter(KnowledgeSourceAdapter):
    """
    Adapter for DisGeNET REST API.
    """

    BASE_URL = "https://api.disgenet.com/api/v1"

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.api_key = config.get_api_key("disgenet")
        if not self.api_key:
            logger.warning("DisGeNET API key not found in config.")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DISGENET

    def is_available(self) -> bool:
        return self.api_key is not None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get detailed information about a disease.

        Accepts DisGeNET disease identifiers such as ``UMLS_C0004096`` (as returned
        by :meth:`search_concepts`), a bare UMLS CUI (``C0004096``) or other
        vocabulary IDs (``MONDO_0004979``, ``MONDO:0004979``). Returns ``None`` when
        the disease is unknown or the request fails.
        """
        try:
            disease_id = self._normalize_disease_id(concept_id)
            data = await self._make_request(
                f"{self.BASE_URL}/entity/disease",
                params={"disease": disease_id},
                headers=self._headers(),
            )
            payload = (data or {}).get("payload") or []
            if not payload:
                logger.info(f"No DisGeNET details found for disease {concept_id}")
                return None

            item = payload[0]
            if disease_id.startswith("UMLS_"):
                cui = disease_id.removeprefix("UMLS_")
                item = next((row for row in payload if row.get("diseaseUMLSCUI") == cui), item)
            return self._convert_disease_entity_to_concept(item)

        except Exception as e:
            logger.error(f"DisGeNET get_concept_details failed for '{concept_id}': {e}")
            return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key or "",
            "accept": "application/json",
        }

    @staticmethod
    def _normalize_disease_id(concept_id: str) -> str:
        """Normalize a disease ID to DisGeNET's ``<VOCAB>_<code>`` form."""
        disease_id = concept_id.strip()
        if ":" in disease_id:
            prefix, code = disease_id.split(":", 1)
            if prefix.upper() in _DISEASE_VOCABULARIES:
                disease_id = f"{prefix.upper()}_{code}"
        if _UMLS_CUI_RE.match(disease_id):
            disease_id = f"UMLS_{disease_id}"
        return disease_id

    @staticmethod
    def _score_to_confidence(score: Any) -> float:
        try:
            return max(0.0, min(float(score), 1.0))
        except (TypeError, ValueError):
            return 0.0

    def _add_disease_classes(self, concept: UnifiedConcept, item: dict[str, Any]) -> None:
        if concept.semantic_types is not None:
            for semantic_type in item.get("diseaseClasses_UMLS_ST") or []:
                if semantic_type and semantic_type not in concept.semantic_types:
                    concept.semantic_types.append(semantic_type)
        if concept.categories is not None:
            for disease_class in item.get("diseaseClasses_MSH") or []:
                if disease_class and disease_class not in concept.categories:
                    concept.categories.append(disease_class)

    def _convert_disease_entity_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a ``/entity/disease`` row to a DISEASE concept."""
        cui = item.get("diseaseUMLSCUI", "")
        name = item.get("name", "") or item.get("diseaseName", "")
        if not cui or not name:
            return None

        concept = self._create_concept(f"UMLS_{cui}", name, ConceptType.DISEASE)
        if concept.synonyms is not None:
            for synonym in item.get("synonyms") or []:
                synonym_name = synonym.get("name") if isinstance(synonym, dict) else synonym
                if synonym_name and synonym_name != name and synonym_name not in concept.synonyms:
                    concept.synonyms.append(synonym_name)
        self._add_disease_classes(concept, item)
        concept.confidence_score = 0.8
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.DISGENET] = item
        return concept

    def _convert_gda_row_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a ``/gda/summary`` row to a DISEASE concept scored by the association."""
        cui = item.get("diseaseUMLSCUI", "")
        name = item.get("diseaseName", "")
        if not cui or not name:
            return None

        concept = self._create_concept(f"UMLS_{cui}", name, ConceptType.DISEASE)
        self._add_disease_classes(concept, item)
        gene_symbol = item.get("symbolOfGene")
        if gene_symbol and concept.related is not None:
            concept.related.append(gene_symbol)
        concept.confidence_score = self._score_to_confidence(item.get("score"))
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.DISGENET] = item
        return concept

    async def _make_request(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request with smart retry and DisGeNET rate-limit awareness.

        Delegates to the base class ``_call_with_retry`` which handles
        circuit-breaker gating, error classification, and per-category
        exponential backoff (4 retries for rate limits, 2s/4s/8s/16s).

        Uses ``json_data is None`` to always do GET requests (DisGeNET API
        does not use POST for search operations).
        """

        async def _do() -> dict[str, Any]:
            session = await self._get_session()
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

        return await self._call_with_retry("disgenet_api", _do)

    async def get_gene_disease_associations(
        self, params: dict[str, Any], raw: bool = False
    ) -> Any | None:
        """
        Query gene-disease associations with flexible parameters.

        Supported parameters (all optional, see DisGeNET API docs for details):
            gene_ncbi_id: str or comma-separated list
            gene_ensembl_id: str or comma-separated list
            gene_symbol: str or comma-separated list
            uniprot_id: str or comma-separated list
            disease: str or comma-separated list
            chemical_id: str or comma-separated list
            chemical_association: str
            source: List[str]
            evidence_level: List[str]
            min_score, max_score, min_ei, max_ei, min_dsi, max_dsi, min_dpi, max_dpi, min_pli, max_pli: float  # noqa: E501
            min_numCTs: int
            min_yearInitial, max_yearInitial, min_yearFinal, max_yearFinal: int
            type: str
            dis_class_list: List[str]
            disease_prevalence_class, disease_prevalence_geo_area, disease_prevalence_type, disease_inheritance: str  # noqa: E501
            order_by: List[str]
            page_number: int

        Example:
            params = {
                "gene_ncbi_id": "1234,5678",
                "disease": "UMLS_C0005745,MONDO_0000728",
                "min_score": 0.2,
                "page_number": 0
            }
            result = await adapter.get_gene_disease_associations(params)
            result_raw = await adapter.get_gene_disease_associations(params, raw=True)
        """  # noqa: E501
        clean_params = {k: v for k, v in params.items() if v is not None}
        headers = {
            "Authorization": self.api_key or "",
            "accept": "application/json",
        }
        url = f"{self.BASE_URL}/gda/summary"
        data = await self._make_request(url, clean_params, headers)
        if not data or "payload" not in data:
            logger.error("No data returned from DisGeNET API.")
            return None
        if raw:
            return data
        parsed_results = []
        for item in data["payload"]:
            parsed = {
                "assocID": item.get("assocID"),
                "gene_symbol": item.get("symbolOfGene"),
                "gene_ncbi_id": item.get("geneNcbiID"),
                "gene_ensembl_ids": item.get("geneEnsemblIDs"),
                "gene_type": item.get("geneNcbiType"),
                "disease_name": item.get("diseaseName"),
                "disease_vocabularies": item.get("diseaseVocabularies"),
                "disease_umls_cui": item.get("diseaseUMLSCUI"),
                "score": item.get("score"),
                "year_initial": item.get("yearInitial"),
                "year_final": item.get("yearFinal"),
                "num_pmids": item.get("numPMIDs"),
                "num_ct_supporting_association": item.get("numCTsupportingAssociation"),
                "gene_dsi": item.get("geneDSI"),
                "gene_dpi": item.get("geneDPI"),
                "gene_pli": item.get("genepLI"),
                "gene_protein_str_ids": item.get("geneProteinStrIDs"),
                "gene_protein_class_names": item.get("geneProteinClassNames"),
                "disease_classes_msh": item.get("diseaseClasses_MSH"),
                "disease_classes_umls_st": item.get("diseaseClasses_UMLS_ST"),
                "disease_classes_do": item.get("diseaseClasses_DO"),
                "disease_classes_hpo": item.get("diseaseClasses_HPO"),
                "disease_prevalence_class": item.get("disease_prevalence_class"),
                "disease_prevalence_geo_area": item.get("disease_prevalence_geo_area"),
                "disease_prevalence_type": item.get("disease_prevalence_type"),
                "disease_inheritance": item.get("disease_inheritance"),
                "ei": item.get("ei"),
                "el": item.get("el"),
            }
            parsed_results.append(parsed)
        return parsed_results

    async def get_gene_disease_associations_evidence(
        self, params: dict[str, Any], raw: bool = False
    ) -> Any | None:
        """
        Query gene-disease associations with flexible parameters.

        Supported parameters (all optional, see DisGeNET API docs for details):
            gene_ncbi_id: str or comma-separated list
            gene_ensembl_id: str or comma-separated list
            gene_symbol: str or comma-separated list
            uniprot_id: str or comma-separated list
            disease: str or comma-separated list
            chemical_id: str or comma-separated list
            chemical_association: str
            source: List[str]
            evidence_level: List[str]
            min_score, max_score, min_ei, max_ei, min_dsi, max_dsi, min_dpi, max_dpi, min_pli, max_pli: float  # noqa: E501
            min_numCTs: int
            min_yearInitial, max_yearInitial, min_yearFinal, max_yearFinal: int
            type: str
            dis_class_list: List[str]
            disease_prevalence_class, disease_prevalence_geo_area, disease_prevalence_type, disease_inheritance: str  # noqa: E501
            order_by: List[str]
            page_number: int

        Example:
            params = {
                "gene_ncbi_id": "1234,5678",
                "disease": "UMLS_C0005745,MONDO_0000728",
                "min_score": 0.2,
                "page_number": 0
            }
            result = await adapter.get_gene_disease_associations_evidence(params)
            result_raw = await adapter.get_gene_disease_associations_evidence(params, raw=True)
        """  # noqa: E501
        clean_params = {k: v for k, v in params.items() if v is not None}
        headers = {
            "Authorization": self.api_key or "",
            "accept": "application/json",
        }
        url = f"{self.BASE_URL}/gda/evidence"
        data = await self._make_request(url, clean_params, headers)
        if not data or "payload" not in data:
            logger.error("No data returned from DisGeNET API.")
            return None
        if raw:
            return data
        parsed_results = []
        for item in data["payload"]:
            parsed = {
                "assocID": item.get("assocID"),
                "gene_symbol": item.get("symbolOfGene"),
                "gene_ncbi_id": item.get("geneNcbiID"),
                "gene_ensembl_ids": item.get("geneEnsemblIDs"),
                "gene_type": item.get("geneNcbiType"),
                "disease_name": item.get("diseaseName"),
                "disease_vocabularies": item.get("diseaseVocabularies"),
                "disease_umls_cui": item.get("diseaseUMLSCUI"),
                "score": item.get("score"),
                "year_initial": item.get("yearInitial"),
                "year_final": item.get("yearFinal"),
                "num_pmids": item.get("numPMIDs"),
                "num_ct_supporting_association": item.get("numCTsupportingAssociation"),
                "gene_dsi": item.get("geneDSI"),
                "gene_dpi": item.get("geneDPI"),
                "gene_pli": item.get("genepLI"),
                "gene_protein_str_ids": item.get("geneProteinStrIDs"),
                "gene_protein_class_names": item.get("geneProteinClassNames"),
                "disease_classes_msh": item.get("diseaseClasses_MSH"),
                "disease_classes_umls_st": item.get("diseaseClasses_UMLS_ST"),
                "disease_classes_do": item.get("diseaseClasses_DO"),
                "disease_classes_hpo": item.get("diseaseClasses_HPO"),
                "disease_prevalence_class": item.get("disease_prevalence_class"),
                "disease_prevalence_geo_area": item.get("disease_prevalence_geo_area"),
                "disease_prevalence_type": item.get("disease_prevalence_type"),
                "disease_inheritance": item.get("disease_inheritance"),
                "ei": item.get("ei"),
                "el": item.get("el"),
            }
            parsed_results.append(parsed)
        return parsed_results

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search for gene-disease associations and return UnifiedConcepts.

        Smart parameter detection:
        - All-numeric query → diseases associated with ``gene_ncbi_id`` (``/gda/summary``)
        - Gene-symbol-like query (``CDK2``, ``BRCA1``) → diseases associated with
          ``gene_symbol`` (``/gda/summary``); falls back to the disease name search
          when no gene matches (``COPD``, ``ASTHMA``)
        - Everything else → disease name search
          (``/entity/disease?disease_free_text_search_string=...``)

        Every result is a ``DISEASE`` concept with ID ``UMLS_<CUI>``, usable with
        :meth:`get_concept_details`. Association results carry the GDA score as
        ``confidence_score``.
        """
        try:
            query_stripped = query.strip()
            if not query_stripped:
                return []

            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()

            def _add(concept: UnifiedConcept | None) -> None:
                if concept and concept.primary_id not in seen and len(concepts) < limit:
                    seen.add(concept.primary_id)
                    concepts.append(concept)

            # Gene queries: diseases associated with the gene
            gene_params: dict[str, Any] | None = None
            if query_stripped.isdigit():
                gene_params = {"gene_ncbi_id": query_stripped, "page_number": 0}
            elif _GENE_SYMBOL_RE.match(query_stripped):
                gene_params = {"gene_symbol": query_stripped, "page_number": 0}

            if gene_params is not None:
                data = await self._make_request(
                    f"{self.BASE_URL}/gda/summary", params=gene_params, headers=self._headers()
                )
                for item in (data or {}).get("payload") or []:
                    _add(self._convert_gda_row_to_concept(item))

            # Disease name search (also the fallback for symbol-like disease names)
            if not concepts and not query_stripped.isdigit():
                data = await self._make_request(
                    f"{self.BASE_URL}/entity/disease",
                    params={"disease_free_text_search_string": query_stripped, "page_number": 0},
                    headers=self._headers(),
                )
                for item in (data or {}).get("payload") or []:
                    _add(self._convert_disease_entity_to_concept(item))

            logger.info(f"DisGeNET search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"DisGeNET search failed for '{query}': {e}")
            return []
