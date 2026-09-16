---
description: Save a LookupResult as JSON, CSV, Turtle, a pandas DataFrame, an Excel workbook, a text report or an RDF graph.
---

# Exporting results

`CentralKnowledgeLookup` has an export method for each common format. Every method takes a `LookupResult`; file-based exports create missing parent directories and return the path as a string.

| Method | Output | Needs |
| --- | --- | --- |
| `export_to_json(result, filepath=None)` | JSON file, or a `dict` when `filepath` is omitted | Core |
| `export_to_csv(result, filepath)` | CSV file | Core |
| `export_to_ttl(result, filepath, namespace="http://example.org/concepts/")` | SKOS Turtle file | Core |
| `export_to_dataframe(result)` | `pandas.DataFrame` | `export` extra |
| `export_to_excel(result, filepath)` | `.xlsx` workbook | `export` extra |
| `export_summary_report(result, filepath)` | Plain-text report | Core |
| *async* `lookup_and_convert_to_rdf(query, output_path=None, ...)` | Searches, then returns an `rdflib.Graph` and optionally saves it | Core |
| `UnifiedRDFConverter` | `rdflib.Graph` in Turtle, RDF/XML, JSON-LD or N-Triples | Core |

## Export a search

{% code title="export.py" %}
```python
import asyncio
from pathlib import Path

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.HPO]))
    try:
        result = await lookup.search_concepts("seizure", sources=[KnowledgeSource.HPO], max_results=5)
        out = Path("exports")

        data = lookup.export_to_json(result)  # dict, nothing written
        print(len(data["concepts"]), "concepts")

        print(lookup.export_to_json(result, out / "seizure.json"))
        print(lookup.export_to_csv(result, out / "seizure.csv"))
        print(lookup.export_to_ttl(result, out / "seizure.ttl"))
        print(lookup.export_summary_report(result, out / "seizure_report.txt"))

        df = lookup.export_to_dataframe(result)  # requires pandas
        print(df.shape, df.attrs["query"])
        print(lookup.export_to_excel(result, out / "seizure.xlsx"))  # requires openpyxl
    finally:
        await lookup.close()


asyncio.run(main())
```
{% endcode %}

## Format details

### JSON

Top-level keys: `query`, `execution_time`, `total_found`, `sources_queried`, `sources_succeeded`, `errors` and `concepts`. Each concept has `primary_label`, `primary_id`, `concept_type`, `confidence_score`, `sources`, `definitions`, `synonyms`, `semantic_types`, `categories`, `parents`, `children` and `identifiers` (`source`, `identifier`, `label`, `url`).

For a lossless round trip use the pydantic model instead: `result.model_dump(mode="json")` and `LookupResult.model_validate(data)`.

### CSV

Columns: `primary_label`, `primary_id`, `concept_type`, `confidence_score`, `sources`, `definitions`, `synonyms`, `semantic_types`, `categories`. List values are joined with `"; "`.

{% hint style="warning" %}
The first row after the header is a metadata row (`# Query: ...`, execution time, totals). Skip it when loading the file:

```python
import pandas as pd

df = pd.read_csv("exports/seizure.csv", skiprows=[1])
```
{% endhint %}

### Turtle (`export_to_ttl`)

Writes a lightweight SKOS vocabulary: one `dct:BibliographicResource` describing the query, and one `skos:Concept` per result with `skos:prefLabel`, `dct:identifier`, `dct:source`, up to 3 `skos:definition`, up to 10 `skos:altLabel` and up to 5 semantic types. Concept URIs are built from `namespace` plus the sanitized `primary_id`. For a richer, type-aware graph use the RDF converter below.

### DataFrame

Columns: `primary_label`, `primary_id`, `concept_type`, `confidence_score`, `sources`, `num_sources`, `definitions`, `num_definitions`, `synonyms`, `num_synonyms`, `semantic_types`, `categories`, `parents`, `children`. List columns contain Python lists. `df.attrs` holds `query`, `execution_time`, `total_found`, `sources_queried` and `sources_succeeded`.

### Excel

A workbook with the sheets **Summary** (query metrics), **Results** (the DataFrame above) and **Source Stats** (concepts per source), plus **Errors** (source and message) when any source failed.

### Summary report

A text report with an overview (sources queried and succeeded, success rate), per-source contribution, quality metrics (average confidence, share above 0.8, multi-source concepts), the top 10 results, errors, and short recommendations.

## Build an RDF graph

`UnifiedRDFConverter` in `knowledge_lookup.services` maps concepts to RDF with type-specific handlers for diseases, drugs, chemicals, genes and proteins:

```python
from knowledge_lookup.services import UnifiedRDFConverter

converter = UnifiedRDFConverter()
graph = converter.convert_concepts_to_graph(result.concepts)  # rdflib.Graph
print(len(graph), "triples")

converter.save_graph(graph, "exports/seizure_rdf.ttl", format="turtle")
converter.convert_and_save(result.concepts, "exports/seizure.jsonld", format="json-ld")
```

`format` accepts `turtle`, `xml`, `json-ld` and `nt`. Other methods: `merge_with_existing_graph(...)` to combine with an existing Turtle file, `add_concept_type_handler(concept_type, handler)` for custom mappings, and `UnifiedRDFConverter.from_ontology(ontology_dir)` to load concept types from ontology files.

To search and convert in one call, use `lookup_and_convert_to_rdf()`:

```python
graph = await lookup.lookup_and_convert_to_rdf(
    "seizure",
    sources=[KnowledgeSource.HPO],
    max_results=5,
    output_path="exports/seizure_rdf.ttl",  # optional
    rdf_format="turtle",
)
print(len(graph), "triples")
```

It takes the same `concept_types`, `sources` and `max_results` arguments as `search_concepts()`, plus `rdf_format` and `adapter_hints` for the converter. When the search finds nothing it returns an empty graph and writes no file. The `LookupResult` is not returned, so call `search_concepts()` yourself if you need `result.errors`.

## Module-level helpers

`knowledge_lookup.export` provides `export_to_json()` and `export_to_csv()` functions for code that has a `LookupResult` but no lookup instance. The [agent workflow](agent-workflow.md) has its own JSON, CSV and Turtle export step.

## Next steps

* [Searching concepts](searching-concepts.md)
* [Command-line interface](cli.md): JSON and CSV output from the terminal
