"""
NCBI Taxonomy adapter.

NCBI Taxonomy is the reference classification of organisms in GenBank and most sequence
and metabolomics resources. For this library it provides the identifier hub for pathogens
and host species relevant to Long COVID and ME/CFS (SARS-CoV-2 ``2697049``, Epstein-Barr
virus ``10376``, HHV-6A/B ``32603``/``32604``, enteroviruses ``12059``) and their lineages.

Served by the NCBI Datasets taxonomy API v2 (keyless), verified live 2026-10:

* ``taxon_suggest/{text}?tax_rank_filter=higher_taxon`` searches names, synonyms and common
  names. The default ``species`` filter drops viruses without a species rank (SARS-CoV-2
  itself has no rank in NCBI Taxonomy) and returns unrelated species; ``higher_taxon`` still
  returns species. Entries carry ``sci_name``, ``tax_id`` (a string), ``common_name``,
  ``matched_term`` (the synonym that matched), ``rank`` (absent for "no rank") and
  ``group_name`` (BLAST name, e.g. ``viruses``).
* ``taxon/{ids}/dataset_report`` returns the scientific name, ``rank`` (absent for no
  rank), the ``classification`` block, ``parents`` (the whole lineage as taxids, root first,
  the node itself excluded), ``children`` (taxids), genome/gene counts, ``secondary_tax_ids``
  (merged ids) and the genetic code. It accepts a comma-separated list and returns reports in
  taxid order, not lineage order, so ancestor names/ranks cost one extra call that is
  re-ordered by the ``parents`` list. A merged id (``47902``) resolves to its current node.
* ``taxon/{id}/name_report`` holds ``informal_names`` and ``other_common_names`` (GenBank
  synonyms and acronyms such as ``EBV``), used as synonyms.
* ``taxon/{id}/links`` exposes the Wikipedia and Encyclopedia of Life pages when known.
* Unknown ids and names answer HTTP 200 with an ``errors`` entry (no 404).

Rate limit: the service advertises 5 requests/s without a key (``x-ratelimit-limit``) and
10/s with an NCBI key. The adapter spaces calls at 3/s keyless (as for NCBI E-utilities) and
10/s when ``NCBI_API_KEY`` (or ``ncbi`` in the config's ``api_keys``) is set, sent in the
``api-key`` header. NCBI data are in the public domain; NCBI asks users to cite it.
"""

import asyncio
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

DATASETS_BASE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy"
OBO_PURL = "http://purl.obolibrary.org/obo/NCBITaxon_"
BROWSER_URL = "https://www.ncbi.nlm.nih.gov/datasets/taxonomy/"

_MAX_SEARCH = 100
_MAX_SYNONYMS = 50
_DEFAULT_CHILDREN = 25
_MIN_INTERVAL_KEYLESS = 0.34  # 3 requests/s
_MIN_INTERVAL_KEYED = 0.11  # 10 requests/s

_ID_RE = re.compile(r"^\d{1,10}$")
_PREFIX_RE = re.compile(r"^(?:ncbitaxon|ncbi_taxon|taxid|txid|tax_id|taxon|ncbi)\s*[:_]\s*", re.I)


