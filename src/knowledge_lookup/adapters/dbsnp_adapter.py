"""
dbSNP adapter (NCBI Variation Services).

dbSNP is NCBI's catalogue of short genetic variants. Its rsIDs (``rs1801133``) are the
common currency for variants in GWAS, ClinVar, gnomAD and pharmacogenomics. This adapter
uses the Variation Services REST API (https://api.ncbi.nlm.nih.gov/variation/v0), which
returns one JSON document per rsID: placements on every assembly, per-study allele
frequencies, ClinVar records and gene/transcript consequences.

Concepts are rsIDs (``rs1801133``; bare ``1801133`` and ``dbSNP:rs...`` are accepted).
SPDI (``NC_000001.11:11796320:G:A``) and genomic HGVS (``NC_000001.11:g.11796321G>A``)
strings are resolved to rsIDs first. Merged rsIDs are followed to the surviving id
(``merged_snapshot_data.merged_into``); the original id is kept in ``source_data``.

Quirks (verified live, October 2026)
------------------------------------
* There is no free-text or gene search: only identifiers resolve, so ``search_concepts``
  returns ``[]`` for words.
* Documents are big and slow: rs1801133 is 200 KB (3-7 s), rs80357906 (BRCA1) 440 KB (~1 s).
  Responses are compacted before they are put into ``source_data``.
* Not found is HTTP 404 (``RefSNP not found``); a malformed id (``abc``) is HTTP 500, so ids
  are validated before any request is sent.
* NCBI asks for at most 1 request per second to this service (still labelled beta); the
  adapter spaces its calls accordingly. An NCBI key (``NCBI_API_KEY``, as for E-utilities)
  is sent as ``api_key`` when configured and shortens the spacing; the Variation Services
  documentation does not state a higher limit, so the effect is not verified.
* Public domain data (NCBI). ClinVar interpretations inside the record are submitter-supplied.
"""

import asyncio
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

DBSNP_API_URL = "https://api.ncbi.nlm.nih.gov/variation/v0"
# documented limit of the Variation Services; faster only if the user has an NCBI key
MIN_INTERVAL_SECONDS = 1.0
MIN_INTERVAL_WITH_KEY_SECONDS = 0.15
MAX_MERGE_HOPS = 3

_RSID_RE = re.compile(r"^(?:dbsnp:)?(?:rs)?(\d{1,12})$", re.IGNORECASE)
_SPDI_RE = re.compile(r"^(N[CGTW]_\d+\.\d+):(\d+):([ACGTN]*|\d+):([ACGTN]*|\d+)$", re.IGNORECASE)
_HGVS_RE = re.compile(r"^N[CG]_\d+\.\d+:g\.\S+$")
_CHROM_RE = re.compile(r"^NC_0{4,5}(\d{1,2})\.\d+$")

# studies shown first when trimming the (often 30+) frequency studies
_PREFERRED_STUDIES = (
    "GnomAD_genomes",
    "GnomAD_exomes",
    "TOPMED",
    "1000Genomes",
    "ExAC",
    "ALSPAC",
    "TWINSUK",
    "dbGaP_PopFreq",
)
MAX_STUDIES = 8
MAX_CLINICAL_RECORDS = 25
_UNINFORMATIVE_CONDITIONS = frozenset({"not provided", "not specified", "see cases"})
_CONDITION_ID_PRIORITY = ("MedGen", "MONDO", "OMIM", "Orphanet", "MeSH")


def parse_rsid(value: str) -> str | None:
    """Return the bare rsID number (``"1801133"``) from ``rs1801133`` / ``1801133`` forms."""
    match = _RSID_RE.match((value or "").strip())
    return match.group(1).lstrip("0") or "0" if match else None


def _chrom_from_accession(seq_id: str) -> str | None:
    if seq_id == "NC_012920.1":
        return "MT"
    match = _CHROM_RE.match(seq_id or "")
    if not match:
        return None
    number = int(match.group(1))
    return {23: "X", 24: "Y"}.get(number, str(number)) if 1 <= number <= 24 else None


def _spdi_to_str(spdi: dict[str, Any]) -> str:
    return (
        f"{spdi.get('seq_id')}:{spdi.get('position')}:"
        f"{spdi.get('deleted_sequence')}:{spdi.get('inserted_sequence')}"
    )


