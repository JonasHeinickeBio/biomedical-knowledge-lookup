"""
CTD adapter (Comparative Toxicogenomics Database, https://ctdbase.org), bulk-file based.

Licence and citation (read before redistributing results):
    CTD data is free for research but "subject to the terms set forth at
    http://ctdbase.org/about/legal.jsp". The header of every CTD report states four conditions:
    (1) all publications / databases / software that use or rely on CTD data must cite CTD
    (use the current reference listed at https://ctdbase.org/about/publications/#citing);
    (2) online applications must hyperlink from the contexts using CTD data to the CTD data
    pages (https://ctdbase.org/help/linking.jsp); (3) CTD must be notified of the use
    (https://ctdbase.org/help/contact.go); (4) CTD must be given periodic access to the
    resulting publication of its data. Commercial use needs a separate licence from CTD.

Why bulk files and not the batch query web service:
    The keyless ``https://ctdbase.org/tools/batchQuery.go?...&format=json`` endpoint is, as of
    2026-10, answered with an HTTP 302 to an interstitial page that loads an ALTCHA
    proof-of-work widget (a bot challenge) instead of JSON, so scripted access is blocked. That
    challenge is deliberately not circumvented. CTD's bulk reports under
    ``https://ctdbase.org/reports/`` are served normally (HEAD/Range verified, 2026-09-29
    release) and are what this adapter reads.

Data files (gzipped CSV with ``#`` comment headers, sizes as downloaded):

====================================  =========  ===========================================
file                                  size       used for
====================================  =========  ===========================================
``CTD_chemicals.csv.gz``              10.5 MB    chemical concepts / search / mappings
``CTD_diseases.csv.gz``                1.8 MB    disease concepts / search / mappings
``CTD_chem_gene_ixns.csv.gz``         43.4 MB    chemical <-> gene interactions (+ gene ids)
``CTD_chemicals_diseases.csv.gz``    163.6 MB    chemical <-> disease (curated evidence)
``CTD_genes.csv.gz`` (optional)      122.9 MB    gene names/synonyms; only if present or
                                                 ``CTD_DOWNLOAD_GENES=1``
``CTD_genes_diseases.csv.gz``          3.2 GB    gene <-> disease; only if present or
(optional)                                       ``CTD_DOWNLOAD_GENES_DISEASES=1``
====================================  =========  ===========================================

Nothing is downloaded at import or construction: each file is fetched on first use through
:func:`knowledge_lookup.utils.dataset_cache.ensure_dataset` (kept gzipped, streamed on every
query with a cheap substring pre-filter, so a lookup scans the file once, a few seconds for the
largest required one) and refreshed after 60 days. ``CTD_DATA_DIR`` overrides the directory
(drop the files there to work offline). Scan results are memoised per adapter instance.

Identifiers: chemicals ``MESH:D001241``; diseases ``MESH:D003920`` or ``OMIM:264300``; genes
``NCBIGene:672``. CTD writes chemical ids without the ``MESH:`` prefix in its relation files;
that is normalised here.
"""

import asyncio
import csv
import gzip
import logging
import os
import re
from collections import OrderedDict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ..utils.dataset_cache import default_cache_dir, downloads_allowed, ensure_dataset

logger = logging.getLogger(__name__)

CTD_REPORTS_URL = "https://ctdbase.org/reports/"
CTD_WEB_BASE = "https://ctdbase.org/detail.go"
DATA_DIR_ENV = "CTD_DATA_DIR"
DOWNLOAD_ENV = "CTD_DOWNLOAD"
MAX_AGE_DAYS = 60  # CTD publishes monthly; the cached copy is refreshed after two months
MAX_SYNONYMS = 100
MAX_PMIDS = 25
SCAN_CACHE_SIZE = 32

FILE_CHEMICALS = "CTD_chemicals.csv.gz"
FILE_DISEASES = "CTD_diseases.csv.gz"
FILE_GENES = "CTD_genes.csv.gz"
FILE_IXNS = "CTD_chem_gene_ixns.csv.gz"
FILE_CHEM_DISEASES = "CTD_chemicals_diseases.csv.gz"
FILE_GENE_DISEASES = "CTD_genes_diseases.csv.gz"

# Optional files are only downloaded when this environment variable is "1"
_OPT_IN_ENV = {FILE_GENES: "CTD_DOWNLOAD_GENES", FILE_GENE_DISEASES: "CTD_DOWNLOAD_GENES_DISEASES"}

