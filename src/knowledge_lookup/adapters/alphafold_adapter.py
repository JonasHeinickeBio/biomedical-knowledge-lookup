"""
AlphaFold Protein Structure Database adapter.

AlphaFold DB (https://alphafold.ebi.ac.uk, EMBL-EBI + Google DeepMind) holds predicted
3D structures for >200 million UniProt proteins. The adapter uses its keyless REST API:

* ``GET /api/prediction/{uniprot accession | AF entry id}`` -> list of model entries
  (canonical sequence first, then UniProt isoforms such as ``AF-P38398-2-F1``), each with
  the global pLDDT, the pLDDT confidence-band fractions and the model/PAE file URLs.
* ``GET https://rest.uniprot.org/uniprotkb/search`` resolves a gene symbol or protein name
  to a UniProt accession (AlphaFold DB itself is keyed by accession only).
* ``GET https://rest.uniprot.org/uniprotkb/{accession}?fields=xref_pdb`` lists experimental
  PDB structures for the protein (one cheap extra call, only used for relationships).

Concepts are predicted structures: ``primary_id`` is the AlphaFold entry id of the
canonical sequence (``AF-P38398-F1``); the UniProt accession is attached as an identifier.
Structure files are never downloaded: only their URLs are returned.

Quirks (verified live, October 2026)
------------------------------------
* The current model version is v6 (BRCA1 created 2025-08-01); file URLs embed the version,
  so they come from the response, never from a template.
* Lower-case accessions are accepted by the API; an invalid one is HTTP 400, an accession
  without a model is HTTP 404 (empty ``{}`` body).
* Large proteins and isoform-rich genes return several entries (BRCA1: 8 models of
  41-91 pLDDT); the response is ~30 KB because it repeats the full sequence.
* Without ``reviewed:true`` the first UniProt hit for a gene symbol is often an unreviewed
  TrEMBL fragment (BRCA1 -> E7ENB7), so the Swiss-Prot entry is looked up first.
* No rate limit is published; the adapter makes at most a few calls per query. Predicted
  models are released under CC BY 4.0 (cite Jumper 2021 and Varadi 2024).
"""

import logging
import math
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

ALPHAFOLD_API_URL = "https://alphafold.ebi.ac.uk/api"
ALPHAFOLD_ENTRY_PAGE = "https://alphafold.ebi.ac.uk/entry"
UNIPROT_REST_URL = "https://rest.uniprot.org/uniprotkb"
DEFAULT_ORGANISM_ID = 9606  # human; gene symbols are ambiguous across species
MAX_SEARCH_RESOLUTIONS = 5  # AlphaFold lookups per search_concepts call

_ACCESSION = r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?"
_ACCESSION_RE = re.compile(rf"^{_ACCESSION}$")
_ENTRY_ID_RE = re.compile(rf"^AF-({_ACCESSION})-F(\d+)$")
_GENE_QUERY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
# very-low / low / confident / very-high pLDDT bands, as defined by AlphaFold DB
_BAND_KEYS = (
    ("very_low", "fractionPlddtVeryLow"),
    ("low", "fractionPlddtLow"),
    ("confident", "fractionPlddtConfident"),
    ("very_high", "fractionPlddtVeryHigh"),
)


