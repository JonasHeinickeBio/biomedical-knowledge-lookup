"""
OFFSIDES Knowledge Source Adapter

OFFSIDES (Tatonetti lab, part of nSIDES) lists *off-label* drug side-effect signals mined from
the FDA Adverse Event Reporting System (FAERS): a drug-event pair is reported when it is
disproportionately frequent against propensity-score-matched control drugs and is *not* already
listed on the drug's label. Drugs are RxNorm ingredients, events are MedDRA preferred terms.

**These are statistical signals, not causal findings.** FAERS is a spontaneous-reporting system
with under-reporting, stimulated reporting, duplicate reports and above all *confounding by
indication*: a "side effect" such as fatigue is very often a symptom of the disease the drug
treats (or of a co-medication), not an effect of the drug. A PRR above 1 only says the event was
reported relatively more often with this drug than with its matched controls; the dataset also
contains many pairs with PRR <= 1. Use it to generate hypotheses, never to infer causation or
incidence. The data is also dated (the nSIDES site calls it "quite a bit out of date"; the
file was last updated 2024-03-30).

Data access: the table is only published as a file, ``OFFSIDES.csv.gz`` (68.8 MB; the row
count was not measured, extrapolating from the first 64 KiB suggests ~3 million) in the Tatonetti lab S3 bucket linked from https://nsides.io and
https://tatonettilab.org/offsides/::

    https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/OFFSIDES.csv.gz

Because of its size the adapter will **not** download it on its own: either point
``OFFSIDES_PATH`` at a local copy (``.csv`` or ``.csv.gz``), or opt in with
``OFFSIDES_DOWNLOAD=1`` (downloaded once through
:func:`knowledge_lookup.utils.dataset_cache.ensure_dataset`, kept gzipped in the dataset cache).
A copy that is already in the cache is used without any flag. Parsing is estimated at ~10-20 s and the
columnar in-memory index at roughly 150 MB (both extrapolated, not measured on the full file); both happen lazily on the first method call that
needs data, never at construction.

Columns: ``drug_rxnorm_id`` (spelled ``drug_rxnorn_id`` in the real header), ``drug_concept_name``,
``condition_meddra_id``, ``condition_concept_name``, ``A`` (reports of the drug with the event),
``B`` (drug, without), ``C`` (matched controls with), ``D`` (controls without), ``PRR =
(A/(A+B))/(C/(C+D))``, ``PRR_error`` (standard error of ln PRR, verified against the counts) and
``mean_reporting_frequency = A/(A+B)``.

Licence: the nSIDES site states none for the flat files; cite Tatonetti et al., Sci Transl Med
2012 (PMID 22422992) and check https://nsides.io before redistributing.
"""

import asyncio
import csv
import logging
import math
import os
import re
import threading
from array import array
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ..utils.dataset_cache import default_cache_dir, ensure_dataset
from ._safety_common import (
    dedupe_mappings,
    fill_concept,
    make_mapping,
    match_score,
    open_text,
)

logger = logging.getLogger(__name__)

OFFSIDES_URL = "https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/OFFSIDES.csv.gz"
OFFSIDES_FILENAME = "OFFSIDES.csv.gz"
OFFSIDES_PATH_ENV = "OFFSIDES_PATH"
OFFSIDES_DOWNLOAD_ENV = "OFFSIDES_DOWNLOAD"

CAVEAT = (
    "Statistical signal from FAERS spontaneous reports (not causal; confounded by indication)."
)
_Z95 = 1.959964  # two-sided 95 % normal quantile

_MEDDRA_RE = re.compile(r"^10\d{6}$")
_NUMERIC_RE = re.compile(r"^\d+$")

# Parsed stores are shared between adapter instances, keyed by (path, mtime).
_STORE_CACHE: dict[tuple, "_Store"] = {}
_STORE_LOCK = threading.Lock()


