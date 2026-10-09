---
description: NCBI Gene Expression Omnibus series, curated datasets, platforms and samples via E-utilities (metadata and URLs only).
---

# GEO adapter

Finds functional-genomics datasets (expression, methylation, ChIP-/ATAC-seq, ...) in the NCBI Gene Expression Omnibus through the E-utilities `gds` database. It returns **metadata and URLs only** and never downloads data files: supplementary files appear as file *types* (`CSV, IDAT`) and the FTP folder as a URL. Its main use here is dataset discovery, for example "which GEO series study ME/CFS or Long COVID, on which platform, with how many samples and which paper".

| | |
|---|---|
| Source | `KnowledgeSource.GEO` |
| Class | `knowledge_lookup.adapters.GEOAdapter` |
| Requires | none (`NCBI_API_KEY` raises the rate limit, `NCBI_EMAIL` is optional) |
| Identifiers | `GSE226260` (series), `GDS5435` (curated dataset), `GPL21145` (platform), `GSM9652321` (sample); lower case and a `GEO:` prefix are accepted |
| Upstream API | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (`db=gds`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import GEOAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with GEOAdapter(LookupConfig()) as adapter:
        hits = await adapter.search_concepts('"long covid" AND "Homo sapiens"[ORGN]', limit=3)
        for concept in hits:
            print(concept.primary_id, concept.primary_label[:70])

        series = await adapter.get_concept_details("GSE226260")
        print(series.primary_label[:60], series.source_data[adapter.get_source()]["n_samples"])
        for rel in await adapter.get_relationships("GSE226260", limit=3):
            print(rel["relation_label"], rel["related_id"])
        print([m["toId"] for m in await adapter.get_mappings("GSE226260")])


asyncio.run(main())
```

Output (recorded 2026-10-09):

```
GSE335593 Severe long-COVID is driven by monocyte reprogramming and broad immune
GSE348165 Persistent Borrelia burgdorferi protein antigen in CD16⁺ monocytes is
GSE343379 Narsoplimab (anti-MASP2) modulates long COVID patient plasma-induced t
Long COVID involves activation of proinflammatory and immune exhaustion pathways 331
uses_platform GPL34284
uses_platform GPL24676
has_sample GSM7069899
has_publication PMID:41388153
has_organism NCBITaxon:9606
['PMID:41388153', 'NCBITaxon:9606', 'BioProject:PRJNA939253', 'SRA:SRP424803']
```

## Searching

`search_concepts(query, limit=20, entry_type=None)` runs `esearch` on `db=gds` and one `esummary` for the hits.

- **Scope.** Without `entry_type` the query is wrapped as `(<query>) AND (gse[ETYP] OR gds[ETYP])`, i.e. series and curated datasets. Samples alone would drown the result (202 samples against 30 series for "chronic fatigue syndrome"). Pass `entry_type="series" | "dataset" | "platform" | "sample" | "any"`, or put `gse[ETYP]`, `gsm[ETYP]`, ... into the query yourself and no restriction is added. An unknown `entry_type` returns `[]`.
- **Field syntax.** The query is passed to NCBI as is, so GEO fields work (from `einfo`): `"Homo sapiens"[ORGN]` organism, `[GTYP]` dataset type (`"expression profiling by array"[GTYP]`), `[PTYP]` platform technology, `2024/01:2026/12[PDAT]` publication date, `50:1000[NSAM]` number of samples, `[MESH]`, `[ACCN]` accession, `[AUTH]`, `[SRC]` sample source. `GPL24676[ACCN]` restricts to records of a platform (it also matches the platform and sample entries, so combine it with `gse[ETYP]`). `[GPL]`, `[PMID]` and `[TaxID]` are **not** fields; NCBI silently treats them as plain words and returns nothing useful. Free text is mapped to MeSH where possible (`chronic fatigue syndrome` also matches the MeSH heading).
- **Order.** Newest first. `sort=relevance` is accepted by NCBI but changes nothing (verified), `sort=pdat` is rejected, so no sort is sent; rank is not a relevance score. `confidence_score` just decreases from 0.9 with position.
- `limit` is capped at 50 per call because every `esummary` document lists all sample accessions.
- A query that is itself an accession (`GSE226260`) goes straight to details.

Example queries for the research focus (counts on 2026-10-09): `chronic fatigue syndrome` 30 series; `long covid` 53 series; `"long covid" OR "post-acute covid"` 55; `fatigue` 351. Mouse and hamster models of Long COVID are in there too (check `categories` for the organism).

## Concept details

| Field | Value |
|---|---|
| `primary_id` | accession (`GSE226260`) |
| `primary_label` | record title |
| `concept_type` | `STUDY` (series, dataset), `ASSAY` (platform), `OBSERVATION` (sample) |
| `definitions` | the summary (capped at 6,000 characters) |
| `semantic_types` | `GEO Series` / `GEO DataSet` / `GEO Platform` / `GEO Sample`, then the GEO data types (e.g. `Expression profiling by high throughput sequencing`) |
| `categories` | organisms (`Homo sapiens`) |
| `identifiers` | the accession with its GEO page URL |
| `source_data[GEO]` | `uid`, `url`, `organisms`, `data_type`, `platforms` (GPL list), `series` (parent GSE for datasets and samples), `n_samples`, `pubmed_ids`, `bioproject`, `sra_studies`, `publication_date`, `supplementary_file_types`, `ftp_url`, `geo2r_available`, `platform_technology`, `value_type`, `subset_info`, `series_title`, `platform_title`, `license_note` |

The accession is converted to the `gds` UID without a search call: GSE `200000000 + n`, GPL `100000000 + n`, GSM `300000000 + n`, GDS the bare number.

## Relationships and mappings

`get_relationships(id, limit=50)` (the cap applies to samples and to the series of a platform):

| `relation_label` | From | `related_id` |
|---|---|---|
| `uses_platform` | series, dataset, sample | `GPL...`, `related_name` is the platform title (one extra `esummary`) |
| `has_sample` | series, dataset | `GSM...` sorted by number, `related_name` the sample title, `total_samples` the real count |
| `part_of_series` | sample | `GSE...` |
| `derived_from_series` | dataset | `GSE...` with the series title |
| `used_by_series` | platform | `GSE...` (the platform's list is truncated by NCBI for popular platforms) |
| `has_publication` | all with PubMed links | `PMID:<id>` |
| `has_organism` | all | `NCBITaxon:<id>` with the scientific name (`elink` to taxonomy plus one taxonomy `esummary`) |

`get_mappings(id)` returns `PMID:` (`toSource` `PUBMED`, type `cites`), `NCBITaxon:` (`NCBITAXON`, `organism`), `BioProject:PRJNA...` (`BIOPROJECT`) and `SRA:SRP...` (`SRA`), all with confidence 1.0. BioProject and SRA study ids are only present where GEO exposes them (sequencing series; GSE226260 has both, array-only or old series often have neither). BioSample ids are not exposed in the `esummary`.

## Usage guidelines, rate limits and licence

- NCBI E-utilities policy ([guidelines](https://www.ncbi.nlm.nih.gov/books/NBK25497/)): at most **3 requests/s** without an API key, **10/s** with one. The adapter spaces calls to 0.34 s (0.11 s with a key). Set `NCBI_API_KEY` (or `ncbi` in `LookupConfig.api_keys`) for the higher limit; large jobs should run outside US weekday peak hours.
- `tool=knowledge-lookup` is sent with every call. A contact address (`NCBI_EMAIL` or `ncbi_email`) is sent only if you configure one; nothing identifying is sent otherwise.
- GEO records are public. NCBI's disclaimer applies and submitters may claim rights over their data: cite the GEO accession and the associated publication. This adapter does not fetch supplementary files, SOFT/MINiML files or SRA reads; the URLs it returns point to the GEO page and the FTP folder (`ftp_url` is the `ftp://` link NCBI reports; the same folder is served over HTTPS, HEAD-checked for GSE327255: HTTP 200).
- Shared HTTP retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). All methods log errors and return `[]` / `None`.

