"""
ClinGen Knowledge Source Adapter

ClinGen (Clinical Genome Resource, https://search.clinicalgenome.org) curates gene-disease
validity (Definitive / Strong / Moderate / Limited / Disputed / Refuted / No Known Disease
Relationship) by expert panels (GCEPs) and gene dosage sensitivity (haploinsufficiency and
triplosensitivity). This adapter serves both from ClinGen's small public CSV exports:

* gene-disease validity  https://search.clinicalgenome.org/kb/gene-validity/download
  (~1.1 MB, ~3,700 curations, one row per gene / disease / mode of inheritance);
* dosage sensitivity     https://search.clinicalgenome.org/kb/gene-dosage/download
  (~0.33 MB, ~1,700 genes).

Why files and not an API: the site has no documented query API. Live probing found only
undocumented typeahead helpers used by the web UI (``/api/genes/look/{q}``,
``/api/genes/lookByName/{q}``, ``/api/conditions/look/{q}``; they answer JSON with a
``text/html`` content type and the condition lookup took ~20 s), and the ClinGen Evidence
Repository API (``erepo.clinicalgenome.org/evrepo/api``) only holds *variant*
classifications. The CSVs are the supported, stable route (they are regenerated on every
request), so they are loaded once, cached via
:func:`knowledge_lookup.utils.dataset_cache.ensure_dataset` (refreshed after 7 days) and
indexed in memory.

Opt-in like the other dataset-backed sources: ``is_available()`` is true when
``CLINGEN_PATH`` names a local validity CSV, the files are already cached, or
``CLINGEN_DOWNLOAD=1`` (or ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``) allows the ~1.4 MB download.
``CLINGEN_DOSAGE_PATH`` optionally points at a local dosage CSV; dosage data is a bonus, the
adapter works without it.

Licence: ClinGen data are released under CC0 1.0 (https://clinicalgenome.org/docs/terms-of-use/);
please cite ClinGen (Rehm et al., N Engl J Med 2015). ClinGen curates only ~3,700
gene-disease pairs, so a miss means "not curated", not "no relationship" (see also the GenCC
adapter for the cross-curator view).
"""

import asyncio
import csv
import logging
import os
from pathlib import Path
from typing import Any, NamedTuple

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._gene_disease_common import (
    MOI_LABELS,
    classification_rank,
    classification_strength,
    normalize_disease_curie,
    normalize_hgnc,
    relation_for_classification,
    summarize,
)
from ._pheno_common import add_known_identifier

logger = logging.getLogger(__name__)

VALIDITY_URL = "https://search.clinicalgenome.org/kb/gene-validity/download"
DOSAGE_URL = "https://search.clinicalgenome.org/kb/gene-dosage/download"
VALIDITY_FILENAME = "clingen_gene_validity.csv"
DOSAGE_FILENAME = "clingen_gene_dosage.csv"
CLINGEN_PATH_ENV = "CLINGEN_PATH"
CLINGEN_DOSAGE_PATH_ENV = "CLINGEN_DOSAGE_PATH"
CLINGEN_DOWNLOAD_ENV = "CLINGEN_DOWNLOAD"
MAX_AGE_DAYS = 7  # the exports are regenerated live, curations change weekly
GENE_PAGE = "https://search.clinicalgenome.org/kb/genes/{hgnc}"
DISEASE_PAGE = "https://search.clinicalgenome.org/kb/conditions/{mondo}"


class Curation(NamedTuple):
    """One gene-disease validity curation (a row of the validity CSV)."""

    gene_symbol: str
    hgnc_id: str
    disease_label: str
    mondo_id: str
    moi: str
    sop: str
    classification: str
    report_url: str
    date: str
    expert_panel: str


class Dosage(NamedTuple):
    """Dosage sensitivity curation of one gene."""

    gene_symbol: str
    hgnc_id: str
    haploinsufficiency: str
    triplosensitivity: str
    report_url: str
    date: str


class ClinGenIndex:
    """In-memory indexes over the validity and dosage CSVs."""

    def __init__(self) -> None:
        self.curations: list[Curation] = []
        self.by_gene: dict[str, list[Curation]] = {}
        self.by_disease: dict[str, list[Curation]] = {}
        self.dosage: dict[str, Dosage] = {}
        self.gene_symbols: dict[str, str] = {}  # HGNC id -> symbol
        self.symbol_ids: dict[str, str] = {}  # UPPER symbol -> HGNC id
        self.disease_labels: dict[str, str] = {}  # MONDO id -> label

    def add_curation(self, row: Curation) -> None:
        self.curations.append(row)
        self.by_gene.setdefault(row.hgnc_id, []).append(row)
        self.by_disease.setdefault(row.mondo_id, []).append(row)
        self.add_gene(row.hgnc_id, row.gene_symbol)
        self.disease_labels.setdefault(row.mondo_id, row.disease_label)

    def add_gene(self, hgnc_id: str, symbol: str) -> None:
        self.gene_symbols.setdefault(hgnc_id, symbol)
        self.symbol_ids.setdefault(symbol.upper(), hgnc_id)


