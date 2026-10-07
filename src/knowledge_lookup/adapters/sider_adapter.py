"""
SIDER Knowledge Source Adapter

SIDER (Side Effect Resource, EMBL) 4.1 lists adverse drug reactions that were text-mined
from FDA drug-label package inserts and mapped to MedDRA. It is only published as flat
files (http://sideeffects.embl.de/download/), so this adapter downloads the small TSV files
once through :func:`knowledge_lookup.utils.dataset_cache.ensure_dataset` (about 5.5 MB in
total, nothing at construction time, only when a method needs the data), indexes them in
memory and answers every call from that index.

Caveats worth knowing before you rely on it:

* **Outdated.** SIDER 4.1 was released in October 2015 (the site was last touched in 2016) and
  is no longer updated. Labels changed since then; use it for historical / label-derived
  side-effect lists, not as a current safety reference. For current label data see OnSIDES.
* **Licence.** The download page currently states CC BY-SA 4.0 (older SIDER releases and the
  original paper used CC BY-NC-SA; treat the data as share-alike and, to be safe, non-commercial
  unless you have checked the licence yourself). Attribute Kuhn et al., NAR 2016.
* **Label-derived, not causal.** Entries mean "mentioned on a label", not "proven cause", and
  many side effects are also symptoms of the treated disease.
* Identifiers are STITCH compound ids: ``CID1xxxxxxxx`` ("flat", stereo-merged) equals
  ``100000000 + PubChem CID``; ``CID0xxxxxxxx`` ("stereo") equals the PubChem CID itself.

Files used (``https://sideeffects.embl.de/media/download/``; the ``/download/<file>`` links
on the old http host return 404): ``drug_names.tsv`` (34 KB), ``drug_atc.tsv`` (33 KB),
``meddra_all_se.tsv.gz`` (2.4 MB), ``meddra_freq.tsv.gz`` (2.1 MB, loaded on first
relationship call) and ``meddra.tsv.gz`` (1.1 MB, loaded on first MedDRA mapping call).

Set ``SIDER_DATA_DIR`` to a directory that already contains (or should receive) these files
to avoid the download or to work offline; ``.gz`` and decompressed copies are both accepted.
"""

import asyncio
import logging
import os
import re
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ..utils.dataset_cache import default_cache_dir, downloads_allowed, ensure_dataset
from ._safety_common import (
    dedupe_mappings,
    fill_concept,
    make_mapping,
    match_score,
    to_float,
    tsv_rows,
)

logger = logging.getLogger(__name__)

SIDER_BASE_URL = "https://sideeffects.embl.de/media/download"
SIDER_DATA_DIR_ENV = "SIDER_DATA_DIR"
SIDER_DOWNLOAD_ENV = "SIDER_DOWNLOAD"

# Logical name -> file name on the server (gz files are kept decompressed in the cache).
SIDER_FILES: dict[str, str] = {
    "names": "drug_names.tsv",
    "atc": "drug_atc.tsv",
    "se": "meddra_all_se.tsv.gz",
    "freq": "meddra_freq.tsv.gz",
    "meddra": "meddra.tsv.gz",
}

# SIDER 4.1 is frozen: never re-download a cached copy.
_MAX_AGE_DAYS = None

# STITCH flat ids are PubChem CID + 100000000 (verified: CID100002244 -> CID 2244 = aspirin).
_FLAT_OFFSET = 100_000_000
_FLAT_RE = re.compile(r"^CID1\d{8}$", re.IGNORECASE)
_STEREO_RE = re.compile(r"^CID0\d{8}$", re.IGNORECASE)
_CUI_RE = re.compile(r"^C\d{7}$", re.IGNORECASE)
_ATC_RE = re.compile(r"^[A-Z]\d{2}([A-Z]([A-Z]\d{0,2})?)?$")

# Parsed indexes are shared between adapter instances (a fresh adapter per lookup would
# otherwise re-parse the files every time), keyed by the resolved file paths.
_INDEX_CACHE: dict[tuple, Any] = {}
_INDEX_LOCK = threading.Lock()


# (description, lower bound, upper bound, is_placebo) as in meddra_freq columns 5-7 and 4
_FreqEntry = tuple[str, float | None, float | None, bool]


