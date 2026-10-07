"""
gnomAD adapter.

The Genome Aggregation Database (https://gnomad.broadinstitute.org) publishes allele
frequencies from >800k exomes/genomes and per-gene constraint metrics (pLI, LOEUF,
missense/LoF z-scores). This adapter talks to the browser's public GraphQL endpoint
(``POST https://gnomad.broadinstitute.org/api``), which needs no key.

Concepts
--------
* genes, keyed by Ensembl gene id (``ENSG00000012048``); symbols are accepted as input.
  ``source_data["GNOMAD"]["constraint"]`` holds the gnomAD v4 constraint metrics.
* variants, keyed by gnomAD variant id (``1-11796321-G-A``, GRCh38); rsIDs are accepted as
  input. ``source_data`` carries exome/genome/joint allele counts and frequencies, the
  ancestry-group breakdown and the transcript consequences.

Quirks (verified live, October 2026)
------------------------------------
* The schema is a GraphQL schema, so a mistyped field is an HTTP 400, an unknown gene or
  variant is HTTP 200 with ``errors`` and ``data: null``, and an unparsable ``variant_search``
  query is an HTTP 500 ("Unrecognized query"): only well-formed ids are ever searched.
* ``gene.variants`` cannot be limited server side. For BRCA1 (126 kb) it returns ~1.7 MB in
  ~15 s; huge genes (TTN, DMD) return tens of MB. ``get_relationships`` for genes therefore
  refuses genes longer than ``MAX_GENE_SPAN_BP`` and keeps only the top results.
* The API is undocumented as a public service: gnomAD enforces per-IP request and query-cost
  quotas (about 10 queries per minute is the figure quoted by the gnomAD team) and answers
  429 when exceeded, which the shared retry layer backs off from. Keep calls few.
* gnomAD states that its data are released under CC0 1.0 (check its terms of use before
  redistributing); please cite Karczewski 2020 and Chen 2024.
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"
# gnomAD v4.1 (GRCh38): 807,162 individuals (730,947 exomes + 76,215 genomes). Older releases: gnomad_r3 (GRCh38,
# genomes only), gnomad_r2_1 (GRCh37). Other valid ids are listed in the docs page.
DEFAULT_DATASET = "gnomad_r4"
REFERENCE_GENOME = "GRCh38"
# gene.variants returns every variant in the gene; refuse genes whose span would make the
# response unreasonably large (BRCA1 = 126 kb -> 1.7 MB, TTN = 281 kb -> tens of MB).
MAX_GENE_SPAN_BP = 250_000

_ENSEMBL_GENE_RE = re.compile(r"^ENSG\d{11}(?:\.\d+)?$", re.IGNORECASE)
_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_GENE_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,39}$")
_VARIANT_ID_RE = re.compile(
    r"^(?:chr)?(?P<chrom>[0-9]{1,2}|X|Y|M|MT)[-:_](?P<pos>\d+)[-:_]"
    r"(?P<ref>[ACGT]+)[-:_](?P<alt>[ACGT]+)$",
    re.IGNORECASE,
)
_CLINVAR_ID_RE = re.compile(r"^\d{1,9}$")

# Consequences that change the protein: the sensible "notable variants" of a gene.
_PROTEIN_ALTERING = frozenset(
    {
        "transcript_ablation",
        "stop_gained",
        "frameshift_variant",
        "splice_acceptor_variant",
        "splice_donor_variant",
        "start_lost",
        "stop_lost",
        "inframe_insertion",
        "inframe_deletion",
        "missense_variant",
        "protein_altering_variant",
    }
)

_GENE_FIELDS = """
  gene_id symbol name hgnc_id ncbi_id omim_id chrom start stop strand
  canonical_transcript_id
  gnomad_constraint {
    exp_lof exp_mis exp_syn obs_lof obs_mis obs_syn oe_lof oe_lof_lower oe_lof_upper
    oe_mis oe_syn lof_z mis_z syn_z pLI flags
  }
