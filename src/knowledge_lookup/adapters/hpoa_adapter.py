"""
HPO annotations (phenotype.hpoa) Knowledge Source Adapter

Adapter for the Human Phenotype Ontology annotation file ``phenotype.hpoa``: rare-disease
(OMIM, Orphanet, DECIPHER) -> HPO phenotype annotations with frequency, onset, sex,
modifier and evidence. There is no query API for it, so the file (about 36 MB, regenerated
roughly monthly) is downloaded once on first use via
:func:`knowledge_lookup.utils.dataset_cache.ensure_dataset`, parsed into in-memory indexes
and served from there. Nothing is downloaded at import or construction time.

Set ``HPOA_PATH`` to a local copy of the file (plain or ``.gz``) to skip the download.
Download URL: https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa

File format (tab separated, ``#`` header lines first, then one column-header row)::

    database_id  disease_name  qualifier  hpo_id  reference  evidence  onset  frequency
    sex  modifier  aspect  biocuration

``qualifier`` is empty or ``NOT``; ``frequency`` is an HP frequency term
(``HP:0040280``..``HP:0040285``), ``n/m`` or ``x%``; ``aspect`` is ``P`` (phenotypic
abnormality), ``I`` (inheritance), ``C`` (clinical course) or ``M`` (modifier).

Licence: HPO annotations are free for research, see https://hpo.jax.org/license; OMIM-derived
rows carry OMIM's terms. The file contains HPO ids only, no HPO term labels; pair this adapter
with the HPO/Monarch adapters to label phenotypes.
"""

import asyncio
import gzip
import logging
import os
from pathlib import Path
from typing import Any, NamedTuple

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._pheno_common import add_known_identifier, frequency_extras, parse_frequency

logger = logging.getLogger(__name__)

HPOA_URL = "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa"
HPOA_PATH_ENV = "HPOA_PATH"
HPOA_DOWNLOAD_ENV = "HPOA_DOWNLOAD"
HPOA_FILENAME = "phenotype.hpoa"

# aspect letter -> relation label (a NOT qualifier prefixes "not_")
_ASPECT_RELATIONS = {
    "P": "has_phenotype",
    "I": "has_inheritance",
    "C": "has_clinical_course",
    "M": "has_clinical_modifier",
}

_EVIDENCE_LABELS = {
    "IEA": "inferred from electronic annotation",
    "PCS": "published clinical study",
    "TAS": "traceable author statement",
}

# HPO "Onset" branch terms that occur in the file.
_ONSET_LABELS = {
    "HP:0030674": "Antenatal onset",
    "HP:0003577": "Congenital onset",
    "HP:0003623": "Neonatal onset",
    "HP:0003593": "Infantile onset",
    "HP:0011463": "Childhood onset",
    "HP:0003621": "Juvenile onset",
    "HP:0011462": "Young adult onset",
    "HP:0003581": "Adult onset",
    "HP:0003596": "Middle age onset",
    "HP:0003584": "Late onset",
}

# Disease id prefixes as written in the file; aliases users type map onto them.
_PREFIX_ALIASES = {"ORPHANET": "ORPHA", "ORPHA": "ORPHA", "OMIM": "OMIM", "DECIPHER": "DECIPHER"}


class _Annotation(NamedTuple):
    """One data row of phenotype.hpoa."""

    disease_id: str
    disease_name: str
    negated: bool
    hpo_id: str
    reference: str
    evidence: str
    onset: str
    frequency: str
    sex: str
    modifier: str
    aspect: str
    biocuration: str


class HpoaIndex:
    """In-memory indexes over a parsed phenotype.hpoa."""

    def __init__(self) -> None:
        self.metadata: dict[str, str] = {}
        self.names: dict[str, str] = {}  # disease id -> name
        self.by_disease: dict[str, list[_Annotation]] = {}
        self.by_hpo: dict[str, list[_Annotation]] = {}
        self._lowered: list[tuple[str, str]] | None = None  # (lower-cased name, disease id)

    def add(self, row: _Annotation) -> None:
        self.names.setdefault(row.disease_id, row.disease_name)
        self.by_disease.setdefault(row.disease_id, []).append(row)
        self.by_hpo.setdefault(row.hpo_id, []).append(row)
        self._lowered = None

    @property
    def lowered_names(self) -> list[tuple[str, str]]:
        if self._lowered is None:
            self._lowered = [(name.lower(), did) for did, name in self.names.items()]
        return self._lowered


