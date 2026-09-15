"""
EUtils Knowledge Source Adapter

Adapter for querying NCBI databases via EUtils (Entrez Utilities).
Provides access to PubMed, Gene, Protein, and other NCBI databases.
Critical for literature mining and gene information in ME/CFS research.
"""

import importlib.util
import logging
import math
import sys
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

# Databases searched by search_concepts, in result order: (db, ID prefix, concept type)
_SEARCH_DATABASES: tuple[tuple[str, str, ConceptType], ...] = (
    ("pubmed", "PMID", ConceptType.CITATION),
    ("gene", "GeneID", ConceptType.GENE),
    ("protein", "Protein", ConceptType.PROTEIN),
    ("taxonomy", "TaxID", ConceptType.ORGANISM),
)

# EFetch rettype per database; "full" returns an empty body for pubmed and protein
_EFETCH_RETTYPES = {"pubmed": "abstract", "protein": "gp", "nuccore": "gb"}


def _bioservices_installed() -> bool:
    """True if ``bioservices`` can be imported (without importing it)."""
    if "bioservices" in sys.modules:
        return sys.modules["bioservices"] is not None
    try:
        return importlib.util.find_spec("bioservices") is not None
    except (ImportError, ValueError):
        return False


class EUtilsAdapter(KnowledgeSourceAdapter):
    """Adapter for NCBI EUtils (Entrez Programming Utilities)."""

    def get_source(self):
        return KnowledgeSource.EUTILS

    def is_available(self) -> bool:
        """Available only when the optional ``bioservices`` package is installed."""
        return _bioservices_installed()

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

        if limit <= 0:
            return []

        email = self.config.get_api_key("ncbi_email") or "anonymous@example.com"

        def _do_search(search_limit: int) -> list[UnifiedConcept]:
            eu = EUtils(email=email)
            results: list[UnifiedConcept] = []
            errors: list[Exception] = []
            per_database = max(1, math.ceil(search_limit / len(_SEARCH_DATABASES)))

            for db, _prefix, _concept_type in _SEARCH_DATABASES:
                try:
                    results.extend(_search_database(eu, db, query, per_database))
                except Exception as exc:
                    logger.warning(f"EUtils {db} search failed for '{query}': {exc}")
                    errors.append(exc)

            # Every database failed: surface the error to the retry/circuit breaker
            if len(errors) == len(_SEARCH_DATABASES):
                raise errors[-1]
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
            elif cid.startswith("Protein:"):
                db = "protein"
                ncbi_id = cid.replace("Protein:", "")
            else:
                if cid.startswith("NP_") or cid.startswith("XP_"):
                    db = "protein"
                elif cid.startswith("NM_") or cid.startswith("XM_"):
                    db = "nuccore"
                else:
                    db = "pubmed"
                ncbi_id = cid

            record = eu.EFetch(
                db, ncbi_id, rettype=_EFETCH_RETTYPES.get(db, "full"), retmode="text"
            )
            if isinstance(record, bytes):
                record = record.decode("utf-8", errors="replace")
            # bioservices returns an int status or error object instead of raising
            if not isinstance(record, str) or not record.strip():
                return None

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
                concept_type = ConceptType.ORGANISM
                label = f"Organism {ncbi_id}"
            else:
                concept_type = ConceptType.MOLECULAR_ENTITY
                label = f"{db.upper()} {ncbi_id}"

            # Prefer the real title/name from ESummary over the placeholder label
            try:
                summary = eu.ESummary(db, ncbi_id)
                summary_record = _first_summary_record(summary)
                label = _summary_label(db, summary_record) or label
            except Exception as exc:
                logger.debug(f"EUtils ESummary failed for {cid}: {exc}")

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
                    "full_record": record,
                    "description": f"NCBI {db.upper()} record: {ncbi_id}",
                }
            return concept

        try:
            return await self._thread_with_retry("eutils_get_details", _do_get_details, concept_id)
        except Exception as e:
            logger.error(f"Error getting EUtils concept details for {concept_id}: {e}")
            return None


# Module-level helper functions (no self access needed)


def _id_list(response: Any) -> list[str]:
    """Return the UIDs from an ESearch response.

    ``bioservices`` returns NCBI's JSON ``esearchresult`` object (``idlist``).
    Anything else (an error dict, an HTTP status code) raises so the failure is
    logged instead of looking like an empty result.
    """
    if isinstance(response, dict):
        if "esearchresult" in response:
            return _id_list(response["esearchresult"])
        ids = response.get("idlist", response.get("IdList"))
        if isinstance(ids, list):
            return [str(i) for i in ids]
    raise RuntimeError(f"unexpected ESearch response: {response!r}")


