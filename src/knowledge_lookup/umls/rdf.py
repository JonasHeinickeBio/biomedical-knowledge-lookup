"""
UMLS → RDF / SPARQL Export Module

Converts UMLS concepts and adapter results into RDF triples for knowledge
graph integration (Neo4j, Blazegraph, GraphDB).  Also provides a lightweight
SPARQL endpoint query client for remote biomedical knowledge graphs.

Features
--------
- Export UnifiedConcept → RDF/Turtle (reuses ``rdf_converter.RDFNamespaces``)
- Bulk export of adapter search results
- SPARQL endpoint querying (remote BioPortal, Wikidata, etc.)
- Round-trip compatible with the existing ``rdf_converter`` module

Usage::

    from knowledge_lookup.umls.rdf import concept_to_graph, SparqlEndpoint

    # Export a concept
    triples = concept_to_turtle(concept)
    print(triples)  # Turtle string

    # Query a SPARQL endpoint
    client = SparqlEndpoint("https://query.wikidata.org/sparql")
    results = await client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiohttp
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from ..models import ConceptType, UnifiedConcept
from ..services.rdf_converter import RDFNamespaces

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared namespace — UMLS-specific predicates
# ---------------------------------------------------------------------------

UMLS = Namespace("https://uts.nlm.nih.gov/uts/umls/concept/")


def _concept_uri(concept: UnifiedConcept) -> URIRef:
    """Build a deterministic URI for a UnifiedConcept."""
    return URIRef(UMLS[concept.primary_id])


def concept_to_graph(concept: UnifiedConcept, graph: Graph | None = None) -> Graph:
    """Convert a *concept* to an RDF :class:`Graph` and return it.

    Parameters
    ----------
    concept :
        The concept to serialise.
    graph :
        An optional existing graph to add triples to (creates a new one if
        ``None``).

    Returns
    -------
    The populated RDF graph.
    """
    g = graph if graph is not None else Graph()
    ns = RDFNamespaces()
    uri = _concept_uri(concept)

    # Bind namespaces for pretty Turtle
    for prefix, namespace in ns.get_namespace_bindings().items():
        g.bind(prefix, namespace)
    g.bind("umls", UMLS)

    # ── Type assertion ──────────────────────────────────────────────
    type_uri = _concept_type_to_rdf_class(concept.concept_type)
    g.add((uri, RDF.type, type_uri))

    # ── Labels & descriptions ───────────────────────────────────────
    g.add((uri, RDFS.label, Literal(concept.primary_label, lang="en")))
    for lang, label in concept.labels.items():
        g.add((uri, RDFS.label, Literal(label, lang=lang)))
    for synonym in concept.synonyms:
        g.add((uri, ns.VOCAB["synonym"], Literal(synonym, lang="en")))
    for definition in concept.definitions:
        g.add((uri, ns.VOCAB["definition"], Literal(definition, lang="en")))

    # ── Identifiers (cross-references) ──────────────────────────────
    for cid in concept.identifiers:
        _add_identifier(g, uri, cid, ns)

    # ── Semantic types & categories ─────────────────────────────────
    for st in concept.semantic_types:
        g.add((uri, ns.VOCAB["semanticType"], Literal(st)))
    for cat in concept.categories:
        g.add((uri, ns.VOCAB["category"], Literal(cat)))

    # ── Relationships ───────────────────────────────────────────────
    for parent_id in concept.parents:
        parent_uri = URIRef(UMLS[parent_id])
        g.add((uri, RDFS.subClassOf, parent_uri))
    for child_id in concept.children:
        child_uri = URIRef(UMLS[child_id])
        g.add((child_uri, RDFS.subClassOf, uri))
    for related_id in concept.related:
        related_uri = URIRef(UMLS[related_id])
        g.add((uri, ns.VOCAB["related"], related_uri))

    # ── Confidence / provenance ─────────────────────────────────────
    g.add(
        (uri, ns.VOCAB["confidenceScore"], Literal(concept.confidence_score, datatype=XSD.float))
    )
    for src in concept.sources:
        g.add((uri, ns.VOCAB["source"], Literal(str(src))))

    return g


def concept_to_turtle(concept: UnifiedConcept) -> str:
    """Return a Turtle (``.ttl``) serialisation of *concept*."""
    return concept_to_graph(concept).serialize(format="turtle")


def concepts_to_graph(concepts: list[UnifiedConcept], graph: Graph | None = None) -> Graph:
    """Convert multiple concepts into a single RDF graph."""
    g = graph if graph is not None else Graph()
    for c in concepts:
        concept_to_graph(c, graph=g)
    return g


def concepts_to_turtle(concepts: list[UnifiedConcept]) -> str:
    """Return Turtle for a list of concepts."""
    return concepts_to_graph(concepts).serialize(format="turtle")


def concepts_to_jsonld(concepts: list[UnifiedConcept]) -> dict:
    """Return JSON-LD dict for a list of concepts."""
    g = concepts_to_graph(concepts)
    return json.loads(g.serialize(format="json-ld"))


def save_concepts_to_file(
    concepts: list[UnifiedConcept],
    path: str | Path,
    fmt: str = "turtle",
) -> Path:
    """Save concepts as RDF to a file.

    Parameters
    ----------
    concepts :
        Concepts to serialise.
    path :
        Output file path.
    fmt :
        RDF format — ``"turtle"`` (default), ``"xml"``, ``"json-ld"``,
        ``"n3"``, or ``"nt"``.

    Returns
    -------
    The resolved output path.
    """
    path = Path(path)
    g = concepts_to_graph(concepts)
    g.serialize(destination=str(path), format=fmt)
    logger.info("Exported %d concepts to %s (%s)", len(concepts), path, fmt)
    return path


# ---------------------------------------------------------------------------
# SPARQL endpoint query client
# ---------------------------------------------------------------------------


class SparqlEndpoint:
    """Lightweight async SPARQL endpoint client.

    Can query any public (or authenticated) SPARQL endpoint and return
    results as structured JSON.

    Examples
    --------
    >>> client = SparqlEndpoint("https://query.wikidata.org/sparql")
    >>> results = await client.query("SELECT ?item WHERE { ?item wdt:P31 wd:Q12198 } LIMIT 5")
    >>> for row in results:
    ...     print(row["item"])
    """

    def __init__(
        self,
        url: str,
        *,
        auth: tuple[str, str] | None = None,
        timeout: float = 30.0,
        user_agent: str = "knowledge-lookup/1.0",
    ):
        self.url = url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self.user_agent = user_agent
        self._session = None

    async def _get_session(self):
        if self._session is None:
            import aiohttp

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": self.user_agent},
            )
        return self._session

    async def query(
        self,
        sparql: str,
        *,
        format: str = "json",
    ) -> list[dict[str, Any]]:
        """Execute a SPARQL query and return results as a list of dicts.

        Parameters
        ----------
        sparql :
            The SPARQL query string.
        format :
            Response format — ``"json"`` (default) or ``"xml"``.

        Returns
        -------
        A list of result bindings, each as ``{variable: value}``.
        """
        session = await self._get_session()
        params = {"query": sparql, "format": format}

        try:
            async with session.get(
                self.url,
                params=params,
                auth=aiohttp.BasicAuth(*self.auth) if self.auth else None,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as exc:
            logger.error("SPARQL query failed against %s: %s", self.url, exc)
            return []

        return self._parse_sparql_json(data)

    async def close(self):
        """Close the underlying HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    @staticmethod
    def _parse_sparql_json(data: dict) -> list[dict[str, Any]]:
        """Parse SPARQL JSON results into flat dicts."""
        bindings = data.get("results", {}).get("bindings", [])
        parsed: list[dict[str, Any]] = []
        for binding in bindings:
            row: dict[str, Any] = {}
            for var, val in binding.items():
                row[var] = val.get("value", "")
            parsed.append(row)
        return parsed


