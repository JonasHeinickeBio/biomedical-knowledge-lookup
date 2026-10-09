"""
Alliance of Genome Resources adapter (model-organism genes, orthologs, diseases, phenotypes).

The Alliance merges the curated data of HGNC/RGD, MGI, RGD, ZFIN, SGD, WormBase, FlyBase
and Xenbase behind one API (``https://www.alliancegenome.org/api``, keyless, release 9.1.0
of 2026-09 when verified live). Swagger: ``https://www.alliancegenome.org/openapi``.

Endpoints used, with the quirks found live:

* ``GET /search?q=&category=gene_search_result&limit=&offset=[&species=]``: gene search.
  The category value is ``gene_search_result`` (``category=gene`` silently returns
  ``{"total": 0}``). ``species`` takes one full species name (``Homo sapiens``); repeating
  the parameter means AND and returns nothing, so only one species can be filtered.
  Ranking is by relevance only (BRCA1 lists the rat gene before the human one), so results
  are re-ranked here: exact symbol first, then human, mouse, rat, zebrafish ...
  About 3 KB per hit plus ~4 KB of facet counts.
* ``GET /gene/{id}``: one gene, 17 - 46 KB, because it carries every UniProt isoform and the
  genomic location; only a few cross-references are kept. The gene description is in
  ``relatedNotes`` (MOD-provided preferred, else the automated description). An unknown id
  answers **400** (not 404).
* ``GET /gene/{id}/orthologs?limit=&page=``: a few KB. The server applies the "stringent"
  filter; a ``stringency`` parameter is accepted but changes nothing.
* ``POST /disease?geneID={id}&limit=&page=`` with a JSON body ``["{id}"]``: the
  disease annotations of that gene (there is no ``/gene/{id}/diseases``; the ``geneID``
  query parameter alone is **ignored** and returns all 55k annotations, the body filters).
  About 9 KB per annotation because each embeds resource descriptors.
* ``GET /gene/{id}/phenotypes?limit=&page=``: about 33 KB per phenotype statement, in
  alphabetical order of the statement (so a capped list is a sample, not a ranking). Terms
  are MP, HP, ZP, WBPhenotype, FBcv ... depending on the species.
* ``GET /gene/{id}/molecular-interactions?limit=&page=``: one row per *experiment*
  (BRCA1: 2,499 rows for far fewer partners), sorted alphabetically by partner, 10 KB per
  row. The capped list is therefore an alphabetical sample, not a ranking; ``total`` counts
  records. Genetic interactions (``/genetic-interactions``) are not queried.

``get_relationships`` makes four requests (orthologs, diseases, phenotypes, interactions)
spaced 0.3 s apart and returns at most 25 orthologs, 10 diseases, 10 phenotypes and 15
interaction rows (de-duplicated by partner); the caps are class attributes. A section that
fails is skipped without losing the others.

Identifiers are CURIEs with the source database prefix: ``HGNC:1100``, ``MGI:104537``,
``RGD:2218``, ``ZFIN:ZDB-GENE-990415-72``, ``SGD:S000003865``, ``WB:WBGene00004930``,
``FB:FBgn0003462``, ``Xenbase:XB-GENE-1006488``. A bare gene symbol is resolved through
search (human preferred).

Licence: the Alliance states that most of its data are CC0 1.0 and some CC BY 4.0
(see https://www.alliancegenome.org/terms-of-use); cite the Alliance (Nucleic Acids Res
2023, doi:10.1093/nar/gkac1003). No rate limit is published.
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

ALLIANCE_BASE_URL = "https://www.alliancegenome.org/api"
_GENE_PAGE_URL = "https://www.alliancegenome.org/gene/{}"

_MIN_INTERVAL = 0.3  # seconds between requests: no published limit, stay polite
_MAX_SEARCH = 50
_MAX_UNIPROT_XREFS = 5  # genes list every UniProt isoform (BRCA1: >100)

# Database prefix as typed (case-insensitive) -> the canonical Alliance prefix
_PREFIXES = {
    "hgnc": "HGNC",
    "mgi": "MGI",
    "rgd": "RGD",
    "zfin": "ZFIN",
    "sgd": "SGD",
    "wb": "WB",
    "fb": "FB",
    "xenbase": "Xenbase",
}
_ID_RE = re.compile(r"^([A-Za-z]+)\s*:\s*(\S+)$")
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,40}$")

# Common names -> the species names the search facet uses
_SPECIES_ALIASES = {
    "human": "Homo sapiens",
    "mouse": "Mus musculus",
    "rat": "Rattus norvegicus",
    "zebrafish": "Danio rerio",
    "fly": "Drosophila melanogaster",
    "fruit fly": "Drosophila melanogaster",
    "worm": "Caenorhabditis elegans",
    "yeast": "Saccharomyces cerevisiae",
    "frog": "Xenopus tropicalis",
    "xenopus": "Xenopus tropicalis",
}
# Preference order when several species carry the same symbol
_SPECIES_ORDER = [
    "Homo sapiens",
    "Mus musculus",
    "Rattus norvegicus",
    "Danio rerio",
    "Drosophila melanogaster",
    "Caenorhabditis elegans",
    "Saccharomyces cerevisiae",
    "Xenopus laevis",
    "Xenopus tropicalis",
]

# Cross-reference prefix -> (KnowledgeSource-style display name)
_XREF_SOURCES = {
    "ENSEMBL": "Ensembl",
    "NCBI_Gene": "NCBI Gene",
    "UniProtKB": "UniProt",
    "OMIM": "OMIM",
    "HGNC": "HGNC",
    "MGI": "MGI",
    "RGD": "RGD",
    "ZFIN": "ZFIN",
    "SGD": "SGD",
    "WB": "WormBase",
    "FB": "FlyBase",
    "Xenbase": "Xenbase",
    "PANTHER": "PANTHER",
}


def _text(value: Any) -> str:
    """``displayText`` of an Alliance ``{formatText, displayText}`` object, or the string."""
    if isinstance(value, dict):
        return str(value.get("displayText") or value.get("formatText") or "")
    return str(value) if value else ""


def _gene_of(record: dict[str, Any]) -> dict[str, Any]:
    """The gene object of a ``/gene/{id}`` answer (``{"gene": {...}}``), or the record itself."""
    gene = record.get("gene")
    return gene if isinstance(gene, dict) else record


def _name(value: Any) -> str:
    return str(value.get("name") or "") if isinstance(value, dict) else ""


class AllianceGenomeAdapter(KnowledgeSourceAdapter):
    """Adapter for the Alliance of Genome Resources API (genes of eight model organisms)."""

    min_request_timeout = 60.0
    #: caps for :meth:`get_relationships`; see the module docstring for payload sizes
    max_orthologs = 25
    max_diseases = 10
    max_phenotypes = 10
    max_interaction_rows = 15

    def __init__(self, config):
        super().__init__(config)
        self.base_url = ALLIANCE_BASE_URL
        self.default_species = self._normalise_species(os.getenv("ALLIANCE_SPECIES"))
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ALLIANCE

    def is_available(self) -> bool:
        return True  # public API, no key

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _throttle(self) -> None:
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._throttle()
        data = await self._make_request(f"{self.base_url}/{path}", params)
        return data if isinstance(data, dict) else {}

    async def _post_ids(self, path: str, gene_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """POST a JSON array of gene ids (the base ``_make_request`` drops falsy bodies and
        has no way to send arrays together with query parameters)."""
        await self._throttle()
        url = f"{self.base_url}/{path}"

        async def _do() -> Any:
            session = await self._get_session()
            async with session.post(url, params=params, json=[gene_id]) as response:
                response.raise_for_status()
                return json.loads(await response.text())

        data = await self._call_with_retry("alliance_post", _do)
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_species(value: str | None) -> str | None:
        text = (value or "").strip()
        if not text:
            return None
        return _SPECIES_ALIASES.get(text.casefold(), text)

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("id", "HGNC:1100")``, ``("symbol", "BRCA1")`` or ``None``.

        The database prefix is case-insensitive (``hgnc:1100``, ``Mgi:104537``); ``HGNC:``
        and other known prefixes give an id, anything else that looks like a symbol is a
        symbol. Unknown prefixes (``NCBIGene:672``) are rejected because the gene endpoint
        only knows the source-database ids.
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        match = _ID_RE.match(text)
        if match:
            prefix = _PREFIXES.get(match.group(1).casefold())
            return ("id", f"{prefix}:{match.group(2)}") if prefix else None
        if _SYMBOL_RE.match(text):
            return "symbol", text
        return None

    async def _resolve_id(self, concept_id: str) -> str | None:
        """The Alliance gene id for an id or an exact symbol (best species first)."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        if parsed[0] == "id":
            return parsed[1]
        for hit in await self._search_hits(parsed[1], 20, None):
            if str(hit.get("symbol", "")).casefold() == parsed[1].casefold() and hit.get("id"):
                return str(hit["id"])
        return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def _search_hits(
        self, query: str, rows: int, species: str | None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "category": "gene_search_result",
            "limit": min(max(rows, 20), _MAX_SEARCH),
            "offset": 0,
        }
        if species:
            params["species"] = species
        data = await self._get("search", params)
        hits = [r for r in data.get("results") or [] if isinstance(r, dict) and r.get("id")]
        needle = query.strip().casefold()

        def rank(hit: dict[str, Any]) -> tuple[int, int]:
            exact = 0 if str(hit.get("symbol", "")).casefold() == needle else 1
            species_name = str(hit.get("species", ""))
            order = (
                _SPECIES_ORDER.index(species_name)
                if species_name in _SPECIES_ORDER
                else len(_SPECIES_ORDER)
            )
            return exact, order

        return sorted(hits, key=rank)  # sorted() is stable: relevance breaks ties

    def _hit_to_concept(self, hit: dict[str, Any]) -> UnifiedConcept | None:
        gene_id = str(hit.get("id") or "")
        symbol = str(hit.get("symbol") or "")
        if not gene_id or not symbol:
            return None
        concept = self._create_concept(gene_id, symbol, ConceptType.GENE)
        name = str(hit.get("name") or "")
        synonyms = [s for s in dict.fromkeys(str(x) for x in hit.get("synonyms") or []) if s]
        if name and name not in synonyms:
            synonyms.insert(0, name)
        concept.synonyms = [s for s in synonyms if s != symbol]
        description = hit.get("geneDescription") or hit.get("automatedGeneDescription")
        concept.definitions = [str(description)] if description else []
        species = str(hit.get("species") or "")
        concept.categories = [species] if species else []
        concept.semantic_types = [str(hit["soTermName"])] if hit.get("soTermName") else []
        for identifier in (concept.identifiers or [])[:1]:
            identifier.url = _GENE_PAGE_URL.format(gene_id)
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[self.source] = {
                "name": name,
                "species": species,
                "diseases": [str(d) for d in hit.get("diseases") or []][:20],
                "cross_references": [str(x) for x in hit.get("crossReferences") or []][:20],
                "evidence_note": "model-organism curation; orthology is computational",
            }
        return concept

    async def search_concepts(
        self, query: str, limit: int = 20, species: str | None = None
    ) -> list[UnifiedConcept]:
        """Search genes by symbol, name or synonym, optionally within one species.

        ``species`` is a full name (``Mus musculus``) or an alias (``mouse``); it defaults
        to the ``ALLIANCE_SPECIES`` environment variable, else all species.
        """
        text = (query or "").strip()
        if not text or limit < 1:
            return []
        wanted = self._normalise_species(species) or self.default_species
        try:
            hits = await self._search_hits(text, limit, wanted)
        except Exception as e:
            logger.error(f"Alliance search failed for '{text}': {e}")
            return []
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for hit in hits:
            concept = self._hit_to_concept(hit)
            if concept and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concepts.append(concept)
            if len(concepts) >= limit:
                break
        logger.info(f"Alliance search for '{text}' returned {len(concepts)} concepts")
        return concepts

    # ------------------------------------------------------------------
    # Details
    # ------------------------------------------------------------------

    @staticmethod
    def _xrefs(gene: dict[str, Any]) -> list[str]:
        """Cross-reference CURIEs of a gene record, canonical UniProt first, de-duplicated,
        with at most ``_MAX_UNIPROT_XREFS`` UniProt entries (isoform lists are huge)."""
        curies: list[str] = []
        canonical = gene.get("gcrpCrossReference")
        if isinstance(canonical, dict) and canonical.get("referencedCurie"):
            curies.append(str(canonical["referencedCurie"]))
        for xref in gene.get("crossReferences") or []:
            if isinstance(xref, dict) and xref.get("referencedCurie"):
                curies.append(str(xref["referencedCurie"]))
        result: list[str] = []
        uniprot = 0
        for curie in dict.fromkeys(curies):
            prefix = curie.split(":", 1)[0]
            if prefix not in _XREF_SOURCES:
                continue
            if prefix == "UniProtKB":
                uniprot += 1
                if uniprot > _MAX_UNIPROT_XREFS:
                    continue
            result.append(curie)
        return result

    def _gene_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        gene = _gene_of(record)
        gene_id = str(gene.get("primaryExternalId") or "")
        symbol = _text(gene.get("geneSymbol"))
        if not gene_id or not symbol:
            return None
        concept = self._create_concept(gene_id, symbol, ConceptType.GENE)
        name = _text(gene.get("geneFullName"))
        synonyms = [_text(s) for s in gene.get("geneSynonyms") or []]
        if name:
            synonyms.insert(0, name)
        concept.synonyms = [s for s in dict.fromkeys(synonyms) if s and s != symbol]
        notes = {
            _name(n.get("noteType")): n.get("freeText")
            for n in gene.get("relatedNotes") or []
            if isinstance(n, dict)
        }
        description = notes.get("MOD_provided_gene_description") or notes.get(
            "automated_gene_description"
        )
        concept.definitions = [str(description)] if description else []
        taxon: dict[str, Any] = gene.get("taxon") or {}
        species = str(taxon.get("name") or "")
        concept.categories = [species] if species else []
        gene_type = _name(gene.get("geneType"))
        concept.semantic_types = [gene_type] if gene_type else []
        for identifier in (concept.identifiers or [])[:1]:
            identifier.url = _GENE_PAGE_URL.format(gene_id)
        xrefs = self._xrefs(gene)
        concept.confidence_score = 0.95
        if isinstance(concept.source_data, dict):
            location = {}
            associations = gene.get("geneGenomicLocationAssociations") or []
            if associations and isinstance(associations[0], dict):
                first = associations[0]
                chromosome = first.get("geneGenomicLocationAssociationObject") or {}
                location = {
                    "chromosome": chromosome.get("name"),
                    "start": first.get("start"),
                    "end": first.get("end"),
                    "strand": first.get("strand"),
                }
            concept.source_data[self.source] = {
                "name": name,
                "species": species,
                "taxon": taxon.get("curie"),
                "gene_type": gene_type,
                "cross_references": xrefs,
                "location": location,
                "evidence_note": "model-organism curation; orthology is computational",
            }
        return concept

    async def _fetch_gene(self, gene_id: str) -> dict[str, Any]:
        return await self._get(f"gene/{gene_id}")

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full gene record (``HGNC:1100``, ``MGI:104537``... or an exact symbol)."""
        try:
            gene_id = await self._resolve_id(concept_id)
            if gene_id is None:
                return None
            return self._gene_to_concept(await self._fetch_gene(gene_id))
        except Exception as e:
            logger.error(f"Alliance get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references of the gene: Ensembl, NCBI Gene, UniProt (canonical + up to 4),
        OMIM, PANTHER and the species database ids. ``toId`` keeps the CURIE form."""
        try:
            gene_id = await self._resolve_id(concept_id)
            if gene_id is None:
                return []
            record = await self._fetch_gene(gene_id)
            gene = _gene_of(record)
            mappings = []
            for curie in self._xrefs(gene):
                if curie == gene_id:
                    continue
                mappings.append(
                    {
                        "fromId": gene_id,
                        "toId": curie,
                        "fromSource": "Alliance",
                        "toSource": _XREF_SOURCES[curie.split(":", 1)[0]],
                        "mappingType": "xref",
                        "confidence": 0.95,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"Alliance get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Gene -> orthologs, disease annotations, phenotypes and molecular interactions.

        Predicates: ``ortholog_of``, ``associated_with_disease``, ``has_phenotype``,
        ``interacts_with``. Each section is capped (see the module docstring) and a failing
        section is skipped. Interaction rows are de-duplicated by partner; the capped list is
        an alphabetical sample of the Alliance's order, not a ranking.
        """
        try:
            gene_id = await self._resolve_id(concept_id)
        except Exception as e:
            logger.warning(f"Alliance get_relationships failed for '{concept_id}': {e}")
            return []
        if gene_id is None:
            return []
        edges: list[dict[str, Any]] = []
        for name, builder in (
            ("orthologs", self._orthologs),
            ("diseases", self._diseases),
            ("phenotypes", self._phenotypes),
            ("interactions", self._interactions),
        ):
            try:
                edges.extend(await builder(gene_id))
            except Exception as e:
                logger.warning(f"Alliance {name} failed for '{gene_id}': {e}")
        return edges

    async def _orthologs(self, gene_id: str) -> list[dict[str, Any]]:
        data = await self._get(
            f"gene/{gene_id}/orthologs", {"limit": self.max_orthologs, "page": 1}
        )
        edges = []
        for row in data.get("results") or []:
            ortho = row.get("geneToGeneOrthologyGenerated") if isinstance(row, dict) else None
            if not isinstance(ortho, dict) or not isinstance(ortho.get("objectGene"), dict):
                continue
            obj = ortho["objectGene"]
            matched = [_name(m) for m in ortho.get("predictionMethodsMatched") or []]
            not_matched = ortho.get("predictionMethodsNotMatched") or []
            taxon = obj.get("taxon") if isinstance(obj.get("taxon"), dict) else {}
            edges.append(
                {
                    "relation_label": "ortholog_of",
                    "related_id": str(obj.get("primaryExternalId") or ""),
                    "related_name": _text(obj.get("geneSymbol")),
                    "source": "ALLIANCE",
                    "related_species": taxon.get("name"),
                    "best": _name(ortho.get("isBestScore")) == "Yes",
                    "best_reverse": _name(ortho.get("isBestScoreReverse")) == "Yes",
                    "confidence": _name(ortho.get("confidence")),
                    "methods_matched": len(matched),
                    "methods_total": len(matched) + len(not_matched),
                    "methods": matched,
                    "stringency": row.get("stringencyFilter"),
                    "total_orthologs": data.get("total"),
                }
            )
        return [e for e in edges if e["related_id"]]

    async def _diseases(self, gene_id: str) -> list[dict[str, Any]]:
        data = await self._post_ids(
            "disease", gene_id, {"geneID": gene_id, "limit": self.max_diseases, "page": 1}
        )
        edges = []
        seen: set[tuple[str, str]] = set()
        for row in data.get("results") or []:
            if not isinstance(row, dict) or not isinstance(row.get("object"), dict):
                continue
            term = row["object"]
            relation = _name(row.get("relation"))
            key = (str(term.get("curie")), relation)
            if not term.get("curie") or key in seen:
                continue
            seen.add(key)
            evidence = [
                str(e.get("abbreviation") or e.get("curie") or "")
                for e in row.get("evidenceCodes") or []
                if isinstance(e, dict)
            ]
            edges.append(
                {
                    "relation_label": "associated_with_disease",
                    "related_id": str(term["curie"]),
                    "related_name": str(term.get("name") or ""),
                    "source": "ALLIANCE",
                    "association": relation,
                    "evidence_codes": [e for e in evidence if e],
                    "total_annotations": data.get("total"),
                }
            )
        return edges

    async def _phenotypes(self, gene_id: str) -> list[dict[str, Any]]:
        data = await self._get(
            f"gene/{gene_id}/phenotypes", {"limit": self.max_phenotypes, "page": 1}
        )
        edges = []
        seen: set[str] = set()
        for row in data.get("results") or []:
            if not isinstance(row, dict):
                continue
            statement = str(row.get("phenotypeStatement") or "")
            annotations = [a for a in row.get("primaryAnnotations") or [] if isinstance(a, dict)]
            term: dict[str, Any] = {}
            for annotation in annotations:
                terms = annotation.get("phenotypeTerms") or []
                if terms and isinstance(terms[0], dict):
                    term = terms[0]
                    break
            related_id = str(term.get("curie") or "")
            name = str(term.get("name") or statement)
            key = related_id or name
            if not name or key in seen:
                continue
            seen.add(key)
            pubmed = [
                str(p.get("referencedCurie") or p.get("referenceID") or "")
                for p in row.get("pubmedPublications") or []
                if isinstance(p, dict)
            ]
            edges.append(
                {
                    "relation_label": "has_phenotype",
                    "related_id": related_id,
                    "related_name": name,
                    "source": "ALLIANCE",
                    "phenotype_statement": statement,
                    "n_annotations": len(annotations),
                    "publications": [p for p in pubmed if p][:5],
                    "total_phenotypes": data.get("total"),
                }
            )
        return edges

    async def _interactions(self, gene_id: str) -> list[dict[str, Any]]:
        data = await self._get(
            f"gene/{gene_id}/molecular-interactions",
            {"limit": self.max_interaction_rows, "page": 1},
        )
        edges = []
        seen: set[str] = set()
        for row in data.get("results") or []:
            inter = row.get("geneMolecularInteraction") if isinstance(row, dict) else None
            if not isinstance(inter, dict):
                continue
            subject = inter.get("geneAssociationSubject") or {}
            obj = inter.get("geneGeneAssociationObject") or {}
            partner = obj if subject.get("primaryExternalId") == gene_id else subject
            partner_id = str(partner.get("primaryExternalId") or "")
            if not partner_id or partner_id == gene_id or partner_id in seen:
                continue  # missing partner, self-interaction or already listed
            seen.add(partner_id)
            edges.append(
                {
                    "relation_label": "interacts_with",
                    "related_id": partner_id,
                    "related_name": _text(partner.get("geneSymbol")),
                    "source": "ALLIANCE",
                    "interaction_type": _name(inter.get("interactionType")),
                    "detection_method": _name(inter.get("detectionMethod")),
                    "interaction_source": _name(inter.get("interactionSource")),
                    "total_interaction_records": data.get("total"),
                }
            )
        return edges
