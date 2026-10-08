"""
eQTL Catalogue adapter (dataset / study / tissue metadata only).

The eQTL Catalogue (EMBL-EBI, Kerimov et al., Nat Genet 2021) re-processes public expression,
splicing and protein QTL studies uniformly. **Its REST API is gone**: every path under
``https://www.ebi.ac.uk/eqtl/api`` (``/v1``, ``/v2``, ``/v3``, ``/associations``, ``/studies``,
``/api-docs``) answers HTTP 410 "This API is no longer available" (verified live 2026-10), and
the Data access page states "The RESTful API has now been deprecated and is no longer
available". Association data are only published as bulk files on the EBI FTP site
(``sumstats/<QTS>/<QTD>/<QTD>.all.tsv.gz``, up to ~3 GB per dataset, plain HTTP / FTP only,
being migrated from tabix TSV to parquet in release 8). The EBI firewall treats frequent tabix
requests as denial of service. Those files are far too large and the transport too weak for
this library, so **gene -> eQTL variant and variant -> gene queries are deliberately not
implemented**; use the GTEx adapter (tissue eQTLs of one gene, keyless API) or the Open Targets
adapter (credible sets from this catalogue) for association questions.

What is verifiable and what this adapter serves is the catalogue's **dataset table**, published
by the project on GitHub (``data_tables/dataset_metadata_<release>.tsv``, tab separated, 76 KB for
release 7: 758 datasets, 42 studies, 99 tissues / cell types / conditions). Columns:
``study_id`` (QTS), ``dataset_id`` (QTD), ``study_label``, ``sample_group``, ``tissue_id``
(``UBERON_...``, ``CL_...``, ``EFO_...`` or ``BTO_...``), ``tissue_label``, ``condition_label``
(``naive`` or a stimulus), ``sample_size``, ``quant_method`` (``ge`` gene expression, ``exon``,
``tx`` transcript usage, ``txrev`` transcript events, ``leafcutter`` splicing, ``microarray``,
``aptamer`` protein), ``pmid`` and ``study_type`` (``bulk`` / ``single-cell``). Release 7 is the
default; ``EQTLCATALOGUE_RELEASE=r8_beta`` selects the pre-release table (GTEx v10, MAGE, IBDverse;
final release 8 is announced for December 2026). The table is fetched once per hour at most.

Data licence: Creative Commons Attribution 4.0 (code Apache 2.0). Cite Kerimov et al. 2021
(PMID 34493867) and eQTL Catalogue 2023 (PLoS Genet, PMID 37751440) plus the original study.
"""

import asyncio
import csv
import io
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

METADATA_URL = (
    "https://raw.githubusercontent.com/eQTL-Catalogue/eQTL-Catalogue-resources/master/"
    "data_tables/dataset_metadata_{release}.tsv"
)
DEFAULT_RELEASE = "r7"
RELEASES = ("r7", "r8_beta")
_CACHE_TTL = 3600.0
_MAX_SEARCH = 100
_DEFAULT_RELATION_LIMIT = 25

_QTD_RE = re.compile(r"^QTD\d{6}$", re.IGNORECASE)
_QTS_RE = re.compile(r"^QTS\d{6}$", re.IGNORECASE)
_ONTOLOGY_RE = re.compile(r"^(UBERON|CL|EFO|BTO)[:_](\d+)$", re.IGNORECASE)
_PREFIX_RE = re.compile(r"^(?:eqtlcatalogue|eqtl|eqtl_catalogue)\s*:\s*", re.IGNORECASE)

_QUANT_METHODS = {
    "ge": "gene expression (eQTL)",
    "exon": "exon expression",
    "tx": "transcript usage",
    "txrev": "transcript event usage",
    "leafcutter": "splice junction usage (sQTL)",
    "microarray": "microarray gene expression",
    "aptamer": "protein abundance (pQTL, aptamer)",
}
_REQUIRED_COLUMNS = {"study_id", "dataset_id", "tissue_id", "quant_method"}


def _ontology_id(raw: str) -> str:
    """``UBERON_0000178`` -> ``UBERON:0000178`` (metadata uses underscores)."""
    match = _ONTOLOGY_RE.match((raw or "").strip())
    return f"{match.group(1).upper()}:{match.group(2)}" if match else (raw or "").strip()