def parse_hpoa(path: str | Path) -> HpoaIndex:
    """Parse a ``phenotype.hpoa`` file (plain or gzip) into an :class:`HpoaIndex`.

    ``#key: value`` header lines are kept in ``metadata`` (``version``, ``hpo-version``).
    Rows with fewer than 4 columns (e.g. a truncated last line) are skipped; short rows are
    padded so older files without the trailing columns still load. Plain ``str.split("\\t")``
    is used rather than :mod:`csv` because disease names may contain quote characters.
    """
    index = HpoaIndex()
    target = Path(path)
    opener = gzip.open if target.suffix == ".gz" else open
    with opener(target, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("#"):
                key, sep, value = line.lstrip("#").partition(":")
                if sep:
                    index.metadata[key.strip()] = value.strip().strip('"')
                continue
            cols = line.split("\t")
            if cols[0] == "database_id" or len(cols) < 4 or not cols[3].startswith("HP:"):
                continue
            cols += [""] * (12 - len(cols))
            index.add(
                _Annotation(
                    disease_id=cols[0].strip(),
                    disease_name=cols[1].strip(),
                    negated=cols[2].strip().upper() == "NOT",
                    hpo_id=cols[3].strip(),
                    reference=cols[4].strip(),
                    evidence=cols[5].strip(),
                    onset=cols[6].strip(),
                    frequency=cols[7].strip(),
                    sex=cols[8].strip(),
                    modifier=cols[9].strip(),
                    aspect=cols[10].strip().upper(),
                    biocuration=cols[11].strip(),
                )
            )
    return index


class HPOAAdapter(KnowledgeSourceAdapter):
    """Adapter for the HPO disease-phenotype annotation file (``phenotype.hpoa``)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self._index: HpoaIndex | None = None
        self._load_lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.HPOA

    def is_available(self) -> bool:
        """True when ``HPOA_PATH`` names an existing file, the file is already cached, or the
        ~36 MB download is allowed (``HPOA_DOWNLOAD=1`` or ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``).

        Opt-in, so a default multi-source lookup never starts the download on its own."""
        from ..utils.dataset_cache import default_cache_dir, downloads_allowed

        configured = os.environ.get(HPOA_PATH_ENV)
        if configured:
            return Path(configured).is_file()
        return (default_cache_dir() / HPOA_FILENAME).is_file() or downloads_allowed(
            HPOA_DOWNLOAD_ENV
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _ensure_index(self) -> HpoaIndex:
        """Load (once) and return the index; downloads the file on first use if needed."""
        if self._index is not None:
            return self._index
        async with self._load_lock:
            if self._index is None:
                configured = os.environ.get(HPOA_PATH_ENV)
                if configured:
                    path = Path(configured)
                else:
                    from ..utils.dataset_cache import ensure_dataset  # lazy: only on first use

                    path = await ensure_dataset(HPOA_URL, filename=HPOA_FILENAME)
                self._index = await asyncio.to_thread(parse_hpoa, path)
                logger.info(
                    f"HPOA loaded: {len(self._index.names)} diseases, "
                    f"{len(self._index.by_hpo)} phenotypes "
                    f"(version {self._index.metadata.get('version', '?')})"
                )
        return self._index

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_id(concept_id: str) -> str | None:
        """Normalise ``omim:154700`` / ``Orphanet:558`` / ``154700`` to the file's spelling
        (``OMIM:154700``, ``ORPHA:558``). A bare number is assumed to be an OMIM id."""
        text = (concept_id or "").strip()
        if not text:
            return None
        if ":" not in text:
            return f"OMIM:{text}" if text.isdigit() else None
        prefix, _, local = text.partition(":")
        key = prefix.strip().upper()
        if key == "HP":
            return f"HP:{local.strip()}"
        canonical = _PREFIX_ALIASES.get(key)
        return f"{canonical}:{local.strip()}" if canonical and local.strip() else None

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Find diseases by name substring (case-insensitive), disease id or HP id.

        Ranking: exact name 1.0, name prefix 0.9, word-start match 0.8, other substring 0.7;
        ties broken by number of annotations. An ``HP:`` query returns the diseases annotated
        with that phenotype. A disease id returns that disease.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            index = await self._ensure_index()
            normalized = self._normalize_id(text)

            if normalized and normalized.startswith("HP:"):
                rows = [r for r in index.by_hpo.get(normalized, []) if not r.negated]
                disease_ids = list(dict.fromkeys(r.disease_id for r in rows))
                scored = [(1.0, did) for did in disease_ids]
            elif normalized and normalized in index.names:
                scored = [(1.0, normalized)]
            else:
                needle = text.lower()
                scored = []
                for lowered, disease_id in index.lowered_names:
                    pos = lowered.find(needle)
                    if pos < 0:
                        continue
                    if lowered == needle:
                        score = 1.0
                    elif pos == 0:
                        score = 0.9
                    elif _is_word_match(lowered, needle, pos):
                        score = 0.8
                    else:
                        score = 0.7
                    scored.append((score, disease_id))

            scored.sort(key=lambda s: (-s[0], -len(index.by_disease.get(s[1], [])), s[1]))
            concepts = [
                self._convert_disease(index, disease_id, score)
                for score, disease_id in scored[:limit]
            ]
            logger.info(f"HPOA search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"HPOA search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Return the disease record (``OMIM:``/``ORPHA:``/``DECIPHER:``) with an annotation
        summary in ``source_data``. HP ids return ``None`` (the file has no HPO term labels)."""
        try:
            disease_id = self._normalize_id(concept_id)
            if disease_id is None:
                return None
            index = await self._ensure_index()
            if disease_id not in index.names:
                return None
            return self._convert_disease(index, disease_id, 1.0, detailed=True)
        except Exception as e:
            logger.error(f"HPOA get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = 50, aspect: str | None = "P"
    ) -> list[dict[str, Any]]:
        """Return a disease's annotations, or the diseases annotated with an HP term.

        - disease id: ``has_phenotype`` / ``not_has_phenotype`` edges to HP ids, most frequent
          first, with ``frequency`` (numeric fraction), ``frequency_label``/``frequency_raw``,
          ``onset``, ``evidence``, ``references``, ``sex`` and ``modifier`` when present.
        - HP id: ``phenotype_of`` / ``not_phenotype_of`` edges to the diseases.

        ``aspect`` keeps one kind of annotation (``"P"`` phenotypic abnormality by default,
        ``"I"`` inheritance, ``"C"`` clinical course, ``"M"`` modifier); ``None`` returns all.
        Repeated annotations of the same term from several references are merged.
        """
        if limit <= 0:
            return []
        try:
            normalized = self._normalize_id(concept_id)
            if normalized is None:
                return []
            index = await self._ensure_index()
            wanted = aspect.upper() if aspect else None

            if normalized.startswith("HP:"):
                rows = index.by_hpo.get(normalized, [])
                edges = self._merge_rows(rows, wanted, key=lambda r: r.disease_id, outgoing=False)
            else:
                rows = index.by_disease.get(normalized, [])
                edges = self._merge_rows(rows, wanted, key=lambda r: r.hpo_id, outgoing=True)
            # most frequent first; unknown frequency last; stable otherwise
            edges.sort(key=lambda e: -e["frequency"] if "frequency" in e else 2.0)
            return edges[:limit]
        except Exception as e:
            logger.warning(f"HPOA get_relationships failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _merge_rows(self, rows, wanted_aspect, key, outgoing: bool) -> list[dict[str, Any]]:
        merged: dict[tuple[str, bool, str], dict[str, Any]] = {}
        for row in rows:
            if wanted_aspect and row.aspect != wanted_aspect:
                continue
            slot = (key(row), row.negated, row.aspect)
            if slot in merged:
                edge = merged[slot]
                if row.reference and row.reference not in edge["references"]:
                    edge["references"].append(row.reference)
                continue
            merged[slot] = self._edge(row, outgoing)
        return list(merged.values())

    def _edge(self, row: _Annotation, outgoing: bool) -> dict[str, Any]:
        base = _ASPECT_RELATIONS.get(row.aspect, "has_phenotype")
        if outgoing:
            label = base
            related_id, related_name = row.hpo_id, row.hpo_id  # file carries no HPO labels
        else:
            label = (
                "phenotype_of" if row.aspect in ("P", "") else f"{base.removeprefix('has_')}_of"
            )
            related_id, related_name = row.disease_id, row.disease_name
        if row.negated:
            label = f"not_{label}"
        edge: dict[str, Any] = {
            "relation_label": label,
            "related_id": related_id,
            "related_name": related_name,
            "source": "HPOA",
            "aspect": row.aspect,
            "direction": "outgoing" if outgoing else "incoming",
            "references": [row.reference] if row.reference else [],
        }
        if row.evidence:
            edge["evidence"] = row.evidence
            if row.evidence in _EVIDENCE_LABELS:
                edge["evidence_label"] = _EVIDENCE_LABELS[row.evidence]
        if row.onset:
            edge["onset"] = row.onset
            if row.onset in _ONSET_LABELS:
                edge["onset_label"] = _ONSET_LABELS[row.onset]
        if row.sex:
            edge["sex"] = row.sex
        if row.modifier:
            edge["modifier"] = row.modifier
        edge.update(frequency_extras(parse_frequency(row.frequency)))
        return edge

    def _convert_disease(
        self, index: HpoaIndex, disease_id: str, score: float, detailed: bool = False
    ) -> UnifiedConcept:
        name = index.names.get(disease_id, disease_id)
        concept = self._create_concept(disease_id, name, ConceptType.DISEASE)
        concept.confidence_score = score
        add_known_identifier(concept, disease_id, name)
        if concept.categories is not None:
            concept.categories.append(f"hpoa:{disease_id.split(':', 1)[0]}")

        rows = index.by_disease.get(disease_id, [])
        positive = {r.hpo_id for r in rows if r.aspect == "P" and not r.negated}
        summary: dict[str, Any] = {
            "annotations": len(rows),
            "phenotypes": len(positive),
            "excluded_phenotypes": len({r.hpo_id for r in rows if r.aspect == "P" and r.negated}),
        }
        if detailed:
            summary["inheritance"] = sorted({r.hpo_id for r in rows if r.aspect == "I"})
            summary["clinical_course"] = sorted({r.hpo_id for r in rows if r.aspect == "C"})
            summary["references"] = sorted({r.reference for r in rows if r.reference})[:50]
            summary["hpoa_version"] = index.metadata.get("version")
            summary["hpo_version"] = index.metadata.get("hpo-version")
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.HPOA] = summary
        return concept


def _is_word_match(text: str, needle: str, pos: int) -> bool:
    """True when ``needle`` found at ``pos`` in ``text`` starts at a word boundary."""
    return pos == 0 or not text[pos - 1].isalnum()
