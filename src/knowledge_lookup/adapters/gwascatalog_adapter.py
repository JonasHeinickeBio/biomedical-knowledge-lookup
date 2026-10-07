"""
GWAS Catalog adapter (NHGRI-EBI GWAS Catalog REST API v2).

The Catalog curates genome-wide association studies: *studies*, the *traits* they report
(mapped to EFO / MONDO / HP terms) and the variant-trait *associations* (rsID, p-value,
effect allele, mapped genes, study accession and PMID). Data is free to reuse (CC0).

Why v2 and not the "HAL" API of the older documentation:
    The legacy endpoints (``/gwas/rest/api/efoTraits/...``, ``.../studies/search/...``)
    are deprecated and now answer ``HTTP 429`` with a retirement notice ("intentionally rate
    limited ahead of retirement"). This adapter therefore targets
    ``https://www.ebi.ac.uk/gwas/rest/api/v2`` (verified live, no key, documented limit 15
    requests/s). v2 still returns Spring-HATEOAS-style JSON (``_embedded`` / ``_links`` /
    ``page``) but with flat resources and snake_case filters.

Endpoints used (all ``GET``):

* ``efo-traits?efo_trait=<text>`` (case-insensitive substring match) and ``efo-traits/<id>``
  with ``<id>`` written ``MONDO_0005404``. The old ids from the v1 API (e.g. ``EFO_0004540``)
  may no longer exist; a 404 simply yields ``None``.
* ``associations?efo_id=<id>`` / ``associations?rs_id=<rs>`` with ``sort=p_value&direction=asc``
  and ``page``/``size`` (``size`` <= 500).
* ``single-nucleotide-polymorphisms/<rs>`` for variant details.
* ``studies?efo_id=<id>`` is only used for the study count (``page.totalElements``).

Concepts are *traits* (``MONDO:0005404``, ``EFO:0004540``, ``HP:0012378``; underscore and
colon forms are both accepted) and *variants* (``rs1801270``). The GWAS Catalog has no
trait cross-reference table (a trait is just ``efo_id`` + ``uri``), so :meth:`get_mappings`
only reports the ontology the id comes from.
"""

import asyncio
import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

GWAS_API_BASE = "https://www.ebi.ac.uk/gwas/rest/api/v2"
GWAS_WEB_BASE = "https://www.ebi.ac.uk/gwas"
MAX_PAGE_SIZE = 500  # documented API maximum
MAX_PAGES = 3  # associations are de-duplicated client-side, so allow a few extra pages

_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_TRAIT_ID_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)[_:](\d+)$")

# Ontology prefixes GWAS Catalog uses for ``efo_id`` -> (canonical prefix, source label,
# concept type). Anything else defaults to a phenotype in the ontology named by its prefix.
_DISEASE_PREFIXES = {"MONDO", "DOID", "ORPHANET", "OMIM", "ICD10", "NCIT"}
_ONTOLOGY_SOURCE = {
    "EFO": "EFO",
    "MONDO": "MONDO",
    "HP": "HPO",
    "OBA": "OBA",
    "ORPHANET": "ORPHANET",
    "DOID": "DOID",
    "GO": "GO",
    "CL": "CL",
    "NCIT": "NCIT",
    "CHEBI": "CHEBI",
}


def _normalize_id(concept_id: str) -> tuple[str, str] | None:
    """Classify an identifier as ``("variant", "rs123")`` or ``("trait", "MONDO_0005404")``.

    Returns the id in the form the API expects (underscore for traits), or ``None`` when it
    is neither an rsID nor a ``PREFIX_digits`` / ``PREFIX:digits`` trait id.
    """
    cleaned = (concept_id or "").strip()
    if cleaned.upper().startswith("GWASCATALOG:"):
        cleaned = cleaned.split(":", 1)[1]
    if _RSID_RE.match(cleaned):
        return "variant", cleaned.lower()
    match = _TRAIT_ID_RE.match(cleaned)
    if not match:
        return None
    prefix = match.group(1)
    prefix = "Orphanet" if prefix.lower() == "orphanet" else prefix.upper()
    return "trait", f"{prefix}_{match.group(2)}"