"""

_SEQ_FIELDS = (
    "ac an af homozygote_count hemizygote_count filters faf95 { popmax popmax_population }"
)

_VARIANT_BODY = """
    variant_id reference_genome chrom pos ref alt caid rsids flags
    exome { @SEQ@ }
    genome { @SEQ@ }
    joint {
      ac an homozygote_count hemizygote_count filters faf95 { popmax popmax_population }
      populations { id ac an homozygote_count }
    }
    transcript_consequences {
      gene_id gene_symbol transcript_id major_consequence hgvsc hgvsp is_canonical
      is_mane_select lof lof_flags polyphen_prediction sift_prediction
    }
""".replace("@SEQ@", _SEQ_FIELDS)

# Looked up by variant id, together with its ClinVar record (ClinVar is keyed by variant id).
_VARIANT_QUERY = (
    """
query GnomadVariant($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {@BODY@}
  clinvar: clinvar_variant(variant_id: $variantId, reference_genome: GRCh38) {
    clinvar_variation_id clinical_significance review_status gold_stars
  }
}
"""
).replace("@BODY@", _VARIANT_BODY)

# Looked up by rsID: ClinVar cannot be asked by rsID, so it is fetched in a second call.
_VARIANT_BY_RSID_QUERY = (
    """
query GnomadVariantByRsid($rsid: String!, $dataset: DatasetId!) {
  variant(rsid: $rsid, dataset: $dataset) {@BODY@}
}
"""
).replace("@BODY@", _VARIANT_BODY)

_CLINVAR_QUERY = """
query GnomadClinvar($variantId: String!) {
  clinvar_variant(variant_id: $variantId, reference_genome: GRCh38) {
    clinvar_variation_id clinical_significance review_status gold_stars
  }
}
"""

_GENE_QUERY = (
    """
