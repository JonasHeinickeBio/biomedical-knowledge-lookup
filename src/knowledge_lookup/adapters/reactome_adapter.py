"""
Reactome Pathway Database Adapter

Integrates with the Reactome ContentService for biological pathway lookup.

Beyond search and details, :meth:`ReactomeAdapter.get_relationships` links genes and
proteins to their pathways and walks the pathway hierarchy, and
:meth:`ReactomeAdapter.get_mappings` returns cross-references. Endpoints used (all keyless,
verified live 2026-10):

- ``/data/mapping/{UniProt|ENSEMBL|HGNC|NCBI Gene}/{id}/pathways?species=9606``: lowest-level
  pathways that contain a gene/protein (404 when there are none).
- ``/data/query/{stId}/schemaClass`` (text): tells events from physical entities.
- ``/data/event/{stId}/ancestors`` (paths from the event up to its top-level pathway),
  ``/data/query/{stId}/hasEvent`` (text/TSV; direct children) and
  ``/data/participants/{stId}`` (physical entities with their UniProt/ChEBI reference
  entities; up to ~160 kB for a mid-sized pathway, so results are capped after parsing).
- ``/data/pathways/low/entity/{stId}`` for physical-entity ids.
- ``/data/query/uniprot:{acc}`` (reference entity with cross-references) and
  ``/references/mapping/{id}`` (Ensembl gene id or gene symbol to UniProt; slow, about 8 s).

The ``/data/query/{id}/{attribute}`` endpoints answer ``text/plain`` only (HTTP 406 for
``Accept: application/json``), hence the text request helper for them.
"""

import html
import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(text: Any) -> str:
    """Remove the HTML markup Reactome embeds in search hits (highlighting spans, <BR>)."""
    if not isinstance(text, str):
        return ""
    return html.unescape(_TAG_RE.sub(" ", text)).replace("  ", " ").strip()


# Reactome schema classes (search entry "type", details "schemaClass") -> ConceptType
_EVENT_TYPES: dict[str, ConceptType] = {
    "Pathway": ConceptType.PATHWAY,
    "TopLevelPathway": ConceptType.PATHWAY,
    "Reaction": ConceptType.BIOLOGICAL_PROCESS,
    "BlackBoxEvent": ConceptType.BIOLOGICAL_PROCESS,
    "Depolymerisation": ConceptType.BIOLOGICAL_PROCESS,
    "Polymerisation": ConceptType.BIOLOGICAL_PROCESS,
    "FailedReaction": ConceptType.BIOLOGICAL_PROCESS,
}


def _concept_type(schema_class: Any) -> ConceptType:
    """Map a Reactome schema class to a ConceptType (UNKNOWN when unmapped)."""
    return _EVENT_TYPES.get(schema_class, ConceptType.UNKNOWN)


# Identifier shapes understood by get_relationships / get_mappings
_STABLE_ID_RE = re.compile(r"^R-[A-Z]{3}-\d+(?:\.\d+)?$")
_UNIPROT_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})"
    r"(?:-\d+)?$"
)
_ISOFORM_RE = re.compile(r"-\d+$")
_ENSEMBL_GENE_RE = re.compile(r"^ENS[A-Z]*G\d{11}(?:\.\d+)?$", re.I)
_HGNC_ID_RE = re.compile(r"^HGNC:(\d+)$", re.I)
_ENTREZ_RE = re.compile(r"^(?:NCBIGENE|ENTREZGENE|ENTREZ|GENEID):?\s*(\d+)$|^(\d+)$", re.I)
_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,24}$")
_PREFIX_RE = re.compile(r"^(?:uniprotkb|uniprot)\s*:\s*", re.I)

# Schema classes that are events (the rest are physical entities)
_EVENT_CLASSES = frozenset(_EVENT_TYPES) | {"ReactionLikeEvent", "CellLineagePath", "Event"}

_MAX_XREFS_PER_DB = 10
_MAX_ORTHOLOG_EVENTS = 20
# Reactome reference-database names that differ from the names used in mappings elsewhere
_XREF_SOURCE_NAMES = {"ENSEMBL": "Ensembl", "Pharos - Targets": "Pharos"}


