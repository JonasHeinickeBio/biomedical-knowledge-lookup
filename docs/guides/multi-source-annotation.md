---
description: Send the same text to several sources, group the concepts they return and score how strongly the sources agree.
---

# Multi-source annotation

`MultiSourceAnnotator` asks several knowledge sources about the same text and compares their answers. Concepts that different sources return for the same thing are grouped, and each group gets a consensus level based on how many sources agree. Use it to pick well-supported identifiers for a term, or to see where sources disagree.

## How it works

1. **Query each source.** The text is sent to every selected source concurrently. Most sources run an ordinary search with the whole text as the query (up to 50 concepts each). BioLinker uses its sentence-annotation endpoint when the adapter provides one.
2. **Group concepts.** Concepts from different sources are grouped when they share a `primary_id`, or when any of their labels or synonyms have a normalized Levenshtein similarity of at least 0.8.
3. **Score agreement.** Each group gets a primary concept (the best-scoring one), the set of agreeing sources and a consensus level.
4. **Report** discrepancies and statistics.

{% hint style="warning" %}
There is no tokenisation or entity recognition step (except inside BioLinker): the whole text is one search query. Short terms and phrases such as "seizure" or "insulin resistance" give meaningful consensus. Long sentences mostly match whatever each source's full-text search ranks highest.
{% endhint %}

## Annotate a term

{% code title="annotate.py" %}
```python
import asyncio

from knowledge_lookup import KnowledgeSource, LookupConfig, MultiSourceAnnotator

SOURCES = [KnowledgeSource.HPO, KnowledgeSource.MONDO, KnowledgeSource.OLS]


async def main() -> None:
    annotator = MultiSourceAnnotator(LookupConfig(enabled_sources=SOURCES))
    try:
        result = await annotator.annotate_text("seizure", sources=SOURCES)
        print(f"overall confidence {result.overall_confidence:.2f}")
        for annotation in result.source_annotations:
            print(annotation.source.value, len(annotation.concepts), annotation.error)
        for agreement in annotator.get_consensus_annotations(result)[:5]:
            print(
                agreement.primary_concept.primary_label,
                agreement.confidence_level.value,
                round(agreement.consensus_score, 2),
                sorted(source.value for source in agreement.agreeing_sources),
            )
    finally:
        await annotator.close()


asyncio.run(main())
```
{% endcode %}

Typical output (live data varies):

```
overall confidence 0.26
HPO 50 None
MONDO 50 None
OLS 50 None
Seizure high 0.8 ['HPO', 'MONDO', 'OLS']
Seizure cluster medium 0.63 ['HPO', 'OLS']
Focal myoclonic seizure medium 0.63 ['HPO', 'OLS']
...
```

Without `sources`, the annotator uses BioLinker, OLS, BioPortal, OxO and UMLS. Sources that aren't initialised yet are added on demand; sources that can't start (for example BioPortal or UMLS without an API key) appear as annotations with an `error`.

## Methods

| Method | Description |
| --- | --- |
| `MultiSourceAnnotator(config=None)` | Creates its own `CentralKnowledgeLookup(config)` (available as `annotator.central_lookup`) |
| `await annotate_text(text, sources=None, enable_cross_reference=True, majority_vote_threshold=0.6)` | Annotate one text; returns `MultiSourceAnnotationResult` |
| `await annotate_sentence(sentence, ...)` | Same as `annotate_text()` |
| `await annotate_multiple_sentences(sentences, sources=None, enable_cross_reference=True, majority_vote_threshold=0.6, batch_delay=0.5)` | Annotate texts one after another, pausing `batch_delay` seconds between them |
| `get_consensus_annotations(result)` | Returns `result.consensus_concepts` |
| `await close()` | Close the underlying lookup |

{% hint style="info" %}
`enable_cross_reference` and `majority_vote_threshold` are accepted but currently don't change the result: cross-referencing is not implemented and the consensus levels use the fixed thresholds below. The label-matching threshold is the instance attribute `annotator.similarity_threshold` (default `0.8`).
{% endhint %}

## Understand the result

### `MultiSourceAnnotationResult`

| Field | Description |
| --- | --- |
| `sentence` | The annotated text |
| `source_annotations` | One `SourceAnnotation` per source |
| `consensus_concepts` | `list[ConceptAgreement]`, sorted by `consensus_score` |
| `discrepancies` | `list[dict]`, see below |
| `overall_confidence` | 0 to 1; the average of the mean consensus score and a level-weighted score (HIGH 1.0, MEDIUM 0.7, LOW 0.4, DISPUTED 0.1) |
| `processing_time` | Seconds |
| `annotation_stats` | `total_sources`, `successful_sources`, `failed_sources`, `total_consensus_concepts`, `confidence_distribution`, `concept_type_distribution`, `source_concept_counts`, `source_health`, `average_processing_time`, `fastest_source`, `slowest_source` |

### `SourceAnnotation`

`source`, `concepts`, `surface_forms` (the concept labels, or BioLinker's matched text), `positions` (only BioLinker fills these), `processing_time` and `error`.

### `ConceptAgreement`

| Field | Description |
| --- | --- |
| `primary_concept` | Representative `UnifiedConcept` of the group |
| `agreeing_sources` | `set[KnowledgeSource]` that returned a concept in the group |
| `disagreeing_sources` | Every other `KnowledgeSource` member, not only the queried ones |
| `alternative_concepts` | The group's other concepts |
| `confidence_level` | `AnnotationConfidence` |
| `consensus_score` | Agreement ratio multiplied by the primary concept's `confidence_score` |

### Consensus levels

The agreement ratio is the number of agreeing sources divided by the number of annotated sources, including sources that failed.

| `AnnotationConfidence` | Agreement ratio |
| --- | --- |
| `HIGH` | 0.8 or more |
| `MEDIUM` | 0.6 to below 0.8 |
| `LOW` | 0.4 to below 0.6 |
| `DISPUTED` | below 0.4 |

### Discrepancies

Each entry has a `type`, `description` and `count`:

* `single_source_concepts`: groups found by only one source, with `concepts` and `sources`
* `disputed_concepts`: groups with a `DISPUTED` level, with `concepts`
* `source_errors`: sources that failed, with `sources` and `errors`

{% hint style="info" %}
Import `SourceAnnotation`, `ConceptAgreement`, `MultiSourceAnnotationResult` and `AnnotationConfidence` from `knowledge_lookup`. `knowledge_lookup.models` has pydantic classes with the same names that the annotator does not return.
{% endhint %}

## Next steps

* [Searching concepts](searching-concepts.md): exact label de-duplication in a normal search
* [Knowledge source adapters](../adapters/README.md), including BioLinker
