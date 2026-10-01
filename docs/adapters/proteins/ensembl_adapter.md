---
description: Ensembl gene records by stable ID or human gene symbol, plus a full catalog of the Ensembl REST API as async adapter methods.
---

# Ensembl adapter

Fetches gene records from the Ensembl REST API (display name, description, biotype, species), resolves human gene symbols to Ensembl gene IDs, and wraps the full Ensembl REST API as thin async methods (comparative genomics, lookup, mapping, phenotypes, sequences, VEP, GA4GH, and more — see the [endpoint catalog](#rest-endpoint-catalog) below).

| | |
|---|---|
| Source | `KnowledgeSource.ENSEMBL` |
| Class | `knowledge_lookup.adapters.EnsemblAdapter` |
| Requires | none |
| Identifiers | stable ID, e.g. `ENSG00000139618` |
| Upstream API | `https://rest.ensembl.org` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EnsemblAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with EnsemblAdapter(LookupConfig()) as adapter:
        brca2 = await adapter.get_concept_details("ENSG00000139618")
        print(brca2.primary_id, brca2.primary_label, brca2.categories)
        print(brca2.definitions[0])

        for concept in await adapter.search_concepts("TP53", limit=2):
            print(concept.primary_id, concept.primary_label)


asyncio.run(main())
```

Output (this run took about 50 seconds, mostly the symbol lookup):

```
ENSG00000139618 BRCA2 ['Biotype: protein_coding', 'Species: homo_sapiens']
BRCA2 DNA repair associated [Source:HGNC Symbol;Acc:HGNC:1101]
ENSG00000141510 TP53
LRG_321 TP53
```

## Searching

`search_concepts(query, limit)` is a **human gene symbol lookup**, not free-text search:

1. `/xrefs/symbol/homo_sapiens/{query}` returns matching Ensembl and LRG IDs.
2. `get_concept_details` is called for each of the first `limit` IDs.

The query must be a symbol or synonym known to Ensembl; other species are not searched. Each search costs one request plus one per result, and the xrefs endpoint can take ten seconds or more.

## Concept details

`get_concept_details(stable_id)` calls `/lookup/id/{id}?expand=1`.

| Field | Value |
|---|---|
| `primary_id` | stable ID |
| `primary_label` | `display_name` |
| `concept_type` | `GENE` (also for transcript or LRG IDs) |
| `definitions` | `[description]` |
| `categories` | `Biotype: <biotype>`, `Species: <species>` |
| `identifiers` | one `ENSEMBL` identifier, URL `https://www.ensembl.org/id/<id>` |
| `confidence_score` | `1.0` |
| `source_data[ENSEMBL]` | full lookup response (with `expand=1`, including transcripts) |

## REST endpoint catalog

Beyond symbol search and concept details, `EnsemblAdapter` wraps the entire
Ensembl REST API (base URL `https://rest.ensembl.org`). All methods are async,
return the parsed JSON payload directly (`None` on failure after retries), and
support `limit`/`offset` pagination where the API does. Python keywords are
escaped with a trailing underscore (`type_`, `all_`, `min_`, `max_`, `class_`,
`id_`) and map to the wire params `type`, `all`, `min`, `max`, `class`, `id`.
Methods that take a list of IDs POST a JSON array; methods that can go either
way (e.g. `map_cdna`) POST when given a list and GET with a single param
otherwise.

### Archive, comparative genomics, and cross-references

| Method | Endpoint | Notes |
|--------|----------|-------|
| `get_archive(archive_id)` | `GET /archive/id/:id` | Re-fetch a stored response via an archive ID (returned in `X-...-Archive` headers) |
| `get_cafes(species, cafe_type="expansion", ...)` | `GET /cafe/genetree/:species` | `cafe_type` = `expansion` \| `contraction` |
| `get_genetree(tax_id)` | `GET /genetree/:taxid` | Genomic context for a taxon |
| `get_alignment(species, seq_region, start, end, upstream=0, downstream=0, ...)` | `GET /alignment/region/:species/:seq_region/:start/:end` | `type_` = `dna` \| `pep` |
| `get_homology_by_symbol(species, symbol, ...)` | `GET /homology/symbol/:species/:symbol` | Backs `get_relationships` |
| `get_xrefs_by_name(species, name, dbname)` | `GET /xrefs/name/:species/:name/:dbname` | Backs `get_mappings` |

### `info/*`

`get_info_rest`, `get_info_ping`, `get_info_software`, `get_info_data`,
`get_info_species`, `get_info_variation`, `get_info_assembly(species, version)`,
`get_info_divisions`, `get_info_biotypes(species)`, `get_info_genomes`,
`get_info_populations`, `get_info_compara`, `get_info_analysis` — map one-to-one
to `GET /info/rest`, `/info/ping`, `/info/software`, `/info/data`,
`/info/species`, `/info/variation`, `/info/assembly/:species/:version`,
`/info/divisions`, `/info/biotypes/:species`, `/info/genomes`,
`/info/populations`, `/info/compara`, `/info/analysis`. Use `get_info_ping` as
a cheap health check.

### LD, lookup, mapping

| Method | Endpoint | Notes |
|--------|----------|-------|
| `get_ld(splicing)` | `GET /ld/:splicing` | Linkage-disease region |
| `lookup_ids(ids, expand=0, all_=0)` | `POST /lookup/id` | Batch Ensembl ID → full object |
| `lookup_symbols(species, symbols, expand=0, all_=0)` | `POST /lookup/symbol` | Batch symbol → Ensembl ID |
| `map_cdna(cdna_id, types=None, type_=None)` | `GET/POST /map/cdna/:id` | cDNA → features |
| `map_cds(cds_id, types=None, type_=None)` | `GET/POST /map/cds/:id` | CDS → features |
| `map_translation(translation_id, types=None, type_=None)` | `GET/POST /map/translation/:id` | Translation → features |
| `map_ids(species, ids, target)` | `POST /map/:species` | Body `{"id": [...], "target": ...}`; `target` = cdna \| cds \| exon \| genomic \| protein |

### Ontology, taxonomy, overlap

| Method | Endpoint | Notes |
|--------|----------|-------|
| `get_ontology(ontology_type, term=None, type_=None, id_=None)` | `GET /ontology/:type` | e.g. `go` |
| `get_ontology_parents(term_id)` | `GET /ontology/parents/:id` | |
| `get_ontology_id(term_id)` | `GET /ontology/id/:term_id` | |
| `get_taxonomy_id(tax_id)` | `GET /taxonomy/id/:tax_id` | |
| `get_taxonomy_name(name)` | `GET /taxonomy/name/:name` | |
| `get_taxonomy_common(common_name)` | `GET /taxonomy/common/:name` | |
| `get_taxonomy_root()` | `GET /taxonomy/root` | |
| `overlap_ids(ids, feature=None, all_=None)` | `POST /overlap/id` | |
| `get_overlap_region(species, seq_region, start, end, up=0, down=0, ...)` | `GET /overlap/region/:species/:seq_region/:start/:end` | `feature` = gene \| transcript \| regulatory |
| `overlap_translations(ids, feature=None, all_=None)` | `POST /overlap/translation` | |

### Phenotype

`get_phenotypes(species=None, term=None, accession=None, gene=None, region=None,
limit=100, offset=1)` → `GET /phenotype`; plus `get_phenotype(accession)`,
`get_phenotype_by_accession(accession)`, `get_phenotypes_by_gene(gene, species)`,
`get_phenotypes_by_region(species, seq_region, start, end)`, and
`get_phenotypes_by_term(term)` mapping one-to-one to the `/phenotype/...`
sub-endpoints.

### Regulation, sequence, transcript

| Method | Endpoint | Notes |
|--------|----------|-------|
| `get_binding_matrix(species, feature="protein_coding", matrix_type="all", ...)` | `GET /species/:species/binding_matrix` | `matrix_type` = all \| motif \| domain; `min_`/`max_` score bounds |
| `get_sequences(ids, type_="dna", class_=None)` | `POST /sequence/id` | `type_` = dna \| cdna \| pep |
| `get_sequence(species, seq_region, start, end, type_="dna", class_=None)` | `GET /sequence/region/:species/:seq_region/:start/:end` | |
| `get_transcript_haplotypes(transcript_id, ...)` | `GET /transcript/:id/haplotypes` | `type_` = ref \| alt; `min_`/`max_` frequency bounds |

### VEP and variation

| Method | Endpoint | Notes |
|--------|----------|-------|
| `vep_hgvs(species, hgvs, **params)` | `POST /vep/:species/hgvs` | Extra VEP options (`cache`, `canonical`, `extra`, ...) pass through as query params |
| `vep_ids(species, ids, **params)` | `POST /vep/:species/id` | |
| `vep_regions(species, regions, **params)` | `POST /vep/:species/region` | Regions may be strings or dicts |
| `get_variations(spid, type_=None, feature_type=None, limit=50, offset=0)` | `GET /variation` | `spid` is `\|`-separated species |
| `get_variations_by_pmcid(pmcid)` | `GET /variation/pmcid/:pmcid` | |
| `get_variations_by_pmid(pmid)` | `GET /variation/pmid/:pmid` | |
| `variant_recoder(spid, ...)` | `GET /variant_recoder` | Recode variants between reference genomes |

### GA4GH v0.7

All GA4GH resources are wrapped through a shared `_ga4gh(resource, id,
**params)` helper. Each has a list form (`GET /ga4gh/<resource>`) and, where
the API supports it, a single-item form (`GET /ga4gh/<resource>/:id`):
`ga4gh_beacon`, `ga4gh_callsets`, `ga4gh_datasets`, `ga4gh_features` (uses a
`featureset` query param instead of a path ID), `ga4gh_featuresets`,
`ga4gh_references`, `ga4gh_referencesets`, `ga4gh_searches`,
`ga4gh_variants`, `ga4gh_variantsets`.

## Live responses

`scripts/probe_ensembl_endpoints.py` fires one live request at every endpoint
above (with realistic sample values), saves the raw JSON per endpoint under
`docs/adapters/proteins/ensembl_rest_responses/<endpoint>.json`, and writes a
`manifest.json` summarizing status, byte size, elapsed time, response shape,
and a truncated sample for each. Run it with:

```bash
poetry run python scripts/probe_ensembl_endpoints.py
# --only <regex> to subset, --base-url to override, --no-ga4gh to skip GA4GH
```

> **Status: pending.** The Ensembl platform (all REST hosts, mirrors, and the
> status page) was down when this catalog was written, so the captured
> responses and per-endpoint notes are still to be filled in once the API
> recovers. The probe script is ready and was sanity-checked offline
> (all 67 probes build with the expected skip/active behavior).

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`. Through `CentralKnowledgeLookup` the whole search must finish within `timeout_per_source` (default 30 s), which a slow symbol lookup can exceed. Raise the timeout, or call `get_concept_details` when you already have the ID.

## See also

- [HGNC adapter](hgnc_adapter.md): symbol → HGNC record with the Ensembl ID
- [Open Targets adapter](../core/opentargets_adapter.md): uses Ensembl gene IDs for targets
- [All adapters](../README.md)