_MESH_RE = re.compile(r"^(?:MESH:)?([CD]\d{6,9})$", re.IGNORECASE)
_OMIM_RE = re.compile(r"^OMIM:(\d+)$", re.IGNORECASE)
_GENE_RE = re.compile(r"^(?:NCBIGENE|NCBI_GENE|GENEID|ENTREZ|NCBI):(\d+)$", re.IGNORECASE)
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_GENE_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{1,14}$")

# DirectEvidence value -> (chemical->disease label, disease->chemical label)
_CHEM_DISEASE_LABELS = {
    "therapeutic": ("therapeutic_for", "treated_by"),
    "marker/mechanism": ("marker_mechanism_for", "marker_mechanism_chemical"),
}
_GENE_DISEASE_LABELS = {
    "therapeutic": ("therapeutic_target_for", "has_therapeutic_target_gene"),
    "marker/mechanism": ("marker_mechanism_for", "has_marker_mechanism_gene"),
}


def _split(value: str) -> list[str]:
    return [part for part in (value or "").split("|") if part]


def _action_label(action: str) -> str:
    """``increases^expression`` -> ``increases_expression``."""
    return re.sub(r"[^a-z0-9]+", "_", action.lower().replace("^", "_")).strip("_")


def _classify(concept_id: str) -> tuple[str, str] | None:
    """Return ``(kind, key)``: ``mesh``/``omim``/``gene``/``cas`` and the bare key."""
    cleaned = (concept_id or "").strip()
    if cleaned.upper().startswith("CTD:"):
        cleaned = cleaned.split(":", 1)[1]
    if match := _MESH_RE.match(cleaned):
        return "mesh", match.group(1).upper()
    if match := _OMIM_RE.match(cleaned):
        return "omim", match.group(1)
    if match := _GENE_RE.match(cleaned):
        return "gene", match.group(1)
    if _CAS_RE.match(cleaned):
        return "cas", cleaned
    return None


def _store(concept: UnifiedConcept, raw: dict[str, Any]) -> None:
    """Keep the parsed CTD record on the concept (``source_data`` is dict-backed at runtime)."""
    if isinstance(concept.source_data, dict):
        concept.source_data[KnowledgeSource.CTD] = raw


def _iter_rows(path: Path, needle: str | None, lower: bool = False) -> Iterator[list[str]]:
    """Yield CSV rows of a (gzipped) CTD report whose raw line contains ``needle``.

    Comment lines (``#``) are skipped. The substring test happens before CSV parsing, which is
    what keeps scanning a few-hundred-MB file to seconds. Truncated gzip files (a sample, an
    interrupted copy) end the scan instead of raising.
    """
    if needle is not None and lower:
        needle = needle.lower()
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
        try:
            for line in handle:
                if line.startswith("#"):
                    continue
                if needle is not None and needle not in (line.lower() if lower else line):
                    continue
                yield next(csv.reader([line]))
        except EOFError:
            logger.warning(f"{path.name} ended unexpectedly (truncated file?)")


