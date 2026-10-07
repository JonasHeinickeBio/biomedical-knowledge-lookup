"""
PubTator 3 Knowledge Source Adapter

Adapter for PubTator 3 (NCBI/NLM), which text-mines PubMed abstracts and PMC full text for
six entity types (genes, diseases, chemicals, variants, species, cell lines) and extracts
typed relations between them (treat, cause, associate, inhibit, stimulate, ...). It is a
literature-derived *silver* resource: the relations are machine-extracted, so use the
publication counts as evidence strength, not as curated truth.

API documentation: https://www.ncbi.nlm.nih.gov/research/pubtator3-api/

The API is keyless. NCBI asks for at most about 3 requests per second, which the adapter
enforces itself (see ``_min_interval``).

Identifiers
-----------
PubTator names entities ``@TYPE_Name`` (``@GENE_BRCA1``, ``@DISEASE_Fatigue_Syndrome_Chronic``)
where the name part is the preferred label with spaces and most punctuation replaced by
``_`` (variant names keep characters such as ``.`` and ``>``, and end in ``_<gene>_<species>``).
These accessions are what ``search``/``relations`` take. The adapter's ``primary_id`` is the accession; MeSH and NCBI
Gene identifiers are attached as cross-references and are also accepted as input ids
(``D015673``, ``MESH:D015673``, ``672``, ``NCBIGene:672``) by resolving them through a
one-article ``search`` call, because the entity autocomplete endpoint cannot look up by id.
"""

import asyncio
import logging
import math
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

_PUBTATOR_BASE_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
_AUTOCOMPLETE_ENDPOINT = "/entity/autocomplete/"
_SEARCH_ENDPOINT = "/search/"
_RELATIONS_ENDPOINT = "/relations"
_BIOC_ENDPOINT = "/publications/export/biocjson"

#: Entity types PubTator annotates, mapped to the library's concept types. There is no
#: dedicated variant or cell-line type, so variants are MOLECULAR_ENTITY and cell lines
#: CELL_TYPE (the closest available).
_ENTITY_TYPES: dict[str, ConceptType] = {
    "GENE": ConceptType.GENE,
    "DISEASE": ConceptType.DISEASE,
    "CHEMICAL": ConceptType.CHEMICAL,
    "VARIANT": ConceptType.MOLECULAR_ENTITY,
    "SPECIES": ConceptType.ORGANISM,
    "CELLLINE": ConceptType.CELL_TYPE,
}

_ACCESSION_RE = re.compile(r"^@(" + "|".join(_ENTITY_TYPES) + r")_(\S+)$", re.IGNORECASE)
_MESH_RE = re.compile(r"^(?:MESH:|MeSH:)?([CD]\d{4,9})$")
_GENE_ID_RE = re.compile(r"^(?:NCBIGENE:|NCBI_GENE:|NCBI:|GENE:)?(\d+)$", re.IGNORECASE)
_TAXON_RE = re.compile(r"^(?:NCBITAXON|TAXON):(\d+)$", re.IGNORECASE)
_TAG_RE = re.compile(r"</?m>")

#: Pages of 10 articles per ``search`` call; cap the loop so one ``get_publications`` call
#: stays polite (50 articles = 5 requests).
_SEARCH_PAGE_SIZE = 10
_MAX_SEARCH_PAGES = 5


