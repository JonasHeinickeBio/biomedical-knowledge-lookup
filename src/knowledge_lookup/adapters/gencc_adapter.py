"""
GenCC Knowledge Source Adapter

GenCC (Gene Curation Coalition, https://search.thegencc.org) harmonises gene-disease validity
assertions submitted by many curators (ClinGen, Orphanet, Genomics England PanelApp, Gene2Phenotype,
Ambry, Invitae, Illumina, ...) onto one vocabulary: Definitive, Strong, Moderate, Supportive,
Limited, Disputed Evidence, Refuted Evidence, Animal Model Only, No Known Disease Relationship.
Genes are HGNC, diseases are MONDO (the id the submitter used, e.g. OMIM or Orphanet, is kept as
the "original" id).

Why a file: the website is a Livewire application with no query API (``/api``, ``/api/docs`` and
``/swagger`` all 404), so the only programmatic route is the submissions export:

    https://thegencc.org/download/action/submissions-export-csv   (~28.4 MB, plain text,
    no gzip; ``-tsv`` ~26.5 MB, ``-xlsx`` ~7.3 MB; one row per submission, ~30 columns)

Measured live: the export supports ``Range`` requests, is refreshed about weekly
(``Last-Modified`` 2026-10-04) and the host answers HTTP 429 when several downloads/HEAD
requests are made in a few seconds, so be patient with it. The adapter downloads it once via
:func:`knowledge_lookup.utils.dataset_cache.ensure_dataset` (refreshed after 30 days), parses
it into in-memory indexes (long free-text ``submitted_as_notes`` are dropped) and serves from
there. It is **opt-in**: ``is_available()`` is true when ``GENCC_PATH`` names a local copy
(CSV), the file is already cached, or ``GENCC_DOWNLOAD=1`` (or
``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``) allows the 28 MB download. Nothing downloads at import
or construction time.

Columns used (the "new format" export): ``gene_curie``, ``gene_symbol``, ``disease_curie``,
``disease_title``, ``disease_original_curie``, ``disease_original_title``,
``classification_title``, ``moi_title``, ``submitter_title``, ``submitted_as_date``,
``submitted_as_public_report_url``, ``submitted_as_pmids``, ``submitted_as_assertion_criteria_url``,
``submitted_run_date``.

How this differs from the neighbours: *ClinGen* is one curator (expert panels, ~3,700
curations, SOP-based, includes dosage); *GenCC* aggregates ClinGen **and** the others, so the
same gene-disease pair can carry several, sometimes disagreeing, classifications; *OMIM* (and
Monarch's gene-disease edges) are catalogue/knowledge-graph associations without a validity
grade. Use GenCC for "how strongly, and per whom, is gene X linked to disease Y".

Licence: GenCC data are CC0 1.0 (https://thegencc.org/terms); cite the GenCC (DiStefano et al.,
Genet Med 2022).
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
    classification_rank,
    classification_strength,
    normalize_disease_curie,
    normalize_hgnc,
    relation_for_classification,
    summarize,
)
from ._pheno_common import add_known_identifier

logger = logging.getLogger(__name__)

GENCC_URL = "https://thegencc.org/download/action/submissions-export-csv"
GENCC_FILENAME = "gencc-submissions.csv"
GENCC_PATH_ENV = "GENCC_PATH"
GENCC_DOWNLOAD_ENV = "GENCC_DOWNLOAD"
GENE_PAGE = "https://search.thegencc.org/genes/{hgnc}"
DISEASE_PAGE = "https://search.thegencc.org/diseases/{curie}"

_REQUIRED_COLUMNS = (
    "gene_curie",
    "gene_symbol",
    "disease_curie",
    "disease_title",
    "classification_title",
    "submitter_title",
)
_FIELD_LIMIT = 50_000_000  # submitted_as_notes can exceed csv's 128 kB default


class Submission(NamedTuple):
    """One submitter's assertion about one gene-disease pair (a row of the export)."""

    gene_id: str
    gene_symbol: str
    disease_id: str
    disease_label: str
    original_id: str
    original_label: str
    classification: str
    moi: str
    submitter: str
    date: str
    report_url: str
    pmids: str
    criteria_url: str


