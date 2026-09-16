"""
Tyto Knowledge Source Adapter

Integrates with the Tyto library for ontology term lookup.

Tyto has no cross-ontology search or ``get_label`` function; it exposes one
``Ontology`` object per ontology (``tyto.SO``, ``tyto.SBO``, ``tyto.NCIT``, ...)
with ``get_term_by_uri`` (URI → label) and ``get_uri_by_term`` (exact label →
URI). This adapter supports the Sequence Ontology, the Systems Biology Ontology
and the NCI Thesaurus.
"""

import logging
import re

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

try:
    import tyto
except ImportError:
    tyto = None
    logger.warning("Tyto library not available. Install with: pip install tyto")

# Supported tyto ontologies (attribute names on the tyto module), in search order,
# with the term URI prefixes that select them. tyto accepts both the PURL and the
# identifiers.org form of a term URI.
_ONTOLOGY_URI_PREFIXES: dict[str, tuple[str, ...]] = {
    "SO": (
        "http://purl.obolibrary.org/obo/SO_",
        "https://identifiers.org/SO:",
        "https://identifiers.org/so/SO:",
    ),
    "SBO": (
        "http://biomodels.net/SBO/SBO_",
        "https://identifiers.org/SBO:",
        "https://identifiers.org/sbo/SBO:",
    ),
    "NCIT": (
        "http://purl.obolibrary.org/obo/NCIT_",
        "https://identifiers.org/ncit:",
        "https://identifiers.org/ncit/ncit:",
    ),
}

# tyto interpolates terms into a SPARQL regex and URIs into <...> without
# escaping, so only plain labels and well-formed URIs are passed on.
_SAFE_TERM = re.compile(r"\w[\w \-]*")
_IRI_FORBIDDEN = re.compile(r'[<>"{}|^`\\\s]')


def _normalize_uri(uri: str) -> str:
    """tyto only recognises identifiers.org URIs in their https form."""
    if uri.startswith("http://identifiers.org/"):
        return "https://" + uri[len("http://") :]
    return uri


def _ontology_for_uri(uri: str) -> str | None:
    """Name of the supported tyto ontology a term URI belongs to, if any."""
    for name, prefixes in _ONTOLOGY_URI_PREFIXES.items():
        if uri.startswith(prefixes):
            return name
    return None


class TytoAdapter(KnowledgeSourceAdapter):
    """Adapter for Tyto."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.TYTO

    def is_available(self) -> bool:
        return tyto is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Look up an exact term label in SO, SBO and NCIT.

        tyto has no free-text search: ``get_uri_by_term`` matches whole labels
        (case-insensitively, spaces also matching ``-``/``_``). Each ontology
        returns at most one term.
        """
        if not tyto or limit <= 0:
            return []

        term = query.strip()
        if not _SAFE_TERM.fullmatch(term):
            logger.warning(
                "Tyto search only supports labels made of letters, digits, spaces and "
                f"hyphens; skipping '{query}'"
            )
            return []

        def _do_search() -> list[UnifiedConcept]:
            concepts: list[UnifiedConcept] = []
            errors: list[Exception] = []
            for name in _ONTOLOGY_URI_PREFIXES:
                ontology = getattr(tyto, name)
                try:
                    uri = ontology.get_uri_by_term(term)
                except LookupError:
                    continue  # the label is not in this ontology
                except Exception as exc:
                    if str(exc).startswith("Ambiguous term"):
                        logger.info(f"Tyto {name}: {exc}")
                    else:
                        logger.warning(f"Tyto {name} lookup failed for '{term}': {exc}")
                        errors.append(exc)
                    continue
                if not uri:
                    continue
                try:
                    label = str(ontology.get_term_by_uri(str(uri))) or term
                except Exception:
                    label = term
                concepts.append(self._make_concept(str(uri), label, name))

            # Every ontology failed: surface the error to the retry/circuit breaker
            if len(errors) == len(_ONTOLOGY_URI_PREFIXES):
                raise errors[-1]
            return concepts[:limit]

        try:
            return await self._thread_with_retry("tyto_search", _do_search)
        except Exception as e:
            logger.error(f"Tyto search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get the label of an SO, SBO or NCIT term URI using tyto."""
        if not tyto:
            return None

        # Tyto works with term URIs
        if not concept_id.startswith("http") or _IRI_FORBIDDEN.search(concept_id):
            return None

        uri = _normalize_uri(concept_id)
        ontology_name = _ontology_for_uri(uri)
        if ontology_name is None:
            logger.warning(
                f"Tyto adapter supports SO, SBO and NCIT term URIs; cannot resolve '{concept_id}'"
            )
            return None
        ontology = getattr(tyto, ontology_name)

        def _lookup(term_uri: str) -> str | None:
            try:
                return str(ontology.get_term_by_uri(term_uri))
            except LookupError:
                return None  # not a term of this ontology

        try:
            label = await self._thread_with_retry("tyto_get_term", _lookup, uri)
        except Exception as e:
            logger.error(f"Tyto lookup failed for '{concept_id}': {e}")
            return None

        if not label:
            return None
        return self._make_concept(concept_id, label, ontology_name)

    def _make_concept(self, uri: str, label: str, ontology_name: str) -> UnifiedConcept:
        concept = UnifiedConcept(
            primary_id=uri, primary_label=label, concept_type=ConceptType.UNKNOWN
        )
        concept.add_identifier(KnowledgeSource.TYTO, uri, label, uri)
        if concept.categories is not None:
            concept.categories.append(ontology_name)
        concept.confidence_score = 1.0
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.TYTO] = {
                "ontology": ontology_name,
                "uri": uri,
                "label": label,
            }
        return concept