def _curie(api_id: str) -> str:
    """``MONDO_0005404`` -> ``MONDO:0005404``."""
    prefix, _, local = api_id.partition("_")
    return f"{prefix}:{local}"


class GWASCatalogAdapter(KnowledgeSourceAdapter):
    """Adapter for the NHGRI-EBI GWAS Catalog (keyless REST API v2)."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = GWAS_API_BASE

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.GWASCATALOG

    def is_available(self) -> bool:
        return True  # public, keyless

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _embedded(data: Any, key: str) -> list[dict[str, Any]]:
        """Items of ``_embedded[key]`` (absent when a query has no hit)."""
        if not isinstance(data, dict):
            return []
        items = (data.get("_embedded") or {}).get(key) or []
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _total(data: Any) -> int | None:
        if isinstance(data, dict):
            total = (data.get("page") or {}).get("totalElements")
            if isinstance(total, int):
                return total
        return None

    def _trait_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        efo_id = item.get("efo_id") or ""
        label = item.get("efo_trait") or ""
        normalized = _normalize_id(efo_id)
        if not label or not normalized or normalized[0] != "trait":
            return None
        api_id = normalized[1]
        prefix = api_id.split("_", 1)[0]
        ctype = (
            ConceptType.DISEASE if prefix.upper() in _DISEASE_PREFIXES else ConceptType.PHENOTYPE
        )
        concept = self._create_concept(_curie(api_id), label, ctype)
        concept.add_identifier(
            KnowledgeSource.GWASCATALOG, api_id, label, f"{GWAS_WEB_BASE}/efotraits/{api_id}"
        )
        if concept.categories is not None:
            concept.categories.append("gwas_trait")
        if item.get("uri") and concept.definitions is not None:
            concept.definitions.append(f"GWAS Catalog trait mapped to {item['uri']}")
        concept.confidence_score = 0.8
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.GWASCATALOG] = dict(item)  # copy: counts get added
        return concept

    def _variant_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        rs_id = item.get("rs_id") or ""
        if not _RSID_RE.match(rs_id):
            return None
        concept = self._create_concept(rs_id, rs_id, ConceptType.MOLECULAR_ENTITY)
        consequence = item.get("most_severe_consequence") or item.get("functional_class")
        parts = [consequence] if consequence else []
        locations = item.get("locations") or []
        for loc in locations[:1]:
            region = (loc.get("region") or {}).get("name")
            chrom, pos = loc.get("chromosome_name"), loc.get("chromosome_position")
            if chrom and pos:
                parts.append(f"chr{chrom}:{pos}" + (f" ({region})" if region else ""))
        if item.get("alleles"):
            parts.append(f"alleles {item['alleles']}")
        genes = item.get("mapped_genes") or []
        if genes:
            parts.append("mapped genes " + ", ".join(genes))
        if parts and concept.definitions is not None:
            concept.definitions.append("Variant: " + "; ".join(parts))
        if concept.categories is not None:
            concept.categories.append("gwas_variant")
        if consequence and concept.semantic_types is not None:
            concept.semantic_types.append(consequence)
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.GWASCATALOG] = dict(item)  # copy: counts get added
        return concept

    async def _fetch_associations(
        self, params: dict[str, Any], wanted: int, key_fn: Any
    ) -> list[dict[str, Any]]:
        """Page through ``associations`` (strongest p-value first) until ``wanted`` distinct
        ``key_fn(association)`` keys were seen or the pages run out."""
        size = min(MAX_PAGE_SIZE, max(wanted * 2, 20))
        seen: set[Any] = set()
        out: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            data = await self._make_request(
                f"{self.base_url}/associations",
                {**params, "sort": "p_value", "direction": "asc", "size": size, "page": page},
            )
            for assoc in self._embedded(data, "associations"):
                for key in key_fn(assoc):
                    if key not in seen:
                        seen.add(key)
                        out.append(assoc)
                        break
                if len(seen) >= wanted:
                    return out
            total_pages = (data.get("page") or {}).get("totalPages", 0) if data else 0
            if page + 1 >= total_pages:
                break
        return out

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search traits by label (substring), or resolve a trait id / rsID directly."""
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            normalized = _normalize_id(query)
            if normalized:
                concept = await self.get_concept_details(query)
                return [concept] if concept else []

            data = await self._make_request(
                f"{self.base_url}/efo-traits",
                {"efo_trait": query, "size": min(MAX_PAGE_SIZE, max(limit, 20))},
            )
            lowered = query.lower()
            items = self._embedded(data, "efo_traits")
            # Exact label first, then shorter (closer) labels
            items.sort(
                key=lambda it: (
                    (it.get("efo_trait") or "").lower() != lowered,
                    len(it.get("efo_trait") or ""),
                )
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in items:
                concept = self._trait_to_concept(item)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"GWAS Catalog search for '{query}' returned {len(concepts)} traits")
            return concepts
        except Exception as e:
            logger.error(f"GWAS Catalog search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for a trait (adds study / association counts) or a variant."""
        normalized = _normalize_id(concept_id)
        if not normalized:
            return None
        kind, api_id = normalized
        try:
            if kind == "variant":
                data = await self._make_request(
                    f"{self.base_url}/single-nucleotide-polymorphisms/{api_id}"
                )
                return self._variant_to_concept(data) if isinstance(data, dict) else None

            data = await self._make_request(f"{self.base_url}/efo-traits/{api_id}")
            concept = self._trait_to_concept(data) if isinstance(data, dict) else None
            if concept is None:
                return None
            await self._add_counts(concept, api_id)
            return concept
        except Exception as e:
            logger.warning(f"GWAS Catalog get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _add_counts(self, concept: UnifiedConcept, api_id: str) -> None:
        """Attach study and association counts (best effort, two tiny ``size=1`` calls)."""
        try:
            studies, assocs = await asyncio.gather(
                self._make_request(f"{self.base_url}/studies", {"efo_id": api_id, "size": 1}),
                self._make_request(f"{self.base_url}/associations", {"efo_id": api_id, "size": 1}),
            )
            n_studies, n_assocs = self._total(studies), self._total(assocs)
            if n_studies is not None and n_assocs is not None and concept.definitions is not None:
                concept.definitions.append(
                    f"{n_studies} GWAS Catalog studies and {n_assocs} associations for this trait"
                )
                if isinstance(concept.source_data, dict):
                    raw = concept.source_data.get(KnowledgeSource.GWASCATALOG)
                    if isinstance(raw, dict):
                        raw["gwas_counts"] = {"studies": n_studies, "associations": n_assocs}
        except Exception as e:
            logger.debug(f"GWAS Catalog counts unavailable for {api_id}: {e}")

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    @staticmethod
    def _assoc_extra(assoc: dict[str, Any], allele: dict[str, Any] | None) -> dict[str, Any]:
        effect = (allele or {}).get("effect_allele")
        if effect in ("?", ""):  # the Catalog uses "?" when the risk allele is not reported
            effect = None
        rs_id = (allele or {}).get("rs_id")
        return {
            "p_value": assoc.get("p_value"),
            "risk_allele": f"{rs_id}-{effect}" if rs_id and effect else None,
            "effect_allele": effect,
            "risk_frequency": assoc.get("risk_frequency"),
            "beta": assoc.get("beta"),
            "ci": [assoc.get("ci_lower"), assoc.get("ci_upper")],
            "mapped_genes": assoc.get("mapped_genes") or [],
            "study_accession": assoc.get("accession_id"),
            "pmid": assoc.get("pubmed_id"),
            "reported_trait": assoc.get("reported_trait") or [],
        }

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Trait -> associated variants; variant -> associated traits and mapped genes.

        Trait edges are ``associated_variant`` (strongest p-values first, one edge per rsID);
        variant edges are ``associated_trait`` (one per trait, best p-value) and
        ``mapped_gene``. Extra keys: ``p_value``, ``risk_allele``, ``mapped_genes``,
        ``study_accession``, ``pmid``, ``beta``, ``risk_frequency``. Degrades to ``[]``.
        """
        normalized = _normalize_id(concept_id)
        if not normalized or limit <= 0:
            return []
        kind, api_id = normalized
        try:
            if kind == "trait":
                return await self._trait_relationships(api_id, limit)
            return await self._variant_relationships(api_id, limit)
        except Exception as e:
            logger.warning(f"GWAS Catalog get_relationships failed for '{concept_id}': {e}")
            return []

    async def _trait_relationships(self, api_id: str, limit: int) -> list[dict[str, Any]]:
        def keys(assoc: dict[str, Any]) -> list[str]:
            return [a.get("rs_id") for a in assoc.get("snp_allele") or [] if a.get("rs_id")]

        assocs = await self._fetch_associations({"efo_id": api_id}, limit, keys)
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for assoc in assocs:
            for allele in assoc.get("snp_allele") or []:
                rs_id = allele.get("rs_id")
                if not rs_id or rs_id in seen:
                    continue
                seen.add(rs_id)
                edges.append(
                    {
                        "relation_label": "associated_variant",
                        "related_id": rs_id,
                        "related_name": rs_id,
                        "source": "GWASCATALOG",
                        "related_type": "variant",
                        **self._assoc_extra(assoc, allele),
                    }
                )
        return edges[:limit]

    async def _variant_relationships(self, rs_id: str, limit: int) -> list[dict[str, Any]]:
        def keys(assoc: dict[str, Any]) -> list[str]:
            return [t.get("efo_id") for t in assoc.get("efo_traits") or [] if t.get("efo_id")]

        snp, assocs = await asyncio.gather(
            self._make_request(f"{self.base_url}/single-nucleotide-polymorphisms/{rs_id}"),
            self._fetch_associations({"rs_id": rs_id}, limit, keys),
            return_exceptions=True,
        )
        edges: list[dict[str, Any]] = []
        if isinstance(assocs, BaseException):
            raise assocs
        seen: set[str] = set()
        for assoc in assocs:
            allele = next(
                (a for a in assoc.get("snp_allele") or [] if a.get("rs_id") == rs_id), None
            )
            for trait in assoc.get("efo_traits") or []:
                efo_id = trait.get("efo_id")
                if not efo_id or efo_id in seen:
                    continue
                seen.add(efo_id)
                edges.append(
                    {
                        "relation_label": "associated_trait",
                        "related_id": _curie(efo_id),
                        "related_name": trait.get("efo_trait") or efo_id,
                        "source": "GWASCATALOG",
                        "related_type": "trait",
                        **self._assoc_extra(assoc, allele),
                    }
                )
        edges = edges[:limit]
        # Mapped genes come from the variant record (a failed lookup must not drop traits)
        if isinstance(snp, dict):
            for gene in dict.fromkeys(snp.get("mapped_genes") or []):
                edges.append(
                    {
                        "relation_label": "mapped_gene",
                        "related_id": gene,
                        "related_name": gene,
                        "source": "GWASCATALOG",
                        "related_type": "gene",
                        "functional_class": snp.get("functional_class"),
                    }
                )
        return edges

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Ontology identity of a trait (the Catalog stores no further cross references).

        A trait id such as ``MONDO_0005404`` is mapped to the same term in its home ontology
        (``toSource`` ``MONDO``/``HPO``/``EFO``...); a variant maps to dbSNP.
        """
        normalized = _normalize_id(concept_id)
        if not normalized:
            return []
        kind, api_id = normalized
        if kind == "variant":
            return [
                {
                    "fromId": api_id,
                    "toId": api_id,
                    "fromSource": "GWASCATALOG",
                    "toSource": "dbSNP",
                    "mappingType": "sameAs",
                    "confidence": 1.0,
                }
            ]
        prefix = api_id.split("_", 1)[0]
        return [
            {
                "fromId": _curie(api_id),
                "toId": _curie(api_id),
                "fromSource": "GWASCATALOG",
                "toSource": _ONTOLOGY_SOURCE.get(prefix.upper(), prefix.upper()),
                "mappingType": "sameAs",
                "confidence": 1.0,
            }
        ]
