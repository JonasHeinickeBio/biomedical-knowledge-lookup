"""
Export functions for CentralKnowledgeLookup results.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any

from ..models import KnowledgeSource, LookupResult

logger = logging.getLogger(__name__)


def export_to_json(result: LookupResult, filepath: str | Path | None = None) -> str | dict:
    """
    Export search results to JSON format.
    """
    json_data: dict[str, Any] = {
        "query": result.query,
        "execution_time": result.execution_time,
        "total_found": result.total_found,
        "sources_queried": [
            str(s.value) if isinstance(s, KnowledgeSource) else str(s)
            for s in (result.sources_queried or [])
        ],
        "sources_succeeded": [
            str(s.value) if isinstance(s, KnowledgeSource) else str(s)
            for s in (result.sources_succeeded or [])
        ],
        "errors": {
            str(k.value) if isinstance(k, KnowledgeSource) else str(k): str(v)
            for k, v in result.errors.items()  # type: ignore[attr-defined]
        }
        if result.errors
        else {},
        "concepts": [],
    }
    for concept in result.concepts or []:
        concept_data = {
            "primary_label": concept.primary_label,
            "primary_id": concept.primary_id,
            "concept_type": str(concept.concept_type) if concept.concept_type else None,
            "confidence_score": concept.confidence_score,
            "sources": [str(s) for s in (concept.sources or [])],
            "definitions": concept.definitions,
            "synonyms": concept.synonyms,
            "semantic_types": concept.semantic_types,
            "categories": concept.categories,
            "parents": concept.parents,
            "children": concept.children,
            "identifiers": (
                [
                    {
                        "source": str(id.source),
                        "identifier": id.identifier,
                        "label": id.label,
                        "url": id.url,
                    }
                    for id in concept.identifiers
                ]
                if concept.identifiers
                else []
            ),
        }
        json_data["concepts"].append(concept_data)
    if filepath:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Results exported to JSON: {filepath}")
        return str(filepath)
    return json_data


def export_to_csv(result: LookupResult, filepath: str | Path | None = None) -> str | None:
    """
    Export search results to CSV format.
    """
    if not result.concepts:
        logger.warning("No concepts to export.")
        return None
    fieldnames = [
        "primary_label",
        "primary_id",
        "concept_type",
        "confidence_score",
        "sources",
        "definitions",
        "synonyms",
        "semantic_types",
        "categories",
        "parents",
        "children",
        "identifiers",
    ]
    rows = []
    for concept in result.concepts:
        row = {
            "primary_label": concept.primary_label,
            "primary_id": concept.primary_id,
            "concept_type": str(concept.concept_type) if concept.concept_type else "",
            "confidence_score": concept.confidence_score,
            "sources": ";".join([str(s) for s in (concept.sources or [])]),
            "definitions": ";".join(concept.definitions or []),
            "synonyms": ";".join(concept.synonyms or []),
            "semantic_types": ";".join(concept.semantic_types or []),
            "categories": ";".join(concept.categories or []),
            "parents": ";".join(concept.parents or []),
            "children": ";".join(concept.children or []),
            "identifiers": (
                ";".join([f"{id.source}:{id.identifier}" for id in concept.identifiers])
                if concept.identifiers
                else ""
            ),
        }
        rows.append(row)
    if filepath:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Results exported to CSV: {filepath}")
        return str(filepath)
    return None