def _col(header: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int:
    """Index of the first header cell containing all *needles* (case-insensitive)."""
    for i, cell in enumerate(header):
        low = cell.strip().lower()
        if all(n in low for n in needles) and not any(x in low for x in exclude):
            return i
    raise ValueError(f"OFFSIDES file has no column matching {needles}; header={header}")


def _exact(header: list[str], name: str) -> int:
    for i, cell in enumerate(header):
        if cell.strip().lower() == name:
            return i
    raise ValueError(f"OFFSIDES file has no column '{name}'; header={header}")


class _Store:
    """Columnar in-memory table of OFFSIDES rows (about 36 bytes/row plus the two indexes).

    One Python tuple per row would need ~1 GB for the ~3 million rows, so numbers live in
    ``array`` columns and each drug / event keeps an ``array('I')`` of its row numbers.
    """

    def __init__(self) -> None:
        self.drug_names: dict[int, str] = {}
        self.cond_names: dict[int, str] = {}
        self.drug_col = array("I")
        self.cond_col = array("I")
        self.a = array("I")
        self.b = array("I")
        self.c = array("I")
        self.d = array("I")
        self.prr = array("f")
        self.prr_err = array("f")
        self.freq = array("f")
        self.by_drug: dict[int, array] = defaultdict(lambda: array("I"))
        self.by_cond: dict[int, array] = defaultdict(lambda: array("I"))

    def __len__(self) -> int:
        return len(self.a)

    @classmethod
    def from_file(cls, path: Path) -> "_Store":
        store = cls()
        with open_text(path) as handle:
            reader = csv.reader(handle)
            header = next(reader)
            i_did = _col(header, "drug", "rxnor")
            i_dname = _col(header, "drug", "name")
            i_cid = _col(header, "condition", "meddra")
            i_cname = _col(header, "condition", "name")
            i_a, i_b, i_c, i_d = (_exact(header, n) for n in ("a", "b", "c", "d"))
            i_prr = _exact(header, "prr")
            i_err = _exact(header, "prr_error")
            i_freq = _col(header, "reporting_frequency")
            need = max(i_did, i_dname, i_cid, i_cname, i_a, i_b, i_c, i_d, i_prr, i_err, i_freq)
            for row in reader:
                if len(row) <= need:
                    continue
                try:
                    drug = int(row[i_did])
                    cond = int(row[i_cid])
                    counts = (int(row[i_a]), int(row[i_b]), int(row[i_c]), int(row[i_d]))
                    stats = (float(row[i_prr]), float(row[i_err]), float(row[i_freq]))
                except ValueError:
                    continue
                n = len(store.a)
                store.drug_names.setdefault(drug, row[i_dname])
                store.cond_names.setdefault(cond, row[i_cname])
                store.drug_col.append(drug)
                store.cond_col.append(cond)
                store.a.append(counts[0])
                store.b.append(counts[1])
                store.c.append(counts[2])
                store.d.append(counts[3])
                store.prr.append(stats[0])
                store.prr_err.append(stats[1])
                store.freq.append(stats[2])
                store.by_drug[drug].append(n)
                store.by_cond[cond].append(n)
        return store

    def signal(self, row: int) -> dict[str, Any]:
        """Statistics of one row as a plain dict (floats rounded to the file's precision)."""
        prr = float(f"{self.prr[row]:.6g}")
        err = float(f"{self.prr_err[row]:.6g}")
        out: dict[str, Any] = {
            "prr": prr,
            "prr_error": err,
            "reporting_frequency": float(f"{self.freq[row]:.6g}"),
            "a": self.a[row],
            "b": self.b[row],
            "c": self.c[row],
            "d": self.d[row],
        }
        if prr > 0 and err >= 0:
            out["prr_ci95_low"] = round(prr * math.exp(-_Z95 * err), 4)
            out["prr_ci95_high"] = round(prr * math.exp(_Z95 * err), 4)
        return out


def _ci_low(store: _Store, row: int) -> float:
    prr, err = store.prr[row], store.prr_err[row]
    return prr * math.exp(-_Z95 * err) if prr > 0 else 0.0


class OFFSIDESAdapter(KnowledgeSourceAdapter):
    """Adapter for OFFSIDES off-label side-effect signals (statistical, not causal).

    Concept ids: ``RXNORM:<id>`` for drugs and ``MEDDRA:<code>`` for adverse events (bare
    numbers also work: an 8-digit ``10xxxxxx`` is read as MedDRA, anything else as RxNorm).
    """

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.data_path = os.getenv(OFFSIDES_PATH_ENV) or None
        self._store: _Store | None = None
        self._lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OFFSIDES

    def _cached_file(self) -> Path | None:
        candidate = default_cache_dir() / OFFSIDES_FILENAME
        return candidate if candidate.exists() else None

    @staticmethod
    def _download_allowed() -> bool:
        return os.getenv(OFFSIDES_DOWNLOAD_ENV, "").strip().lower() in {"1", "true", "yes", "on"}

    def is_available(self) -> bool:
        """True when a local file is configured/cached or the 69 MB download is opted into."""
        if self.data_path:
            return Path(self.data_path).exists()
        return self._cached_file() is not None or self._download_allowed()

    async def _dataset(self) -> Path:
        if self.data_path:
            path = Path(self.data_path)
            if not path.exists():
                raise FileNotFoundError(f"{OFFSIDES_PATH_ENV}={self.data_path} does not exist")
            return path
        cached = self._cached_file()
        if cached is not None:
            return cached
        if not self._download_allowed():
            raise RuntimeError(
                f"OFFSIDES is a 69 MB download: set {OFFSIDES_PATH_ENV} to a local "
                f"OFFSIDES.csv(.gz) or {OFFSIDES_DOWNLOAD_ENV}=1 to fetch {OFFSIDES_URL}"
            )
        # Keep it gzipped (decompress=False): ~69 MB on disk instead of several hundred.
        return await ensure_dataset(
            OFFSIDES_URL, filename=OFFSIDES_FILENAME, decompress=False, max_age_days=None
        )

    async def _load_store(self) -> _Store:
        if self._store is not None:
            return self._store
        async with self._lock:
            if self._store is None:
                path = await self._dataset()
                self._store = await asyncio.to_thread(self._cached_store, path)
        return self._store

    @staticmethod
    def _cached_store(path: Path) -> _Store:
        key = (str(path), path.stat().st_mtime_ns)
        with _STORE_LOCK:
            if key not in _STORE_CACHE:
                _STORE_CACHE.clear()  # one dataset at a time keeps memory bounded
                _STORE_CACHE[key] = _Store.from_file(path)
            return _STORE_CACHE[key]

    # ------------------------------------------------------------------
    # Ids
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve(concept_id: str, store: _Store) -> tuple[str, int] | None:
        """``("drug", rxnorm)`` / ``("event", meddra)`` for a known id, else ``None``."""
        value = (concept_id or "").strip()
        if value.upper().startswith("OFFSIDES:"):
            value = value[9:]
        upper = value.upper()
        kind = None
        if upper.startswith(("RXNORM:", "RXCUI:")):
            kind, upper = "drug", upper.split(":", 1)[1]
        elif upper.startswith("MEDDRA:"):
            kind, upper = "event", upper.split(":", 1)[1]
        upper = upper.strip()
        if not _NUMERIC_RE.match(upper):
            return None
        number = int(upper)
        if kind is None:
            kind = "event" if _MEDDRA_RE.match(upper) else "drug"
        known = store.by_drug if kind == "drug" else store.by_cond
        return (kind, number) if number in known else None

    @staticmethod
    def _id(kind: str, number: int) -> str:
        return f"RXNORM:{number}" if kind == "drug" else f"MEDDRA:{number}"

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search drugs (RxNorm ingredient names) and adverse events (MedDRA PTs) by substring.

        Ranking: exact > prefix > whole word > substring; drugs before events on ties.
        """
        try:
            needle = (query or "").strip().lower()
            if not needle or limit <= 0:
                return []
            store = await self._load_store()

            direct = self._resolve(query, store)
            if direct:
                concept = self._build_concept(direct, store)
                return [concept] if concept else []

            scored: list[tuple[float, int, str, tuple[str, int]]] = []
            for number, name in store.drug_names.items():
                score = match_score(needle, name.lower())
                if score is not None:
                    scored.append((score, 0, name.lower(), ("drug", number)))
            for number, name in store.cond_names.items():
                score = match_score(needle, name.lower())
                if score is not None:
                    scored.append((score, 1, name.lower(), ("event", number)))
            scored.sort(key=lambda item: (-item[0], item[1], item[2]))

            concepts: list[UnifiedConcept] = []
            for score, _kind, _name, ref in scored[:limit]:
                concept = self._build_concept(ref, store)
                if concept:
                    concept.confidence_score = score
                    concepts.append(concept)
            logger.info(f"OFFSIDES search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"OFFSIDES search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Drug (RxNorm) or adverse-event (MedDRA PT) concept with signal counts."""
        try:
            store = await self._load_store()
            ref = self._resolve(concept_id, store)
            if ref is None:
                return None
            concept = self._build_concept(ref, store)
            if concept is not None:
                concept.confidence_score = 1.0
            return concept
        except Exception as e:
            logger.error(f"OFFSIDES get_concept_details failed for '{concept_id}': {e}")
            return None

    def _build_concept(self, ref: tuple[str, int], store: _Store) -> UnifiedConcept | None:
        kind, number = ref
        if kind == "drug":
            name = store.drug_names.get(number)
            rows = store.by_drug.get(number)
            ctype = ConceptType.DRUG
            data = {"rxnorm_id": number}
            semantic = "drug (RxNorm ingredient)"
        else:
            name = store.cond_names.get(number)
            rows = store.by_cond.get(number)
            ctype = ConceptType.PHENOTYPE
            data = {"meddra_code": number}
            semantic = "MedDRA adverse event"
        if not name or rows is None:
            return None
        n_pairs = len(rows)
        n_signals = sum(1 for r in rows if _ci_low(store, r) > 1.0)
        data.update({"n_pairs": n_pairs, "n_prr_signals_ci95_above_1": n_signals})
        concept = self._create_concept(self._id(kind, number), name, ctype)
        fill_concept(
            concept,
            KnowledgeSource.OFFSIDES,
            data,
            semantic_types=[semantic],
            definitions=[
                f"{name}: {n_pairs} drug-event pairs in OFFSIDES, {n_signals} with a PRR whose "
                f"95% CI lies above 1. {CAVEAT}"
            ],
        )
        return concept

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Drug -> adverse events (``has_adverse_event_signal``) and the reverse
        (``adverse_event_signal_of``).

        Each edge carries ``prr``, ``prr_error`` (SE of ln PRR), ``prr_ci95_low`` /
        ``prr_ci95_high``, ``reporting_frequency`` (A/(A+B)), the 2x2 counts ``a`` .. ``d`` and a
        ``caveat``. Edges are ordered by the lower 95 % bound of the PRR, so signals that
        survive their own uncertainty come first and one-report pairs with a huge PRR do not
        dominate. Edges with ``prr_ci95_low`` <= 1 are not signals; they are included because
        the table lists them and callers may want the full picture.
        """
        try:
            if limit <= 0:
                return []
            store = await self._load_store()
            ref = self._resolve(concept_id, store)
            if ref is None:
                return []
            kind, number = ref
            if kind == "drug":
                rows, names, col, label = (
                    store.by_drug[number],
                    store.cond_names,
                    store.cond_col,
                    "has_adverse_event_signal",
                )
                other = "event"
            else:
                rows, names, col, label = (
                    store.by_cond[number],
                    store.drug_names,
                    store.drug_col,
                    "adverse_event_signal_of",
                )
                other = "drug"
            ordered = sorted(rows, key=lambda r: (-_ci_low(store, r), -store.prr[r], r))
            edges: list[dict[str, Any]] = []
            for row in ordered[:limit]:
                related = col[row]
                edge: dict[str, Any] = {
                    "relation_label": label,
                    "related_id": self._id(other, related),
                    "related_name": names.get(related, str(related)),
                    "source": "OFFSIDES",
                    "evidence": "FAERS disproportionality (propensity-score-matched PRR)",
                    "caveat": CAVEAT,
                }
                edge.update(store.signal(row))
                edges.append(edge)
            return edges
        except Exception as e:
            logger.warning(f"OFFSIDES get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """The vocabulary identifier behind the concept: RxNorm (drugs) or MedDRA (events)."""
        try:
            store = await self._load_store()
            ref = self._resolve(concept_id, store)
            if ref is None:
                return []
            kind, number = ref
            to_source = "RXNORM" if kind == "drug" else "MEDDRA"
            mapping = make_mapping(
                self._id(kind, number), "OFFSIDES", str(number), to_source, "exact", 1.0
            )
            return dedupe_mappings([mapping])
        except Exception as e:
            logger.warning(f"OFFSIDES get_mappings failed for '{concept_id}': {e}")
            return []
