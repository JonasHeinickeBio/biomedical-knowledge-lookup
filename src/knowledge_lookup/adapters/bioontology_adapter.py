"""
Adapter for BioOntology.org (now part of BioPortal).
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class BioOntologyAdapter(KnowledgeSourceAdapter):
    """
    Adapter for BioOntology.org (now part of BioPortal).
    This is essentially an alias for BioPortal functionality.
    """

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://data.bioontology.org"
        self.api_key = config.get_api_key("bioontology") or config.get_api_key("bioportal")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.BIOONTOLOGY

    def is_available(self) -> bool:
        return self.api_key is not None

    _api_endpoints: dict[str, str] | None = None

    @property
    def endpoints(self) -> dict[str, str]:
        """
        Return cached endpoints if available, else empty dict.
        """
        return self._api_endpoints if isinstance(self._api_endpoints, dict) else {}

    def _build_params(
        self, extra_params: dict[str, Any] | None = None, **kwargs
    ) -> dict[str, Any]:
        params = {
            "apikey": self.api_key,
            "format": kwargs.get("format", "json"),
            "include": kwargs.get("include"),
            "page": kwargs.get("page"),
            "pagesize": kwargs.get("pagesize"),
            "include_views": kwargs.get("include_views"),
            "display_context": kwargs.get("display_context"),
            "display_links": kwargs.get("display_links"),
        }
        # Map 'query' or 'q' to 'q' for search endpoints
        if "query" in kwargs:
            params["q"] = kwargs["query"]
        elif "q" in kwargs:
            params["q"] = kwargs["q"]
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        if extra_params:
            params.update(extra_params)
        return params

    def _build_headers(self, use_auth_header: bool = False) -> dict[str, str]:
        headers = {}
        if use_auth_header and self.api_key:
            headers["Authorization"] = f"apikey token={self.api_key}"
        return headers

    async def _make_request(
        self,
        url: str,
        params: dict[Any, Any] | None = None,
        headers: dict[Any, Any] | None = None,
        json_data: dict[Any, Any] | None = None,
        use_auth_header: bool = False,
    ) -> dict[str, Any]:
        """
        Make an async HTTP request, logging the URL, params, and headers for debugging.
        """
        logger.info(f"API Request URL: {url}")
        logger.info(f"API Request Params: {params}")
        if headers:
            logger.info(f"API Request Headers: {headers}")
        if use_auth_header:
            if headers is None:
                headers = {}
            headers.update(self._build_headers(use_auth_header=True))
        try:
            return await super()._make_request(url, params, headers)
        except Exception as e:
            logger.error(f"API request failed for URL {url}: {e}")
            return {}

    async def fetch_api_endpoints(self) -> dict[str, str]:
        """
        Fetch and cache available API endpoints from the BioOntology API root.
        """
        # Always return a dict, never None
        url = self.base_url
        params = {"apikey": self.api_key, "format": "json"}
        try:
            data = await self._make_request(url, params)
            if data and "links" in data:
                self._api_endpoints = data["links"]
                return self._api_endpoints if isinstance(self._api_endpoints, dict) else {}
            else:
                logger.warning("BioOntology API endpoints not found in response.")
                return {}
        except Exception as e:
            logger.error(f"Failed to fetch BioOntology API endpoints: {e}")
            return {}

    async def call_endpoint(
        self, endpoint_name: str, params: dict[str, Any] | None = None
    ) -> dict | None:
        """
        Call any BioOntology API endpoint by name, using cached endpoints if available.
        """
        if not self._api_endpoints:
            await self.fetch_api_endpoints()
        url = self.endpoints.get(endpoint_name)
        if not url:
            logger.error(f"Endpoint '{endpoint_name}' not found in BioOntology API endpoints.")
            return None
        if params is None:
            params = {}
        params.setdefault("apikey", self.api_key)
        params.setdefault("format", "json")
        try:
            data = await self._make_request(url, params)
            return data
        except Exception as e:
            logger.error(f"Failed to call endpoint '{endpoint_name}': {e}")
            return None

    async def search_concepts(
        self,
        query: str,
        limit: int = 20,
        raw: bool = False,
        extra_params: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[Any]:
        if not self.api_key:
            logger.warning("BioOntology API key not available")
            return []
        try:
            url = f"{self.base_url}/search"
            params = self._build_params(
                extra_params, query=query, pagesize=min(limit, 50), **kwargs
            )
            logger.info(f"BioOntology search URL: {url}")
            logger.info(f"BioOntology search Params: {params}")
            data = await self._make_request(url, params)
            if raw:
                logger.info(f"BioOntology search for '{query}' returned raw output")
                return data.get("collection", [])[:limit] if "collection" in data else []
            concepts = self._parse_search_response(data, limit)
            logger.info(f"BioOntology search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"BioOntology search failed for '{query}': {e}")
            return []

    def _build_search_request(self, query: str, limit: int) -> tuple:
        url = f"{self.base_url}/search"
        params = {
            "q": query,
            "pagesize": min(limit, 50),
            "apikey": self.api_key,
            "format": "json",
        }
        return url, params

    def _parse_search_response(self, data: dict, limit: int) -> list[UnifiedConcept]:
        concepts = []
        if "collection" in data:
            for item in data["collection"][:limit]:
                concept = self._convert_bioontology_result_to_concept(item)
                if concept:
                    concepts.append(concept)
        return concepts

    async def get_concept_details(
        self,
        concept_id: str,
        ontology: str | None = None,
        fetch_related: bool = True,
        extra_params: dict[str, Any] | None = None,
        use_auth_header: bool = False,
        minimal: bool = False,
        raw: bool = False,
        **kwargs,
    ) -> Any | None:
        """
        Fetch concept details. Use 'raw' for full metadata, 'minimal' for reduced metadata,  # noqa: E501
        default for parsed object.
        """  # noqa: E501
        if not self.api_key:
            logger.warning("BioOntology API key not available")
            return None
        try:
            url, params = self._build_details_request(concept_id, ontology=ontology)
            params.update(self._build_params(extra_params, **kwargs))
            logger.info(f"BioOntology details URL: {url}")
            logger.info(f"BioOntology details Params: {params}")
            data = await self._make_request(url, params, use_auth_header=use_auth_header)
            if raw:
                logger.info(f"Fetched raw details for concept '{concept_id}'")
                return data
            if minimal:
                logger.info(f"Fetched minimal details for concept '{concept_id}'")
                return self.parse_minimal_metadata(data)
            concept = self._parse_details_response(data)
            if concept and fetch_related and "links" in data:
                await self._fetch_related_resources(
                    concept, data["links"], concept_id, extra_params=extra_params
                )
            if concept:
                logger.info(f"Fetched details for concept '{concept_id}'")
            else:
                logger.info(f"No details found for concept '{concept_id}'")
            return concept
        except Exception as e:
            logger.error(f"BioOntology get_concept_details failed for '{concept_id}': {e}")
            return None

    @staticmethod
    def parse_minimal_metadata(concept_details: dict) -> dict:
        """
        Return a minimal metadata dict for a concept (id, label, synonyms, definition, obsolete).
        """
        if not isinstance(concept_details, dict):
            return {}
        return {
            "id": concept_details.get("@id"),
            "label": concept_details.get("prefLabel"),
            "synonyms": concept_details.get("synonym"),
            "definition": concept_details.get("definition"),
            "obsolete": concept_details.get("obsolete"),
        }

    async def annotate(
        self,
        text: str,
        ontologies: str | None = None,
        longest_only: bool = True,
        extra_params: dict[str, Any] | None = None,
        **kwargs,
    ) -> Any:
        """
        Annotate text using the BioOntology Annotator endpoint.

        Examines the input text and returns relevant ontology classes.

        Args:
            text: The text to annotate.
            ontologies: Comma-separated list of ontology IDs to limit annotation.
            longest_only: Return only the longest match per phrase.
            extra_params: Additional query parameters.

        Returns:
            Raw annotation response list from BioOntology API, or empty list on failure.
        """
        if not self.api_key:
            logger.warning("BioOntology API key not available for annotation")
            return []

        url = f"{self.base_url}/annotator"
        params: dict[str, Any] = {
            "apikey": self.api_key,
            "text": text,
            "longest_only": str(longest_only).lower(),
        }
        if ontologies:
            params["ontologies"] = ontologies
        if extra_params:
            params.update(extra_params)

        logger.info(f"BioOntology annotate URL: {url}")
        logger.info(f"BioOntology annotate text (first 80 chars): {text[:80]}")
        try:
            data = await self._make_request(url, params)
            if isinstance(data, list):
                return data
            # Some responses may be a dict with a key
            return data.get("annotations", data.get("results", []))
        except Exception as e:
            logger.error(f"BioOntology annotate failed: {e}")
            return []

    async def batch_annotate(
        self,
        texts: list[str],
        ontologies: str | None = None,
        longest_only: bool = True,
        extra_params: dict[str, Any] | None = None,
        **kwargs,
    ) -> Any:
        """
        Batch annotate multiple texts using BioOntology batch endpoint.
        """
        url = f"{self.base_url}/annotator/batch"
        params = self._build_params(
            extra_params, longest_only=longest_only, ontologies=ontologies, **kwargs
        )
        logger.info(f"BioOntology batch annotate URL: {url}")
        logger.info(f"BioOntology batch annotate Params: {params}")
        try:
            data = await self._make_request(url, params)
            return data
        except Exception as e:
            logger.error(f"BioOntology batch annotate failed: {e}")
            return None

    async def get_analytics(
        self,
        ontology: str | None = None,
        month: int | None = None,
        year: int | None = None,
        extra_params: dict[str, Any] | None = None,
        **kwargs,
    ) -> Any:
        """
        Get analytics data for BioOntology usage/popularity.
        """
        url = f"{self.base_url}/analytics"
        params = self._build_params(
            extra_params, ontology=ontology, month=month, year=year, **kwargs
        )
        logger.info(f"BioOntology analytics URL: {url}")
        logger.info(f"BioOntology analytics Params: {params}")
        try:
            data = await self._make_request(url, params)
            return data
        except Exception as e:
            logger.error(f"BioOntology analytics failed: {e}")
            return None

    async def _fetch_related_resources(
        self, concept, links, concept_id, extra_params: dict[str, Any] | None = None
    ):
        """
        Fetch related resources (children, parents, ancestors, etc.) and add  # noqa: E501
        to concept.source_data.
        """
        related_keys = [
            "children",
            "parents",
            "ancestors",
            "descendants",
            "tree",
            "notes",
            "mappings",
            "instances",
        ]
        for key in related_keys:
            link = links.get(key)
            if link:
                try:
                    params = {"apikey": self.api_key, "format": "json"}
                    if extra_params:
                        params.update(extra_params)
                    logger.info(f"Related resource API URL: {link}")
                    logger.info(f"Related resource API Params: {params}")
                    related_data = await self._make_request(link, params)
                    if isinstance(concept.source_data, dict):
                        concept.source_data[f"bioontology_{key}"] = related_data
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch related resource '{key}' for concept '{concept_id}': {e}"
                    )

    def _build_details_request(self, concept_id: str, ontology: str | None = None) -> tuple:
        # Always use data.bioontology.org API endpoint
        from urllib.parse import quote

        if not ontology:
            raise ValueError("Ontology must be provided for concept details request.")
        # If concept_id is a full URL, encode it
        if concept_id.startswith("http"):
            encoded_id = quote(concept_id, safe="")
        else:
            encoded_id = concept_id
        url = f"{self.base_url}/ontologies/{ontology}/classes/{encoded_id}"
        params = {
            "apikey": self.api_key,
            "format": "json",
        }
        return url, params

    def _parse_details_response(self, data: dict) -> UnifiedConcept | None:
        return self._convert_bioontology_result_to_concept(data)

    def _convert_bioontology_result_to_concept(
        self, result: dict[str, Any]
    ) -> UnifiedConcept | None:
        try:
            concept_id = result.get("@id", "")
            label = result.get("prefLabel", "")
            if not concept_id or not label:
                return None
            concept = UnifiedConcept(
                primary_id=concept_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )
            concept.add_identifier(
                KnowledgeSource.BIOONTOLOGY, concept_id, label, result.get("@id", "")
            )
            # Parse synonyms
            synonyms = result.get("synonym") or result.get("synonyms")
            if isinstance(synonyms, list):
                if concept.synonyms is not None:
                    concept.synonyms.extend(synonyms)
            elif isinstance(synonyms, str):
                if concept.synonyms is not None:
                    concept.synonyms.append(synonyms)
            # Parse definitions
            definitions = result.get("definition")
            if isinstance(definitions, list):
                if concept.definitions is not None:
                    concept.definitions.extend(definitions)
            elif isinstance(definitions, str):
                if concept.definitions is not None:
                    concept.definitions.append(definitions)
            # Parse CUI
            cui = result.get("cui")
            if cui:
                if isinstance(cui, list):
                    if concept.categories is not None:
                        concept.categories.extend(cui)
                else:
                    if concept.categories is not None:
                        concept.categories.append(str(cui))
            # Parse semanticType
            semantic_type = result.get("semanticType")
            if semantic_type:
                if isinstance(semantic_type, list):
                    if concept.semantic_types is not None:
                        concept.semantic_types.extend(semantic_type)
                else:
                    if concept.semantic_types is not None:
                        concept.semantic_types.append(str(semantic_type))
            # Parse obsolete status
            if result.get("obsolete") is True:
                if concept.categories is not None:
                    concept.categories.append("obsolete")
            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.BIOONTOLOGY] = result
            return concept
        except Exception as e:
            logger.error(f"Error converting BioOntology result: {e}")
            return None