class DbSNPAdapter(KnowledgeSourceAdapter):
    """NCBI dbSNP through the Variation Services API (keyless, ~1 request/second)."""

    # rs documents are up to several hundred KB and sometimes take 5-10 s
    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = DBSNP_API_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DBSNP

    def is_available(self) -> bool:
        return True  # public API; an NCBI key only raises the polite request rate

    def _api_key(self) -> str | None:
        return self.config.get_api_key("ncbi") or os.getenv("NCBI_API_KEY") or None

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> dict[str, Any] | None:
        """GET ``{base}/{path}``, spacing calls to respect the 1 request/second guidance."""
        key = self._api_key()
        interval = MIN_INTERVAL_WITH_KEY_SECONDS if key else MIN_INTERVAL_SECONDS
        async with self._throttle_lock:
            wait = self._last_request + interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        try:
            data = await self._make_request(
                f"{self.base_url}/{path}",
                params={"api_key": key} if key else None,
                headers={"Accept": "application/json"},
            )
        except Exception as e:
            logger.debug(f"dbSNP request {path} failed: {e}")
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # Identifier resolution
    # ------------------------------------------------------------------

    async def _resolve_to_rsid(self, identifier: str) -> str | None:
        """Turn an rsID, SPDI or genomic HGVS string into a bare rsID number."""
        text = (identifier or "").strip()
        number = parse_rsid(text)
        if number is not None:
            return number
        spdi: str | None = None
        if _SPDI_RE.match(text):
            spdi = text
        elif _HGVS_RE.match(text):
            data = await self._get(f"hgvs/{text}/contextuals")
            spdis = ((data or {}).get("data") or {}).get("spdis") or []
            spdi = _spdi_to_str(spdis[0]) if spdis else None
        if not spdi:
            return None
        data = await self._get(f"spdi/{spdi}/rsids")
        rsids = ((data or {}).get("data") or {}).get("rsids") or []
        return str(rsids[0]) if rsids else None

    async def _fetch_refsnp(self, number: str) -> tuple[dict[str, Any], list[str]] | None:
        """Fetch a refsnp, following merges. Returns ``(document, ids_merged_through)``."""
        merged_from: list[str] = []
        current = number
        for _ in range(MAX_MERGE_HOPS + 1):
            doc = await self._get(f"refsnp/{current}")
            if not doc:
                return None
            merged_into = (doc.get("merged_snapshot_data") or {}).get("merged_into") or []
            if not merged_into:
                return doc, merged_from
            merged_from.append(current)
            current = str(merged_into[0])
        return None

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _placements(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Chromosome placements (GRCh38 first) with SPDI and HGVS per allele."""
        placements: list[dict[str, Any]] = []
        for pl in snapshot.get("placements_with_allele") or []:
            annot = pl.get("placement_annot") or {}
            traits = annot.get("seq_id_traits_by_assembly") or []
            if annot.get("seq_type") != "refseq_chromosome" or not traits:
                continue
            seq_id = pl.get("seq_id")
            alleles = [
                {
                    "spdi": _spdi_to_str((a.get("allele") or {}).get("spdi") or {}),
                    "hgvs": a.get("hgvs"),
                }
                for a in pl.get("alleles") or []
            ]
            placements.append(
                {
                    "assembly": traits[0].get("assembly_name"),
                    "seq_id": seq_id,
                    "chrom": _chrom_from_accession(seq_id or ""),
                    "is_primary": bool(pl.get("is_ptlp")),
                    "alleles": alleles,
                }
            )
        placements.sort(key=lambda p: not str(p["assembly"]).startswith("GRCh38"))
        return placements

    @staticmethod
    def _genes(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        genes: dict[str, dict[str, Any]] = {}
        for ann in snapshot.get("allele_annotations") or []:
            for assembly in ann.get("assembly_annotation") or []:
                for gene in assembly.get("genes") or []:
                    gene_id = gene.get("id")
                    if gene_id is None or str(gene_id) in genes:
                        continue
                    genes[str(gene_id)] = {
                        "gene_id": str(gene_id),
                        "symbol": gene.get("locus"),
                        "name": gene.get("name"),
                        "orientation": gene.get("orientation"),
                    }
        return list(genes.values())

    @staticmethod
    def _consequences(snapshot: dict[str, Any], mane_ids: list[str]) -> list[str]:
        """Sequence Ontology terms of the MANE Select transcripts (all transcripts if none)."""
        preferred: list[str] = []
        fallback: list[str] = []
        for ann in snapshot.get("allele_annotations") or []:
            for assembly in ann.get("assembly_annotation") or []:
                for gene in assembly.get("genes") or []:
                    for rna in gene.get("rnas") or []:
                        terms = [t.get("name") for t in rna.get("sequence_ontology") or []]
                        terms += [
                            t.get("name")
                            for t in (rna.get("protein") or {}).get("sequence_ontology") or []
                        ]
                        target = preferred if rna.get("id") in mane_ids else fallback
                        target.extend(t for t in terms if t)
        ordered = preferred or fallback
        return sorted(set(ordered), key=ordered.index)

    @staticmethod
    def _frequencies(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Per-study allele frequencies, compacted to the most informative studies."""
        studies: dict[str, dict[str, Any]] = {}
        for ann in snapshot.get("allele_annotations") or []:
            for freq in ann.get("frequency") or []:
                name = freq.get("study_name")
                total = freq.get("total_count")
                count = freq.get("allele_count")
                if not name or not total or count is None:
                    continue
                allele = (freq.get("observation") or {}).get("inserted_sequence") or "-"
                entry = studies.setdefault(name, {"study": name, "total": total, "alleles": {}})
                entry["alleles"][allele] = round(count / total, 6)
        ordered = sorted(
            studies.values(),
            key=lambda s: (
                _PREFERRED_STUDIES.index(s["study"])
                if s["study"] in _PREFERRED_STUDIES
                else len(_PREFERRED_STUDIES),
                -s["total"],
            ),
        )
        return ordered[:MAX_STUDIES]

    @staticmethod
    def _clinical(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ann in snapshot.get("allele_annotations") or []:
            for rec in ann.get("clinical") or []:
                rcv = rec.get("accession_version")
                if not rcv or rcv in seen:
                    continue
                seen.add(rcv)
                names = [n for n in rec.get("disease_names") or [] if n]
                ids = {
                    d.get("organization"): d.get("accession")
                    for d in reversed(rec.get("disease_ids") or [])
                    if d.get("organization") and d.get("accession")
                }
                records.append(
                    {
                        "rcv": rcv,
                        "allele_id": rec.get("allele_id"),
                        "variation_id": rec.get("measure_set_id"),
                        "significance": list(rec.get("clinical_significances") or []),
                        "review_status": rec.get("review_status"),
                        "conditions": names,
                        "condition_ids": {
                            org: ids[org] for org in _CONDITION_ID_PRIORITY if org in ids
                        },
                        "last_evaluated": rec.get("last_evaluated_date"),
                    }
                )
        return records

    def _doc_to_concept(
        self, doc: dict[str, Any], requested: str, merged_from: list[str]
    ) -> UnifiedConcept | None:
        number = str(doc.get("refsnp_id") or "")
        if not number:
            return None
        rsid = f"rs{number}"
        concept = self._create_concept(rsid, rsid, ConceptType.MOLECULAR_ENTITY)
        concept.confidence_score = 0.95
        concept.semantic_types = ["sequence_variant"]
        if concept.identifiers:  # the primary identifier added by _create_concept
            concept.identifiers[0].url = f"https://www.ncbi.nlm.nih.gov/snp/{rsid}"

        status = "current"
        for key, label in (
            ("withdrawn_snapshot_data", "withdrawn"),
            ("unsupported_snapshot_data", "unsupported"),
        ):
            if doc.get(key) is not None:
                status = label
        snapshot = doc.get("primary_snapshot_data") or {}
        merges = [
            f"rs{m['merged_rsid']}" for m in doc.get("dbsnp1_merges") or [] if m.get("merged_rsid")
        ]
        mane_ids = list(doc.get("mane_select_ids") or [])
        placements = self._placements(snapshot)
        genes = self._genes(snapshot)
        clinical = self._clinical(snapshot)
        significances = sorted({s for rec in clinical for s in rec["significance"]})
        consequences = self._consequences(snapshot, mane_ids)

        for gene in genes:
            concept.add_identifier(
                KnowledgeSource.NCBI,
                gene["gene_id"],
                gene["symbol"],
                f"https://www.ncbi.nlm.nih.gov/gene/{gene['gene_id']}",
            )
        concept.synonyms = merges + [
            a["hgvs"]
            for p in placements[:1]
            for a in p["alleles"][1:]
            if a.get("hgvs")  # GRCh38 genomic HGVS of the alternate alleles
        ]
        if placements:
            concept.categories = [p["assembly"] for p in placements if p["assembly"]]

        pieces = [str(snapshot.get("variant_type") or "variant").upper() + f" {rsid}"]
        if genes:
            pieces.append("in " + ", ".join(str(g["symbol"]) for g in genes[:3] if g["symbol"]))
        if consequences:
            pieces.append(f"({', '.join(consequences[:3])})")
        if significances:
            pieces.append("ClinVar: " + ", ".join(significances[:4]))
        concept.definitions = [" ".join(p for p in pieces if p)]

        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.DBSNP] = {
                "rsid": rsid,
                "requested_id": requested,
                "status": status,
                "merged_from": merged_from,
                "merged_rsids": merges,
                "variant_type": snapshot.get("variant_type"),
                "anchor": snapshot.get("anchor"),
                "created": doc.get("create_date"),
                "last_updated": doc.get("last_update_date"),
                "build": doc.get("last_update_build_id"),
                "placements": placements,
                "genes": genes,
                "consequences": consequences,
                "mane_select_ids": mane_ids,
                "allele_frequencies": self._frequencies(snapshot),
                "clinvar": clinical[:MAX_CLINICAL_RECORDS],
                "clinvar_significances": significances,
                "citation_count": len(doc.get("citations") or []),
            }
        return concept

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @staticmethod
    def _record(concept: UnifiedConcept | None) -> dict[str, Any] | None:
        """The ``source_data[DBSNP]`` record of a concept built by this adapter."""
        source_data = concept.source_data if concept else None
        record = source_data.get(KnowledgeSource.DBSNP) if isinstance(source_data, dict) else None
        return record if isinstance(record, dict) else None

    async def _load(self, identifier: str) -> tuple[dict[str, Any], str, list[str]] | None:
        number = await self._resolve_to_rsid(identifier)
        if number is None:
            return None
        fetched = await self._fetch_refsnp(number)
        if not fetched:
            return None
        doc, merged_from = fetched
        return doc, f"rs{number}", merged_from

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Resolve an rsID, SPDI or genomic HGVS string. Free text is not searchable."""
        if limit <= 0:
            return []
        concept = await self.get_concept_details(query)
        return [concept] if concept else []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for an rsID (``rs1801133`` or ``1801133``), SPDI or genomic HGVS string."""
        try:
            loaded = await self._load(concept_id)
            if not loaded:
                return None
            doc, requested, merged_from = loaded
            return self._doc_to_concept(doc, requested, merged_from)
        except Exception as e:
            logger.error(f"dbSNP get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Variant -> genes (``located_in``) and -> ClinVar conditions (``has_clinical_...``).

        Condition edges carry the submitter's significance and review status; the
        uninformative "not provided" / "not specified" conditions are skipped.
        """
        if limit <= 0:
            return []
        try:
            concept = await self.get_concept_details(concept_id)
            data = self._record(concept)
            if not data:
                return []
            relationships: list[dict[str, Any]] = []
            for gene in data["genes"]:
                relationships.append(
                    {
                        "relation_label": "located_in",
                        "related_id": gene["gene_id"],
                        "related_name": gene["symbol"] or gene["gene_id"],
                        "source": "dbSNP",
                        "id_namespace": "NCBI Gene",
                        "gene_name": gene["name"],
                    }
                )
            seen: set[tuple[str, str]] = set()
            for rec in data["clinvar"]:
                significance = ", ".join(rec["significance"]) or "unknown"
                for name in rec["conditions"]:
                    if name.strip().lower() in _UNINFORMATIVE_CONDITIONS:
                        continue
                    ids = rec["condition_ids"]
                    org = next((o for o in _CONDITION_ID_PRIORITY if o in ids), None)
                    related_id = ids[org] if org else name
                    if (related_id, significance) in seen:
                        continue
                    seen.add((related_id, significance))
                    relationships.append(
                        {
                            "relation_label": "has_clinical_association",
                            "related_id": related_id,
                            "related_name": name,
                            "source": "ClinVar via dbSNP",
                            "id_namespace": org,
                            "clinical_significance": significance,
                            "review_status": rec["review_status"],
                            "rcv": rec["rcv"],
                            "last_evaluated": rec["last_evaluated"],
                        }
                    )
            return relationships[:limit]
        except Exception as e:
            logger.warning(f"dbSNP get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """ClinVar variation/VCV/RCV ids, HGVS strings, merged rsIDs and the NCBI Gene ids."""
        try:
            concept = await self.get_concept_details(concept_id)
            data = self._record(concept)
            if not data:
                return []
            rsid = data["rsid"]
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(to_id: Any, to_source: str, mapping_type: str, **extra: Any) -> None:
                if to_id is None or (str(to_id), to_source) in seen:
                    return
                seen.add((str(to_id), to_source))
                mappings.append(
                    {
                        "fromId": rsid,
                        "toId": str(to_id),
                        "fromSource": "dbSNP",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": 1.0,
                        **extra,
                    }
                )

            for old in data["merged_from"]:
                add(f"rs{old}", "dbSNP", "merged_from")
            for old in data["merged_rsids"]:
                add(old, "dbSNP", "merged_from")
            for rec in data["clinvar"]:
                if rec.get("variation_id"):
                    variation_id = str(rec["variation_id"])
                    add(variation_id, "ClinVar", "xref", kind="variation")
                    add(f"VCV{int(variation_id):09d}", "ClinVar", "xref", kind="VCV")
                add(rec["rcv"], "ClinVar", "xref", kind="RCV", significance=rec["significance"])
            for placement in data["placements"]:
                for allele in placement["alleles"][1:]:  # [0] is the reference allele
                    add(allele["hgvs"], "HGVS", "xref", assembly=placement["assembly"])
            for gene in data["genes"]:
                add(gene["gene_id"], "NCBI", "located_in", symbol=gene["symbol"])
            return mappings
        except Exception as e:
            logger.warning(f"dbSNP get_mappings failed for '{concept_id}': {e}")
            return []
