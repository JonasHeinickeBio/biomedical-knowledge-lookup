---
description: Complete scripts for common tasks that combine several knowledge sources.
---

# Use cases

Each section is a complete script. Save it to a file and run it with `python`. All sources
used here are public unless a section says otherwise. For the building blocks, see the
[per-source examples](README.md) and the [notebooks](notebooks/README.md).

## Map free-text terms to ontology identifiers

Normalise terms from a spreadsheet or a clinical note to HPO and Mondo identifiers.
`get_best_matches` sorts by confidence, and many hits share the same score, so print a
few candidates for review instead of trusting the first one blindly.

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup

TERMS = ["seizures", "short stature", "type 2 diabetes"]
SOURCES = [KnowledgeSource.HPO, KnowledgeSource.MONDO]


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=SOURCES)
    try:
        for term in TERMS:
            result = await lookup.search_concepts(term, sources=SOURCES, max_results=10)
            print(f"{term}:")
            for concept in result.get_best_matches(3):
                sources = ", ".join(concept.sources)
                print(f"  {concept.primary_id:<16} {concept.primary_label} ({sources})")
            if result.errors:
                print("  errors:", result.errors)
    finally:
        await lookup.close()


asyncio.run(main())
```

## Find cross-references for a concept

`find_mappings` combines the identifiers already attached to a concept with live
cross-references from EBI OxO, so enable OxO alongside the source that resolves the
identifier. Pass `target_sources=` to keep only some sources.

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.MONDO, KnowledgeSource.OXO])
    try:
        mappings = await lookup.find_mappings("MONDO:0005148")  # type 2 diabetes mellitus
        print(len(mappings), "mappings")
        for identifier in mappings:
            print(f"{identifier.source:<6} {identifier.identifier:<28} {identifier.label or ''}")
    finally:
        await lookup.close()


asyncio.run(main())
```

Among the mappings are `DOID:9352`, `ICD10CM:E11`, `NCIT:C26747`, `MESH:D003924` and
`UMLS:C0011860`.

## Build a gene profile from several databases

Fetch the same gene from HGNC, UniProt and Ensembl in parallel. Each source takes its own
identifier format.

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup

BRCA1 = {
    KnowledgeSource.HGNC: "HGNC:1100",
    KnowledgeSource.UNIPROT: "P38398",
    KnowledgeSource.ENSEMBL: "ENSG00000012048",
}


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=list(BRCA1))
    try:
        records = await asyncio.gather(
            *(
                lookup.get_concept_details(concept_id, source=source)
                for source, concept_id in BRCA1.items()
            )
        )
        for (source, concept_id), record in zip(BRCA1.items(), records):
            if record is None:
                print(f"{source.value}: {concept_id} not found")
                continue
            definition = record.definitions[0][:80] if record.definitions else ""
            print(f"{source.value}: {record.primary_id} {record.primary_label} | {definition}")
    finally:
        await lookup.close()


asyncio.run(main())
```

## Compare a drug across chemistry sources

Search PubChem, ChEMBL and Wikidata at once and group the hits by source. Concepts with
the same label are merged, so "Aspirin" from PubChem and ChEMBL becomes one concept that
lists both sources.

{% hint style="info" %}
ChEMBL needs the `[chembl]` extra: `pip install "biomedical-knowledge-lookup[chembl]"`.
Without it, the script still runs with PubChem and Wikidata.
{% endhint %}

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup

SOURCES = [KnowledgeSource.PUBCHEM, KnowledgeSource.CHEMBL, KnowledgeSource.WIKIDATA]


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=SOURCES)
    try:
        result = await lookup.search_concepts("aspirin", sources=SOURCES, max_results=15)
        for source, concepts in result.group_by_source().items():
            name = getattr(source, "value", source)
            print(f"{name}:", [(c.primary_id, c.primary_label) for c in concepts[:3]])
        if result.errors:
            print("errors:", result.errors)
    finally:
        await lookup.close()


asyncio.run(main())
```

## Widen a search with synonyms and long forms

`search_concepts_expanded` searches the query, collects synonyms from the hits, and
searches those too, for up to `max_rounds` rounds. With the `[umls]` extra and
`UMLS_API_KEY` it also expands abbreviations to their long forms (COPD to "chronic
obstructive pulmonary disease"). `persist=False` skips recording the expansion trail.

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup

SOURCES = [KnowledgeSource.MONDO, KnowledgeSource.HPO]


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=SOURCES)
    try:
        result = await lookup.search_concepts_expanded(
            "COPD", sources=SOURCES, max_results=10, max_rounds=2, persist=False
        )
        print(f"{result.total_found} concepts")
        for concept in result.concepts[:5]:
            print(f"  {concept.primary_id:<16} {concept.primary_label}")
    finally:
        await lookup.close()


asyncio.run(main())
```

## Annotate a sentence and compare sources

`MultiSourceAnnotator` annotates text with several sources and scores how well they
agree. Without `sources=` it uses BioLinker, OLS, BioPortal, OxO and UMLS, skipping any
that are unavailable.

```python
import asyncio

from knowledge_lookup import KnowledgeSource, MultiSourceAnnotator


async def main() -> None:
    annotator = MultiSourceAnnotator()
    try:
        result = await annotator.annotate_text(
            "Patients with asthma often report wheezing.",
            sources=[KnowledgeSource.OLS, KnowledgeSource.BIOLINKER],
        )
        print(f"Overall confidence {result.overall_confidence:.2f}")
        for agreement in result.consensus_concepts:
            concept = agreement.primary_concept
            print(
                f"{concept.primary_label} ({concept.primary_id}): "
                f"{agreement.confidence_level.value}, score {agreement.consensus_score:.2f}"
            )
        for annotation in result.source_annotations:
            print(f"{annotation.source.value}: {len(annotation.concepts)} concepts")
    finally:
        await annotator.close()


asyncio.run(main())
```

## Search the literature

Europe PMC returns citations as concepts, with the PubMed ID as identifier.

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.EUROPEPMC])
    try:
        result = await lookup.search_concepts("BRCA1 PARP inhibitor", max_results=5)
        for citation in result.concepts:
            print(citation.primary_id, citation.primary_label)
    finally:
        await lookup.close()


asyncio.run(main())
```

## Export results

The lookup exports a `LookupResult` to JSON, CSV, RDF Turtle and a text report.
`export_to_dataframe` and `export_to_excel` need pandas, from the `[export]` extra.

```python
import asyncio
from pathlib import Path

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.HPO])
    try:
        result = await lookup.search_concepts("ataxia", max_results=5)
        out = Path("ataxia-export")
        out.mkdir(exist_ok=True)

        data = lookup.export_to_json(result)  # a dict when no file path is given
        print(list(data)[:5])
        lookup.export_to_json(result, out / "ataxia.json")
        lookup.export_to_csv(result, out / "ataxia.csv")
        lookup.export_to_ttl(result, out / "ataxia.ttl")
        lookup.export_summary_report(result, out / "ataxia.txt")

        frame = lookup.export_to_dataframe(result)  # needs the [export] extra
        print(frame[["primary_id", "primary_label", "confidence_score"]])
    finally:
        await lookup.close()


asyncio.run(main())
```