def flat_to_pubchem_cid(flat_id: str) -> int | None:
    """``CID100002244`` -> ``2244``; ``None`` if *flat_id* is not a STITCH flat id."""
    if not _FLAT_RE.match(flat_id):
        return None
    return int(flat_id[3:]) - _FLAT_OFFSET


def pubchem_cid_to_flat(cid: int) -> str:
    """``2244`` -> ``CID100002244``."""
    return f"CID{cid + _FLAT_OFFSET:09d}"


class SIDERAdapter(KnowledgeSourceAdapter):
    """Adapter for SIDER 4.1 drug side effects (outdated, label-derived; see module docs)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.data_dir = os.getenv(SIDER_DATA_DIR_ENV) or None
        self.base_url = SIDER_BASE_URL
        self._index: dict[str, Any] | None = None
        self._freq: dict[tuple[str, str], list[_FreqEntry]] = {}
        self._freq_loaded = False
        self._meddra: dict[str, list[tuple[str, str, str]]] | None = None
        self._lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.SIDER

    def is_available(self) -> bool:
        """True when ``SIDER_DATA_DIR`` is set, the files are already cached, or the ~5.5 MB
        download is allowed (``SIDER_DOWNLOAD=1`` or ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``)."""
        if self.data_dir:
            return Path(self.data_dir).is_dir()
        name = SIDER_FILES["se"]
        directory = default_cache_dir()
        if (directory / name.removesuffix(".gz")).exists() or (directory / name).exists():
            return True
        return downloads_allowed(SIDER_DOWNLOAD_ENV)

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    async def _dataset(self, key: str) -> Path:
        """Return a local path to SIDER file *key*, downloading it only if absent."""
        name = SIDER_FILES[key]
        if self.data_dir:
            directory = Path(self.data_dir)
            for candidate in (directory / name.removesuffix(".gz"), directory / name):
                if candidate.exists():
                    return candidate
        return await ensure_dataset(
            f"{self.base_url}/{name}",
            cache_dir=self.data_dir,
            max_age_days=_MAX_AGE_DAYS,
        )

    async def _load_index(self) -> dict[str, Any]:
        """Build (once) the drug / side-effect index from names, ATC and meddra_all_se."""
        if self._index is not None:
            return self._index
        async with self._lock:
            if self._index is None:
                paths = (
                    str(await self._dataset("names")),
                    str(await self._dataset("atc")),
                    str(await self._dataset("se")),
                )
                self._index = await asyncio.to_thread(self._cached_build, paths)
        return self._index

    @staticmethod
    def _cached_build(paths: tuple[str, ...]) -> dict[str, Any]:
        key = ("index", *paths, *(Path(p).stat().st_mtime_ns for p in paths))
        with _INDEX_LOCK:
            if key not in _INDEX_CACHE:
                _INDEX_CACHE[key] = SIDERAdapter._build_index(*(Path(p) for p in paths))
            return _INDEX_CACHE[key]

    @staticmethod
    def _build_index(names_path: Path, atc_path: Path, se_path: Path) -> dict[str, Any]:
        """Parse the three base files.

        ``meddra_all_se`` lists every label term as LLT plus its PT; only the non-LLT rows are
        kept so that "Abdominal cramps" and "Abdominal pain" collapse onto the PT, which is
        what the frequency file and downstream MedDRA users expect.
        """
        names: dict[str, str] = {}
        for row in tsv_rows(names_path):
            if len(row) >= 2:
                names[row[0]] = row[1]

        atc: dict[str, list[str]] = defaultdict(list)
        for row in tsv_rows(atc_path):
            if len(row) >= 2 and row[1] not in atc[row[0]]:
                atc[row[0]].append(row[1])

        se_by_drug: dict[str, dict[str, str]] = defaultdict(dict)
        drugs_by_se: dict[str, set[str]] = defaultdict(set)
        se_names: dict[str, str] = {}
        stereo: dict[str, set[str]] = defaultdict(set)
        stereo_to_flat: dict[str, str] = {}
        for row in tsv_rows(se_path):
            if len(row) < 6:
                continue
            flat, stereo_id, _label_cui, term_type, cui, term = row[:6]
            stereo[flat].add(stereo_id)
            stereo_to_flat[stereo_id] = flat
            if term_type == "LLT":
                continue
            se_by_drug[flat].setdefault(cui, term)
            drugs_by_se[cui].add(flat)
            se_names.setdefault(cui, term)

        return {
            "names": names,
            "atc": dict(atc),
            "se_by_drug": dict(se_by_drug),
            "drugs_by_se": dict(drugs_by_se),
            "se_names": se_names,
            "stereo": {k: sorted(v) for k, v in stereo.items()},
            "stereo_to_flat": stereo_to_flat,
        }

    async def _load_freq(self) -> None:
        """Load ``meddra_freq`` (side-effect frequencies) once, on first need."""
        if self._freq_loaded:
            return
        async with self._lock:
            if not self._freq_loaded:
                path = await self._dataset("freq")
                key = ("freq", str(path), path.stat().st_mtime_ns)

                def build() -> dict[tuple[str, str], list[_FreqEntry]]:
                    with _INDEX_LOCK:
                        if key not in _INDEX_CACHE:
                            _INDEX_CACHE[key] = SIDERAdapter._build_freq(path)
                        return _INDEX_CACHE[key]

                self._freq = await asyncio.to_thread(build)
                self._freq_loaded = True

    @staticmethod
    def _build_freq(path: Path) -> dict[tuple[str, str], list[_FreqEntry]]:
        """(flat id, PT CUI) -> distinct (description, lower, upper, is_placebo) tuples."""
        freq: dict[tuple[str, str], set[_FreqEntry]] = defaultdict(set)
        for row in tsv_rows(path):
            if len(row) < 10 or row[7] == "LLT":
                continue
            flat, placebo, desc, low, high, cui = row[0], row[3], row[4], row[5], row[6], row[8]
            freq[(flat, cui)].add((desc, to_float(low), to_float(high), placebo == "placebo"))
        return {k: sorted(v, key=lambda t: (t[2] or 0.0, t[0])) for k, v in freq.items()}

    async def _load_meddra(self) -> dict[str, list[tuple[str, str, str]]]:
        """Load ``meddra.tsv``: UMLS CUI -> [(MedDRA code, term type, name)]."""
        if self._meddra is not None:
            return self._meddra
        async with self._lock:
            if self._meddra is None:
                path = await self._dataset("meddra")

                def build() -> dict[str, list[tuple[str, str, str]]]:
                    result: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
                    for row in tsv_rows(path):
                        if len(row) >= 4:
                            result[row[0]].append((row[2], row[1], row[3]))
                    return dict(result)

                self._meddra = await asyncio.to_thread(build)
        return self._meddra

    # ------------------------------------------------------------------
    # Id handling
    # ------------------------------------------------------------------

    @staticmethod
    def _strip(concept_id: str) -> str:
        value = (concept_id or "").strip()
        if value.upper().startswith("SIDER:"):
            value = value[6:]
        return value.strip()

    def _resolve(self, concept_id: str, index: dict[str, Any]) -> tuple[str, str] | None:
        """Classify *concept_id*; returns ``("drug", flat_id)`` or ``("se", CUI)``.

        Accepts STITCH flat (``CID100002244``) and stereo (``CID000002244``) ids, a
        ``PUBCHEM:<cid>`` / ``CID:<cid>`` form for drugs and UMLS CUIs (``C0015672`` /
        ``UMLS:C0015672``) for side effects. Anything unknown returns ``None``.
        """
        value = self._strip(concept_id)
        if not value:
            return None
        upper = value.upper()
        if upper.startswith("UMLS:"):
            upper = upper[5:]
        if _CUI_RE.match(upper):
            return ("se", upper) if upper in index["drugs_by_se"] else None
        if _FLAT_RE.match(upper):
            flat = upper
        elif _STEREO_RE.match(upper):
            flat = index["stereo_to_flat"].get(upper, "")
        else:
            m = re.match(r"^(?:PUBCHEM(?:\.COMPOUND)?|CID)[:_ ]?(\d+)$", upper)
            flat = pubchem_cid_to_flat(int(m.group(1))) if m else ""
        if flat and (flat in index["names"] or flat in index["se_by_drug"]):
            return ("drug", flat)
        return None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search drugs (name, ATC code, STITCH id) and side effects (name) by substring.

        Ranking: exact match > prefix > word match > substring; drugs rank before side
        effects on ties. ``search_concepts("fatigue")`` returns the "Fatigue" side effect
        (UMLS C0015672) first, followed by related terms such as "Chronic fatigue syndrome".
        """
        try:
            needle = (query or "").strip().lower()
            if not needle or limit <= 0:
                return []
            index = await self._load_index()

            direct = self._resolve(query, index)
            if direct:
                concept = self._build_concept(direct, index)
                return [concept] if concept else []

            scored: list[tuple[float, int, str, tuple[str, str]]] = []
            for flat, name in index["names"].items():
                score = match_score(needle, name.lower())
                if score is None and _ATC_RE.match(query.strip().upper()):
                    if any(
                        code.startswith(query.strip().upper())
                        for code in index["atc"].get(flat, [])
                    ):
                        score = 0.5
                if score is not None:
                    scored.append((score, 0, name.lower(), ("drug", flat)))
            for cui, name in index["se_names"].items():
                score = match_score(needle, name.lower())
                if score is not None:
                    scored.append((score, 1, name.lower(), ("se", cui)))
            scored.sort(key=lambda item: (-item[0], item[1], item[2]))

            concepts: list[UnifiedConcept] = []
            for score, _kind, _name, ref in scored[:limit]:
                concept = self._build_concept(ref, index)
                if concept:
                    concept.confidence_score = score
                    concepts.append(concept)
            logger.info(f"SIDER search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"SIDER search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Drug (STITCH id) or side-effect (UMLS CUI) concept with its SIDER summary."""
        try:
            index = await self._load_index()
            ref = self._resolve(concept_id, index)
            if ref is None:
                return None
            concept = self._build_concept(ref, index)
            if concept is not None:
                concept.confidence_score = 1.0
            return concept
        except Exception as e:
            logger.error(f"SIDER get_concept_details failed for '{concept_id}': {e}")
            return None

    def _build_concept(self, ref: tuple[str, str], index: dict[str, Any]) -> UnifiedConcept | None:
        kind, key = ref
        if kind == "drug":
            return self._drug_concept(key, index)
        return self._side_effect_concept(key, index)

    def _drug_concept(self, flat: str, index: dict[str, Any]) -> UnifiedConcept | None:
        name = index["names"].get(flat)
        if not name:
            return None
        concept = self._create_concept(flat, name, ConceptType.DRUG)
        cid = flat_to_pubchem_cid(flat)
        if cid is not None:
            concept.add_identifier(
                KnowledgeSource.PUBCHEM,
                str(cid),
                name,
                f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            )
        atc_codes = index["atc"].get(flat, [])
        n_side_effects = len(index["se_by_drug"].get(flat, {}))
        fill_concept(
            concept,
            KnowledgeSource.SIDER,
            {
                "stitch_flat_id": flat,
                "stitch_stereo_ids": index["stereo"].get(flat, []),
                "pubchem_cid": cid,
                "atc_codes": atc_codes,
                "n_side_effects": n_side_effects,
                "release": "SIDER 4.1 (2015)",
            },
            categories=[f"ATC:{code}" for code in atc_codes],
            semantic_types=["drug"],
            definitions=[
                f"{name}: {n_side_effects} side effects listed on drug labels "
                "(SIDER 4.1, 2015; label-derived, not causal)."
            ],
        )
        return concept

    def _side_effect_concept(self, cui: str, index: dict[str, Any]) -> UnifiedConcept | None:
        name = index["se_names"].get(cui)
        if not name:
            return None
        concept = self._create_concept(cui, name, ConceptType.PHENOTYPE)
        concept.add_identifier(
            KnowledgeSource.UMLS, cui, name, f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}"
        )
        n_drugs = len(index["drugs_by_se"].get(cui, ()))
        fill_concept(
            concept,
            KnowledgeSource.SIDER,
            {"umls_cui": cui, "n_drugs": n_drugs, "release": "SIDER 4.1 (2015)"},
            semantic_types=["MedDRA adverse event"],
            definitions=[
                f"{name}: listed as a side effect on the labels of {n_drugs} drugs in SIDER 4.1."
            ],
        )
        return concept

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Drug -> side effects (``has_side_effect``) or side effect -> drugs (``side_effect_of``).

        Drug edges carry the label frequency when ``meddra_freq`` has one: ``frequency`` (the
        label text of the most specific high figure, e.g. "21%" or "rare"),
        ``frequency_min`` / ``frequency_max`` (that entry's bounds as fractions),
        ``frequency_all`` (every distinct figure on the labels) and
        ``placebo_frequency_max``; side effects with a known frequency come first, highest
        lower bound first. Side-effect -> drug edges are ordered by drug name.
        """
        try:
            if limit <= 0:
                return []
            index = await self._load_index()
            ref = self._resolve(concept_id, index)
            if ref is None:
                return []
            kind, key = ref
            if kind == "se":
                flats = sorted(
                    index["drugs_by_se"].get(key, ()),
                    key=lambda f: (index["names"].get(f, f).lower(), f),
                )
                return [
                    {
                        "relation_label": "side_effect_of",
                        "related_id": flat,
                        "related_name": index["names"].get(flat, flat),
                        "source": "SIDER",
                    }
                    for flat in flats[:limit]
                ]

            await self._load_freq()
            edges: list[tuple[float, str, dict[str, Any]]] = []
            for cui, term in index["se_by_drug"].get(key, {}).items():
                edge: dict[str, Any] = {
                    "relation_label": "has_side_effect",
                    "related_id": cui,
                    "related_name": term,
                    "source": "SIDER",
                }
                entries = self._freq.get((key, cui), [])
                drug_entries = [e for e in entries if not e[3]]
                placebo_entries = [e for e in entries if e[3]]
                top = -1.0
                if drug_entries:
                    # Labels often list several figures (different trials, severities) plus
                    # vague bands like "frequent" (0.01-1). Report the entry with the highest
                    # lower bound, i.e. the most specific high figure, and list the rest.
                    best = max(drug_entries, key=lambda e: (e[1] or 0.0, e[2] or 0.0, e[0]))
                    edge["frequency"] = best[0]
                    edge["frequency_min"] = best[1]
                    edge["frequency_max"] = best[2]
                    edge["frequency_all"] = sorted({e[0] for e in drug_entries})
                    top = best[1] or 0.0
                if placebo_entries:
                    highs = [e[2] for e in placebo_entries if e[2] is not None]
                    edge["placebo_frequency_max"] = max(highs) if highs else None
                edges.append((top, term.lower(), edge))
            edges.sort(key=lambda item: (-item[0], item[1]))
            return [edge for _top, _term, edge in edges[:limit]]
        except Exception as e:
            logger.warning(f"SIDER get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references: drug -> PubChem CID (+ stereo CIDs) and ATC; side effect -> UMLS / MedDRA.

        The flat STITCH id maps to PubChem exactly (CID - 100000000, verified for aspirin,
        metformin and ibuprofen); stereo ids are separate PubChem CIDs for specific
        stereoisomers and are reported with lower confidence.
        """
        try:
            index = await self._load_index()
            ref = self._resolve(concept_id, index)
            if ref is None:
                return []
            kind, key = ref
            mappings: list[dict[str, Any]] = []

            def add(to_id: str, to_source: str, mapping_type: str, confidence: float) -> None:
                mappings.append(
                    make_mapping(key, "SIDER", to_id, to_source, mapping_type, confidence)
                )

            if kind == "drug":
                cid = flat_to_pubchem_cid(key)
                if cid is not None:
                    add(str(cid), "PUBCHEM", "exact", 1.0)
                for stereo_id in index["stereo"].get(key, []):
                    stereo_cid = int(stereo_id[3:])
                    if stereo_cid != cid:
                        add(str(stereo_cid), "PUBCHEM", "stereoisomer", 0.8)
                for code in index["atc"].get(key, []):
                    add(code, "ATC", "xref", 0.9)
                return dedupe_mappings(mappings)

            add(key, "UMLS", "exact", 1.0)
            meddra = await self._load_meddra()
            for code, term_type, _name in meddra.get(key, []):
                if term_type == "PT":
                    add(code, "MEDDRA", "exact", 1.0)
            for code, term_type, _name in meddra.get(key, []):
                if term_type != "PT":
                    add(code, "MEDDRA", "synonym", 0.8)
            return dedupe_mappings(mappings)
        except Exception as e:
            logger.warning(f"SIDER get_mappings failed for '{concept_id}': {e}")
            return []