class PubTatorAdapter(KnowledgeSourceAdapter):
    """Adapter for PubTator 3 entities, relations and supporting publications."""

    #: Minimum seconds between requests; PubTator documents a limit of ~3 requests/second.
    _min_interval: float = 0.34

    def __init__(self, config):
        super().__init__(config)
        self.base_url = _PUBTATOR_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.PUBTATOR

    def is_available(self) -> bool:
        return True  # PubTator 3 API is public and keyless

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str, params: dict[str, Any]) -> Any:
        """GET a PubTator endpoint, spacing requests to respect the ~3 req/s limit."""
        async with self._throttle_lock:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        return await self._make_request(f"{self.base_url}{endpoint}", params)

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def _split_accession(accession: str) -> tuple[str, str] | None:
        """Split ``@GENE_BRCA1`` into ``("GENE", "BRCA1")``; ``None`` if malformed."""
        match = _ACCESSION_RE.match(accession.strip())
        if not match:
            return None
        return match.group(1).upper(), match.group(2)

    @staticmethod
    def _label_from_accession(accession: str) -> str:
        """Best-effort display name from an accession (``Fatigue_Syndrome_Chronic`` ->
        ``Fatigue Syndrome Chronic``). Relation rows carry no names, only accessions."""
        parts = PubTatorAdapter._split_accession(accession)
        if not parts:
            return accession
        etype, name = parts
        if etype == "VARIANT":
            # @VARIANT_<variant>_<gene>_<species>: keep the variant and gene, drop species
            pieces = name.rsplit("_", 2)
            return " ".join(pieces[:2]) if len(pieces) == 3 else name
        return name.replace("_", " ")

    @staticmethod
    def _id_token(concept_id: str) -> str | None:
        """Map MeSH / NCBI Gene / NCBI Taxon ids to PubTator's ``TYPE_ID`` search token.

        MeSH ids are ambiguous between diseases and chemicals, so ``None`` is returned
        for them and the caller tries both (see ``_resolve_accession``).
        """
        gene = _GENE_ID_RE.match(concept_id)
        if gene:
            return f"GENE_{gene.group(1)}"
        taxon = _TAXON_RE.match(concept_id)
        if taxon:
            return f"SPECIES_{taxon.group(1)}"
        return None

    async def _resolve_accession(self, concept_id: str) -> str | None:
        """Turn any accepted input id into a PubTator accession (``@TYPE_Name``).

        Accessions pass through unchanged. For MeSH / NCBI Gene / NCBI Taxon ids the
        top-ranked article for ``@TYPE_<id>`` is fetched and the accession read from its
        highlighted text (``@GENE_BRCA1 @<m>GENE_672</m>``). Returns ``None`` on failure.
        """
        cid = (concept_id or "").strip()
        if cid.upper().startswith("PUBTATOR:"):
            cid = cid[len("PUBTATOR:") :].strip()
        if not cid:
            return None
        if self._split_accession(cid):
            return cid

        tokens: list[str] = []
        mesh = _MESH_RE.match(cid)
        if mesh:
            tokens = [f"DISEASE_MESH:{mesh.group(1)}", f"CHEMICAL_MESH:{mesh.group(1)}"]
        else:
            token = self._id_token(cid)
            if token:
                tokens = [token]
        for token in tokens:
            try:
                data = await self._get(_SEARCH_ENDPOINT, {"text": f"@{token}", "page": 1})
            except Exception as e:
                logger.warning(f"PubTator id resolution failed for '{concept_id}': {e}")
                return None
            pattern = re.compile(
                r"(@(?:"
                + "|".join(_ENTITY_TYPES)
                + r")_\S+)\s+@(?:<m>)?"
                + re.escape(token)
                + r"(?:</m>)?"
            )
            for article in (data or {}).get("results", []) if isinstance(data, dict) else []:
                found = pattern.search(article.get("text_hl", "") or "")
                if found:
                    return found.group(1)
        return None

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(
        self,
        query: str,
        limit: int = 20,
        entity_types: list[str] | None = None,
    ) -> list[UnifiedConcept]:
        """Search PubTator entities by name or synonym via entity autocomplete.

        Without ``entity_types`` a single unfiltered autocomplete call returns a mix of
        types ranked by PubTator (``BRCA1`` -> gene plus variants; ``fatigue`` ->
        diseases). Pass e.g. ``["GENE", "DISEASE"]`` to query each type separately (one
        request per type) when a specific type is needed.
        """
        if not query or not query.strip() or limit <= 0:
            return []
        try:
            types: list[str | None] = [None]
            if entity_types:
                types = [t.upper() for t in entity_types if t.upper() in _ENTITY_TYPES]
                if not types:
                    return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for etype in types:
                params: dict[str, Any] = {"query": query.strip(), "limit": limit}
                if etype:
                    params["concept"] = etype
                data = await self._get(_AUTOCOMPLETE_ENDPOINT, params)
                if not isinstance(data, list):
                    continue
                for hit in data:
                    concept = self._convert_hit_to_concept(hit)
                    if concept and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
            logger.info(f"PubTator search for '{query}' returned {len(concepts)} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"PubTator search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get a PubTator entity by accession (``@GENE_BRCA1``), MeSH id or NCBI Gene id."""
        try:
            accession = await self._resolve_accession(concept_id)
            parts = self._split_accession(accession) if accession else None
            if not accession or not parts:
                return None
            etype, name = parts
            if etype == "VARIANT":
                # autocomplete only matches the bare variant name, not the whole accession
                query = name.rsplit("_", 2)[0] if name.count("_") >= 2 else name
            else:
                query = name.replace("_", " ")
            data = await self._get(
                _AUTOCOMPLETE_ENDPOINT, {"query": query, "concept": etype, "limit": 20}
            )
            if not isinstance(data, list):
                return None
            for hit in data:
                if str(hit.get("_id", "")).lower() == accession.lower():
                    return self._convert_hit_to_concept(hit)
            return None
        except Exception as e:
            logger.error(f"PubTator get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self,
        concept_id: str,
        limit: int = 50,
        relation_type: str | None = None,
        target_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return PubTator relations that involve the entity, strongest first.

        ``relation_label`` is PubTator's relation type (``treat``, ``cause``, ``associate``,
        ``inhibit``, ``stimulate``, ``positive_correlate``, ...) and ``publication_count``
        the number of articles supporting that exact triple. ``direction`` is ``outgoing``
        when the query entity is the relation's source and ``incoming`` when it is the
        target (``@CHEMICAL_Aspirin -treat-> @DISEASE_Stroke``). Relation rows carry only
        accessions, so ``related_name`` is derived from the accession (underscores to
        spaces) rather than the exact preferred label. The endpoint has no limit
        parameter: responses can be >100 kB for popular entities, so ``limit`` is applied
        client-side. ``relation_type`` and ``target_type`` (``GENE``/``DISEASE``/...) are
        server-side filters.
        """
        if limit <= 0:
            return []
        try:
            accession = await self._resolve_accession(concept_id)
            if not accession or not self._split_accession(accession):
                return []
            params: dict[str, Any] = {"e1": accession}
            if relation_type:
                params["type"] = relation_type.lower()
            if target_type and target_type.upper() in _ENTITY_TYPES:
                params["e2"] = target_type.upper()
            data = await self._get(_RELATIONS_ENDPOINT, params)
            if not isinstance(data, list):
                return []

            relationships: list[dict[str, Any]] = []
            seen: set[tuple[str, str, str]] = set()
            for row in data:
                source, target = row.get("source", ""), row.get("target", "")
                rel_type = row.get("type", "")
                if not source or not target or not rel_type:
                    continue
                outgoing = source.lower() == accession.lower()
                related = target if outgoing else source
                direction = "outgoing" if outgoing else "incoming"
                key = (rel_type, related, direction)
                if key in seen:
                    continue
                seen.add(key)
                parts = self._split_accession(related)
                relationships.append(
                    {
                        "relation_label": rel_type,
                        "related_id": related,
                        "related_name": self._label_from_accession(related),
                        "source": "PubTator",
                        "direction": direction,
                        "related_type": parts[0] if parts else None,
                        "publication_count": row.get("publications"),
                    }
                )
            relationships.sort(key=lambda r: r["publication_count"] or 0, reverse=True)
            return relationships[:limit]
        except Exception as e:
            logger.warning(f"PubTator get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return the entity's own database identifier(s) as cross-references.

        PubTator normalises genes to NCBI Gene, diseases and chemicals to MeSH, and
        variants to dbSNP rsIDs / LitVar ids (the latter embeds the parent NCBI gene).
        """
        try:
            concept = await self.get_concept_details(concept_id)
            if concept is None:
                return []
            source_data: Any = concept.source_data
            hit = (source_data or {}).get(KnowledgeSource.PUBTATOR) or {}
            db, db_id = str(hit.get("db", "")), str(hit.get("db_id", ""))
            if not db_id:
                return []
            mappings: list[dict[str, Any]] = []

            def add(to_id: str, to_source: str, mapping_type: str = "exact") -> None:
                mappings.append(
                    {
                        "fromId": concept.primary_id,
                        "toId": to_id,
                        "fromSource": "PubTator",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": 0.95,
                    }
                )

            if db == "ncbi_mesh":
                add(f"MESH:{db_id}", "MeSH")
            elif db == "ncbi_gene":
                add(f"NCBIGene:{db_id}", "NCBI Gene")
            elif db == "litvar":
                # "rs386833395##" or "#672#c.68_69del": rsID and/or <gene id>#<hgvs>
                rs, _, rest = db_id.partition("#")
                if rs.startswith("rs"):
                    add(rs, "dbSNP")
                gene = rest.strip("#").split("#")[0] if rest else ""
                if gene.isdigit():
                    add(f"NCBIGene:{gene}", "NCBI Gene", "parent_gene")
            else:
                add(db_id, db)
            return mappings
        except Exception as e:
            logger.warning(f"PubTator get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Evidence helpers
    # ------------------------------------------------------------------

    async def get_publications(self, entity_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return articles PubTator has annotated with the entity, best-scoring first.

        Intended for the evidence step: each item has ``pmid``, ``title``, ``journal``,
        ``date``, ``doi``, ``pmcid`` and ``score`` (PubTator's relevance score). Uses
        ``search/?text=<accession>`` at 10 articles per page, fetching at most 5 pages
        (50 articles) per call. ``entity_id`` takes the same ids as
        :meth:`get_concept_details`.
        """
        if limit <= 0:
            return []
        try:
            accession = await self._resolve_accession(entity_id)
            if not accession or not self._split_accession(accession):
                return []
            pages = min(math.ceil(limit / _SEARCH_PAGE_SIZE), _MAX_SEARCH_PAGES)
            publications: list[dict[str, Any]] = []
            seen: set[str] = set()
            for page in range(1, pages + 1):
                data = await self._get(_SEARCH_ENDPOINT, {"text": accession, "page": page})
                if not isinstance(data, dict):
                    break
                results = data.get("results") or []
                for article in results:
                    pmid = str(article.get("pmid") or article.get("_id") or "")
                    if not pmid or pmid in seen:
                        continue
                    seen.add(pmid)
                    publications.append(
                        {
                            "pmid": pmid,
                            "title": article.get("title", ""),
                            "journal": article.get("journal"),
                            "date": article.get("date"),
                            "doi": article.get("doi"),
                            "pmcid": article.get("pmcid"),
                            "score": article.get("score"),
                        }
                    )
                if len(publications) >= limit or not results or page >= data.get("total_pages", 0):
                    break
            return publications[:limit]
        except Exception as e:
            logger.warning(f"PubTator get_publications failed for '{entity_id}': {e}")
            return []

    async def get_publication_annotations(self, pmids: list[str]) -> dict[str, list[dict]]:
        """Fetch PubTator's entity annotations for PMIDs (BioC JSON export).

        Returns ``{pmid: [{"accession", "name", "type", "identifier", "text"}, ...]}`` with
        one entry per distinct (accession, mention text). Returns ``{}`` on failure.
        """
        ids = [str(p).strip() for p in pmids if str(p).strip().isdigit()]
        if not ids:
            return {}
        try:
            data = await self._get(_BIOC_ENDPOINT, {"pmids": ",".join(ids)})
            documents = data.get("PubTator3", []) if isinstance(data, dict) else []
            result: dict[str, list[dict]] = {}
            for doc in documents:
                found: dict[tuple[str, str], dict] = {}
                for passage in doc.get("passages", []):
                    for ann in passage.get("annotations", []):
                        infons = ann.get("infons", {})
                        accession = infons.get("accession") or ""
                        text = ann.get("text", "")
                        found.setdefault(
                            (accession, text),
                            {
                                "accession": accession,
                                "name": infons.get("name"),
                                "type": infons.get("type"),
                                "identifier": infons.get("identifier"),
                                "text": text,
                            },
                        )
                result[str(doc.get("id", ""))] = list(found.values())
            return result
        except Exception as e:
            logger.warning(f"PubTator get_publication_annotations failed: {e}")
            return {}

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_hit_to_concept(self, hit: dict[str, Any]) -> UnifiedConcept | None:
        """Convert an autocomplete hit to a UnifiedConcept."""
        try:
            accession = hit.get("_id", "")
            name = hit.get("name", "")
            parts = self._split_accession(accession) if accession else None
            if not parts or not name:
                return None
            etype = (hit.get("biotype") or parts[0]).upper()
            concept_type = _ENTITY_TYPES.get(etype, _ENTITY_TYPES[parts[0]])

            concept = self._create_concept(accession, name, concept_type)

            match = hit.get("match", "") or ""
            plain = _TAG_RE.sub("", match)
            if plain.startswith("Matched on synonyms ") and concept.synonyms is not None:
                synonym = plain[len("Matched on synonyms ") :].strip()
                if synonym and synonym.lower() != name.lower():
                    concept.synonyms.append(synonym)

            description = hit.get("description")
            if description and concept.categories is not None:
                concept.categories.append(str(description))

            db, db_id = hit.get("db"), hit.get("db_id")
            if db == "ncbi_mesh" and db_id:
                concept.add_identifier(
                    KnowledgeSource.MESH,
                    str(db_id),
                    name,
                    f"https://meshb.nlm.nih.gov/record/ui?ui={db_id}",
                )
            elif db == "ncbi_gene" and db_id:
                concept.add_identifier(
                    KnowledgeSource.NCBI,
                    str(db_id),
                    name,
                    f"https://www.ncbi.nlm.nih.gov/gene/{db_id}",
                )

            concept.confidence_score = 0.9 if plain.startswith("Matched on name") else 0.7
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.PUBTATOR] = hit
            return concept
        except Exception as e:
            logger.error(f"Error converting PubTator result: {e}")
            return None
