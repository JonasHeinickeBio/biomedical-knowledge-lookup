import asyncio
import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


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
        Get detailed information about a disease by its DisGeNET ID.
        """
        headers = {
            "Authorization": self.api_key or "",
            "accept": "application/json",
        }
        url = f"{self.BASE_URL}/disease/{concept_id}"
        data = await self._make_request(url, headers=headers)
        if not data or "diseaseid" not in data:
            logger.error(f"No details found for disease {concept_id}")
            return None
        disease_id = data.get("diseaseid", concept_id)
        disease_name = data.get("diseasename", "")
        concept = UnifiedConcept(
            primary_id=disease_id,
            primary_label=disease_name,
            concept_type=ConceptType.DISEASE,
        )
        concept.source_data[KnowledgeSource.DISGENET] = data
        return concept

    async def _make_request(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with error handling and rate limit support.
        """
        try:
            session = await self._get_session()
            while True:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 429:
                        retry_after = int(
                            response.headers.get("x-rate-limit-retry-after-seconds", "5")
                        )
                        logger.warning(f"Rate limit reached. Waiting {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        continue
                    if not response.ok:
                        logger.error(f"DisGeNET API error: {response.status}")
                        return {}
                    return await response.json()
        except Exception as e:
            logger.error(f"DisGeNET API network error: {e}")
            return {}

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
            min_score, max_score, min_ei, max_ei, min_dsi, max_dsi, min_dpi, max_dpi, min_pli, max_pli: float
            min_numCTs: int
            min_yearInitial, max_yearInitial, min_yearFinal, max_yearFinal: int
            type: str
            dis_class_list: List[str]
            disease_prevalence_class, disease_prevalence_geo_area, disease_prevalence_type, disease_inheritance: str
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
        """
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
            min_score, max_score, min_ei, max_ei, min_dsi, max_dsi, min_dpi, max_dpi, min_pli, max_pli: float
            min_numCTs: int
            min_yearInitial, max_yearInitial, min_yearFinal, max_yearFinal: int
            type: str
            dis_class_list: List[str]
            disease_prevalence_class, disease_prevalence_geo_area, disease_prevalence_type, disease_inheritance: str
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
        """
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
        query: NCBI gene ID (as string)
        limit: max results (maps to page_number, 100 results per page)
        """
        params = {"gene_ncbi_id": query, "page_number": 0}
        # DisGeNET returns 100 results per page, so limit is only used for page_number=0
        data = await self.get_gene_disease_associations(params)
        concepts = []
        if data and "payload" in data:
            for i, item in enumerate(data["payload"]):
                if i >= limit:
                    break
                disease_id = item.get("diseaseid", "")
                disease_name = item.get("diseasename", "")
                score = item.get("score", 0.0)
                concept = UnifiedConcept(
                    primary_id=disease_id,
                    primary_label=disease_name,
                    concept_type=ConceptType.UNKNOWN,
                )
                concept.confidence_score = score
                concept.source_data[KnowledgeSource.DISGENET] = item
                concepts.append(concept)
        logger.info(
            f"DisGeNET search for gene {params.get('gene_ncbi_id', query)} returned {len(concepts)} concepts (limit {limit})"
        )
        return concepts
