"""
CZ CELLxGENE Discover adapter (single-cell collections, datasets, cell types, tissues).

CELLxGENE Discover (Chan Zuckerberg Initiative) hosts curated single-cell RNA-seq datasets
annotated with ontology terms (Cell Ontology ``CL``, ``UBERON`` tissues, ``MONDO`` diseases,
``EFO`` assays). The API at ``https://api.cellxgene.cziscience.com`` is keyless. Verified live
2026-10, what the adapter uses and why:

* ``dp/v1/datasets/index`` (13 MB, ~0.6 s from the CDN: 2238 datasets) and
  ``dp/v1/collections/index`` (555 KB, 397 collections) are the portal's own index. They are the
  only cheap source of **per-dataset cell types and cell counts**. The documented Curation API
  list ``curation/v1/collections`` carries tissue / disease / assay but no cell types, and is
  3 MB and 7 - 11 s, so it is *not* used for the list. Both ``dp`` indexes are loaded once and
  kept in memory for 15 minutes; searching then happens locally (the portal has no search API).
  The ``dp`` endpoints are internal to the web app and could change without notice; if they
  fail every method degrades to ``[]`` / ``None`` rather than raising.
* ``curation/v1/collections/{id}`` (20 KB, ~1 s) and
  ``curation/v1/collections/{id}/datasets/{dataset_id}`` (3 KB) are the supported API and add
  what the index lacks: description, DOI, links, journal, and the asset **URLs and sizes** of the
  ``.h5ad`` files. Those files (1 GB and more) are never downloaded; only their URLs are
  returned.
* ``wmg/v2/primary_filter_dimensions`` (3.5 MB, ~4 s, once per six hours) maps Ensembl ids to
  symbols and lists the tissues the "Where is my gene" service knows;
  ``POST wmg/v2/markers`` returns computational marker genes (``test="ttest"``; ``binomtest``
  answers HTTP 500) for one human cell type in one tissue. The WMG snapshot is a fixed
  expression snapshot (id echoed in results), not live data.

Disease labels worth knowing for ME/CFS and Long COVID research: ``long COVID-19``,
``post-COVID-19 disorder`` and ``COVID-19`` all occur (≈ 66 datasets mention COVID-19).

Data are released under CC BY 4.0 (CC0 for some collections: see each collection's license
in the portal); cite the original publication (DOI in ``source_data``) and "CZ CELLxGENE
Discover" (CZI Single-Cell Biology et al., bioRxiv 2023). Requests are spaced 0.3 s apart.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

CELLXGENE_BASE_URL = "https://api.cellxgene.cziscience.com"
PORTAL_URL = "https://cellxgene.cziscience.com"
HUMAN = "NCBITaxon:9606"

_MIN_INTERVAL = 0.3
_INDEX_TTL = 900.0  # seconds the dp indexes stay cached
_WMG_TTL = 6 * 3600.0
_DEFAULT_RELATION_LIMIT = 25
_MAX_SEARCH = 100
_MAX_MAPPINGS = 100
_MARKER_TISSUE_TRIES = 3

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_TERM_RE = re.compile(r"^(CL|UBERON|MONDO|PATO|EFO|HP|NCBITaxon)[:_](\d+)$", re.IGNORECASE)
_EXPLORER_RE = re.compile(r"/e/([0-9a-fA-F-]{36})")
_PREFIX_RE = re.compile(r"^(cellxgene|collection|dataset)\s*:\s*", re.IGNORECASE)

_KIND_TYPES = {
    "cell_type": ConceptType.CELL_TYPE,
    "tissue": ConceptType.TISSUE,
    "disease": ConceptType.DISEASE,
}


@dataclass
class _Term:
    """An ontology term seen on at least one dataset (cell type, tissue or disease)."""

    id: str
    label: str
    kind: str
    datasets: list[str] = field(default_factory=list)
    collections: set[str] = field(default_factory=set)
    cells: int = 0


@dataclass
class _Index:
    """In-memory view of the portal index, built once per load."""

    loaded_at: float
    datasets: dict[str, dict[str, Any]]
    collections: dict[str, dict[str, Any]]
    terms: dict[str, _Term]
    by_collection: dict[str, list[str]]
    versions: dict[str, str]  # dataset version id -> dataset id


def _ontology_pairs(items: Any) -> list[tuple[str, str]]:
    """``[{"label": .., "ontology_term_id": ..}]`` -> ``[(id, label)]`` without duplicates.

    Multi-valued annotations (several diseases on one donor) are stored as one entry whose
    id and label are joined with `` || `` (``MONDO:0005556 || MONDO:0007915``); they are split
    here so every term counts on its own.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict) or not item.get("ontology_term_id"):
            continue
        ids = [i.strip() for i in str(item["ontology_term_id"]).split("||") if i.strip()]
        labels = [lbl.strip() for lbl in str(item.get("label") or "").split("||")]
        if len(labels) != len(ids):
            labels = [str(item.get("label") or i) if len(ids) == 1 else i for i in ids]
        for term_id, label in zip(ids, labels, strict=True):
            if term_id not in seen:
                seen.add(term_id)
                out.append((term_id, label or term_id))
    return out


