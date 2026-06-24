"""
QuickGO Knowledge Source Adapter

Adapter for querying QuickGO gene ontology annotation service.
QuickGO provides comprehensive Gene Ontology (GO) annotations for genes and gene products.
Essential for functional analysis and understanding biological processes in ME/CFS research.
"""

import logging

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class QuickGOAdapter(KnowledgeSourceAdapter):
    """Adapter for QuickGO gene ontology annotation service."""

    def get_source(self):
        return KnowledgeSource.QUICKGO

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

        def _do_search(search_limit: int) -> list[UnifiedConcept]:
            qgo = QuickGO()
            results: list[UnifiedConcept] = []

            # Search for GO terms
            try:
                term_results = qgo.get_go_terms(query=query)
                if term_results and isinstance(term_results, list) and len(term_results) > 0:
                    for term in term_results[: search_limit // 2]:
                        if isinstance(term, dict):
                            go_id = term.get("id", "")
                            go_name = term.get("name", "")
                            go_namespace = term.get("aspect", "")

                            if go_namespace == "biological_process":
                                concept_type = ConceptType.BIOLOGICAL_PROCESS
                            elif go_namespace == "molecular_function":
                                concept_type = ConceptType.MOLECULAR_FUNCTION
                            elif go_namespace == "cellular_component":
                                concept_type = ConceptType.CELLULAR_COMPONENT
                            else:
                                concept_type = ConceptType.BIOLOGICAL_PROCESS

                            if go_id and go_name:
                                concept = UnifiedConcept(
                                    primary_id=go_id,
                                    primary_label=go_name,
                                    concept_type=concept_type,
                                )
                                concept.sources.append("QUICKGO")
                                concept.source_data[KnowledgeSource.QUICKGO] = {
                                    "go_aspect": go_namespace,
                                    "definition": term.get("definition", ""),
                                    "obsolete": term.get("isObsolete", False),
                                    "description": f"GO Term: {go_name} ({go_namespace})",
                                }
                                results.append(concept)
            except Exception:
                pass

            # Search for annotations (gene associations)
            try:
                annotation_results = qgo.Annotation(geneProductId=query, limit=search_limit // 2)
                if (
                    annotation_results
                    and isinstance(annotation_results, list)
                    and len(annotation_results) > 0
                ):
                    for annotation in annotation_results[: search_limit // 2]:
                        if isinstance(annotation, dict):
                            gene_id = annotation.get("geneProductId", "")
                            go_id = annotation.get("goId", "")
                            qualifier = annotation.get("qualifier", "")
                            evidence_code = annotation.get("evidenceCode", "")

                            if gene_id and go_id:
                                concept = UnifiedConcept(
                                    primary_id=f"{gene_id}_{go_id}",
                                    primary_label=f"{gene_id} → {go_id}",
                                    concept_type=ConceptType.GENE_DISEASE_ASSOCIATION,
                                )
                                concept.sources.append("QUICKGO")
                                concept.source_data[KnowledgeSource.QUICKGO] = {
                                    "gene_id": gene_id,
                                    "go_id": go_id,
                                    "qualifier": qualifier,
                                    "evidence_code": evidence_code,
                                    "aspect": annotation.get("aspect", ""),
                                    "description": f"GO Annotation: {gene_id} associated with {go_id}",
                                }
                                results.append(concept)
            except Exception:
                pass

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
            qgo = QuickGO()

            if cid.startswith("GO:"):
                term_results = qgo.get_go_terms(query=cid)
                if term_results and isinstance(term_results, list) and len(term_results) > 0:
                    term = term_results[0]
                    if isinstance(term, dict):
                        go_name = term.get("name", "")
                        go_namespace = term.get("aspect", "")

                        if go_namespace == "biological_process":
                            concept_type = ConceptType.BIOLOGICAL_PROCESS
                        elif go_namespace == "molecular_function":
                            concept_type = ConceptType.MOLECULAR_FUNCTION
                        elif go_namespace == "cellular_component":
                            concept_type = ConceptType.CELLULAR_COMPONENT
                        else:
                            concept_type = ConceptType.BIOLOGICAL_PROCESS

                        if go_name:
                            concept = UnifiedConcept(
                                primary_id=cid,
                                primary_label=go_name,
                                concept_type=concept_type,
                            )
                            concept.sources.append("QUICKGO")
                            concept.source_data[KnowledgeSource.QUICKGO] = {
                                "go_aspect": go_namespace,
                                "definition": term.get("definition", ""),
                                "synonyms": term.get("synonyms", []),
                                "obsolete": term.get("isObsolete", False),
                                "comment": term.get("comment", ""),
                                "usage": term.get("usage", ""),
                                "full_details": term,
                            }
                            return concept
            else:
                annotation_results = qgo.Annotation(geneProductId=cid, limit=10)
                if (
                    annotation_results
                    and isinstance(annotation_results, list)
                    and len(annotation_results) > 0
                ):
                    annotation = annotation_results[0]
                    if isinstance(annotation, dict):
                        gene_id = annotation.get("geneProductId", "")
                        go_id = annotation.get("goId", "")

                        if gene_id and go_id:
                            concept = UnifiedConcept(
                                primary_id=f"{gene_id}_{go_id}",
                                primary_label=f"{gene_id} → {go_id}",
                                concept_type=ConceptType.GENE_DISEASE_ASSOCIATION,
                            )
                            concept.sources.append("QUICKGO")
                            concept.source_data[KnowledgeSource.QUICKGO] = {
                                "gene_id": gene_id,
                                "go_id": go_id,
                                "qualifier": annotation.get("qualifier", ""),
                                "evidence_code": annotation.get("evidenceCode", ""),
                                "aspect": annotation.get("aspect", ""),
                                "reference": annotation.get("reference", ""),
                                "withFrom": annotation.get("withFrom", []),
                                "taxonId": annotation.get("taxonId", ""),
                                "date": annotation.get("date", ""),
                                "assignedBy": annotation.get("assignedBy", ""),
                                "extensions": annotation.get("extensions", []),
                                "full_annotation": annotation,
                            }
                            return concept

            return None

        try:
            return await self._thread_with_retry(
                "quickgo_get_details", _do_get_details, concept_id
            )
        except Exception as e:
            logger.error(f"Error getting QuickGO concept details for {concept_id}: {e}")
            return None