def normalize_identifier(value: str) -> tuple[str, str] | None:
    """Classify an input as ``("accession", "P38398")``, ``("entry", "AF-P38398-F1")``
    or ``("query", text)`` for gene symbols / names. ``None`` for empty input."""
    text = (value or "").strip()
    if not text:
        return None
    for prefix in ("uniprot:", "uniprotkb:", "alphafold:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :].strip()
    upper = text.upper()
    if _ENTRY_ID_RE.match(upper):
        return "entry", upper
    if _ACCESSION_RE.match(upper):
        return "accession", upper
    return ("query", text) if text else None


def _entry_urls(entry: dict[str, Any]) -> dict[str, Any]:
    urls = {
        "model_cif": entry.get("cifUrl"),
        "model_pdb": entry.get("pdbUrl"),
        "model_bcif": entry.get("bcifUrl"),
        "pae_image": entry.get("paeImageUrl"),
        "pae_json": entry.get("paeDocUrl"),
        "plddt_json": entry.get("plddtDocUrl"),
        "msa": entry.get("msaUrl"),
        "alphamissense_csv": entry.get("amAnnotationsUrl"),
        "page": f"{ALPHAFOLD_ENTRY_PAGE}/{entry.get('entryId')}",
    }
    return {k: v for k, v in urls.items() if v}


def _entry_summary(entry: dict[str, Any]) -> dict[str, Any]:
    """Compact, sequence-free view of one AlphaFold model entry."""
    start, end = entry.get("uniprotStart"), entry.get("uniprotEnd")
    length = end - start + 1 if isinstance(start, int) and isinstance(end, int) else None
    return {
        "entry_id": entry.get("entryId"),
        "uniprot_accession": entry.get("uniprotAccession"),
        "uniprot_id": entry.get("uniprotId"),
        "gene": entry.get("gene"),
        "description": entry.get("uniprotDescription"),
        "organism": entry.get("organismScientificName"),
        "tax_id": entry.get("taxId"),
        "sequence_length": length,
        "global_plddt": entry.get("globalMetricValue"),
        "plddt_fractions": {name: entry.get(key) for name, key in _BAND_KEYS},
        "model_version": entry.get("latestVersion"),
        "all_versions": entry.get("allVersions"),
        "model_created": entry.get("modelCreatedDate"),
        "tool": entry.get("toolUsed"),
        "reviewed": entry.get("isUniProtReviewed"),
        "reference_proteome": entry.get("isUniProtReferenceProteome"),
        "is_complex": entry.get("isComplex"),
        "sequence_checksum": entry.get("sequenceChecksum"),
        "urls": _entry_urls(entry),
    }


class AlphaFoldAdapter(KnowledgeSourceAdapter):
    """AlphaFold Protein Structure Database (predicted structures; CC BY 4.0, no key)."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = ALPHAFOLD_API_URL
        self.uniprot_url = UNIPROT_REST_URL
        self.organism_id = DEFAULT_ORGANISM_ID

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ALPHAFOLD

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Fetchers
    # ------------------------------------------------------------------

    async def _fetch_entries(self, identifier: str) -> list[dict[str, Any]]:
        """All model entries for an accession or entry id (empty on 400/404/errors)."""
        try:
            data = await self._make_request(
                f"{self.base_url}/prediction/{identifier}",
                headers={"Accept": "application/json"},
            )
        except Exception as e:
            logger.debug(f"AlphaFold prediction lookup for '{identifier}' failed: {e}")
            return []
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict) and e.get("entryId")]
        return []

    async def _resolve_accessions(self, query: str, limit: int) -> list[str]:
        """Map a gene symbol / protein name to UniProt accessions (reviewed human first)."""
        text = query.strip()
        organism = f"organism_id:{self.organism_id}"
        queries = []
        if _GENE_QUERY_RE.match(text):
            queries.append(f"gene_exact:{text} AND {organism} AND reviewed:true")
            queries.append(f"gene_exact:{text} AND {organism}")
        else:  # names and phrases: a gene_exact clause would never match them
            phrase = re.sub(r'[()"\\]', " ", text)
            queries.append(f"({phrase}) AND {organism} AND reviewed:true")
        accessions: list[str] = []
        for uniprot_query in queries:
            try:
                data = await self._make_request(
                    f"{self.uniprot_url}/search",
                    params={"query": uniprot_query, "fields": "accession", "size": limit},
                    headers={"Accept": "application/json"},
                )
            except Exception as e:
                logger.warning(f"UniProt lookup for '{query}' failed: {e}")
                return accessions
            for hit in (data or {}).get("results") or []:
                accession = hit.get("primaryAccession")
                if accession and accession not in accessions:
                    accessions.append(accession)
            if accessions:
                break
        return accessions[:limit]

    async def _entries_for(self, value: str) -> list[dict[str, Any]]:
        """Resolve any supported input (accession, entry id, gene symbol) to AlphaFold entries."""
        classified = normalize_identifier(value)
        if not classified:
            return []
        kind, text = classified
        if kind == "query":
            accessions = await self._resolve_accessions(text, 1)
            if not accessions:
                return []
            text = accessions[0]
        return await self._fetch_entries(text)

    # ------------------------------------------------------------------
    # Concept construction
    # ------------------------------------------------------------------

    def _entries_to_concept(
        self, entries: list[dict[str, Any]], wanted: str | None = None
    ) -> UnifiedConcept | None:
        if not entries:
            return None
        chosen = next((e for e in entries if wanted and e.get("entryId") == wanted), entries[0])
        summary = _entry_summary(chosen)
        entry_id = str(summary["entry_id"])
        accession = summary["uniprot_accession"]
        label = summary["description"] or summary["gene"] or entry_id
        concept = self._create_concept(entry_id, str(label), ConceptType.PROTEIN)
        concept.confidence_score = 0.9
        concept.semantic_types = ["predicted_protein_structure"]
        if concept.identifiers:  # primary identifier added by _create_concept
            concept.identifiers[0].url = f"{ALPHAFOLD_ENTRY_PAGE}/{entry_id}"
        if accession:
            concept.add_identifier(
                KnowledgeSource.UNIPROT,
                str(accession),
                summary["uniprot_id"],
                f"https://www.uniprot.org/uniprotkb/{accession}",
            )
        concept.synonyms = [
            s
            for s in dict.fromkeys(
                [summary["gene"], summary["uniprot_id"], accession, entry_id]
            ).keys()
            if s and s != label
        ]
        concept.categories = [c for c in [summary["organism"]] if c]

        plddt = summary["global_plddt"]
        bands = summary["plddt_fractions"]
        description = f"AlphaFold v{summary['model_version']} predicted structure"
        if summary["uniprot_id"]:
            description += f" of {summary['uniprot_id']}"
        if summary["organism"]:
            description += f" ({summary['organism']})"
        if summary["sequence_length"]:
            description += f", {summary['sequence_length']} residues"
        if plddt is not None:
            description += f", mean pLDDT {plddt:.1f}"
        if bands.get("very_low") is not None:
            description += f" ({bands['very_low']:.0%} very low confidence)"
        concept.definitions = [description]

        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.ALPHAFOLD] = {
                **summary,
                "other_entries": [
                    {
                        "entry_id": e.get("entryId"),
                        "uniprot_accession": e.get("uniprotAccession"),
                        "global_plddt": e.get("globalMetricValue"),
                    }
                    for e in entries
                    if e is not chosen
                ],
            }
        return concept

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Look up predicted structures by UniProt accession, AF entry id or gene symbol/name.

        Gene symbols and names are resolved to human UniProt accessions first (Swiss-Prot
        before TrEMBL); at most ``MAX_SEARCH_RESOLUTIONS`` structures are fetched per call.
        """
        if limit <= 0:
            return []
        try:
            classified = normalize_identifier(query)
            if not classified:
                return []
            kind, text = classified
            if kind != "query":
                concept = self._entries_to_concept(await self._fetch_entries(text), text)
                return [concept] if concept else []
            accessions = await self._resolve_accessions(text, min(limit, MAX_SEARCH_RESOLUTIONS))
            concepts: list[UnifiedConcept] = []
            for accession in accessions:
                concept = self._entries_to_concept(await self._fetch_entries(accession))
                if concept:
                    concepts.append(concept)
            logger.info(f"AlphaFold search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"AlphaFold search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for a UniProt accession (``P38398``), an AlphaFold entry id
        (``AF-P38398-F1``, ``AF-P38398-2-F1`` for an isoform) or a human gene symbol."""
        try:
            classified = normalize_identifier(concept_id)
            if not classified:
                return None
            wanted = classified[1] if classified[0] == "entry" else None
            return self._entries_to_concept(await self._entries_for(concept_id), wanted)
        except Exception as e:
            logger.error(f"AlphaFold get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _experimental_structures(self, accession: str) -> list[dict[str, Any]]:
        """PDB cross-references from the UniProt record (best resolution first)."""
        try:
            data = await self._make_request(
                f"{self.uniprot_url}/{accession.split('-')[0]}",
                params={"fields": "accession,xref_pdb"},
                headers={"Accept": "application/json"},
            )
        except Exception as e:
            logger.debug(f"UniProt PDB cross-references for '{accession}' failed: {e}")
            return []
        structures = []
        for xref in (data or {}).get("uniProtKBCrossReferences") or []:
            if xref.get("database") != "PDB" or not xref.get("id"):
                continue
            props = {p.get("key"): p.get("value") for p in xref.get("properties") or []}
            resolution = props.get("Resolution")
            try:
                sort_key = float(str(resolution).split()[0])
            except (ValueError, IndexError):
                sort_key = math.inf  # NMR / unknown: after X-ray and cryo-EM
            structures.append(
                {
                    "pdb_id": xref["id"],
                    "method": props.get("Method"),
                    "resolution": resolution,
                    "chains": props.get("Chains"),
                    "_sort": sort_key,
                }
            )
        structures.sort(key=lambda s: s["_sort"])
        for s in structures:
            s.pop("_sort")
        return structures

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Protein -> predicted structures (``has_predicted_structure``) and experimental
        PDB structures from UniProt (``has_experimental_structure``).

        ``limit`` is shared: up to half goes to experimental structures when both exist.
        """
        if limit <= 0:
            return []
        try:
            entries = await self._entries_for(concept_id)
            if not entries:
                return []
            accession = str(entries[0].get("uniprotAccession") or "")
            experimental = await self._experimental_structures(accession) if accession else []

            n_experimental = min(len(experimental), limit // 2)
            n_predicted = min(len(entries), max(1, limit - n_experimental))
            n_experimental = min(len(experimental), limit - n_predicted)

            relationships: list[dict[str, Any]] = []
            for entry in entries[:n_predicted]:
                summary = _entry_summary(entry)
                relationships.append(
                    {
                        "relation_label": "has_predicted_structure",
                        "related_id": summary["entry_id"],
                        "related_name": (
                            f"AlphaFold model {summary['entry_id']} (v{summary['model_version']})"
                        ),
                        "source": "AlphaFold DB",
                        "global_plddt": summary["global_plddt"],
                        "model_url": summary["urls"].get("model_cif"),
                        "pae_image_url": summary["urls"].get("pae_image"),
                        "page_url": summary["urls"].get("page"),
                    }
                )
            for structure in experimental[:n_experimental]:
                details = ", ".join(
                    str(v)
                    for v in (structure["method"], structure["resolution"])
                    if v and v != "-"
                )
                relationships.append(
                    {
                        "relation_label": "has_experimental_structure",
                        "related_id": structure["pdb_id"],
                        "related_name": f"PDB {structure['pdb_id']}"
                        + (f" ({details})" if details else ""),
                        "source": "UniProt",
                        "method": structure["method"],
                        "resolution": structure["resolution"],
                        "chains": structure["chains"],
                        "page_url": f"https://www.rcsb.org/structure/{structure['pdb_id']}",
                    }
                )
            return relationships
        except Exception as e:
            logger.warning(f"AlphaFold get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """UniProt accession <-> AlphaFold entry id (isoform models included)."""
        try:
            classified = normalize_identifier(concept_id)
            if not classified:
                return []
            kind, text = classified
            entries = await self._entries_for(concept_id)
            if not entries:
                return []

            def mapping(from_id, to_id, from_source, to_source, mapping_type):
                return {
                    "fromId": from_id,
                    "toId": to_id,
                    "fromSource": from_source,
                    "toSource": to_source,
                    "mappingType": mapping_type,
                    "confidence": 1.0,
                }

            mappings = []
            if kind == "entry":
                entry = next((e for e in entries if e.get("entryId") == text), entries[0])
                if entry.get("uniprotAccession"):
                    mappings.append(
                        mapping(
                            entry["entryId"],
                            entry["uniprotAccession"],
                            "AlphaFold",
                            "UniProt",
                            "predicted_structure_of",
                        )
                    )
                return mappings
            from_id = text if kind == "accession" else str(entries[0].get("uniprotAccession"))
            for entry in entries:
                mappings.append(
                    mapping(
                        from_id,
                        entry["entryId"],
                        "UniProt",
                        "AlphaFold",
                        "has_predicted_structure",
                    )
                )
            return mappings
        except Exception as e:
            logger.warning(f"AlphaFold get_mappings failed for '{concept_id}': {e}")
            return []
