"""Graph node: export results to multiple formats."""

from __future__ import annotations

import csv
import json
import os
import tempfile

from ...models import KnowledgeSource, LookupResult
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step


def _get_umls_cui(concept) -> str | None:
    """Extract UMLS CUI from a concept's identifiers, if any."""
    if not concept.identifiers:
        return None
    for ident in concept.identifiers:
        if ident.source == KnowledgeSource.UMLS:
            return ident.identifier
    return None


def _get_umls_cui_from_dict(concept_dict: dict) -> str | None:
    """Extract UMLS CUI from a serialized concept dict."""
    identifiers = concept_dict.get("identifiers") or []
    for ident in identifiers:
        if ident.get("source") == KnowledgeSource.UMLS.value:
            return ident.get("identifier")
    return None


async def export_node(state: LookupWorkflowState) -> dict:
    """Export final results to configured formats."""
    result = dict_to_lookup_result(
        state.get("final_result") or state.get("lookup_result")
    )
    if result is None:
        return {
            "status": "completed",
            "export_paths": [],
            "steps": [make_step("ExportAgent", "skip", "No results to export")],
        }

    export_formats = state.get("export_formats", ["json"])
    export_path = state.get("export_path")
    paths: list[str] = []

    base_path = export_path or os.path.join(
        tempfile.gettempdir(), "knowledge_lookup_export"
    )
    os.makedirs(base_path, exist_ok=True)

    query_slug = result.query.replace(" ", "_")[:50]

    for fmt in export_formats:
        try:
            if fmt == "json":
                path = os.path.join(base_path, f"{query_slug}.json")
                # Add umls_cui to each concept for flat access
                data = result.model_dump(mode="json")
                if data.get("concepts"):
                    for c in data["concepts"]:
                        c["umls_cui"] = _get_umls_cui_from_dict(c)
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(path)

            elif fmt == "csv":
                path = os.path.join(base_path, f"{query_slug}.csv")
                concepts = result.concepts or []
                if concepts:
                    with open(path, "w", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            [
                                "primary_id",
                                "primary_label",
                                "concept_type",
                                "confidence_score",
                                "umls_cui",
                                "sources",
                                "definitions",
                            ]
                        )
                        for c in concepts:
                            umls_cui = _get_umls_cui(c)
                            writer.writerow(
                                [
                                    c.primary_id,
                                    c.primary_label,
                                    str(c.concept_type) if c.concept_type else "",
                                    c.confidence_score or "",
                                    umls_cui or "",
                                    "; ".join(str(s) for s in (c.sources or [])),
                                    "; ".join(c.definitions or []),
                                ]
                            )
                paths.append(path)

            elif fmt == "ttl":
                path = os.path.join(base_path, f"{query_slug}.ttl")
                from rdflib import Graph, Literal, Namespace, URIRef
                from rdflib.namespace import RDF

                SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
                g = Graph()
                g.bind("skos", SKOS)

                for c in result.concepts or []:
                    concept_uri = URIRef(c.primary_id)
                    g.add((concept_uri, RDF.type, SKOS.Concept))
                    if c.primary_label:
                        g.add((concept_uri, SKOS.prefLabel, Literal(c.primary_label)))
                    for defn in c.definitions or []:
                        g.add((concept_uri, SKOS.definition, Literal(defn)))
                    for syn in c.synonyms or []:
                        g.add((concept_uri, SKOS.altLabel, Literal(syn)))

                g.serialize(destination=path, format="turtle")
                paths.append(path)

        except Exception as e:
            return {
                "status": "failed",
                "errors": [f"Export failed for {fmt}: {e}"],
                "steps": [
                    make_step("ExportAgent", "error", f"Export {fmt} failed: {e}")
                ],
            }

    return {
        "status": "completed",
        "final_result": state.get("final_result") or state.get("lookup_result"),
        "export_paths": paths,
        "steps": [
            make_step(
                "ExportAgent",
                "export",
                f"Exported to {len(paths)} file(s): {', '.join(paths)}",
            )
        ],
    }
