"""
CellMarker adapter (cell-type marker genes).

CellMarker is a manually curated resource of cell-type marker genes (human and mouse) with
the tissue, species, evidence type and PMID behind every marker. Cite: Hu C et al., Nucleic
Acids Res 2023 (CellMarker 2.0). The data is published for academic use only
(http://bio-bigdata.hrbmu.edu.cn/CellMarker/); check its terms before commercial use.

There is **no query API**: the data is distributed as files, so this adapter downloads one
file lazily (never at construction), aggregates it in memory and answers every call from the
index. Aggregation is per (cell type, marker gene): number of records, species, tissues,
evidence types and distinct PMIDs.

Data sources (verified by HEAD / range requests, see ``docs/adapters/ontologies``):

* default - CellMarker 2.0 ``Cell_marker_Human.xlsx`` (~8 MB, ~1.0 M rows, 20 columns) from the
  2.0 server ``http://117.50.127.228/CellMarker/CellMarker_download_files/file/``. The
  official ``bio-bigdata.hrbmu.edu.cn`` host now serves CellMarker 3.0, whose downloads are
  ``file/human_cell_marker.zip`` etc. (49 MB zips holding a ~580 MB TSV): too large to index
  in memory per process, but accepted via ``CELLMARKER_URL`` / ``CELLMARKER_PATH``.
* ``CELLMARKER_PATH`` - local ``.xlsx`` / ``.tsv`` / ``.csv`` / ``.txt`` (optionally ``.gz``).
* ``CELLMARKER_URL`` - alternative download URL (``.xlsx``, or a zip/gz of a TSV/CSV).

Column names differ between releases (``Symbol``/``symbol``, ``UNIPROTID``/``uniprot_id``,
``cancer_type``/``disease``, ``uberonongology_id`` [sic]/``uberon_id``); headers are matched
case-insensitively with punctuation ignored. The parsed index is persisted next to the data
file (``*.index.json.gz``) so the ~1 M-row parse happens once per data file.
"""

import asyncio
import csv
import gzip
import json
import logging
import os
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

CELLMARKER_PATH_ENV = "CELLMARKER_PATH"
CELLMARKER_URL_ENV = "CELLMARKER_URL"
INDEX_VERSION = 1
_DATASET_MAX_AGE_DAYS = 90  # CellMarker releases are infrequent

# Normalised header (lower case, alphanumerics only) -> canonical column name.
_COLUMN_ALIASES: dict[str, str] = {
    "species": "species",
    "tissueclass": "tissue_class",
    "tissuetype": "tissue_type",
    "uberonid": "uberon_id",
    "uberonongologyid": "uberon_id",
    "uberonontologyid": "uberon_id",
    "cancertype": "condition",
    "disease": "condition",
    "celltype": "cell_class",
    "cellnameclass": "cell_class",
    "cellname": "cell_name",
    "cellontologyid": "cl_id",
    "marker": "marker",
    "symbol": "symbol",
    "geneid": "gene_id",
    "genetype": "gene_type",
    "genename": "gene_name",
    "uniprotid": "uniprot",
    "uniprot": "uniprot",
    "technologyseq": "technology",
    "markersource": "marker_source",
    "pmid": "pmid",
}
_NORMAL_CONDITIONS = {"", "normal", "none", "na", "n/a"}
_MISSING = {"", "na", "n/a", "none", "null", "nan", "unknown"}
_CL_RE = re.compile(r"^CL[:_](\d{7})$", re.IGNORECASE)
_GENE_ID_RE = re.compile(r"^(?:NCBIGene|GeneID|NCBI|Entrez)?:?(\d+)$", re.IGNORECASE)
_UNIPROT_SPLIT = re.compile(r"[;,|\s]+")
_MAX_UNIPROT = 5
_MAX_ALIASES = 12
_MAX_PMID_SAMPLE = 5


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in _MISSING else text


def _norm_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower())


def _digits(value: Any) -> str:
    """``"31982413.0"`` / ``"4321"`` -> ``"31982413"`` / ``"4321"``; anything else -> ``""``."""
    text = _clean(value).split(".")[0]
    return text if text.isdigit() else ""


def _cl_curie(value: Any) -> str:
    match = _CL_RE.match(_clean(value))
    return f"CL:{match.group(1)}" if match else ""


