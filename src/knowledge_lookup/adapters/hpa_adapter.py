"""
Human Protein Atlas Knowledge Source Adapter

The Human Protein Atlas (HPA, https://www.proteinatlas.org) maps human genes/proteins to the
tissues, blood/immune cell types, cells and subcellular compartments where they are expressed.
This adapter uses the keyless ``search_download`` API, which returns exactly the columns you
ask for, so every call is one small request (about 1 KB per gene for the details call, ~0.4 s)
instead of the 10 KB per-gene ``<ENSG>.json`` or the 1.7 MB ``<ENSG>.xml``:

* search: ``search_download.php?search=<text>&format=json&columns=<summary columns>`` -
  free-text over symbols, synonyms and descriptions; returns every match (``limit`` is applied
  client-side), exact symbol matches first.
* details/relationships: the same endpoint with ``search=<ENSG id>`` (exactly one hit) and the
  per-tissue / per-blood-cell nTPM columns (``t_RNA_*``, ``blood_RNA_*``).

What is in the data (all human, consensus RNA expression in nTPM unless noted): RNA tissue
specificity/distribution, nTPM in 50 tissues, nTPM in 18 blood immune cell types (HPA blood
atlas: monocytes, T/B/NK cells, dendritic cells, granulocytes), the subset where the gene is
"enriched/enhanced" (``RNA tissue specific nTPM`` / ``RNA blood cell specific nTPM``),
plasma-protein membership (protein class "Plasma proteins"), blood concentration (pg/L, from
immunoassay and mass spectrometry) and subcellular location. Protein-level IHC tissue data
exists upstream but is not requested here.

Licence: HPA's licence page (https://www.proteinatlas.org/about/licence, checked live) states
CC BY 4.0 for all copyrightable parts; earlier releases and many references say CC BY-SA 3.0.
Either way: attribute the Human Protein Atlas (cite Uhlen et al., Science 2015, and the
version you used), and treat third-party sub-data separately. The adapter does not fetch or
store anything beyond the requested columns.

Quirks: tissue columns for endometrium, skin and stomach carry a ``_1`` suffix upstream
(``t_RNA_skin_1``); the adapter reports plain names ("skin"). ``search`` is free text, so
"CD4" also returns genes that merely mention CD4. The tissue/blood column lists below are
HPA's current set; a renamed or removed column is silently omitted by the API, in which case
that tissue is simply missing from the results.
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._safety_common import dedupe_mappings, fill_concept, make_mapping, to_float

logger = logging.getLogger(__name__)

HPA_BASE_URL = "https://www.proteinatlas.org"
HPA_SEARCH_ENDPOINT = "/api/search_download.php"
_CACHE_TTL = 6 * 60 * 60  # HPA releases are infrequent; avoid re-asking within a session

# Column specifiers (see https://www.proteinatlas.org/about/help/dataaccess).
_SUMMARY_COLUMNS = "g,gs,eg,gd,up,rnats,rnatd,rnatsm,rnabcs,rnabcd,rnabcsm,scl"
_DETAIL_BASE_COLUMNS = (
    "g,gs,eg,gd,up,chr,chrp,pc,di,evih,rnats,rnatd,rnatsm,rnabcs,rnabcd,rnabcsm,"
    "scl,secl,blconcia,blconcms"
)
_TISSUES = (
    "adipose_tissue adrenal_gland amygdala appendix basal_ganglia blood_vessel bone_marrow "
    "breast cerebellum cerebral_cortex cervix choroid_plexus colon duodenum endometrium_1 "
    "epididymis esophagus fallopian_tube gallbladder heart_muscle hippocampal_formation "
    "hypothalamus kidney liver lung lymph_node midbrain ovary pancreas parathyroid_gland "
    "pituitary_gland placenta prostate rectum retina salivary_gland seminal_vesicle "
    "skeletal_muscle skin_1 small_intestine smooth_muscle spinal_cord spleen stomach_1 testis "
    "thymus thyroid_gland tongue tonsil urinary_bladder vagina"
).split()
_BLOOD_CELLS = (
    "MAIT_T-cell NK-cell T-reg basophil classical_monocyte eosinophil gdT-cell "
    "intermediate_monocyte memory_B-cell memory_CD4_T-cell memory_CD8_T-cell myeloid_DC "
    "naive_B-cell naive_CD4_T-cell naive_CD8_T-cell neutrophil non-classical_monocyte "
    "plasmacytoid_DC total_PBMC"
).split()
_DETAIL_COLUMNS = ",".join(
    [_DETAIL_BASE_COLUMNS]
    + [f"t_RNA_{t}" for t in _TISSUES]
    + [f"blood_RNA_{c}" for c in _BLOOD_CELLS]
)

_TISSUE_KEY = re.compile(r"^Tissue RNA - (.+) \[nTPM\]$")
_BLOOD_KEY = re.compile(r"^Blood RNA - (.+) \[nTPM\]$")
_ENSG_RE = re.compile(r"^ENSG\d{11}(?:\.\d+)?$", re.IGNORECASE)

#: nTPM below this counts as "not meaningfully expressed" when filling up edge lists.
EXPRESSED_NTPM = 1.0
#: HPA's pooled "total PBMC" sample is not a cell type.
_NOT_A_CELL_TYPE = {"total PBMC"}


def _tidy_tissue(name: str) -> str:
    """``skin 1`` / ``stomach 1`` / ``endometrium 1`` -> plain tissue name."""
    return re.sub(r" 1$", "", name.strip())


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v not in (None, "")]
    if isinstance(value, str) and value:
        return [value]
    return []


def _ntpm_dict(value: Any) -> dict[str, float]:
    """``{"liver": "143.1"}`` -> ``{"liver": 143.1}`` (HPA ships numbers as strings)."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for name, raw in value.items():
        number = to_float(raw)
        if number is not None:
            out[_tidy_tissue(str(name))] = number
    return out