## Caveats

- Response size is driven by the sample list: a series with 75 samples is a 6 KB `esummary`, one with 805 samples about 48 KB; platforms with very many series are about 43 KB (GPL570). `limit` therefore also bounds the transfer.
- `esearch` has no relevance ranking and no pagination in this adapter; refine with fields instead of asking for more.
- Curated DataSets (GDS) exist only for a small fraction of series; a search for `long covid OR chronic fatigue syndrome` restricted to datasets returned none at the time of writing.
- The GEO data type of a series (`gdstype`) can hold several values separated by `;`; they are split into `semantic_types`.
- Study design (case/control labels, tissue, treatment) lives in the per-sample characteristics, which `esummary` does not return; use the GEO page or GEO2R (`geo2r_available`) for that.

## Live verification (2026-10-09)

- `esearch` for `chronic fatigue syndrome AND gse[ETYP]`: 30 series, 0.35 s; full search plus `esummary` of 5-50 hits 0.7-1.1 s.
- `esummary` documents: 6 KB (75 samples), 55 KB for two series with 805 and 86 samples, 11 KB for a platform with a long `gse` list.
- Details 0.4-4.2 s (NCBI latency varies run to run); relationships 2-4 s (up to four sequential calls); mappings 1.7-3 s (two calls: `esummary` and `elink`).
- Verified against real records: GSE327255 (ME/CFS saliva methylation, 75 samples, PMID 42010606), GSE226260 (Long COVID, 331 samples, BioProject and SRA study), GSE292461 (hamster), GPL21145, GDS5435, GSM1. `python -m knowledge_lookup check GEO` passes.
- Not verified: behaviour above 3 requests/s with a key (no key was available), and `elink` to BioSample/SRA ids (only the ids already in the `esummary` are used).

## See also

- [MedGen adapter](../phenotypes/medgen_adapter.md), [dbSNP adapter](../phenotypes/dbsnp_adapter.md) (same E-utilities conventions)
- [Zenodo adapter](zenodo_adapter.md), [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