def _summary_records(summary: Any, ids: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(uid, record)`` pairs from an ESummary ``result`` object."""
    if not isinstance(summary, dict):
        raise RuntimeError(f"unexpected ESummary response: {summary!r}")
    if "result" in summary and isinstance(summary["result"], dict):
        summary = summary["result"]
    if "error" in summary and "uids" not in summary:
        raise RuntimeError(f"ESummary error: {summary['error']}")
    uids = summary.get("uids") or ids
    return [
        (str(uid), summary[str(uid)]) for uid in uids if isinstance(summary.get(str(uid)), dict)
    ]


def _first_summary_record(summary: Any) -> dict[str, Any] | None:
    records = _summary_records(summary, [])
    return records[0][1] if records else None


def _summary_label(db: str, record: dict[str, Any] | None) -> str:
    """Human-readable label of an ESummary record for *db*."""
    if not record:
        return ""
    if db == "gene":
        return str(_extract_gene_field(record, "Name") or "")
    if db == "taxonomy":
        return str(_extract_taxonomy_field(record, "ScientificName") or "")
    return str(_extract_pubmed_field(record, "Title") or "")


def _search_database(eu: Any, db: str, query: str, retmax: int) -> list[UnifiedConcept]:
    """Run ESearch + one batched ESummary on *db* and convert the records."""
    ids = _id_list(eu.ESearch(db, query, retmax=retmax))[:retmax]
    if not ids:
        return []
    summary = eu.ESummary(db, ",".join(ids))
    concepts = []
    for uid, record in _summary_records(summary, ids):
        concept = _summary_to_concept(db, uid, record)
        if concept is not None:
            concepts.append(concept)
    return concepts


def _summary_to_concept(db: str, uid: str, record: dict[str, Any]) -> UnifiedConcept | None:
    """Convert one ESummary JSON record into a concept (``None`` without a label)."""
    if db == "pubmed":
        title = _extract_pubmed_field(record, "Title")
        if not title:
            return None
        authors = [a.get("name", "") for a in record.get("authors") or [] if isinstance(a, dict)]
        concept = UnifiedConcept(
            primary_id=f"PMID:{uid}", primary_label=title, concept_type=ConceptType.CITATION
        )
        data = {
            "database": "pubmed",
            "pmid": uid,
            "title": title,
            "authors": authors,
            "journal": record.get("fulljournalname") or record.get("source", ""),
            "pubdate": record.get("pubdate", ""),
            "description": f"PubMed Citation: {title}",
        }
    elif db == "gene":
        name = _extract_gene_field(record, "Name")
        if not name:
            return None
        description = _extract_gene_field(record, "Description")
        concept = UnifiedConcept(
            primary_id=f"GeneID:{uid}", primary_label=name, concept_type=ConceptType.GENE
        )
        organism = record.get("organism")
        data = {
            "database": "gene",
            "gene_id": uid,
            "name": name,
            "description": description,
            "organism": organism.get("scientificname", "") if isinstance(organism, dict) else "",
            "summary": f"Gene: {name} - {description}",
        }
    elif db == "protein":
        name = _extract_protein_field(record, "Title")
        if not name:
            return None
        accession = _extract_protein_field(record, "AccessionVersion")
        concept = UnifiedConcept(
            primary_id=f"Protein:{uid}", primary_label=name, concept_type=ConceptType.PROTEIN
        )
        data = {
            "database": "protein",
            "protein_id": uid,
            "name": name,
            "accession": accession,
            "summary": f"Protein: {name}",
        }
    elif db == "taxonomy":
        scientific_name = _extract_taxonomy_field(record, "ScientificName")
        if not scientific_name:
            return None
        common_name = _extract_taxonomy_field(record, "CommonName")
        concept = UnifiedConcept(
            primary_id=f"TaxID:{uid}",
            primary_label=scientific_name,
            concept_type=ConceptType.ORGANISM,
        )
        data = {
            "database": "taxonomy",
            "tax_id": uid,
            "scientific_name": scientific_name,
            "common_name": common_name,
            "summary": f"Organism: {scientific_name}",
        }
    else:
        return None

    if concept.sources is not None:
        concept.sources.append(KnowledgeSource.EUTILS)
    if isinstance(concept.source_data, dict):
        concept.source_data[KnowledgeSource.EUTILS] = data
    return concept


def _extract_field(record: Any, field_name: str) -> Any:
    """Extract *field_name* from an ESummary record.

    Current NCBI JSON records are flat dicts with lower-case keys (``title``,
    ``scientificname``). Older XML-derived ``DocSum`` dicts keep the values in
    an ``Item`` list; both shapes are accepted.
    """
    try:
        if not isinstance(record, dict):
            return ""
        key = field_name.lower()
        if key in record:
            return record[key]
        for item in record.get("Item") or []:
            if isinstance(item, dict) and item.get("Name") == field_name:
                return item.get("ItemContent", "")
        return ""
    except Exception:
        return ""


def _extract_pubmed_field(docsum, field_name: str) -> str:
    """Extract field from a PubMed ESummary record."""
    return _extract_field(docsum, field_name)


def _extract_gene_field(docsum, field_name: str) -> str:
    """Extract field from a Gene ESummary record."""
    return _extract_field(docsum, field_name)


def _extract_protein_field(docsum, field_name: str) -> str:
    """Extract field from a Protein ESummary record."""
    return _extract_field(docsum, field_name)


def _extract_taxonomy_field(docsum, field_name: str) -> str:
    """Extract field from a Taxonomy ESummary record."""
    return _extract_field(docsum, field_name)
