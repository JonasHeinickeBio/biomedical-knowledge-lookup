"""
QuickGO Knowledge Source Adapter

Adapter for querying QuickGO gene ontology annotation service.
QuickGO provides comprehensive Gene Ontology (GO) annotations for genes and gene products.
Essential for functional analysis and understanding biological processes in ME/CFS research.
"""

import importlib.util
import logging
import re
import sys
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

_ASPECT_TO_CONCEPT_TYPE = {
    "biological_process": ConceptType.BIOLOGICAL_PROCESS,
    "molecular_function": ConceptType.MOLECULAR_FUNCTION,
    "cellular_component": ConceptType.CELLULAR_COMPONENT,
}

# Gene product IDs accepted by QuickGO's annotation search: a database-prefixed
# ID (UniProtKB:P04637, ComplexPortal:CPX-1) or a bare UniProt accession (P04637).
# Free text is not sent there, because QuickGO answers it with HTTP 400.
_GENE_PRODUCT_ID = re.compile(
    r"[A-Za-z][A-Za-z0-9_.-]*:[A-Za-z0-9_.-]+"
    r"|[OPQ][0-9][A-Z0-9]{3}[0-9](?:-\d+)?"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}(?:-\d+)?"
)


def _bioservices_installed() -> bool:
    """True if ``bioservices`` can be imported (without importing it)."""
    if "bioservices" in sys.modules:
        return sys.modules["bioservices"] is not None
    try:
        return importlib.util.find_spec("bioservices") is not None
    except (ImportError, ValueError):
        return False


def _is_gene_product_id(value: str) -> bool:
    value = value.strip()
    return bool(_GENE_PRODUCT_ID.fullmatch(value)) and not value.upper().startswith("GO:")


def _results_list(response: Any, what: str) -> list[Any]:
    """Return the result list of a QuickGO response.

    ``bioservices`` returns an ``HTTPResponseError`` object (or a status code)
    instead of raising on HTTP errors, and ``Annotation`` returns the whole
    page (``{"numberOfHits": ..., "results": [...]}``). Anything that is not a
    result list raises, so failures are not mistaken for "no results".
    """
    if isinstance(response, list):
        return response
    if isinstance(response, dict) and isinstance(response.get("results"), list):
        return response["results"]
    raise RuntimeError(f"QuickGO {what} failed: {response!r}")


