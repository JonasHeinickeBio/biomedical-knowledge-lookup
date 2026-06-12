"""
Helper functions for CentralKnowledgeLookup (deduplication, formatting, etc).
"""

from .models import LookupResult, UnifiedConcept


def _deduplicate_concepts(
    concepts: list[UnifiedConcept], similarity_threshold: float = 0.8
) -> list[UnifiedConcept]:
    """
    Deduplicate concepts based on similarity threshold.
    """
    deduped = []
    seen = set()
    for concept in concepts:
        key = (concept.primary_id, concept.primary_label)
        if key not in seen:
            deduped.append(concept)
            seen.add(key)
    return deduped


def format_results_table(result: LookupResult) -> str:
    """
    Format lookup results as a simple table (TSV).
    """
    if not result.concepts:
        return "No concepts found."
    headers = [
        "Primary Label",
        "Primary ID",
        "Type",
        "Confidence",
        "Sources",
        "Synonyms",
        "Definitions",
    ]
    lines = ["\t".join(headers)]
    for concept in result.concepts:
        line = [
            concept.primary_label,
            concept.primary_id,
            concept.concept_type.value,
            f"{concept.confidence_score:.2f}",
            ";".join([s.value for s in concept.sources]),
            ";".join(concept.synonyms),
            ";".join(concept.definitions),
        ]
        lines.append("\t".join(line))
    return "\n".join(lines)


def format_results_detailed(result: LookupResult) -> str:
    """
    Format lookup results with detailed information for each concept.
    """
    if not result.concepts:
        return "No concepts found."
    details = []
    for idx, concept in enumerate(result.concepts, 1):
        details.append(f"Concept {idx}:")
        details.append(f"  Label: {concept.primary_label}")
        details.append(f"  ID: {concept.primary_id}")
        details.append(f"  Type: {concept.concept_type.value}")
        details.append(f"  Confidence: {concept.confidence_score:.2f}")
        details.append(f"  Sources: {', '.join([s.value for s in concept.sources])}")
        if concept.synonyms:
            details.append(f"  Synonyms: {', '.join(concept.synonyms)}")
        if concept.definitions:
            details.append(f"  Definitions: {', '.join(concept.definitions)}")
        if concept.semantic_types:
            details.append(f"  Semantic Types: {', '.join(concept.semantic_types)}")
        if concept.categories:
            details.append(f"  Categories: {', '.join(concept.categories)}")
        if concept.parents:
            details.append(f"  Parents: {', '.join(concept.parents)}")
        if concept.children:
            details.append(f"  Children: {', '.join(concept.children)}")
        details.append("")
    return "\n".join(details)
