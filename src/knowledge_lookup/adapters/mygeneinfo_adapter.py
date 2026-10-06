"""
MyGene.info Knowledge Source Adapter

Adapter for MyGene.info (v3), the BioThings gene annotation service. One record per
NCBI (Entrez) gene aggregates the symbol, name, aliases, summary and the identifiers
other databases use for the same gene (Ensembl, HGNC, UniProt, OMIM, PharmGKB, PDB,
HomoloGene) plus pathway memberships (KEGG, WikiPathways, Reactome, BioCarta, PID, ...).
That makes it the cheapest hub for gene-identifier linking.

API documentation: https://docs.mygene.info/en/latest/

Identifiers
-----------
``primary_id`` is the NCBI Gene id as a CURIE, ``NCBIGene:672``. MyGene.info's own
``_id`` is that number, so the id round-trips with no lookup. Every method also accepts
a bare Entrez number (``672``), ``ENSG00000012048``, ``HGNC:1100``, a UniProt accession
(``P38398``) or a gene symbol/alias (``BRCA1``); non-Entrez forms cost one extra
``/query`` request to resolve (Ensembl ids are accepted by ``/gene`` directly).

Quirks verified live (2026-10)
------------------------------
Many fields are a single value for one gene and a list for another, so every parser
goes through :func:`_as_list`: ``alias`` (str or list), ``ensembl`` (dict or list of
dicts), ``uniprot.TrEMBL`` (str or list), ``pathway.<db>`` (dict or list of dicts) and
``MIM`` / ``HGNC`` / ``entrezgene`` (always strings). Reactome pathway data is sparse in
MyGene.info (about 2,800 human genes); use :class:`ReactomeAdapter` for full coverage.

Rate limits and licence
-----------------------
Keyless; the service asks for at most about 10 requests per second per IP. Annotation
data comes from the source databases (NCBI, Ensembl, HGNC, UniProt, ...) under their own
terms; MyGene.info itself is free to use.
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

_MYGENE_BASE_URL = "https://mygene.info/v3"

# Fields requested for details and search hits. ``ensembl.gene`` (not ``ensembl``) skips
# the huge per-transcript structures; ``pathway`` and ``homologene`` are only fetched by
# get_relationships.
_CONCEPT_FIELDS = (
    "symbol,name,alias,other_names,type_of_gene,summary,entrezgene,taxid,map_location,"
    "ensembl.gene,uniprot,HGNC,MIM,pharmgkb,pdb"
)
_RELATIONSHIP_FIELDS = "symbol,pathway,homologene"

_ENTREZ_RE = re.compile(r"^(?:NCBIGENE|ENTREZ|ENTREZGENE|GENEID|NCBI)?:?\s*(\d+)$", re.I)
_ENSEMBL_RE = re.compile(r"^ENS[A-Z]*G\d{11}(?:\.\d+)?$", re.I)
_HGNC_RE = re.compile(r"^HGNC:\d+$", re.I)
_UNIPROT_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

# Pathway databases in MyGene.info: key -> (display name, URL template). Ordered by how
# useful the pathway ids are for ID linking; get_relationships emits them in this order.
_PATHWAY_DBS: dict[str, tuple[str, str]] = {
    "reactome": ("Reactome", "https://reactome.org/content/detail/{id}"),
    "wikipathways": ("WikiPathways", "https://www.wikipathways.org/pathways/{id}.html"),
    "kegg": ("KEGG", "https://www.kegg.jp/entry/{id}"),
    "biocarta": ("BioCarta", ""),
    "pid": ("PID", ""),
    "netpath": ("NetPath", ""),
    "smpdb": ("SMPDB", "https://smpdb.ca/view/{id}"),
    "pharmgkb": ("PharmGKB", "https://www.pharmgkb.org/pathway/{id}"),
    "humancyc": ("HumanCyc", ""),
}

# NCBI taxon ids that HomoloGene returns most often, for readable ortholog species.
_TAXA: dict[int, str] = {
    9606: "Homo sapiens",
    9598: "Pan troglodytes",
    9544: "Macaca mulatta",
    9615: "Canis lupus familiaris",
    9913: "Bos taurus",
    10090: "Mus musculus",
    10116: "Rattus norvegicus",
    9031: "Gallus gallus",
    8364: "Xenopus tropicalis",
    7955: "Danio rerio",
    7227: "Drosophila melanogaster",
    6239: "Caenorhabditis elegans",
    559292: "Saccharomyces cerevisiae",
}

_MAX_TREMBL_MAPPINGS = 10  # a gene can have 100+ unreviewed entries; keep the useful few
_MAX_PDB_MAPPINGS = 10
_MAX_ORTHOLOGS = 20


def _as_list(value: Any) -> list[Any]:
    """Normalise MyGene.info's "single value or list" fields to a list."""
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def _uniprot_field(hit: dict[str, Any]) -> dict[str, Any]:
    """The ``uniprot`` field: ``{"Swiss-Prot": str | list, "TrEMBL": str | list}``."""
    value = hit.get("uniprot")
    return value if isinstance(value, dict) else {}