def _term_id(raw: str) -> str:
    match = _TERM_RE.match(raw.strip())
    if not match:
        return raw.strip()
    prefix = "NCBITaxon" if match.group(1).lower() == "ncbitaxon" else match.group(1).upper()
    return f"{prefix}:{match.group(2)}"


class CellxGeneAdapter(KnowledgeSourceAdapter):
    """Adapter for CZ CELLxGENE Discover (collections, datasets, cell types, markers)."""

    min_request_timeout = 120.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = CELLXGENE_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._index: _Index | None = None
        self._index_lock = asyncio.Lock()
        self._wmg: tuple[float, dict[str, str], dict[str, str]] | None = None
        self._wmg_lock = asyncio.Lock()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CELLXGENE

    def is_available(self) -> bool:
        return True  # public API, no key

    # ------------------------------------------------------------------
    # HTTP / index loading
    # ------------------------------------------------------------------

    async def _request(self, path: str, json_data: dict[str, Any] | None = None) -> Any:
        """GET (or POST with ``json_data``) ``<base>/<path>``, 0.3 s apart."""
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        return await self._make_request(f"{self.base_url}/{path}", json_data=json_data)

    async def _load_index(self) -> _Index:
        """Portal datasets + collections index (about 13.5 MB), cached for 15 minutes."""
        async with self._index_lock:
            cached = self._index
            if cached and time.monotonic() - cached.loaded_at < _INDEX_TTL:
                return cached
            raw_datasets = await self._request("dp/v1/datasets/index")
            raw_collections = await self._request("dp/v1/collections/index")
            if not isinstance(raw_datasets, list) or not isinstance(raw_collections, list):
                raise ValueError("unexpected CELLxGENE index response")
            index = self._build_index(raw_datasets, raw_collections)
            self._index = index
            return index

    @staticmethod
    def _build_index(raw_datasets: list[Any], raw_collections: list[Any]) -> _Index:
        collections: dict[str, dict[str, Any]] = {}
        for col in raw_collections:
            if isinstance(col, dict) and col.get("id"):
                meta = col.get("publisher_metadata") or {}
                collections[str(col["id"])] = {
                    "id": str(col["id"]),
                    "name": str(col.get("name") or col["id"]),
                    "consortia": list(col.get("consortia") or []),
                    "journal": meta.get("journal"),
                    "year": meta.get("published_year"),
                    "is_preprint": meta.get("is_preprint"),
                    "citation": col.get("summary_citation"),
                }
        datasets: dict[str, dict[str, Any]] = {}
        terms: dict[str, _Term] = {}
        by_collection: dict[str, list[str]] = {}
        versions: dict[str, str] = {}
        for raw in raw_datasets:
            if not isinstance(raw, dict) or not raw.get("id") or raw.get("tombstone"):
                continue
            version_id = str(raw["id"])
            # the index "id" is the dataset *version* id; the stable dataset id (the one in
            # portal URLs and the Curation API) is the uuid in explorer_url for all datasets
            match = _EXPLORER_RE.search(str(raw.get("explorer_url") or ""))
            ds_id = match.group(1).lower() if match else version_id
            versions[version_id] = ds_id
            col_id = str(raw.get("collection_id") or "")
            record: dict[str, Any] = {
                "id": ds_id,
                "version_id": version_id,
                "collection_id": col_id,
                "name": str(raw.get("name") or ds_id),
                "cell_count": raw.get("cell_count") or 0,
                "tissues": _ontology_pairs(raw.get("tissue")),
                "cell_types": _ontology_pairs(raw.get("cell_type")),
                "diseases": _ontology_pairs(raw.get("disease")),
                "assays": _ontology_pairs(raw.get("assay")),
                "organisms": _ontology_pairs(raw.get("organism")),
                "tissue_ancestors": set(raw.get("tissue_ancestors") or []),
                "n_donors": len(raw.get("donor_id") or []),
                "explorer_url": raw.get("explorer_url"),
            }
            datasets[ds_id] = record
            by_collection.setdefault(col_id, []).append(ds_id)
            for kind, key in (
                ("cell_type", "cell_types"),
                ("tissue", "tissues"),
                ("disease", "diseases"),
            ):
                for term_id, label in record[key]:
                    term = terms.setdefault(term_id, _Term(term_id, label, kind))
                    term.datasets.append(ds_id)
                    term.collections.add(col_id)
                    term.cells += int(record["cell_count"])
        return _Index(time.monotonic(), datasets, collections, terms, by_collection, versions)

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("uuid", "...")`` (collection or dataset) or ``("term", "CL:0000623")``."""
        text = _PREFIX_RE.sub("", (concept_id or "").strip())
        if _UUID_RE.match(text):
            return "uuid", text.lower()
        if _TERM_RE.match(text):
            return "term", _term_id(text)
        return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Cell types, tissues, diseases, collections and datasets matching every token.

        Matching is local, case-insensitive and on whole words, on labels (terms), collection /
        dataset titles and disease labels (so ``long covid`` finds the collections that contain a
        ``long COVID-19`` dataset). Buckets are interleaved so a common query shows terms,
        collections and datasets together; each bucket is ranked by match quality, then size.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            index = await self._load_index()
        except Exception as e:
            logger.error(f"CELLxGENE search failed for '{text}': {e}")
            return []
        limit = min(limit, _MAX_SEARCH)
        tokens = [t for t in re.split(r"[\s,;/]+", text.casefold()) if t]
        folded = text.casefold()

        # whole words (a plural "s" is allowed): "long" must not match "longitudinal"
        patterns = [
            re.compile(rf"(?<![a-z0-9]){re.escape(t)}(?:e?s)?(?![a-z0-9])") for t in tokens
        ]

        def has_all(haystack: str) -> bool:
            folded_haystack = haystack.casefold()
            return all(p.search(folded_haystack) for p in patterns)

        terms: list[tuple[float, int, UnifiedConcept]] = []
        for term in index.terms.values():
            if has_all(term.label) or term.id.casefold() == folded:
                score = 0.95 if term.label.casefold() == folded else 0.85
                terms.append((score, len(term.datasets), self._term_concept(term, index)))
        collections: list[tuple[float, int, UnifiedConcept]] = []
        for col_id, col in index.collections.items():
            ds_ids = index.by_collection.get(col_id, [])
            if has_all(col["name"]):
                score = 0.8
            elif has_all(
                " ".join(lbl for d in ds_ids for _, lbl in index.datasets[d]["diseases"])
            ):
                score = 0.65
            else:
                continue
            collections.append((score, len(ds_ids), self._collection_concept(col, index)))
        datasets: list[tuple[float, int, UnifiedConcept]] = []
        for record in index.datasets.values():
            if has_all(record["name"]):
                score = 0.6
            elif has_all(" ".join(lbl for _, lbl in record["diseases"])):
                score = 0.5
            else:
                continue
            datasets.append(
                (score, int(record["cell_count"]), self._dataset_concept(record, index))
            )

        buckets = []
        for bucket in (terms, collections, datasets):
            bucket.sort(key=lambda s: (-s[0], -s[1], s[2].primary_label))
            buckets.append(bucket)
        picked: list[UnifiedConcept] = []
        position = 0
        while len(picked) < limit and any(position < len(b) for b in buckets):
            for bucket in buckets:
                if position < len(bucket) and len(picked) < limit:
                    score, _, concept = bucket[position]
                    concept.confidence_score = score
                    picked.append(concept)
            position += 1
        picked.sort(key=lambda c: -(c.confidence_score or 0))
        logger.info(f"CELLxGENE search for '{text}' returned {len(picked)} concepts")
        return picked

    # ------------------------------------------------------------------
    # Details
    # ------------------------------------------------------------------

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Collection / dataset (UUID) or cell type / tissue / disease (ontology id).

        Collections add description, DOI, links and journal from the Curation API; datasets
        add the asset URLs and sizes (never downloaded). If that second request fails the
        index-based concept is still returned.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        try:
            index = await self._load_index()
            kind, value = parsed
            value = index.versions.get(value, value)  # accept dataset version ids
            if kind == "term":
                term = index.terms.get(value)
                concept = self._term_concept(term, index) if term else None
            elif value in index.collections:
                concept = self._collection_concept(index.collections[value], index)
                await self._add_collection_detail(concept, value)
            elif value in index.datasets:
                record = index.datasets[value]
                concept = self._dataset_concept(record, index)
                await self._add_dataset_detail(concept, record)
            else:
                return None
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"CELLxGENE get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _add_collection_detail(self, concept: UnifiedConcept, collection_id: str) -> None:
        try:
            data = await self._request(f"curation/v1/collections/{collection_id}")
        except Exception as e:
            logger.warning(f"CELLxGENE collection {collection_id} detail failed: {e}")
            return
        if not isinstance(data, dict):
            return
        meta = data.get("publisher_metadata") or {}
        authors = [
            f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in (meta.get("authors") or [])[:5]
            if isinstance(a, dict)
        ]
        if data.get("description") and concept.definitions is not None:
            concept.definitions.append(str(data["description"]).strip())
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()].update(
                {
                    "doi": data.get("doi"),
                    "journal": meta.get("journal"),
                    "first_authors": authors,
                    "links": [
                        {"type": link.get("link_type"), "url": link.get("link_url")}
                        for link in data.get("links") or []
                        if isinstance(link, dict) and link.get("link_url")
                    ],
                    "published_at": data.get("published_at"),
                    "revised_at": data.get("revised_at"),
                }
            )

    async def _add_dataset_detail(self, concept: UnifiedConcept, record: dict[str, Any]) -> None:
        if not record["collection_id"]:
            return
        try:
            data = await self._request(
                f"curation/v1/collections/{record['collection_id']}/datasets/{record['id']}"
            )
        except Exception as e:
            logger.warning(f"CELLxGENE dataset {record['id']} detail failed: {e}")
            return
        if not isinstance(data, dict) or not isinstance(concept.source_data, dict):
            return
        concept.source_data[self.get_source()].update(
            {
                "assets": [  # URLs only: h5ad files are 1 GB and more
                    {
                        "filetype": a.get("filetype"),
                        "url": a.get("url"),
                        "filesize_bytes": a.get("filesize"),
                    }
                    for a in data.get("assets") or []
                    if isinstance(a, dict) and a.get("url")
                ],
                "schema_version": data.get("schema_version"),
                "citation": data.get("citation"),
                "donor_ids": list(data.get("donor_id") or [])[:20],
                "sex": [s for s in data.get("sex") or [] if isinstance(s, dict)][:5],
                "mean_genes_per_cell": data.get("mean_genes_per_cell"),
                "suspension_type": data.get("suspension_type"),
            }
        )

    # ------------------------------------------------------------------
    # Mappings
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Ontology ids carried by a collection / dataset (and the DOI of a collection).

        Collections and datasets map to their tissue (UBERON), disease (MONDO / PATO), assay
        (EFO), organism (NCBITaxon) and cell type (CL) terms, ``mappingType="annotation"``,
        capped at 100. An ontology-term concept maps to itself in its own ontology.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return []
        try:
            index = await self._load_index()
        except Exception as e:
            logger.error(f"CELLxGENE get_mappings failed for '{concept_id}': {e}")
            return []
        kind, value = parsed
        value = index.versions.get(value, value)  # accept dataset version ids
        if kind == "term":
            if value not in index.terms:
                return []
            return [self._mapping(value, value, "exact", 1.0)]
        records: list[dict[str, Any]]
        doi: str | None = None
        if value in index.collections:
            records = [index.datasets[d] for d in index.by_collection.get(value, [])]
            try:
                data = await self._request(f"curation/v1/collections/{value}")
                doi = data.get("doi") if isinstance(data, dict) else None
            except Exception as e:
                logger.warning(f"CELLxGENE collection {value} DOI lookup failed: {e}")
        elif value in index.datasets:
            records = [index.datasets[value]]
        else:
            return []
        mappings: list[dict[str, Any]] = []
        if doi:
            mappings.append(self._mapping(value, f"DOI:{doi}", "exact", 0.95))
        seen: set[str] = set()
        for key in ("tissues", "diseases", "assays", "organisms", "cell_types"):
            for record in records:
                for term_id, _ in record[key]:
                    if term_id not in seen and len(mappings) < _MAX_MAPPINGS:
                        seen.add(term_id)
                        mappings.append(self._mapping(value, term_id, "annotation", 0.95))
        return mappings

    @staticmethod
    def _mapping(from_id: str, to_id: str, mapping_type: str, confidence: float) -> dict[str, Any]:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "CELLXGENE",
            "toSource": to_id.split(":")[0].upper() if ":" in to_id else "CELLXGENE",
            "mappingType": mapping_type,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_relationships(
        self,
        concept_id: str,
        limit: int = _DEFAULT_RELATION_LIMIT,
        tissue: str | None = None,
    ) -> list[dict[str, Any]]:
        """Typed edges between collections, datasets, cell types, tissues and diseases.

        ``limit`` caps every repeated relation type.

        * collection: ``has_dataset`` (extras ``cell_count``, ``tissues``, ``diseases``),
          ``has_tissue``, ``has_disease`` (UBERON / MONDO ids, ``n_datasets``).
        * dataset: ``part_of_collection``, ``has_tissue``, ``has_cell_type``, ``has_disease``,
          ``uses_assay`` (EFO), ``from_organism`` (NCBITaxon).
        * cell type: ``found_in_tissue`` (``n_datasets``), ``found_in_dataset`` (largest first)
          and ``has_marker_gene`` from the WMG service (human only; ``tissue`` optionally pins
          the UBERON tissue, otherwise the best-represented WMG tissue is used; extras
          ``marker_score``, ``specificity``, ``tissue``, ``tissue_id``, ``snapshot_id``).
        * tissue: ``contains_cell_type``, ``studied_in_collection``.
        * disease: ``studied_in_collection`` (``n_datasets``, ``cells``), ``observed_in_tissue``,
          ``contains_cell_type``.
        """
        if limit <= 0:
            return []
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return []
        try:
            index = await self._load_index()
            kind, value = parsed
            value = index.versions.get(value, value)  # accept dataset version ids
            if kind == "term":
                term = index.terms.get(value)
                if term is None:
                    return []
                edges = self._term_edges(term, index, limit)
                if term.kind == "cell_type":
                    edges += await self._marker_edges(term, index, limit, tissue)
                return edges
            if value in index.collections:
                return self._collection_edges(value, index, limit)
            if value in index.datasets:
                return self._dataset_edges(index.datasets[value], index, limit)
            return []
        except Exception as e:
            logger.error(f"CELLxGENE get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _edge(label: str, related_id: str, related_name: str, **extra: Any) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": related_id,
            "related_name": related_name,
            "source": "CELLXGENE",
            **extra,
        }

    @staticmethod
    def _count_terms(
        dataset_ids: list[str], index: _Index, key: str
    ) -> list[tuple[str, str, int]]:
        """``(id, label, n_datasets)`` for an annotation field, most frequent first."""
        counts: dict[str, int] = {}
        labels: dict[str, str] = {}
        for ds_id in dataset_ids:
            for term_id, label in index.datasets[ds_id][key]:
                counts[term_id] = counts.get(term_id, 0) + 1
                labels[term_id] = label
        return sorted(((t, labels[t], n) for t, n in counts.items()), key=lambda x: (-x[2], x[1]))

    def _collection_edges(
        self, collection_id: str, index: _Index, limit: int
    ) -> list[dict[str, Any]]:
        ds_ids = index.by_collection.get(collection_id, [])
        ordered = sorted(ds_ids, key=lambda d: -int(index.datasets[d]["cell_count"]))
        edges = [
            self._edge(
                "has_dataset",
                d,
                index.datasets[d]["name"],
                cell_count=index.datasets[d]["cell_count"],
                tissues=[lbl for _, lbl in index.datasets[d]["tissues"]],
                diseases=[lbl for _, lbl in index.datasets[d]["diseases"]],
                explorer_url=index.datasets[d]["explorer_url"],
            )
            for d in ordered[:limit]
        ]
        for label, key in (("has_tissue", "tissues"), ("has_disease", "diseases")):
            for term_id, name, n in self._count_terms(ds_ids, index, key)[:limit]:
                edges.append(self._edge(label, term_id, name, n_datasets=n))
        return edges

    def _dataset_edges(
        self, record: dict[str, Any], index: _Index, limit: int
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        collection = index.collections.get(record["collection_id"])
        if collection:
            edges.append(self._edge("part_of_collection", collection["id"], collection["name"]))
        for label, key in (
            ("has_tissue", "tissues"),
            ("has_disease", "diseases"),
            ("uses_assay", "assays"),
            ("from_organism", "organisms"),
            ("has_cell_type", "cell_types"),
        ):
            for term_id, name in sorted(record[key], key=lambda p: p[1])[:limit]:
                edges.append(self._edge(label, term_id, name))
        return edges

    def _term_edges(self, term: _Term, index: _Index, limit: int) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        if term.kind in ("cell_type", "disease"):
            for term_id, name, n in self._count_terms(term.datasets, index, "tissues")[:limit]:
                label = "found_in_tissue" if term.kind == "cell_type" else "observed_in_tissue"
                edges.append(self._edge(label, term_id, name, n_datasets=n))
        if term.kind in ("tissue", "disease"):
            for term_id, name, n in self._count_terms(term.datasets, index, "cell_types")[:limit]:
                edges.append(self._edge("contains_cell_type", term_id, name, n_datasets=n))
        if term.kind in ("tissue", "disease"):
            per_collection: dict[str, list[str]] = {}
            for ds_id in term.datasets:
                per_collection.setdefault(index.datasets[ds_id]["collection_id"], []).append(ds_id)
            ranked = sorted(per_collection.items(), key=lambda kv: (-len(kv[1]), kv[0]))
            for col_id, ds_ids in ranked[:limit]:
                col = index.collections.get(col_id)
                if col:
                    edges.append(
                        self._edge(
                            "studied_in_collection",
                            col_id,
                            col["name"],
                            n_datasets=len(ds_ids),
                            cells=sum(int(index.datasets[d]["cell_count"]) for d in ds_ids),
                        )
                    )
        if term.kind == "cell_type":
            largest = sorted(term.datasets, key=lambda d: -int(index.datasets[d]["cell_count"]))
            for ds_id in largest[:limit]:
                record = index.datasets[ds_id]
                edges.append(
                    self._edge(
                        "found_in_dataset",
                        ds_id,
                        record["name"],
                        cell_count=record["cell_count"],
                        collection=(index.collections.get(record["collection_id"]) or {}).get(
                            "name"
                        ),
                    )
                )
        return edges

    # ------------------------------------------------------------------
    # Marker genes (WMG)
    # ------------------------------------------------------------------

    async def _wmg_dimensions(self) -> tuple[dict[str, str], dict[str, str]]:
        """``(ensembl id -> symbol, tissue id -> name)`` for human; empty when unavailable."""
        async with self._wmg_lock:
            if self._wmg and time.monotonic() - self._wmg[0] < _WMG_TTL:
                return self._wmg[1], self._wmg[2]
            try:
                data = await self._request("wmg/v2/primary_filter_dimensions")
                genes: dict[str, str] = {}
                for entry in (data.get("gene_terms") or {}).get(HUMAN, []):
                    genes.update({str(k): str(v) for k, v in entry.items()})
                tissues: dict[str, str] = {}
                for entry in (data.get("tissue_terms") or {}).get(HUMAN, []):
                    tissues.update({str(k): str(v) for k, v in entry.items()})
            except Exception as e:
                logger.warning(f"CELLxGENE WMG dimensions unavailable: {e}")
                return {}, {}
            self._wmg = (time.monotonic(), genes, tissues)
            return genes, tissues

    async def _marker_edges(
        self, term: _Term, index: _Index, limit: int, tissue: str | None
    ) -> list[dict[str, Any]]:
        symbols, wmg_tissues = await self._wmg_dimensions()
        if tissue:
            candidates = [_term_id(tissue)]
        else:
            direct: dict[str, int] = {}
            rolled_up: dict[str, int] = {}
            for ds_id in term.datasets:
                record = index.datasets[ds_id]
                if HUMAN not in {o for o, _ in record["organisms"]}:
                    continue
                own = {t for t, _ in record["tissues"]}
                for tissue_id in own | record["tissue_ancestors"]:
                    if wmg_tissues and tissue_id not in wmg_tissues:
                        continue
                    bucket = direct if tissue_id in own else rolled_up
                    bucket[tissue_id] = bucket.get(tissue_id, 0) + 1
            # tissues the datasets name directly (blood for NK cells) before rolled-up
            # ancestors (brain), each best-represented first
            candidates = []
            for counts in (direct, rolled_up):
                for tissue_id, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                    if tissue_id not in candidates:
                        candidates.append(tissue_id)
        for tissue_id in candidates[:_MARKER_TISSUE_TRIES]:
            try:
                data = await self._request(
                    "wmg/v2/markers",
                    json_data={
                        "celltype": term.id,
                        "organism": HUMAN,
                        "tissue": tissue_id,
                        "test": "ttest",
                        "n_markers": min(limit, 100),
                    },
                )
            except Exception as e:
                logger.warning(f"CELLxGENE markers for {term.id} in {tissue_id} failed: {e}")
                continue
            markers = data.get("marker_genes") if isinstance(data, dict) else None
            if not markers:
                continue
            return [
                self._edge(
                    "has_marker_gene",
                    str(m["gene_ontology_term_id"]),
                    symbols.get(str(m["gene_ontology_term_id"]), str(m["gene_ontology_term_id"])),
                    marker_score=m.get("marker_score"),
                    specificity=m.get("specificity"),
                    tissue=wmg_tissues.get(tissue_id) or tissue_id,
                    tissue_id=tissue_id,
                    organism="Homo sapiens",
                    snapshot_id=data.get("snapshot_id"),
                )
                for m in markers[:limit]
                if isinstance(m, dict) and m.get("gene_ontology_term_id")
            ]
        return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _term_concept(self, term: _Term, index: _Index) -> UnifiedConcept:
        concept = self._create_concept(term.id, term.label, _KIND_TYPES[term.kind])
        tissues = self._count_terms(term.datasets, index, "tissues")[:10]
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": term.kind,
                "n_datasets": len(term.datasets),
                "n_collections": len(term.collections),
                # sum over datasets that carry the term: a dataset's cells are all counted,
                # not only those of this type, and re-annotated datasets can overlap
                "cells_in_datasets": term.cells,
                "top_tissues": [{"id": t, "label": n, "n_datasets": c} for t, n, c in tissues],
            }
        return concept

    def _collection_concept(self, col: dict[str, Any], index: _Index) -> UnifiedConcept:
        col_id = col["id"]
        concept = self._create_concept(col_id, col["name"], ConceptType.REFERENCE)
        ds_ids = index.by_collection.get(col_id, [])
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": "collection",
                "citation": col.get("citation"),
                "journal": col.get("journal"),
                "year": col.get("year"),
                "is_preprint": col.get("is_preprint"),
                "consortia": col.get("consortia"),
                "n_datasets": len(ds_ids),
                "total_cells": sum(int(index.datasets[d]["cell_count"]) for d in ds_ids),
                "tissues": [
                    {"id": t, "label": n}
                    for t, n, _ in self._count_terms(ds_ids, index, "tissues")
                ],
                "diseases": [
                    {"id": t, "label": n}
                    for t, n, _ in self._count_terms(ds_ids, index, "diseases")
                ],
                "assays": [lbl for _, lbl, _ in self._count_terms(ds_ids, index, "assays")],
                "organisms": [lbl for _, lbl, _ in self._count_terms(ds_ids, index, "organisms")],
                "n_cell_types": len(self._count_terms(ds_ids, index, "cell_types")),
                "url": f"{PORTAL_URL}/collections/{col_id}",
            }
        return concept

    def _dataset_concept(self, record: dict[str, Any], index: _Index) -> UnifiedConcept:
        ds_id = record["id"]
        concept = self._create_concept(ds_id, record["name"], ConceptType.ASSAY)
        collection = index.collections.get(record["collection_id"]) or {}
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": "dataset",
                "collection_id": record["collection_id"],
                "collection_name": collection.get("name"),
                "cell_count": record["cell_count"],
                "n_donors": record["n_donors"],
                "organisms": [lbl for _, lbl in record["organisms"]],
                "tissues": [{"id": t, "label": n} for t, n in record["tissues"]],
                "diseases": [{"id": t, "label": n} for t, n in record["diseases"]],
                "assays": [lbl for _, lbl in record["assays"]],
                "n_cell_types": len(record["cell_types"]),
                "cell_types": [{"id": t, "label": n} for t, n in record["cell_types"][:50]],
                "explorer_url": record["explorer_url"],
            }
        return concept