class EQTLCatalogueAdapter(KnowledgeSourceAdapter):
    """Adapter for the eQTL Catalogue dataset table (datasets, studies, tissues)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        requested = os.getenv("EQTLCATALOGUE_RELEASE", DEFAULT_RELEASE).strip().lower()
        self.release = requested if requested in RELEASES else DEFAULT_RELEASE
        if requested != self.release:
            logger.warning(f"Unknown EQTLCATALOGUE_RELEASE '{requested}', using {DEFAULT_RELEASE}")
        self.metadata_url = METADATA_URL.format(release=self.release)
        self._table: tuple[float, list[dict[str, str]]] | None = None
        self._lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.EQTLCATALOGUE

    def is_available(self) -> bool:
        return True  # public file on GitHub, no key

    # ------------------------------------------------------------------
    # Dataset table
    # ------------------------------------------------------------------

    async def _datasets(self) -> list[dict[str, str]]:
        """All dataset rows (cached for an hour); raises when the table cannot be read."""
        async with self._lock:
            cached = self._table
            if cached and time.monotonic() - cached[0] < _CACHE_TTL:
                return cached[1]
            text = await self._make_request_text(self.metadata_url)
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not _REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
                raise ValueError(f"unexpected eQTL Catalogue table header: {reader.fieldnames}")
            rows = [
                {k: (v or "").strip() for k, v in row.items() if k}
                for row in reader
                if row.get("dataset_id")
            ]
            self._table = (time.monotonic(), rows)
            return rows

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("dataset", "QTD000021")``, ``("study", "QTS000002")`` or ``("term", "CL:0000235")``."""
        text = _PREFIX_RE.sub("", (concept_id or "").strip())
        if _QTD_RE.match(text):
            return "dataset", text.upper()
        if _QTS_RE.match(text):
            return "study", text.upper()
        match = _ONTOLOGY_RE.match(text)
        if match:
            return "term", f"{match.group(1).upper()}:{match.group(2)}"
        return None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Tissues / cell types, studies and datasets whose metadata contain every token.

        The catalogue has no gene or variant search any more (see the module docstring), so
        gene symbols and rsIDs find nothing. Order: tissues, studies, then datasets (a tissue
        has up to ~7 datasets, one per quantification method).
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            rows = await self._datasets()
        except Exception as e:
            logger.error(f"eQTL Catalogue search failed for '{text}': {e}")
            return []
        limit = min(limit, _MAX_SEARCH)
        if self._parse_id(text) is not None:  # an exact QTD / QTS / ontology id
            exact = await self.get_concept_details(text)
            return [exact] if exact else []
        tokens = [t for t in re.split(r"[\s,;/]+", text.casefold()) if t]
        matching = [r for r in rows if all(t in self._haystack(r) for t in tokens)]
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()

        def add(concept: UnifiedConcept | None, score: float) -> None:
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concept.confidence_score = score
                concepts.append(concept)

        for row in matching:
            label = row.get("tissue_label", "").casefold()
            add(self._tissue_concept(row, rows), 0.9 if label == text.casefold() else 0.75)
        for row in matching:
            label = row.get("study_label", "").casefold()
            add(self._study_concept(row, rows), 0.9 if label == text.casefold() else 0.7)
        for row in matching:
            add(self._dataset_concept(row), 0.6)
        logger.info(f"eQTL Catalogue search for '{text}' returned {len(concepts[:limit])}")
        return concepts[:limit]

    @staticmethod
    def _haystack(row: dict[str, str]) -> str:
        fields = (
            "dataset_id",
            "study_id",
            "study_label",
            "sample_group",
            "tissue_id",
            "tissue_label",
            "condition_label",
            "quant_method",
            "pmid",
            "study_type",
        )
        text = " ".join(row.get(f, "") for f in fields).casefold()
        return text + " " + _QUANT_METHODS.get(row.get("quant_method", ""), "").casefold()

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Dataset (``QTD000021``), study (``QTS000002``) or tissue / cell type (``CL:0000235``)."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        try:
            rows = await self._datasets()
            kind, value = parsed
            if kind == "dataset":
                row = next((r for r in rows if r["dataset_id"].upper() == value), None)
                return self._dataset_concept(row, confidence=0.95) if row else None
            if kind == "study":
                row = next((r for r in rows if r["study_id"].upper() == value), None)
                return self._study_concept(row, rows, confidence=0.95) if row else None
            row = next((r for r in rows if _ontology_id(r["tissue_id"]) == value), None)
            return self._tissue_concept(row, rows, confidence=0.95) if row else None
        except Exception as e:
            logger.error(f"eQTL Catalogue get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Mappings / relationships
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Ontology term (tissue / cell type) of a dataset or tissue and the PMID of a study.

        Dataset -> its tissue term and PMID; study -> PMID; tissue term -> itself (so the term
        can be fed to the UBERON / Cell Ontology adapters). The ontology id is taken as
        published (``EFO`` and ``BTO`` terms occur for cell lines and iPSC derivatives).
        """
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return []
        try:
            rows = await self._datasets()
        except Exception as e:
            logger.error(f"eQTL Catalogue get_mappings failed for '{concept_id}': {e}")
            return []
        kind, value = parsed
        targets: list[tuple[str, str]] = []
        if kind == "dataset":
            row = next((r for r in rows if r["dataset_id"].upper() == value), None)
            if row:
                targets = self._term_and_pmid(row)
        elif kind == "study":
            row = next((r for r in rows if r["study_id"].upper() == value), None)
            if row and row.get("pmid"):
                targets = [("PMID", f"PMID:{row['pmid']}")]
        else:
            row = next((r for r in rows if _ontology_id(r["tissue_id"]) == value), None)
            if row:
                targets = [(value.split(":")[0], value)]
        return [
            {
                "fromId": value,
                "toId": to_id,
                "fromSource": "EQTLCATALOGUE",
                "toSource": to_source,
                "mappingType": "exact" if kind == "term" else "annotation",
                "confidence": 0.95,
            }
            for to_source, to_id in targets
        ]

    @staticmethod
    def _term_and_pmid(row: dict[str, str]) -> list[tuple[str, str]]:
        term = _ontology_id(row.get("tissue_id", ""))
        out: list[tuple[str, str]] = []
        if term:
            out.append((term.split(":")[0], term))
        if row.get("pmid"):
            out.append(("PMID", f"PMID:{row['pmid']}"))
        return out

    async def get_relationships(
        self, concept_id: str, limit: int = _DEFAULT_RELATION_LIMIT
    ) -> list[dict[str, Any]]:
        """Dataset -> study / tissue; study -> datasets / tissues; tissue -> datasets / studies.

        ``limit`` caps each repeated relation type. Dataset order is the table order (study,
        then quantification method). There are no gene or variant edges (see module docstring).
        """
        parsed = self._parse_id(concept_id)
        if parsed is None or limit <= 0:
            return []
        try:
            rows = await self._datasets()
        except Exception as e:
            logger.error(f"eQTL Catalogue get_relationships failed for '{concept_id}': {e}")
            return []
        kind, value = parsed
        if kind == "dataset":
            row = next((r for r in rows if r["dataset_id"].upper() == value), None)
            return self._dataset_edges(row) if row else []
        if kind == "study":
            study_rows = [r for r in rows if r["study_id"].upper() == value]
            if not study_rows:
                return []
            return self._tissue_edges(study_rows, limit) + self._dataset_list_edges(
                study_rows, limit
            )
        term_rows = [r for r in rows if _ontology_id(r["tissue_id"]) == value]
        if not term_rows:
            return []
        return self._study_edges(term_rows, limit) + self._dataset_list_edges(term_rows, limit)

    @staticmethod
    def _edge(label: str, related_id: str, related_name: str, **extra: Any) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": related_id,
            "related_name": related_name,
            "source": "EQTLCATALOGUE",
            **extra,
        }

    def _dataset_edges(self, row: dict[str, str]) -> list[dict[str, Any]]:
        edges = [
            self._edge(
                "part_of_study",
                row["study_id"],
                row.get("study_label", ""),
                study_type=row.get("study_type"),
            ),
            self._edge(
                "profiled_in_tissue",
                _ontology_id(row["tissue_id"]),
                row.get("tissue_label", ""),
                condition=row.get("condition_label"),
                sample_group=row.get("sample_group"),
            ),
        ]
        if row.get("pmid"):
            edges.append(self._edge("described_in", f"PMID:{row['pmid']}", f"PMID {row['pmid']}"))
        return edges

    def _tissue_edges(self, rows: list[dict[str, str]], limit: int) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            term = _ontology_id(row["tissue_id"])
            if term in seen:
                continue
            seen.add(term)
            edges.append(
                self._edge(
                    "profiles_tissue",
                    term,
                    row.get("tissue_label", ""),
                    condition=row.get("condition_label"),
                    sample_size=row.get("sample_size"),
                )
            )
            if len(edges) >= limit:
                break
        return edges

    def _study_edges(self, rows: list[dict[str, str]], limit: int) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if row["study_id"] in seen:
                continue
            seen.add(row["study_id"])
            edges.append(
                self._edge(
                    "profiled_in_study",
                    row["study_id"],
                    row.get("study_label", ""),
                    study_type=row.get("study_type"),
                )
            )
            if len(edges) >= limit:
                break
        return edges

    def _dataset_list_edges(self, rows: list[dict[str, str]], limit: int) -> list[dict[str, Any]]:
        return [
            self._edge(
                "has_dataset",
                row["dataset_id"],
                f"{row.get('study_label', '')} {row.get('tissue_label', '')} "
                f"({row.get('quant_method', '')})".strip(),
                quant_method=row.get("quant_method"),
                condition=row.get("condition_label"),
                sample_size=row.get("sample_size"),
            )
            for row in rows[:limit]
        ]

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _dataset_concept(
        self, row: dict[str, str], confidence: float | None = None
    ) -> UnifiedConcept | None:
        dataset_id = row.get("dataset_id")
        if not dataset_id:
            return None
        quant = row.get("quant_method", "")
        label = (
            f"{row.get('study_label', '')} - {row.get('tissue_label', '')}"
            f" ({row.get('condition_label', '')}, {quant})"
        )
        concept = self._create_concept(dataset_id, label, ConceptType.ASSAY)
        if concept.definitions is not None:
            concept.definitions.append(
                f"{_QUANT_METHODS.get(quant, quant)} QTL dataset of {row.get('study_label', '')}: "
                f"{row.get('tissue_label', '')}, {row.get('condition_label', '')}, "
                f"n={row.get('sample_size', '?')}"
            )
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {
                "release": self.release,
                "study_id": row.get("study_id"),
                "study_label": row.get("study_label"),
                "sample_group": row.get("sample_group"),
                "tissue_id": _ontology_id(row.get("tissue_id", "")),
                "tissue_label": row.get("tissue_label"),
                "condition": row.get("condition_label"),
                "sample_size": row.get("sample_size"),
                "quant_method": quant,
                "quant_method_description": _QUANT_METHODS.get(quant),
                "pmid": row.get("pmid") or None,
                "study_type": row.get("study_type"),
            }
            if self.release == "r7":  # file layout verified for release 7 only
                data["sumstats_url"] = (
                    "ftp://ftp.ebi.ac.uk/pub/databases/spot/eQTL/sumstats/"
                    f"{row.get('study_id')}/{dataset_id}/{dataset_id}.all.tsv.gz"
                )
            concept.source_data[self.get_source()] = data
        if confidence is not None:
            concept.confidence_score = confidence
        return concept

    def _study_concept(
        self, row: dict[str, str], rows: list[dict[str, str]], confidence: float | None = None
    ) -> UnifiedConcept | None:
        study_id = row.get("study_id")
        if not study_id:
            return None
        members = [r for r in rows if r["study_id"] == study_id]
        concept = self._create_concept(
            study_id, row.get("study_label") or study_id, ConceptType.REFERENCE
        )
        if concept.definitions is not None:
            concept.definitions.append(
                f"eQTL Catalogue {row.get('study_type', '')} study with {len(members)} datasets"
            )
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "release": self.release,
                "study_label": row.get("study_label"),
                "study_type": row.get("study_type"),
                "pmid": row.get("pmid") or None,
                "n_datasets": len(members),
                "tissues": sorted({r.get("tissue_label", "") for r in members}),
                "conditions": sorted({r.get("condition_label", "") for r in members}),
                "quant_methods": sorted({r.get("quant_method", "") for r in members}),
            }
        if confidence is not None:
            concept.confidence_score = confidence
        return concept

    def _tissue_concept(
        self, row: dict[str, str], rows: list[dict[str, str]], confidence: float | None = None
    ) -> UnifiedConcept | None:
        term = _ontology_id(row.get("tissue_id", ""))
        if not term:
            return None
        members = [r for r in rows if _ontology_id(r["tissue_id"]) == term]
        ctype = ConceptType.CELL_TYPE if term.startswith("CL:") else ConceptType.TISSUE
        concept = self._create_concept(term, row.get("tissue_label") or term, ctype)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "release": self.release,
                "n_datasets": len(members),
                "studies": sorted({r["study_id"] for r in members}),
                "conditions": sorted({r.get("condition_label", "") for r in members}),
                "quant_methods": sorted({r.get("quant_method", "") for r in members}),
            }
        if confidence is not None:
            concept.confidence_score = confidence
        return concept
