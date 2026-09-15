"""
MCP server for biomedical knowledge lookup.

Exposes :class:`~knowledge_lookup.core.central_lookup.CentralKnowledgeLookup` to
LLM agents through five read-only tools, two resources and two prompts, built on
the official ``mcp`` SDK (2.x ``MCPServer``).

Design notes:

* Tools are annotated read-only. A source that fails or times out is reported
  inside the result (``source_errors``) instead of failing the whole call;
  anticipated problems raise :class:`ToolError` with a message saying what to do
  next. Anything else is masked by the SDK and logged with its traceback.
* Every tool returns a pydantic model, so clients get an ``outputSchema`` and
  ``structuredContent``. ``response_format``, pagination and
  :data:`CHARACTER_LIMIT` keep results small enough for a model's context.
* Importing the library and initialising 36 adapters takes seconds, so the
  lookup is built in a worker thread as the server starts and awaited by the
  first tool call rather than blocking the protocol handshake.
* stdout belongs to the stdio transport: logging goes to stderr.
"""

import argparse
import asyncio
import logging
import os
import re
import sys
import textwrap
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.types import ToolAnnotations
from pydantic import BeforeValidator, Field

from .. import __version__
from ..core.central_lookup import CentralKnowledgeLookup
from ..core.term_expansion import expand_and_search
from ..curie_utils.normalization import get_converter
from ..models import ConceptType, KnowledgeSource, LookupConfig
from .isolation import isolate_blocking_adapters
from .schemas import (
    Concept,
    ConceptDetail,
    CrossReference,
    CurieValidation,
    MappingsResponse,
    ResponseFormat,
    SearchResponse,
    SourceInfo,
    SourcesResponse,
    display_id,
)
from .sources import (
    DEFAULT_SEARCH_SOURCES,
    SOURCE_CATALOG,
    SourceName,
    normalize_source_name,
    parse_source_names,
    route_identifier,
)

logger = logging.getLogger(__name__)

SERVER_NAME = "biomedical-knowledge-lookup"

#: Upper bound on a serialized tool result. Claude Code warns above ~10k tokens,
#: so pages are trimmed (with a note on how to fetch the rest) past this size.
CHARACTER_LIMIT = 25_000

_PER_SOURCE_DEPTH = 5
_SEARCH_CACHE_SIZE = 128
_SEARCH_CACHE_TTL_SECONDS = 600.0
_EXPANSION_ROUNDS = 2
_EXPANSION_TERMS_PER_ROUND = 5

SERVER_INSTRUCTIONS = """\
Look up biomedical concepts (diseases, phenotypes, genes, proteins, chemicals, pathways, \
biological processes) across 36 ontologies and databases.

Typical workflow:
1. biomed_search_concepts: free-text term -> ranked candidate identifiers.
2. biomed_get_concept: full record (definitions, synonyms, xrefs, hierarchy) for one identifier.
3. biomed_find_mappings: cross-walk an identifier to other vocabularies (MeSH, NCIT, DOID, UMLS, ...).
biomed_validate_curie checks and normalizes an identifier offline; biomed_list_sources shows \
which sources are available (UMLS, BioPortal, DisGeNET and OMIM need API keys).

Tips: name `sources` for faster, more precise searches (HPO for phenotypes, MONDO for diseases, \
HGNC/UNIPROT for genes and proteins, PUBCHEM/CHEMBL for chemicals, REACTOME for pathways). \
Scores are source-reported and not comparable across sources. Identifiers are CURIEs \
(PREFIX:LOCAL_ID, e.g. HP:0001250) unless a source uses bare accessions (P38398, C0011849).\
"""

_READ_ONLY_REMOTE = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)
_READ_ONLY_LOCAL = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


