"""
ICD-10-GM Knowledge Source Adapter

German Modification of ICD-10, published yearly by the BfArM (Bundesinstitut fuer
Arzneimittel und Medizinprodukte) and used for German diagnosis coding; for example
ME/CFS is coded ``G93.3`` and Post-COVID ``U09.9``. Labels are German.

There is no query API: BfArM publishes the "Systematik" as a ClaML/XML download
(``icd10gm<year>syst-claml.zip``, about 17 MB for 2026) from
https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html. That download sits
behind a consent page ("Zustimmung zum Download", usage contract with the BfArM: the
Systematik is an official work under s. 5(2) UrhG, so it may be used with attribution and
without modification), and no stable direct file URL is exposed. The adapter therefore
does **not** download by itself from BfArM; the user fetches the file once and points the
adapter at it:

- ``ICD10GM_CLAML_PATH`` (or ``config.get_api_key("icd10gm")``): path to the ClaML ``.xml``
  or to the BfArM ``.zip`` (the XML member is picked automatically).
- ``ICD10GM_URL`` (optional, ``{year}`` is replaced with ``ICD10GM_YEAR``): a URL the user
  controls, e.g. an internal mirror. It is fetched lazily on first use through
  :func:`knowledge_lookup.utils.dataset_cache.ensure_dataset` (never at construction);
  ``ICD10GM_MEMBER`` names the XML member when the URL is a multi-file zip.

The file is parsed with ``xml.etree.ElementTree.iterparse`` in a worker thread on first
use and kept in memory (a few MB for ~17k classes); parsed indexes are shared between
adapter instances for the same file.

Not live-verified against the full official file (consent-gated, 17 MB); the parser is
tested on a small synthetic ClaML sample that mirrors the documented structure.
"""

import asyncio
import json
import logging
import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any
from xml.etree import ElementTree as ET

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Rubric kinds worth keeping; everything else (e.g. text, coding-hint) is ignored.
_PREFERRED_KINDS = ("preferred", "preferredLong")
_CODE_LIKE_RE = re.compile(r"^[A-Z]\d{1,2}(?:\.?\d{0,2})$")
_REF_CODE_RE = re.compile(r"^[A-Z]\d{2}(?:\.\d{1,2})?(?:-[A-Z]\d{2}(?:\.\d{1,2})?)?$")
_CURIE_RE = re.compile(r"^ICD-?10-?GM\s*:\s*", re.IGNORECASE)
_CODE_MARKS = "†*!+"  # dagger, aster, exclamation mark, plus
_KIND_RANK = {"category": 0, "block": 1, "chapter": 2}
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

# Parsed indexes are shared by adapter instances: (path, mtime_ns) -> index.
_INDEX_CACHE: dict[tuple[str, int], "ClaMLIndex"] = {}


def _local(tag: str) -> str:
    """Element name without an XML namespace, so namespaced exports parse too."""
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def fold_accents(text: str) -> str:
    """Lower-case and strip diacritics: ``Ermüdung`` -> ``ermudung``."""
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("ß", "ss"))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def fold_translit(text: str) -> str:
    """Lower-case with German transliteration: ``Ermüdung`` -> ``ermuedung``."""
    return fold_accents(text.lower().translate(_UMLAUTS)) if text else ""


@dataclass(slots=True)
class ClaMLClass:
    """One ClaML ``Class`` (chapter, block or category)."""

    code: str
    kind: str
    label: str = ""
    long_label: str = ""
    usage: str = ""
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    # (text, referenced codes) per rubric
    inclusions: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    exclusions: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # search keys, filled by ClaMLIndex
    key_accent: str = ""
    key_translit: str = ""
    incl_accent: str = ""
    incl_translit: str = ""


