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

        # Set email for NCBI (required by their policy)
        email = self.config.get_api_key("ncbi_email") or "anonymous@example.com"
        eu = EUtils(email=email)
        results = []

        try:
            # Search PubMed for literature
            pubmed_results = eu.ESearch(db="pubmed", term=query, retmax=limit // 4)
            if pubmed_results and isinstance(pubmed_results, dict) and "IdList" in pubmed_results:
                id_list = pubmed_results["IdList"]
                if isinstance(id_list, list):
                    for pmid in id_list[: limit // 4]:
                        # Get summary for each paper
                        summary = eu.ESummary(db="pubmed", id=pmid)
                        if summary and isinstance(summary, dict) and "DocSum" in summary:
                            docsum = summary["DocSum"]
                            title = self._extract_pubmed_field(docsum, "Title")
                            authors = self._extract_pubmed_field(docsum, "AuthorList")

                            if title:  # Only add if we have valid data
                                concept = UnifiedConcept(
                                    primary_id=f"PMID:{pmid}",
                                    primary_label=title,
                                    concept_type=ConceptType.CITATION,
                                )
                                concept.sources.add(self.source)
                                concept.source_data[self.source] = {
                                    "database": "pubmed",
                                    "pmid": pmid,
                                    "title": title,
                                    "authors": authors,
                                    "description": f"PubMed Citation: {title}",
                                }
                                results.append(concept)

            # Search Gene database
            gene_results = eu.ESearch(db="gene", term=query, retmax=limit // 4)
            if gene_results and isinstance(gene_results, dict) and "IdList" in gene_results:
                id_list = gene_results["IdList"]
                if isinstance(id_list, list):
                    for gene_id in id_list[: limit // 4]:
                        # Get summary for each gene
                        summary = eu.ESummary(db="gene", id=gene_id)
                        if summary and isinstance(summary, dict) and "DocSum" in summary:
                            docsum = summary["DocSum"]
                            name = self._extract_gene_field(docsum, "Name")
                            description = self._extract_gene_field(docsum, "Description")

                            if name:  # Only add if we have valid data
                                concept = UnifiedConcept(
                                    primary_id=f"GeneID:{gene_id}",
                                    primary_label=name,
                                    concept_type=ConceptType.GENE,
                                )
                                concept.sources.add(self.source)
                                concept.source_data[self.source] = {
                                    "database": "gene",
                                    "gene_id": gene_id,
                                    "name": name,
                                    "description": description,
                                    "summary": f"Gene: {name} - {description}",
                                }
                                results.append(concept)

            # Search Protein database
            protein_results = eu.ESearch(db="protein", term=query, retmax=limit // 4)
            if (
                protein_results
                and isinstance(protein_results, dict)
                and "IdList" in protein_results
            ):
                id_list = protein_results["IdList"]
                if isinstance(id_list, list):
                    for protein_id in id_list[: limit // 4]:
                        # Get summary for each protein
                        summary = eu.ESummary(db="protein", id=protein_id)
                        if summary and isinstance(summary, dict) and "DocSum" in summary:
                            docsum = summary["DocSum"]
                            name = self._extract_protein_field(docsum, "Title")
                            accession = self._extract_protein_field(docsum, "AccessionVersion")

                            if name:  # Only add if we have valid data
                                concept = UnifiedConcept(
                                    primary_id=f"Protein:{protein_id}",
                                    primary_label=name,
                                    concept_type=ConceptType.PROTEIN,
                                )
                                concept.sources.add(self.source)
                                concept.source_data[self.source] = {
                                    "database": "protein",
                                    "protein_id": protein_id,
                                    "name": name,
                                    "accession": accession,
                                    "summary": f"Protein: {name}",
                                }
                                results.append(concept)

            # Search Taxonomy database
            taxonomy_results = eu.ESearch(db="taxonomy", term=query, retmax=limit // 4)
            if (
                taxonomy_results
                and isinstance(taxonomy_results, dict)
                and "IdList" in taxonomy_results
            ):
                id_list = taxonomy_results["IdList"]
                if isinstance(id_list, list):
                    for tax_id in id_list[: limit // 4]:
                        # Get summary for each taxonomy entry
                        summary = eu.ESummary(db="taxonomy", id=tax_id)
                        if summary and isinstance(summary, dict) and "DocSum" in summary:
                            docsum = summary["DocSum"]
                            scientific_name = self._extract_taxonomy_field(
                                docsum, "ScientificName"
                            )
                            common_name = self._extract_taxonomy_field(docsum, "CommonName")

                            if scientific_name:  # Only add if we have valid data
                                concept = UnifiedConcept(
                                    primary_id=f"TaxID:{tax_id}",
                                    primary_label=scientific_name,
                                    concept_type=ConceptType.ORGANISM,
                                )
                                concept.sources.add(self.source)
                                concept.source_data[self.source] = {
                                    "database": "taxonomy",
                                    "tax_id": tax_id,
                                    "scientific_name": scientific_name,
                                    "common_name": common_name,
                                    "summary": f"Organism: {scientific_name}",
                                }
                                results.append(concept)

        except Exception as e:
            logger.error(f"Error searching EUtils: {e}")

        return results[:limit]

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
        eu = EUtils(email=email)

        try:
            # Parse concept ID to determine database and ID
            if concept_id.startswith("PMID:"):
                db = "pubmed"
                ncbi_id = concept_id.replace("PMID:", "")
            elif concept_id.startswith("GeneID:"):
                db = "gene"
                ncbi_id = concept_id.replace("GeneID:", "")
            elif concept_id.startswith("TaxID:"):
                db = "taxonomy"
                ncbi_id = concept_id.replace("TaxID:", "")
            else:
                # Assume it's a direct NCBI accession
                # Try to determine database from format
                if concept_id.startswith("NP_") or concept_id.startswith("XP_"):
                    db = "protein"
                elif concept_id.startswith("NM_") or concept_id.startswith("XM_"):
                    db = "nuccore"
                else:
                    db = "pubmed"  # Default fallback
                ncbi_id = concept_id

            # Get detailed record
            record = eu.EFetch(db=db, id=ncbi_id, rettype="full", retmode="text")

            if record:
                # Create concept with full details
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
                    primary_id=concept_id,
                    primary_label=label,
                    concept_type=concept_type,
                )
                concept.sources.add(self.source)
                concept.source_data[self.source] = {
                    "database": db,
                    "ncbi_id": ncbi_id,
                    "full_record": str(record),
                    "description": f"NCBI {db.upper()} record: {ncbi_id}",
                }
                return concept

        except Exception as e:
            logger.error(f"Error getting EUtils concept details for {concept_id}: {e}")

        return None

    def _extract_pubmed_field(self, docsum, field_name: str) -> str:
        """Extract field from PubMed DocSum."""
        try:
            if isinstance(docsum, dict) and "Item" in docsum:
                for item in docsum["Item"]:
                    if isinstance(item, dict) and item.get("Name") == field_name:
                        return item.get("ItemContent", "")
            return ""
        except Exception:
            return ""

    def _extract_gene_field(self, docsum, field_name: str) -> str:
        """Extract field from Gene DocSum."""
        try:
            if isinstance(docsum, dict) and "Item" in docsum:
                for item in docsum["Item"]:
                    if isinstance(item, dict) and item.get("Name") == field_name:
                        return item.get("ItemContent", "")
            return ""
        except Exception:
            return ""

    def _extract_protein_field(self, docsum, field_name: str) -> str:
        """Extract field from Protein DocSum."""
        try:
            if isinstance(docsum, dict) and "Item" in docsum:
                for item in docsum["Item"]:
                    if isinstance(item, dict) and item.get("Name") == field_name:
                        return item.get("ItemContent", "")
            return ""
        except Exception:
            return ""

    def _extract_taxonomy_field(self, docsum, field_name: str) -> str:
        """Extract field from Taxonomy DocSum."""
        try:
            if isinstance(docsum, dict) and "Item" in docsum:
                for item in docsum["Item"]:
                    if isinstance(item, dict) and item.get("Name") == field_name:
                        return item.get("ItemContent", "")
            return ""
        except Exception:
            return ""