def _ensembl_gene_ids(hit: dict[str, Any]) -> list[str]:
    """Ensembl gene ids of a hit: ``ensembl`` is a dict, or a list of dicts for multi-locus genes."""
    ids: list[str] = []
    for entry in _as_list(hit.get("ensembl")):
        gene = entry.get("gene") if isinstance(entry, dict) else None
        for gene_id in _as_list(gene):
            if isinstance(gene_id, str) and gene_id not in ids:
                ids.append(gene_id)
    return ids


class MyGeneInfoAdapter(KnowledgeSourceAdapter):
    """Adapter for MyGene.info gene annotations (human genes by default)."""

    def __init__(self, config, species: str = "human"):
        super().__init__(config)
        self.base_url = _MYGENE_BASE_URL
        # "human" restricts query hits; pass e.g. "mouse" or "all" for other organisms.
        self.species = species

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.MYGENEINFO

    def is_available(self) -> bool:
        return True  # keyless public API

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search genes by symbol, alias, name, summary text or any supported identifier.

        Identifier-shaped queries (Entrez, Ensembl, HGNC, UniProt) are resolved exactly;
        everything else is a MyGene.info free-text query, which ranks exact symbol hits
        first (``BRCA1`` returns BRCA1 before BRAP).
        """
        query = (query or "").strip()
        if not query or limit < 1:
            return []
        try:
            hits: list[dict[str, Any]]
            if _ENTREZ_RE.match(query) or _ENSEMBL_RE.match(query):
                hit = await self._fetch_gene(query)
                hits = [hit] if hit else []
            elif _HGNC_RE.match(query) or _UNIPROT_RE.match(query):
                hits = await self._query(self._identifier_query(query), size=limit)
            else:
                hits = await self._query(query, size=limit)

            concepts: list[UnifiedConcept] = []
            for hit in hits[:limit]:
                concept = self._convert_gene_to_concept(hit, confidence=0.9)
                if concept:
                    concepts.append(concept)
            logger.info(f"MyGene.info search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"MyGene.info search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get a full gene record (cross-references, aliases, summary) by any gene id."""
        try:
            hit = await self._resolve_gene(concept_id, _CONCEPT_FIELDS)
            return self._convert_gene_to_concept(hit, confidence=1.0) if hit else None
        except Exception as e:
            logger.error(f"MyGene.info get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return a gene's pathway memberships and orthologs as edges.

        - ``participates_in``: one edge per pathway across KEGG, WikiPathways, Reactome,
          BioCarta, PID, NetPath, SMPDB, PharmGKB and HumanCyc (``pathway_db`` names the
          database; the first ``limit`` edges, Reactome/WikiPathways/KEGG first).
        - ``ortholog``: HomoloGene orthologs (``related_id`` ``NCBIGene:<id>``, ``species``
          the taxon name; capped at 20). Symbols come from one extra batched query and
          fall back to the id when that fails.

        Same ``{relation_label, related_id, related_name, source}`` shape as the other
        adapters; degrades to ``[]`` on any failure.
        """
        if limit < 1:
            return []
        try:
            hit = await self._resolve_gene(concept_id, _RELATIONSHIP_FIELDS)
            if not hit:
                return []
            relationships = self._pathway_edges(hit)[:limit]
            relationships.extend(await self._ortholog_edges(hit))
            return relationships
        except Exception as e:
            logger.warning(f"MyGene.info get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the gene's cross-references to other databases.

        Targets: NCBIGene, Ensembl, HGNC, UniProt (Swiss-Prot ``exact``; up to 10 TrEMBL
        entries ``related``), OMIM (gene MIM number), PharmGKB and PDB (up to 10, ``related``).
        Same ``{fromId, toId, fromSource, toSource, mappingType, confidence}`` shape as the
        Ensembl/KEGG adapters; degrades to ``[]`` on any failure.
        """
        try:
            hit = await self._resolve_gene(concept_id, _CONCEPT_FIELDS)
            if not hit:
                return []
            from_id = f"NCBIGene:{hit['_id']}"
            mappings: list[dict[str, Any]] = []

            def add(to_source: str, to_id: str, mapping_type: str = "exact") -> None:
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": to_id,
                        "fromSource": "MyGeneInfo",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": 1.0 if mapping_type == "exact" else 0.8,
                    }
                )

            for ensembl_id in _ensembl_gene_ids(hit):
                add("Ensembl", ensembl_id)
            if hit.get("HGNC"):
                add("HGNC", f"HGNC:{hit['HGNC']}")
            uniprot = _uniprot_field(hit)
            for acc in _as_list(uniprot.get("Swiss-Prot")):
                add("UniProt", str(acc))
            for acc in _as_list(uniprot.get("TrEMBL"))[:_MAX_TREMBL_MAPPINGS]:
                add("UniProt", str(acc), "related")
            if hit.get("MIM"):
                add("OMIM", f"OMIM:{hit['MIM']}")
            if hit.get("pharmgkb"):
                add("PharmGKB", str(hit["pharmgkb"]))
            for pdb_id in _as_list(hit.get("pdb"))[:_MAX_PDB_MAPPINGS]:
                add("PDB", str(pdb_id), "related")
            return mappings
        except Exception as e:
            logger.warning(f"MyGene.info get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Requests and id resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _identifier_query(identifier: str) -> str:
        """Lucene query for a non-Entrez identifier (HGNC id, UniProt accession, symbol)."""
        if _HGNC_RE.match(identifier):
            return f"HGNC:{identifier.split(':', 1)[1]}"
        if _UNIPROT_RE.match(identifier):
            return f"uniprot:{identifier.upper()}"
        quoted = identifier.replace('"', "")
        return f'symbol:"{quoted}" OR alias:"{quoted}"'

    async def _query(
        self, q: str, size: int = 5, fields: str = _CONCEPT_FIELDS
    ) -> list[dict[str, Any]]:
        """Run ``/query`` and return the hit list (empty when nothing matches)."""
        params = {"q": q, "species": self.species, "fields": fields, "size": min(size, 100)}
        data = await self._make_request(f"{self.base_url}/query", params)
        hits = data.get("hits") if isinstance(data, dict) else None
        return [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []

    async def _fetch_gene(self, gene_id: str, fields: str = _CONCEPT_FIELDS) -> dict[str, Any]:
        """GET ``/gene/{id}`` for an Entrez number or Ensembl gene id; ``{}`` when unknown."""
        match = _ENTREZ_RE.match(gene_id)
        key = match.group(1) if match else gene_id.split(".")[0].upper()
        try:
            data = await self._make_request(f"{self.base_url}/gene/{key}", {"fields": fields})
        except Exception as e:  # 404 means "no such gene": an answer, not a failure
            if getattr(e, "status", None) == 404:
                return {}
            raise
        # MyGene.info returns a list when one Ensembl id maps to several Entrez genes
        if isinstance(data, list):
            data = data[0] if data and isinstance(data[0], dict) else {}
        return data if isinstance(data, dict) and data.get("_id") else {}

    async def _resolve_gene(self, concept_id: str, fields: str) -> dict[str, Any]:
        """Resolve any supported gene identifier to one annotated gene record."""
        gene_id = (concept_id or "").strip()
        if not gene_id:
            return {}
        if _ENTREZ_RE.match(gene_id) or _ENSEMBL_RE.match(gene_id):
            return await self._fetch_gene(gene_id, fields)
        hits = await self._query(self._identifier_query(gene_id), size=5, fields=fields)
        if not hits:
            return {}
        # Prefer the exact symbol when several genes share an alias (symbol lookups only)
        wanted = gene_id.lower()
        for hit in hits:
            if str(hit.get("symbol", "")).lower() == wanted:
                return hit
        return hits[0]

    # ------------------------------------------------------------------
    # Converters
    # ------------------------------------------------------------------

    def _convert_gene_to_concept(
        self, hit: dict[str, Any], confidence: float = 1.0
    ) -> UnifiedConcept | None:
        """Convert a MyGene.info gene hit/record to a UnifiedConcept (type ``GENE``)."""
        try:
            entrez = str(hit.get("entrezgene") or hit.get("_id") or "")
            symbol = hit.get("symbol") or ""
            if not entrez or not symbol:
                return None

            concept = self._create_concept(f"NCBIGene:{entrez}", symbol, ConceptType.GENE)

            name = hit.get("name") or ""
            synonyms: list[str] = []
            for synonym in [name, *_as_list(hit.get("alias")), *_as_list(hit.get("other_names"))]:
                if isinstance(synonym, str) and synonym and synonym not in synonyms:
                    synonyms.append(synonym)
            concept.synonyms = synonyms
            if hit.get("summary"):
                concept.definitions = [str(hit["summary"])]
            categories = []
            if hit.get("map_location"):
                categories.append(f"locus:{hit['map_location']}")
            if hit.get("taxid"):
                categories.append(f"taxon:{hit['taxid']}")
            concept.categories = categories
            if hit.get("type_of_gene"):
                concept.semantic_types = [str(hit["type_of_gene"])]

            # Cross-references the library has a KnowledgeSource for
            concept.add_identifier(
                KnowledgeSource.NCBI,
                entrez,
                symbol,
                f"https://www.ncbi.nlm.nih.gov/gene/{entrez}",
            )
            for ensembl_id in _ensembl_gene_ids(hit):
                concept.add_identifier(
                    KnowledgeSource.ENSEMBL,
                    ensembl_id,
                    symbol,
                    f"https://www.ensembl.org/id/{ensembl_id}",
                )
            if hit.get("HGNC"):
                hgnc = f"HGNC:{hit['HGNC']}"
                concept.add_identifier(
                    KnowledgeSource.HGNC,
                    hgnc,
                    symbol,
                    f"https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/{hgnc}",
                )
            uniprot = _uniprot_field(hit)
            for acc in _as_list(uniprot.get("Swiss-Prot")):
                concept.add_identifier(
                    KnowledgeSource.UNIPROT,
                    str(acc),
                    symbol,
                    f"https://www.uniprot.org/uniprot/{acc}",
                )
            if hit.get("MIM"):
                concept.add_identifier(
                    KnowledgeSource.OMIM,
                    str(hit["MIM"]),
                    symbol,
                    f"https://omim.org/entry/{hit['MIM']}",
                )

            concept.confidence_score = confidence
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.MYGENEINFO] = hit
            return concept
        except Exception as e:
            logger.error(f"Error converting MyGene.info result: {e}")
            return None

    @staticmethod
    def _pathway_edges(hit: dict[str, Any]) -> list[dict[str, Any]]:
        """``participates_in`` edges from the ``pathway`` field (dict or list per database)."""
        pathways = hit.get("pathway")
        if not isinstance(pathways, dict):
            return []
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for db_key, (db_name, url_template) in _PATHWAY_DBS.items():
            for entry in _as_list(pathways.get(db_key)):
                if not isinstance(entry, dict):
                    continue
                pathway_id = str(entry.get("id") or "").strip()
                if not pathway_id or (db_key, pathway_id) in seen:
                    continue
                seen.add((db_key, pathway_id))
                edge: dict[str, Any] = {
                    "relation_label": "participates_in",
                    "related_id": pathway_id,
                    "related_name": entry.get("name") or pathway_id,
                    "source": "MyGeneInfo",
                    "pathway_db": db_name,
                }
                if url_template:
                    edge["url"] = url_template.format(id=pathway_id)
                edges.append(edge)
        return edges

    async def _ortholog_edges(self, hit: dict[str, Any]) -> list[dict[str, Any]]:
        """``ortholog`` edges from HomoloGene, with symbols from one batched query."""
        homologene = hit.get("homologene")
        genes = homologene.get("genes") if isinstance(homologene, dict) else None
        own_id = str(hit.get("_id", ""))
        orthologs: list[tuple[int, str]] = []
        for pair in _as_list(genes):
            if isinstance(pair, list) and len(pair) == 2:
                taxid, gene_id = int(pair[0]), str(pair[1])
                if gene_id != own_id and (taxid, gene_id) not in orthologs:
                    orthologs.append((taxid, gene_id))
        orthologs = orthologs[:_MAX_ORTHOLOGS]
        if not orthologs:
            return []

        symbols: dict[str, str] = {}
        try:
            batch = " OR ".join(gene_id for _, gene_id in orthologs)
            data = await self._make_request(
                f"{self.base_url}/query",
                {
                    "q": f"entrezgene:({batch})",
                    "fields": "symbol",
                    "size": len(orthologs),
                    "species": "all",
                },
            )
            for found in data.get("hits", []) if isinstance(data, dict) else []:
                if found.get("symbol"):
                    symbols[str(found.get("_id"))] = found["symbol"]
        except Exception as e:  # symbols are cosmetic: keep the edges, fall back to ids
            logger.warning(f"MyGene.info ortholog symbol lookup failed: {e}")

        return [
            {
                "relation_label": "ortholog",
                "related_id": f"NCBIGene:{gene_id}",
                "related_name": symbols.get(gene_id, f"NCBIGene:{gene_id}"),
                "source": "MyGeneInfo",
                "species": _TAXA.get(taxid, f"taxon:{taxid}"),
                "taxid": taxid,
                "homology_type": "HomoloGene",
            }
            for taxid, gene_id in orthologs
        ]
