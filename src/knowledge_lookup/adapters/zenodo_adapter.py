"""
Zenodo adapter: discovery of research datasets, software and publications (metadata only).

Zenodo (CERN/OpenAIRE) is a general-purpose repository; researchers deposit datasets,
code and papers there and receive a DOI (``10.5281/zenodo.<record id>``). This adapter helps
*find* material (for example ME/CFS or Long COVID datasets): it returns metadata and the
record URL and **never downloads files**. Verified live 2026-10 against
``https://zenodo.org/api``:

* ``GET /records?q=<text>&size=<=25&page=<n>&sort=bestmatch|mostrecent&type=<resource type>``
  (``q`` is Elasticsearch query-string syntax: ``"long covid"`` for a phrase, ``AND``/``OR``,
  fields such as ``metadata.keywords:"ME/CFS"``; a bare ``long covid`` means long OR covid).
  Only the latest version of each record is returned. ``size`` above 25 is rejected with 400
  for anonymous callers, a ``page`` past the end gives 400, an unknown ``type`` silently gives
  zero hits (the adapter validates it first) and an invalid ``sort`` gives 400.
* ``GET /records/<id>`` returns one record with the same shape as a search hit. A missing
  record answers 404; very small ids (``records/1``) answer 500, which is treated as "not
  found". Hits carry: ``id``, ``doi``, ``conceptdoi`` / ``conceptrecid`` (the DOI that always
  resolves to the latest version; absent on records whose DOI was minted elsewhere, e.g.
  Dryad), ``links.self_html``, ``metadata`` (``title``, ``description`` as HTML,
  ``publication_date``, ``creators``, ``keywords``, ``resource_type``, ``license``,
  ``communities`` as ``[{"id": slug}]``, ``access_right``, ``related_identifiers`` with
  ``identifier`` / ``relation`` / ``scheme``) and ``files`` (``key``, ``size``, ``checksum``).
  Only the number and total size of files are exposed here; file download links are never
  returned or followed.

Rate limits (``X-RateLimit-*`` headers, verified): search is limited to **30 requests/minute**
for anonymous callers, single-record reads to about 130/minute; both are throttled here
(2.1 s between searches, 0.5 s between record reads). With an optional personal access token
(``ZENODO_ACCESS_TOKEN`` or ``zenodo`` in the config's ``api_keys``; sent as a bearer header
only if set, never required) Zenodo documents higher limits and larger pages, but this could
not be verified without a token, so the adapter keeps the conservative anonymous behaviour
apart from a shorter search interval.

Licences: Zenodo metadata is CC0. The *content* of each record is under its own licence
(``license.id`` such as ``cc-by-4.0``; closed, restricted or embargoed records may not be
downloadable at all). Every concept's ``source_data`` carries the licence, the access right
and a ready-made attribution string; honour them before reusing any data.
"""

import asyncio
import html
import logging
import math
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

ZENODO_API_URL = "https://zenodo.org/api"
ZENODO_RECORD_URL = "https://zenodo.org/records/{record_id}"
ZENODO_COMMUNITY_URL = "https://zenodo.org/communities/{slug}"

# Verified limits: search 30/min anonymous, record reads ~130/min.
_MIN_INTERVAL_SEARCH = 2.1
_MIN_INTERVAL_SEARCH_TOKEN = 1.0
_MIN_INTERVAL_RECORD = 0.5
_PAGE_SIZE = 25  # largest page the API accepts anonymously
_MAX_SEARCH = 50  # two pages: a larger crawl is a bulk job, not a lookup
_MAX_DESCRIPTION_LENGTH = 4000
_MAX_CREATORS = 25

_RESOURCE_TYPES = {
    "dataset",
    "software",
    "publication",
    "image",
    "video",
    "poster",
    "presentation",
    "lesson",
    "physicalobject",
    "other",
}
_SORTS = {"bestmatch", "mostrecent"}