def _normalize_enum_name(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper().replace("-", "_").replace(" ", "_")
    return value


_Source = Annotated[SourceName, BeforeValidator(normalize_source_name)]
_ConceptTypeName = Annotated[ConceptType, BeforeValidator(_normalize_enum_name)]


# ---------------------------------------------------------------------------
# Configuration and shared state
# ---------------------------------------------------------------------------


@dataclass
class ServerSettings:
    """Runtime configuration. :meth:`from_env` reads ``KNOWLEDGE_LOOKUP_MCP_*`` variables."""

    #: Sources searched when a tool call names none (unavailable ones are skipped).
    default_sources: list[KnowledgeSource] = field(
        default_factory=lambda: list(DEFAULT_SEARCH_SOURCES)
    )
    #: Adapters to initialise; ``None`` initialises every available adapter.
    enabled_sources: list[KnowledgeSource] | None = None
    #: Per-source timeout in seconds for every upstream call.
    timeout_per_source: float = 15.0
    #: Record term-expansion trails in the durable ExpansionStore (off: tools stay side-effect free).
    persist_expansions: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ServerSettings":
        env = os.environ if environ is None else environ
        settings = cls()
        if raw := env.get("KNOWLEDGE_LOOKUP_MCP_DEFAULT_SOURCES"):
            settings.default_sources = parse_source_names(raw)
        if raw := env.get("KNOWLEDGE_LOOKUP_MCP_ENABLED_SOURCES"):
            settings.enabled_sources = parse_source_names(raw)
        if raw := env.get("KNOWLEDGE_LOOKUP_MCP_TIMEOUT"):
            settings.timeout_per_source = float(raw)
        if raw := env.get("KNOWLEDGE_LOOKUP_MCP_PERSIST_EXPANSIONS"):
            settings.persist_expansions = raw.strip().lower() in {"1", "true", "yes", "on"}
        return settings


LookupFactory = Callable[[ServerSettings], CentralKnowledgeLookup]


def _build_lookup(settings: ServerSettings) -> CentralKnowledgeLookup:
    config = LookupConfig(
        timeout_per_source=settings.timeout_per_source,
        enabled_sources=settings.enabled_sources,
    )
    lookup = CentralKnowledgeLookup(config)
    isolate_blocking_adapters(lookup)
    return lookup


@dataclass
class _CachedSearch:
    concepts: list[Any]
    errors: dict[str, str]
    expanded_terms: list[str]
    depth: int

    @property
    def exhausted(self) -> bool:
        """True when the upstream search returned fewer hits than it was allowed to."""
        return len(self.concepts) < self.depth


class _SearchCache:
    """Small TTL/LRU cache so paging through one query reuses a single upstream search."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[tuple, tuple[float, _CachedSearch]] = OrderedDict()

    def get(self, key: tuple) -> _CachedSearch | None:
        item = self._data.get(key)
        if item is None:
            return None
        stored_at, value = item
        if time.monotonic() - stored_at > self._ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: tuple, value: _CachedSearch) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


class AppState:
    """Process-wide state: the lazily built lookup plus the search cache."""

    def __init__(self, settings: ServerSettings, lookup_factory: LookupFactory) -> None:
        self.settings = settings
        self._factory = lookup_factory
        self._lookup: CentralKnowledgeLookup | None = None
        self._init_task: asyncio.Task[CentralKnowledgeLookup] | None = None
        self.search_cache = _SearchCache(_SEARCH_CACHE_SIZE, _SEARCH_CACHE_TTL_SECONDS)

    def start(self) -> None:
        """Start building the lookup in a worker thread (idempotent)."""
        if self._lookup is None and self._init_task is None:
            self._init_task = asyncio.create_task(asyncio.to_thread(self._factory, self.settings))

    async def lookup(self) -> CentralKnowledgeLookup:
        if self._lookup is not None:
            return self._lookup
        self.start()
        assert self._init_task is not None
        try:
            # shield: a cancelled tool call must not cancel the shared initialisation
            self._lookup = await asyncio.shield(self._init_task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._init_task = None
            logger.exception("Knowledge lookup initialisation failed")
            raise ToolError(
                f"The knowledge lookup backend failed to start ({exc}). "
                "Check the server logs; the next call will retry."
            ) from exc
        return self._lookup

    async def aclose(self) -> None:
        task, self._init_task = self._init_task, None
        lookup, self._lookup = self._lookup, None
        if lookup is None and task is not None:
            try:
                lookup = await task
            except Exception:  # noqa: BLE001 - nothing to close if it never started
                lookup = None
        if lookup is not None:
            await lookup.close()
        self.search_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unavailable_reason(source: KnowledgeSource) -> str:
    spec = SOURCE_CATALOG.get(source)
    if spec is not None and spec.requires:
        return f"requires {spec.requires}"
    return "failed to initialise (see server logs)"


def _resolve_search_sources(
    state: AppState, lookup: CentralKnowledgeLookup, requested: Sequence[str] | None
) -> tuple[list[KnowledgeSource], list[str]]:
    available = lookup.adapters
    warnings: list[str] = []

    if requested:
        wanted = [KnowledgeSource(name) for name in dict.fromkeys(requested)]
        sources = [s for s in wanted if s in available]
        skipped = [s for s in wanted if s not in available]
        if skipped:
            details = "; ".join(f"{s.value} {_unavailable_reason(s)}" for s in skipped)
            if not sources:
                raise ToolError(
                    f"None of the requested sources are available ({details}). "
                    f"Available sources: {', '.join(sorted(s.value for s in available))}."
                )
            warnings.append(f"Skipped unavailable sources: {details}.")
        return sources, warnings

    sources = [s for s in state.settings.default_sources if s in available]
    if not sources:
        sources = sorted(available, key=lambda s: s.value)
    if not sources:
        raise ToolError(
            "No knowledge sources are available. Check the server logs and API keys "
            "(biomed_list_sources shows what each source needs)."
        )
    return sources, warnings


def _serialized_size(response: SearchResponse) -> int:
    # the SDK mirrors structured output as indented JSON text, so measure that
    return len(response.model_dump_json(indent=2))


def _fit_to_character_limit(response: SearchResponse) -> SearchResponse:
    if _serialized_size(response) <= CHARACTER_LIMIT:
        return response
    original = response.count
    while len(response.concepts) > 1 and _serialized_size(response) > CHARACTER_LIMIT:
        response.concepts.pop()
    response.count = len(response.concepts)
    response.has_more = True
    response.next_offset = response.offset + response.count
    response.warnings.append(
        f"Truncated from {original} to {response.count} concepts to stay under "
        f"{CHARACTER_LIMIT:,} characters. Fetch the rest with offset={response.next_offset}, "
        "or use response_format='concise' or a smaller limit."
    )
    return response


async def _report(ctx: Context | None, progress: float, message: str) -> None:
    if ctx is not None:
        await ctx.report_progress(progress, 1.0, message)


async def _resolve_concept(
    state: AppState,
    lookup: CentralKnowledgeLookup,
    concept_id: str,
    source: KnowledgeSource | None,
    ctx: Context | None,
) -> tuple[Any, str] | None:
    """Resolve *concept_id* to ``(UnifiedConcept, resolving source)`` or ``None``."""
    timeout = state.settings.timeout_per_source

    if source is not None:
        if source not in lookup.adapters:
            raise ToolError(
                f"Source {source.value} is not available: {_unavailable_reason(source)}. "
                "Omit `source` to route the identifier automatically."
            )
        candidates = [(source, concept_id)]
        prefix, _, local = concept_id.partition(":")
        if local and "://" not in concept_id:
            candidates.append((source, local))
    else:
        candidates = [(s, i) for s, i in route_identifier(concept_id) if s in lookup.adapters]

    async def attempt(src: KnowledgeSource, ident: str) -> Any:
        try:
            return await asyncio.wait_for(
                lookup.adapters[src].get_concept_details(ident), timeout=timeout
            )
        except Exception as exc:  # noqa: BLE001 - one failed route must not sink the others
            logger.debug("get_concept_details(%s) via %s failed: %s", ident, src.value, exc)
            return None

    if candidates:
        results = await asyncio.gather(*(attempt(s, i) for s, i in candidates))
        for (src, _), concept in zip(candidates, results, strict=True):
            if concept is not None:
                return concept, src.value

    # No route, or the routed sources did not know the ID: search OLS (which indexes
    # OBO IDs across 250+ ontologies) for the ID itself and accept only an exact
    # match. Deliberately not the library's ask-every-adapter fallback: adapters
    # wrapping synchronous clients block the event loop for minutes on unknown IDs,
    # which would stall the whole server.
    if source is None and KnowledgeSource.OLS in lookup.adapters:
        await _report(ctx, 0.5, "No direct route for this identifier; searching OLS for it")
        try:
            result = await asyncio.wait_for(
                lookup.search_concepts(concept_id, sources=[KnowledgeSource.OLS], max_results=10),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort fallback
            logger.debug("OLS identifier search for %s failed: %s", concept_id, exc)
            return None
        wanted = display_id(concept_id).lower()
        for concept in result.concepts or []:
            # OLS reports some terms by IRI, listing the short form among identifiers
            known_ids = [concept.primary_id or ""] + [
                getattr(ident, "identifier", None) or "" for ident in concept.identifiers or []
            ]
            if any(display_id(known).lower() == wanted for known in known_ids):
                return concept, KnowledgeSource.OLS.value
    return None


@lru_cache(maxsize=1)
def _bioregistry_converter() -> Any:
    return get_converter()


def _validate_identifier(identifier: str) -> CurieValidation:
    text = identifier.strip()
    converter = _bioregistry_converter()

    def routed(curie: str) -> str | None:
        routes = route_identifier(curie)
        return routes[0][0].value if routes else None

    if converter is None:
        prefix, sep, local = text.partition(":")
        return CurieValidation(
            input=identifier,
            valid=False,
            prefix=prefix if sep else None,
            local_id=local or None,
            resolvable_via=routed(text),
            message=(
                "Bioregistry validation is unavailable; install the 'curie' extra "
                "(pip install 'biomedical-knowledge-lookup[curie]'). Only routing is reported."
            ),
        )

    is_uri = "://" in text
    if not is_uri and ":" not in text:
        return CurieValidation(
            input=identifier,
            valid=False,
            resolvable_via=routed(text),
            message=(
                "Not a CURIE: expected PREFIX:LOCAL_ID (e.g. HP:0001250) or an IRI. "
                + (
                    "It looks like a bare accession, which biomed_get_concept can still resolve."
                    if routed(text)
                    else ""
                )
            ).strip(),
        )

    try:
        curie = converter.compress(text) if is_uri else converter.standardize_curie(text)
    except Exception:  # noqa: BLE001 - malformed input is a validation result, not a crash
        curie = None
    if not curie:
        unknown = text if is_uri else text.partition(":")[0]
        return CurieValidation(
            input=identifier,
            valid=False,
            message=(
                f"Unrecognized {'IRI namespace' if is_uri else 'prefix'} '{unknown}': it is not "
                "registered in Bioregistry. Check the spelling (common prefixes: HP, MONDO, GO, "
                "DOID, MESH, NCIT, CHEBI, UniProtKB, HGNC, UMLS)."
            ),
        )

    prefix, _, local = curie.partition(":")
    record = converter.get_record(prefix)
    pattern = getattr(record, "pattern", None) or None
    matches = bool(re.fullmatch(pattern, local)) if pattern else True
    preferred, example = prefix.upper(), None
    try:
        import bioregistry

        preferred = bioregistry.get_preferred_prefix(prefix) or preferred
        example = bioregistry.get_example(prefix)
    except Exception:  # noqa: BLE001 - cosmetic only
        pass
    display = f"{preferred}:{local}"

    message = None
    if not matches:
        message = f"Local ID '{local}' does not match the {preferred} pattern {pattern}" + (
            f" (example: {preferred}:{example})." if example else "."
        )
    return CurieValidation(
        input=identifier,
        valid=matches,
        curie=display,
        prefix=preferred,
        local_id=local,
        uri=converter.expand(curie),
        pattern=pattern,
        resolvable_via=routed(display),
        message=message,
    )


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_server(
    settings: ServerSettings | None = None,
    lookup_factory: LookupFactory | None = None,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING",
) -> MCPServer:
    """Build the MCP server.

    Args:
        settings: Runtime configuration; defaults to :meth:`ServerSettings.from_env`.
        lookup_factory: Builds the :class:`CentralKnowledgeLookup` (in a worker
            thread). Injected by tests; defaults to one configured from *settings*.
        log_level: Passed to the SDK, which configures stderr logging with it when
            logging is not configured yet (and to uvicorn for HTTP transports).
    """
    state = AppState(settings or ServerSettings.from_env(), lookup_factory or _build_lookup)

    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[AppState]:
        state.start()
        try:
            yield state
        finally:
            await state.aclose()

    server = MCPServer(
        name=SERVER_NAME,
        title="Biomedical Knowledge Lookup",
        description="Search and resolve biomedical concepts across 36 ontologies and databases.",
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
        website_url="https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup",
        lifespan=lifespan,
        log_level=log_level,
    )

    # -- tools ----------------------------------------------------------------

    @server.tool(
        name="biomed_search_concepts",
        title="Search biomedical concepts",
        annotations=_READ_ONLY_REMOTE,
    )
    async def search_concepts(
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=500,
                description="Free-text term, symbol or phrase, e.g. 'type 2 diabetes', 'BRCA1'.",
            ),
        ],
        ctx: Context,
        sources: Annotated[
            list[_Source] | None,
            Field(
                description=(
                    "Sources to search, e.g. ['HPO', 'MONDO']. Omit for the default set "
                    "(see biomed_list_sources)."
                ),
            ),
        ] = None,
        concept_types: Annotated[
            list[_ConceptTypeName] | None,
            Field(
                description=(
                    "Keep only these concept types, e.g. ['DISEASE'] or ['GENE', 'PROTEIN']. "
                    "Concepts a source leaves unclassified (UNKNOWN) are kept."
                ),
            ),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Page size.")] = 10,
        offset: Annotated[
            int, Field(ge=0, le=500, description="Results to skip; use next_offset to page.")
        ] = 0,
        expand_synonyms: Annotated[
            bool,
            Field(
                description=(
                    "Also search synonyms and long forms discovered in the first results. "
                    "Helps with abbreviations and colloquial terms; slower."
                ),
            ),
        ] = False,
        response_format: Annotated[
            ResponseFormat,
            Field(
                description=(
                    "'concise': id, label, type, sources, score, first definition, a few "
                    "synonyms. 'detailed': adds all definitions, xrefs, semantic types, hierarchy."
                ),
            ),
        ] = "concise",
    ) -> SearchResponse:
        """Search biomedical ontologies and databases for concepts matching a free-text term.

        Use this first to turn a name, symbol or phrase into identifiers, e.g. 'type 2 diabetes'
        -> MONDO:0005148, 'seizure' -> HP:0001250, 'BRCA1' -> HGNC:1100 / P38398. Results from
        all searched sources are merged, de-duplicated by label and ranked by score.

        Name `sources` for faster, more precise results: HPO for phenotypes and symptoms, MONDO
        for diseases, HGNC/UNIPROT/ENSEMBL for genes and proteins, PUBCHEM/CHEMBL for chemicals
        and drugs, REACTOME for pathways, GENEONTOLOGY for biological processes, UMLS/BIOPORTAL
        for clinical terminologies such as SNOMED CT, MeSH and ICD (these need API keys).

        Returns one page; pass next_offset as offset for more. Sources that fail are listed in
        source_errors while results from the rest are still returned. For the full record of a
        single hit, call biomed_get_concept instead of requesting 'detailed' for every hit.
        """
        lookup = await state.lookup()
        search_sources, warnings = _resolve_search_sources(state, lookup, sources)
        types = list(concept_types) if concept_types else None
        normalized_query = " ".join(query.split())
        key = (
            normalized_query.lower(),
            tuple(s.value for s in search_sources),
            tuple(sorted(t.value for t in types or [])),
            expand_synonyms,
        )

        cached = state.search_cache.get(key)
        if cached is None or (not cached.exhausted and cached.depth < offset + limit):
            depth = max(offset + limit, _PER_SOURCE_DEPTH * len(search_sources))
            await _report(ctx, 0.0, f"Searching {len(search_sources)} source(s)")
            expanded_terms: list[str] = []
            if expand_synonyms:
                result, trace = await expand_and_search(
                    lookup,
                    normalized_query,
                    concept_types=types,
                    sources=search_sources,
                    max_results=depth,
                    max_rounds=_EXPANSION_ROUNDS,
                    max_terms_per_round=_EXPANSION_TERMS_PER_ROUND,
                    persist=state.settings.persist_expansions,
                )
                expanded_terms = [
                    t for t in trace.all_terms_tried if t.lower() != normalized_query.lower()
                ]
            else:
                result = await lookup.search_concepts(
                    normalized_query,
                    concept_types=types,
                    sources=search_sources,
                    max_results=depth,
                )
            concepts = sorted(
                result.concepts or [], key=lambda c: c.confidence_score or 0.0, reverse=True
            )
            # LookupResult keeps errors in a dict side-channel (the generated field is a str)
            raw_errors: dict = result.errors if isinstance(result.errors, dict) else {}
            cached = _CachedSearch(
                concepts=concepts,
                errors={str(k): " ".join(str(v).split())[:300] for k, v in raw_errors.items()},
                expanded_terms=expanded_terms,
                depth=depth,
            )
            if concepts:  # never cache a search that found nothing (it may be an outage)
                state.search_cache.set(key, cached)
            await _report(ctx, 1.0, f"Found {len(concepts)} concept(s)")

        total = len(cached.concepts)
        page = cached.concepts[offset : offset + limit]
        end = offset + len(page)
        has_more = end < total or (not cached.exhausted and bool(page))
        if total == 0:
            warnings.append(
                "No concepts matched. Try a synonym or broader term, set expand_synonyms=true, "
                "or search other sources (biomed_list_sources)."
            )
        elif not page:
            warnings.append(f"offset {offset} is past the last result ({total} found).")

        response = SearchResponse(
            query=normalized_query,
            total=total,
            count=len(page),
            offset=offset,
            has_more=has_more,
            next_offset=end if has_more else None,
            concepts=[Concept.from_unified(c, response_format) for c in page],
            sources_searched=[s.value for s in search_sources],
            source_errors=cached.errors,
            expanded_terms=cached.expanded_terms,
            warnings=warnings,
        )
        return _fit_to_character_limit(response)

    @server.tool(
        name="biomed_get_concept",
        title="Get concept details",
        annotations=_READ_ONLY_REMOTE,
    )
    async def get_concept(
        concept_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=300,
                description=(
                    "CURIE ('HP:0001250', 'MONDO:0005148', 'GO:0006915', 'HGNC:1100'), bare "
                    "accession ('P38398', 'C0011849', 'R-HSA-1640170', 'CHEMBL25') or ontology IRI."
                ),
            ),
        ],
        ctx: Context,
        source: Annotated[
            _Source | None,
            Field(description="Force one source; omit to route by identifier (recommended)."),
        ] = None,
        response_format: Annotated[
            ResponseFormat,
            Field(description="'detailed' (default) or 'concise' for just the essentials."),
        ] = "detailed",
    ) -> ConceptDetail:
        """Get the full record for one concept identifier.

        Returns label, type, definitions, synonyms, semantic types, cross-references to other
        sources and parent/child identifiers. Accepts CURIEs ('HP:0001250', 'MONDO:0005148',
        'DOID:9351', 'CHEBI:15365'), bare accessions ('P38398' UniProt, 'C0011849' UMLS,
        'R-HSA-1640170' Reactome, 'DB00945' DrugBank, 'Q12136' Wikidata) and ontology IRIs.
        The identifier is routed to the source that owns it. If you only have a name, call
        biomed_search_concepts first.
        """
        concept_id = concept_id.strip()
        lookup = await state.lookup()
        forced = KnowledgeSource(source) if source else None
        resolved = await _resolve_concept(state, lookup, concept_id, forced, ctx)
        if resolved is None:
            where = f" in {forced.value}" if forced else ""
            raise ToolError(
                f"No concept found for '{concept_id}'{where}. Check the identifier with "
                "biomed_validate_curie (expected e.g. HP:0001250, MONDO:0005148, P38398), "
                "or find the right one with biomed_search_concepts."
            )
        concept, via = resolved
        return ConceptDetail.from_unified(concept, response_format, resolved_via=via)

    @server.tool(
        name="biomed_find_mappings",
        title="Find cross-vocabulary mappings",
        annotations=_READ_ONLY_REMOTE,
    )
    async def find_mappings(
        concept_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=300,
                description="CURIE to map, e.g. 'MONDO:0005148', 'HP:0001250', 'DOID:9351'.",
            ),
        ],
        ctx: Context,
        target_prefixes: Annotated[
            list[str] | None,
            Field(
                description="Keep only mappings to these vocabularies, e.g. ['MESH', 'NCIT', 'UMLS'].",
            ),
        ] = None,
        distance: Annotated[
            int,
            Field(
                ge=1,
                le=3,
                description=(
                    "OxO mapping hops. 1 = direct cross-references (most precise); 2-3 follow "
                    "mapping chains and add broader, less reliable matches."
                ),
            ),
        ] = 1,
        limit: Annotated[int, Field(ge=1, le=200, description="Maximum mappings returned.")] = 50,
    ) -> MappingsResponse:
        """Cross-walk a concept identifier to equivalent identifiers in other vocabularies.

        Combines the concept's own cross-references with the EBI OxO mapping service to find
        the same concept in MeSH, NCIT, DOID, UMLS, SNOMED CT, ICD, OMIM, Orphanet, EFO and
        more. Each mapping reports its source vocabulary and, for OxO results, its distance.
        """
        concept_id = concept_id.strip()
        lookup = await state.lookup()
        warnings: list[str] = []
        timeout = state.settings.timeout_per_source

        await _report(ctx, 0.0, "Resolving concept")
        resolved = await _resolve_concept(state, lookup, concept_id, None, ctx)

        mappings: list[CrossReference] = []
        seen = {concept_id.lower()}
        label = None

        def add(ref: CrossReference) -> None:
            if ref.id and ref.id.lower() not in seen:
                seen.add(ref.id.lower())
                mappings.append(ref)

        if resolved is not None:
            concept, _ = resolved
            label = concept.primary_label
            seen.add((concept.primary_id or "").lower())
            for ident in concept.identifiers or []:
                add(
                    CrossReference(
                        id=(getattr(ident, "identifier", None) or "").strip(),
                        source=str(getattr(ident.source, "value", ident.source)),
                        label=getattr(ident, "label", None) or None,
                    )
                )

        oxo = lookup.adapters.get(KnowledgeSource.OXO)
        if oxo is None or not hasattr(oxo, "get_mappings_for_concepts"):
            warnings.append(
                "OxO is unavailable, so only cross-references attached to the concept are listed."
            )
        else:
            await _report(ctx, 0.5, "Querying OxO mappings")
            try:
                by_id = await asyncio.wait_for(
                    oxo.get_mappings_for_concepts([concept_id], distance=distance),
                    timeout=timeout,
                )
            except Exception as exc:  # noqa: BLE001 - degrade to the concept's own xrefs
                warnings.append(f"OxO mapping lookup failed ({exc}); results may be incomplete.")
                by_id = {}
            for entries in (by_id or {}).values():
                for entry in entries or []:
                    curie = (entry.get("curie") or "").strip()
                    add(
                        CrossReference(
                            id=curie,
                            source=entry.get("targetPrefix") or curie.partition(":")[0],
                            label=entry.get("label") or None,
                            distance=entry.get("distance"),
                        )
                    )

        if resolved is None and not mappings:
            raise ToolError(
                f"No concept or cross-references found for '{concept_id}'. Check the CURIE with "
                "biomed_validate_curie, or find the identifier with biomed_search_concepts."
            )

        if target_prefixes:
            wanted = {p.strip().upper() for p in target_prefixes if p.strip()}
            mappings = [
                m
                for m in mappings
                if m.source.upper() in wanted or m.id.partition(":")[0].upper() in wanted
            ]
        mappings.sort(key=lambda m: (m.distance or 0, m.source.upper(), m.id))
        if len(mappings) > limit:
            warnings.append(
                f"Showing {limit} of {len(mappings)} mappings; raise `limit` or narrow with "
                "`target_prefixes`."
            )
            mappings = mappings[:limit]

        return MappingsResponse(
            concept_id=concept_id,
            label=label,
            count=len(mappings),
            mappings=mappings,
            warnings=warnings,
        )

    @server.tool(
        name="biomed_list_sources",
        title="List knowledge sources",
        annotations=_READ_ONLY_LOCAL,
    )
    async def list_sources() -> SourcesResponse:
        """List every knowledge source and whether this server can use it.

        Shows a one-line description, availability, membership in the default search set, and
        what an unavailable source needs (an API key environment variable or an optional extra).
        Call this to pick `sources` for biomed_search_concepts or to explain missing results.
        """
        lookup = await state.lookup()
        infos = []
        for source, spec in SOURCE_CATALOG.items():
            available = source in lookup.adapters
            circuit = None
            if available:
                health = lookup.health_tracker.get_health(source)
                state_value = getattr(health, "circuit_state", None) if health else None
                circuit = str(getattr(state_value, "value", state_value) or "").lower() or None
            infos.append(
                SourceInfo(
                    name=source.value,
                    description=spec.description,
                    available=available,
                    in_default_search=available and source in state.settings.default_sources,
                    requires=None
                    if available
                    else _unavailable_reason(source).removeprefix("requires "),
                    circuit_state=None if circuit == "closed" else circuit,
                )
            )
        infos.sort(key=lambda i: (not i.available, i.name))
        defaults = [s.value for s in state.settings.default_sources if s in lookup.adapters]
        return SourcesResponse(
            available_count=sum(i.available for i in infos),
            default_search_sources=defaults,
            sources=infos,
        )

    @server.tool(
        name="biomed_validate_curie",
        title="Validate and normalize an identifier",
        annotations=_READ_ONLY_LOCAL,
    )
    async def validate_curie(
        identifier: Annotated[
            str,
            Field(
                min_length=1,
                max_length=500,
                description=(
                    "CURIE in any case ('hp:0001250', 'UniProtKB:P38398') or IRI "
                    "('http://purl.obolibrary.org/obo/HP_0001250')."
                ),
            ),
        ],
    ) -> CurieValidation:
        """Check and normalize an identifier offline against Bioregistry (no remote API calls).

        Reports whether the prefix is registered, whether the local ID matches the prefix's
        pattern (with an example when it does not), the canonical CURIE and IRI, and which
        source biomed_get_concept would route it to. Useful before resolving identifiers taken
        from papers, spreadsheets or model output.
        """
        return await asyncio.to_thread(_validate_identifier, identifier)

    # -- resources ------------------------------------------------------------

    @server.resource(
        "biomed://sources",
        name="knowledge_sources",
        title="Knowledge sources",
        description="Catalog of knowledge sources with availability and requirements.",
        mime_type="application/json",
    )
    async def sources_resource() -> str:
        return (await list_sources()).model_dump_json(indent=2)

    @server.resource(
        "biomed://concept/{concept_id}",
        name="concept",
        title="Concept record",
        description="Detailed record for an identifier, e.g. biomed://concept/HP:0001250.",
        mime_type="application/json",
    )
    async def concept_resource(concept_id: str) -> str:
        lookup = await state.lookup()
        resolved = await _resolve_concept(state, lookup, concept_id.strip(), None, None)
        if resolved is None:
            raise ResourceNotFoundError(f"No concept found for '{concept_id}'.")
        concept, via = resolved
        detail = ConceptDetail.from_unified(concept, "detailed", resolved_via=via)
        return detail.model_dump_json(indent=2)

    # -- prompts --------------------------------------------------------------

    @server.prompt(
        name="normalize_terms",
        title="Normalize terms to ontology identifiers",
        description="Map a list of biomedical terms to their best ontology identifiers.",
    )
    def normalize_terms(
        terms: Annotated[str, Field(description="Comma- or newline-separated terms.")],
        preferred_sources: Annotated[
            str, Field(description="Optional comma-separated sources to prefer, e.g. 'HPO,MONDO'.")
        ] = "",
    ) -> str:
        preference = (
            f"Prefer these sources: {preferred_sources}. " if preferred_sources.strip() else ""
        )
        return textwrap.dedent(
            f"""\
            Normalize each of the following biomedical terms to a standard ontology identifier.

            Terms:
            {terms}

            For every term: call biomed_search_concepts ({preference}use expand_synonyms=true for
            abbreviations), pick the best match by label, synonyms and definition rather than by
            score alone, and confirm ambiguous picks with biomed_get_concept.

            Answer with a table: term | identifier | label | source | confidence (high/medium/low)
            | notes (ambiguity, runner-up identifiers). Mark terms without a convincing match as
            unmapped instead of guessing."""
        )

    @server.prompt(
        name="annotate_text",
        title="Annotate biomedical text",
        description="Extract biomedical entities from text and ground them to identifiers.",
    )
    def annotate_text(
        text: Annotated[str, Field(description="Clinical note, abstract or other free text.")],
    ) -> str:
        return textwrap.dedent(
            f"""\
            Identify the biomedical entities (diseases, phenotypes and symptoms, genes and
            proteins, chemicals and drugs, anatomy, procedures) mentioned in the text below and
            ground each one to an ontology identifier.

            Text:
            \"\"\"
            {text}
            \"\"\"

            Use biomed_search_concepts with focused `sources` per entity type (HPO for phenotypes,
            MONDO for diseases, HGNC/UNIPROT for genes and proteins, CHEBI via OLS or PUBCHEM for
            chemicals). Respect negation and uncertainty in the text.

            Answer with a table: mention | entity type | identifier | label | negated? | notes."""
        )

    return server


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="knowledge-lookup-mcp",
        description="Serve biomedical knowledge lookup over the Model Context Protocol.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.environ.get("KNOWLEDGE_LOOKUP_MCP_TRANSPORT", "stdio"),
        help="stdio for local clients (default), streamable-http to serve over HTTP.",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP bind address (default: %(default)s)."
    )
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: %(default)s).")
    parser.add_argument(
        "--default-sources",
        help="Comma-separated sources searched when a call names none "
        "(env KNOWLEDGE_LOOKUP_MCP_DEFAULT_SOURCES).",
    )
    parser.add_argument(
        "--enabled-sources",
        help="Comma-separated sources to initialise; default all "
        "(env KNOWLEDGE_LOOKUP_MCP_ENABLED_SOURCES).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Per-source timeout in seconds (default 15; env KNOWLEDGE_LOOKUP_MCP_TIMEOUT).",
    )
    parser.add_argument(
        "--persist-expansions",
        action="store_true",
        help="Record synonym-expansion trails in the durable expansion store "
        "(env KNOWLEDGE_LOOKUP_MCP_PERSIST_EXPANSIONS).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=os.environ.get("KNOWLEDGE_LOOKUP_MCP_LOG_LEVEL", "WARNING").upper(),
        help="Log level for stderr logging (default: %(default)s).",
    )
    return parser.parse_args(argv)


def settings_from_args(args: argparse.Namespace) -> ServerSettings:
    """Environment settings overridden by explicit command-line flags."""
    try:
        settings = ServerSettings.from_env()
        if args.default_sources:
            settings.default_sources = parse_source_names(args.default_sources)
        if args.enabled_sources:
            settings.enabled_sources = parse_source_names(args.enabled_sources)
    except ValueError as exc:
        valid = ", ".join(sorted(s.value for s in SOURCE_CATALOG))
        raise SystemExit(f"Invalid server configuration: {exc}. Valid sources: {valid}") from exc
    if args.timeout is not None:
        settings.timeout_per_source = args.timeout
    if args.persist_expansions:
        settings.persist_expansions = True
    return settings


def run(argv: list[str] | None = None) -> None:
    """Parse arguments and serve until the client disconnects."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = create_server(settings_from_args(args), log_level=args.log_level)
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port, stateless_http=True)