class ReactomeAdapter(KnowledgeSourceAdapter):
    """Adapter for Reactome."""

    def __init__(self, config: LookupConfig, species: str | None = "9606"):
        super().__init__(config)
        self.base_url = "https://reactome.org/ContentService"
        # NCBI taxon id (or name) that restricts gene -> pathway lookups; None = all species
        self.species = species

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.REACTOME

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Reactome for pathways."""
        try:
            url = f"{self.base_url}/search/query"
            params = {"query": query, "rows": min(limit, 100)}

            data = await self._make_request(url, params)

            concepts: list[UnifiedConcept] = []
            # The ContentService groups hits by type:
            # {"results": [{"typeName": "Pathway", "entries": [{"type": "Pathway", ...}]}]}
            for group in data.get("results", []) or []:
                for entry in group.get("entries", []) or []:
                    if len(concepts) >= limit:
                        break
                    # Only include pathways and reactions
                    if entry.get("type") in ["Pathway", "Reaction"]:
                        concept = self._convert_reactome_result_to_concept(entry)
                        if concept:
                            concepts.append(concept)

            logger.info(f"Reactome search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                # Reactome answers 404 when a query has no matches
                logger.info(f"Reactome search for '{query}' returned no matches")
                return []
            logger.error(f"Reactome search failed for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Reactome search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed pathway information from Reactome."""
        try:
            # concept_id should be Reactome ID (e.g., R-HSA-1640170)
            url = f"{self.base_url}/data/query/{concept_id}"
            data = await self._make_request(url)

            if data and "dbId" in data:
                concept = self._convert_reactome_details_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Reactome concept details for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return pathway edges for a gene/protein, or hierarchy and participants for a pathway.

        ``concept_id`` may be:

        - a UniProt accession (``P38398``), Ensembl gene id (``ENSG00000012048``), HGNC id
          (``HGNC:1100``), NCBI Gene id (``NCBIGene:672`` or ``672``) or a gene symbol
          (``BRCA1``): one ``participates_in`` edge per lowest-level pathway that contains
          the gene's products (species restricted by ``self.species``, human by default);
        - a pathway or reaction stable id (``R-HSA-109581``): ``part_of`` edges to the
          parent and further ancestor pathways (``depth`` 1 = direct parent), ``has_part``
          edges to the direct child events and ``has_participant`` edges to the UniProt
          proteins and ChEBI molecules taking part (``related_id_source`` names the database);
        - a physical-entity stable id (complex, protein, molecule): ``participates_in`` edges
          to the pathways it occurs in.

        Edges use the shared ``{relation_label, related_id, related_name, source}`` shape plus
        ``stId``, ``name`` and ``species`` for pathways. ``limit`` caps each relation kind
        separately; Reactome's own order is kept. Degrades to ``[]`` on any failure.
        """
        identifier = _PREFIX_RE.sub("", (concept_id or "").strip())
        if not identifier or limit < 1:
            return []
        try:
            if _STABLE_ID_RE.match(identifier):
                return await self._stable_id_relationships(identifier.split(".")[0], limit)
            for resource, value in self._gene_resources(identifier):
                pathways = await self._get_json(
                    f"{self.base_url}/data/mapping/{quote(resource)}/{quote(value)}/pathways",
                    self._species_params(),
                )
                if isinstance(pathways, list) and pathways:
                    return self._pathway_edges(pathways, limit)
            return []
        except Exception as e:
            logger.warning(f"Reactome get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _gene_resources(identifier: str) -> list[tuple[str, str]]:
        """Reactome mapping resources (and the id to send) worth trying for a gene id."""
        if _ENSEMBL_GENE_RE.match(identifier):
            return [("ENSEMBL", identifier.split(".")[0].upper())]
        if match := _HGNC_ID_RE.match(identifier):
            return [("HGNC", match.group(1))]
        if match := _ENTREZ_RE.match(identifier):
            return [("NCBI Gene", match.group(1) or match.group(2))]
        resources: list[tuple[str, str]] = []
        if _UNIPROT_RE.match(identifier.upper()):
            resources.append(("UniProt", identifier.upper()))
        # accession-shaped symbols exist (P2RY12), so symbols are tried after UniProt
        if _SYMBOL_RE.match(identifier):
            resources.append(("HGNC", identifier))
        return resources

    def _species_params(self) -> dict[str, Any]:
        return {"species": self.species} if self.species else {}

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET JSON; ``None`` for 404 (Reactome's "nothing found" answer)."""
        try:
            return await self._make_request(url, params)
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                return None
            raise

    async def _get_text(self, url: str) -> str:
        """GET text; ``""`` for 404."""
        try:
            return (await self._make_request_text(url)).strip()
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                return ""
            raise

    @staticmethod
    def _pathway_edge(pathway: dict[str, Any], relation_label: str) -> dict[str, Any] | None:
        st_id = pathway.get("stId")
        name = pathway.get("displayName") or ""
        if not st_id:
            return None
        return {
            "relation_label": relation_label,
            "related_id": st_id,
            "related_name": name,
            "source": "Reactome",
            "stId": st_id,
            "name": name,
            "species": pathway.get("speciesName"),
            "schema_class": pathway.get("schemaClass"),
            "is_in_disease": pathway.get("isInDisease"),
            "is_inferred": pathway.get("isInferred"),
        }

    def _pathway_edges(
        self, pathways: list[dict[str, Any]], limit: int, relation_label: str = "participates_in"
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pathway in pathways:
            edge = (
                self._pathway_edge(pathway, relation_label) if isinstance(pathway, dict) else None
            )
            if edge and edge["stId"] not in seen:
                seen.add(edge["stId"])
                edges.append(edge)
            if len(edges) >= limit:
                break
        return edges

    async def _stable_id_relationships(self, st_id: str, limit: int) -> list[dict[str, Any]]:
        schema_class = await self._get_text(f"{self.base_url}/data/query/{st_id}/schemaClass")
        if not schema_class:
            return []
        if schema_class not in _EVENT_CLASSES:
            pathways = await self._get_json(
                f"{self.base_url}/data/pathways/low/entity/{st_id}", self._species_params()
            )
            return self._pathway_edges(pathways, limit) if isinstance(pathways, list) else []

        edges = await self._ancestor_edges(st_id, limit)
        edges.extend(await self._child_edges(st_id, limit))
        edges.extend(await self._participant_edges(st_id, limit))
        return edges

    async def _ancestor_edges(self, st_id: str, limit: int) -> list[dict[str, Any]]:
        """``part_of`` edges from ``/data/event/{id}/ancestors`` (a list of paths to the top)."""
        paths = await self._get_json(f"{self.base_url}/data/event/{st_id}/ancestors")
        depths: dict[str, int] = {}
        events: dict[str, dict[str, Any]] = {}
        for path in paths if isinstance(paths, list) else []:
            # each path starts with the event itself, then its parent, then upwards
            for depth, event in enumerate(path if isinstance(path, list) else []):
                if depth == 0 or not isinstance(event, dict) or not event.get("stId"):
                    continue
                key = event["stId"]
                events.setdefault(key, event)
                depths[key] = min(depth, depths.get(key, depth))
        ordered = sorted(events, key=lambda key: depths[key])
        edges: list[dict[str, Any]] = []
        for key in ordered[:limit]:
            edge = self._pathway_edge(events[key], "part_of")
            if edge:
                edge["depth"] = depths[key]
                edges.append(edge)
        return edges

    async def _child_edges(self, st_id: str, limit: int) -> list[dict[str, Any]]:
        """``has_part`` edges from ``/data/query/{id}/hasEvent`` (TSV: stId, name, class)."""
        text = await self._get_text(f"{self.base_url}/data/query/{st_id}/hasEvent")
        edges: list[dict[str, Any]] = []
        for line in text.splitlines():
            cells = line.split("\t")
            if len(cells) < 2 or not cells[0].strip():
                continue
            edges.append(
                {
                    "relation_label": "has_part",
                    "related_id": cells[0].strip(),
                    "related_name": cells[1].strip(),
                    "source": "Reactome",
                    "stId": cells[0].strip(),
                    "name": cells[1].strip(),
                    "schema_class": cells[2].strip() if len(cells) > 2 else None,
                }
            )
            if len(edges) >= limit:
                break
        return edges

    async def _participant_edges(self, st_id: str, limit: int) -> list[dict[str, Any]]:
        """``has_participant`` edges from ``/data/participants/{id}``, one per reference entity."""
        participants = await self._get_json(f"{self.base_url}/data/participants/{st_id}")
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entity in participants if isinstance(participants, list) else []:
            for ref in entity.get("refEntities") or []:
                edge = self._participant_edge(ref, entity)
                if edge and edge["related_id"] not in seen:
                    seen.add(edge["related_id"])
                    edges.append(edge)
                if len(edges) >= limit:
                    return edges
        return edges

    @staticmethod
    def _participant_edge(ref: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any] | None:
        """Edge for one reference entity (``stId`` ``uniprot:Q12933`` / ``chebi:15377``)."""
        database, _, tail = str(ref.get("stId") or "").partition(":")
        identifier = str(ref.get("identifier") or tail)
        display = str(ref.get("displayName") or "")
        if not identifier:
            return None
        if database == "uniprot":
            related_id, source = _ISOFORM_RE.sub("", identifier), "UniProt"
            name = display.split(" ", 1)[1] if " " in display else identifier
        elif database == "chebi":
            related_id, source = f"CHEBI:{identifier}", "ChEBI"
            name = re.sub(r"\s*\[[^\]]*\]$", "", display) or related_id
        else:
            related_id, source, name = identifier, database or "Reactome", display or identifier
        edge = {
            "relation_label": "has_participant",
            "related_id": related_id,
            "related_name": name,
            "source": "Reactome",
            "related_id_source": source,
            "schema_class": ref.get("schemaClass"),
            "participant": entity.get("displayName"),
        }
        if related_id != identifier and source == "UniProt":
            edge["isoform"] = identifier
        return edge

    # ------------------------------------------------------------------
    # Mappings
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return cross-references of a gene/protein, pathway or physical entity.

        - UniProt accession: Ensembl gene and protein ids, RefSeq, PDB, Orphanet, OpenTargets,
          HPA, GeneCards, PRO and Pharos ids from the Reactome reference entity (up to 10 per
          database, ``related``), plus secondary UniProt accessions.
        - Ensembl gene id or gene symbol: first resolved to UniProt through Reactome's (slow,
          ~8 s) ``references/mapping`` endpoint, then as above; the UniProt accession itself is
          an ``exact`` mapping.
        - Pathway/event stable id: the GO biological process (``related``) and the inferred
          orthologous events in other species (``ortholog``).
        - Physical-entity stable id: the reference entity (UniProt, ChEBI, ...) and GO
          cellular component.

        HGNC numeric and NCBI Gene ids are not resolvable this way (the mapping endpoint
        matches them against unrelated cross-references) and return ``[]``; use
        :meth:`get_relationships` for pathway edges from those ids. Same
        ``{fromId, toId, fromSource, toSource, mappingType, confidence}`` shape as the other
        adapters; degrades to ``[]`` on any failure.
        """
        identifier = _PREFIX_RE.sub("", (concept_id or "").strip())
        if not identifier:
            return []
        try:
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(to_source: str, to_id: str, mapping_type: str, confidence: float) -> None:
                if to_id and (to_source, to_id) not in seen:
                    seen.add((to_source, to_id))
                    mappings.append(
                        {
                            "fromId": identifier,
                            "toId": to_id,
                            "fromSource": "Reactome",
                            "toSource": to_source,
                            "mappingType": mapping_type,
                            "confidence": confidence,
                        }
                    )

            if _STABLE_ID_RE.match(identifier):
                data = await self._get_json(
                    f"{self.base_url}/data/query/{identifier.split('.')[0]}"
                )
                self._add_event_mappings(data, add)
                return mappings

            for accession in await self._resolve_uniprot(identifier):
                if accession != identifier.upper():
                    add("UniProt", accession, "exact", 1.0)
                reference = await self._get_json(f"{self.base_url}/data/query/uniprot:{accession}")
                self._add_reference_mappings(reference, add)
            return mappings
        except Exception as e:
            logger.warning(f"Reactome get_mappings failed for '{concept_id}': {e}")
            return []

    async def _resolve_uniprot(self, identifier: str) -> list[str]:
        """UniProt accessions for an accession, Ensembl gene id or gene symbol."""
        if _UNIPROT_RE.match(identifier.upper()):
            return [identifier.upper()]
        if _ENSEMBL_GENE_RE.match(identifier):
            wanted = None
            lookup = identifier.split(".")[0].upper()
        elif _SYMBOL_RE.match(identifier) and not _ENTREZ_RE.match(identifier):
            wanted = identifier.upper()
            lookup = identifier
        else:
            return []
        entities = await self._get_json(f"{self.base_url}/references/mapping/{quote(lookup)}")
        accessions: list[str] = []
        for entity in entities if isinstance(entities, list) else []:
            if not str(entity.get("stId", "")).startswith("uniprot:"):
                continue
            names = [str(n).upper() for n in entity.get("geneName") or []]
            if wanted and names and wanted not in names:
                continue  # the endpoint also matches unrelated cross-references
            accession = str(entity.get("identifier") or "")
            if accession and accession not in accessions:
                accessions.append(accession)
        return accessions[:3]

    @staticmethod
    def _add_event_mappings(data: Any, add: Any) -> None:
        if not isinstance(data, dict):
            return
        for key in ("goBiologicalProcess", "goCellularComponent"):
            go = data.get(key)
            if isinstance(go, dict) and go.get("accession"):
                add("GO", f"GO:{go['accession']}", "related", 0.9)
        ref = data.get("referenceEntity")
        if isinstance(ref, dict) and ref.get("identifier"):
            database = _XREF_SOURCE_NAMES.get(ref.get("databaseName", ""), ref.get("databaseName"))
            add(str(database or "Reactome"), str(ref["identifier"]), "exact", 1.0)
        for event in (data.get("orthologousEvent") or [])[:_MAX_ORTHOLOG_EVENTS]:
            if isinstance(event, dict):
                add("Reactome", str(event.get("stId") or ""), "ortholog", 0.8)

    @staticmethod
    def _add_reference_mappings(reference: Any, add: Any) -> None:
        """Cross-references of a Reactome UniProt reference entity."""
        if not isinstance(reference, dict):
            return
        counts: dict[str, int] = {}
        for xref in reference.get("crossReference") or []:
            database = str(xref.get("databaseName") or "")
            identifier = str(xref.get("identifier") or "")
            if not database or not identifier or database.startswith("ZINC"):
                continue
            if database == "ENSEMBL" and identifier.startswith("ENST"):
                continue  # transcripts add noise; the gene and protein ids are kept
            source = _XREF_SOURCE_NAMES.get(database, database)
            if counts.get(source, 0) >= _MAX_XREFS_PER_DB:
                continue
            counts[source] = counts.get(source, 0) + 1
            add(source, identifier, "exact" if identifier.startswith("ENSG") else "related", 0.9)
        for secondary in reference.get("secondaryIdentifier") or []:
            if _UNIPROT_RE.match(str(secondary)):
                add("UniProt", str(secondary), "related", 0.8)

    def _convert_reactome_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Reactome search result to unified concept."""
        try:
            st_id = result.get("stId", "")
            # Search hits wrap matched words in <span class="highlighting"> markup
            label = _strip_markup(result.get("name", ""))

            if not st_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=st_id,
                primary_label=label,
                concept_type=_concept_type(result.get("type")),
            )

            concept.add_identifier(
                KnowledgeSource.REACTOME,
                st_id,
                label,
                f"https://reactome.org/content/detail/{st_id}",
            )

            if "summation" in result:
                summation = _strip_markup(result["summation"])
                if summation and concept.definitions is not None:
                    concept.definitions.append(summation)

            if "species" in result:
                if concept.categories is not None:
                    concept.categories.extend(result["species"])

            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.REACTOME] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Reactome result: {e}")
            return None

    def _convert_reactome_details_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Reactome detailed concept to unified concept."""
        try:
            st_id = data.get("stId", "")
            label = data.get("displayName", "")

            if not st_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=st_id,
                primary_label=label,
                concept_type=_concept_type(data.get("schemaClass") or data.get("className")),
            )

            concept.add_identifier(
                KnowledgeSource.REACTOME,
                st_id,
                label,
                f"https://reactome.org/content/detail/{st_id}",
            )

            if "summation" in data and data["summation"]:
                if concept.definitions is not None:
                    concept.definitions.append(data["summation"][0].get("text", ""))

            concept.confidence_score = 1.0
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.REACTOME] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting Reactome details: {e}")
            return None
