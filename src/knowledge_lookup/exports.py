"""
Export functions for CentralKnowledgeLookup results.
"""

import json
import csv
from pathlib import Path
from typing import Union, Optional
import logging
from .models import LookupResult

logger = logging.getLogger(__name__)


def export_to_json(result: LookupResult, filepath: Optional[Union[str, Path]] = None) -> Union[str, dict]:
	"""
	Export search results to JSON format.
	"""
	json_data = {
		"query": result.query,
		"execution_time": result.execution_time,
		"total_found": result.total_found,
		"sources_queried": [s.value for s in result.sources_queried],
		"sources_succeeded": [s.value for s in result.sources_succeeded],
		"errors": {k: str(v) for k, v in result.errors.items()} if result.errors else {},
		"concepts": []
	}
	for concept in result.concepts:
		concept_data = {
			"primary_label": concept.primary_label,
			"primary_id": concept.primary_id,
			"concept_type": concept.concept_type.value,
			"confidence_score": concept.confidence_score,
			"sources": [s.value for s in concept.sources],
			"definitions": concept.definitions,
			"synonyms": concept.synonyms,
			"semantic_types": concept.semantic_types,
			"categories": concept.categories,
			"parents": concept.parents,
			"children": concept.children,
			"identifiers": [
				{
					"source": id.source.value,
					"identifier": id.identifier,
					"label": id.label,
					"url": id.url
				} for id in concept.identifiers
			] if concept.identifiers else []
		}
		json_data["concepts"].append(concept_data)
	if filepath:
		filepath = Path(filepath)
		filepath.parent.mkdir(parents=True, exist_ok=True)
		with open(filepath, 'w', encoding='utf-8') as f:
			json.dump(json_data, f, indent=2, ensure_ascii=False)
		logger.info(f"Results exported to JSON: {filepath}")
		return str(filepath)
	return json_data

def export_to_csv(result: LookupResult, filepath: Optional[Union[str, Path]] = None) -> Optional[str]:
	"""
	Export search results to CSV format.
	"""
	if not result.concepts:
		logger.warning("No concepts to export.")
		return None
	fieldnames = [
		"primary_label", "primary_id", "concept_type", "confidence_score", "sources",
		"definitions", "synonyms", "semantic_types", "categories", "parents", "children", "identifiers"
	]
	rows = []
	for concept in result.concepts:
		row = {
			"primary_label": concept.primary_label,
			"primary_id": concept.primary_id,
			"concept_type": concept.concept_type.value,
			"confidence_score": concept.confidence_score,
			"sources": ";".join([s.value for s in concept.sources]),
			"definitions": ";".join(concept.definitions),
			"synonyms": ";".join(concept.synonyms),
			"semantic_types": ";".join(concept.semantic_types),
			"categories": ";".join(concept.categories),
			"parents": ";".join(concept.parents),
			"children": ";".join(concept.children),
			"identifiers": ";".join([
				f"{id.source.value}:{id.identifier}" for id in concept.identifiers
			]) if concept.identifiers else ""
		}
		rows.append(row)
	if filepath:
		filepath = Path(filepath)
		filepath.parent.mkdir(parents=True, exist_ok=True)
		with open(filepath, 'w', encoding='utf-8', newline='') as f:
			writer = csv.DictWriter(f, fieldnames=fieldnames)
			writer.writeheader()
			writer.writerows(rows)
		logger.info(f"Results exported to CSV: {filepath}")
		return str(filepath)
	return None