class ClaMLIndex:
    """In-memory index over the classes of one ClaML file."""

    def __init__(self, classes: list[ClaMLClass], version: str = ""):
        self.classes = classes
        self.version = version
        self.by_code: dict[str, ClaMLClass] = {c.code.upper(): c for c in classes}
        for cls in classes:
            cls.key_accent = fold_accents(cls.label)
            cls.key_translit = fold_translit(cls.label)
            inclusion_text = " | ".join(text for text, _ in cls.inclusions)
            cls.incl_accent = fold_accents(inclusion_text)
            cls.incl_translit = fold_translit(inclusion_text)

    def get(self, code: str) -> ClaMLClass | None:
        return self.by_code.get(code.upper())

    def path(self, code: str) -> list[ClaMLClass]:
        """Root-to-node chain following the first superclass at each step."""
        chain: list[ClaMLClass] = []
        seen: set[str] = set()
        node = self.get(code)
        while node is not None and node.code not in seen:
            seen.add(node.code)
            chain.append(node)
            node = self.get(node.parents[0]) if node.parents else None
        chain.reverse()
        return chain

    def search_code(self, code: str, limit: int) -> list[tuple[float, ClaMLClass]]:
        """Exact code first, then codes that start with it (in code order)."""
        hits: list[tuple[float, ClaMLClass]] = []
        exact = self.get(code)
        if exact is not None:
            hits.append((1.0, exact))
        prefix = code.upper()
        if len(hits) < limit:
            for cls in self.classes:
                if cls is exact or cls.kind == "chapter":
                    continue
                if cls.code.upper().startswith(prefix):
                    hits.append((0.9, cls))
                    if len(hits) >= limit:
                        break
        return hits

    def search_text(self, query: str, limit: int) -> list[tuple[float, ClaMLClass]]:
        """Case- and umlaut-insensitive title (and inclusion term) search."""
        q_accent, q_translit = fold_accents(query).strip(), fold_translit(query).strip()
        if not q_accent:
            return []
        tokens_a, tokens_t = q_accent.split(), q_translit.split()
        scored: list[tuple[float, int, int, str, ClaMLClass]] = []
        for cls in self.classes:
            score = self._score(cls, q_accent, q_translit, tokens_a, tokens_t)
            if score:
                rank = _KIND_RANK.get(cls.kind, 3)
                scored.append((-score, rank, len(cls.label), cls.code, cls))
        scored.sort(key=lambda item: item[:4])
        return [(-s, cls) for s, _, _, _, cls in scored[:limit]]

    @staticmethod
    def _score(
        cls: ClaMLClass, q_a: str, q_t: str, tokens_a: list[str], tokens_t: list[str]
    ) -> float:
        for q, key in ((q_a, cls.key_accent), (q_t, cls.key_translit)):
            if key == q:
                return 1.0
        for q, key in ((q_a, cls.key_accent), (q_t, cls.key_translit)):
            if key.startswith(q):
                return 0.9
        for q, key in ((q_a, cls.key_accent), (q_t, cls.key_translit)):
            if q in key:
                return 0.8
        for tokens, key in ((tokens_a, cls.key_accent), (tokens_t, cls.key_translit)):
            if len(tokens) > 1 and all(t in key for t in tokens):
                return 0.7
        for q, key in ((q_a, cls.incl_accent), (q_t, cls.incl_translit)):
            if q in key:
                return 0.6
        return 0.0


def _references(label: ET.Element) -> tuple[str, ...]:
    """Class codes referenced inside a rubric label (exclusion/inclusion targets)."""
    codes: list[str] = []
    for ref in label.iter():
        if _local(ref.tag) != "Reference":
            continue
        candidate = (ref.get("code") or _text(ref)).strip().upper().rstrip(_CODE_MARKS)
        if _REF_CODE_RE.match(candidate) and candidate not in codes:
            codes.append(candidate)
    return tuple(codes)


def _parse_class(elem: ET.Element) -> ClaMLClass | None:
    code = (elem.get("code") or "").strip()
    if not code:
        return None
    cls = ClaMLClass(code=code, kind=elem.get("kind") or "category", usage=elem.get("usage") or "")
    for child in elem:
        name = _local(child.tag)
        if name == "SuperClass":
            parent = (child.get("code") or "").strip()
            if parent and parent not in cls.parents:
                cls.parents.append(parent)
        elif name == "SubClass":
            sub = (child.get("code") or "").strip()
            if sub and sub not in cls.children:
                cls.children.append(sub)
        elif name == "Rubric":
            kind = child.get("kind") or ""
            label = next((c for c in child if _local(c.tag) == "Label"), None)
            if label is None:
                continue
            text = _text(label)
            if not text:
                continue
            if kind == "preferred":
                cls.label = cls.label or text
            elif kind == "preferredLong":
                cls.long_label = cls.long_label or text
            elif kind == "inclusion":
                cls.inclusions.append((text, _references(label)))
            elif kind == "exclusion":
                cls.exclusions.append((text, _references(label)))
            elif kind == "note":
                cls.notes.append(text)
    if not cls.label:
        cls.label = cls.long_label
    return cls