class _Interner:
    """Maps strings to small ints so per-pair sets become bitmasks."""

    def __init__(self, names: list[str] | None = None) -> None:
        self.names: list[str] = list(names or [])
        self._ids = {n: i for i, n in enumerate(self.names)}

    def mask(self, name: str) -> int:
        if not name:
            return 0
        idx = self._ids.get(name)
        if idx is None:
            idx = self._ids[name] = len(self.names)
            self.names.append(name)
        return 1 << idx

    def decode(self, mask: int) -> list[str]:
        return [n for i, n in enumerate(self.names) if mask >> i & 1]


class _Pair:
    """Aggregated evidence for one (cell type, marker gene) combination."""

    __slots__ = ("rows", "species", "tissues", "sources", "pmids")

    def __init__(self) -> None:
        self.rows = 0
        self.species = 0
        self.tissues = 0
        self.sources = 0
        self.pmids: list[int] = []


class _Cell:
    __slots__ = ("key", "cl_id", "names", "tissues", "species", "uberon", "conditions", "markers")

    def __init__(self, key: str, cl_id: str) -> None:
        self.key = key
        self.cl_id = cl_id
        self.names: Counter[str] = Counter()
        self.tissues = 0
        self.species = 0
        self.uberon: set[str] = set()
        self.conditions: set[str] = set()
        self.markers: dict[str, _Pair] = {}  # upper-case symbol -> evidence

    @property
    def label(self) -> str:
        return self.names.most_common(1)[0][0] if self.names else self.key


class _Gene:
    __slots__ = ("symbol", "gene_id", "gene_name", "gene_type", "uniprot", "aliases", "cells")

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.gene_id = ""
        self.gene_name = ""
        self.gene_type = ""
        self.uniprot = ""
        self.aliases: set[str] = set()
        self.cells: dict[str, _Pair] = {}  # cell key -> the same evidence object