query GnomadGene($geneId: String, $symbol: String) {
  gene(gene_id: $geneId, gene_symbol: $symbol, reference_genome: GRCh38) { @GENE@ }
}
"""
).replace("@GENE@", _GENE_FIELDS)

_GENE_SEARCH_QUERY = """
query GnomadGeneSearch($query: String!) {
  gene_search(query: $query, reference_genome: GRCh38) { ensembl_id symbol }
}
"""

_VARIANT_SEARCH_QUERY = """
query GnomadVariantSearch($query: String!, $dataset: DatasetId!) {
  variant_search(query: $query, dataset: $dataset) { variant_id }
}
"""

_GENE_SPAN_QUERY = """
query GnomadGeneSpan($geneId: String!) {
  gene(gene_id: $geneId, reference_genome: GRCh38) { gene_id symbol start stop }
}
"""

_GENE_VARIANTS_QUERY = """
query GnomadGeneVariants($geneId: String!, $dataset: DatasetId!) {
  gene(gene_id: $geneId, reference_genome: GRCh38) {
    variants(dataset: $dataset) {
      variant_id rsids consequence hgvsp hgvsc lof
      exome { ac an } genome { ac an }
    }
  }
}
"""


def normalize_variant_id(value: str) -> str | None:
    """Return the canonical gnomAD id (``1-55516888-G-GA``) or ``None``.

    Accepts ``chr1:55516888:G:GA`` and ``1_55516888_G_GA`` style spellings.
    """
    match = _VARIANT_ID_RE.match((value or "").strip())
    if not match:
        return None
    chrom = match.group("chrom").upper()
    chrom = "M" if chrom == "MT" else chrom
    return (
        f"{chrom}-{match.group('pos')}-{match.group('ref').upper()}-{match.group('alt').upper()}"
    )


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _allele_frequency(ac: Any, an: Any) -> float | None:
    if isinstance(ac, int) and isinstance(an, int) and an > 0:
        return ac / an
    return None


class GnomADAdapter(KnowledgeSourceAdapter):
    """gnomAD (Genome Aggregation Database) via its public GraphQL API.

    No key required; data licence CC0 1.0 per gnomAD (see module docstring).
    """

    # a cold 'all variants in a gene' query can take ~15 s
    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.api_url = GNOMAD_API_URL
        self.dataset = DEFAULT_DATASET

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.GNOMAD

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # GraphQL transport
    # ------------------------------------------------------------------

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any] | None:
        """POST a query; return ``data`` (possibly partial) or ``None`` on failure.

        gnomAD reports "not found" as HTTP 200 with ``errors`` and ``data: {field: null}``,
        so a response is only discarded when it carries no usable field at all.
        """
        try:
            payload = await self._make_request(
                self.api_url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json_data={"query": query, "variables": variables},
            )
        except Exception as e:
            logger.error(f"gnomAD GraphQL request failed: {e}")
            return None
        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        if payload.get("errors"):
            messages = "; ".join(str(err.get("message")) for err in payload["errors"][:2])
            logger.debug(f"gnomAD GraphQL errors: {messages}")
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def _classify(value: str) -> tuple[str, str] | None:
        """Return ``(kind, canonical)`` where kind is gene_id, symbol, rsid or variant."""
        text = (value or "").strip()
        if not text:
            return None
        if text.upper().startswith("GNOMAD:"):
            text = text.split(":", 1)[1].strip()
        if _ENSEMBL_GENE_RE.match(text):
            return "gene_id", text.upper().split(".")[0]
        if _RSID_RE.match(text):
            return "rsid", text.lower()
        variant_id = normalize_variant_id(text)
        if variant_id:
            return "variant", variant_id
        if _GENE_SYMBOL_RE.match(text):
            return "symbol", text.upper()
        return None

    # ------------------------------------------------------------------
    # Concept builders
    # ------------------------------------------------------------------

    def _gene_to_concept(self, gene: dict[str, Any]) -> UnifiedConcept | None:
        gene_id = gene.get("gene_id")
        symbol = gene.get("symbol")
        if not gene_id or not symbol:
            return None
        concept = self._create_concept(gene_id, symbol, ConceptType.GENE)
        concept.confidence_score = 0.9
        name = gene.get("name")
        if name:
            concept.definitions = [name]
            concept.synonyms = [name]
        concept.semantic_types = ["gene"]
        if gene.get("hgnc_id"):
            concept.add_identifier(KnowledgeSource.HGNC, gene["hgnc_id"], symbol)
        if gene.get("ncbi_id"):
            concept.add_identifier(KnowledgeSource.NCBI, str(gene["ncbi_id"]), symbol)
        if gene.get("omim_id"):
            concept.add_identifier(KnowledgeSource.OMIM, str(gene["omim_id"]), symbol)

        constraint = gene.get("gnomad_constraint") or {}
        compact_constraint = {
            key: constraint.get(key)
            for key in (
                "pLI",
                "oe_lof",
                "oe_lof_lower",
                "oe_lof_upper",
                "lof_z",
                "mis_z",
                "syn_z",
                "oe_mis",
                "oe_syn",
                "obs_lof",
                "exp_lof",
                "obs_mis",
                "exp_mis",
                "obs_syn",
                "exp_syn",
                "flags",
            )
            if key in constraint
        }
        if "oe_lof_upper" in compact_constraint:
            compact_constraint["loeuf"] = compact_constraint["oe_lof_upper"]
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.GNOMAD] = {
                "kind": "gene",
                "gene_id": gene_id,
                "symbol": symbol,
                "name": name,
                "hgnc_id": gene.get("hgnc_id"),
                "ncbi_id": gene.get("ncbi_id"),
                "omim_id": gene.get("omim_id"),
                "chrom": gene.get("chrom"),
                "start": gene.get("start"),
                "stop": gene.get("stop"),
                "strand": gene.get("strand"),
                "reference_genome": REFERENCE_GENOME,
                "canonical_transcript_id": gene.get("canonical_transcript_id"),
                "constraint": compact_constraint,
                "constraint_dataset": "gnomad_v4",
            }
        return concept

    @staticmethod
    def _sequencing_summary(block: Any) -> dict[str, Any] | None:
        if not isinstance(block, dict):
            return None
        faf = block.get("faf95") or {}
        ac, an = block.get("ac"), block.get("an")
        return {
            "ac": ac,
            "an": an,
            "af": block.get("af") if block.get("af") is not None else _allele_frequency(ac, an),
            "homozygotes": block.get("homozygote_count"),
            "hemizygotes": block.get("hemizygote_count"),
            "filters": block.get("filters") or [],
            "faf95_popmax": faf.get("popmax"),
            "faf95_popmax_population": faf.get("popmax_population"),
        }

    @staticmethod
    def _ancestry_groups(joint: Any) -> list[dict[str, Any]]:
        """Compact the ancestry-group table; sex-stratified rows (``nfe_XX``, ``XY``) are dropped."""
        groups: list[dict[str, Any]] = []
        for pop in (joint or {}).get("populations") or []:
            pop_id = str(pop.get("id") or "")
            if not pop_id or pop_id.endswith(("_XX", "_XY")) or pop_id in ("XX", "XY"):
                continue
            groups.append(
                {
                    "id": pop_id,
                    "ac": pop.get("ac"),
                    "an": pop.get("an"),
                    "af": _allele_frequency(pop.get("ac"), pop.get("an")),
                    "homozygotes": pop.get("homozygote_count"),
                }
            )
        return groups

    def _variant_to_concept(
        self, variant: dict[str, Any], clinvar: dict[str, Any] | None = None
    ) -> UnifiedConcept | None:
        variant_id = variant.get("variant_id")
        if not variant_id:
            return None
        rsids = [r for r in (variant.get("rsids") or []) if r]
        label = rsids[0] if rsids else variant_id
        concept = self._create_concept(variant_id, label, ConceptType.MOLECULAR_ENTITY)
        concept.confidence_score = 0.9
        concept.synonyms = [variant_id] + [r for r in rsids if r != label]
        concept.semantic_types = ["sequence_variant"]
        for rsid in rsids:
            concept.add_identifier(
                KnowledgeSource.DBSNP,
                rsid,
                rsid,
                f"https://www.ncbi.nlm.nih.gov/snp/{rsid}",
            )
        if clinvar and clinvar.get("clinvar_variation_id"):
            concept.add_identifier(
                KnowledgeSource.CLINVAR,
                str(clinvar["clinvar_variation_id"]),
                clinvar.get("clinical_significance"),
                f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{clinvar['clinvar_variation_id']}/",
            )

        consequences = []
        for tc in variant.get("transcript_consequences") or []:
            consequences.append(
                {
                    "gene_id": tc.get("gene_id"),
                    "gene_symbol": tc.get("gene_symbol"),
                    "transcript_id": tc.get("transcript_id"),
                    "consequence": tc.get("major_consequence"),
                    "hgvsc": tc.get("hgvsc"),
                    "hgvsp": tc.get("hgvsp"),
                    "lof": tc.get("lof"),
                    "lof_flags": tc.get("lof_flags"),
                    "polyphen": tc.get("polyphen_prediction"),
                    "sift": tc.get("sift_prediction"),
                    "canonical": bool(tc.get("is_canonical")),
                    "mane_select": bool(tc.get("is_mane_select")),
                }
            )
        consequences.sort(key=lambda c: (not c["mane_select"], not c["canonical"]))
        joint = self._sequencing_summary(variant.get("joint"))
        exome = self._sequencing_summary(variant.get("exome"))
        genome = self._sequencing_summary(variant.get("genome"))
        top = consequences[0] if consequences else None
        if top and top.get("consequence"):
            concept.categories = [top["consequence"]]
        freq = (joint or exome or genome or {}).get("af")
        concept.definitions = [
            "; ".join(
                part
                for part in (
                    f"{top['consequence'].replace('_', ' ')} in {top['gene_symbol']}"
                    if top and top.get("consequence") and top.get("gene_symbol")
                    else None,
                    f"gnomAD {self.dataset} allele frequency {freq:.3g}"
                    if freq is not None
                    else None,
                )
                if part
            )
            or f"gnomAD variant {variant_id}"
        ]
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.GNOMAD] = {
                "kind": "variant",
                "variant_id": variant_id,
                "reference_genome": variant.get("reference_genome") or REFERENCE_GENOME,
                "dataset": self.dataset,
                "chrom": variant.get("chrom"),
                "pos": variant.get("pos"),
                "ref": variant.get("ref"),
                "alt": variant.get("alt"),
                "caid": variant.get("caid"),
                "rsids": rsids,
                "flags": variant.get("flags") or [],
                "exome": exome,
                "genome": genome,
                "joint": joint,
                "ancestry_groups": self._ancestry_groups(variant.get("joint")),
                "transcript_consequences": consequences[:8],
                "clinvar": (
                    {
                        "variation_id": clinvar.get("clinvar_variation_id"),
                        "clinical_significance": clinvar.get("clinical_significance"),
                        "review_status": clinvar.get("review_status"),
                        "gold_stars": clinvar.get("gold_stars"),
                    }
                    if clinvar
                    else None
                ),
            }
        return concept

    # ------------------------------------------------------------------
    # Fetchers
    # ------------------------------------------------------------------

    async def _fetch_gene(self, kind: str, value: str) -> dict[str, Any] | None:
        variables = {"geneId": value} if kind == "gene_id" else {"symbol": value}
        data = await self._graphql(_GENE_QUERY, variables)
        gene = (data or {}).get("gene")
        return gene if isinstance(gene, dict) else None

    async def _fetch_variant(
        self, kind: str, value: str
    ) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
        if kind == "rsid":
            data = await self._graphql(
                _VARIANT_BY_RSID_QUERY,
                {"rsid": value, "dataset": self.dataset},
            )
        else:
            data = await self._graphql(
                _VARIANT_QUERY, {"variantId": value, "dataset": self.dataset}
            )
        variant = (data or {}).get("variant")
        if not isinstance(variant, dict):
            return None
        if kind == "rsid" and variant.get("variant_id"):
            data = await self._graphql(_CLINVAR_QUERY, {"variantId": variant["variant_id"]})
        clinvar = (data or {}).get("clinvar") or (data or {}).get("clinvar_variant")
        return variant, clinvar if isinstance(clinvar, dict) else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search genes (symbol/Ensembl id, prefix match) or look up a variant id / rsID.

        Free-text disease or phenotype words match nothing in gnomAD: it only indexes
        genes, variants, regions and transcripts.
        """
        if limit <= 0:
            return []
        text = (query or "").strip()
        if not text:
            return []
        try:
            classified = self._classify(text)
            if classified and classified[0] in ("rsid", "variant"):
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            if _CLINVAR_ID_RE.match(text):
                data = await self._graphql(
                    _VARIANT_SEARCH_QUERY, {"query": text, "dataset": self.dataset}
                )
                ids = [v["variant_id"] for v in (data or {}).get("variant_search") or []]
                concepts = []
                for variant_id in ids[: min(limit, 3)]:
                    concept = await self.get_concept_details(variant_id)
                    if concept:
                        concepts.append(concept)
                return concepts
            if not classified:
                return []

            data = await self._graphql(_GENE_SEARCH_QUERY, {"query": text})
            hits = (data or {}).get("gene_search") or []
            gene_ids = [h["ensembl_id"] for h in hits if h.get("ensembl_id")][:limit]
            concepts = []
            # One aliased request enriches every hit (name, constraint) instead of N calls.
            ids = [g for g in gene_ids if _ENSEMBL_GENE_RE.match(g)][:10]
            if ids:
                aliases = "\n".join(
                    f'  g{i}: gene(gene_id: "{gid}", reference_genome: GRCh38) {{ {_GENE_FIELDS} }}'
                    for i, gid in enumerate(ids)
                )
                batch = await self._graphql("query GnomadGenes {\n" + aliases + "\n}", {})
                for i in range(len(ids)):
                    gene = (batch or {}).get(f"g{i}")
                    concept = self._gene_to_concept(gene) if isinstance(gene, dict) else None
                    if concept:
                        concepts.append(concept)
            logger.info(f"gnomAD search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"gnomAD search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Details for a gene (``ENSG...`` or symbol) or variant (``1-11796321-G-A``, ``rs...``)."""
        try:
            classified = self._classify(concept_id)
            if not classified:
                return None
            kind, value = classified
            if kind in ("gene_id", "symbol"):
                gene = await self._fetch_gene(kind, value)
                return self._gene_to_concept(gene) if gene else None
            fetched = await self._fetch_variant(kind, value)
            if not fetched:
                return None
            return self._variant_to_concept(*fetched)
        except Exception as e:
            logger.error(f"gnomAD get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Gene -> most frequent protein-altering variants; variant -> gene and consequence.

        Gene results are ranked by allele frequency (exome + genome counts of the default
        dataset) among protein-altering variants and capped at ``limit``.
        """
        if limit <= 0:
            return []
        try:
            classified = self._classify(concept_id)
            if not classified:
                return []
            kind, value = classified
            if kind in ("gene_id", "symbol"):
                return await self._gene_relationships(kind, value, limit)
            return await self._variant_relationships(kind, value, limit)
        except Exception as e:
            logger.warning(f"gnomAD get_relationships failed for '{concept_id}': {e}")
            return []

    async def _gene_relationships(self, kind: str, value: str, limit: int) -> list[dict[str, Any]]:
        if kind == "symbol":
            span_query = _GENE_SPAN_QUERY.replace("$geneId: String!", "$symbol: String!").replace(
                "gene_id: $geneId", "gene_symbol: $symbol"
            )
            data = await self._graphql(span_query, {"symbol": value})
        else:
            data = await self._graphql(_GENE_SPAN_QUERY, {"geneId": value})
        gene = (data or {}).get("gene")
        if not isinstance(gene, dict):
            return []
        span = (gene.get("stop") or 0) - (gene.get("start") or 0)
        if span > MAX_GENE_SPAN_BP:
            logger.warning(
                f"gnomAD: {gene.get('symbol')} spans {span} bp (> {MAX_GENE_SPAN_BP}); "
                "skipping the full variant list"
            )
            return []

        data = await self._graphql(
            _GENE_VARIANTS_QUERY, {"geneId": gene["gene_id"], "dataset": self.dataset}
        )
        variants = ((data or {}).get("gene") or {}).get("variants") or []
        ranked: list[tuple[float, dict[str, Any]]] = []
        for v in variants:
            if v.get("consequence") not in _PROTEIN_ALTERING and v.get("lof") != "HC":
                continue
            ac = sum((v.get(k) or {}).get("ac") or 0 for k in ("exome", "genome"))
            an = sum((v.get(k) or {}).get("an") or 0 for k in ("exome", "genome"))
            frequency = _allele_frequency(ac, an)
            if frequency:
                ranked.append((frequency, {**v, "_ac": ac, "_an": an}))
        ranked.sort(key=lambda item: item[0], reverse=True)

        relationships: list[dict[str, Any]] = []
        seen: set[str] = set()
        for frequency, v in ranked:
            variant_id = v["variant_id"]
            if variant_id in seen:
                continue
            seen.add(variant_id)
            rsids = [r for r in (v.get("rsids") or []) if r]
            relationships.append(
                {
                    "relation_label": "has_variant",
                    "related_id": variant_id,
                    "related_name": rsids[0] if rsids else variant_id,
                    "source": "gnomAD",
                    "allele_frequency": frequency,
                    "allele_count": v["_ac"],
                    "allele_number": v["_an"],
                    "consequence": v.get("consequence"),
                    "hgvsp": v.get("hgvsp"),
                    "lof": v.get("lof"),
                    "dataset": self.dataset,
                }
            )
            if len(relationships) >= limit:
                break
        return relationships

    async def _variant_relationships(
        self, kind: str, value: str, limit: int
    ) -> list[dict[str, Any]]:
        fetched = await self._fetch_variant(kind, value)
        if not fetched:
            return []
        variant, _ = fetched
        relationships: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        consequences = sorted(
            variant.get("transcript_consequences") or [],
            key=lambda c: (not c.get("is_mane_select"), not c.get("is_canonical")),
        )
        for tc in consequences:
            gene_id = tc.get("gene_id")
            if gene_id and ("in_gene", gene_id) not in seen:
                seen.add(("in_gene", gene_id))
                relationships.append(
                    {
                        "relation_label": "in_gene",
                        "related_id": gene_id,
                        "related_name": tc.get("gene_symbol") or gene_id,
                        "source": "gnomAD",
                        "consequence": tc.get("major_consequence"),
                        "hgvsc": tc.get("hgvsc"),
                        "hgvsp": tc.get("hgvsp"),
                        "transcript_id": tc.get("transcript_id"),
                    }
                )
            term = tc.get("major_consequence")
            if term and ("has_consequence", term) not in seen:
                seen.add(("has_consequence", term))
                relationships.append(
                    {
                        "relation_label": "has_consequence",
                        "related_id": term,
                        "related_name": term.replace("_", " "),
                        "source": "gnomAD",
                        "gene_symbol": tc.get("gene_symbol"),
                    }
                )
        return relationships[:limit]

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references: gene -> HGNC/NCBI Gene/OMIM; variant -> dbSNP, ClinVar, ClinGen."""
        try:
            classified = self._classify(concept_id)
            if not classified:
                return []
            kind, value = classified
            mappings: list[dict[str, Any]] = []

            def add(from_id: str, to_id: Any, to_source: str, mapping_type: str, **extra: Any):
                if to_id:
                    mappings.append(
                        {
                            "fromId": from_id,
                            "toId": str(to_id),
                            "fromSource": "gnomAD",
                            "toSource": to_source,
                            "mappingType": mapping_type,
                            "confidence": 1.0,
                            **extra,
                        }
                    )

            if kind in ("gene_id", "symbol"):
                gene = await self._fetch_gene(kind, value)
                if not gene:
                    return []
                gid = gene["gene_id"]
                add(gid, gene.get("hgnc_id"), "HGNC", "xref")
                add(gid, gene.get("ncbi_id"), "NCBI", "xref")
                add(gid, gene.get("omim_id"), "OMIM", "xref")
                add(gid, gid, "Ensembl", "xref")
                return mappings

            fetched = await self._fetch_variant(kind, value)
            if not fetched:
                return []
            variant, clinvar = fetched
            vid = variant["variant_id"]
            for rsid in variant.get("rsids") or []:
                add(vid, rsid, "dbSNP", "xref")
            if clinvar:
                add(
                    vid,
                    clinvar.get("clinvar_variation_id"),
                    "ClinVar",
                    "xref",
                    clinicalSignificance=clinvar.get("clinical_significance"),
                )
            add(vid, variant.get("caid"), "ClinGen", "xref")
            return mappings
        except Exception as e:
            logger.warning(f"gnomAD get_mappings failed for '{concept_id}': {e}")
            return []