class GenCCIndex:
    """In-memory indexes over the submissions export."""

    def __init__(self) -> None:
        self.submissions = 0
        self.by_gene: dict[str, list[Submission]] = {}
        self.by_disease: dict[str, list[Submission]] = {}
        self.by_original: dict[str, list[Submission]] = {}  # submitted id (OMIM/ORPHA/...)
        self.gene_symbols: dict[str, str] = {}
        self.symbol_ids: dict[str, str] = {}
        self.disease_labels: dict[str, str] = {}
        self.original_labels: dict[str, str] = {}

    def add(self, s: Submission) -> None:
        self.submissions += 1
        self.by_gene.setdefault(s.gene_id, []).append(s)
        self.by_disease.setdefault(s.disease_id, []).append(s)
        self.gene_symbols.setdefault(s.gene_id, s.gene_symbol)
        self.symbol_ids.setdefault(s.gene_symbol.upper(), s.gene_id)
        self.disease_labels.setdefault(s.disease_id, s.disease_label)
        original = normalize_disease_curie(s.original_id)
        if original and original != s.disease_id:
            self.by_original.setdefault(original, []).append(s)
            self.original_labels.setdefault(original, s.original_label or s.disease_label)


def parse_submissions(path: str | Path) -> GenCCIndex:
    """Parse a GenCC submissions CSV into a :class:`GenCCIndex`.

    Columns are looked up by header name, so column order changes do not matter. Rows
    without a gene or disease id are skipped. Quoted multi-line notes are handled by the
    :mod:`csv` module and discarded.
    """
    if csv.field_size_limit() < _FIELD_LIMIT:
        csv.field_size_limit(_FIELD_LIMIT)
    index = GenCCIndex()
    with Path(path).open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return index
        pos = {name: i for i, name in enumerate(header)}
        missing = [c for c in _REQUIRED_COLUMNS if c not in pos]
        if missing:
            raise ValueError(f"not a GenCC submissions export, missing columns: {missing}")

        def col(row: list[str], name: str) -> str:
            i = pos.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        for row in reader:
            gene_id = col(row, "gene_curie")
            disease_id = col(row, "disease_curie") or col(row, "disease_original_curie")
            if not gene_id.startswith("HGNC:") or not disease_id:
                continue
            index.add(
                Submission(
                    gene_id=gene_id,
                    gene_symbol=col(row, "gene_symbol"),
                    disease_id=disease_id,
                    disease_label=col(row, "disease_title") or col(row, "disease_original_title"),
                    original_id=col(row, "disease_original_curie"),
                    original_label=col(row, "disease_original_title"),
                    classification=col(row, "classification_title"),
                    moi=col(row, "moi_title"),
                    submitter=col(row, "submitter_title"),
                    date=col(row, "submitted_as_date")[:10],
                    report_url=col(row, "submitted_as_public_report_url"),
                    pmids=col(row, "submitted_as_pmids").replace("\xa0", " "),
                    criteria_url=col(row, "submitted_as_assertion_criteria_url").replace(
                        "\xa0", " "
                    ),
                )
            )
    return index


def _is_word_match(text: str, pos: int) -> bool:
    return pos == 0 or not text[pos - 1].isalnum()