class NCBITaxonomyAdapter(KnowledgeSourceAdapter):
    """NCBI Taxonomy through the keyless NCBI Datasets v2 API (about 3 requests/s)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = DATASETS_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.NCBITAXONOMY

    def is_available(self) -> bool:
        return True  # public API; an NCBI key only raises the polite request rate

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _api_key(self) -> str | None:
        return self.config.get_api_key("ncbi") or os.getenv("NCBI_API_KEY") or None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``{base}/{path}``, spacing calls to NCBI's rate limit."""
        api_key = self._api_key()
        interval = _MIN_INTERVAL_KEYED if api_key else _MIN_INTERVAL_KEYLESS
        headers = {"Accept": "application/json"}
        if api_key:
            headers["api-key"] = api_key
        async with self._throttle_lock:
            wait = interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(f"{self.base_url}/{path}", params, headers)
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> str | None:
        """Bare taxid from ``NCBITaxon:2697049``, ``taxid:2697049`` or ``2697049``."""
        text = _PREFIX_RE.sub("", (concept_id or "").strip())
        if not _ID_RE.match(text) or int(text) <= 0:
            return None
        return str(int(text))

    async def _reports(self, tax_ids: list[str]) -> list[dict[str, Any]]:
        """``dataset_report`` taxonomy blocks for ``tax_ids`` (unknown ids are dropped)."""
        if not tax_ids:
            return []
        data = await self._get(
            f"taxon/{','.join(tax_ids)}/dataset_report", {"page_size": max(len(tax_ids), 1)}
        )
        out = []
        for report in data.get("reports") or []:
            tax = report.get("taxonomy") if isinstance(report, dict) else None
            if isinstance(tax, dict) and tax.get("tax_id") is not None:
                out.append(tax)
        return out

    async def _report(self, concept_id: str) -> dict[str, Any] | None:
        tax_id = self._parse_id(concept_id)
        if tax_id is None:
            return None
        reports = await self._reports([tax_id])
        return reports[0] if reports else None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search taxon names, synonyms and common names; a taxid goes straight to details."""
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            if self._parse_id(text) is not None:
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            data = await self._get(
                f"taxon_suggest/{text.replace('/', ' ')}", {"tax_rank_filter": "higher_taxon"}
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank_pos, item in enumerate(data.get("sci_name_and_ids") or []):
                concept = self._suggest_to_concept(item)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concept.confidence_score = max(0.5, 0.9 - 0.02 * rank_pos)
                concepts.append(concept)
                if len(concepts) >= min(limit, _MAX_SEARCH):
                    break
            logger.info(f"NCBI Taxonomy search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"NCBI Taxonomy search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Taxon record: name, rank, lineage, synonyms (GenBank/common names), counts."""
        try:
            tax = await self._report(concept_id)
            if tax is None:
                return None
            concept = self._report_to_concept(tax)
            if concept is None:
                return None
            # synonyms live in a separate report; losing them must not lose the record
            try:
                names = await self._get(f"taxon/{tax['tax_id']}/name_report")
                self._add_synonyms(concept, names)
            except Exception as e:
                logger.warning(f"NCBI Taxonomy name_report failed for {tax['tax_id']}: {e}")
            concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"NCBI Taxonomy get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Mappings / relationships
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """OBO ``NCBITaxon`` id, merged (secondary) taxids, Wikipedia and EOL pages.

        ``NCBITaxon:<id>`` is the same taxon in the OBO ontology (``exactMatch``); merged taxids
        are ids NCBI retired into this node; Wikipedia/EOL come from the ``links`` endpoint and
        are ``xref`` pages describing the taxon (not guaranteed to match its exact rank).
        """
        try:
            tax = await self._report(concept_id)
            if tax is None:
                return []
            tax_id = str(tax["tax_id"])
            mappings: list[dict[str, Any]] = []

            def add(to_id: str, to_source: str, mapping_type: str, confidence: float) -> None:
                if all(m["toId"] != to_id for m in mappings):
                    mappings.append(
                        {
                            "fromId": tax_id,
                            "toId": to_id,
                            "fromSource": "NCBITAXONOMY",
                            "toSource": to_source,
                            "mappingType": mapping_type,
                            "confidence": confidence,
                        }
                    )

            add(f"NCBITaxon:{tax_id}", "NCBITAXON", "exactMatch", 1.0)
            for secondary in tax.get("secondary_tax_ids") or []:
                add(f"NCBITaxon:{secondary}", "NCBITAXON", "merged_id", 1.0)
            try:
                links = await self._get(f"taxon/{tax_id}/links")
            except Exception as e:
                logger.warning(f"NCBI Taxonomy links failed for {tax_id}: {e}")
                links = {}
            if links.get("wikipedia"):
                add(str(links["wikipedia"]), "WIKIPEDIA", "xref", 0.9)
            if links.get("encyclopedia_of_life"):
                add(str(links["encyclopedia_of_life"]), "EOL", "xref", 0.9)
            return mappings
        except Exception as e:
            logger.error(f"NCBI Taxonomy get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_relationships(
        self, concept_id: str, limit: int = _DEFAULT_CHILDREN
    ) -> list[dict[str, Any]]:
        """Parent, lineage ancestors and children of a taxon.

        ``is_a`` is the direct parent, ``descendant_of`` every higher ancestor (root first,
        each with its ``rank`` and ``depth`` from the root) and ``has_subclass`` the child
        taxa, capped at ``limit`` (genera such as Enterovirus have hundreds). Names and ranks
        come from a single extra ``dataset_report`` call for all related taxids.
        """
        if limit <= 0:
            return []
        try:
            tax = await self._report(concept_id)
            if tax is None:
                return []
            lineage = [str(i) for i in tax.get("parents") or []]
            children = [str(i) for i in (tax.get("children") or [])[:limit]]
            by_id = {str(t["tax_id"]): t for t in await self._reports(lineage + children)}
            relationships: list[dict[str, Any]] = []

            def add(label: str, rel_id: str, **extra: Any) -> None:
                node = by_id.get(rel_id)
                if node is None:
                    return
                name = (node.get("current_scientific_name") or {}).get("name") or rel_id
                relationships.append(
                    {
                        "relation_label": label,
                        "related_id": f"NCBITaxon:{rel_id}",
                        "related_name": name,
                        "source": "NCBITAXONOMY",
                        "rank": self._rank(node),
                        **extra,
                    }
                )

            if lineage:
                add("is_a", lineage[-1])
                for depth, ancestor in enumerate(lineage[:-1]):
                    add("descendant_of", ancestor, depth=depth)
            for child in children:
                add("has_subclass", child)
            return relationships
        except Exception as e:
            logger.error(f"NCBI Taxonomy get_relationships failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _rank(node: dict[str, Any]) -> str:
        """Lower-case rank, ``no rank`` where NCBI omits it (e.g. SARS-CoV-2, root)."""
        rank = str(node.get("rank") or "NO_RANK")
        return rank.replace("_", " ").lower()

    @staticmethod
    def _add_unique(target: list[str] | None, value: Any, limit: int = _MAX_SYNONYMS) -> None:
        if target is None or not isinstance(value, str):
            return
        value = value.strip()
        if (
            value
            and len(target) < limit
            and value.casefold() not in {t.casefold() for t in target}
        ):
            target.append(value)

    def _suggest_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        tax_id, name = str(item.get("tax_id") or ""), item.get("sci_name")
        if not tax_id.isdigit() or not name:
            return None
        concept = self._create_concept(tax_id, str(name), ConceptType.ORGANISM)
        concept.add_identifier(
            self.get_source(), f"NCBITaxon:{tax_id}", str(name), f"{BROWSER_URL}{tax_id}"
        )
        if concept.synonyms is not None:
            for alt in (item.get("common_name"), item.get("matched_term")):
                if isinstance(alt, str) and alt.strip().casefold() != str(name).casefold():
                    self._add_unique(concept.synonyms, alt)
        rank = self._rank(item)
        if concept.semantic_types is not None:
            concept.semantic_types.append(rank)
        if concept.categories is not None and item.get("group_name"):
            concept.categories.append(str(item["group_name"]))
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "tax_id": tax_id,
                "rank": rank,
                "matched_term": item.get("matched_term"),
                "group_name": item.get("group_name"),
            }
        return concept

    def _report_to_concept(self, tax: dict[str, Any]) -> UnifiedConcept | None:
        tax_id = str(tax.get("tax_id") or "")
        name = (tax.get("current_scientific_name") or {}).get("name")
        if not tax_id or not name:
            return None
        concept = self._create_concept(tax_id, str(name), ConceptType.ORGANISM)
        concept.add_identifier(
            self.get_source(), f"NCBITaxon:{tax_id}", str(name), f"{BROWSER_URL}{tax_id}"
        )
        self._add_unique(concept.synonyms, tax.get("curator_common_name"))
        rank = self._rank(tax)
        if concept.semantic_types is not None:
            concept.semantic_types.append(rank)
        classification = tax.get("classification") or {}
        if concept.categories is not None:
            if tax.get("group_name"):
                concept.categories.append(str(tax["group_name"]))
            if tax.get("genomic_moltype"):
                concept.categories.append(f"moltype:{tax['genomic_moltype']}")
        lineage = {
            level: node.get("name")
            for level, node in classification.items()
            if isinstance(node, dict) and node.get("name")
        }
        counts = {
            str(c.get("type", "")).removeprefix("COUNT_TYPE_").lower(): c.get("count")
            for c in tax.get("counts") or []
            if isinstance(c, dict)
        }
        if concept.definitions is not None:
            summary = f"NCBI Taxonomy {rank} (taxid {tax_id})"
            if lineage:
                summary += ": " + " > ".join(str(v) for v in lineage.values())
            concept.definitions.append(summary)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "tax_id": tax_id,
                "rank": rank,
                "classification": lineage,
                "parents": tax.get("parents") or [],
                "children": tax.get("children") or [],
                "counts": counts,
                "genomic_moltype": tax.get("genomic_moltype"),
                "secondary_tax_ids": tax.get("secondary_tax_ids") or [],
                "authority": (tax.get("current_scientific_name") or {}).get("authority"),
            }
        return concept

    def _add_synonyms(self, concept: UnifiedConcept, data: dict[str, Any]) -> None:
        for report in data.get("reports") or []:
            tax = report.get("taxonomy") if isinstance(report, dict) else None
            if not isinstance(tax, dict):
                continue
            informal = (tax.get("current_scientific_name") or {}).get("informal_names") or []
            for name in [*(tax.get("other_common_names") or []), *informal]:
                self._add_unique(concept.synonyms, name)
