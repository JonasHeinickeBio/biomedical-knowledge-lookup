---
description: PubTator 3 literature entities (genes, diseases, chemicals, variants) and text-mined relations for PubMed/PMC.
---

# PubTator 3 adapter

Looks up entities that PubTator 3 (NCBI/NLM) text-mines from PubMed abstracts and PMC full text, and the typed relations it extracts between them (`treat`, `cause`, `associate`, `inhibit`, ...), each with the number of supporting articles. Relations are machine-extracted, so this is a *silver* evidence source: good for ranking and for finding the literature behind a link, not curated truth. It also lists the articles an entity appears in (`get_publications`) for the evidence step.

| | |
|---|---|
| Source | `KnowledgeSource.PUBTATOR` |
| Class | `knowledge_lookup.adapters.PubTatorAdapter` |
| Requires | none (keyless) |
| Identifiers | `@GENE_BRCA1`, `@DISEASE_Fatigue_Syndrome_Chronic`; also MeSH (`D015673`, `MESH:D015673`) and NCBI Gene (`672`, `NCBIGene:672`) |
| Upstream API | `https://www.ncbi.nlm.nih.gov/research/pubtator3-api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import PubTatorAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with PubTatorAdapter(LookupConfig()) as adapter:
        hit = (await adapter.search_concepts("chronic fatigue", limit=3))[0]
        print(hit.primary_id, hit.concept_type)           # @DISEASE_Fatigue_Syndrome_Chronic DISEASE

        cfs = await adapter.get_concept_details("D015673")  # MeSH id works too
        print(cfs.primary_id, cfs.primary_label)

        for rel in await adapter.get_relationships(cfs.primary_id, limit=3):
            print(rel["relation_label"], rel["direction"], rel["related_id"], rel["publication_count"])

        for pub in await adapter.get_publications(cfs.primary_id, limit=3):
            print(pub["pmid"], pub["title"])


asyncio.run(main())
```

Output (live, October 2026):

```
@DISEASE_Fatigue_Syndrome_Chronic DISEASE
@DISEASE_Fatigue_Syndrome_Chronic Fatigue Syndrome Chronic
treat incoming @CHEMICAL_Hydrocortisone 47
associate incoming @CHEMICAL_Hydrocortisone 27
associate incoming @CHEMICAL_Serotonin 25
35046929 The Gut Microbiome in Myalgic Encephalomyelitis (ME)/Chronic Fatigue Syndrome (CFS)
...
```

## Identifiers

PubTator names an entity `@TYPE_Name` (the "accession"): the type (`GENE`, `DISEASE`, `CHEMICAL`, `VARIANT`, `SPECIES`, `CELLLINE`) plus the preferred label with spaces and most punctuation turned into `_`. Variants end in `_<gene>_<species>`, e.g. `@VARIANT_c.68_69del_BRCA1_human`. The accession is `primary_id`; the normalised database id is kept as a cross-reference (MeSH for diseases and chemicals, NCBI Gene for genes).

The entity-autocomplete endpoint cannot look up by database id, so MeSH and NCBI Gene ids are resolved through one `search` call (the highlighted text of the top article contains both forms). MeSH ids are ambiguous between diseases and chemicals, so up to two calls are made. `PUBTATOR:` prefixes and lower-case type prefixes are accepted.

## Methods

| Method | Endpoint | Returns |
|---|---|---|
| `search_concepts(query, limit, entity_types=None)` | `/entity/autocomplete/` | Entities matching a name or synonym. Without `entity_types` one unfiltered call returns a mix of types (`BRCA1` gives the gene plus variants, `fatigue` gives diseases). With e.g. `["GENE", "DISEASE"]` one call per type. |
| `get_concept_details(id)` | `/search/` (id resolution) + `/entity/autocomplete/` | One entity, found by exact accession match among the autocomplete hits. |
| `get_relationships(id, limit=50, relation_type=None, target_type=None)` | `/relations` | Relation edges, strongest first. |
| `get_mappings(id)` | autocomplete | The entity's own id: `MESH:D015673`, `NCBIGene:672`, `dbSNP` rsID or the parent NCBI gene of a variant. |
| `get_publications(id, limit=20)` | `/search/` | `pmid`, `title`, `journal`, `date`, `doi`, `pmcid`, `score` per article. |
| `get_publication_annotations(pmids)` | `/publications/export/biocjson` | Per PMID, the entities PubTator annotated (accession, name, type, identifier, mention text). |

Concept fields: `concept_type` follows the entity type (`GENE`, `DISEASE`, `CHEMICAL`, `ORGANISM` for species, `CELL_TYPE` for cell lines, `MOLECULAR_ENTITY` for variants); `synonyms` holds the matched synonym when the hit was a synonym match; `categories` carries PubTator's description (`All Species`, `BRCA1 (human)`); `confidence_score` is `0.9` for a name match and `0.7` otherwise; `source_data["PUBTATOR"]` is the raw hit.

### Relationships

Each edge has `relation_label` (PubTator's type: `treat`, `cause`, `associate`, `stimulate`, `inhibit`, `positive_correlate`, `negative_correlate`, ...), `related_id` (accession), `related_name`, `related_type`, `direction` and `publication_count`. `direction` is `outgoing` when the queried entity is the relation source, `incoming` when it is the target: `@CHEMICAL_Aspirin -treat-> @DISEASE_Stroke` is `outgoing` for aspirin and `incoming` for stroke. `relation_type="treat"` and `target_type="CHEMICAL"` filter server-side.

## Rate limits and caveats

- NCBI asks for about 3 requests per second; the adapter spaces requests by 0.34 s. Shared retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)).
- `/relations` has no limit parameter and answers with the full list: about 136 kB and 3 s for ME/CFS, 220 kB for aspirin. `limit` is applied client-side.
- Relation rows carry accessions only, so `related_name` is the accession with `_` turned back into spaces, not necessarily the exact preferred label. Call `get_concept_details` for the exact label.
- Species and cell-line autocomplete returned nothing for `human`, `HeLa` or `HEK293` when tested; genes, diseases, chemicals and variants work.
- `get_publications` fetches 10 articles per page, at most 5 pages per call.
- Latency in testing was 0.4 to 0.9 s per call, except `/relations` for popular entities.

## See also

- [Europe PMC adapter](europepmc_adapter.md), [SemMedDB adapter](semmeddb_adapter.md), [ClinicalTrials.gov adapter](clinicaltrials_adapter.md)
- [All adapters](../README.md)