class GenCCAdapter(KnowledgeSourceAdapter):
    """Adapter for GenCC harmonised gene-disease validity submissions (CSV export)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self._index: GenCCIndex | None = None
        self._load_lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.GENCC

    def is_available(self) -> bool:
        """True when ``GENCC_PATH`` names an existing file, the export is already cached, or
        the ~28 MB download is allowed (``GENCC_DOWNLOAD=1`` or
        ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``)."""
        from ..utils.dataset_cache import default_cache_dir, downloads_allowed

        configured = os.environ.get(GENCC_PATH_ENV)
        if configured:
            return Path(configured).is_file()
        return (default_cache_dir() / GENCC_FILENAME).is_file() or downloads_allowed(
            GENCC_DOWNLOAD_ENV
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _ensure_index(self) -> GenCCIndex:
        """Load (once) and return the index; downloads the export on first use if needed."""
        if self._index is not None:
            return self._index
        async with self._load_lock:
            if self._index is None:
                configured = os.environ.get(GENCC_PATH_ENV)
                if configured:
                    path = Path(configured)
                else:
                    from ..utils.dataset_cache import ensure_dataset  # lazy: first use only

                    path = await ensure_dataset(GENCC_URL, filename=GENCC_FILENAME)
                self._index = await asyncio.to_thread(parse_submissions, path)
                logger.info(
                    f"GenCC loaded: {self._index.submissions} submissions, "
                    f"{len(self._index.by_gene)} genes, {len(self._index.by_disease)} diseases"
                )
        return self._index

    # ------------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------------

    @staticmethod
    def _submission_dict(s: Submission) -> dict[str, Any]:
        return {
            "submitter": s.submitter,
            "classification": s.classification,
            "mode_of_inheritance": s.moi,
            "date": s.date,
            "original_disease_id": s.original_id,
            "report_url": s.report_url,
            "pmids": s.pmids,
            "assertion_criteria_url": s.criteria_url,
        }

    def _pair_summary(self, subs: list[Submission]) -> dict[str, Any]:
        """Consensus summary for all submissions of one gene-disease pair."""
        summary = summarize((s.submitter, s.classification) for s in subs)
        summary["modes_of_inheritance"] = sorted({s.moi for s in subs if s.moi})
        summary["latest_date"] = max((s.date for s in subs if s.date), default="")
        return summary

    def _group(self, subs: list[Submission], by_gene: bool) -> dict[str, list[Submission]]:
        """Group submissions by the *other* end of the edge (disease for a gene, else gene)."""
        grouped: dict[str, list[Submission]] = {}
        for s in subs:
            grouped.setdefault(s.disease_id if by_gene else s.gene_id, []).append(s)
        return grouped

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _gene_concept(
        self, index: GenCCIndex, hgnc_id: str, score: float, detailed: bool = False
    ) -> UnifiedConcept:
        symbol = index.gene_symbols.get(hgnc_id, hgnc_id)
        subs = index.by_gene.get(hgnc_id, [])
        concept = self._create_concept(hgnc_id, symbol, ConceptType.GENE)
        concept.confidence_score = score
        concept.semantic_types = ["gene"]
        concept.categories = ["GenCC gene-disease validity"]
        add_known_identifier(concept, hgnc_id)
        diseases = self._group(subs, by_gene=True)
        if detailed:
            best = max((s.classification for s in subs), key=classification_rank, default="")
            concept.definitions = [
                f"{symbol}: {len(subs)} GenCC submission(s) from "
                f"{len({s.submitter for s in subs})} submitter(s) on {len(diseases)} disease(s); "
                f"strongest classification: {best}."
            ]
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {
                "url": GENE_PAGE.format(hgnc=hgnc_id),
                "n_submissions": len(subs),
                "n_diseases": len(diseases),
                "submitters": sorted({s.submitter for s in subs}),
                "validity_summary": summarize((s.submitter, s.classification) for s in subs),
            }
            if detailed:
                data["diseases"] = {
                    d: {
                        "label": index.disease_labels.get(d, d),
                        **self._pair_summary(group),
                    }
                    for d, group in diseases.items()
                }
            concept.source_data[KnowledgeSource.GENCC] = data
        return concept

    def _disease_concept(
        self, index: GenCCIndex, disease_id: str, score: float, detailed: bool = False
    ) -> UnifiedConcept:
        original = self._is_submitted_id(index, disease_id)
        subs = index.by_original[disease_id] if original else index.by_disease.get(disease_id, [])
        label = (
            index.original_labels.get(disease_id, disease_id)
            if original
            else index.disease_labels.get(disease_id, disease_id)
        )
        concept = self._create_concept(disease_id, label, ConceptType.DISEASE)
        concept.confidence_score = score
        concept.semantic_types = ["disease"]
        concept.categories = ["GenCC gene-disease validity"]
        add_known_identifier(concept, disease_id, label)
        genes = self._group(subs, by_gene=False)
        if detailed:
            symbols = ", ".join(sorted(index.gene_symbols.get(g, g) for g in genes))
            concept.definitions = [
                f"{label}: {len(subs)} GenCC submission(s) on {len(genes)} gene(s): {symbols}."
            ]
            if original:
                # a submitted (OMIM/Orphanet) id: show the MONDO ids GenCC mapped it to
                for mondo in sorted({s.disease_id for s in subs}):
                    add_known_identifier(concept, mondo, index.disease_labels.get(mondo))
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {
                "url": DISEASE_PAGE.format(curie=disease_id),
                "n_submissions": len(subs),
                "n_genes": len(genes),
                "submitters": sorted({s.submitter for s in subs}),
                "validity_summary": summarize((s.submitter, s.classification) for s in subs),
            }
            if detailed:
                data["genes"] = {
                    g: {"symbol": index.gene_symbols.get(g, g), **self._pair_summary(group)}
                    for g, group in genes.items()
                }
            concept.source_data[KnowledgeSource.GENCC] = data
        return concept

    @staticmethod
    def _is_submitted_id(index: GenCCIndex, disease_id: str) -> bool:
        """True for an OMIM/Orphanet/... id that submitters used (not a MONDO id GenCC keeps)."""
        return disease_id not in index.disease_labels and disease_id in index.by_original

    @staticmethod
    def _resolve_gene(index: GenCCIndex, text: str) -> str | None:
        parsed = normalize_hgnc(text)
        if parsed is None:
            return None
        kind, value = parsed
        if kind == "id":
            return value if value in index.gene_symbols else None
        return index.symbol_ids.get(value)

    @staticmethod
    def _resolve_disease(index: GenCCIndex, text: str) -> str | None:
        curie = normalize_disease_curie(text)
        if curie and (curie in index.disease_labels or curie in index.by_original):
            return curie
        return None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Find genes (symbol, ``HGNC:n``) and diseases (label, MONDO/OMIM/Orphanet id).

        Ranking: exact 1.0, prefix 0.9, word-start 0.8, other substring 0.7; genes before
        diseases on ties, then more submissions first. Diseases are matched on the MONDO
        label only (the submitted OMIM/Orphanet titles are reachable by id).
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            index = await self._ensure_index()
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
            scored: list[tuple[float, int, int, str, str]] = []
            for hgnc_id, symbol in index.gene_symbols.items():
                score = self._score(symbol.lower(), needle)
                if score:
                    scored.append((score, 0, -len(index.by_gene[hgnc_id]), symbol, hgnc_id))
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
            logger.info(f"GenCC search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"GenCC search failed for '{query}': {e}")
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
        return 0.8 if _is_word_match(lowered, pos) else 0.7

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """A gene (``HGNC:1100`` / ``BRCA1``) or disease (``MONDO:``, or the submitted
        ``OMIM:`` / ``Orphanet:`` id) with per-partner consensus summaries in ``source_data``."""
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
            logger.error(f"GenCC get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Gene -> diseases or disease -> genes: one edge per pair, every submitter listed.

        ``relation_label`` follows the *best* classification of the pair
        (``associated_with`` for Limited or stronger, otherwise
        ``disputed_association_with`` / ``refuted_association_with`` /
        ``no_known_relationship_with`` / ``animal_model_association_with``); check
        ``conflicting`` when submitters disagree. Extra keys: ``best_classification``,
        ``consensus_classification`` (most frequent, ties to the weaker side),
        ``classification_strength``, ``n_submitters``, ``classification_counts``,
        ``conflicting`` (a Moderate-or-stronger assertion next to Disputed/Refuted),
        ``modes_of_inheritance``, ``latest_date`` and ``submissions`` (a list with
        submitter, classification, mode_of_inheritance, date, report_url, pmids per submitter).
        Strongest pairs first, then by number of submitters.
        """
        if limit <= 0:
            return []
        try:
            index = await self._ensure_index()
            gene_id = self._resolve_gene(index, concept_id)
            if gene_id:
                subs, by_gene = index.by_gene.get(gene_id, []), True
            else:
                disease_id = self._resolve_disease(index, concept_id)
                if not disease_id:
                    return []
                original = self._is_submitted_id(index, disease_id)
                subs = index.by_original[disease_id] if original else index.by_disease[disease_id]
                by_gene = False
            edges = []
            for other, group in self._group(subs, by_gene).items():
                summary = self._pair_summary(group)
                best = summary.get("best_classification", "")
                edges.append(
                    {
                        "relation_label": relation_for_classification(best),
                        "related_id": other,
                        "related_name": (
                            index.disease_labels.get(other, other)
                            if by_gene
                            else index.gene_symbols.get(other, other)
                        ),
                        "source": "GENCC",
                        "classification_strength": classification_strength(best),
                        **summary,
                        "submissions": [self._submission_dict(s) for s in group],
                    }
                )
            edges.sort(
                key=lambda e: (
                    -classification_rank(e["best_classification"]),
                    -e["n_submitters"],
                    e["related_name"],
                )
            )
            return edges[:limit]
        except Exception as e:
            logger.warning(f"GenCC get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Disease id mappings GenCC performed: a MONDO id <-> the OMIM / Orphanet / ... ids the
        submitters used (``mappingType`` ``submitted_as``), in either direction."""
        try:
            index = await self._ensure_index()
            disease_id = self._resolve_disease(index, concept_id)
            if not disease_id:
                return []
            pairs: dict[tuple[str, str], None] = {}
            if self._is_submitted_id(index, disease_id):  # queried by OMIM/Orphanet id -> MONDO
                for s in index.by_original[disease_id]:
                    pairs[(disease_id, s.disease_id)] = None
            else:  # queried by MONDO id -> submitted ids
                for s in index.by_disease.get(disease_id, []):
                    original = normalize_disease_curie(s.original_id)
                    if original and original != disease_id:
                        pairs[(disease_id, original)] = None
            return [
                {
                    "fromId": src,
                    "toId": dst,
                    "fromSource": "GENCC",
                    "toSource": dst.split(":", 1)[0],
                    "mappingType": "submitted_as",
                    "confidence": 0.9,
                }
                for src, dst in pairs
            ]
        except Exception as e:
            logger.warning(f"GenCC get_mappings failed for '{concept_id}': {e}")
            return []