def _table_rows(path: Path, first_header: str) -> list[list[str]]:
    """Data rows of a ClinGen export: skips the title block, the header and ``+++`` rules."""
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.reader(handle))
    start = next((i for i, r in enumerate(rows) if r and r[0].strip() == first_header), None)
    if start is None:
        return []
    return [r for r in rows[start + 1 :] if r and r[0] and not r[0].startswith("+")]


def parse_validity_csv(path: str | Path) -> ClinGenIndex:
    """Parse the gene-disease validity export into a :class:`ClinGenIndex`.

    Columns: GENE SYMBOL, GENE ID (HGNC), DISEASE LABEL, DISEASE ID (MONDO), MOI, SOP,
    CLASSIFICATION, ONLINE REPORT, CLASSIFICATION DATE, GCEP. Short rows are skipped.
    """
    index = ClinGenIndex()
    for r in _table_rows(Path(path), "GENE SYMBOL"):
        if len(r) < 10 or not r[1].startswith("HGNC:"):
            continue
        index.add_curation(
            Curation(
                gene_symbol=r[0].strip(),
                hgnc_id=r[1].strip(),
                disease_label=r[2].strip(),
                mondo_id=r[3].strip(),
                moi=r[4].strip(),
                sop=r[5].strip(),
                classification=r[6].strip(),
                report_url=r[7].strip(),
                date=r[8].strip()[:10],
                expert_panel=r[9].strip(),
            )
        )
    return index


def parse_dosage_csv(path: str | Path, index: ClinGenIndex) -> None:
    """Add the dosage sensitivity export (SYMBOL, HGNC ID, HI, TS, REPORT, DATE) to ``index``."""
    for r in _table_rows(Path(path), "GENE SYMBOL"):
        if len(r) < 6 or not r[1].startswith("HGNC:"):
            continue
        dosage = Dosage(
            r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip(), r[4].strip(), r[5][:10]
        )
        index.dosage[dosage.hgnc_id] = dosage
        index.add_gene(dosage.hgnc_id, dosage.gene_symbol)


def _is_word_match(text: str, needle: str, pos: int) -> bool:
    return pos == 0 or not text[pos - 1].isalnum()


