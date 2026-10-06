"""
WHO ICD-11 Knowledge Source Adapter

Adapter for the WHO ICD-API (https://icd.who.int/icdapi), which serves the ICD-11
Mortality and Morbidity Statistics (MMS) linearization: the tabular list with codes such
as ``8E49`` (Postviral fatigue syndrome, the ME/CFS context) or ``RA02`` (Post COVID-19
condition).

Authentication: the cloud API (``https://id.who.int``) needs an OAuth2
client-credentials token (free registration at https://icd.who.int/icdapi). The token is
fetched from ``https://icdaccessmanagement.who.int/connect/token`` with
``scope=icdapi_access``, valid for about an hour, and is cached here (behind an async
lock) until shortly before it expires. A 401 from the API discards the cached token and
the request is retried once with a fresh one.

WHO also ships the API as a self-hosted Docker container (``whoicd/icd-api``) which needs
no token: set ``ICD11_API_BASE`` (e.g. ``http://localhost``) and the adapter sends no
``Authorization`` header and ``is_available()`` is true without credentials.

Configuration (environment variables, or ``config.get_api_key`` entries named
``icd11_client_id`` / ``icd11_client_secret``):

- ``ICD11_CLIENT_ID`` / ``ICD11_CLIENT_SECRET``: OAuth2 credentials.
- ``ICD11_API_BASE``: override the API root (self-hosted container).
- ``ICD11_RELEASE``: MMS release id, default ``2025-01`` (releases are listed at
  https://icd.who.int/docs/icd-api/SupportedClassifications/).
- ``ICD11_LANGUAGE``: ``Accept-Language`` value, default ``en`` (e.g. ``de``).

Post-coordination (``stem/extension`` codes) is ignored: only stem codes are resolved.
ICD-11 content is licensed by WHO (CC BY-ND 3.0 IGO); see the terms at
https://icd.who.int/en/docs/icd11-license.pdf. This adapter was written against the
public API documentation and OpenAPI description and is not live-verified (credentials
are required).
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

ICD11_TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
ICD11_API_BASE = "https://id.who.int"
ICD11_SCOPE = "icdapi_access"
DEFAULT_RELEASE = "2025-01"
DEFAULT_LANGUAGE = "en"
# Refresh the token this many seconds before WHO says it expires.
TOKEN_EXPIRY_SKEW = 60.0
# Parent/child entities are resolved one request each; keep the fan-out polite.
_FETCH_CONCURRENCY = 4

_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_ID_RE = re.compile(r"/(?:mms|entity)/(\d+)(?:/(other|unspecified))?(?:[/?#]|$)")
_CURIE_RE = re.compile(r"^(?:ICD-?11(?:MMS)?|ICD11)\s*:\s*", re.IGNORECASE)


def _strip_markup(text: str) -> str:
    """Remove the ``<em class='found'>`` highlighting WHO puts into search titles."""
    return _TAG_RE.sub("", text or "").strip()


def _lang_text(value: Any) -> str:
    """Return the string of a JSON-LD ``{"@language": ..., "@value": ...}`` object."""
    if isinstance(value, dict):
        return str(value.get("@value") or "").strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _terms(value: Any) -> list[str]:
    """Labels of a list of ICD ``Term`` objects (inclusions, index terms, ...)."""
    out: list[str] = []
    if not isinstance(value, list):
        return out
    for term in value:
        if not isinstance(term, dict) or term.get("deprecated"):
            continue
        label = _lang_text(term.get("label"))
        if label:
            out.append(label)
    return out


def _entity_ref(uri: str) -> tuple[str, str | None] | None:
    """Extract ``(numeric id, residual)`` from an entity or MMS URI; ``None`` if absent."""
    match = _ENTITY_ID_RE.search(uri or "")
    if not match:
        return None
    return match.group(1), match.group(2)


class ICD11Adapter(KnowledgeSourceAdapter):
    """Adapter for the WHO ICD-11 MMS linearization (ICD-API v2)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        # code/entity id -> parsed entity JSON, so relationship expansion does not
        # re-fetch the same parent for every child.
        self._entity_cache: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def custom_base(self) -> str | None:
        """``ICD11_API_BASE`` (self-hosted container) without trailing slash, if set."""
        base = (os.getenv("ICD11_API_BASE") or "").strip().rstrip("/")
        return base or None

    @property
    def base_url(self) -> str:
        return self.custom_base or ICD11_API_BASE

    @property
    def release(self) -> str:
        return (os.getenv("ICD11_RELEASE") or DEFAULT_RELEASE).strip()

    @property
    def language(self) -> str:
        return (os.getenv("ICD11_LANGUAGE") or DEFAULT_LANGUAGE).strip()

    def _credentials(self) -> tuple[str | None, str | None]:
        client_id = self.config.get_api_key("icd11_client_id") or os.getenv("ICD11_CLIENT_ID")
        secret = self.config.get_api_key("icd11_client_secret") or os.getenv("ICD11_CLIENT_SECRET")
        return client_id, secret

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ICD11

    def is_available(self) -> bool:
        if self.custom_base:
            return True  # WHO's self-hosted container needs no token
        client_id, secret = self._credentials()
        return bool(client_id and secret)

    # ------------------------------------------------------------------
    # OAuth2 token handling
    # ------------------------------------------------------------------

    async def _request_token(self) -> dict[str, Any]:
        """POST the client-credentials grant and return WHO's token JSON.

        ``_make_request`` only speaks JSON, but the token endpoint wants a form body,
        so this goes through the shared session directly (still with retry/breaker).
        """
        client_id, secret = self._credentials()
        form = {
            "grant_type": "client_credentials",
            "client_id": client_id or "",
            "client_secret": secret or "",
            "scope": ICD11_SCOPE,
        }

        async def _do() -> dict[str, Any]:
            session = await self._get_session()
            async with session.post(ICD11_TOKEN_URL, data=form) as response:
                response.raise_for_status()
                return await response.json()

        return await self._call_with_retry("icd11_token", _do)

    async def _get_token(self, force_refresh: bool = False) -> str | None:
        """Return a valid bearer token, fetching a new one when needed.

        The lock makes concurrent searches share a single token request. ``None`` when
        no credentials are configured or the token request fails.
        """
        async with self._token_lock:
            fresh = self._token and time.monotonic() < self._token_expires_at
            if fresh and not force_refresh:
                return self._token
            try:
                payload = await self._request_token()
                token = payload.get("access_token") if isinstance(payload, dict) else None
                if not token:
                    logger.error("ICD-11 token response had no access_token")
                    self._token = None
                    return None
                expires_in = float(payload.get("expires_in") or 3600)
                self._token = str(token)
                self._token_expires_at = time.monotonic() + max(expires_in - TOKEN_EXPIRY_SKEW, 0)
                return self._token
            except Exception as e:
                logger.error(f"ICD-11 token request failed: {e}")
                self._token = None
                return None

    def _headers(self, token: str | None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Accept-Language": self.language,
            "API-Version": "v2",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``url`` with auth; on a 401 refresh the token once and retry.

        Raises on any failure; callers turn that into ``[]`` / ``None``.
        """
        token: str | None = None
        if not self.custom_base:
            token = await self._get_token()
            if token is None:
                raise RuntimeError("ICD-11 access token unavailable (check credentials)")
        try:
            return await self._make_request(url, params, self._headers(token))
        except Exception as exc:
            if getattr(exc, "status", None) != 401 or self.custom_base:
                raise
            logger.warning("ICD-11 API answered 401; refreshing the access token")
            token = await self._get_token(force_refresh=True)
            if token is None:
                raise
            return await self._make_request(url, params, self._headers(token))

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    def _mms_url(self, tail: str) -> str:
        return f"{self.base_url}/icd/release/11/{self.release}/mms/{tail}"

    @staticmethod
    def _normalise_id(concept_id: str) -> tuple[str, str] | None:
        """Classify ``concept_id`` as ``("entity", "<id>[/residual]")`` or ``("code", X)``.

        Accepts a bare code (``8E49``), ``ICD11:8E49``, a numeric entity id, or a full
        WHO URI. Post-coordination suffixes (``/`` or ``&``) are dropped.
        """
        cid = _CURIE_RE.sub("", (concept_id or "").strip())
        if not cid:
            return None
        if "id.who.int" in cid or cid.startswith(("http://", "https://")):
            ref = _entity_ref(cid)
            if not ref:
                return None
            return "entity", ref[0] + (f"/{ref[1]}" if ref[1] else "")
        if cid.isdigit() and len(cid) >= 5:
            return "entity", cid
        code = re.split(r"[/&]", cid)[0].strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{2,6}(?:\.[0-9A-Z]{1,3})?", code):
            return None
        return "code", code

    async def _resolve_entity_path(self, concept_id: str) -> str | None:
        """Return the ``{id}[/{residual}]`` path segment for any accepted identifier."""
        normalised = self._normalise_id(concept_id)
        if normalised is None:
            return None
        kind, value = normalised
        if kind == "entity":
            return value
        data = await self._get(self._mms_url(f"codeinfo/{value}"))
        ref = _entity_ref(str(data.get("stemId") or ""))
        if not ref:
            return None
        return ref[0] + (f"/{ref[1]}" if ref[1] else "")

    async def _fetch_entity(self, path: str) -> dict[str, Any] | None:
        cached = self._entity_cache.get(path)
        if cached is not None:
            return cached
        data = await self._get(self._mms_url(path))
        if not isinstance(data, dict) or not data:
            return None
        self._entity_cache[path] = data
        return data

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search the MMS linearization (flexisearch, flat result list)."""
        query = (query or "").strip()
        if not query or limit <= 0:
            return []
        try:
            params = {
                "q": query,
                "useFlexisearch": "true",
                "flatResults": "true",
                "highlightingEnabled": "false",
            }
            data = await self._get(self._mms_url("search"), params)
            if not isinstance(data, dict):
                return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in data.get("destinationEntities") or []:
                concept = self._convert_search_item(item)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"ICD-11 search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"ICD-11 search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Fetch one MMS entity by code, numeric entity id or WHO URI."""
        try:
            path = await self._resolve_entity_path(concept_id)
            if not path:
                return None
            entity = await self._fetch_entity(path)
            if not entity:
                return None
            return self._convert_entity(entity, path)
        except Exception as e:
            logger.error(f"ICD-11 get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Return ``is_a`` (parents) and ``has_subtype`` (children) edges.

        The entity page lists parents/children only as URIs, so each related entity is
        fetched once (4 at a time) to get its code and title; children are capped at
        ``limit``. Foundation-only multi-parenting is not followed: this is the
        single-parent MMS tree.
        """
        try:
            path = await self._resolve_entity_path(concept_id)
            if not path:
                return []
            entity = await self._fetch_entity(path)
            if not entity:
                return []
            parents = [str(u) for u in entity.get("parent") or []]
            children = [str(u) for u in entity.get("child") or []][: max(limit, 0)]
            semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

            async def resolve(uri: str) -> dict[str, Any] | None:
                ref = _entity_ref(uri)
                if not ref:
                    return None
                rel_path = ref[0] + (f"/{ref[1]}" if ref[1] else "")
                async with semaphore:
                    try:
                        return await self._fetch_entity(rel_path)
                    except Exception as e:
                        logger.debug(f"ICD-11 related entity {rel_path} failed: {e}")
                        return None

            labelled = [("is_a", u) for u in parents] + [("has_subtype", u) for u in children]
            fetched = await asyncio.gather(*(resolve(u) for _, u in labelled))

            relationships: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for (label, uri), related in zip(labelled, fetched, strict=True):
                ref = _entity_ref(uri)
                if related is None and ref is None:
                    continue
                related = related or {}
                related_id = str(related.get("code") or (ref[0] if ref else ""))
                if not related_id or (label, related_id) in seen:
                    continue
                seen.add((label, related_id))
                relationships.append(
                    {
                        "relation_label": label,
                        "related_id": related_id,
                        "related_name": _lang_text(related.get("title")) or related_id,
                        "source": "ICD11",
                    }
                )
            return relationships
        except Exception as e:
            logger.error(f"ICD-11 get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the link from the MMS code to its ICD-11 Foundation entity URI.

        The API exposes no ICD-10 crosswalk, so the Foundation URI (``source`` field of
        the linearization entity) is the only cross-reference available.
        """
        try:
            path = await self._resolve_entity_path(concept_id)
            if not path:
                return []
            entity = await self._fetch_entity(path)
            foundation = str((entity or {}).get("source") or "").strip()
            if not foundation:
                return []
            code = str((entity or {}).get("code") or path)
            return [
                {
                    "fromId": code,
                    "toId": foundation,
                    "fromSource": "ICD11",
                    "toSource": "ICD11",
                    "mappingType": "foundation_uri",
                    "confidence": 1.0,
                }
            ]
        except Exception as e:
            logger.warning(f"ICD-11 get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _concept_type(code: str, class_kind: str = "") -> ConceptType:
        if code[:1] == "X":
            return ConceptType.UNKNOWN  # extension codes (severity, laterality, ...)
        if len(code) >= 2 and code[0] == "M" and code[1] in "ABCDEFGH":
            return ConceptType.SYMPTOM  # chapter 21: symptoms, signs, clinical findings
        return ConceptType.DISEASE

    def _convert_search_item(self, item: dict[str, Any]) -> UnifiedConcept | None:
        if not isinstance(item, dict):
            return None
        title = _strip_markup(str(item.get("title") or ""))
        code = str(item.get("theCode") or "").strip()
        ref = _entity_ref(str(item.get("stemId") or item.get("id") or ""))
        primary = code or (ref[0] if ref else "")
        if not primary or not title:
            return None
        concept = self._create_concept(primary, title, self._concept_type(code))
        if item.get("chapter") and concept.categories is not None:
            concept.categories.append(f"chapter:{item['chapter']}")
        score = item.get("score")
        concept.confidence_score = (
            min(float(score), 1.0) if isinstance(score, int | float) else 0.8
        )
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.ICD11] = item
        return concept

    def _convert_entity(self, entity: dict[str, Any], path: str) -> UnifiedConcept | None:
        title = _lang_text(entity.get("title"))
        code = str(entity.get("code") or "").strip()
        primary = code or path.split("/")[0]
        if not title:
            return None
        concept = self._create_concept(primary, title, self._concept_type(code))

        definitions = [
            d
            for d in (
                _lang_text(entity.get("definition")),
                _lang_text(entity.get("longDefinition")),
            )
            if d
        ]
        concept.definitions = list(dict.fromkeys(definitions))

        synonyms: list[str] = []
        for label in _terms(entity.get("indexTerm")) + _terms(entity.get("inclusion")):
            if label != title and label not in synonyms:
                synonyms.append(label)
        concept.synonyms = synonyms

        class_kind = str(entity.get("classKind") or "")
        if class_kind and concept.semantic_types is not None:
            concept.semantic_types.append(class_kind)
        fully_specified = _lang_text(entity.get("fullySpecifiedName"))
        if fully_specified and concept.categories is not None:
            concept.categories.append(f"fullySpecifiedName:{fully_specified}")

        concept.parents = [r[0] for u in entity.get("parent") or [] if (r := _entity_ref(str(u)))]
        concept.children = [r[0] for u in entity.get("child") or [] if (r := _entity_ref(str(u)))]
        concept.confidence_score = 1.0
        concept.labels = json.dumps({self.language: title})
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.ICD11] = entity
        return concept
