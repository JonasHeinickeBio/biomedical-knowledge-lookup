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

Beyond symbol search, concept details, relationships and mappings,
`EnsemblAdapter` wraps the whole Ensembl REST catalog (base URL
`https://rest.ensembl.org`, release 15.12 paths). All methods are async and
return the parsed JSON payload. Unlike the interface methods above, they
**propagate** errors so the shared retry / circuit-breaker machinery handles
transient failures. Python keywords are escaped with a trailing underscore
(`type_`, `all_`, `class_`, `id_`, `min_`, `max_`) and map to the wire params
`type`, `all`, `class`, `id`, `min`, `max`.

Batch POST endpoints need a keyed JSON object, not a bare array. A bare array
returns HTTP 500, and the key differs per endpoint: `ids` for
`lookup/id`, `sequence/id`, `vep/.../id`, `variation` and `variant_recoder`;
`hgvs_notations` for `vep/.../hgvs`; `variants` for `vep/.../region`;
`symbols` for `lookup/symbol`. The wrappers build these bodies for you.

This table is generated from the adapter's signatures and docstrings.

### Archive

| Method | Endpoint | Notes |
|---|---|---|
| `get_archive(archive_id)` | `GET /archive/id/:id` | Fetch a stored REST response. `archive_id` is the archive identifier captured from the header of a previous Ensembl REST response. |

### Comparative genomics

| Method | Endpoint | Notes |
|---|---|---|
| `get_cafe_genetree(gene_id)` | `GET /cafe/genetree/id/:id` | Copy-number events (CAFE) on the gene tree of a gene. |
| `get_cafe_genetree_by_symbol(species, symbol)` | `GET /cafe/genetree/member/symbol/:species/:symbol` | CAFE gene tree via a gene symbol. |
| `get_genetree(gene_id)` | `GET /genetree/id/:id` | Gene tree containing a gene. |
| `get_genetree_by_symbol(species, symbol)` | `GET /genetree/member/symbol/:species/:symbol` | Gene tree via a gene symbol. |
| `get_alignment(species, region, method=None, alignment=None, data=None, type_=None)` | `GET /alignment/region/:species/:region` | Conserved alignment over a region. `region` is a coordinate string such as `"11:2159779-2159779:1"`; `type_`: dna \| pep. |
| `get_homology_by_id(species, gene_id, homology_type=None, target_species=None)` | `GET /homology/id/:species/:id` | Homologies for an Ensembl gene ID. `homology_type`: all \| orthologues \| paralogues \| reciprocal \| nonreciprocal \| one2one \| one2many \| many2one \| many2many. |
| `get_homology_by_symbol(species, symbol, homology_type=None, target_species=None)` | `GET /homology/symbol/:species/:symbol` | Homologies for a gene symbol. `homology_type`: all \| orthologues \| paralogues \| reciprocal \| nonreciprocal \| one2one \| one2many \| many2one \| many2many. |

### Cross references

| Method | Endpoint | Notes |
|---|---|---|
| `get_xrefs_by_name(species, name, dbname=None)` | `GET /xrefs/name/:species/:name` | Cross-references for a name. `dbname` is now an optional query filter rather than a path segment. |

### Information