class ClinGenAdapter(KnowledgeSourceAdapter):
    """Adapter for ClinGen gene-disease validity and dosage sensitivity (CSV exports)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self._index: ClinGenIndex | None = None
        self._load_lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CLINGEN

    def is_available(self) -> bool:
        """True when ``CLINGEN_PATH`` names an existing file, the validity export is already
        cached, or the ~1.4 MB download is allowed (``CLINGEN_DOWNLOAD=1`` or
        ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``)."""
        from ..utils.dataset_cache import default_cache_dir, downloads_allowed

        configured = os.environ.get(CLINGEN_PATH_ENV)
        if configured:
            return Path(configured).is_file()
        return (default_cache_dir() / VALIDITY_FILENAME).is_file() or downloads_allowed(
            CLINGEN_DOWNLOAD_ENV
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _ensure_index(self) -> ClinGenIndex:
        """Load (once) and return the index; downloads the CSVs on first use if needed."""
        if self._index is not None:
            return self._index
        async with self._load_lock:
            if self._index is None:
                self._index = await self._load()
        return self._index

    async def _load(self) -> ClinGenIndex:
        from ..utils.dataset_cache import ensure_dataset  # lazy: only on first use

        configured = os.environ.get(CLINGEN_PATH_ENV)
        validity = (
            Path(configured)
            if configured
            else await ensure_dataset(
                VALIDITY_URL, filename=VALIDITY_FILENAME, max_age_days=MAX_AGE_DAYS
            )
        )
        index = await asyncio.to_thread(parse_validity_csv, validity)
        try:
            dosage_env = os.environ.get(CLINGEN_DOSAGE_PATH_ENV)
            if dosage_env:
                dosage = Path(dosage_env)
            elif configured:
                dosage = None  # user supplied local files only: never download behind their back
            else:
                dosage = await ensure_dataset(
                    DOSAGE_URL, filename=DOSAGE_FILENAME, max_age_days=MAX_AGE_DAYS
                )
            if dosage is not None and dosage.is_file():
                await asyncio.to_thread(parse_dosage_csv, dosage, index)
        except Exception as e:
            logger.warning(f"ClinGen dosage data unavailable, continuing without it: {e}")
        logger.info(
            f"ClinGen loaded: {len(index.curations)} validity curations, "
            f"{len(index.gene_symbols)} genes, {len(index.dosage)} dosage records"
        )
        return index

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _curation_dict(c: Curation) -> dict[str, Any]:
        return {
            "gene": c.gene_symbol,
            "gene_id": c.hgnc_id,
            "disease": c.disease_label,
            "disease_id": c.mondo_id,
            "classification": c.classification,
            "mode_of_inheritance": MOI_LABELS.get(c.moi, c.moi),
            "moi_code": c.moi,
            "sop": c.sop,
            "curation_date": c.date,
            "expert_panel": c.expert_panel,
            "report_url": c.report_url,
        }

    @staticmethod
    def _dosage_dict(d: Dosage) -> dict[str, Any]:
        return {
            "haploinsufficiency": d.haploinsufficiency,
            "triplosensitivity": d.triplosensitivity,
            "date": d.date,
            "report_url": d.report_url,
        }

    def _gene_concept(
        self, index: ClinGenIndex, hgnc_id: str, score: float, detailed: bool = False
    ) -> UnifiedConcept:
        symbol = index.gene_symbols.get(hgnc_id, hgnc_id)
        concept = self._create_concept(hgnc_id, symbol, ConceptType.GENE)
        concept.confidence_score = score
        concept.semantic_types = ["gene"]
        curations = index.by_gene.get(hgnc_id, [])
        summary = summarize((c.expert_panel, c.classification) for c in curations)
        dosage = index.dosage.get(hgnc_id)
        concept.categories = []
        if curations:
            concept.categories.append("ClinGen gene-disease validity")
        if dosage:
            concept.categories.append("ClinGen dosage sensitivity")
        add_known_identifier(concept, hgnc_id)
        if detailed:
            parts = []
            if curations:
                counts = ", ".join(f"{n} {k}" for k, n in summary["classification_counts"].items())
                parts.append(
                    f"{symbol}: {len(curations)} ClinGen gene-disease validity curation(s) "
                    f"({counts})."
                )
            if dosage:
                parts.append(
                    f"Dosage sensitivity: {dosage.haploinsufficiency}; {dosage.triplosensitivity}."
                )
            concept.definitions = parts
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {"url": GENE_PAGE.format(hgnc=hgnc_id)}
            if curations:
                data["validity_summary"] = summary
                if detailed:
                    data["validity"] = [self._curation_dict(c) for c in curations]
            if dosage:
                data["dosage"] = self._dosage_dict(dosage)
            concept.source_data[KnowledgeSource.CLINGEN] = data
        return concept

    def _disease_concept(
        self, index: ClinGenIndex, mondo_id: str, score: float, detailed: bool = False
    ) -> UnifiedConcept:
        label = index.disease_labels.get(mondo_id, mondo_id)
        concept = self._create_concept(mondo_id, label, ConceptType.DISEASE)
        concept.confidence_score = score
        concept.semantic_types = ["disease"]
        concept.categories = ["ClinGen gene-disease validity"]
        add_known_identifier(concept, mondo_id, label)
        curations = index.by_disease.get(mondo_id, [])
        summary = summarize((c.expert_panel, c.classification) for c in curations)
        if detailed:
            genes = ", ".join(sorted({c.gene_symbol for c in curations}))
            concept.definitions = [f"{label}: ClinGen gene-disease validity curated for {genes}."]
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {
                "url": DISEASE_PAGE.format(mondo=mondo_id),
                "validity_summary": summary,
            }
            if detailed:
                data["validity"] = [self._curation_dict(c) for c in curations]
            concept.source_data[KnowledgeSource.CLINGEN] = data
        return concept

    @staticmethod
    def _resolve_gene(index: ClinGenIndex, text: str) -> str | None:
        parsed = normalize_hgnc(text)
        if parsed is None:
            return None
        kind, value = parsed
        if kind == "id":
            return value if value in index.gene_symbols else None
        return index.symbol_ids.get(value)

    @staticmethod
    def _resolve_disease(index: ClinGenIndex, text: str) -> str | None:
        curie = normalize_disease_curie(text)
        return curie if curie in index.disease_labels else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Find genes (symbol or HGNC id) and diseases (label or MONDO id) with curations.

        Ranking: exact symbol/label 1.0, prefix 0.9, word-start 0.8, other substring 0.7;
        genes win ties over diseases, then more curations first.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            index = await self._ensure_index()
            # identifiers (HGNC:1100, MONDO:0007947) resolve directly; a gene symbol is
            # ranked below so diseases named after it ("BRCA1-related ...") are returned too
            parsed = normalize_hgnc(text)
            gene_id = self._resolve_gene(index, text) if parsed and parsed[0] == "id" else None
            disease_id = self._resolve_disease(index, text)
            if gene_id or disease_id:
                found: list[UnifiedConcept] = []
                if gene_id:
                    found.append(self._gene_concept(index, gene_id, 1.0))
                if disease_id:
                    found.append(self._disease_concept(index, disease_id, 1.0))
                return found[:limit]

            needle = text.lower()
            scored: list[tuple[float, int, int, str, str]] = []  # score, kind, -n, key, id
            for hgnc_id, symbol in index.gene_symbols.items():
                score = self._score(symbol.lower(), needle)
                if score:
                    n = len(index.by_gene.get(hgnc_id, []))
                    scored.append((score, 0, -n, symbol, hgnc_id))
            for mondo_id, label in index.disease_labels.items():
                score = self._score(label.lower(), needle)
                if score:
                    scored.append((score, 1, -len(index.by_disease[mondo_id]), label, mondo_id))
            scored.sort(key=lambda s: (-s[0], s[1], s[2], s[3]))
            concepts = [
                self._gene_concept(index, key, score)
                if kind == 0
                else self._disease_concept(index, key, score)
                for score, kind, _n, _label, key in scored[:limit]
            ]
            logger.info(f"ClinGen search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"ClinGen search failed for '{query}': {e}")
            return []

    @staticmethod
    def _score(lowered: str, needle: str) -> float:
        pos = lowered.find(needle)
        if pos < 0:
            return 0.0
        if lowered == needle:
            return 1.0
        if pos == 0:
            return 0.9
        return 0.8 if _is_word_match(lowered, needle, pos) else 0.7

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """A gene (``HGNC:1100`` or ``BRCA1``) or a disease (``MONDO:0007947``) with its
        curation summary in ``definitions`` and the full curations/dosage in ``source_data``."""
        try:
            index = await self._ensure_index()
            gene_id = self._resolve_gene(index, concept_id)
            if gene_id:
                return self._gene_concept(index, gene_id, 1.0, detailed=True)
            disease_id = self._resolve_disease(index, concept_id)
            if disease_id:
                return self._disease_concept(index, disease_id, 1.0, detailed=True)
            return None
        except Exception as e:
            logger.error(f"ClinGen get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Gene -> diseases or disease -> genes, strongest classification first.

        ``relation_label`` is ``associated_with`` for Limited or stronger and
        ``disputed_association_with`` / ``refuted_association_with`` /
        ``no_known_relationship_with`` otherwise. Extra keys: ``classification``,
        ``classification_strength`` (0-1), ``mode_of_inheritance`` (+ ``moi_code``),
        ``curation_date``, ``expert_panel``, ``sop``, ``report_url``, and, for the gene side,
        ``dosage_haploinsufficiency`` / ``dosage_triplosensitivity`` / ``dosage_date``.
        """
        if limit <= 0:
            return []
        try:
            index = await self._ensure_index()
            gene_id = self._resolve_gene(index, concept_id)
            if gene_id:
                rows, by_gene = index.by_gene.get(gene_id, []), True
            else:
                disease_id = self._resolve_disease(index, concept_id)
                if not disease_id:
                    return []
                rows, by_gene = index.by_disease.get(disease_id, []), False
            # strongest first, newest first within one classification (two stable sorts)
            ordered = sorted(rows, key=lambda c: c.date, reverse=True)
            ordered.sort(key=lambda c: -classification_rank(c.classification))
            edges = [self._edge(index, c, by_gene) for c in ordered]
            return edges[:limit]
        except Exception as e:
            logger.warning(f"ClinGen get_relationships failed for '{concept_id}': {e}")
            return []

    def _edge(self, index: ClinGenIndex, c: Curation, by_gene: bool) -> dict[str, Any]:
        edge: dict[str, Any] = {
            "relation_label": relation_for_classification(c.classification),
            "related_id": c.mondo_id if by_gene else c.hgnc_id,
            "related_name": c.disease_label if by_gene else c.gene_symbol,
            "source": "CLINGEN",
            "classification": c.classification,
            "classification_strength": classification_strength(c.classification),
            "mode_of_inheritance": MOI_LABELS.get(c.moi, c.moi),
            "moi_code": c.moi,
            "curation_date": c.date,
            "expert_panel": c.expert_panel,
            "sop": c.sop,
            "report_url": c.report_url,
        }
        dosage = index.dosage.get(c.hgnc_id)
        if dosage:
            edge["dosage_haploinsufficiency"] = dosage.haploinsufficiency
            edge["dosage_triplosensitivity"] = dosage.triplosensitivity
            edge["dosage_date"] = dosage.date
        return edge
