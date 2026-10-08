---
description: Genomics England PanelApp expert-reviewed gene panels, with green/amber/red gene evidence, inheritance and phenotypes.
---

# PanelApp adapter

Searches [Genomics England PanelApp](https://panelapp.genomicsengland.co.uk/), a curated knowledgebase of gene panels for rare disease and cancer. Each panel lists genes with a traffic-light **confidence level** (green = diagnostic-grade, amber = borderline, red = insufficient evidence), a mode of inheritance, phenotypes and publications. Use it to answer "which genes are expert-curated for this disorder" and "on which panels, and with what evidence, is this gene".

| | |
|---|---|
| Source | `KnowledgeSource.PANELAPP` |
| Class | `knowledge_lookup.adapters.PanelAppAdapter` |
| Requires | none (keyless) |
| Identifiers | panel: numeric id (`158`, `panelapp:158`); gene: `HGNC:1100` or the symbol `BRCA1` |
| Upstream API | `https://panelapp.genomicsengland.co.uk/api/v1` (override with `PANELAPP_API_BASE`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import PanelAppAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with PanelAppAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("ataxia", limit=3):
            print(concept.primary_id, concept.primary_label)

        # genes of a panel, best evidence first
        for rel in await adapter.get_relationships("158", limit=3, evidence_level="green"):
            print(rel["relation_label"], rel["related_name"], rel["mode_of_inheritance"])

        # panels a gene is on
        for rel in await adapter.get_relationships("BRCA1", limit=2):
            print(rel["relation_label"], rel["related_name"], rel.get("confidence_level"))


asyncio.run(main())
```

## Searching

`search_concepts(query, limit)` returns panels, plus the gene when the query is one exact symbol-like word.

- The PanelApp list endpoint ignores `search=` and `page_size=` (verified), and `name=` only matches one phrase against the panel name. The adapter therefore downloads the full panel list once (433 panels, 5 pages of 100, about 375 KB, 3 to 8 s including politeness delay) and caches it for 10 minutes. Matching is local: every query word must occur in the panel name, disease group, sub-group or *relevant disorders*.
- Scores: exact name `0.95`, all words in the name `0.8`, only via disease group or relevant disorders `0.6`. Larger panels rank first within a score.
- A gene lookup (one extra request, `genes/?entity_name=SYMBOL`, exact match, upper-cased) happens only for single-token queries. An exact gene hit comes first with `0.95`. There is no partial or alias gene search.

Panels are typed `DISEASE`; genes `GENE`.

## Concept details

`get_concept_details(concept_id)`:

- **Panel** (`158`): `panels/{id}/`. `source_data[PANELAPP]` has `version`, `version_created`, `disease_group`, `disease_sub_group`, `relevant_disorders`, `stats` (genes / STRs / regions), `types` and `gene_confidence_counts` (`green`/`amber`/`red`). `synonyms` holds the relevant disorders (test-directory codes such as `R295` excluded). This endpoint returns every gene of the panel: 25 KB for 27 genes, 470 KB for the 494-gene mitochondrial disorders panel.
- **Gene** (`HGNC:1100` or `BRCA1`): all panel entries of the gene (`genes/?entity_name=BRCA1`: 28 records, about 50 KB). `source_data[PANELAPP]` has `n_panels`, `confidence_counts`, `green_modes_of_inheritance`, `omim_gene`, `ensembl_id`, `biotype`. `synonyms` are the aliases, `definitions` the gene name.

`genes/` cannot filter by HGNC id (verified: `hgnc_id=` is ignored), so `HGNC:n` is resolved to a symbol through the HGNC REST service (`rest.genenames.org/fetch/hgnc_id/HGNC:n`, keyless, cached per adapter). Unknown or retired ids return `None`.

## Relationships

`get_relationships(concept_id, limit=25, evidence_level=None)`. `limit` caps each relation type; `evidence_level` is `green`/`amber`/`red` (or `3`/`2`/`1`) and keeps only that level; an invalid value returns `[]`. All edges carry `source: "PANELAPP"`.

| From | `relation_label` | Notes |
|---|---|---|
| gene | `listed_in_panel` | `related_id` panel id, plus `confidence_level`, `mode_of_inheritance`, `mode_of_pathogenicity`, `penetrance`, `phenotypes`, `publications` (PMIDs), `panel_version`, `disease_group`. Green first, then amber, red; by panel name |
| gene | `associated_with_phenotype` | distinct phenotype strings from green and amber entries; `related_id` is `OMIM:<n>` when the string carries one, OMIM-coded first. The field also holds notes such as "Adult only" |
| panel | `has_gene` | `related_id` HGNC id, `related_name` symbol, same extras. Requests `panels/{id}/genes/?confidence_level=3`, then `2`, then `1` until `limit` is reached (the endpoint honours `confidence_level`, pages of 100) |
| panel | `has_relevant_disorder` | free text or NHS test-directory code (`R169`, `GT220`, `TP313`; `is_test_directory_code` flags them) |

## Mappings

`get_mappings(gene)` returns `HGNC.SYMBOL`, `ENSEMBL` (newest GRCh38 release in the record) and `OMIM` (gene id as exposed). PanelApp's HGNC data come from a 2017 release, so a few symbols are outdated. Panels have no cross-references and return `[]`.

## Other deployments

PanelApp Australia runs the same software: `PANELAPP_API_BASE=https://panelapp-aus.org/api/v1` (verified: `panels/?name=ataxia` returns one panel in 1.2 s). Only `https://` bases are accepted; anything else falls back to Genomics England. Panel ids differ between deployments.

## Rate limits, size and errors

No limit is published. Requests are spaced 0.3 s and use the shared retry and circuit breaker. Large responses are bounded by `limit`, a three-page cap per gene lookup and the cached panel list. Errors are logged; search returns `[]`, details `None`.

## Licence and terms

PanelApp's *Terms of Use* (Genomics England, December 2019, section 1.1) apply to the website **and the API**: no use "for any commercial purposes (including commercial research)" and no diagnostic use or medical decision-making without a separate agreement with Genomics England. Third-party content (for example OMIM, Johns Hopkins University) must be acknowledged. Panels are research information, not clinical advice. Cite PanelApp (Martin et al., *Nat Genet* 2019, PMID 31676867) and the panel id and version. Check the current terms before any non-research use.

## Live verification (2026-10-08)

| Call | Result |
|---|---|
| `panels/?name=ataxia` | 200, 3.6 KB, 0.5 s, 5 panels |
| `panels/?page=1..5` | 200, 72 to 76 KB each, 0.5 s (page 6: 404) |
| `genes/?entity_name=BRCA1` | 200, 52 KB, 0.5 s, 28 records (22 green, 2 amber, 4 red) |
| `panels/158/genes/?confidence_level=3` | 200, 18.5 KB, 0.5 s, 12 genes |
| `panels/112/` | 200, 472 KB, 1.3 s |
| `knowledge-lookup check PANELAPP` | pass (search 8 s cold because of the panel list, details 0.9 s, relationships 0.9 s) |

## Caveats

- The panel list is a snapshot: new panels appear after the 10-minute cache expires.
- `genes/?entity_name=` is exact: use the approved symbol, not an alias.
- Red-rated genes are returned (flagged `red`); filter with `evidence_level="green"` for diagnostic-grade lists.

## See also

- [HGNC adapter](../proteins/hgnc_adapter.md), [GenCC adapter](gencc_adapter.md), [ClinGen adapter](clingen_adapter.md)