# ---------------------------------------------------------------------------
# Well-known SPARQL endpoints
# ---------------------------------------------------------------------------

SPARQL_ENDPOINTS: dict[str, str] = {
    "wikidata": "https://query.wikidata.org/sparql",
    "dbpedia": "https://dbpedia.org/sparql",
    "bioportal": "https://sparql.bioontology.org/sparql",
    "ontobee": "https://sparql.hegroup.org/sparql",
    "ncbi_umls": "https://uts-ws.nlm.nih.gov/sparql",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _concept_type_to_rdf_class(ct: ConceptType) -> URIRef:
    """Map a :class:`ConceptType` to an RDFS/OWL class URI."""
    ns = RDFNamespaces()
    mapping: dict[ConceptType, URIRef] = {
        ConceptType.DISEASE: ns.AIDPAIS["Disease"],
        ConceptType.SYMPTOM: ns.AIDPAIS["Symptom"],
        ConceptType.PHENOTYPE: ns.AIDPAIS["Phenotype"],
        ConceptType.TREATMENT: ns.AIDPAIS["Treatment"],
        ConceptType.DRUG: ns.AIDPAIS["Drug"],
        ConceptType.CHEMICAL: ns.AIDPAIS["Chemical"],
        ConceptType.GENE: ns.AIDPAIS["Gene"],
        ConceptType.PROTEIN: ns.AIDPAIS["Protein"],
        ConceptType.PATHWAY: ns.AIDPAIS["Pathway"],
        ConceptType.PROCEDURE: ns.AIDPAIS["Procedure"],
        ConceptType.ANATOMICAL_ENTITY: ns.AIDPAIS["AnatomicalEntity"],
        ConceptType.BIOLOGICAL_PROCESS: ns.AIDPAIS["BiologicalProcess"],
        ConceptType.CELL_TYPE: ns.AIDPAIS["CellType"],
        ConceptType.CELLULAR_COMPONENT: ns.AIDPAIS["CellularComponent"],
    }
    return mapping.get(ct, ns.AIDPAIS["Concept"])


def _add_identifier(
    g: Graph,
    subject: URIRef,
    cid: Any,
    ns: RDFNamespaces,
) -> None:
    """Add a ``vocab:xref`` triple for a concept identifier."""
    try:
        value = f"{str(cid.source)}:{cid.identifier}" if hasattr(cid, "source") else str(cid)
    except Exception:
        value = str(cid)
    g.add((subject, ns.VOCAB["xref"], Literal(value)))
