"""
NCBI Gene Knowledge Source Adapter

Adapter for NCBI Gene through the NCBI Datasets v2 gene API
(``https://api.ncbi.nlm.nih.gov/datasets/v2/gene``). A concept is a gene (id = Entrez Gene id,
label = official symbol) with full name, synonyms, RefSeq summary, chromosome and map
location, genomic annotation, Gene Ontology terms and cross-references to HGNC (or the
organism's own nomenclature authority), Ensembl, OMIM and UniProt (Swiss-Prot).

Endpoints used (all verified live, keyless):

* ``gene/id/{ids}`` - gene reports by Entrez id (comma-separated, several at once);
* ``gene/symbol/{symbols}/taxon/{taxon}`` - gene reports by official symbol **or alias**
  (``BRCC1`` returns BRCA1 and ICE2); the taxon is a tax id or a name (``9606``, ``human``);
  an unknown symbol answers HTTP 200 with ``{}``, a malformed id HTTP 400;
* ``gene/taxon/{taxon}/dataset_report?query=...`` - free-text search over names, aliases and
  descriptions (``breast cancer`` finds 63 human genes), used to fill a search after the
  symbol lookup;
* ``gene/id/{id}/product_report`` - RefSeq transcripts and proteins. ``page_size`` and
  ``table_fields`` are ignored, so BRCA1 (368 transcripts) costs 1.4 MB and 1.5-3 s; the
  adapter therefore fetches it only for ``get_relationships`` and caps the edges;
* ``gene/id/{id}/orthologs?taxon_filter={taxon}`` - orthologs in one organism (22 KB); without
  the filter the answer is 1.3 MB.

Rate limit: the service advertises 5 requests/s without a key (``x-ratelimit-limit``) and
10/s with an NCBI key. The adapter spaces calls at 3/s keyless and 10/s when ``NCBI_API_KEY``
(or ``ncbi`` in the config's ``api_keys``) is set, sent in the ``api-key`` header, the same as
the NCBI Taxonomy and dbSNP adapters. NCBI data are in the public domain; NCBI asks users to
cite it.

When to use it instead of HGNC / Ensembl / MyGene.info: NCBI Gene covers every organism NCBI
annotates (HGNC and Ensembl-by-symbol are human-centred), carries the RefSeq curated summary
and the RefSeq transcript/protein accessions, and resolves aliases. It is slower per request
than MyGene.info and its search is by symbol/alias and a basic text match, not ranked by
relevance.
"""

import asyncio
import logging
import os
import re
import time
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

DATASETS_BASE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/gene"
GENE_URL = "https://www.ncbi.nlm.nih.gov/gene/{id}"
DEFAULT_TAXON = "9606"  # human
DEFAULT_ORTHOLOG_TAXA = ("10090",)  # mouse

_MAX_SEARCH = 100
_MAX_IDS = 100
_MAX_SYNONYMS = 50
_MAX_GO = 50
_DEFAULT_TRANSCRIPTS = 25
_MIN_INTERVAL_KEYLESS = 0.34  # 3 requests/s
_MIN_INTERVAL_KEYED = 0.11  # 10 requests/s

_PREFIX_RE = re.compile(
    r"^(?:ncbigene|ncbi_gene|geneid|gene_id|entrezgene|entrez|ncbi)\s*[:_]\s*", re.I
)
_ID_LIST_RE = re.compile(r"^\d{1,10}(?:\s*,\s*\d{1,10})*$")
_SYMBOL_LIST_RE = re.compile(r"^[A-Za-z0-9_.@-]+(?:\s*,\s*[A-Za-z0-9_.@-]+)*$")
_TAXON_RE = re.compile(r"^[A-Za-z0-9 ._-]{1,80}$")

#: nomenclature authority -> library source for the identifier on the concept.
_AUTHORITY_SOURCE = {"HGNC": KnowledgeSource.HGNC}


