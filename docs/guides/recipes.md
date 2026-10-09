---
description: Six tested end-to-end workflows for ME/CFS and Long COVID research - codes, related conditions, drugs, datasets, literature and immune cells - with the real output of each.
---

# Recipes

Each recipe is a complete script you can run, followed by what it printed on 2026-10-09 against the live APIs. They combine several sources the way a real question does. The scripts are in [`docs/examples/recipes/`](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/tree/main/docs/examples/recipes).

{% hint style="info" %}
Live data changes. Your output will differ in details (counts, newer papers), not in shape. Recipe 5 needs `UNPAYWALL_EMAIL` to be set; the others need no key.
{% endhint %}

| Recipe | Sources |
|---|---|
| [1. From a symptom or disease name to codes in every vocabulary](#1-from-a-symptom-or-disease-name-to-codes-in-every-vocabulary) | MeSH, MedGen, NCI EVS, Clinical Tables, Node Normalizer |
| [2. Related conditions and shared phenotypes](#2-related-conditions-and-shared-phenotypes) | Monarch |
| [3. A drug's codes, classes and reported adverse events](#3-a-drugs-codes-classes-and-reported-adverse-events) | RxNorm, RxClass, openFDA events |
| [4. Public omics datasets for a disease](#4-public-omics-datasets-for-a-disease) | OmicsDI, GEO, MetaboLights |
| [5. Papers, then a legal open-access copy](#5-papers-then-a-legal-open-access-copy) | OpenAlex, Unpaywall |
| [6. An immune cell type, its relations and where it is found](#6-an-immune-cell-type-its-relations-and-where-it-is-found) | Cell Ontology, CELLxGENE |


## 1. From a symptom or disease name to codes in every vocabulary

You have a phrase and need the identifiers registries and papers use. Search five sources at once, then follow one concept to its cross-references.

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

SOURCES = [
    KnowledgeSource.MESH,
    KnowledgeSource.MEDGEN,
    KnowledgeSource.NCIEVS,
    KnowledgeSource.CLINICALTABLES,
    KnowledgeSource.NODENORM,
]


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=SOURCES))
    try:
        # 1. Every source that knows the phrase, merged
        result = await lookup.search_concepts("chronic fatigue syndrome", max_results=10)
        for c in result.concepts:
            print(f"{c.primary_id:<18} {c.primary_label[:48]:<48} {c.sources}")

        if not result.concepts:
            print("no source knew this phrase:", result.errors)
            return

        # 2. Follow the top hit to its cross-references in other vocabularies
        top = result.concepts[0]
        maps = await lookup.find_mappings(top.primary_id)
        print(
            top.primary_id,
            "->",
            len(maps),
            "cross-references, e.g.",
            [m.identifier for m in maps[:6]],
        )
    finally:
        await lookup.close()


asyncio.run(main())
```

Output:

```text
MONDO:0005404      myalgic encephalomeyelitis/chronic fatigue syndr ['NODENORM', 'MEDGEN']
ICD10CM:G93.32     Myalgic encephalomyelitis/chronic fatigue syndro ['CLINICALTABLES']
CONDITIONS:12927   Chronic fatigue syndrome                         ['CLINICALTABLES', 'NCIEVS']
NCIT:C227796       Chronic Fatigue Syndrome Primary Factor Question ['NCIEVS']
UMLS:C3824694      Chronic fatigue syndrome in adolescence          ['NODENORM']
D015673            Fatigue Syndrome, Chronic                        ['MESH']
MONDO:0005404 -> 4 cross-references, e.g. ['C0015674', 'D015673', '51771007', '52702003']
```

**What to notice**

* Each concept lists the sources that returned it. The ICD-10-CM code, the NCI Thesaurus concept, the MeSH heading and the UMLS concept all describe ME/CFS in different systems, and none of them is the same identifier.
* `find_mappings` collects cross-references from the concept's own identifiers: here the UMLS CUI `C0015674`, the MeSH descriptor `D015673` and two numeric SNOMED CT concept ids.
* A source that does not understand an identifier logs a line and is skipped; it never raises.

## 2. Related conditions and shared phenotypes

Look up two conditions that are often considered in the differential diagnosis of ME/CFS and see what Monarch links them to.

```python
import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import MonarchAdapter


async def main() -> None:
    async with MonarchAdapter(LookupConfig()) as monarch:
        for term in ["postural orthostatic tachycardia syndrome", "fibromyalgia"]:
            hits = await monarch.search_concepts(term, limit=1)
            if not hits:
                print(term, "-> no hit")
                continue
            d = hits[0]
            edges = await monarch.get_relationships(d.primary_id)
            kinds = sorted({e["relation_label"] for e in edges})
            print(f"{term}: {d.primary_id} {d.primary_label}  ({len(edges)} edges: {kinds})")
            for e in edges[:3]:
                print("   ", e["relation_label"], e["related_id"], e["related_name"])


asyncio.run(main())
```

Output:

```text
postural orthostatic tachycardia syndrome: MONDO:0001315 orthostatic intolerance  (4 edges: ['caused_by', 'condition_associated_with_gene', 'has_phenotype'])
    has_phenotype HP:0012173 Orthostatic tachycardia
    has_phenotype HP:0003345 Elevated urinary norepinephrine level
    caused_by HGNC:11048 SLC6A2
fibromyalgia: MONDO:0005546 fibromyalgia  (0 edges: [])
```

**What to notice**

* Monarch resolves each name to a MONDO disease and returns typed edges: phenotypes (`has_phenotype`) and genes (`caused_by`).
* Coverage varies by disease. Fibromyalgia resolves to a MONDO term but has no edges in Monarch, which is why this page shows both: check `len(edges)` before you rely on a result.
* For disease-phenotype tables with frequencies use [HPO annotations](../adapters/phenotypes/hpoa_adapter.md) or [Orphanet](../adapters/phenotypes/orphanet_adapter.md); ME/CFS itself is not in `phenotype.hpoa`.

## 3. A drug's codes, classes and reported adverse events

Resolve a drug name to RxNorm, map it to ATC classes, then read how often each reaction appears in FDA adverse-event reports.

```python
import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import OpenFDAEventsAdapter, RxClassAdapter, RxNormAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with (
        RxNormAdapter(cfg) as rxnorm,
        RxClassAdapter(cfg) as rxclass,
        OpenFDAEventsAdapter(cfg) as faers,
    ):
        found = await rxnorm.search_concepts("naltrexone", limit=1)
        if not found:
            print("RxNorm does not know this drug")
            return
        drug = found[0]
        print("RxNorm  ", drug.primary_id, drug.primary_label)

        for m in (await rxclass.get_mappings(drug.primary_id))[:4]:
            print("RxClass ", m["toSource"], m["toId"])

        reports = await faers.search_concepts("naltrexone", limit=1)
        if not reports:
            print("no FAERS reports found")
            return
        hit = reports[0]
        print("FAERS   ", hit.primary_id)
        for e in (await faers.get_relationships(hit.primary_id))[:5]:
            print(
                f"    {e['related_name']:<26} {e['report_count']:>6} of {e['total_reports']} reports"
            )


asyncio.run(main())
```

Output:

```text
RxNorm   7243 naltrexone
RxClass  ATC N07BB
RxClass  ATC N07BB04
FAERS    FAERS:DRUG:NALTREXONE
    INJECTION SITE REACTION      4409 of 30616 reports
    INJECTION SITE PAIN          3159 of 30616 reports
    NAUSEA                       2142 of 30616 reports
    ALCOHOLISM                   1952 of 30616 reports
    INJECTION SITE MASS          1916 of 30616 reports
```

**What to notice**

* RxNorm gives the ingredient id `7243`; RxClass maps it to the ATC classes `N07BB` and `N07BB04`.
* FAERS counts are **spontaneous reports**, not incidence: each edge carries an `evidence` text that says so. Injection-site reactions lead, which likely reflects the injectable product rather than the typical oral use.
* openFDA allows about 1,000 keyless requests per day; set `OPENFDA_API_KEY` for more.

## 4. Public omics datasets for a disease

Find studies you could download and reanalyse. OmicsDI searches several repositories at once; GEO and MetaboLights are queried directly.

```python
import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import GEOAdapter, MetaboLightsAdapter, OmicsDIAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with (
        OmicsDIAdapter(cfg) as omicsdi,
        GEOAdapter(cfg) as geo,
        MetaboLightsAdapter(cfg) as mtbls,
    ):
        for name, adapter in [("OmicsDI", omicsdi), ("GEO", geo), ("MetaboLights", mtbls)]:
            hits = await adapter.search_concepts("chronic fatigue syndrome", limit=3)
            print(f"{name}: {len(hits)} hits")
            for c in hits:
                print(f"   {c.primary_id:<28} {c.primary_label[:70]}")


asyncio.run(main())
```

Output:

```text
OmicsDI: 3 hits
   metabolights_dataset:MTBLS161 Metabolic profiling reveals anomalous energy metabolism and oxidative 
   metabolomics_workbench:ST000450 Metabolic features of chronic fatigue syndrome
   massive:MSV000090685         Proteomic Analysis of Cerebrospinal Fluids from Chronic Fatigue Syndro
GEO: 3 hits
   GSE327255                    PTPRN2 hypomethylation and PHB2-modulated miR-153-3p maturation reveal
   GSE317067                    Extracellular vesicle protein and miRNA signatures as biomarkers for p
   GSE304805                    Precision Medicine Study of Post-Exertional Malaise epigenetic changes
MetaboLights: 1 hits
   MTBLS161                     Metabolic profiling reveals anomalous energy metabolism and oxidative
```

**What to notice**

* OmicsDI returned a MetaboLights study, a Metabolomics Workbench study and a MassIVE proteomics dataset in one call. The same MetaboLights study (`MTBLS161`) appears again when MetaboLights is queried directly.
* GEO returns series accessions (`GSE...`) with titles; the adapter gives metadata and links only, never the data files.
* Titles are cut to 70 characters in this output; `concept.definitions` holds the longer description.

## 5. Papers, then a legal open-access copy

Search the literature, pick a DOI from the result and ask Unpaywall where a free copy lives.

```python
import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import OpenAlexAdapter, UnpaywallAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with OpenAlexAdapter(cfg) as openalex, UnpaywallAdapter(cfg) as unpaywall:
        papers = await openalex.search_concepts("long covid post-exertional malaise", limit=4)
        papers = [p for p in papers if p.concept_type == "CITATION"]
        for p in papers:
            print(p.primary_id, p.primary_label[:80])

        doi = next(
            (
                i.identifier.removeprefix("DOI:")
                for p in papers
                for i in p.identifiers or []
                if i.identifier.startswith("DOI:")
            ),
            None,
        )
        print("DOI:", doi)
        if doi:
            oa = await unpaywall.get_concept_details(doi)
            print("open access:", oa.primary_label[:60] if oa else None)
            for e in (await unpaywall.get_relationships(doi))[:3]:
                print("   ", e["relation_label"], e["related_id"])


asyncio.run(main())
```

Output:

```text
W4403904216 Two-day cardiopulmonary exercise testing in long COVID post-exertional malaise d
W4390582057 Muscle abnormalities worsen after post-exertional malaise in long COVID
W4313501493 ME/CFS and Post-Exertional Malaise among Patients with Long COVID
DOI: 10.1016/j.resp.2024.104362
open access: Two-day cardiopulmonary exercise testing in long COVID post-
    available_at https://doi.org/10.1016/j.resp.2024.104362
    available_at https://escholarship.org/uc/item/8mw162z5
    published_in ISSN:1569-9048
```

**What to notice**

* OpenAlex also returns *topics* (ids like `T11368`); the script keeps only works by checking `concept_type == "CITATION"`.
* The DOI is stored in the concept's identifiers as `DOI:10.1016/...`.
* Unpaywall resolves DOIs only (its title search was retired) and needs `UNPAYWALL_EMAIL`. The `available_at` edges point to the publisher and to repository copies.

## 6. An immune cell type, its relations and where it is found

Start from a cell name, read its ontology relations, then ask CELLxGENE which tissues have single-cell data for it.

```python
import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import CellOntologyAdapter, CellxGeneAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with CellOntologyAdapter(cfg) as cl, CellxGeneAdapter(cfg) as cxg:
        found = await cl.search_concepts("natural killer cell", limit=1)
        if not found:
            print("Cell Ontology returned nothing")
            return
        nk = found[0]
        print(nk.primary_id, nk.primary_label)
        for e in (await cl.get_relationships(nk.primary_id))[:5]:
            print("  ", e["relation_label"], e["related_id"], e["related_name"])
        for e in (await cxg.get_relationships(nk.primary_id))[:3]:
            print("CELLxGENE", e["relation_label"], e["related_id"], e["related_name"])


asyncio.run(main())
```

Output:

```text
CL:0000623 natural killer cell
   is_a CL:0001067 group 1 innate lymphoid cell
   develops_from CL:0000825 pro-NK cell
   capable_of GO:0002228 natural killer cell mediated immunity
   capable_of GO:0050776 regulation of immune response
   lacks_plasma_membrane_part PR:000001289 membrane-spanning 4-domains subfamily A member 1
CELLxGENE found_in_tissue UBERON:0000178 blood
CELLxGENE found_in_tissue UBERON:0002113 kidney
CELLxGENE found_in_tissue UBERON:0002048 lung
```

**What to notice**

* Cell Ontology returns typed relations: `is_a`, `develops_from`, `capable_of` and negative statements such as `lacks_plasma_membrane_part`.
* The CELLxGENE edges link the same `CL:` identifier to tissues, which lets you jump from an ontology term to datasets.
* To go from a cell type to marker genes, add [CellMarker](../adapters/ontologies/cellmarker_adapter.md) (you provide the file).

## Adapting a recipe

* Swap the query string; every adapter in a recipe accepts free text, and the [coverage tables](data-coverage.md) show what each source returns.
* Pick other sources with [Which source for which question](choosing-sources.md).
* Use `CentralKnowledgeLookup` when you want one merged answer, and an adapter directly when you need its extra methods or fields (`report_count`, `evidence`).
* Wrap calls in `try/finally` and close the lookup, as the scripts do. See [Troubleshooting](../getting-started/troubleshooting.md) if a source is slow or unavailable.