class QuickGOAdapter(KnowledgeSourceAdapter):
    """Adapter for QuickGO gene ontology annotation service."""

    def get_source(self):
        return KnowledgeSource.QUICKGO

    def is_available(self) -> bool:
        """Available only when the optional ``bioservices`` package is installed."""
        return _bioservices_installed()

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search QuickGO for GO terms and annotations.

        QuickGO provides:
        - Gene Ontology terms (Biological Process, Molecular Function, Cellular Component)
        - GO annotations for genes/proteins
        - Cross-references to other databases
        - Evidence codes and sources
        """
        try:
            from bioservices import QuickGO
        except ImportError:
            logger.error("bioservices not available for QuickGO adapter")
            return []

        if limit <= 0:
            return []

        def _do_search(search_limit: int) -> list[UnifiedConcept]:
            qgo = QuickGO(verbose=False)
            results: list[UnifiedConcept] = []
            errors: list[Exception] = []
            attempts = 1

            # Free-text GO term search (ontology/go/search endpoint)
            try:
                terms = _results_list(
                    qgo.go_search(query, limit=min(search_limit, 600)), "term search"
                )
                for term in terms[:search_limit]:
                    concept = self._term_to_concept(term)
                    if concept is not None:
                        results.append(concept)
            except Exception as exc:
                logger.warning(f"QuickGO term search failed for '{query}': {exc}")
                errors.append(exc)

            # Annotations (gene associations), only for gene product IDs
            if _is_gene_product_id(query):
                attempts += 1
                try:
                    annotations = _results_list(
                        qgo.Annotation(geneProductId=query.strip(), limit=min(search_limit, 100)),
                        "annotation search",
                    )
                    for annotation in annotations[:search_limit]:
                        concept = self._annotation_to_concept(annotation)
                        if concept is not None:
                            results.append(concept)
                except Exception as exc:
                    logger.warning(f"QuickGO annotation search failed for '{query}': {exc}")
                    errors.append(exc)

            # Every lookup failed: surface the error to the retry/circuit breaker
            if len(errors) == attempts:
                raise errors[-1]
            return results[:search_limit]

        try:
            return await self._thread_with_retry("quickgo_search", _do_search, limit)
        except Exception as e:
            logger.error(f"Error searching QuickGO: {e}")
            return []

    async def get_concept_details(self, concept_id: str):
        """
        Get detailed information about a GO term or annotation.

        Returns term definitions, synonyms, relationships, and annotation details.
        """
        try:
            from bioservices import QuickGO
        except ImportError:
            logger.error("bioservices not available for QuickGO adapter")
            return None

        def _do_get_details(cid: str) -> UnifiedConcept | None:
            if cid.startswith("GO:"):
                qgo = QuickGO(verbose=False)
                terms = _results_list(qgo.get_go_terms(cid), "term lookup")
                if not terms:
                    return None
                return self._term_to_concept(terms[0], concept_id=cid, detailed=True)

            if not _is_gene_product_id(cid):
                return None
            qgo = QuickGO(verbose=False)
            annotations = _results_list(
                qgo.Annotation(geneProductId=cid, limit=10), "annotation lookup"
            )
            if not annotations:
                return None
            return self._annotation_to_concept(annotations[0], detailed=True)

        try:
            return await self._thread_with_retry(
                "quickgo_get_details", _do_get_details, concept_id
            )
        except Exception as e:
            logger.error(f"Error getting QuickGO concept details for {concept_id}: {e}")
            return None

    def _term_to_concept(
        self, term: Any, concept_id: str | None = None, detailed: bool = False
    ) -> UnifiedConcept | None:
        """Convert a QuickGO GO term record into a concept."""
        if not isinstance(term, dict):
            return None
        go_id = concept_id or term.get("id", "")
        go_name = term.get("name", "")
        if not go_id or not go_name:
            return None

        go_namespace = term.get("aspect", "")
        concept = self._create_concept(
            go_id,
            go_name,
            _ASPECT_TO_CONCEPT_TYPE.get(go_namespace, ConceptType.BIOLOGICAL_PROCESS),
        )

        definition = term.get("definition", "")
        definition_text = (
            definition.get("text", "") if isinstance(definition, dict) else definition
        )
        if definition_text and concept.definitions is not None:
            concept.definitions.append(str(definition_text))

        data: dict[str, Any] = {
            "go_aspect": go_namespace,
            "definition": definition,
            "obsolete": term.get("isObsolete", False),
        }
        if detailed:
            synonyms = term.get("synonyms") or []
            names = [s.get("name") if isinstance(s, dict) else s for s in synonyms]
            if concept.synonyms is not None:
                concept.synonyms.extend(n for n in names if isinstance(n, str) and n)
            data.update(
                {
                    "synonyms": synonyms,
                    "comment": term.get("comment", ""),
                    "usage": term.get("usage", ""),
                    "full_details": term,
                }
            )
        else:
            data["description"] = f"GO Term: {go_name} ({go_namespace})"

        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.QUICKGO] = data
        return concept

    def _annotation_to_concept(
        self, annotation: Any, detailed: bool = False
    ) -> UnifiedConcept | None:
        """Convert a QuickGO annotation record into a gene product → GO term concept."""
        if not isinstance(annotation, dict):
            return None
        gene_id = annotation.get("geneProductId", "")
        go_id = annotation.get("goId", "")
        if not gene_id or not go_id:
            return None

        concept = UnifiedConcept(
            primary_id=f"{gene_id}_{go_id}",
            primary_label=f"{gene_id} → {go_id}",
            concept_type=ConceptType.GENE_DISEASE_ASSOCIATION,
        )
        if concept.sources is not None:
            concept.sources.append(KnowledgeSource.QUICKGO)

        data: dict[str, Any] = {
            "gene_id": gene_id,
            "symbol": annotation.get("symbol", ""),
            "go_id": go_id,
            "qualifier": annotation.get("qualifier", ""),
            "evidence_code": annotation.get("evidenceCode", ""),
            "go_evidence": annotation.get("goEvidence", ""),
            "aspect": annotation.get("goAspect") or annotation.get("aspect", ""),
        }
        if detailed:
            data.update(
                {
                    "reference": annotation.get("reference", ""),
                    "withFrom": annotation.get("withFrom", []),
                    "taxonId": annotation.get("taxonId", ""),
                    "date": annotation.get("date", ""),
                    "assignedBy": annotation.get("assignedBy", ""),
                    "extensions": annotation.get("extensions", []),
                    "full_annotation": annotation,
                }
            )
        else:
            data["description"] = f"GO Annotation: {gene_id} associated with {go_id}"

        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.QUICKGO] = data
        return concept
