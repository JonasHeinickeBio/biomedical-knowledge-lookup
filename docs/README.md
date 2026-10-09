---
description: One async Python API, CLI and MCP server for searching, resolving and cross-walking concepts across 106 biomedical ontologies, terminologies and databases.
---

# Biomedical Knowledge Lookup

**Ask 106 biomedical sources one question and get one answer format back.** `biomedical-knowledge-lookup` (imported as `knowledge_lookup`) searches ontologies, clinical code systems, gene, protein and drug databases, literature indexes and dataset repositories through a single asynchronous interface. Every source returns the same `UnifiedConcept`, so you can merge hits, follow cross-references and export results without writing per-source code.

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig


async def main() -> None:
    lookup = CentralKnowledgeLookup(
        LookupConfig(
            enabled_sources=[
                KnowledgeSource.MESH,
                KnowledgeSource.MEDGEN,
                KnowledgeSource.NCIEVS,
                KnowledgeSource.CLINICALTABLES,
            ]
        )
    )
    try:
        result = await lookup.search_concepts("chronic fatigue syndrome", max_results=6)
        for concept in result.concepts:
            print(concept.primary_id, concept.primary_label, concept.sources)
    finally:
        await lookup.close()


asyncio.run(main())
```

```
C0015674 Myalgic encephalomeyelitis/chronic fatigue syndrome ['MEDGEN']
ICD10CM:G93.32 Myalgic encephalomyelitis/chronic fatigue syndrome ['CLINICALTABLES']
CONDITIONS:12927 Chronic fatigue syndrome ['CLINICALTABLES', 'NCIEVS']
NCIT:C227796 Chronic Fatigue Syndrome Primary Factor Question ['NCIEVS']
D015673 Fatigue Syndrome, Chronic ['MESH']
```

One phrase, four sources: a UMLS CUI, an ICD-10-CM code, an NCI Thesaurus concept and a MeSH heading. Concepts found by more than one source are merged and list every source that returned them.

{% hint style="success" %}
**Install:** `pip install biomedical-knowledge-lookup`. The core needs no API key; 70+ of the sources work out of the box. See [Installation](getting-started/installation.md).
{% endhint %}

## Where to start

| I want to ... | Go to |
|---|---|
| run my first search in five minutes | [Quickstart](getting-started/quickstart.md) |
| know **which source** answers my question | [Which source for which question](guides/choosing-sources.md) |
| see **what data** each API actually returns | [What each source returns](guides/data-coverage.md) |
| use it from the terminal | [Command-line interface](guides/cli.md) |
| give Claude, Cursor or another agent these tools | [MCP server](guides/mcp-server.md) |
| set API keys, timeouts and rate limits | [Configuration](getting-started/configuration.md) |
| fix an unavailable source or a slow call | [Troubleshooting and FAQ](getting-started/troubleshooting.md) |
| look up one adapter's identifiers and quirks | [All adapters](adapters/README.md) |
| copy a complete workflow (codes, drugs, datasets, literature) | [Recipes](guides/recipes.md) |
| find a setting or variable | [Environment variables](reference/environment-variables.md) |
| add a new source | [Writing an adapter](contributing/writing-an-adapter.md) |
| understand an abbreviation (CUI, CURIE, ATC ...) | [Glossary](reference/glossary.md) |

## What you can do

| Task | Guide |
|---|---|
| Search many sources in parallel and get merged, de-duplicated, ranked results | [Searching concepts](guides/searching-concepts.md) |
| Resolve an identifier such as `HP:0001250` and map it to other vocabularies | [Searching concepts](guides/searching-concepts.md) |
| Widen a search with synonyms and abbreviation/long-form variants, with a record of every term tried | [Term expansion](guides/term-expansion.md) |
| Compare what several sources return for the same text and score their agreement | [Multi-source annotation](guides/multi-source-annotation.md) |
| Parse, validate and normalise CURIEs with Bioregistry | [CURIE management](guides/curie-management.md) |
| Export to JSON, CSV, Turtle, pandas, Excel, a text report or an RDF graph | [Exporting results](guides/exporting-results.md) |
| Run a LangGraph search, review and approval workflow | [Agent workflow](guides/agent-workflow.md) |

## The 106 sources

The sources are grouped by what you use them for. Each domain has its own section in the sidebar.

<!-- sources:start -->
| Domain | Sources | Examples |
|---|---|---|
| **Ontology services and mappings**<br>Search hundreds of ontologies at once and translate identifiers between them. | 11 | OLS, EBI OLS, BioPortal, BioOntology, OBO Foundry and 6 more |
| **Clinical terminologies and coding**<br>The code systems used in registries and health records. | 9 | MeSH, SNOMED CT, WHO ICD-11, ICD-10-GM, LOINC and 4 more |
| **Diseases and phenotypes**<br>Disease ontologies, phenotype annotations and gene-disease evidence. | 15 | Mondo, Disease Ontology, HPO, HPO annotations, Orphanet and 10 more |
| **Genes, variants and expression**<br>Gene records, variants, population frequencies and tissue expression. | 15 | HGNC, NCBI Gene, MyGene.info, Ensembl, ClinVar and 10 more |
| **Proteins, structures and interactions**<br>Protein records, predicted and solved structures, families and interaction networks. | 7 | UniProt, AlphaFold DB, PDB, InterPro, Pfam and 2 more |
| **Drugs and pharmacology**<br>Drug names and classes, targets, labels, adverse events and toxicogenomics. | 11 | DrugBank, RxNorm, RxClass, ChEMBL, DGIdb and 6 more |
| **Chemicals and metabolites**<br>Small molecules, lipids, reactions and metabolomics studies. | 7 | PubChem, ChEBI, UniChem, LIPID MAPS, Rhea and 2 more |
| **Pathways and enrichment**<br>Curated pathways and gene-set enrichment. | 4 | Reactome, KEGG, WikiPathways, Enrichr |
| **Immunology and cell types**<br>Cell types, marker genes, single-cell datasets and epitopes. | 4 | Cell Ontology, CellMarker, CZ CELLxGENE, IEDB |
| **Literature and citations**<br>Papers, preprints, citation links, text-mined entities and open-access status. | 13 | Europe PMC, NCBI E-utilities, PubTator 3, LitCovid, OpenAlex and 8 more |
| **Trials, grants and datasets**<br>Clinical-trial registries, funded projects and public omics datasets. | 8 | ClinicalTrials.gov, ISRCTN registry, NIH RePORTER, GEO, OmicsDI and 3 more |
| **General knowledge**<br>Broad knowledge graphs for names and facts that specialist sources lack. | 2 | Wikidata, DBpedia |
<!-- sources:end -->

## Design at a glance

* **One data model.** Pydantic models generated from a LinkML schema: `UnifiedConcept`, `LookupResult`, `LookupConfig`, `KnowledgeSource`, `ConceptType`. Every adapter has `search_concepts`, `get_concept_details`, and where the source supports it `get_relationships` and `get_mappings`.
* **Async first.** All lookups are coroutines; sources are queried concurrently with a per-source timeout.
* **Partial failure is expected.** A source that errors or times out is reported in `result.errors`; results from the other sources are still returned.
* **Nothing surprising.** Datasets are downloaded only when you opt in, e-mail addresses are sent only when you set them, and `import knowledge_lookup` never touches the network.
* **Light core.** Heavy clients (ChEMBL, UMLS, bioservices, LangGraph, MCP, pandas) are optional extras. A source whose extra or key is missing is skipped, not fatal.

{% hint style="info" %}
Every source keeps its own licence and terms of use. Some are non-commercial (CTD, PanelApp) or send your input to a third party (Enrichr). The notes are collected in [Which source for which question](guides/choosing-sources.md#terms-of-use-worth-knowing).
{% endhint %}

## Project links

* Source code: [github.com/JonasHeinickeBio/biomedical-knowledge-lookup](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup)
* Package: [pypi.org/project/biomedical-knowledge-lookup](https://pypi.org/project/biomedical-knowledge-lookup/)
* Changelog: [CHANGELOG.md](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/CHANGELOG.md)
* Issues: [GitHub issues](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/issues)
* Contributing: [Contributing](contributing/README.md)
* License: MIT
