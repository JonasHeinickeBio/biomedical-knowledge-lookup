"""
UniChem Adapter

Integrates with EMBL-EBI UniChem for chemical compound cross-referencing.
UniChem provides mappings between chemical compound identifiers across different databases.
"""

import asyncio
import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..cache import get_cache
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class UniChemAdapter(KnowledgeSourceAdapter):
    """Adapter for EMBL-EBI UniChem chemical compound cross-referencing service."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        try:
            from bioservices import UniChem

            self.unichem = UniChem(verbose=False, cache=False)
        except ImportError:
            logger.error("bioservices not available. Install with: pip install bioservices")
            self.unichem = None

        # Initialize cache
        self._cache = get_cache()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.UNICHEM

    def is_available(self) -> bool:
        return self.unichem is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search UniChem for compounds by identifier.

        Args:
            query: Compound identifier (InChI, InChIKey, UCI, or source compound ID)
            limit: Maximum number of results

        Returns:
            List of unified concepts
        """
        if not self.is_available():
            return []

        try:
            concepts = await self._thread_with_retry(
                "unichem_search", self._determine_search_strategy, query, limit
            )
            logger.info(f"UniChem search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]

        except Exception as e:
            logger.error(f"UniChem search failed for '{query}': {e}")
            return []

    def _determine_search_strategy(self, query: str, limit: int) -> list[UnifiedConcept]:
        """Determine the appropriate search strategy based on query format."""
        concepts = []

        # Try different search strategies in order of specificity
        strategies = [
            self._search_by_uci,
            self._search_by_inchikey,
            self._search_by_inchi,
            self._search_by_source_id,
        ]

        for strategy in strategies:
            try:
                results = strategy(query, limit)
                if results:
                    concepts.extend(results)
                    if len(concepts) >= limit:
                        break
            except Exception:
                continue

        return concepts

    def _search_by_uci(self, query: str, limit: int) -> list[UnifiedConcept]:
        """Search by UniChem Compound Identifier (UCI)."""
        if not query.isdigit() or not self.unichem:
            return []

        # Use direct bioservices call for internal methods (not cached)
        compound_data = self.unichem.get_compounds(query, "uci")
        return self._extract_concepts_from_compound_data(compound_data, limit)

    def _search_by_inchikey(self, query: str, limit: int) -> list[UnifiedConcept]:
        """Search by InChIKey."""
        if not (len(query) == 27 and query.count("-") == 2) or not self.unichem:
            return []

        compound_data = self.unichem.get_compounds(query, "inchikey")
        return self._extract_concepts_from_compound_data(compound_data, limit)

    def _search_by_inchi(self, query: str, limit: int) -> list[UnifiedConcept]:
        """Search by InChI."""
        if not query.startswith("InChI=") or not self.unichem:
            return []

        compound_data = self.unichem.get_compounds(query, "inchi")
        return self._extract_concepts_from_compound_data(compound_data, limit)

    def _search_by_source_id(self, query: str, limit: int) -> list[UnifiedConcept]:
        """Search by source compound ID across common databases."""
        if not self.unichem:
            return []

        concepts = []
        common_sources = ["chembl", "chebi", "pubchem", "drugbank"]

        for source in common_sources:
            try:
                compound_data = self.unichem.get_compounds(query, source)
                source_concepts = self._extract_concepts_from_compound_data(compound_data, limit)
                concepts.extend(source_concepts)

                if len(concepts) >= limit:
                    break
            except Exception:
                continue

        return concepts

    def _extract_concepts_from_compound_data(
        self, compound_data: dict[str, Any] | None, limit: int
    ) -> list[UnifiedConcept]:
        """Extract UnifiedConcept objects from compound data."""
        concepts: list[UnifiedConcept] = []

        if not compound_data or "compounds" not in compound_data:
            return concepts

        for compound in compound_data["compounds"][:limit]:
            concept = self._convert_compound_to_concept(compound)
            if concept:
                concepts.append(concept)

        return concepts

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get detailed compound information from UniChem.

        Args:
            concept_id: UniChem compound identifier (UCI)

        Returns:
            Unified concept with cross-references or None if not found
        """
        if not self.is_available():
            return None

        try:
            compound_data = await self._thread_with_retry(
                "unichem_get_details", self._find_compound_data, concept_id
            )

            if compound_data and "compounds" in compound_data and compound_data["compounds"]:
                compound = compound_data["compounds"][0]
                return self._convert_compound_to_concept(compound)

            return None

        except Exception as e:
            logger.error(f"Failed to get UniChem concept details for '{concept_id}': {e}")
            return None

    async def get_cross_references(self, concept_id: str) -> dict[str, list[dict[str, str]]]:
        """
        Get cross-references for a compound from all sources, including URLs.

        Args:
            concept_id: UniChem compound identifier (UCI) or source compound ID

        Returns:
            Dictionary mapping source names to lists of compound info dicts.
            Each dict contains 'id' and 'url' keys.
        """
        if not self.is_available():
            return {}

        try:
            compound_data = self._find_compound_data(concept_id)
            if not compound_data:
                return {}

            return await self._extract_cross_references_with_urls(compound_data)

        except Exception as e:
            logger.error(f"Failed to get cross-references for '{concept_id}': {e}")
            return {}

    def _find_compound_data(self, concept_id: str) -> dict[str, Any] | None:
        """Find compound data by trying UCI first, then common sources."""
        if not self.unichem:
            return None

        # Try UCI first
        compound_data = self.unichem.get_compounds(concept_id, "uci")
        if self._is_valid_compound_data(compound_data):
            return compound_data

        # Fall back to common sources
        common_sources = ["chembl", "chebi", "pubchem", "drugbank"]
        for source in common_sources:
            try:
                compound_data = self.unichem.get_compounds(concept_id, source)
                if self._is_valid_compound_data(compound_data):
                    return compound_data
            except Exception:
                continue

        return None

    def _is_valid_compound_data(self, compound_data: dict[str, Any] | None) -> bool:
        """Check if compound data is valid and contains compounds."""
        return (
            compound_data is not None
            and "compounds" in compound_data
            and compound_data["compounds"]
        )

    async def _extract_cross_references_with_urls(
        self, compound_data: dict[str, Any]
    ) -> dict[str, list[dict[str, str]]]:
        """Extract cross-references with URLs from compound data."""
        xrefs: dict[str, list[dict[str, str]]] = {}
        compound = compound_data["compounds"][0]
        sources = compound.get("sources", [])

        for source in sources:
            source_name = self._get_source_name(source)
            compound_id_in_source = source.get("compoundId")
            source_url = source.get("url")  # URL is already provided by UniChem!

            if compound_id_in_source and source_url:
                compound_info = {"id": str(compound_id_in_source), "url": source_url}

                if source_name not in xrefs:
                    xrefs[source_name] = []
                xrefs[source_name].append(compound_info)

        return xrefs

    async def _build_compound_url(self, source_id: int, compound_id: str) -> str:
        """
        Build a URL for a compound in a specific source.

        Args:
            source_id: UniChem source ID
            compound_id: Compound identifier in that source

        Returns:
            URL string for the compound
        """
        # Common URL patterns for major chemical databases
        url_patterns = {
            1: f"https://www.ebi.ac.uk/chembl/compound_report_card/{compound_id}/",  # ChEMBL
            2: f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={compound_id}",  # ChEBI
            3: f"https://www.drugbank.ca/drugs/{compound_id}",  # DrugBank
            4: f"https://pubchem.ncbi.nlm.nih.gov/compound/{compound_id}",  # PubChem
            5: f"https://www.ebi.ac.uk/pdbe/entry/search/text:{compound_id}",  # PDBe
            6: f"https://www.uniprot.org/uniprotkb/{compound_id}/entry",  # UniProt
            7: f"https://www.ebi.ac.uk/intact/search?query={compound_id}",  # IntAct
            8: f"https://www.ebi.ac.uk/QuickGO/term/{compound_id}",  # QuickGO
            9: f"https://www.ebi.ac.uk/interpro/entry/{compound_id}/",  # InterPro
            10: f"https://www.ebi.ac.uk/ena/browser/view/{compound_id}",  # ENA
            11: f"https://www.ebi.ac.uk/arrayexpress/experiments/{compound_id}",  # ArrayExpress
            12: f"https://www.ebi.ac.uk/pride/archive/projects/{compound_id}",  # PRIDE
            13: f"https://www.ebi.ac.uk/metabolights/{compound_id}",  # Metabolights
            14: f"https://www.ebi.ac.uk/ols/ontologies/chebi/terms?iri=http://purl.obolibrary.org/obo/{compound_id}",  # noqa: E501  # ChEBI (OLS)
            15: f"https://www.ncbi.nlm.nih.gov/nuccore/{compound_id}",  # noqa: E501  # NCBI Nucleotide
            16: f"https://www.ncbi.nlm.nih.gov/protein/{compound_id}",  # noqa: E501  # NCBI Protein
            17: f"https://www.ncbi.nlm.nih.gov/gene/{compound_id}",  # noqa: E501  # NCBI Gene
            18: f"https://www.ebi.ac.uk/ols/ontologies/go/terms?iri=http://purl.obolibrary.org/obo/{compound_id}",  # noqa: E501  # GO
            19: f"https://www.ebi.ac.uk/ols/ontologies/efo/terms?iri=http://www.ebi.ac.uk/efo/{compound_id}",  # noqa: E501  # EFO
            20: f"https://www.ebi.ac.uk/ols/ontologies/hp/terms?iri=http://purl.obolibrary.org/obo/{compound_id}",  # noqa: E501  # HP
            21: f"https://www.ebi.ac.uk/ols/ontologies/mp/terms?iri=http://purl.obolibrary.org/obo/{compound_id}",  # noqa: E501  # MP
            22: f"https://www.ebi.ac.uk/ols/ontologies/ordo/terms?iri=http://www.orpha.net/ORDO/{compound_id}",  # noqa: E501  # ORDO
            23: f"https://www.ebi.ac.uk/ols/ontologies/mondo/terms?iri=http://purl.obolibrary.org/obo/{compound_id}",  # noqa: E501  # MONDO
            24: f"https://www.ebi.ac.uk/ols/ontologies/ncit/terms?iri=http://purl.obolibrary.org/obo/{compound_id}",  # noqa: E501  # NCIT
            25: f"https://www.ebi.ac.uk/ols/ontologies/omim/terms?iri=https://omim.org/entry/{compound_id}",  # noqa: E501  # OMIM
        }

        # Try to get URL from predefined patterns
        if source_id in url_patterns:
            return url_patterns[source_id]

        # For unknown sources, try to get source info and build URL
        source_info = await self.get_source_info_by_id(source_id)
        if source_info and "srcUrl" in source_info:
            base_url = source_info["srcUrl"].rstrip("/")
            # Try common URL construction patterns
            if "chembl" in base_url.lower():
                return f"{base_url}/compound_report_card/{compound_id}/"
            elif "drugbank" in base_url.lower():
                return f"{base_url}/drugs/{compound_id}"
            elif "pubchem" in base_url.lower():
                return f"{base_url}/compound/{compound_id}"
            elif "chebi" in base_url.lower():
                return f"{base_url}/searchId.do?chebiId={compound_id}"
            else:
                # Generic fallback - just append the compound ID
                return f"{base_url}/{compound_id}"

        # Final fallback - return a generic UniChem URL
        return f"https://www.ebi.ac.uk/unichem/compoundsources/{compound_id}"

    def _get_source_name(self, source: dict[str, Any]) -> str:
        """Get the best available name for a source."""
        return source.get("shortName", source.get("nameLong", f"source_{source.get('sourceID')}"))

    # Bioservices UniChem method wrappers

    async def get_all_src_ids(self) -> list[int]:
        """
        Obtain all src_ids of sources available in UniChem.

        Returns:
            List of source IDs
        """
        if not self.unichem:
            return []

        # Try cache first
        cache_key = "all_src_ids"
        cached_ids = self._cache.get(cache_key, namespace="unichem")
        if cached_ids is not None:
            logger.debug("Retrieved all source IDs from cache")
            return cached_ids

        try:
            # Run synchronous bioservices call in thread pool
            src_ids = await asyncio.to_thread(self.unichem.get_all_src_ids)

            # Cache for 24 hours (source IDs are very stable)
            if src_ids:
                self._cache.set(cache_key, src_ids, ttl=86400, namespace="unichem")
                logger.debug("Cached all source IDs for 24 hours")

            return src_ids

        except Exception as e:
            logger.error(f"Failed to get all source IDs: {e}")
            return []

    async def get_compounds(self, compound: str, source_type: str) -> dict[str, Any] | None:
        """
        Get matched compounds information.

        Args:
            compound: InChI, InChIKey, Name, UCI or Compound Source ID
            source_type: uci, inchi, inchikey, or sourceID (e.g., 'chembl')

        Returns:
            Dictionary with matched compounds and their assigned sources or None if failed
        """
        if not self.unichem:
            return None

        # Create cache key from parameters
        cache_key = f"compounds_{source_type}_{hash(compound)}"
        cached_result = self._cache.get(cache_key, namespace="unichem")
        if cached_result is not None:
            logger.debug(f"Retrieved compounds for '{compound}' from cache")
            return cached_result

        try:
            # Run synchronous bioservices call in thread pool
            result = await asyncio.to_thread(self.unichem.get_compounds, compound, source_type)

            # Cache for 1 hour (compound data is relatively stable)
            if result:
                self._cache.set(cache_key, result, ttl=3600, namespace="unichem")
                logger.debug(f"Cached compounds for '{compound}' for 1 hour")

            return result

        except Exception as e:
            logger.error(f"Failed to get compounds for '{compound}' from '{source_type}': {e}")
            return None

    async def get_connectivity(self, compound: str, source_type: str) -> dict[str, Any] | None:
        """
        Fetch multiple source data sets for a given compound with common connectivity.

        Args:
            compound: InChI, InChIKey, UCI or Compound Source ID
            source_type: uci, inchi, inchikey, or sourceID

        Returns:
            Dictionary with connectivity information or None if failed
        """
        if not self.unichem:
            return None

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_connectivity, compound, source_type)
        except Exception as e:
            logger.error(f"Failed to get connectivity for '{compound}': {e}")
            return None

    async def get_id_from_name(self, name: str) -> int | None:
        """
        Return the ID of a source given its name.

        Args:
            name: A valid database name (e.g., 'chembl')

        Returns:
            Source ID or None if not found
        """
        if not self.unichem:
            return None

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_id_from_name, name)
        except Exception as e:
            logger.error(f"Failed to get ID for source name '{name}': {e}")
            return None

    async def get_images(self, uci: str, filename: str | None = None) -> str | None:
        """
        Return/create compound image.

        Args:
            uci: The UCI of the compound
            filename: Optional filename to save the SVG+XML output

        Returns:
            SVG+XML string or None if failed
        """
        if not self.unichem:
            return None

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_images, uci, filename)
        except Exception as e:
            logger.error(f"Failed to get image for UCI '{uci}': {e}")
            return None

    async def get_inchi_from_inchikey(self, inchikey: str) -> Any:
        """
        Get a list of InChIs given a valid InChIKey.

        Args:
            inchikey: InChI Key to search

        Returns:
            List of InChIs or dictionary if input is a list
        """
        if not self.unichem:
            return []

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_inchi_from_inchikey, inchikey)
        except Exception as e:
            logger.error(f"Failed to get InChI for InChIKey '{inchikey}': {e}")
            return []

    async def get_source_info_by_id(self, source_id: int) -> dict[str, Any] | None:
        """
        Obtain all information on a source by querying with a source ID.

        Args:
            source_id: Valid source identifier

        Returns:
            Dictionary with source information or None if failed
        """
        if not self.unichem:
            return None

        # Try cache first
        cache_key = f"source_info_id_{source_id}"
        cached_info = self._cache.get(cache_key, namespace="unichem")
        if cached_info is not None:
            logger.debug(f"Retrieved source info for ID {source_id} from cache")
            return cached_info

        try:
            # Run synchronous bioservices call in thread pool
            source_info = await asyncio.to_thread(self.unichem.get_source_info_by_id, source_id)

            # Cache for 24 hours (source info is very stable)
            if source_info:
                self._cache.set(cache_key, source_info, ttl=86400, namespace="unichem")
                logger.debug(f"Cached source info for ID {source_id} for 24 hours")

            return source_info

        except Exception as e:
            logger.error(f"Failed to get source info for ID {source_id}: {e}")
            return None

    async def get_source_info_by_name(self, source_name: str) -> dict[str, Any] | None:
        """
        Obtain all information on a source by querying with a source name.

        Args:
            source_name: Valid source name (e.g., 'chembl')

        Returns:
            Dictionary with source information or None if failed
        """
        if not self.unichem:
            return None

        # Try cache first
        cache_key = f"source_info_name_{source_name}"
        cached_info = self._cache.get(cache_key, namespace="unichem")
        if cached_info is not None:
            logger.debug(f"Retrieved source info for name '{source_name}' from cache")
            return cached_info

        try:
            # Run synchronous bioservices call in thread pool
            source_info = await asyncio.to_thread(
                self.unichem.get_source_info_by_name, source_name
            )

            # Cache for 24 hours (source info is very stable)
            if source_info:
                self._cache.set(cache_key, source_info, ttl=86400, namespace="unichem")
                logger.debug(f"Cached source info for name '{source_name}' for 24 hours")

            return source_info

        except Exception as e:
            logger.error(f"Failed to get source info for name '{source_name}': {e}")
            return None

    async def get_sources(self) -> dict[str, Any] | None:
        """
        Get all information about all sources used in UniChem.

        Returns:
            Dictionary with sources information or None if failed
        """
        if not self.unichem:
            return None

        # Try cache first
        cache_key = "unichem_sources"
        cached_sources = self._cache.get(cache_key, namespace="unichem")
        if cached_sources is not None:
            logger.debug("Retrieved UniChem sources from cache")
            return cached_sources

        try:
            # Run synchronous bioservices call in thread pool
            sources_data = await asyncio.to_thread(self.unichem.get_sources)

            # Cache for 24 hours (sources don't change frequently)
            if sources_data:
                self._cache.set(cache_key, sources_data, ttl=86400, namespace="unichem")
                logger.debug("Cached UniChem sources for 24 hours")

            return sources_data

        except Exception as e:
            logger.error(f"Failed to get sources: {e}")
            return None

    async def get_sources_by_inchikey(self, inchikey: str) -> Any:
        """
        Get sources by InChIKey.

        Args:
            inchikey: InChI Key to search

        Returns:
            List of sources or dictionary if input is a list
        """
        if not self.unichem:
            return []

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_sources_by_inchikey, inchikey)
        except Exception as e:
            logger.error(f"Failed to get sources for InChIKey '{inchikey}': {e}")
            return []

    async def get_sources_by_inchikey_verbose(self, inchikey: str) -> Any:
        """
        Get sources by InChIKey (verbose version).

        Args:
            inchikey: InChI Key to search

        Returns:
            List of sources with details or dictionary if input is a list
        """
        if not self.unichem:
            return []

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_sources_by_inchikey_verbose, inchikey)
        except Exception as e:
            logger.error(f"Failed to get verbose sources for InChIKey '{inchikey}': {e}")
            return []

    async def get_structure(self, compound_id: str, src_id: str) -> dict[str, Any] | None:
        """
        Obtain structure(s) CURRENTLY assigned to a query compound ID.

        Args:
            compound_id: A valid compound identifier
            src_id: Corresponding database identifier (name or ID)

        Returns:
            Dictionary with 'standardinchi' and 'standardinchikey' keys or None if failed
        """
        if not self.unichem:
            return None

        try:
            # Run synchronous bioservices call in thread pool
            return await asyncio.to_thread(self.unichem.get_structure, compound_id, src_id)
        except Exception as e:
            logger.error(
                f"Failed to get structure for compound '{compound_id}' from source '{src_id}': {e}"
            )
            return None

    def _convert_compound_to_concept(self, compound: dict[str, Any]) -> UnifiedConcept | None:
        """
        Convert UniChem compound data to UnifiedConcept.

        Args:
            compound: Compound data from UniChem

        Returns:
            UnifiedConcept or None if conversion fails
        """
        try:
            uci = compound.get("uci")
            if not uci:
                return None

            concept = self._create_base_concept(uci)
            self._add_unichem_identifier(concept, uci)
            self._add_source_identifiers(concept, compound)
            self._add_source_categories(concept, compound)
            self._set_concept_metadata(concept, compound)

            return concept

        except Exception as e:
            logger.error(f"Error converting UniChem compound to concept: {e}")
            return None

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache performance statistics for this adapter.

        Returns:
            Dictionary with cache statistics
        """
        return self._cache.get_stats()

    def clear_cache(self, namespace: str = "unichem") -> None:
        """
        Clear cached data for this adapter.

        Args:
            namespace: Cache namespace to clear (default: 'unichem')
        """
        self._cache.clear(namespace)
        logger.info(f"Cleared UniChem cache for namespace '{namespace}'")

    def _create_base_concept(self, uci: str) -> UnifiedConcept:
        """Create the base UnifiedConcept with primary information."""
        return UnifiedConcept(
            primary_id=str(uci), primary_label=f"UCI_{uci}", concept_type=ConceptType.CHEMICAL
        )

    def _add_unichem_identifier(self, concept: UnifiedConcept, uci: str) -> None:
        """Add the primary UniChem identifier."""
        concept.add_identifier(
            KnowledgeSource.UNICHEM,
            str(uci),
            "UniChem Compound Identifier",
            f"https://www.ebi.ac.uk/unichem/compounds/{uci}",
        )

    def _add_source_identifiers(self, concept: UnifiedConcept, compound: dict[str, Any]) -> None:
        """Add identifiers from all sources."""
        sources = compound.get("sources", [])

        for source in sources:
            source_name = self._get_source_name(source)
            compound_id_in_source = source.get("compoundId")
            url = source.get("url", "")

            if compound_id_in_source:
                concept.add_identifier(
                    KnowledgeSource.UNICHEM,
                    str(compound_id_in_source),
                    f"{source_name} ID",
                    url,
                )

    def _add_source_categories(self, concept: UnifiedConcept, compound: dict[str, Any]) -> None:
        """Add source names as categories."""
        sources = compound.get("sources", [])
        source_names = [s.get("shortName", "") for s in sources if s.get("shortName")]
        concept.categories.extend(source_names)

    def _set_concept_metadata(self, concept: UnifiedConcept, compound: dict[str, Any]) -> None:
        """Set confidence score and source data."""
        concept.confidence_score = 0.9
        concept.source_data[KnowledgeSource.UNICHEM] = compound