| Method | Endpoint | Notes |
|---|---|---|
| `get_info_rest()` | `GET /info/rest` | REST service metadata. |
| `get_info_ping()` | `GET /info/ping` | Service liveness check. |
| `get_info_software()` | `GET /info/software` | Installed software versions. |
| `get_info_data(database=None)` | `GET /info/data` | Database version info or `GET /info/data/:database`. |
| `get_info_species(species=None, tax_id=None, format_=None)` | `GET /info/species` | Species and division info. `format_`: list \| hash. |
| `get_info_variation(species)` | `GET /info/variation/:species` | Variation databases for a species. |
| `get_info_consequence_types()` | `GET /info/variation/consequence_types` | All known consequence types. |
| `get_info_assembly(species, region_name=None)` | `GET /info/assembly/:species` | Assembly for a species, optionally one region or `GET /info/assembly/:species/:region_name`. |
| `get_info_divisions()` | `GET /info/divisions` | Available divisions. |
| `get_info_biotypes(species, type_=None)` | `GET /info/biotypes/:species` | Biotypes for a species. `type_`: e.g. gene \| regulatory. |
| `get_info_biotypes_by_name(name, object_type)` | `GET /info/biotypes/name/:name/:object_type` | Biotype by name. |
| `get_info_biotypes_by_group(group, object_type)` | `GET /info/biotypes/groups/:group/:object_type` | Biotypes by group. |
| `get_info_external_dbs(species)` | `GET /info/external_dbs/:species` | External databases used by a species. |
| `get_info_eg_version()` | `GET /info/eg_version` | Ensembl Genomes release. |
| `get_info_genome(genome_name)` | `GET /info/genomes/:genome_name` | Genome by name. |
| `get_info_genomes_by_accession(accession)` | `GET /info/genomes/accession/:accession` | Genomes by assembly accession. |
| `get_info_genomes_by_assembly(assembly_id)` | `GET /info/genomes/assembly/:assembly_id` | Genomes by assembly ID. |
| `get_info_genomes_by_division(division_name)` | `GET /info/genomes/division/:division_name` | Genomes by division. |
| `get_info_genomes_by_taxonomy(taxon_name)` | `GET /info/genomes/taxonomy/:taxon_name` | Genomes by taxon name. |
| `get_info_populations(species, population_name=None)` | `GET /info/variation/populations/:species` | Populations for a species (optionally `/:population_name`). |
| `get_info_comparas()` | `GET /info/comparas` | Compara database releases. |
| `get_info_compara_methods()` | `GET /info/compara/methods` | Compara analysis methods. |
| `get_info_compara_species_sets(method)` | `GET /info/compara/species_sets/:method` | Species sets for a Compara method. |
| `get_info_analysis(species)` | `GET /info/analysis/:species` | Analyses for a species. |

### Linkage disequilibrium

| Method | Endpoint | Notes |
|---|---|---|
| `get_ld_by_id(species, id_, population_name, window_size=None, d_prime=None, r2=None)` | `GET /ld/:species/:id/:population_name` | LD around a variant. |
| `get_ld_pairwise(species, id1, id2, population_name=None, d_prime=None, r2=None)` | `GET /ld/:species/pairwise/:id1/:id2` | LD between two variants. Without `population_name` the server returns one record per population; with it, only that population's record. |
| `get_ld_region(species, region, population_name, window_size=None, d_prime=None, r2=None)` | `GET /ld/:species/region/:region/:population_name` | LD in a region. |

### Lookup (batch)

| Method | Endpoint | Notes |
|---|---|---|
| `lookup_ids(ids, expand=0, all_=0)` | `POST /lookup/id` | Batch object lookup with body `{"ids": [...]}`. (A bare JSON array is rejected by the server with a 500.) `all_`: 1 to include objects from all databases, not just the matching species. |
| `lookup_symbols(species, symbols, expand=0, all_=0)` | `POST /lookup/symbol/:species` | Batch symbol lookup with body `{"symbols": [...]}`. |

### Mapping

| Method | Endpoint | Notes |
|---|---|---|
| `map_cdna(cdna_id, region)` | `GET /map/cdna/:id/:region` | Map a cDNA coordinate range to genomic features (`region` like `100..200`). |
| `map_cds(cds_id, region)` | `GET /map/cds/:id/:region` | Map a CDS coordinate range to genomic features. |
| `map_translation(translation_id, region)` | `GET /map/translation/:id/:region` | Map translation (protein) coordinates onto genomic features. |

### Ontologies

| Method | Endpoint | Notes |
|---|---|---|
| `get_ontology_by_name(name)` | `GET /ontology/name/:name` | Terms for an ontology by name. |
| `get_ontology_ancestors(term_id)` | `GET /ontology/ancestors/:id` | Ancestor terms. |
| `get_ontology_ancestors_chart(term_id)` | `GET /ontology/ancestors/chart/:id` | Ancestor chart. |
| `get_ontology_descendants(term_id)` | `GET /ontology/descendants/:id` | Descendant terms. |
| `get_ontology_id(term_id)` | `GET /ontology/id/:term_id` | A single term. |

### Taxonomy

| Method | Endpoint | Notes |
|---|---|---|
| `get_taxonomy_id(tax_id)` | `GET /taxonomy/id/:tax_id` | Species by NCBI taxon ID. |
| `get_taxonomy_name(name)` | `GET /taxonomy/name/:name` | Species by scientific name. |
| `get_taxonomy_classification(tax_id)` | `GET /taxonomy/classification/:id` | Full lineage of a taxon. |

### Overlap