class _Index:
    """In-memory aggregation of a CellMarker table."""

    def __init__(self) -> None:
        self.cells: dict[str, _Cell] = {}
        self.genes: dict[str, _Gene] = {}
        self.species = _Interner()
        self.tissues = _Interner()
        self.sources = _Interner()
        self.rows = 0
        self._rebuild_lookups()

    # -- lookups -------------------------------------------------------
    def _rebuild_lookups(self) -> None:
        self.cell_by_name: dict[str, set[str]] = {}
        self.gene_by_id: dict[str, str] = {}
        self.gene_by_alias: dict[str, set[str]] = {}
        for key, cell in self.cells.items():
            for name in cell.names:
                self.cell_by_name.setdefault(name.lower(), set()).add(key)
        for upper, gene in self.genes.items():
            if gene.gene_id:
                self.gene_by_id.setdefault(gene.gene_id, upper)
            for alias in gene.aliases:
                self.gene_by_alias.setdefault(alias.upper(), set()).add(upper)

    # -- building ------------------------------------------------------
    def add(self, rec: dict[str, str]) -> None:
        cell_name = _clean(rec.get("cell_name"))
        symbol = _clean(rec.get("symbol"))
        marker = _clean(rec.get("marker"))
        gene_label = symbol or marker
        if not cell_name or not gene_label:
            return
        self.rows += 1
        cl_id = _cl_curie(rec.get("cl_id"))
        key = cl_id or f"name:{cell_name.lower()}"
        cell = self.cells.get(key)
        if cell is None:
            cell = self.cells[key] = _Cell(key, cl_id)
        cell.names[cell_name] += 1
        species = _clean(rec.get("species"))
        tissue = _clean(rec.get("tissue_type")) or _clean(rec.get("tissue_class"))
        species_mask, tissue_mask = self.species.mask(species), self.tissues.mask(tissue)
        cell.species |= species_mask
        cell.tissues |= tissue_mask
        uberon = _clean(rec.get("uberon_id")).replace("_", ":")
        if uberon and len(cell.uberon) < 40:
            cell.uberon.add(uberon)
        condition = _clean(rec.get("condition"))
        if condition.lower() not in _NORMAL_CONDITIONS and len(cell.conditions) < 40:
            cell.conditions.add(condition)

        upper = gene_label.upper()
        gene = self.genes.get(upper)
        if gene is None:
            gene = self.genes[upper] = _Gene(gene_label)
        if symbol:
            gene.gene_id = gene.gene_id or _digits(rec.get("gene_id"))
            gene.gene_name = gene.gene_name or _clean(rec.get("gene_name"))
            gene.gene_type = gene.gene_type or _clean(rec.get("gene_type"))
            known = [a for a in _UNIPROT_SPLIT.split(gene.uniprot) if a]
            for accession in _UNIPROT_SPLIT.split(_clean(rec.get("uniprot"))):
                if accession and accession not in known and len(known) < _MAX_UNIPROT:
                    known.append(accession)
            gene.uniprot = ";".join(known)
            if marker and marker.upper() != upper and len(gene.aliases) < _MAX_ALIASES:
                gene.aliases.add(marker)

        pair = cell.markers.get(upper)
        if pair is None:
            pair = cell.markers[upper] = _Pair()
            gene.cells[key] = pair
        pair.rows += 1
        pair.species |= species_mask
        pair.tissues |= tissue_mask
        pair.sources |= self.sources.mask(_clean(rec.get("marker_source")))
        pmid = _digits(rec.get("pmid"))
        if pmid and int(pmid) not in pair.pmids:
            pair.pmids.append(int(pmid))

    # -- persistence ---------------------------------------------------
    def to_json(self, signature: list[int]) -> dict[str, Any]:
        cell_keys = list(self.cells)
        cell_pos = {k: i for i, k in enumerate(cell_keys)}
        gene_keys = list(self.genes)
        gene_pos = {k: i for i, k in enumerate(gene_keys)}
        pairs: list[list[Any]] = []
        for ckey, cell in self.cells.items():
            for gkey, pair in cell.markers.items():
                pairs.append(
                    [
                        cell_pos[ckey],
                        gene_pos[gkey],
                        pair.rows,
                        pair.species,
                        pair.tissues,
                        pair.sources,
                        pair.pmids,
                    ]
                )
        return {
            "version": INDEX_VERSION,
            "signature": signature,
            "rows": self.rows,
            "species": self.species.names,
            "tissues": self.tissues.names,
            "sources": self.sources.names,
            "cells": [
                [
                    c.key,
                    c.cl_id,
                    dict(c.names),
                    c.tissues,
                    c.species,
                    sorted(c.uberon),
                    sorted(c.conditions),
                ]
                for c in self.cells.values()
            ],
            "genes": [
                [g.symbol, g.gene_id, g.gene_name, g.gene_type, g.uniprot, sorted(g.aliases)]
                for g in self.genes.values()
            ],
            "pairs": pairs,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "_Index":
        index = cls()
        index.rows = int(data.get("rows", 0))
        index.species = _Interner(data["species"])
        index.tissues = _Interner(data["tissues"])
        index.sources = _Interner(data["sources"])
        cell_list: list[_Cell] = []
        for key, cl_id, names, tissues, species, uberon, conditions in data["cells"]:
            cell = _Cell(key, cl_id)
            cell.names = Counter(names)
            cell.tissues, cell.species = tissues, species
            cell.uberon, cell.conditions = set(uberon), set(conditions)
            index.cells[key] = cell
            cell_list.append(cell)
        gene_list: list[tuple[str, _Gene]] = []
        for symbol, gene_id, gene_name, gene_type, uniprot, aliases in data["genes"]:
            gene = _Gene(symbol)
            gene.gene_id, gene.gene_name, gene.gene_type = gene_id, gene_name, gene_type
            gene.uniprot, gene.aliases = uniprot, set(aliases)
            index.genes[symbol.upper()] = gene
            gene_list.append((symbol.upper(), gene))
        for ci, gi, rows, species, tissues, sources, pmids in data["pairs"]:
            pair = _Pair()
            pair.rows, pair.species, pair.tissues = rows, species, tissues
            pair.sources, pair.pmids = sources, list(pmids)
            cell = cell_list[ci]
            upper, gene = gene_list[gi]
            cell.markers[upper] = pair
            gene.cells[cell.key] = pair
        index._rebuild_lookups()
        return index


# ----------------------------------------------------------------------
# File reading
# ----------------------------------------------------------------------


def _iter_table_rows(path: Path) -> Iterator[list[str]]:
    """Rows of an xlsx/tsv/csv(.gz) table as lists of strings."""
    suffixes = [s.lower() for s in path.suffixes]
    if suffixes and suffixes[-1] == ".xlsx":
        from ._xlsx import iter_xlsx_rows

        yield from iter_xlsx_rows(path)
        return
    gz = bool(suffixes) and suffixes[-1] == ".gz"
    opener = gzip.open if gz else open
    delimiter = "," if (suffixes[-2:-1] if gz else suffixes[-1:]) == [".csv"] else "\t"
    csv.field_size_limit(1 << 24)
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.reader(handle, delimiter=delimiter)


def build_index(path: Path) -> _Index:
    """Parse ``path`` into an :class:`_Index` (blocking; run it in a worker thread)."""
    rows = _iter_table_rows(path)
    header = next(rows, None)
    if not header:
        raise ValueError(f"{path} is empty")
    columns: dict[int, str] = {}
    for position, name in enumerate(header):
        canonical = _COLUMN_ALIASES.get(_norm_header(name))
        if canonical and canonical not in columns.values():
            columns[position] = canonical
    names = set(columns.values())
    if "cell_name" not in names or not names & {"symbol", "marker"}:
        raise ValueError(f"{path} does not look like a CellMarker table (columns: {header[:8]})")
    index = _Index()
    for row in rows:
        index.add({canonical: row[pos] for pos, canonical in columns.items() if pos < len(row)})
    index._rebuild_lookups()
    return index


def _signature(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def load_index(path: Path) -> _Index:
    """Load the persisted index for ``path`` when current, else build (and persist) it."""
    cache_file = path.with_name(path.name + ".index.json.gz")
    signature = _signature(path)
    try:
        with gzip.open(cache_file, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("version") == INDEX_VERSION and data.get("signature") == signature:
            return _Index.from_json(data)
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass  # no / stale / unreadable index: rebuild below
    index = build_index(path)
    try:
        tmp = cache_file.with_name(cache_file.name + ".part")
        with gzip.open(tmp, "wt", encoding="utf-8") as handle:
            json.dump(index.to_json(signature), handle, separators=(",", ":"))
        tmp.replace(cache_file)
    except OSError as e:
        logger.debug(f"CellMarker index not persisted ({e})")
    return index


# ----------------------------------------------------------------------
# Adapter
# ----------------------------------------------------------------------


class CellMarkerAdapter(KnowledgeSourceAdapter):
    """Adapter for CellMarker cell-type marker genes (file-based, lazily downloaded)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self._index: _Index | None = None
        self._index_lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CELLMARKER

    def is_available(self) -> bool:
        """True when ``CELLMARKER_PATH`` names an existing file or ``CELLMARKER_URL`` is set.

        There is no built-in download location: the official site now serves CellMarker 3.0
        (a 49 MB zip around a 577 MB TSV) and the old 2.0 workbook is only reachable through a
        third-party host, so you choose the file explicitly."""
        override = os.getenv(CELLMARKER_PATH_ENV)
        if override:
            return Path(override).expanduser().is_file()
        return bool((os.getenv(CELLMARKER_URL_ENV) or "").strip())

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _dataset_path(self) -> Path:
        override = os.getenv(CELLMARKER_PATH_ENV)
        if override:
            path = Path(override).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"{CELLMARKER_PATH_ENV}={override} does not exist")
            return path
        url = (os.getenv(CELLMARKER_URL_ENV) or "").strip()
        if not url:
            raise FileNotFoundError(
                f"CellMarker needs {CELLMARKER_PATH_ENV} (a local file) or {CELLMARKER_URL_ENV}"
            )
        from ..utils.dataset_cache import ensure_dataset

        name = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1] or "cellmarker.dat"
        # An .xlsx is a zip container that must be kept as one file, not unpacked.
        return await ensure_dataset(
            url,
            filename=name,
            max_age_days=_DATASET_MAX_AGE_DAYS,
            raw=name.lower().endswith(".xlsx"),
            headers={"User-Agent": "AID-PAIS-Knowledge-Lookup/1.0"},
        )

    async def _get_index(self) -> _Index | None:
        """The aggregated index, built on first use; ``None`` when the data is unavailable."""
        if self._index is not None:
            return self._index
        async with self._index_lock:
            if self._index is not None:
                return self._index
            try:
                path = await self._dataset_path()
                self._index = await asyncio.to_thread(load_index, path)
                logger.info(
                    f"CellMarker index ready: {len(self._index.cells)} cell types, "
                    f"{len(self._index.genes)} genes, {self._index.rows} records"
                )
            except Exception as e:
                logger.error(f"CellMarker dataset unavailable: {e}")
                self._notify_circuit_breaker(e)
                return None
        return self._index

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search marker genes (symbol or alias such as ``CD16``) and cell types by name.

        Exact symbol/name matches rank first, then aliases and prefixes, then substring
        matches in cell-type names; ties are broken by the amount of curated evidence.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            index = await self._get_index()
            if index is None:
                return []
            hits = sorted(
                self._match(index, text), key=lambda h: (h[0], -h[1], h[2].lower(), h[3])
            )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for rank, _weight, _label, ref in hits:
                if ref in seen:
                    continue
                seen.add(ref)
                entity = index.cells.get(ref) or index.genes[ref.removeprefix("gene:")]
                concept = (
                    self._cell_concept(index, entity)
                    if isinstance(entity, _Cell)
                    else self._gene_concept(index, entity)
                )
                concept.confidence_score = max(0.4, 0.9 - 0.1 * rank)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"CellMarker search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"CellMarker search failed for '{text}': {e}")
            return []

    @staticmethod
    def _match(index: _Index, text: str) -> Iterator[tuple[int, int, str, str]]:
        """Yield ``(rank, evidence size, label, ref)``; ``ref`` is a cell key or ``gene:SYMBOL``."""
        lower, upper = text.lower(), text.upper()
        cl_id = _cl_curie(text)
        aliased = index.gene_by_alias.get(upper, set())
        for gupper, gene in index.genes.items():
            if gupper == upper:
                rank = 0
            elif gupper in aliased:
                rank = 1
            elif len(upper) >= 2 and gupper.startswith(upper):
                rank = 3
            else:
                continue
            yield rank, len(gene.cells), gene.symbol, f"gene:{gupper}"
        for key, cell in index.cells.items():
            names = [n.lower() for n in cell.names]
            if (cl_id and key == cl_id) or lower in names:
                rank = 0
            elif any(n.startswith(lower) for n in names):
                rank = 2
            elif len(lower) >= 3 and any(lower in n for n in names):
                rank = 4
            else:
                continue
            yield rank, len(cell.markers), cell.label, key

    def _resolve(self, index: _Index, concept_id: str) -> _Cell | _Gene | None:
        text = (concept_id or "").strip()
        if not text:
            return None
        cl_id = _cl_curie(text)
        if cl_id:
            return index.cells.get(cl_id)
        match = _GENE_ID_RE.match(text)
        if match:
            upper = index.gene_by_id.get(match.group(1))
            return index.genes.get(upper) if upper else None
        if text.lower().startswith("cellmarker:"):
            name = text.split(":", 1)[1].strip().lower()
            keys = index.cell_by_name.get(name)
            return index.cells[sorted(keys)[0]] if keys else None
        gene = index.genes.get(text.upper())
        if gene is not None:
            return gene
        aliased = index.gene_by_alias.get(text.upper())
        if aliased:
            return index.genes[sorted(aliased)[0]]
        keys = index.cell_by_name.get(text.lower())
        return index.cells[sorted(keys)[0]] if keys else None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Cell type (``CL:0000235`` or exact name) or marker gene (symbol, alias, Entrez id)."""
        try:
            index = await self._get_index()
            if index is None:
                return None
            entity = self._resolve(index, concept_id)
            if entity is None:
                return None
            if isinstance(entity, _Cell):
                return self._cell_concept(index, entity, detailed=True)
            return self._gene_concept(index, entity, detailed=True)
        except Exception as e:
            logger.error(f"CellMarker get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Cell type -> markers (``has_marker``) or marker gene -> cell types
        (``is_marker_of``), strongest evidence first (distinct PMIDs, then records).

        Every item carries ``species``, ``tissues`` (up to 5), ``tissue_count``,
        ``pmid_count``, ``record_count``, ``pmids`` (up to 5) and ``evidence_types``.
        """
        if limit <= 0:
            return []
        try:
            index = await self._get_index()
            entity = self._resolve(index, concept_id) if index else None
            if index is None or entity is None:
                return []
            if isinstance(entity, _Cell):
                items = [
                    ("has_marker", self._gene_ref(index.genes[g]), index.genes[g].symbol, p)
                    for g, p in entity.markers.items()
                ]
            else:
                items = [
                    ("is_marker_of", self._cell_ref(index.cells[c]), index.cells[c].label, p)
                    for c, p in entity.cells.items()
                ]
            items.sort(key=lambda it: (-len(it[3].pmids), -it[3].rows, it[2].lower()))
            return [
                {
                    "relation_label": label,
                    "related_id": rid,
                    "related_name": name,
                    "source": "CellMarker",
                    **self._evidence(index, pair),
                }
                for label, rid, name, pair in items[:limit]
            ]
        except Exception as e:
            logger.error(f"CellMarker get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cell type -> Cell Ontology id; marker gene -> NCBI Gene id and UniProt accession(s)."""
        try:
            index = await self._get_index()
            entity = self._resolve(index, concept_id) if index else None
            if index is None or entity is None:
                return []
            if isinstance(entity, _Cell):
                if not entity.cl_id:
                    return []
                return [self._mapping(self._cell_ref(entity), entity.cl_id, "CL", 0.95)]
            mappings: list[dict[str, Any]] = []
            from_id = self._gene_ref(entity)
            if entity.gene_id:
                mappings.append(self._mapping(from_id, entity.gene_id, "NCBIGene", 0.95))
            for accession in _UNIPROT_SPLIT.split(entity.uniprot):
                if accession:
                    mappings.append(self._mapping(from_id, accession, "UniProt", 0.9))
            return mappings
        except Exception as e:
            logger.error(f"CellMarker get_mappings failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _mapping(from_id: str, to_id: str, to_source: str, confidence: float) -> dict[str, Any]:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "CellMarker",
            "toSource": to_source,
            "mappingType": "xref",
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_ref(cell: _Cell) -> str:
        return cell.cl_id or f"CellMarker:{cell.label}"

    @staticmethod
    def _gene_ref(gene: _Gene) -> str:
        return f"NCBIGene:{gene.gene_id}" if gene.gene_id else gene.symbol

    @staticmethod
    def _evidence(index: _Index, pair: _Pair) -> dict[str, Any]:
        tissues = index.tissues.decode(pair.tissues)
        return {
            "species": index.species.decode(pair.species),
            "tissues": tissues[:5],
            "tissue_count": len(tissues),
            "pmid_count": len(pair.pmids),
            "record_count": pair.rows,
            "pmids": [str(p) for p in pair.pmids[:_MAX_PMID_SAMPLE]],
            "evidence_types": index.sources.decode(pair.sources),
        }

    def _cell_concept(self, index: _Index, cell: _Cell, detailed: bool = False) -> UnifiedConcept:
        concept = self._create_concept(self._cell_ref(cell), cell.label, ConceptType.CELL_TYPE)
        if cell.cl_id:
            concept.add_identifier(KnowledgeSource.CELLONTOLOGY, cell.cl_id, cell.label)
        if concept.synonyms is not None:
            concept.synonyms.extend(n for n in cell.names if n != cell.label)
            del concept.synonyms[30:]
        tissues = index.tissues.decode(cell.tissues)
        if concept.categories is not None:
            concept.categories.extend(f"tissue: {t}" for t in tissues[:10])
        pmids = {p for pair in cell.markers.values() for p in pair.pmids}
        data: dict[str, Any] = {
            "cl_id": cell.cl_id,
            "species": index.species.decode(cell.species),
            "tissue_count": len(tissues),
            "marker_count": len(cell.markers),
            "pmid_count": len(pmids),
        }
        if detailed:
            top = sorted(
                cell.markers.items(), key=lambda kv: (-len(kv[1].pmids), -kv[1].rows, kv[0])
            )
            data.update(
                tissues=tissues[:25],
                uberon_ids=sorted(cell.uberon)[:25],
                conditions=sorted(cell.conditions)[:25],
                top_markers=[index.genes[g].symbol for g, _p in top[:25]],
            )
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = data
        return concept

    def _gene_concept(self, index: _Index, gene: _Gene, detailed: bool = False) -> UnifiedConcept:
        label = gene.gene_name or gene.symbol
        concept = self._create_concept(gene.symbol, label, ConceptType.GENE)
        if concept.synonyms is not None:
            concept.synonyms.append(gene.symbol)
            concept.synonyms.extend(sorted(gene.aliases))
        if gene.gene_id:
            concept.add_identifier(
                KnowledgeSource.NCBI,
                gene.gene_id,
                gene.symbol,
                f"https://www.ncbi.nlm.nih.gov/gene/{gene.gene_id}",
            )
        for accession in _UNIPROT_SPLIT.split(gene.uniprot):
            if accession:
                concept.add_identifier(KnowledgeSource.UNIPROT, accession, gene.symbol)
        if gene.gene_type and concept.semantic_types is not None:
            concept.semantic_types.append(gene.gene_type)
        data: dict[str, Any] = {
            "symbol": gene.symbol,
            "gene_id": gene.gene_id,
            "cell_type_count": len(gene.cells),
            "record_count": sum(p.rows for p in gene.cells.values()),
        }
        if detailed:
            top = sorted(gene.cells.items(), key=lambda kv: (-len(kv[1].pmids), -kv[1].rows))
            data["top_cell_types"] = [index.cells[c].label for c, _p in top[:25]]
        concept.confidence_score = 0.85
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = data
        return concept
