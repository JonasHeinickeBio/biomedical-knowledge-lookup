"""
Adapter for ChEMBL drug/compound database using chembl_webresource_client.
"""

import logging
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any

from chembl_webresource_client.new_client import new_client

from ..base import KnowledgeSourceAdapter
from ..models import ConceptIdentifier, ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ..utils.retry_utils import create_chembl_retry_decorator

# Endpoints check_api_status() probes, each with a one-record request.
_STATUS_PROBE_ENDPOINTS = ("status", "molecule", "activity")


def _is_list_endpoint(client: Any) -> bool:
    """False for single-object resources such as ``status``, whose QuerySet cannot be sliced."""
    return getattr(getattr(client, "query", None), "allows_multiple", True) is not False


def _fetch_one_record(client: Any) -> list[Any]:
    """Fetch one record. ``list()`` is what makes the lazy QuerySet send its request."""
    return list(client.all()[:1])


class ChEMBLAdapter(KnowledgeSourceAdapter):
    def __init__(self, config: LookupConfig):
        """
        Initialize the ChEMBLAdapter with the provided LookupConfig.
        Sets up the ChEMBL client and ontology adapters (OLS, BioOntology).
        Handles errors during initialization and logs them.
        Args:
            config (LookupConfig): Configuration for lookup and adapter setup.
        """
        self.logger = logging.getLogger(__name__)
        try:
            super().__init__(config)
            self.chembl_client = new_client
            # Initialize ontology adapters for mapping
            from .bioontology_adapter import BioOntologyAdapter
            from .ols_adapter import OLSAdapter

            self.ols_adapter = OLSAdapter(config)
            self.bioontology_adapter = BioOntologyAdapter(config)
        except Exception as e:
            self.logger.error(f"Error initializing ChEMBLAdapter: {e}")

    def get_source(self) -> KnowledgeSource:
        """
        Returns the KnowledgeSource enum for ChEMBL.
        Output:
            KnowledgeSource.CHEMBL
        """
        return KnowledgeSource.CHEMBL

    def check_api_status(self, timeout: float | None = None) -> dict:
        """
        Check the current status of the ChEMBL API service.

        Fetches one record from each of the ``status``, ``molecule`` and
        ``activity`` endpoints. ``status`` is a single-object resource in the
        ChEMBL client and is reported as ``status(not a list endpoint)``. The
        synchronous client runs in worker threads; a probe without an answer
        after *timeout* seconds is reported as ``<endpoint>(timed out)`` and its
        thread is left to finish on its own. ``available`` is ``True`` when at
        least one probe returned a response.

        Args:
            timeout: seconds to wait for the probes, together. Defaults to
                ``LookupConfig.timeout_per_source``.
        Returns:
            dict: Status information with keys:
                - 'available': bool, whether API is responding
                - 'status_code': int or None, HTTP status code
                - 'error': str or None, error message if any
                - 'endpoints_tested': list of endpoint names tested
                - 'available_endpoints': list of all available endpoint names
        """
        status: dict[str, Any] = {
            "available": False,
            "status_code": None,
            "error": None,
            "endpoints_tested": [],
            "available_endpoints": [],
        }

        # Known ChEMBL endpoints (based on ChEMBL Web Resource Client)
        known_endpoints = [
            "activity",
            "assay",
            "atc_class",
            "binding_site",
            "biotherapeutic",
            "cell_line",
            "chembl_id_lookup",
            "compound_record",
            "compound_structural_alert",
            "document",
            "document_similarity",
            "drug",
            "drug_indication",
            "drug_warning",
            "go_slim",
            "image",
            "mechanism",
            "metabolism",
            "molecule",
            "molecule_form",
            "organism",
            "protein_class",
            "source",
            "status",
            "substructure",
            "similarity",
            "target",
            "target_component",
            "target_relation",
            "tissue",
            "xref_source",
        ]

        # Test endpoint availability by trying to access them
        available_endpoints = []
        for endpoint in known_endpoints:
            try:
                client = getattr(self.chembl_client, endpoint, None)
                if client is not None:
                    available_endpoints.append(endpoint)
            except Exception:
                continue

        status["available_endpoints"] = sorted(available_endpoints)

        # Probe a few list endpoints by fetching one record each. QuerySets are
        # lazy (slicing only builds the query), so the slice is materialised to
        # send the request. The client is synchronous: the probes run in worker
        # threads and are given up on after `timeout` seconds.
        probe_timeout = (
            timeout if timeout is not None else (self.config.timeout_per_source or 30.0)
        )
        valid_endpoints: list[str] = status["available_endpoints"]
        outcomes: dict[str, str] = {}
        probes: dict[str, Future[list[Any]]] = {}
        executor = ThreadPoolExecutor(
            max_workers=len(_STATUS_PROBE_ENDPOINTS), thread_name_prefix="chembl-status"
        )
        try:
            for endpoint in _STATUS_PROBE_ENDPOINTS:
                client = (
                    getattr(self.chembl_client, endpoint, None)
                    if endpoint in valid_endpoints
                    else None
                )
                if client is None:
                    outcomes[endpoint] = f"{endpoint}(not available)"
                elif not _is_list_endpoint(client):
                    outcomes[endpoint] = f"{endpoint}(not a list endpoint)"
                else:
                    probes[endpoint] = executor.submit(_fetch_one_record, client)
            if probes:
                wait(list(probes.values()), timeout=probe_timeout)
        finally:
            # Don't wait for a hung request; its thread ends with the client's own timeout.
            executor.shutdown(wait=False, cancel_futures=True)

        for endpoint, future in probes.items():
            if not future.done() or future.cancelled():
                outcomes[endpoint] = f"{endpoint}(timed out)"
                status["error"] = f"Endpoint '{endpoint}' did not answer within {probe_timeout}s"
                continue
            error = future.exception()
            if error is not None:
                outcomes[endpoint] = f"{endpoint}(failed)"
                status["error"] = f"Endpoint '{endpoint}' failed: {str(error)[:100]}..."
            else:
                outcomes[endpoint] = endpoint
                status["available"] = True

        status["endpoints_tested"] = [outcomes[e] for e in _STATUS_PROBE_ENDPOINTS]
        return status

    def query(
        self,
        endpoint: str,
        filters: dict | None = None,
        fields: list | None = None,
        limit: int = 100,
    ):
        """
        Generic, reusable query interface for ChEMBL endpoints with retry logic.

        This method is synchronous and blocks while the ChEMBL client downloads.
        From async code use ``await query_async(...)``, which runs the client in a
        worker thread.

        Args:
            endpoint (str): ChEMBL endpoint name (e.g., 'molecule', 'drug', 'target').
            filters (dict, optional): Query filters for endpoint.
            fields (list, optional): Fields to include in results.
            limit (int): Max number of results to return; only this many are fetched.
        Returns:
            List[dict]: List of result dicts from ChEMBL endpoint.
        Error Handling:
            Raises ValueError for an unknown endpoint. Transient API failures
            (5xx, connection errors) are retried with exponential backoff; other
            errors are logged and an empty list is returned.
        """
        try:
            return self._query_with_retry(endpoint, filters, fields, limit)
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(f"ChEMBL query error for endpoint '{endpoint}': {e}")
            return []

    @create_chembl_retry_decorator(
        max_tries=4,
        logger_name=__name__,
    )
    def _query_with_retry(
        self, endpoint: str, filters: dict | None, fields: list | None, limit: int
    ) -> list[dict]:
        # Separate from query() so the decorator sees the exceptions it retries
        return self._run_query(endpoint, filters, fields, limit)

    def _run_query(
        self,
        endpoint: str,
        filters: dict | None = None,
        fields: list | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Run one ChEMBL query and return at most ``limit`` records. Raises on errors."""
        client = getattr(self.chembl_client, endpoint, None)
        if client is None:
            raise ValueError(f"Endpoint '{endpoint}' not found in ChEMBL client.")
        if limit <= 0:
            return []

        if filters is not None:
            results = client.filter(**filters)
        else:
            results = client.all()
        if fields:
            results = results.only(fields)
        # Slice the lazy QuerySet before materialising it, so the client fetches
        # only `limit` records instead of paging through every match.
        return list(results[:limit])

    async def query_async(
        self,
        endpoint: str,
        filters: dict | None = None,
        fields: list | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Async version of :meth:`query` that does not block the event loop.

        The synchronous ChEMBL client runs in a worker thread through the shared
        retry and circuit breaker (``_thread_with_retry``).

        Raises:
            ValueError: unknown endpoint.
            Exception: the last API error once retries are exhausted.
        """
        if getattr(self.chembl_client, endpoint, None) is None:
            raise ValueError(f"Endpoint '{endpoint}' not found in ChEMBL client.")
        return await self._thread_with_retry(
            f"chembl_{endpoint}", self._run_query, endpoint, filters, fields, limit
        )

    async def lookup_molecule(
        self, filters: dict | None = None, fields: list | None = None, limit: int = 100
    ):
        """
        Lookup molecules in ChEMBL and parse results to UnifiedConcepts.

        Async: ``await adapter.lookup_molecule(...)``. The parsers are async
        (ontology mapping), so the synchronous version returned an un-awaited
        coroutine.

        Args:
            filters (dict, optional): Query filters for molecules.
            fields (list, optional): Fields to include in results.
            limit (int): Max number of results.
        Returns:
            List[UnifiedConcept]: List of parsed molecule concepts.
        Error Handling:
            Logs and returns empty list on error.
        """
        try:
            raw_results = await self.query_async(
                "molecule",
                filters=filters if filters is not None else {},
                fields=fields if fields is not None else [],
                limit=limit,
            )
            return await self._parse_molecule_results(raw_results)
        except Exception as e:
            self.logger.error(f"lookup_molecule error: {e}")
            return []

    async def lookup_drug(
        self, filters: dict | None = None, fields: list | None = None, limit: int = 100
    ):
        """
        Lookup drugs in ChEMBL and parse results to UnifiedConcepts.

        Async: ``await adapter.lookup_drug(...)``.

        Args:
            filters (dict, optional): Query filters for drugs.
            fields (list, optional): Fields to include in results.
            limit (int): Max number of results.
        Returns:
            List[UnifiedConcept]: List of parsed drug concepts.
        Error Handling:
            Logs and returns empty list on error.
        """
        try:
            raw_results = await self.query_async(
                "drug",
                filters=filters if filters is not None else {},
                fields=fields if fields is not None else [],
                limit=limit,
            )
            return await self._parse_drug_results(raw_results)
        except Exception as e:
            self.logger.error(f"lookup_drug error: {e}")
            return []

    async def lookup_target(
        self, filters: dict | None = None, fields: list | None = None, limit: int = 100
    ):
        """
        Lookup targets in ChEMBL and parse results to UnifiedConcepts.

        Async: ``await adapter.lookup_target(...)``.

        Args:
            filters (dict, optional): Query filters for targets.
            fields (list, optional): Fields to include in results.
            limit (int): Max number of results.
        Returns:
            List[UnifiedConcept]: List of parsed target concepts.
        Error Handling:
            Logs and returns empty list on error.
        """
        try:
            raw_results = await self.query_async(
                "target",
                filters=filters if filters is not None else {},
                fields=fields if fields is not None else [],
                limit=limit,
            )
            return await self._parse_target_results(raw_results)
        except Exception as e:
            self.logger.error(f"lookup_target error: {e}")
            return []

    def lookup_activity(
        self, filters: dict | None = None, fields: list | None = None, limit: int = 100
    ):
        """
        Lookup activities in ChEMBL and parse results.

        Args:
            filters (dict, optional): Query filters for activities  # noqa: E501
                (e.g., {"molecule_chembl_id": "CHEMBL25"}).
            fields (list, optional): Specific fields to include in results.
                If None, returns all fields.
            limit (int): Max number of results.

        Returns:
            List[dict]: List of raw activity data (not parsed to UnifiedConcepts).
                Each activity record contains 46+ fields - see get_activities_for_molecule()  # noqa: E501
                or get_activities_for_target() docstrings for complete field list.

        Error Handling:
            Logs and returns empty list on error.
        """  # noqa: E501
        try:
            raw_results = self.query(
                "activity",
                filters=filters if filters is not None else {},
                fields=fields if fields is not None else [],
                limit=limit,
            )
            return raw_results
        except Exception as e:
            self.logger.error(f"lookup_activity error: {e}")
            return []

    def get_activities_for_molecule(self, molecule_id: str, limit: int = 50):
        """
        Get all bioactivity data for a specific molecule.

        Args:
            molecule_id (str): ChEMBL molecule ID (e.g., 'CHEMBL25').
            limit (int): Max number of activities to return.

        Returns:
            List[dict]: List of activity records. Each record contains 46+ fields including:

        Core Identifiers:
            - activity_id: Unique activity identifier
            - molecule_chembl_id: ChEMBL ID of the compound
            - molecule_pref_name: Preferred name of the compound
            - target_chembl_id: ChEMBL ID of the biological target
            - target_pref_name: Preferred name of the target
            - target_organism: Species of the target organism
            - target_tax_id: NCBI taxonomy ID of the target organism
            - assay_chembl_id: ChEMBL ID of the assay
            - document_chembl_id: ChEMBL ID of the source document

        Activity Measurements:
            - standard_type: Standardized activity type (e.g., 'Kd', 'IC50', 'EC50')
            - standard_value: Standardized numerical value
            - standard_units: Units for the standardized value (e.g., 'nM', 'uM')
            - standard_relation: Relationship operator ('=', '>', '<', '>=', '<=', '~')
            - pchembl_value: Negative log of standardized value (normalized potency)
            - type: Original activity type from source
            - value: Original numerical value
            - units: Original units
            - relation: Original relationship operator

        Assay Information:
            - assay_description: Description of the assay method
            - assay_type: Type of assay ('F' = Functional, 'B' = Binding, 'A' = ADME,
                'T' = Toxicity, 'P' = Physicochemical, 'U' = Unassigned)
            - bao_endpoint: BioAssay Ontology endpoint term
            - bao_format: BioAssay Ontology format term

        Publication Data:
            - document_journal: Journal where data was published
            - document_year: Year of publication

        Quality & Metadata:
            - standard_flag: 1 if data is standardized, 0 otherwise
            - potential_duplicate: 1 if activity might be duplicate
            - canonical_smiles: SMILES representation of the molecule
            - data_validity_comment: Comments on data quality
            - activity_comment: Additional activity notes

        For Knowledge Graph Integration:
            Recommended fields: activity_id, molecule_chembl_id, target_chembl_id,
            standard_type, standard_value, standard_units, standard_relation,
            pchembl_value, target_pref_name, assay_chembl_id, document_chembl_id
        """
        try:
            filters = {"molecule_chembl_id": molecule_id}
            return self.lookup_activity(filters=filters, limit=limit)
        except Exception as e:
            self.logger.error(f"get_activities_for_molecule error for {molecule_id}: {e}")
            return []

    def get_activities_for_target(self, target_id: str, limit: int = 50):
        """
        Get all bioactivity data for a specific target.

        Args:
            target_id (str): ChEMBL target ID (e.g., 'CHEMBL1806').
            limit (int): Max number of activities to return.

        Returns:
            List[dict]: List of activity records. Each record contains 46+ fields including:

        Core Identifiers:
            - activity_id: Unique activity identifier
            - molecule_chembl_id: ChEMBL ID of the compound
            - molecule_pref_name: Preferred name of the compound
            - target_chembl_id: ChEMBL ID of the biological target
            - target_pref_name: Preferred name of the target
            - target_organism: Species of the target organism
            - target_tax_id: NCBI taxonomy ID of the target organism
            - assay_chembl_id: ChEMBL ID of the assay
            - document_chembl_id: ChEMBL ID of the source document

        Activity Measurements:
            - standard_type: Standardized activity type (e.g., 'Kd', 'IC50', 'EC50')
            - standard_value: Standardized numerical value
            - standard_units: Units for the standardized value (e.g., 'nM', 'uM')
            - standard_relation: Relationship operator ('=', '>', '<', '>=', '<=', '~')
            - pchembl_value: Negative log of standardized value (normalized potency)
            - type: Original activity type from source
            - value: Original numerical value
            - units: Original units
            - relation: Original relationship operator

        Assay Information:
            - assay_description: Description of the assay method
            - assay_type: Type of assay ('F' = Functional, 'B' = Binding, 'A' = ADME,
                'T' = Toxicity, 'P' = Physicochemical, 'U' = Unassigned)
            - bao_endpoint: BioAssay Ontology endpoint term
            - bao_format: BioAssay Ontology format term

        Publication Data:
            - document_journal: Journal where data was published
            - document_year: Year of publication

        Quality & Metadata:
            - standard_flag: 1 if data is standardized, 0 otherwise
            - potential_duplicate: 1 if activity might be duplicate
            - canonical_smiles: SMILES representation of the molecule
            - data_validity_comment: Comments on data quality
            - activity_comment: Additional activity notes

        For Knowledge Graph Integration:
            Recommended fields: activity_id, molecule_chembl_id, target_chembl_id,
            standard_type, standard_value, standard_units, standard_relation,
            pchembl_value, molecule_pref_name, assay_chembl_id, document_chembl_id
        """
        try:
            filters = {"target_chembl_id": target_id}
            return self.lookup_activity(filters=filters, limit=limit)
        except Exception as e:
            self.logger.error(f"get_activities_for_target error for {target_id}: {e}")
            return []

    async def _parse_molecule_results(self, results):
        """
        Parse raw molecule results from ChEMBL into UnifiedConcept objects.
        Extracts comprehensive molecule data including physicochemical properties.

        Args:
            results (list): List of raw molecule dicts from ChEMBL.

        Returns:
            List[UnifiedConcept]: List of parsed molecule concepts with enriched data.

        Error Handling:
            Logs errors during parsing and category mapping.
            Returns partial results if errors occur.
        """
        concepts = []
        try:
            for r in results:
                chembl_id = r.get("molecule_chembl_id")
                label = r.get("pref_name") or r.get("molecule_name") or chembl_id
                synonyms = r.get("synonyms", [])

                # Build comprehensive definition from available data
                definitions = []
                if r.get("description"):
                    definitions.append(r["description"])
                if r.get("molecule_type"):
                    definitions.append(f"Type: {r['molecule_type']}")

                # Extract physicochemical properties
                properties = r.get("molecule_properties", {})
                if properties:
                    props_list = []
                    if properties.get("full_mwt"):
                        props_list.append(f"MW: {properties['full_mwt']}")
                    if properties.get("full_molformula"):
                        props_list.append(f"Formula: {properties['full_molformula']}")
                    if properties.get("alogp") is not None:
                        props_list.append(f"LogP: {properties['alogp']}")
                    if properties.get("psa"):
                        props_list.append(f"PSA: {properties['psa']}")
                    if properties.get("hbd") is not None:
                        props_list.append(f"HBD: {properties['hbd']}")
                    if properties.get("hba") is not None:
                        props_list.append(f"HBA: {properties['hba']}")
                    if properties.get("aromatic_rings"):
                        props_list.append(f"Aromatic rings: {properties['aromatic_rings']}")
                    if properties.get("ro3_pass"):
                        props_list.append(f"RO3 compliant: {properties['ro3_pass']}")
                    if properties.get("qed_weighted"):
                        try:
                            qed_value = float(properties["qed_weighted"])
                            props_list.append(f"QED: {qed_value:.2f}")
                        except (ValueError, TypeError):
                            props_list.append(f"QED: {properties['qed_weighted']}")
                    if props_list:
                        definitions.append("Properties: " + ", ".join(props_list))

                # Extract structural information
                structures = r.get("molecule_structures", {})
                if structures:
                    struct_info = []
                    if structures.get("canonical_smiles"):
                        struct_info.append("Has SMILES")
                    if structures.get("standard_inchi"):
                        struct_info.append("Has InChI")
                    if structures.get("standard_inchi_key"):
                        struct_info.append("Has InChI Key")
                    if struct_info:
                        definitions.append("Structures: " + ", ".join(struct_info))

                # Add natural product flag
                if r.get("natural_product") == 1:
                    definitions.append("Natural product")

                concept_type = ConceptType.CHEMICAL
                identifier = ConceptIdentifier(
                    source=KnowledgeSource.CHEMBL,
                    identifier=chembl_id or "",
                    label=label,
                    url=(
                        f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/"
                        if chembl_id
                        else None
                    ),
                )

                # Enhanced categories
                categories = []
                raw_category = r.get("molecule_type")
                if raw_category:
                    categories.append(raw_category)

                # Add therapeutic flags as categories
                if r.get("therapeutic_flag"):
                    categories.append("Therapeutic")
                if r.get("natural_product") == 1:
                    categories.append("Natural Product")
                if r.get("oral"):
                    categories.append("Oral")
                if r.get("topical"):
                    categories.append("Topical")
                if r.get("parenteral"):
                    categories.append("Parenteral")

                # Map categories to ontology terms (if enabled)
                mapped_categories = []
                if self.config.enable_ontology_mapping:
                    for cat in categories:
                        try:
                            mapped = await self.map_category_to_ontology(cat)
                            if mapped:
                                mapped_categories.append(mapped)
                        except Exception as e:
                            self.logger.error(f"Error mapping category '{cat}': {e}")

                concept = UnifiedConcept(
                    primary_id=chembl_id or "",
                    primary_label=label,
                    concept_type=concept_type,
                    identifiers=[identifier],
                    synonyms=synonyms,
                    definitions=definitions,
                    categories=mapped_categories if mapped_categories else categories,
                    sources={KnowledgeSource.CHEMBL},
                    source_data={KnowledgeSource.CHEMBL: r},
                )
                concepts.append(concept)
            return concepts
        except Exception as e:
            self.logger.error(f"_parse_molecule_results error: {e}")
            return concepts

    async def _parse_drug_results(self, results):
        """
        Parse raw drug results from ChEMBL into UnifiedConcept objects.
        Args:
            results (list): List of raw drug dicts from ChEMBL.
        Returns:
            List[UnifiedConcept]: List of parsed drug concepts.
        Error Handling:
            Logs errors during parsing and category mapping. Returns partial results if errors occur.  # noqa: E501
        """  # noqa: E501
        concepts = []
        try:
            for r in results:
                chembl_id = r.get("drug_chembl_id") or r.get("molecule_chembl_id")
                label = r.get("pref_name") or r.get("drug_name") or chembl_id
                synonyms = r.get("synonyms", [])
                # ChEMBL's drug endpoint returns drug_type as an integer code
                drug_type = r.get("drug_type")
                drug_type = str(drug_type) if drug_type is not None else None
                definition = r.get("description") or drug_type
                concept_type = ConceptType.DRUG
                identifier = ConceptIdentifier(
                    source=KnowledgeSource.CHEMBL,
                    identifier=chembl_id or "",
                    label=label,
                    url=f"https://www.ebi.ac.uk/chembl/drug/{chembl_id}/" if chembl_id else None,
                )
                raw_category = drug_type
                try:
                    mapped_category = (
                        await self.map_category_to_ontology(raw_category) if raw_category else None
                    )
                except Exception as e:
                    self.logger.error(f"Error mapping drug category '{raw_category}': {e}")
                    mapped_category = None
                concept = UnifiedConcept(
                    primary_id=chembl_id or "",
                    primary_label=label,
                    concept_type=concept_type,
                    identifiers=[identifier],
                    synonyms=synonyms,
                    definitions=[definition] if definition else [],
                    categories=[mapped_category] if mapped_category else [],
                    sources={KnowledgeSource.CHEMBL},
                    source_data={KnowledgeSource.CHEMBL: r},
                )
                concepts.append(concept)
            return concepts
        except Exception as e:
            self.logger.error(f"_parse_drug_results error: {e}")
            return concepts

    async def _parse_target_results(self, results):
        """
        Parse raw target results from ChEMBL into UnifiedConcept objects.
        Args:
            results (list): List of raw target dicts from ChEMBL.
        Returns:
            List[UnifiedConcept]: List of parsed target concepts.
        Error Handling:
            Logs errors during parsing and category mapping. Returns partial results if errors occur.  # noqa: E501
        """  # noqa: E501
        concepts = []
        try:
            for r in results:
                target_id = r.get("target_chembl_id")
                label = r.get("pref_name") or r.get("target_name") or target_id
                synonyms = r.get("synonyms", [])
                definition = r.get("description") or r.get("target_type")
                concept_type = (
                    ConceptType.PROTEIN
                    if r.get("target_type") == "PROTEIN"
                    else ConceptType.UNKNOWN
                )
                identifier = ConceptIdentifier(
                    source=KnowledgeSource.CHEMBL,
                    identifier=target_id or "",
                    label=label,
                    url=(
                        f"https://www.ebi.ac.uk/chembl/target_report_card/{target_id}/"
                        if target_id
                        else None
                    ),
                )
                raw_category = r.get("target_type")
                try:
                    mapped_category = (
                        await self.map_category_to_ontology(raw_category) if raw_category else None
                    )
                except Exception as e:
                    self.logger.error(f"Error mapping target category '{raw_category}': {e}")
                    mapped_category = None
                concept = UnifiedConcept(
                    primary_id=target_id or "",
                    primary_label=label,
                    concept_type=concept_type,
                    identifiers=[identifier],
                    synonyms=synonyms,
                    definitions=[definition] if definition else [],
                    categories=[mapped_category] if mapped_category else [],
                    sources={KnowledgeSource.CHEMBL},
                    source_data={KnowledgeSource.CHEMBL: r},
                )
                concepts.append(concept)
            return concepts
        except Exception as e:
            self.logger.error(f"_parse_target_results error: {e}")
            return concepts

    async def map_category_to_ontology(self, category: str) -> str:
        """
        Map a ChEMBL category string to a unified KG ontology term using OLS and BioOntology adapters.  # noqa: E501
        Args:
            category (str): Raw category string from ChEMBL (e.g., molecule_type, drug_type, target_type).  # noqa: E501
        Returns:
            str: Best-matching ontology term label, synonym, or original category if no match found. Returns "unknown" if input is invalid or mapping fails.  # noqa: E501
        Error Handling:
            Logs mapping attempts, errors, and fallbacks. Robust to normalization and empty input.
        Mapping Logic:
            - Normalizes input string
            - Tries OLSAdapter for label/synonym match
            - Falls back to BioOntologyAdapter if OLS fails
            - Returns original category if no match found
        """  # noqa: E501
        import logging

        logger = logging.getLogger(__name__)
        try:
            if not category or not isinstance(category, str):
                logger.info(f"No category provided for ontology mapping: {category}")
                return "unknown"
            norm_category = category.strip().lower()
            # Try OLS first
            try:
                concepts = await self.ols_adapter.search_concepts(norm_category, limit=5)
                for concept in concepts:
                    # Prefer exact label match
                    if (
                        concept.primary_label
                        and concept.primary_label.strip().lower() == norm_category
                    ):
                        logger.info(
                            f"Mapped category '{category}' to OLS label '{concept.primary_label}'"
                        )
                        return concept.primary_label
                    # Fallback to synonyms
                    for syn in concept.synonyms or []:
                        if syn.strip().lower() == norm_category:
                            logger.info(f"Mapped category '{category}' to OLS synonym '{syn}'")
                            return syn
            except Exception as e:
                logger.error(f"OLS mapping error for category '{category}': {e}")
            # Fallback to BioOntology
            try:
                concepts = await self.bioontology_adapter.search_concepts(norm_category, limit=5)
                for concept in concepts:
                    if (
                        concept.primary_label
                        and concept.primary_label.strip().lower() == norm_category
                    ):
                        logger.info(
                            f"Mapped category '{category}' to BioOntology label '{concept.primary_label}'"  # noqa: E501
                        )
                        return concept.primary_label
                    for syn in concept.synonyms or []:
                        if syn.strip().lower() == norm_category:
                            logger.info(
                                f"Mapped category '{category}' to BioOntology synonym '{syn}'"  # noqa: E501
                            )
                            return syn
            except Exception as e:
                logger.error(f"BioOntology mapping error for category '{category}': {e}")
            logger.info(
                f"No ontology mapping found for category '{category}', returning original."
            )
            return category
        except Exception as e:
            logger.error(f"map_category_to_ontology failed for category '{category}': {e}")
            return "unknown"

    async def search_concepts(self, query: str, limit: int = 20):
        """
        Search ChEMBL for concepts matching the query string across molecule, drug, and target endpoints.  # noqa: E501
        Stops early if enough results are found, and skips slow endpoints if previous queries succeed.
        Args:
            query (str): Search term for ChEMBL entities.
            limit (int): Maximum number of results to return in total.
        Returns:
            List[UnifiedConcept]: List of parsed concepts matching the query from any endpoint.
        Error Handling:
            Logs and returns partial results or empty list on error.
        """  # noqa: E501
        try:
            concepts: list[UnifiedConcept] = []
            endpoints = [
                ("molecule", self._parse_molecule_results),
                ("drug", self._parse_drug_results),
                ("target", self._parse_target_results),
            ]
            for endpoint, parser in endpoints:
                filters = {"pref_name__icontains": query}
                try:
                    # Runs the blocking client in a worker thread (retry + circuit breaker)
                    raw_results = await self.query_async(
                        endpoint, filters=filters, limit=limit - len(concepts)
                    )
                    parsed = await parser(raw_results)
                    concepts += parsed
                except Exception as e:
                    self.logger.error(f"search_concepts error for endpoint '{endpoint}': {e}")
                if len(concepts) >= limit:
                    break
            return concepts[:limit]
        except Exception as e:
            self.logger.error(f"search_concepts error: {e}")
            return []

    async def get_concept_details(self, concept_id: str):
        """
        Get detailed information about a specific ChEMBL concept (molecule, drug, or target).
        Args:
            concept_id (str): ChEMBL entity identifier (e.g., CHEMBL25).
        Returns:
            UnifiedConcept or None: Detailed concept if found, else None.
        Error Handling:
            Logs and returns None on error or if not found.
        """
        try:
            # Molecule
            filters = {"molecule_chembl_id": concept_id}
            raw_results = await self.query_async("molecule", filters=filters, limit=1)
            concepts = await self._parse_molecule_results(raw_results)
            if concepts:
                return concepts[0]
            # Drug. The drug resource is keyed by molecule_chembl_id and has no
            # drug_chembl_id field; ChEMBL ignores unknown filters and would
            # return an unrelated drug from the whole table.
            filters = {"molecule_chembl_id": concept_id}
            raw_results = await self.query_async("drug", filters=filters, limit=1)
            concepts = await self._parse_drug_results(raw_results)
            if concepts:
                return concepts[0]
            # Target
            filters = {"target_chembl_id": concept_id}
            raw_results = await self.query_async("target", filters=filters, limit=1)
            concepts = await self._parse_target_results(raw_results)
            if concepts:
                return concepts[0]
            return None
        except Exception as e:
            self.logger.error(f"get_concept_details error: {e}")
            return None