def _top(table: dict[str, float], n: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(((k, v) for k, v in table.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))
    return [{"name": name, "ntpm": ntpm} for name, ntpm in ranked[:n]]


class HumanProteinAtlasAdapter(KnowledgeSourceAdapter):
    """Adapter for the Human Protein Atlas (expression of human genes/proteins).

    Concept ids are Ensembl gene ids (``ENSG00000012048``); approved gene symbols
    (``BRCA1``) are accepted anywhere an id is. Licence and attribution: see module docs.
    """

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = HPA_BASE_URL

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.HUMANPROTEINATLAS

    def is_available(self) -> bool:
        return True  # keyless public API

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _query(self, search: str, columns: str) -> list[dict[str, Any]]:
        """One ``search_download`` call; ``[]`` for no hit. Cached per (search, columns)."""
        key = self._get_cache_key("search_download", search, columns)
        cached = self._get_from_cache(key)
        if cached is not None:
            return cached
        data = await self._make_request(
            f"{self.base_url}{HPA_SEARCH_ENDPOINT}",
            params={"search": search, "format": "json", "columns": columns, "compress": "no"},
        )
        # the declared type is dict (JSON object) but this endpoint returns a JSON array
        payload: Any = data
        records: list[dict[str, Any]] = (
            [r for r in payload if isinstance(r, dict)] if isinstance(payload, list) else []
        )
        self._set_in_cache(key, records, ttl=_CACHE_TTL)
        return records

    async def _resolve_ensg(self, concept_id: str) -> str | None:
        """Ensembl gene id for an ENSG id or an exact gene symbol / synonym, else ``None``."""
        value = (concept_id or "").strip()
        for prefix in ("HPA:", "ENSEMBL:", "HUMANPROTEINATLAS:"):
            if value.upper().startswith(prefix):
                value = value[len(prefix) :].strip()
        if not value:
            return None
        if _ENSG_RE.match(value):
            return value.split(".")[0].upper()
        needle = value.upper()
        for record in await self._query(value, _SUMMARY_COLUMNS):
            symbols = [str(record.get("Gene", ""))] + _as_list(record.get("Gene synonym"))
            if needle in {s.upper() for s in symbols} and record.get("Ensembl"):
                return str(record["Ensembl"])
        return None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Free-text search over HPA genes (symbol, synonyms, description).

        Results are re-ranked so exact symbol hits come first (confidence 1.0), then exact
        synonym hits (0.9), then other matches (0.6). The concepts carry the compact
        expression summary of the search columns (tissue specificity/distribution, enriched
        tissues, blood-cell specificity, subcellular location); use
        :meth:`get_concept_details` for the per-tissue / per-immune-cell nTPM tables.
        """
        try:
            text = (query or "").strip()
            if not text or limit <= 0:
                return []
            records = await self._query(text, _SUMMARY_COLUMNS)
            needle = text.upper()

            def rank(record: dict[str, Any]) -> int:
                if str(record.get("Gene", "")).upper() == needle:
                    return 0
                if needle in {s.upper() for s in _as_list(record.get("Gene synonym"))}:
                    return 1
                return 2

            seen: set[str] = set()
            concepts: list[UnifiedConcept] = []
            for record in sorted(records, key=rank):  # stable: keeps HPA's own order inside a rank
                ensg = str(record.get("Ensembl", ""))
                if not ensg or ensg in seen:
                    continue
                seen.add(ensg)
                concept = self._build_concept(record)
                if concept is not None:
                    concept.confidence_score = (1.0, 0.9, 0.6)[rank(record)]
                    concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"HPA search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"HPA search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Gene concept with the full expression summary (top tissues, immune cells, ...)."""
        try:
            record = await self._gene_record(concept_id)
            if record is None:
                return None
            concept = self._build_concept(record)
            if concept is not None:
                concept.confidence_score = 1.0
            return concept
        except Exception as e:
            logger.error(f"HPA get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _gene_record(self, concept_id: str) -> dict[str, Any] | None:
        ensg = await self._resolve_ensg(concept_id)
        if ensg is None:
            return None
        records = await self._query(ensg, _DETAIL_COLUMNS)
        for record in records:
            if str(record.get("Ensembl", "")).upper() == ensg:
                return record
        return None

    @staticmethod
    def _tables(record: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
        """(tissue -> nTPM, blood immune cell -> nTPM) parsed from the per-column keys."""
        tissues: dict[str, float] = {}
        cells: dict[str, float] = {}
        for key, raw in record.items():
            number = to_float(raw)
            if number is None:
                continue
            if m := _TISSUE_KEY.match(key):
                tissues[_tidy_tissue(m.group(1))] = number
            elif m := _BLOOD_KEY.match(key):
                cells[m.group(1)] = number
        return tissues, cells

    def _build_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        ensg = str(record.get("Ensembl") or "")
        symbol = str(record.get("Gene") or "")
        if not ensg or not symbol:
            return None
        concept = self._create_concept(ensg, symbol, ConceptType.GENE)
        concept.add_identifier(
            KnowledgeSource.ENSEMBL, ensg, symbol, f"https://www.ensembl.org/id/{ensg}"
        )
        for accession in _as_list(record.get("Uniprot")):
            concept.add_identifier(
                KnowledgeSource.UNIPROT,
                accession,
                symbol,
                f"https://www.uniprot.org/uniprot/{accession}",
            )
        concept.add_identifier(
            KnowledgeSource.HUMANPROTEINATLAS,
            ensg,
            symbol,
            f"{self.base_url}/{ensg}-{symbol}",
        )

        tissues, cells = self._tables(record)
        cells_only = {k: v for k, v in cells.items() if k not in _NOT_A_CELL_TYPE}
        enriched_tissues = _ntpm_dict(record.get("RNA tissue specific nTPM"))
        enriched_cells = _ntpm_dict(record.get("RNA blood cell specific nTPM"))
        protein_classes = _as_list(record.get("Protein class"))
        summary: dict[str, Any] = {
            "ensembl": ensg,
            "symbol": symbol,
            "description": record.get("Gene description"),
            "uniprot": _as_list(record.get("Uniprot")),
            "chromosome": record.get("Chromosome"),
            "position": record.get("Position"),
            "protein_class": protein_classes,
            "evidence": record.get("HPA evidence"),
            "rna_tissue_specificity": record.get("RNA tissue specificity"),
            "rna_tissue_distribution": record.get("RNA tissue distribution"),
            "rna_tissue_enriched_ntpm": enriched_tissues,
            "rna_blood_cell_specificity": record.get("RNA blood cell specificity"),
            "rna_blood_cell_distribution": record.get("RNA blood cell distribution"),
            "rna_blood_cell_enriched_ntpm": enriched_cells,
            "subcellular_location": _as_list(record.get("Subcellular location")),
            "secretome_location": record.get("Secretome location"),
            "disease_involvement": _as_list(record.get("Disease involvement")),
        }
        summary["plasma_protein"] = "Plasma proteins" in protein_classes
        for label, key in (
            ("immunoassay", "Blood concentration - Conc. blood IM [pg/L]"),
            ("mass_spec", "Blood concentration - Conc. blood MS [pg/L]"),
        ):
            value = to_float(record.get(key))  # IM comes as a number, MS as a string
            if value is not None:
                summary.setdefault("blood_concentration_pg_per_l", {})[label] = value
        if tissues:
            summary["top_tissues_ntpm"] = _top(tissues)
        if cells_only:
            summary["top_blood_cells_ntpm"] = _top(cells_only)

        description = record.get("Gene description")
        fill_concept(
            concept,
            KnowledgeSource.HUMANPROTEINATLAS,
            summary,
            categories=protein_classes,
            semantic_types=["gene"],
            definitions=[str(description)] if description else [],
            synonyms=[symbol, *_as_list(record.get("Gene synonym"))],
        )
        return concept

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Gene -> tissues (``expressed_in``) and gene -> blood immune cell types
        (``expressed_in_cell_type``), each with ``ntpm`` (consensus RNA, nTPM).

        ``limit`` applies to each of the two relation types. Tissues/cells in HPA's
        "enriched / group enriched / enhanced" list come first with ``enriched=True`` (the
        enriched list can name tissue groups such as "lymphoid tissue", flagged
        ``scope="tissue group"``); the remaining slots are filled with the highest-expressed
        others (``enriched=False``, nTPM >= 1). ``specificity`` is HPA's category for the whole
        gene ("Tissue enhanced", "Group enriched", "Low tissue specificity", ...).
        """
        try:
            if limit <= 0:
                return []
            record = await self._gene_record(concept_id)
            if record is None:
                return []
            tissues, cells = self._tables(record)
            cells = {k: v for k, v in cells.items() if k not in _NOT_A_CELL_TYPE}
            edges = self._edges(
                "expressed_in",
                "tissue",
                tissues,
                _ntpm_dict(record.get("RNA tissue specific nTPM")),
                record.get("RNA tissue specificity"),
                limit,
            )
            edges += self._edges(
                "expressed_in_cell_type",
                "immune cell (blood)",
                cells,
                _ntpm_dict(record.get("RNA blood cell specific nTPM")),
                record.get("RNA blood cell specificity"),
                limit,
            )
            return edges
        except Exception as e:
            logger.warning(f"HPA get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _edges(
        label: str,
        kind: str,
        table: dict[str, float],
        enriched: dict[str, float],
        specificity: Any,
        limit: int,
    ) -> list[dict[str, Any]]:
        def edge(name: str, ntpm: float, is_enriched: bool) -> dict[str, Any]:
            out: dict[str, Any] = {
                "relation_label": label,
                "related_id": name,
                "related_name": name,
                "source": "HUMANPROTEINATLAS",
                "related_type": kind,
                "ntpm": ntpm,
                "enriched": is_enriched,
                "specificity": specificity,
                "evidence": "HPA consensus RNA expression (nTPM)",
            }
            if is_enriched and name not in table:
                out["scope"] = "tissue group"
            return out

        results = [
            edge(name, ntpm, True)
            for name, ntpm in sorted(enriched.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        taken = {e["related_name"] for e in results}
        for name, ntpm in sorted(table.items(), key=lambda kv: (-kv[1], kv[0])):
            if name not in taken and ntpm >= EXPRESSED_NTPM:
                results.append(edge(name, ntpm, False))
        return results[:limit]

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Ensembl gene id, UniProt accessions and the HGNC approved symbol of the gene.

        HPA does not return numeric HGNC ids; its ``Gene`` field is the HGNC approved symbol,
        so the HGNC mapping is by symbol (``mappingType="symbol"``, confidence 0.95).
        """
        try:
            records = await self._query_ids(concept_id)
            if records is None:
                return []
            ensg, symbol, accessions = records
            mappings = [make_mapping(ensg, "HUMANPROTEINATLAS", ensg, "ENSEMBL", "exact", 1.0)]
            for accession in accessions:
                mappings.append(
                    make_mapping(ensg, "HUMANPROTEINATLAS", accession, "UNIPROT", "xref", 1.0)
                )
            mappings.append(
                make_mapping(ensg, "HUMANPROTEINATLAS", symbol, "HGNC", "symbol", 0.95)
            )
            return dedupe_mappings(mappings)
        except Exception as e:
            logger.warning(f"HPA get_mappings failed for '{concept_id}': {e}")
            return []

    async def _query_ids(self, concept_id: str) -> tuple[str, str, list[str]] | None:
        """(ENSG, symbol, UniProt accessions) using only the light summary columns."""
        ensg = await self._resolve_ensg(concept_id)
        if ensg is None:
            return None
        for record in await self._query(ensg, _SUMMARY_COLUMNS):
            if str(record.get("Ensembl", "")).upper() == ensg and record.get("Gene"):
                return ensg, str(record["Gene"]), _as_list(record.get("Uniprot"))
        return None
