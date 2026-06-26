"""
EUtils Knowledge Source Adapter

Adapter for querying NCBI databases via EUtils (Entrez Utilities).
Provides access to PubMed, Gene, Protein, and other NCBI databases.
Critical for literature mining and gene information in ME/CFS research.
"""

import logging

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class EUtilsAdapter(KnowledgeSourceAdapter):
    """Adapter for NCBI EUtils (Entrez Programming Utilities)."""

    def get_source(self):
        return KnowledgeSource.EUTILS

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search NCBI databases for biomedical concepts.

        EUtils provides access to:
        - PubMed (literature citations)
        - Gene (gene information)
        - Protein (protein sequences)
        - Nucleotide (DNA/RNA sequences)
        - Taxonomy (organism classification)
        - And many other databases
        """
        try:
            from bioservices import EUtils
        except ImportError:
            logger.error("bioservices not available for EUtils adapter")
            return []

        email = self.config.get_api_key("ncbi_email") or "anonymous@example.com"

        def _do_search(search_limit: int) -> list[UnifiedConcept]:
            eu = EUtils(email=email)
            results: list[UnifiedConcept] = []

            # Search PubMed for literature
            try:
                pubmed_results = eu.ESearch(db="pubmed", term=query, retmax=search_limit // 4)
                if (
                    pubmed_results
                    and isinstance(pubmed_results, dict)
                    and "IdList" in pubmed_results
                ):
                    id_list = pubmed_results["IdList"]
                    if isinstance(id_list, list):
                        for pmid in id_list[: search_limit // 4]:
                            summary = eu.ESummary(db="pubmed", id=pmid)
                            if summary and isinstance(summary, dict) and "DocSum" in summary:
                                docsum = summary["DocSum"]
                                title = _extract_pubmed_field(docsum, "Title")
                                authors = _extract_pubmed_field(docsum, "AuthorList")
                                if title:
                                    concept = UnifiedConcept(
                                        primary_id=f"PMID:{pmid}",
                                        primary_label=title,
                                        concept_type=ConceptType.CITATION,
                                    )
                                    if concept.sources is not None:
                                        concept.sources.append(KnowledgeSource.EUTILS)
                                    if isinstance(concept.source_data, dict):
                                        concept.source_data[KnowledgeSource.EUTILS] = {
                                            "database": "pubmed",
                                            "pmid": pmid,
                                            "title": title,
                                            "authors": authors,
                                            "description": f"PubMed Citation: {title}",
                                        }
                                    results.append(concept)
            except Exception:
                pass

            # Search Gene database
            try:
                gene_results = eu.ESearch(db="gene", term=query, retmax=search_limit // 4)
                if gene_results and isinstance(gene_results, dict) and "IdList" in gene_results:
                    id_list = gene_results["IdList"]
                    if isinstance(id_list, list):
                        for gene_id in id_list[: search_limit // 4]:
                            summary = eu.ESummary(db="gene", id=gene_id)
                            if summary and isinstance(summary, dict) and "DocSum" in summary:
                                docsum = summary["DocSum"]
                                name = _extract_gene_field(docsum, "Name")
                                description = _extract_gene_field(docsum, "Description")
                                if name:
                                    concept = UnifiedConcept(
                                        primary_id=f"GeneID:{gene_id}",
                                        primary_label=name,
                                        concept_type=ConceptType.GENE,
                                    )
                                    if concept.sources is not None:
                                        concept.sources.append(KnowledgeSource.EUTILS)
                                    if isinstance(concept.source_data, dict):
                                        concept.source_data[KnowledgeSource.EUTILS] = {
                                            "database": "gene",
                                            "gene_id": gene_id,
                                            "name": name,
                                            "description": description,
                                            "summary": f"Gene: {name} - {description}",
                                        }
                                    results.append(concept)
            except Exception:
                pass

            # Search Protein database
            try:
                protein_results = eu.ESearch(db="protein", term=query, retmax=search_limit // 4)
                if (
                    protein_results
                    and isinstance(protein_results, dict)
                    and "IdList" in protein_results
                ):
                    id_list = protein_results["IdList"]
                    if isinstance(id_list, list):
                        for protein_id in id_list[: search_limit // 4]:
                            summary = eu.ESummary(db="protein", id=protein_id)
                            if summary and isinstance(summary, dict) and "DocSum" in summary:
                                docsum = summary["DocSum"]
                                name = _extract_protein_field(docsum, "Title")
                                accession = _extract_protein_field(docsum, "AccessionVersion")
                                if name:
                                    concept = UnifiedConcept(
                                        primary_id=f"Protein:{protein_id}",
                                        primary_label=name,
                                        concept_type=ConceptType.PROTEIN,
                                    )
                                    if concept.sources is not None:
                                        concept.sources.append(KnowledgeSource.EUTILS)
                                    if isinstance(concept.source_data, dict):
                                        concept.source_data[KnowledgeSource.EUTILS] = {
                                            "database": "protein",
                                            "protein_id": protein_id,
                                            "name": name,
                                            "accession": accession,
                                            "summary": f"Protein: {name}",
                                        }
                                    results.append(concept)
            except Exception:
                pass

            # Search Taxonomy database
            try:
                taxonomy_results = eu.ESearch(db="taxonomy", term=query, retmax=search_limit // 4)
                if (
                    taxonomy_results
                    and isinstance(taxonomy_results, dict)
                    and "IdList" in taxonomy_results
                ):
                    id_list = taxonomy_results["IdList"]
                    if isinstance(id_list, list):
                        for tax_id in id_list[: search_limit // 4]:
                            summary = eu.ESummary(db="taxonomy", id=tax_id)
                            if summary and isinstance(summary, dict) and "DocSum" in summary:
                                docsum = summary["DocSum"]
                                scientific_name = _extract_taxonomy_field(docsum, "ScientificName")
                                common_name = _extract_taxonomy_field(docsum, "CommonName")
                                if scientific_name:
                                    concept = UnifiedConcept(
                                        primary_id=f"TaxID:{tax_id}",
                                        primary_label=scientific_name,
                                        concept_type=ConceptType.ORGANISM,
                                    )
                                    if concept.sources is not None:
                                        concept.sources.append(KnowledgeSource.EUTILS)
                                    if isinstance(concept.source_data, dict):
                                        concept.source_data[KnowledgeSource.EUTILS] = {
                                            "database": "taxonomy",
                                            "tax_id": tax_id,
                                            "scientific_name": scientific_name,
                                            "common_name": common_name,
                                            "summary": f"Organism: {scientific_name}",
                                        }
                                    results.append(concept)
            except Exception:
                pass

            return results[:search_limit]

        try:
            return await self._thread_with_retry("eutils_search", _do_search, limit)
        except Exception as e:
            logger.error(f"Error searching EUtils: {e}")
            return []

    async def get_concept_details(self, concept_id: str):
        """
        Get detailed information about an NCBI database entry.

        Returns full records from PubMed, Gene, Protein, or other databases.
        """
        try:
            from bioservices import EUtils
        except ImportError:
            logger.error("bioservices not available for EUtils adapter")
            return None

        email = self.config.get_api_key("ncbi_email") or "anonymous@example.com"

        def _do_get_details(cid: str) -> UnifiedConcept | None:
            eu = EUtils(email=email)
            # Parse concept ID to determine database and ID
            if cid.startswith("PMID:"):
                db = "pubmed"
                ncbi_id = cid.replace("PMID:", "")
            elif cid.startswith("GeneID:"):
                db = "gene"
                ncbi_id = cid.replace("GeneID:", "")
            elif cid.startswith("TaxID:"):
                db = "taxonomy"
                ncbi_id = cid.replace("TaxID:", "")
            else:
                if cid.startswith("NP_") or cid.startswith("XP_"):
                    db = "protein"
                elif cid.startswith("NM_") or cid.startswith("XM_"):
                    db = "nuccore"
                else:
                    db = "pubmed"
                ncbi_id = cid

            record = eu.EFetch(db=db, id=ncbi_id, rettype="full", retmode="text")
            if record:
                if db == "pubmed":
                    concept_type = ConceptType.CITATION
                    label = f"PubMed Article {ncbi_id}"
                elif db == "gene":
                    concept_type = ConceptType.GENE
                    label = f"Gene {ncbi_id}"
                elif db == "protein":
                    concept_type = ConceptType.PROTEIN
                    label = f"Protein {ncbi_id}"
                elif db == "taxonomy":
                    concept_type = ConceptType.OBSERVATION
                    label = f"Organism {ncbi_id}"
                else:
                    concept_type = ConceptType.MOLECULAR_ENTITY
                    label = f"{db.upper()} {ncbi_id}"

                concept = UnifiedConcept(
                    primary_id=cid,
                    primary_label=label,
                    concept_type=concept_type,
                )
                if concept.sources is not None:
                    concept.sources.append(KnowledgeSource.EUTILS)
                if isinstance(concept.source_data, dict):
                    concept.source_data[KnowledgeSource.EUTILS] = {
                        "database": db,
                        "ncbi_id": ncbi_id,
                        "full_record": str(record),
                        "description": f"NCBI {db.upper()} record: {ncbi_id}",
                    }
                return concept
            return None

        try:
            return await self._thread_with_retry("eutils_get_details", _do_get_details, concept_id)
        except Exception as e:
            logger.error(f"Error getting EUtils concept details for {concept_id}: {e}")
            return None


# Module-level helper functions (no self access needed)


def _extract_pubmed_field(docsum, field_name: str) -> str:
    """Extract field from PubMed DocSum."""
    try:
        if isinstance(docsum, dict) and "Item" in docsum:
            for item in docsum["Item"]:
                if isinstance(item, dict) and item.get("Name") == field_name:
                    return item.get("ItemContent", "")
        return ""
    except Exception:
        return ""


def _extract_gene_field(docsum, field_name: str) -> str:
    """Extract field from Gene DocSum."""
    try:
        if isinstance(docsum, dict) and "Item" in docsum:
            for item in docsum["Item"]:
                if isinstance(item, dict) and item.get("Name") == field_name:
                    return item.get("ItemContent", "")
        return ""
    except Exception:
        return ""


def _extract_protein_field(docsum, field_name: str) -> str:
    """Extract field from Protein DocSum."""
    try:
        if isinstance(docsum, dict) and "Item" in docsum:
            for item in docsum["Item"]:
                if isinstance(item, dict) and item.get("Name") == field_name:
                    return item.get("ItemContent", "")
        return ""
    except Exception:
        return ""


def _extract_taxonomy_field(docsum, field_name: str) -> str:
    """Extract field from Taxonomy DocSum."""
    try:
        if isinstance(docsum, dict) and "Item" in docsum:
            for item in docsum["Item"]:
                if isinstance(item, dict) and item.get("Name") == field_name:
                    return item.get("ItemContent", "")
        return ""
    except Exception:
        return ""