| Method | Endpoint | Notes |
|---|---|---|
| `get_overlap_id(id_, feature=None, all_=None, limit=None, offset=None)` | `GET /overlap/id/:id` | Objects overlapping an Ensembl ID. `feature`: e.g. gene \| transcript \| variation. |
| `get_overlap_region(species, region, feature=None, all_=None, limit=None, offset=None)` | `GET /overlap/region/:species/:region` | Objects overlapping a region. `region` is a coordinate string like `X:1000000..1001000`; `feature`: e.g. gene \| transcript \| regulatory. |
| `get_overlap_translation(translation_id, feature=None, all_=None)` | `GET /overlap/translation/:id` | Domain features overlapping a translation. |

### Phenotype

| Method | Endpoint | Notes |
|---|---|---|
| `get_phenotypes_by_gene(species, id_, limit=100, offset=1)` | `GET /phenotype/gene/:species/:id` | Phenotypes annotated to a gene. |
| `get_phenotype_by_accession(species, accession, limit=100, offset=1)` | `GET /phenotype/accession/:species/:accession` | Phenotypes by accession. |
| `get_phenotypes_by_region(species, region, limit=100, offset=1)` | `GET /phenotype/region/:species/:region` | Phenotypes in a region. |
| `get_phenotypes_by_term(species, term, limit=100, offset=1)` | `GET /phenotype/term/:species/:term` | Phenotypes matching a description. |

### Regulation

| Method | Endpoint | Notes |
|---|---|---|
| `get_binding_matrix(species, stable_id, feature='protein_coding', matrix_type='all', limit=100, offset=1, min_=None, max_=None)` | `GET /species/:species/binding_matrix/:stable_id` | Regulatory binding sites for a PFM. `stable_id`: e.g. `ENSPFM0001`; `matrix_type`: all \| motif \| domain; `min_`/`max_`: matrix-score bounds. |

### Sequence

| Method | Endpoint | Notes |
|---|---|---|
| `get_sequences(ids, type_='dna', class_=None)` | `POST /sequence/id` | Sequences by Ensembl ID with body `{"ids": [...]}`. `type_`: dna \| cdna \| pep. |
| `get_sequence_by_id(id_, type_='dna', class_=None)` | `GET /sequence/id/:id` | Sequence of one object. `type_`: dna \| cdna \| pep. |
| `get_sequence(species, region, type_='dna', class_=None)` | `GET /sequence/region/:species/:region` | Sequence of a region. `region` is a coordinate string like `11:2159990-2160000`; `type_`: dna \| cdna \| pep. |

### Transcript haplotypes

| Method | Endpoint | Notes |
|---|---|---|
| `get_transcript_haplotypes(species, transcript_id, assembly=None, population=None, type_=None, min_=None, max_=None)` | `GET /transcript_haplotypes/:species/:id` | Haplotype coverage of a transcript. `type_`: ref \| alt; `min_`/`max_`: frequency bounds. |

### VEP

| Method | Endpoint | Notes |
|---|---|---|
| `get_vep_id(species, id_, **params)` | `GET /vep/:species/id/:id` | VEP consequences for one variant id. Extra VEP options (`canonical`, `hgvs`, `numbers`, `domains`, `updown`, `distance`, ...) pass through as query params, same as the batch POST wrappers below. |
| `get_vep_hgvs(species, hgvs_notation, **params)` | `GET /vep/:species/hgvs/:hgvs_notation` | VEP consequences for one HGVS string. |
| `get_vep_region(species, region, allele, **params)` | `GET /vep/:species/region/:region/:allele` | VEP consequences for one region/allele pair. |
| `vep_hgvs(species, hgvs, **params)` | `POST /vep/:species/hgvs` | VEP over HGVS variant strings with body `{"hgvs_notations": [...]}`. Extra VEP options (`cache`, `dir`, `canonical`, `extra`, `population`, `hgvs`, `limit`, `offset`) pass through as query params. |
| `vep_ids(species, ids, **params)` | `POST /vep/:species/id` | VEP over Ensembl variation IDs with body `{"ids": [...]}` (extra VEP options as in :meth:`vep_hgvs`). |
| `vep_regions(species, regions, **params)` | `POST /vep/:species/region` | VEP over genomic variants with body `{"variants": [...]}`. Each entry is a VEP default-format line, e.g. `"11 2159779 2159779 G/A 1"` (chrom, start, end, ref/alt, strand). Extra VEP options as in :meth:`vep_hgvs`. |

