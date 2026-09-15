---
description: A runnable example for each of the 36 knowledge sources, plus Jupyter notebooks and end-to-end use cases.
---

# Examples

- **Per-source examples:** one short script for each of the 36 knowledge sources. It
  searches the source and, where the adapter supports it, looks up a concept by
  identifier. Each script has its recorded output next to it.
- **[Notebooks](notebooks/README.md):** getting started, API keys, rate limits and error
  handling, step by step.
- **[Use cases](use-cases.md):** complete tasks that combine several sources.
- **[Availability status](availability-status.md):** which examples returned data in the
  last recorded run.

## Run an example

Run the scripts from the repository root.

{% tabs %}
{% tab title="pip" %}
```bash
pip install "biomedical-knowledge-lookup[all]"
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
python docs/examples/phenotypes/hpo/hpo_example.py
```
{% endtab %}

{% tab title="Development install" %}
```bash
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
pip install -e ".[all]"
python docs/examples/phenotypes/hpo/hpo_example.py
```
{% endtab %}
{% endtabs %}

Every example prints three parts:

1. whether the adapter is available;
2. the top five search results, with ID, type, confidence, and definitions or mappings
   when the source provides them;
3. the details of one concept, for sources whose adapter can look one up by identifier.

It ends with a `Summary:` line. The recorded output is in `<source>_example_output.txt`
next to each script.