class CTDAdapter(KnowledgeSourceAdapter):
    """Adapter for CTD chemical-gene-disease data (bulk reports, non-commercial use)."""

    def __init__(self, config):
        super().__init__(config)
        self._scan_cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CTD

    def is_available(self) -> bool:
        """True when a core CTD report is already on disk or the download is allowed.

        The core reports are about 220 MB (chemical-disease alone is 164 MB), so the download is
        opt-in: ``CTD_DOWNLOAD=1`` or ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``. Otherwise a default
        multi-source lookup would start it on its own."""
        directory = self._data_dir()
        core = (FILE_CHEMICALS, FILE_DISEASES, FILE_IXNS, FILE_CHEM_DISEASES)
        return any((directory / name).exists() for name in core) or downloads_allowed(DOWNLOAD_ENV)

    # ------------------------------------------------------------------
    # Data files
    # ------------------------------------------------------------------

    @staticmethod
    def _data_dir() -> Path:
        configured = os.environ.get(DATA_DIR_ENV)
        return Path(configured) if configured else default_cache_dir() / "ctd"

    async def _dataset(self, filename: str, required: bool = True) -> Path | None:
        """Local path of a CTD report, downloading it on first use.

        Optional files (genes, genes-diseases: 123 MB / 3.2 GB) are returned only when they are
        already on disk or their opt-in environment variable is set; otherwise ``None``.
        """
        directory = self._data_dir()
        local = directory / filename
        if not required and not local.exists():
            if os.environ.get(_OPT_IN_ENV[filename]) != "1":
                return None
        return await ensure_dataset(
            CTD_REPORTS_URL + filename,
            filename=filename,
            cache_dir=directory,
            max_age_days=MAX_AGE_DAYS,
            decompress=False,
            headers={"User-Agent": "AID-PAIS-Knowledge-Lookup/1.0"},
        )

    async def _scan(
        self,
        filename: str,
        needle: str | None,
        col: int | None = None,
        value: str | None = None,
        *,
        in_list: bool = False,
        required: bool = True,
        lower: bool = False,
    ) -> list[list[str]] | None:
        """Rows of ``filename`` whose raw line contains ``needle`` and whose column ``col``
        equals ``value`` (or, with ``in_list``, lists it among its ``|``-separated parts).

        Returns ``None`` when an optional file is not available. Results are memoised.
        """
        cache_key = (filename, needle, col, value, in_list, lower)
        if cache_key in self._scan_cache:
            self._scan_cache.move_to_end(cache_key)
            return self._scan_cache[cache_key]
        path = await self._dataset(filename, required)
        if path is None:
            return None

        def _work() -> list[list[str]]:
            rows = []
            for row in _iter_rows(path, needle, lower):
                if col is not None:
                    cell = self._field(row, col)
                    if (value not in _split(cell)) if in_list else (cell != value):
                        continue
                rows.append(row)
            return rows

        rows = await asyncio.to_thread(_work)
        self._scan_cache[cache_key] = rows
        while len(self._scan_cache) > SCAN_CACHE_SIZE:
            self._scan_cache.popitem(last=False)
        return rows

    # ------------------------------------------------------------------
    # Row -> concept
    # ------------------------------------------------------------------

    @staticmethod
    def _field(row: list[str], index: int) -> str:
        return row[index].strip() if len(row) > index else ""

    def _chemical_to_concept(self, row: list[str]) -> UnifiedConcept | None:
        # ChemicalName,ChemicalID,CasRN,PubChemCID,PubChemSID,DTXSID,InChIKey,Definition,
        # ParentIDs,TreeNumbers,ParentTreeNumbers,MESHSynonyms,CTDCuratedSynonyms
        name, chem_id = self._field(row, 0), self._field(row, 1)
        if not name or not chem_id:
            return None
        concept = self._create_concept(chem_id, name, ConceptType.CHEMICAL)
        concept.add_identifier(
            KnowledgeSource.MESH, chem_id, name, f"{CTD_WEB_BASE}?type=chem&acc={chem_id}"
        )
        pubchem = self._field(row, 3).removeprefix("CID:")  # CTD writes "CID:2244"
        if pubchem:
            concept.add_identifier(KnowledgeSource.PUBCHEM, pubchem, name)
        synonyms = _split(self._field(row, 11)) + _split(self._field(row, 12))
        if concept.synonyms is not None:
            concept.synonyms.extend(dict.fromkeys(s for s in synonyms if s != name).keys())
            del concept.synonyms[MAX_SYNONYMS:]
        if (definition := self._field(row, 7)) and concept.definitions is not None:
            concept.definitions.append(definition)
        if concept.parents is not None:
            concept.parents.extend(_split(self._field(row, 8)))
        if concept.categories is not None:
            concept.categories.append("ctd_chemical")
        concept.confidence_score = 0.85
        raw = {
            "ChemicalName": name,
            "ChemicalID": chem_id,
            "CasRN": self._field(row, 2),
            "PubChemCID": pubchem,
            "DTXSID": self._field(row, 5),
            "InChIKey": self._field(row, 6),
            "TreeNumbers": _split(self._field(row, 9)),
        }
        _store(concept, raw)
        return concept

    def _disease_to_concept(self, row: list[str]) -> UnifiedConcept | None:
        # DiseaseName,DiseaseID,AltDiseaseIDs,Definition,ParentIDs,TreeNumbers,
        # ParentTreeNumbers,Synonyms,SlimMappings
        name, disease_id = self._field(row, 0), self._field(row, 1)
        if not name or not disease_id:
            return None
        concept = self._create_concept(disease_id, name, ConceptType.DISEASE)
        concept.add_identifier(
            KnowledgeSource.MESH, disease_id, name, f"{CTD_WEB_BASE}?type=disease&acc={disease_id}"
        )
        alt_ids = _split(self._field(row, 2))
        for alt in alt_ids:
            if alt.upper().startswith("OMIM:"):
                concept.add_identifier(KnowledgeSource.OMIM, alt, name)
        synonyms = [s for s in _split(self._field(row, 7)) if s != name]
        if concept.synonyms is not None:
            concept.synonyms.extend(dict.fromkeys(synonyms).keys())
            del concept.synonyms[MAX_SYNONYMS:]
        if (definition := self._field(row, 3)) and concept.definitions is not None:
            concept.definitions.append(definition)
        if concept.parents is not None:
            concept.parents.extend(_split(self._field(row, 4)))
        if concept.categories is not None:
            concept.categories.append("ctd_disease")
            concept.categories.extend(_split(self._field(row, 8)))
        concept.confidence_score = 0.85
        raw = {
            "DiseaseName": name,
            "DiseaseID": disease_id,
            "AltDiseaseIDs": alt_ids,
            "TreeNumbers": _split(self._field(row, 5)),
        }
        _store(concept, raw)
        return concept

    def _gene_to_concept(self, row: list[str]) -> UnifiedConcept | None:
        # GeneSymbol,GeneName,GeneID,AltGeneIDs,Synonyms,BioGRIDIDs,PharmGKBIDs,UniProtIDs
        symbol, name, gene_id = self._field(row, 0), self._field(row, 1), self._field(row, 2)
        if not symbol or not gene_id.isdigit():
            return None
        concept = self._create_concept(f"NCBIGene:{gene_id}", symbol, ConceptType.GENE)
        concept.add_identifier(
            KnowledgeSource.NCBI,
            gene_id,
            symbol,
            f"{CTD_WEB_BASE}?type=gene&acc={gene_id}",
        )
        if name and concept.definitions is not None:
            concept.definitions.append(name)
        if concept.synonyms is not None:
            concept.synonyms.extend(s for s in _split(self._field(row, 4)) if s != symbol)
            del concept.synonyms[MAX_SYNONYMS:]
        for uniprot in _split(self._field(row, 7)):
            concept.add_identifier(KnowledgeSource.UNIPROT, uniprot, symbol)
        if concept.categories is not None:
            concept.categories.append("ctd_gene")
        concept.confidence_score = 0.85
        raw = {
            "GeneSymbol": symbol,
            "GeneID": gene_id,
            "AltGeneIDs": _split(self._field(row, 3)),
            "PharmGKBIDs": _split(self._field(row, 6)),
            "BioGRIDIDs": _split(self._field(row, 5)),
        }
        _store(concept, raw)
        return concept

    # ------------------------------------------------------------------
    # Resolution of ids to rows
    # ------------------------------------------------------------------

    async def _first(self, filename: str, needle: str, col: int, value: str, **kw: Any):
        rows = await self._scan(filename, needle, col, value, **kw)
        return rows[0] if rows else None

    async def _gene_row(self, gene_id: str) -> list[str] | None:
        """Gene record from ``CTD_genes`` when available, else the id/symbol seen in the
        interaction file (which has no full name or synonyms)."""
        row = await self._first(FILE_GENES, f",{gene_id},", 2, gene_id, required=False)
        if row:
            return row
        hit = await self._first(FILE_IXNS, f",{gene_id},", 4, gene_id)
        return [self._field(hit, 3), "", gene_id] if hit else None

    async def _resolve(self, concept_id: str) -> tuple[str, list[str]] | None:
        """Resolve any supported id to ``(kind, row)`` with kind chemical|disease|gene."""
        classified = _classify(concept_id)
        if not classified:
            return None
        kind, key = classified
        if kind == "gene":
            gene = await self._gene_row(key)
            return ("gene", gene) if gene else None
        if kind == "omim":
            ident = f"OMIM:{key}"
            disease = await self._first(FILE_DISEASES, ident, 2, ident, in_list=True)
            return ("disease", disease) if disease else None
        if kind == "mesh":
            ident = f"MESH:{key}"
            disease = await self._first(FILE_DISEASES, f",{ident},", 1, ident)
            if disease:
                return "disease", disease
            chemical = await self._first(FILE_CHEMICALS, f",{ident},", 1, ident)
        else:  # CAS registry number
            chemical = await self._first(FILE_CHEMICALS, f",{key},", 2, key)
        return ("chemical", chemical) if chemical else None

    def _row_to_concept(self, kind: str, row: list[str]) -> UnifiedConcept | None:
        if kind == "chemical":
            return self._chemical_to_concept(row)
        if kind == "disease":
            return self._disease_to_concept(row)
        return self._gene_to_concept(row)

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    @staticmethod
    def _score(query: str, name: str, synonyms: list[str]) -> int | None:
        """Lower is better; ``None`` when the row does not match at all."""
        q, n = query.lower(), name.lower()
        syn = [s.lower() for s in synonyms]
        if n == q:
            return 0
        if q in syn:
            return 1
        if n.startswith(q):
            return 2
        if q in n:
            return 3
        if any(q in s for s in syn):
            return 4
        return None

    async def _search_file(
        self, filename: str, kind: str, query: str, syn_cols: tuple[int, ...]
    ) -> list[tuple[int, int, str, list[str]]]:
        """``(score, name length, kind, row)`` for rows whose name/synonyms match ``query``."""
        rows = await self._scan(filename, query.lower(), lower=True) or []
        ranked = []
        for row in rows:
            synonyms = [s for i in syn_cols for s in _split(self._field(row, i))]
            name = self._field(row, 0)
            if (score := self._score(query, name, synonyms)) is not None:
                ranked.append((score, len(name), kind, row))
        return ranked

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search chemicals and diseases by name/synonym (exact first); ids and CAS numbers
        resolve directly, and gene-symbol-like queries also look for an exact gene symbol.

        The first call downloads ``CTD_chemicals`` (10.5 MB) and ``CTD_diseases`` (1.8 MB).
        """
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            if _classify(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []

            chem, disease = await asyncio.gather(
                self._search_file(FILE_CHEMICALS, "chemical", query, (11, 12)),
                self._search_file(FILE_DISEASES, "disease", query, (7,)),
            )
            candidates = sorted(chem + disease, key=lambda t: (t[0], t[1]))
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for _, _, kind, row in candidates:
                concept = self._row_to_concept(kind, row)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)

            if _GENE_SYMBOL_RE.match(query) and (
                query.isupper() or any(c.isdigit() for c in query)
            ):
                gene = await self._search_gene_symbol(query)
                if gene and gene.primary_id not in seen:
                    concepts.insert(0, gene)  # an exact symbol beats substring name matches
            logger.info(f"CTD search for '{query}' returned {len(concepts[:limit])} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"CTD search failed for '{query}': {e}")
            return []

    async def _search_gene_symbol(self, symbol: str) -> UnifiedConcept | None:
        """Exact gene-symbol match in ``CTD_genes`` (if present) or the interaction file."""
        # Human symbols are upper case; matching them case-sensitively keeps the pre-filter
        # cheap (no per-line lower-casing of a few hundred MB).
        sym = symbol.upper()
        rows = await self._scan(FILE_GENES, f"{sym},", 0, sym, required=False)
        if rows:
            return self._gene_to_concept(rows[0])
        rows = await self._scan(FILE_IXNS, f",{sym},", 3, sym) or []
        rows = sorted(rows, key=lambda r: self._field(r, 6) != "Homo sapiens")
        for row in rows:
            if self._field(row, 4).isdigit():
                return self._gene_to_concept([sym, "", self._field(row, 4)])
        return None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for a chemical (``MESH:D001241``, CAS number), disease (``MESH:D003920``,
        ``OMIM:264300``) or gene (``NCBIGene:672``)."""
        try:
            resolved = await self._resolve(concept_id)
            return self._row_to_concept(*resolved) if resolved else None
        except Exception as e:
            logger.warning(f"CTD get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    @staticmethod
    def _interaction_edges(rows: list[list[str]], from_chemical: bool) -> list[dict[str, Any]]:
        """Chemical-gene interaction edges, one per (partner, action, organism).

        Rows: ChemicalName,ChemicalID,CasRN,GeneSymbol,GeneID,GeneForms,Organism,OrganismID,
        Interaction,InteractionActions,PubMedIDs. ``relation_label`` is the CTD action
        (``increases^expression`` -> ``increases_expression``), always stated from the
        chemical's side ("the chemical increases the expression of the gene"), whichever end
        the queried concept is.
        """
        merged: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            if from_chemical:
                partner_id = f"NCBIGene:{row[4]}" if len(row) > 4 and row[4] else ""
                partner_name, ptype = (row[3] if len(row) > 3 else ""), "gene"
            else:
                partner_id = f"MESH:{row[1]}" if len(row) > 1 and row[1] else ""
                partner_name, ptype = (row[0] if row else ""), "chemical"
            if not partner_id or not partner_name:
                continue
            organism = row[6] if len(row) > 6 else ""
            pmids = _split(row[10]) if len(row) > 10 else []
            actions = [_action_label(a) for a in _split(row[9] if len(row) > 9 else "")]
            for label in actions or ["interacts_with"]:
                edge = merged.setdefault(
                    (partner_id, label, organism),
                    {
                        "relation_label": label,
                        "related_id": partner_id,
                        "related_name": partner_name,
                        "source": "CTD",
                        "related_type": ptype,
                        "organism": organism or None,
                        "organism_id": (row[7] if len(row) > 7 else "") or None,
                        "interaction": (row[8] if len(row) > 8 else "")[:300],
                        "pmids": [],
                        "n_interactions": 0,
                    },
                )
                edge["n_interactions"] += 1
                edge["pmids"].extend(p for p in pmids if p not in edge["pmids"])
        edges = list(merged.values())
        for edge in edges:
            edge["n_pmids"] = len(edge["pmids"])
            edge["pmids"] = edge["pmids"][:MAX_PMIDS]
        edges.sort(key=lambda e: (e["organism"] != "Homo sapiens", -e["n_pmids"]))
        return edges

    @staticmethod
    def _evidence_edges(
        rows: list[list[str]],
        layout: dict[str, int],
        labels: dict[str, tuple[str, str]],
        forward: bool,
        partner_type: str,
    ) -> list[dict[str, Any]]:
        """Curated (``DirectEvidence`` set) chemical-disease or gene-disease edges.

        ``layout`` names the column of ``evidence``, ``pmids``, ``omim`` and of the partner's
        ``id`` / ``name`` / ``bare`` (True when the id lacks its ``MESH:`` prefix, as chemical
        ids in CTD's relation files do). Inferred rows (no direct evidence) are skipped.
        """
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            evidence = row[layout["evidence"]] if len(row) > layout["evidence"] else ""
            if evidence not in labels:
                continue
            partner_id = row[layout["id"]] if len(row) > layout["id"] else ""
            partner_name = row[layout["name"]] if len(row) > layout["name"] else ""
            if not partner_id or not partner_name:
                continue
            if layout.get("bare"):
                partner_id = f"MESH:{partner_id}"
            elif partner_type == "gene":
                partner_id = f"NCBIGene:{partner_id}"
            label = labels[evidence][0 if forward else 1]
            if (partner_id, label) in seen:
                continue
            seen.add((partner_id, label))
            pmids = _split(row[layout["pmids"]] if len(row) > layout["pmids"] else "")
            edges.append(
                {
                    "relation_label": label,
                    "related_id": partner_id,
                    "related_name": partner_name,
                    "source": "CTD",
                    "related_type": partner_type,
                    "direct_evidence": evidence,
                    "omim_ids": _split(row[layout["omim"]] if len(row) > layout["omim"] else ""),
                    "n_pmids": len(pmids),
                    "pmids": pmids[:MAX_PMIDS],
                }
            )
        edges.sort(key=lambda e: -e["n_pmids"])
        return edges

    @staticmethod
    def _round_robin(families: list[list[dict[str, Any]]], limit: int) -> list[dict[str, Any]]:
        """Interleave edge families so one huge family cannot crowd out the others."""
        out: list[dict[str, Any]] = []
        for rank in range(max((len(f) for f in families), default=0)):
            for family in families:
                if rank < len(family):
                    out.append(family[rank])
                    if len(out) >= limit:
                        return out
        return out

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Curated associations, interleaved across families and capped by ``limit``.

        * chemical: ``increases_expression`` / ``decreases_activity`` / ... gene interactions
          (human first), ``therapeutic_for`` and ``marker_mechanism_for`` diseases;
        * disease: ``treated_by`` / ``marker_mechanism_chemical`` chemicals and, when
          ``CTD_genes_diseases`` is available locally, ``therapeutic_target_for``-style gene
          edges (``has_therapeutic_target_gene`` / ``has_marker_mechanism_gene``);
        * gene: chemical interactions and, with ``CTD_genes_diseases``, disease edges.

        Every edge carries ``pmids`` (<= 25 of ``n_pmids``); interaction edges also the
        ``organism`` and an example ``interaction`` sentence; disease edges the
        ``direct_evidence`` type. Degrades to ``[]``.
        """
        if limit <= 0:
            return []
        try:
            resolved = await self._resolve(concept_id)
            if not resolved:
                return []
            kind, row = resolved
            families: list[list[dict[str, Any]]] = []
            if kind == "chemical":
                bare = self._field(row, 1).removeprefix("MESH:")
                ixns = await self._scan(FILE_IXNS, f",{bare},", 1, bare) or []
                families.append(self._interaction_edges(ixns, True))
                cd = await self._scan(FILE_CHEM_DISEASES, f",{bare},", 1, bare) or []
                layout = {"evidence": 5, "pmids": 9, "omim": 8, "id": 4, "name": 3}
                families.append(
                    self._evidence_edges(cd, layout, _CHEM_DISEASE_LABELS, True, "disease")
                )
            elif kind == "disease":
                ident = self._field(row, 1)
                cd = await self._scan(FILE_CHEM_DISEASES, f",{ident},", 4, ident) or []
                layout = {
                    "evidence": 5,
                    "pmids": 9,
                    "omim": 8,
                    "id": 1,
                    "name": 0,
                    "bare": 1,
                }  # bare: chemical ids lack "MESH:"
                families.append(
                    self._evidence_edges(cd, layout, _CHEM_DISEASE_LABELS, False, "chemical")
                )
                gd = await self._scan(FILE_GENE_DISEASES, f",{ident},", 3, ident, required=False)
                layout = {"evidence": 4, "pmids": 8, "omim": 7, "id": 1, "name": 0}
                families.append(
                    self._evidence_edges(gd or [], layout, _GENE_DISEASE_LABELS, False, "gene")
                )
            else:
                gene_id = self._field(row, 2)
                ixns = await self._scan(FILE_IXNS, f",{gene_id},", 4, gene_id) or []
                families.append(self._interaction_edges(ixns, False))
                gd = await self._scan(
                    FILE_GENE_DISEASES, f",{gene_id},", 1, gene_id, required=False
                )
                layout = {"evidence": 4, "pmids": 8, "omim": 7, "id": 3, "name": 2}
                families.append(
                    self._evidence_edges(gd or [], layout, _GENE_DISEASE_LABELS, True, "disease")
                )
            return self._round_robin(families, limit)
        except Exception as e:
            logger.warning(f"CTD get_relationships failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Mappings
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references CTD lists for the record (MeSH, CAS, PubChem, DSSTox, InChIKey for
        chemicals; OMIM and other alternate ids for diseases; NCBI Gene, UniProt, PharmGKB,
        BioGRID for genes)."""
        try:
            resolved = await self._resolve(concept_id)
            if not resolved:
                return []
            kind, row = resolved
            concept = self._row_to_concept(kind, row)
            if concept is None:
                return []
            pairs: list[tuple[str, str]] = []
            if kind == "chemical":
                pairs = [
                    ("MESH", self._field(row, 1)),
                    ("CAS", self._field(row, 2)),
                    ("PUBCHEM", self._field(row, 3).removeprefix("CID:")),
                    ("DSSTOX", self._field(row, 5)),
                    ("INCHIKEY", self._field(row, 6)),
                ]
            elif kind == "disease":
                pairs = [("MESH", self._field(row, 1))]
                for alt in _split(self._field(row, 2)):
                    prefix = alt.split(":", 1)[0].upper() if ":" in alt else "ALT"
                    pairs.append((prefix, alt))
            else:
                gene_id = self._field(row, 2)
                pairs = [("NCBI", gene_id)]
                pairs += [("NCBI", a) for a in _split(self._field(row, 3)) if a != gene_id]
                pairs += [("UNIPROT", u) for u in _split(self._field(row, 7))]
                pairs += [("PHARMGKB", p) for p in _split(self._field(row, 6))]
                pairs += [("BIOGRID", b) for b in _split(self._field(row, 5))]
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for source, value in pairs:
                if not value or (source, value) in seen:
                    continue
                seen.add((source, value))
                mappings.append(
                    {
                        "fromId": concept.primary_id,
                        "toId": value,
                        "fromSource": "CTD",
                        "toSource": source,
                        "mappingType": "xref",
                        "confidence": 0.95,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"CTD get_mappings failed for '{concept_id}': {e}")
            return []
