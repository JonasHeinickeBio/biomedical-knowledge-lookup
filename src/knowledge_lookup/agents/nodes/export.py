"""Graph node: export results to multiple formats.

Includes:
- Per-concept data: primary_id, label, UMLS CUI, ontology IDs, definitions
- LLM review output: concept map (term→CUI→IDs→type) + overall explanation
"""

from __future__ import annotations

import csv
import json
import os
import tempfile

from ...models import KnowledgeSource
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


def _get_ontology_ids_list(concept) -> list[str]:
    """Get a list of all ontology IDs (including UMLS) for a concept."""
    ids: list[str] = []
    if not concept.identifiers:
        # Fall back to primary_id
        if concept.primary_id:
            ids.append(concept.primary_id)
        return ids
    for ident in concept.identifiers:
        src = (
            str(ident.source).upper()
            if hasattr(ident.source, "upper")
            else str(getattr(ident.source, "value", "")).upper()
        )
        ids.append(f"{src}:{ident.identifier}")
    # Also add primary_id if not already covered
    if concept.primary_id:
        pid = concept.primary_id
        if not any(pid in id_str or id_str.endswith(pid.split(":")[-1]) for id_str in ids):
            ids.append(pid)
    return ids


async def export_node(state: LookupWorkflowState) -> dict:
    """Export final results to configured formats.

    Includes:
    - Full concept data with UMLS CUI and ontology IDs
    - LLM concept map (term→CUI→IDs→type)
    - LLM overall explanation
    """
    result = dict_to_lookup_result(state.get("final_result") or state.get("lookup_result"))
    if result is None:
        return {
            "status": "completed",
            "export_paths": [],
            "steps": [make_step("ExportAgent", "skip", "No results to export")],
        }

    export_formats = state.get("export_formats", ["json"])
    export_path = state.get("export_path")
    paths: list[str] = []

    # Get LLM concept map and explanation
    concept_map = state.get("review_concept_map", [])
    llm_explanation = state.get("review_llm_explanation", "")

    base_path = export_path or os.path.join(tempfile.gettempdir(), "knowledge_lookup_export")
    os.makedirs(base_path, exist_ok=True)

    query_slug = ""
    if result:
        query_slug = result.query.replace(" ", "_")[:50]

    for fmt in export_formats:
        try:
            if fmt == "json":
                path = os.path.join(base_path, f"{query_slug}.json")
                data: dict = {}

                if result:
                    data = result.model_dump(mode="json")
                    # Add flat umls_cui + ontology_ids to each concept
                    if data.get("concepts"):
                        for c in data["concepts"]:
                            c["umls_cui"] = _get_umls_cui_from_dict(c)
                            # Extract ontology IDs from identifiers
                            ids = []
                            for ident in c.get("identifiers") or []:
                                src = ident.get("source", "")
                                ids.append(f"{src}:{ident.get('identifier', '')}")
                            if c.get("primary_id") and not any(
                                c["primary_id"] in id_str for id_str in ids
                            ):
                                ids.append(c["primary_id"])
                            c["ontology_ids"] = ids

                # Add LLM review output
                data["llm_review"] = {
                    "concept_map": concept_map,
                    "explanation": llm_explanation,
                    "score": state.get("review_score"),
                    "summary": state.get("review_summary"),
                    "strengths": state.get("review_strengths", []),
                    "weaknesses": state.get("review_weaknesses", []),
                    "suggestions": state.get("review_suggestions", []),
                }

                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(path)

            elif fmt == "csv":
                path = os.path.join(base_path, f"{query_slug}.csv")
                concepts = result.concepts if result else []
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
                                "ontology_ids",
                                "sources",
                                "definitions",
                            ]
                        )
                        for c in concepts:
                            umls_cui = _get_umls_cui(c)
                            ontology_ids = "; ".join(_get_ontology_ids_list(c))
                            writer.writerow(
                                [
                                    c.primary_id,
                                    c.primary_label,
                                    str(c.concept_type) if c.concept_type else "",
                                    c.confidence_score or "",
                                    umls_cui or "",
                                    ontology_ids,
                                    "; ".join(str(s) for s in (c.sources or [])),
                                    "; ".join(c.definitions or []),
                                ]
                            )
                paths.append(path)

            elif fmt == "ttl":
                path = os.path.join(base_path, f"{query_slug}.ttl")
                if result:
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
                "steps": [make_step("ExportAgent", "error", f"Export {fmt} failed: {e}")],
            }

    step_detail = (
        f"Exported to {len(paths)} file(s): {', '.join(paths)}"
        f" | {len(concept_map)} concepts mapped"
        + (" | LLM explanation included" if llm_explanation else "")
    )

    return {
        "status": "completed",
        "final_result": state.get("final_result") or state.get("lookup_result"),
        "export_paths": paths,
        "steps": [make_step("ExportAgent", "export", step_detail)],
    }