def parse_claml(stream: IO[bytes]) -> ClaMLIndex:
    """Stream-parse a ClaML document; memory stays flat because classes are cleared."""
    classes: list[ClaMLClass] = []
    version = ""
    root: ET.Element | None = None
    for event, elem in ET.iterparse(stream, events=("start", "end")):
        if event == "start":
            if root is None:
                root = elem
            continue
        name = _local(elem.tag)
        if name == "Title":
            version = elem.get("version") or version
        elif name == "Class":
            cls = _parse_class(elem)
            if cls is not None:
                classes.append(cls)
            elem.clear()
            if root is not None and len(root) > 512:
                root.clear()
    return ClaMLIndex(classes, version)


def load_claml(path: Path) -> ClaMLIndex:
    """Parse ``path`` (ClaML ``.xml`` or a ``.zip`` containing one) into an index."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [
                n
                for n in archive.namelist()
                if n.lower().endswith(".xml") and "__macosx" not in n.lower()
            ]
            if not members:
                raise ValueError(f"no XML member in {path.name}")
            chosen = next((n for n in members if "claml" in n.lower()), members[0])
            with archive.open(chosen) as stream:
                return parse_claml(stream)
    with path.open("rb") as stream:
        return parse_claml(stream)


def normalise_code(raw: str) -> str:
    """``"icd10gm:g933"`` / ``"G93.3†"`` -> ``"G93.3"``; block codes pass through."""
    code = _CURIE_RE.sub("", (raw or "").strip()).upper().rstrip(_CODE_MARKS).strip()
    match = re.fullmatch(r"([A-Z]\d{2})(\d{1,2})", code)
    if match:
        code = f"{match.group(1)}.{match.group(2)}"
    return code


class ICD10GMAdapter(KnowledgeSourceAdapter):
    """Adapter for the German ICD-10-GM, read from a local BfArM ClaML file."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self._index: ClaMLIndex | None = None
        self._load_lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ICD10GM

    # ------------------------------------------------------------------
    # Configuration / loading
    # ------------------------------------------------------------------

    def _configured_path(self) -> str | None:
        path = os.getenv("ICD10GM_CLAML_PATH") or self.config.get_api_key("icd10gm")
        return path.strip() if path and path.strip() else None

    @staticmethod
    def _configured_url() -> str | None:
        url = (os.getenv("ICD10GM_URL") or "").strip()
        if not url:
            return None
        return url.replace("{year}", (os.getenv("ICD10GM_YEAR") or "").strip())

    def is_available(self) -> bool:
        """True when a ClaML file path or download URL is configured (not checked yet)."""
        return bool(self._configured_path() or self._configured_url())

    async def _resolve_file(self) -> Path:
        path = self._configured_path()
        if path:
            resolved = Path(path).expanduser()
            if not resolved.is_file():
                raise FileNotFoundError(f"ICD10GM_CLAML_PATH does not exist: {resolved}")
            return resolved
        url = self._configured_url()
        if not url:
            raise RuntimeError("ICD-10-GM is not configured (ICD10GM_CLAML_PATH or ICD10GM_URL)")
        from ..utils.dataset_cache import ensure_dataset  # lazy: only when a download is due

        year = (os.getenv("ICD10GM_YEAR") or "").strip()
        return await ensure_dataset(
            url,
            filename=f"icd10gm{year}_claml.xml",
            member=(os.getenv("ICD10GM_MEMBER") or "").strip() or None,
            max_age_days=None,  # the year is pinned by the URL; never silently refresh
        )

    async def _ensure_index(self) -> ClaMLIndex:
        """Return the (lazily built) index; parsing runs in a worker thread."""
        if self._index is not None:
            return self._index
        async with self._load_lock:
            if self._index is not None:
                return self._index
            file = await self._resolve_file()
            key = (str(file.resolve()), file.stat().st_mtime_ns)
            index = _INDEX_CACHE.get(key)
            if index is None:
                index = await asyncio.to_thread(load_claml, file)
                _INDEX_CACHE[key] = index
                logger.info(f"ICD-10-GM: indexed {len(index.classes)} classes from {file.name}")
            self._index = index
            return index

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search by code (exact, then prefix) or by German title / inclusion term."""
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            index = await self._ensure_index()
            hits: list[tuple[float, ClaMLClass]] = []
            code = normalise_code(query)
            if _CODE_LIKE_RE.match(code) or index.get(code) is not None:
                hits = index.search_code(code, limit)
            if not hits:
                hits = index.search_text(query, limit)
            concepts = [self._convert(cls, index, score) for score, cls in hits]
            logger.info(f"ICD-10-GM search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"ICD-10-GM search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Look up a code (``G93.3``, ``G933``, ``ICD10GM:G93.3``, block ``G90-G99``)."""
        try:
            code = normalise_code(concept_id)
            if not code:
                return None
            index = await self._ensure_index()
            cls = index.get(code)
            return self._convert(cls, index, 1.0, detailed=True) if cls else None
        except Exception as e:
            logger.error(f"ICD-10-GM get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """``is_a`` parents, ``has_subtype`` children, plus ``excludes`` / ``includes``.

        Exclusion and inclusion rubrics only become edges when they carry a reference to
        another class code (e.g. R53 excludes G93.3); free-text rubrics stay in
        ``source_data`` of the concept details.
        """
        try:
            code = normalise_code(concept_id)
            index = await self._ensure_index()
            cls = index.get(code) if code else None
            if cls is None:
                return []
            edges: list[tuple[str, str]] = [("is_a", c) for c in cls.parents]
            edges += [("has_subtype", c) for c in cls.children[: max(limit, 0)]]
            for label, rubrics in (("excludes", cls.exclusions), ("includes", cls.inclusions)):
                for _, refs in rubrics:
                    edges += [(label, ref) for ref in refs]
            relationships: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for label, target in edges:
                if (label, target) in seen:
                    continue
                seen.add((label, target))
                related = index.get(target)
                relationships.append(
                    {
                        "relation_label": label,
                        "related_id": related.code if related else target,
                        "related_name": related.label if related else target,
                        "source": "ICD10GM",
                    }
                )
            return relationships
        except Exception as e:
            logger.error(f"ICD-10-GM get_relationships failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert(
        self, cls: ClaMLClass, index: ClaMLIndex, score: float, detailed: bool = False
    ) -> UnifiedConcept:
        concept_type = ConceptType.SYMPTOM if cls.code.startswith("R") else ConceptType.DISEASE
        concept = self._create_concept(cls.code, cls.label or cls.code, concept_type)
        concept.synonyms = [text for text, _ in cls.inclusions]
        if concept.semantic_types is not None:
            concept.semantic_types.append(cls.kind)
            if cls.usage:
                concept.semantic_types.append(cls.usage)
        concept.parents = list(cls.parents)
        concept.children = list(cls.children)
        concept.labels = json.dumps({"de": cls.label})
        concept.confidence_score = score
        if cls.long_label and cls.long_label != cls.label:
            concept.definitions = [cls.long_label]

        chain = index.path(cls.code)
        if concept.categories is not None:
            for ancestor in chain[:-1]:
                concept.categories.append(f"{ancestor.kind}:{ancestor.code} {ancestor.label}")

        if detailed and isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.ICD10GM] = {
                "code": cls.code,
                "kind": cls.kind,
                "usage": cls.usage,
                "version": index.version,
                "hierarchy": [{"code": c.code, "label": c.label, "kind": c.kind} for c in chain],
                "inclusions": [text for text, _ in cls.inclusions],
                "exclusions": [text for text, _ in cls.exclusions],
                "notes": list(cls.notes),
            }
        return concept