_ID_RE = re.compile(
    r"^(?:(?:https?://(?:dx\.)?doi\.org/|doi:)?10\.5281/zenodo\.|zenodo[.:_/]\s*|"
    r"https?://zenodo\.org/(?:records?|doi)/(?:10\.5281/zenodo\.)?)?(\d{1,12})/?$",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_RE = re.compile(r"</?(?:p|br|li|ul|ol|div|h[1-6]|tr)[^>]*>", re.IGNORECASE)
_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


class ZenodoAdapter(KnowledgeSourceAdapter):
    """Adapter for Zenodo records (datasets, software, publications): metadata and URLs only."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = ZENODO_API_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request: dict[str, float] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ZENODO

    def is_available(self) -> bool:
        return True  # keyless; a token only raises Zenodo's limits

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _token(self) -> str | None:
        return self.config.get_api_key("zenodo") or os.getenv("ZENODO_ACCESS_TOKEN") or None

    async def _zenodo(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``/api/<path>``, spacing calls per bucket (search vs. record reads)."""
        token = self._token()
        bucket = "record" if path.startswith("records/") else "search"
        if bucket == "record":
            interval = _MIN_INTERVAL_RECORD
        else:
            interval = _MIN_INTERVAL_SEARCH_TOKEN if token else _MIN_INTERVAL_SEARCH
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with self._throttle_lock:
            wait = interval - (time.monotonic() - self._last_request.get(bucket, -math.inf))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request[bucket] = time.monotonic()
        return await self._make_request(f"{self.base_url}/{path}", params, headers)

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> str | None:
        """Numeric record id from ``1234567``, ``zenodo.1234567``, ``10.5281/zenodo.1234567``,
        ``doi:...``, ``https://doi.org/...`` or ``https://zenodo.org/records/1234567``.

        Returns ``None`` for anything else (other DOIs included: a Dryad DOI that a Zenodo
        record carries as its own DOI cannot be resolved to a record id offline).
        """
        match = _ID_RE.match((concept_id or "").strip())
        if not match:
            return None
        value = match.group(1).lstrip("0")
        return value or None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(
        self,
        query: str,
        limit: int = 20,
        resource_type: str | None = None,
        sort: str = "bestmatch",
    ) -> list[UnifiedConcept]:
        """Search Zenodo records; a bare record id / Zenodo DOI goes straight to details.

        ``resource_type`` restricts to ``dataset``, ``software``, ``publication``, ``image``,
        ``video``, ``poster``, ``presentation``, ``lesson``, ``physicalobject`` or ``other``;
        ``sort`` is ``bestmatch`` (default) or ``mostrecent``. Results are limited to 50
        (two pages of 25, the anonymous maximum). Unknown values return ``[]``.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        rtype = resource_type.strip().lower() if resource_type else None
        sort_key = (sort or "bestmatch").strip().lower()
        if (rtype is not None and rtype not in _RESOURCE_TYPES) or sort_key not in _SORTS:
            logger.warning(f"Zenodo search: unsupported resource_type={rtype!r} or sort={sort!r}")
            return []
        try:
            # a short bare number ("2021", "5") is far more likely a search word than an id
            if self._parse_id(text) is not None and not (text.isdigit() and len(text) < 6):
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            wanted = min(limit, _MAX_SEARCH)
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for page in range(1, math.ceil(wanted / _PAGE_SIZE) + 1):
                # constant page size: Zenodo derives the offset as (page - 1) * size, so a
                # smaller last page would overlap the previous one
                params: dict[str, Any] = {
                    "q": text,
                    "size": _PAGE_SIZE if wanted > _PAGE_SIZE else wanted,
                    "page": page,
                    "sort": sort_key,
                }
                if rtype:
                    params["type"] = rtype
                data = await self._zenodo("records", params)
                hits = ((data or {}).get("hits") or {}).get("hits") or []
                for hit in hits:
                    concept = self._record_to_concept(hit)
                    if concept is None or concept.primary_id in seen:
                        continue
                    seen.add(concept.primary_id)
                    concept.confidence_score = max(0.5, 0.9 - 0.02 * len(concepts))
                    concepts.append(concept)
                    if len(concepts) >= wanted:
                        break
                if len(concepts) >= wanted or len(hits) < params["size"]:
                    break
            logger.info(f"Zenodo search for '{text}' returned {len(concepts)} records")
            return concepts
        except Exception as e:
            logger.error(f"Zenodo search failed for '{text}': {e}")
            return []

    async def _fetch_record(self, concept_id: str) -> dict[str, Any] | None:
        record_id = self._parse_id(concept_id)
        if record_id is None:
            return None
        data = await self._zenodo(f"records/{record_id}")
        if not isinstance(data, dict) or not data.get("id") or not data.get("metadata"):
            return None
        return data

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """One record: description, creators, licence, access right, file count and size."""
        try:
            record = await self._fetch_record(concept_id)
            if record is None:
                return None
            concept = self._record_to_concept(record)
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"Zenodo get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    @staticmethod
    def _snake(relation: str) -> str:
        """``isSupplementTo`` -> ``is_supplement_to`` (DataCite relation types are camelCase)."""
        return _CAMEL_RE.sub("_", relation.strip()).lower()

    @staticmethod
    def _curie(scheme: str, identifier: str) -> str:
        """Prefixed id for a related identifier (``DOI:``, ``PMID:``, ``arXiv:``; URLs as is)."""
        value = identifier.strip()
        scheme = scheme.strip().lower()
        if scheme == "doi":
            value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", value, flags=re.I)
            return f"DOI:{value}"
        if scheme == "pmid":
            return f"PMID:{value.removeprefix('PMID:').strip()}"
        if scheme == "arxiv":
            return f"arXiv:{re.sub(r'^arxiv:', '', value, flags=re.I).strip()}"
        if scheme in {"url", ""}:
            return value
        return f"{scheme}:{value}"

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Typed links of a record.

        ``relation_label`` values: ``has_license`` (licence id), ``in_community``
        (``zenodo-community:<slug>``, with the community URL), ``is_version_of`` (the concept
        DOI grouping all versions, when Zenodo minted it) and every entry of the record's
        ``related_identifiers`` under its DataCite relation in snake case (``cites``,
        ``is_supplement_to``, ``is_cited_by``, ``is_version_of``, ``has_version``,
        ``references``, ``is_part_of``, ...). ``related_id`` is ``DOI:...``, ``PMID:...``,
        ``arXiv:...``, a URL or ``<scheme>:<id>``; the original relation is kept in
        ``datacite_relation`` and the scheme in ``scheme``. Capped by ``limit``.
        """
        if limit <= 0:
            return []
        try:
            record = await self._fetch_record(concept_id)
        except Exception as e:
            logger.error(f"Zenodo get_relationships failed for '{concept_id}': {e}")
            return []
        if record is None:
            return []
        meta = record.get("metadata") or {}
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(label: str, related_id: str, name: str = "", **extra: Any) -> None:
            if not related_id or (label, related_id) in seen:
                return
            seen.add((label, related_id))
            results.append(
                {
                    "relation_label": label,
                    "related_id": related_id,
                    "related_name": name,
                    "source": "ZENODO",
                    **{k: v for k, v in extra.items() if v not in (None, "")},
                }
            )

        license_id = self._license_id(meta)
        if license_id:
            add("has_license", license_id, str((meta.get("license") or {}).get("title") or ""))
        for slug in self._communities(meta):
            add(
                "in_community",
                f"zenodo-community:{slug}",
                slug,
                url=ZENODO_COMMUNITY_URL.format(slug=slug),
            )
        concept_doi = record.get("conceptdoi")
        if concept_doi and str(record.get("conceptrecid")) != str(record.get("id")):
            add("is_version_of", f"DOI:{concept_doi}", "all versions", kind="concept_doi")
        for item in meta.get("related_identifiers") or []:
            if (
                not isinstance(item, dict)
                or not item.get("identifier")
                or not item.get("relation")
            ):
                continue
            scheme = str(item.get("scheme") or "")
            add(
                self._snake(str(item["relation"])),
                self._curie(scheme, str(item["identifier"])),
                "",
                datacite_relation=item["relation"],
                scheme=scheme,
                resource_type=item.get("resource_type"),
            )
        return results[:limit]

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Identifier mappings: the record DOI, the concept DOI and linked PMIDs/arXiv/DOIs.

        ``mappingType`` is ``same_as`` for the record's own DOI, ``version_group`` for the
        concept DOI (which resolves to the latest version) and the snake-case DataCite
        relation (``is_supplement_to``, ``cites``, ...) for linked publications, so a
        consumer can tell "this record is the supplement of PMID 30777853" from an
        equivalence. Other schemes (URLs, handles, LSIDs) are not mappings and are left to
        :meth:`get_relationships`.
        """
        try:
            record = await self._fetch_record(concept_id)
        except Exception as e:
            logger.error(f"Zenodo get_mappings failed for '{concept_id}': {e}")
            return []
        if record is None:
            return []
        from_id = str(record["id"])
        mappings: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(to_id: str, to_source: str, mapping_type: str) -> None:
            key = f"{mapping_type}|{to_id}"
            if key in seen:
                return
            seen.add(key)
            mappings.append(
                {
                    "fromId": from_id,
                    "toId": to_id,
                    "fromSource": "ZENODO",
                    "toSource": to_source,
                    "mappingType": mapping_type,
                    "confidence": 1.0,
                }
            )

        if record.get("doi"):
            add(f"DOI:{record['doi']}", "DOI", "same_as")
        if record.get("conceptdoi"):
            add(f"DOI:{record['conceptdoi']}", "DOI", "version_group")
        sources = {"doi": "DOI", "pmid": "PUBMED", "arxiv": "ARXIV"}
        for item in (record.get("metadata") or {}).get("related_identifiers") or []:
            if not isinstance(item, dict):
                continue
            scheme = str(item.get("scheme") or "").lower()
            if scheme in sources and item.get("identifier") and item.get("relation"):
                add(
                    self._curie(scheme, str(item["identifier"])),
                    sources[scheme],
                    self._snake(str(item["relation"])),
                )
        return mappings

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _plain_text(markup: Any) -> str:
        """Description HTML -> plain text (block tags become spaces, entities decoded)."""
        if not isinstance(markup, str):
            return ""
        text = _TAG_RE.sub("", _BLOCK_RE.sub(" ", markup))
        return re.sub(r"\s+", " ", html.unescape(text)).strip()

    @staticmethod
    def _license_id(meta: dict[str, Any]) -> str:
        lic = meta.get("license")
        return str(lic.get("id") or "") if isinstance(lic, dict) else ""

    @staticmethod
    def _communities(meta: dict[str, Any]) -> list[str]:
        return [
            str(c["id"])
            for c in meta.get("communities") or []
            if isinstance(c, dict) and c.get("id")
        ]

    def _record_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        if not isinstance(record, dict):
            return None
        meta = record.get("metadata")
        record_id = str(record.get("id") or record.get("recid") or "")
        if not isinstance(meta, dict) or not record_id.isdigit():
            return None
        title = (
            str(meta.get("title") or record.get("title") or "").strip() or f"zenodo.{record_id}"
        )
        raw_type = meta.get("resource_type")
        rtype: dict[str, Any] = raw_type if isinstance(raw_type, dict) else {}
        kind = str(rtype.get("type") or "").lower()
        subtype = str(rtype.get("subtype") or "")
        concept_type = {
            "dataset": ConceptType.STUDY,
            "publication": ConceptType.REFERENCE,
        }.get(kind, ConceptType.UNKNOWN)
        concept = self._create_concept(record_id, title, concept_type)
        url = str((record.get("links") or {}).get("self_html") or "") or ZENODO_RECORD_URL.format(
            record_id=record_id
        )
        if concept.identifiers:
            concept.identifiers[0].url = url
        doi = str(record.get("doi") or meta.get("doi") or "")
        if doi:
            concept.add_identifier(
                self.get_source(), f"DOI:{doi}", title, f"https://doi.org/{doi}"
            )

        description = self._plain_text(meta.get("description"))
        if description and concept.definitions is not None:
            concept.definitions.append(description[:_MAX_DESCRIPTION_LENGTH])
        keywords = [str(k).strip() for k in meta.get("keywords") or [] if str(k).strip()]
        if concept.categories is not None:
            concept.categories.extend(keywords)
        if concept.semantic_types is not None:
            label = str(rtype.get("title") or kind.capitalize() or "Record")
            concept.semantic_types.append(label)

        files = [f for f in record.get("files") or [] if isinstance(f, dict)]
        total_size = sum(f["size"] for f in files if isinstance(f.get("size"), int | float))
        creators = [
            str(c["name"])
            for c in meta.get("creators") or []
            if isinstance(c, dict) and c.get("name")
        ]
        year = str(meta.get("publication_date") or "")[:4]
        license_id = self._license_id(meta)
        access = str(meta.get("access_right") or "")
        who = creators[0] + (" et al." if len(creators) > 1 else "") if creators else "Anonymous"
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "record_id": record_id,
                "url": url,
                "doi": doi or None,
                "concept_doi": record.get("conceptdoi") or None,
                "concept_record_id": record.get("conceptrecid") or None,
                "resource_type": kind or None,
                "resource_subtype": subtype or None,
                "creators": creators[:_MAX_CREATORS],
                "creator_count": len(creators),
                "publication_date": meta.get("publication_date") or None,
                "version": meta.get("version") or None,
                "language": meta.get("language") or None,
                "keywords": keywords,
                "communities": self._communities(meta),
                "license": license_id or None,
                "access_right": access or None,
                "embargo_date": meta.get("embargo_date") or None,
                "file_count": len(files),
                "total_size_bytes": total_size,
                "attribution": f"{who} ({year}). {title}. Zenodo. "
                + (f"https://doi.org/{doi}" if doi else url),
                "license_note": (
                    f"Content licence: {license_id or 'not stated'}; access: "
                    f"{access or 'unknown'}. Zenodo metadata is CC0; no files are downloaded "
                    "by this adapter."
                ),
            }
        return concept