def _unique(values: list[Any], limit: int = _MAX_SYNONYMS) -> list[str]:
    """Strings of *values* without case-insensitive duplicates, at most *limit*."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip().casefold() not in seen:
            seen.add(value.strip().casefold())
            out.append(value.strip())
    return out[:limit]


class NCBIGeneAdapter(KnowledgeSourceAdapter):
    """NCBI Gene through the keyless NCBI Datasets v2 API (about 3 requests/s)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = DATASETS_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.NCBIGENE

    def is_available(self) -> bool:
        return True  # public API; an NCBI key only raises the polite request rate

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _api_key(self) -> str | None:
        return self.config.get_api_key("ncbi") or os.getenv("NCBI_API_KEY") or None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``{base}/{path}``, spacing calls to NCBI's rate limit."""
        api_key = self._api_key()
        interval = _MIN_INTERVAL_KEYED if api_key else _MIN_INTERVAL_KEYLESS
        headers = {"Accept": "application/json"}
        if api_key:
            headers["api-key"] = api_key
        async with self._throttle_lock:
            wait = interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(f"{self.base_url}/{path}", params, headers)
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Identifiers and report fetching
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> str | None:
        """Bare Entrez id from ``672``, ``NCBIGene:672``, ``GeneID:672`` or ``entrez_672``."""
        text = _PREFIX_RE.sub("", (concept_id or "").strip())
        if not text.isdigit() or int(text) <= 0:
            return None
        return str(int(text))

    @staticmethod
    def _taxon_value(taxon: str | int | None) -> str:
        """A tax id or organism name (``9606``, ``human``); anything odd falls back to human."""
        text = str(taxon).strip() if taxon is not None else ""
        return text if _TAXON_RE.match(text) else DEFAULT_TAXON

    @classmethod
    def _taxon_segment(cls, taxon: str | int | None) -> str:
        """The taxon as a URL path segment (names may contain spaces)."""
        return quote(cls._taxon_value(taxon), safe="")

    @staticmethod
    def _gene_of(report: Any) -> dict[str, Any] | None:
        gene = report.get("gene") if isinstance(report, dict) else None
        return gene if isinstance(gene, dict) and gene.get("gene_id") else None

    async def _genes(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Gene records from a ``reports`` answer (empty for ``{}`` = no match)."""
        data = await self._get(path, params)
        genes = (self._gene_of(r) for r in data.get("reports") or [])
        return [g for g in genes if g is not None]

    async def _genes_by_id(self, ids: list[str]) -> list[dict[str, Any]]:
        return await self._genes(f"id/{','.join(ids[:_MAX_IDS])}")

    async def _genes_by_symbol(
        self, symbols: list[str], taxon: str | int | None
    ) -> list[dict[str, Any]]:
        joined = ",".join(quote(s, safe="") for s in symbols)
        return await self._genes(f"symbol/{joined}/taxon/{self._taxon_segment(taxon)}")

    async def _gene(
        self, concept_id: str, taxon: str | int | None = None
    ) -> dict[str, Any] | None:
        """One gene by Entrez id; a non-numeric id is tried as an official symbol (an alias
        shared by several genes resolves only if exactly one matches or one is the symbol)."""
        gene_id = self._parse_id(concept_id)
        if gene_id is not None:
            genes = await self._genes_by_id([gene_id])
            return genes[0] if genes else None
        text = (concept_id or "").strip()
        if not text or text.isdigit() or not _SYMBOL_LIST_RE.match(text) or "," in text:
            return None  # empty, an invalid numeric id, or not a single symbol
        genes = await self._genes_by_symbol([text], taxon)
        exact = [g for g in genes if (g.get("symbol") or "").casefold() == text.casefold()]
        if exact:
            return exact[0]
        return genes[0] if len(genes) == 1 else None

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(
        self, query: str, limit: int = 20, taxon: str | int | None = None
    ) -> list[UnifiedConcept]:
        """Search genes by Entrez id (``672``, ``NCBIGene:672``, comma-separated), by official
        symbol or alias (``BRCA1``, ``brcc1``, ``BRCA1,TP53``) and by free text (names,
        aliases, descriptions: ``breast cancer``).

        Symbol and alias matches come first; the rest of ``limit`` is filled from the text
        search. ``taxon`` is a tax id or organism name and defaults to human (``9606``).
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        limit = min(limit, _MAX_SEARCH)
        try:
            genes: list[dict[str, Any]] = []
            id_text = _PREFIX_RE.sub("", text)
            if _ID_LIST_RE.match(id_text):
                ids = [str(int(i)) for i in re.split(r"\s*,\s*", id_text) if int(i) > 0]
                genes = await self._genes_by_id(ids) if ids else []
            else:
                if _SYMBOL_LIST_RE.match(text):
                    symbols = re.split(r"\s*,\s*", text)[:_MAX_IDS]
                    genes = await self._genes_by_symbol(symbols, taxon)
                if len(genes) < limit:
                    genes += await self._genes(
                        f"taxon/{self._taxon_segment(taxon)}/dataset_report",
                        {"query": text, "page_size": limit},
                    )
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for gene in genes:
                concept = self._convert_gene_to_concept(gene)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
            logger.info(f"NCBI Gene search for '{text}' returned {len(concepts)} genes")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"NCBI Gene search failed for '{text}': {e}")
            return []

    async def get_concept_details(
        self, concept_id: str, taxon: str | int | None = None
    ) -> UnifiedConcept | None:
        """Fetch one gene by Entrez id (``672``, ``NCBIGene:672``) or official symbol
        (``BRCA1``; ``taxon`` selects the organism, default human)."""
        try:
            gene = await self._gene(concept_id, taxon)
        except Exception as e:
            logger.warning(f"NCBI Gene get_concept_details failed for '{concept_id}': {e}")
            return None
        return self._convert_gene_to_concept(gene) if gene else None

    async def get_mappings(
        self, concept_id: str, taxon: str | int | None = None
    ) -> list[dict[str, Any]]:
        """Cross-references NCBI lists for the gene.

        ``exactMatch`` for the OBO-style ``NCBIGene:`` id, HGNC (or the organism's own
        authority, e.g. MGI, RGD, ZFIN) and Ensembl; ``xref`` for the OMIM gene entry;
        ``encodes_product`` for the reviewed UniProtKB/Swiss-Prot protein(s).
        """
        try:
            gene = await self._gene(concept_id, taxon)
        except Exception as e:
            logger.warning(f"NCBI Gene get_mappings failed for '{concept_id}': {e}")
            return []
        if not gene:
            return []
        try:
            gene_id = str(gene["gene_id"])
            mappings: list[dict[str, Any]] = []

            def add(to_id: str, to_source: str, mapping_type: str, confidence: float) -> None:
                if to_id and all(m["toId"] != to_id for m in mappings):
                    mappings.append(
                        {
                            "fromId": gene_id,
                            "toId": to_id,
                            "fromSource": "NCBIGENE",
                            "toSource": to_source,
                            "mappingType": mapping_type,
                            "confidence": confidence,
                        }
                    )

            add(f"NCBIGene:{gene_id}", "NCBIGENE", "exactMatch", 1.0)
            authority = gene.get("nomenclature_authority") or {}
            if authority.get("identifier"):
                add(
                    str(authority["identifier"]),
                    str(authority.get("authority") or "").upper() or "NOMENCLATURE",
                    "exactMatch",
                    1.0,
                )
            for ensembl in gene.get("ensembl_gene_ids") or []:
                add(str(ensembl), "ENSEMBL", "exactMatch", 1.0)
            for omim in gene.get("omim_ids") or []:
                add(f"OMIM:{omim}", "OMIM", "xref", 0.95)
            for accession in gene.get("swiss_prot_accessions") or []:
                add(str(accession), "UNIPROT", "encodes_product", 0.9)
            return mappings
        except Exception as e:
            logger.warning(f"NCBI Gene get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_relationships(
        self,
        concept_id: str,
        max_transcripts: int = _DEFAULT_TRANSCRIPTS,
        ortholog_taxa: list[str | int] | tuple[str | int, ...] | None = None,
        taxon: str | int | None = None,
    ) -> list[dict[str, Any]]:
        """Edges from the gene to its genome annotation, RefSeq products and orthologs.

        - ``located_on``: one per annotated assembly (GRCh38, T2T-CHM13 ...); ``related_id`` is
          the RefSeq chromosome accession, with ``begin``/``end``/``orientation`` (1-based,
          from the Datasets report), ``assembly_name`` and ``chromosome``.
        - ``has_transcript`` (RefSeq ``NM_``/``NR_``) and ``encodes`` (``NP_`` protein of that
          transcript): at most ``max_transcripts`` transcripts, MANE Select first (the full
          list of BRCA1 is 368 transcripts, 1.4 MB; ``0`` skips the request).
        - ``has_ortholog``: the NCBI ortholog (``related_id`` ``NCBIGene:<id>``) in each
          ``ortholog_taxa`` organism; default is mouse (``10090``), pass ``()`` for none.
          Each taxon is one extra 20 KB request.
        """
        try:
            gene = await self._gene(concept_id, taxon)
        except Exception as e:
            logger.warning(f"NCBI Gene get_relationships failed for '{concept_id}': {e}")
            return []
        if not gene:
            return []
        gene_id = str(gene["gene_id"])
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(label: str, rid: str, name: str, rtype: str, **extra: Any) -> None:
            if rid and (label, rid) not in seen:
                seen.add((label, rid))
                edges.append(
                    {
                        "relation_label": label,
                        "related_id": rid,
                        "related_name": name,
                        "related_type": rtype,
                        "source": "NCBIGENE",
                        **extra,
                    }
                )

        try:
            for annotation in gene.get("annotations") or []:
                for loc in annotation.get("genomic_locations") or []:
                    rng = loc.get("genomic_range") or {}
                    accession = loc.get("genomic_accession_version")
                    if not accession:
                        continue
                    chromosome = str(loc.get("sequence_name") or "")
                    assembly = annotation.get("assembly_name") or ""
                    add(
                        "located_on",
                        str(accession),
                        " ".join(
                            part
                            for part in (
                                f"chromosome {chromosome}".strip(),
                                f"({assembly})" if assembly else "",
                            )
                            if part
                        ),
                        "chromosome",
                        chromosome=chromosome,
                        assembly_name=assembly,
                        assembly_accession=annotation.get("assembly_accession"),
                        begin=rng.get("begin"),
                        end=rng.get("end"),
                        orientation=rng.get("orientation"),
                    )
        except Exception as e:
            logger.warning(f"NCBI Gene annotation parsing failed for '{concept_id}': {e}")

        if max_transcripts > 0:
            try:
                self._add_products(await self._products(gene_id), max_transcripts, add)
            except Exception as e:
                logger.warning(f"NCBI Gene product report failed for gene {gene_id}: {e}")

        taxa = DEFAULT_ORTHOLOG_TAXA if ortholog_taxa is None else tuple(ortholog_taxa)
        for ortholog_taxon in taxa:
            if str(ortholog_taxon) == str(gene.get("tax_id")):
                continue
            try:
                found = await self._genes(
                    f"id/{gene_id}/orthologs",
                    {"taxon_filter": self._taxon_value(ortholog_taxon)},
                )
            except Exception as e:
                logger.warning(f"NCBI Gene orthologs failed for gene {gene_id}: {e}")
                continue
            for other in found:
                if str(other["gene_id"]) != gene_id:
                    add(
                        "has_ortholog",
                        f"NCBIGene:{other['gene_id']}",
                        other.get("symbol") or str(other["gene_id"]),
                        "gene",
                        tax_id=other.get("tax_id"),
                        taxname=other.get("taxname"),
                        description=other.get("description"),
                    )
        return edges

    async def _products(self, gene_id: str) -> list[dict[str, Any]]:
        data = await self._get(f"id/{gene_id}/product_report")
        for report in data.get("reports") or []:
            product = report.get("product") if isinstance(report, dict) else None
            if isinstance(product, dict):
                return [t for t in product.get("transcripts") or [] if t.get("accession_version")]
        return []

    @staticmethod
    def _add_products(transcripts: list[dict[str, Any]], cap: int, add: Any) -> None:
        # MANE Select / Plus Clinical first, then accession order
        ordered = sorted(
            transcripts, key=lambda t: (not t.get("select_category"), t["accession_version"])
        )
        for transcript in ordered[:cap]:
            accession = transcript["accession_version"]
            select = transcript.get("select_category")
            add(
                "has_transcript",
                accession,
                transcript.get("name") or accession,
                "transcript",
                length=transcript.get("length"),
                select_category=select,
                ensembl_transcript=transcript.get("ensembl_transcript"),
                transcript_type=transcript.get("type"),
            )
            protein = transcript.get("protein") or {}
            if protein.get("accession_version"):
                name = protein.get("name") or protein["accession_version"]
                isoform = protein.get("isoform_name")
                add(
                    "encodes",
                    protein["accession_version"],
                    f"{name} ({isoform})" if isoform else name,
                    "protein",
                    length=protein.get("length"),
                    transcript=accession,
                    select_category=select,
                    ensembl_protein=protein.get("ensembl_protein"),
                )

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _go_terms(gene: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        """Compact Gene Ontology annotations: aspect -> unique ``{go_id, name, qualifier}``."""
        ontology = gene.get("gene_ontology") or {}
        out: dict[str, list[dict[str, str]]] = {}
        for aspect in ("molecular_functions", "biological_processes", "cellular_components"):
            seen: set[str] = set()
            terms: list[dict[str, str]] = []
            for term in ontology.get(aspect) or []:
                go_id = term.get("go_id")
                if go_id and go_id not in seen and len(terms) < _MAX_GO:
                    seen.add(go_id)
                    terms.append(
                        {
                            "go_id": go_id,
                            "name": term.get("name") or "",
                            "qualifier": term.get("qualifier") or "",
                        }
                    )
            if terms:
                out[aspect] = terms
        return out

    def _convert_gene_to_concept(self, gene: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a Datasets gene record to a UnifiedConcept (``source_data`` keeps the
        record's fields, the annotation and a compact GO list)."""
        try:
            gene_id = str(gene["gene_id"])
            symbol = gene.get("symbol") or ""
            name = gene.get("description") or ""
            label = symbol or name
            if not label:
                return None
            concept = self._create_concept(gene_id, label, ConceptType.GENE)

            if concept.synonyms is not None:
                concept.synonyms.extend(
                    s
                    for s in _unique(
                        [name, *(gene.get("synonyms") or []), *(gene.get("alternate_names") or [])]
                    )
                    if s.casefold() != label.casefold()
                )
            summaries = [
                s.get("description") for s in gene.get("summary") or [] if isinstance(s, dict)
            ]
            if concept.definitions is not None:
                concept.definitions.extend(s[:2000] for s in summaries if s)
            if concept.categories is not None:
                if gene.get("tax_id"):
                    concept.categories.append(f"taxon:{gene['tax_id']}")
                concept.categories.extend(f"chromosome:{c}" for c in gene.get("chromosomes") or [])
                concept.categories.extend(
                    f"locus:{m['map_value']}"
                    for m in gene.get("map_locations") or []
                    if m.get("map_value")
                )
            if gene.get("type") and concept.semantic_types is not None:
                concept.semantic_types.append(str(gene["type"]))

            authority = gene.get("nomenclature_authority") or {}
            source = _AUTHORITY_SOURCE.get(str(authority.get("authority")))
            if source is not None and authority.get("identifier"):
                concept.add_identifier(source, str(authority["identifier"]), label)
            for ensembl in gene.get("ensembl_gene_ids") or []:
                concept.add_identifier(KnowledgeSource.ENSEMBL, str(ensembl), label)
            for omim in gene.get("omim_ids") or []:
                concept.add_identifier(KnowledgeSource.OMIM, str(omim), label)
            for accession in gene.get("swiss_prot_accessions") or []:
                concept.add_identifier(KnowledgeSource.UNIPROT, str(accession), label)

            concept.confidence_score = 0.95
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.NCBIGENE] = {
                    "gene_id": gene_id,
                    "symbol": symbol,
                    "description": name,
                    "tax_id": gene.get("tax_id"),
                    "taxname": gene.get("taxname"),
                    "common_name": gene.get("common_name"),
                    "type": gene.get("type"),
                    "orientation": gene.get("orientation"),
                    "chromosomes": gene.get("chromosomes") or [],
                    "map_locations": gene.get("map_locations") or [],
                    "nomenclature_authority": authority,
                    "ensembl_gene_ids": gene.get("ensembl_gene_ids") or [],
                    "omim_ids": gene.get("omim_ids") or [],
                    "swiss_prot_accessions": gene.get("swiss_prot_accessions") or [],
                    "annotations": gene.get("annotations") or [],
                    "reference_standards": gene.get("reference_standards") or [],
                    "transcript_count": gene.get("transcript_count"),
                    "protein_count": gene.get("protein_count"),
                    "gene_groups": gene.get("gene_groups") or [],
                    "gene_ontology": self._go_terms(gene),
                    "url": GENE_URL.format(id=gene_id),
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting NCBI Gene record: {e}")
            return None