### Variation

| Method | Endpoint | Notes |
|---|---|---|
| `get_variation(species, id_, **params)` | `GET /variation/:species/:id` | A single variation. `params`: `pops` \| `population_genotypes` \| `genotypes`. |
| `get_variations_by_ids(species, ids, **params)` | `POST /variation/:species` | Batch variations with `{"ids": [...]}`. |
| `get_variations_by_pmcid(species, pmcid, limit=10, offset=1)` | `GET /variation/:species/pmcid/:pmcid` | Variations in a PMC article. |
| `get_variations_by_pmid(species, pmid, limit=10, offset=1)` | `GET /variation/:species/pmid/:pmid` | Variations in a PubMed article. |
| `get_variant_recoder(species, id_, **params)` | `GET /variant_recoder/:species/:id` | Recodes for one variant. |
| `variant_recoder(species, ids, **params)` | `POST /variant_recoder/:species` | Batch recoding with `{"ids": [...]}`. |

### GA4GH

| Method | Endpoint | Notes |
|---|---|---|
| `ga4gh_beacon(**params)` | `GET /ga4gh/beacon` | Beacon service info. |
| `ga4gh_beacon_query(reference_name, start, reference_bases, alternate_bases, assembly_id='GRCh38', **params)` | `GET /ga4gh/beacon/query` | Beacon v2 query (GET form). `start` is 0-based. Do not pass `datasetIds`: the server rejects every dataset id it advertises ("Invalid datasetId"), while omitting it queries the default dataset. The legacy `chrom` / `allele` / `assembly` params are not understood: the server answers HTTP 200 with an embedded `error` object instead of failing. |
| `ga4gh_beacon_query_post(request)` | `POST /ga4gh/beacon/query` | Beacon query (GA4GH body). `request` keys (Beacon v2, as in :meth:`ga4gh_beacon_query`): `referenceName` \| `start` \| `referenceBases` \| `alternateBases` \| `assemblyId`. Omit `datasetIds` (a list is stringified server-side to `ARRAY(0x...)` and rejected). |
| `ga4gh_callsets(callset_id, **params)` | `GET /ga4gh/callsets/:id` | A single callset. 15.12 has no callset search endpoint — ids come from the `calls` arrays embedded in variant responses. |
| `ga4gh_get_dataset(dataset_id, **params)` | `GET /ga4gh/datasets/:id` | A single dataset. |
| `ga4gh_search_datasets(**body)` | `POST /ga4gh/datasets/search` | (body keys: `pageSize`). |
| `ga4gh_get_feature(feature_id, **params)` | `GET /ga4gh/features/:id` | A single feature. |
| `ga4gh_search_features(**body)` | `POST /ga4gh/features/search` |  Body needs `featureSetId` (singular, e.g. `"Ensembl.116.GRCh38"`) plus `referenceName` / `start` / `end`. Slow: ~50 s for a 1.4 kb window. |
| `ga4gh_get_featureset(featureset_id, **params)` | `GET /ga4gh/featuresets/:id` | A single feature set. |
| `ga4gh_search_featuresets(**body)` | `POST /ga4gh/featuresets/search` |  `datasetId` must be the literal `"Ensembl"`; the 1000 Genomes id returned by :meth:`ga4gh_search_datasets` gives a 400. |
| `ga4gh_get_reference(reference_id, **params)` | `GET /ga4gh/references/:id` | A single reference. |
| `ga4gh_search_references(**body)` | `POST /ga4gh/references/search` | (body needs `referenceSetId`, e.g. `"GRCh38"`). |
| `ga4gh_search_variant_annotations(**body)` | `POST /ga4gh/variantannotations/search` |  Body needs `variantAnnotationSetId` (e.g. `"Ensembl"`) plus `referenceName` / `start` / `end`. Unlike the other collections this one has no single-item GET. |
| `ga4gh_get_variant(variant_id, **params)` | `GET /ga4gh/variants/:id` | A single variant. |
| `ga4gh_search_variants(**body)` | `POST /ga4gh/variants/search` |  Body needs `variantSetId` plus `referenceName` / `start` / `end`. |
| `ga4gh_get_variantset(variantset_id, **params)` | `GET /ga4gh/variantsets/:id` | A single variant set. |
| `ga4gh_search_variantsets(**body)` | `POST /ga4gh/variantsets/search` | (body needs `datasetId`). |


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