{% hint style="info" %}
An example whose source needs an API key or an optional extra prints `SKIPPED` and
explains what is missing instead of failing. See [API keys and extras](#api-keys-and-extras).
{% endhint %}

## The pattern every example follows

```python
import asyncio

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup


async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.HPO])
    try:
        if KnowledgeSource.HPO not in lookup.adapters:  # key or extra missing
            print("HPO is not available")
            return

        result = await lookup.search_concepts("seizure", max_results=5)
        for concept in result.concepts:
            print(concept.primary_id, concept.primary_label)
        print("Errors:", result.errors)

        details = await lookup.get_concept_details("HP:0001250", source=KnowledgeSource.HPO)
        print(details.primary_label if details else "not found")
    finally:
        await lookup.close()


asyncio.run(main())
```

Identifier formats differ between sources: HPO and Mondo take CURIEs (`HP:0001250`), OLS
takes the full term IRI, UniProt a bare accession. The tables below list an identifier
that works for each source.

## Per-source examples

In the tables, "Query / identifier" is the search term and the `get_concept_details`
identifier used by the example. A dash in "Needs" means the source is a public API.

### Core sources

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [ChEMBL](core/chembl/chembl_example.py) | Bioactive molecules, drugs and targets | `aspirin` / `CHEMBL25` | `[chembl]` extra |
| [DisGeNET](core/disgenet/disgenet_example.py) | Gene-disease associations | `asthma` | `DISGENET_API_KEY` |
| [Mondo](core/mondo/mondo_example.py) | Mondo Disease Ontology | `diabetes` / `MONDO:0005148` | - |
| [OLS](core/ols/ols_example.py) | EBI Ontology Lookup Service: 250+ ontologies (DOID, EFO, NCIT, UBERON, CHEBI, ...) | `cancer` / `http://purl.obolibrary.org/obo/DOID_162` | - |
| [Open Targets](core/opentargets/opentargets_example.py) | Open Targets Platform targets, diseases and drugs | `BRCA1` / `ENSG00000012048` | - |
| [UMLS](core/umls/umls_example.py) | UMLS Metathesaurus: filtered search, bulk search, mappings, relationships and streaming iterators (hand-written example) | `diabetes` / `C0011849` | `[umls]` extra and `UMLS_API_KEY` |

### Chemicals and drugs

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [DrugBank](chemicals/drugbank/drugbank_example.py) | DrugBank drugs, looked up through OLS | `aspirin` | - |
| [PubChem](chemicals/pubchem/pubchem_example.py) | PubChem compounds (CIDs) | `aspirin` / `2244` | - |
| [UniChem](chemicals/unichem/unichem_example.py) | Chemical cross-references; search by InChIKey, details by UniChem compound ID | `BSYNRYMUTXBXSQ-UHFFFAOYSA-N` / `161671` | `[bioservices]` extra |

### Phenotypes, variants and gene function

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [ClinVar](phenotypes/clinvar/clinvar_example.py) | Variants and their clinical significance | `BRCA1` / `17661` | - |
| [Gene Ontology](phenotypes/geneontology/geneontology_example.py) | Gene Ontology terms | `apoptosis` / `GO:0006915` | - |
| [HPO](phenotypes/hpo/hpo_example.py) | Human Phenotype Ontology | `seizure` / `HP:0001250` | - |
| [OMIM](phenotypes/omim/omim_example.py) | Mendelian disorders and genes | `cystic fibrosis` / `219700` | `OMIM_API_KEY` |
| [QuickGO](phenotypes/quickgo/quickgo_example.py) | EBI QuickGO Gene Ontology terms and annotations | `apoptosis` / `GO:0006915` | `[bioservices]` extra |

### Genes and proteins

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [Ensembl](proteins/ensembl/ensembl_example.py) | Human genes, searched by gene symbol | `TP53` / `ENSG00000141510` | - |
| [HGNC](proteins/hgnc/hgnc_example.py) | Human gene nomenclature | `BRCA1` / `HGNC:1100` | - |
| [UniProt](proteins/uniprot/uniprot_example.py) | UniProtKB proteins | `insulin` / `P01308` | - |

### Pathways

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [KEGG](pathways/kegg/kegg_example.py) | KEGG diseases and drugs | `diabetes` / `H00409` | - |
| [Reactome](pathways/reactome/reactome_example.py) | Reactome pathways and reactions | `apoptosis` / `R-HSA-109581` | - |

### Ontology services

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [BioOntology](ontologies/bioontology/bioontology_example.py) | NCBO BioOntology search API | `melanoma` | `BIOPORTAL_API_KEY` |
| [BioPortal](ontologies/bioportal/bioportal_example.py) | NCBO BioPortal: 1000+ ontologies (SNOMED CT, MeSH, ICD, ...) | `melanoma` | `BIOPORTAL_API_KEY` |
| [EBI OLS](ontologies/ebiols/ebiols_example.py) | EMBL-EBI OLS (a variant of the OLS adapter) | `cancer` / `http://purl.obolibrary.org/obo/MONDO_0004992` | - |
| [OBO Foundry](ontologies/obofoundry/obofoundry_example.py) | OBO Foundry ontologies | `cancer` | - |
| [ZOOMA](ontologies/zooma/zooma_example.py) | EBI ZOOMA text-to-ontology annotation | `breast cancer` | - |

### Protein families, structures and interactions

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [InterPro](families/interpro/interpro_example.py) | Protein families and domains | `kinase` / `IPR000719` | - |
| [PDB](families/pdb/pdb_example.py) | RCSB Protein Data Bank structures | `hemoglobin` / `4HHB` | - |
| [Pfam](families/pfam/pfam_example.py) | Pfam protein families | `kinase` / `PF00069` | - |
| [STRING](families/string/string_example.py) | STRING protein-protein interaction network proteins | `TP53` | - |

### Literature

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [Europe PMC](literature/europepmc/europepmc_example.py) | Literature search; details by bare PubMed ID | `CRISPR` / `33203879` | - |
| [NCBI E-utilities](literature/eutils/eutils_example.py) | PubMed and Gene | `BRCA1` / `GeneID:672` | `[bioservices]` extra |

### Other sources

| Source | What it shows | Query / identifier | Needs |
| --- | --- | --- | --- |
| [BioLinker](other/biolinker/biolinker_example.py) | BioLinker entity linking | `cancer` | - |
| [COSMIC](other/cosmic/cosmic_example.py) | COSMIC somatic cancer mutations | `BRAF` | - (`COSMIC_API_KEY` optional) |
| [DBpedia](other/dbpedia/dbpedia_example.py) | DBpedia resources (general knowledge) | `aspirin` / `Aspirin` | - |
| [OxO](other/oxo/oxo_example.py) | EBI OxO cross-reference mappings; search with a CURIE | `MONDO:0005148` / `MONDO:0005148` | - |
| [Tyto](other/tyto/tyto_example.py) | Ontology term lookup by IRI | `promoter` / `http://purl.obolibrary.org/obo/SO_0000167` | `[tyto]` extra |
| [Wikidata](other/wikidata/wikidata_example.py) | Wikidata items | `aspirin` / `Q18216` | - |

{% hint style="warning" %}
Some adapters currently return no results, for example DrugBank, STRING, COSMIC and
Tyto, and Reactome, QuickGO and E-utilities return details but no search results. The
[availability status](availability-status.md) page lists what the last run returned and
the known cause for each source.
{% endhint %}

## API keys and extras

Keys are read from environment variables. A `.env` file in the working directory or one
of its parents also works. You can pass keys in code instead:
`create_knowledge_lookup(api_keys={"umls": "..."})`.

| Variable | Sources |
| --- | --- |
| `UMLS_API_KEY` | UMLS |
| `BIOPORTAL_API_KEY` | BioPortal, BioOntology |
| `DISGENET_API_KEY` | DisGeNET |
| `OMIM_API_KEY` | OMIM |
| `COSMIC_API_KEY` | COSMIC (optional) |

Some sources need an optional dependency group:

| Extra | Sources |
| --- | --- |
| `[chembl]` | ChEMBL |
| `[umls]` | UMLS |
| `[bioservices]` | UniChem, QuickGO, NCBI E-utilities |
| `[tyto]` | Tyto |
| `[all]` | every optional dependency |

```bash
pip install "biomedical-knowledge-lookup[chembl,umls,bioservices,tyto]"
export UMLS_API_KEY="your-umls-key"
python docs/examples/core/umls/umls_example.py
```

{% hint style="warning" %}
Adapters log failed requests, often with their URL. BioPortal and BioOntology send their
key in a request header, and the BioPortal, BioOntology and OMIM adapters redact keys from
logged errors. Other code that logs request URLs can still expose a key passed as a URL
parameter (OMIM, UMLS), so check logs before you share them. The recorded example outputs
in this folder are redacted.
{% endhint %}

## Regenerate the examples

The per-source scripts are generated; only the UMLS example is hand-written.

```bash
# Rewrite the scripts from the SOURCES table in generate_all_examples.py
python docs/examples/scripts/generate_all_examples.py

# Run every example, refresh the *_example_output.txt files,
# scripts/all_adapters_test_results.json and availability-status.md
python docs/examples/scripts/generate_status.py

# Re-run a few sources only
python docs/examples/scripts/generate_status.py OLS HPO --timeout 180
```

To change a query or an identifier, edit the source's entry in
[`scripts/generate_all_examples.py`](scripts/generate_all_examples.py) and run both
commands. `generate_status.py` strips secrets from the outputs it records.

## Layout

```
docs/examples/
├── README.md                  # this page
├── use-cases.md               # end-to-end tasks
├── availability-status.md     # generated: last run of every example
├── notebooks/                 # Jupyter notebooks 01-04
├── scripts/
│   ├── generate_all_examples.py
│   ├── generate_status.py
│   └── all_adapters_test_results.json
└── <category>/<source>/
    ├── <source>_example.py
    └── <source>_example_output.txt
```
