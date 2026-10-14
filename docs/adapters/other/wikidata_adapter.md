---
description: Wikidata items via the Wikidata Query Service - labels, descriptions and the main biomedical cross-reference identifiers.
---

# Wikidata adapter

Searches Wikidata items by label and fetches item details, including some 35 external identifiers (UMLS, MeSH, NCI Thesaurus, SNOMED CT, ICD-11, OMIM, Disease Ontology, HPO, Entrez Gene, UniProt, PubChem, ChEMBL, ...), through the Wikidata Query Service. Useful as a bridge between biomedical IDs and general knowledge.

| | |
|---|---|
| Source | `KnowledgeSource.WIKIDATA` |
| Class | `knowledge_lookup.adapters.WikidataAdapter` |
| Requires | none |
| Identifiers | `Q18216` |
| Upstream API | `https://query.wikidata.org/sparql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import WikidataAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with WikidataAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("metformin", limit=3):
            print(concept.primary_id, concept.primary_label, concept.definitions)

        crohn = await adapter.get_concept_details("Q1472")
        print(crohn.primary_label, crohn.concept_type)
        print(sorted((i.source, i.identifier) for i in crohn.identifiers))
        print(sorted(crohn.categories))


asyncio.run(main())
```

Output:

```
Q19484 metformin ['chemical compound']
Q22250907 Q22250907 []
Q27089363 metformin hydrochloride ['chemical compound']
Crohn's disease DISEASE
[('DOID', 'DOID:8778'), ('HPO', 'HP:0100280'), ('ICD11', 'DD70'), ('KEGG', 'H00286'), ('MEDLINEPLUS', '000249'), ('MESH', 'D003424'), ('NCIEVS', 'C35211'), ('NCIEVS', 'C37262'), ('OMIM', '266600'), ('OPENALEX', 'C2779280984'), ('OPENALEX', 'C2992200296'), ('SNOMEDCT', '34000006'), ('UMLS', 'C0156147'), ('WIKIDATA', 'Q1472')]
['DDC: 616.344', 'DiseasesDB: 3178', 'GARD: 10232', 'ICD-10-CM: K50.1', 'ICD-11 Foundation: 1267652425', 'ICD-9-CM: 555.1', 'MeSH tree: C06.405.205.731.500', 'MeSH tree: C06.405.469.432.500', 'MeSH: D003424', 'designated intractable/rare disease', 'eMedicine: 172940', 'eMedicine: 367666', 'eMedicine: 928288', 'rare disease', 'type of disease']
```

## Searching

`search_concepts(query, limit)` runs a SPARQL query that calls the MediaWiki `EntitySearch` API (English) through `wikibase:mwapi`. A subquery takes the first `limit` items by search rank (`wikibase:apiOrdinal`), and the outer query joins their optional "instance of" (P31) labels.

The best match therefore comes first, and each item is returned once: the rows of an item with several P31 values are merged, so `categories` lists all of its instance-of labels. Items without an English label get their Q-ID as label, like `Q22250907` in the output. The query text is passed as an escaped SPARQL string literal, so quotes and backslashes in the query are safe.

| Field | Value |
|---|---|
| `primary_id` | Q-ID |
| `primary_label` | English label |
| `definitions` | item description |
| `categories` | all instance-of labels, each once |
| `concept_type` | from the first instance-of label that maps to a type: disease/disorder/syndrome → `DISEASE`, symptom/clinical sign → `SYMPTOM`, drug/pharmaceutical/medication → `DRUG`, gene → `GENE`, protein → `PROTEIN`, chemical/compound/isomer/carbohydrate → `CHEMICAL`, taxon/species/organism → `ORGANISM`, else `UNKNOWN` (search only; details also use the fallback below) |
| `identifiers` | one `WIKIDATA` identifier; the URL is the entity IRI |
| `confidence_score` | `0.7` |

## Concept details

`get_concept_details(qid)` only accepts IDs of the form `Q` followed by digits; anything else returns `None` without a request. It returns label, description, all instance-of labels as `categories`, `confidence_score` `0.8` (all SPARQL rows in `source_data[WIKIDATA]`) and the item's external identifiers.

Identifiers whose vocabulary has a `KnowledgeSource` become `identifiers` of that source. A value that Wikidata stores as a bare number gets its CURIE prefix (`CHEBI:15365`, `HGNC:1100`, `MONDO:...`, `ORPHA:...`). Identifiers without a `KnowledgeSource` are kept as `"<label>: <value>"` categories.

| Wikidata property | Exposed as |
|---|---|
| P2892 UMLS CUI | `UMLS` |
| P486 MeSH descriptor ID | `MESH` (also the `MeSH: <id>` category, as before) |
| P1748 NCI Thesaurus ID | `NCIEVS` |
| P5806 SNOMED CT ID | `SNOMEDCT` |
| P7329 ICD-11 ID (MMS) | `ICD11` |
| P492 OMIM ID | `OMIM` |
| P699 Disease Ontology ID | `DOID` |
| P3841 Human Phenotype Ontology ID | `HPO` |
| P5270 Mondo ID, P1550 Orphanet ID | `MONDO`, `ORPHANET` |
| P604 MedlinePlus ID, P665 KEGG ID, P10283 OpenAlex ID | `MEDLINEPLUS`, `KEGG`, `OPENALEX` |
| P351 Entrez Gene, P354 HGNC ID, P594 Ensembl gene, P352 UniProt | `NCBIGENE`, `HGNC`, `ENSEMBL`, `UNIPROT` |
| P686 Gene Ontology, P3937 Reactome, P2410 WikiPathways | `GO`, `REACTOME`, `WIKIPATHWAYS` |
| P662 PubChem CID, P592 ChEMBL, P715 DrugBank, P683 ChEBI, P3345 RxNorm | `PUBCHEM`, `CHEMBL`, `DRUGBANK`, `CHEBI`, `RXNORM` |
| P685 NCBI taxonomy ID | `NCBITAXONOMY` (also the `NCBI Taxon: <id>` category, as before) |
| P494 ICD-10, P4229 ICD-10-CM, P493 ICD-9, P1692 ICD-9-CM, P7807 ICD-11 Foundation | categories `ICD-10: ...`, `ICD-10-CM: ...`, `ICD-9: ...`, `ICD-9-CM: ...`, `ICD-11 Foundation: ...` |
| P672 MeSH tree, P4317 GARD, P557 DiseasesDB, P673 eMedicine, P1036 DDC | categories `MeSH tree: ...`, `GARD: ...`, `DiseasesDB: ...`, `eMedicine: ...`, `DDC: ...` |
| P353 HGNC symbol, P267 ATC, P231 CAS, P235 InChIKey | categories `HGNC symbol: ...`, `ATC: ...`, `CAS: ...`, `InChIKey: ...` |

Identifiers with a landing page carry a URL (MeSH, OMIM, Disease Ontology and HPO as OBO IRIs, Entrez Gene, UniProt, PubChem, DrugBank). The Wikidata `P`-numbers were checked against the live API; other Wikidata properties (news sites, encyclopedias, authority files) are ignored.

The query returns one row per instance-of value and per identifier value (a `UNION`, not a chain of `OPTIONAL`s, so rows do not multiply); the concept type is taken from the first instance-of label that maps to a type, wherever it appears. When no label maps (ibuprofen is a "group of stereoisomers"), `get_concept_details` falls back to the linked vocabularies: NCBI Taxonomy → `ORGANISM`, UniProt → `PROTEIN`, Entrez Gene/Ensembl/HGNC → `GENE`, DrugBank/RxNorm → `DRUG`, ChEBI/PubChem/ChEMBL → `CHEMICAL`, Disease Ontology/Mondo/Orphanet → `DISEASE`, HPO → `PHENOTYPE`. OMIM is deliberately not used, as it covers genes too. Identifiers and categories are de-duplicated across rows.

Wikidata keeps genes and their proteins as separate items: searching `TP53` ranks the protein item (`Q283350`, with HGNC and UniProt) next to the gene item, so look at more than the first hit when you need Entrez Gene or Ensembl IDs.

## Mappings, relationships and lookups

Besides search and details, the adapter exposes these methods. All of them validate their input (a Q-ID must be `Q` plus digits, a language a code such as `en`) before sending a query, and the interface methods degrade to `[]`/`None` instead of raising.

| Method | Returns |
|---|---|
| `get_mappings(qid)` | the item's external identifiers as `{fromId, toId, fromSource, toSource, mappingType, confidence}` dicts, the shape the Ensembl and KEGG adapters use. `toSource` is the `KnowledgeSource` value (`MESH`, `OMIM`, ...) or, for vocabularies without one, the label (`ICD-10-CM`, `GARD`, ...). |
| `get_relationships(qid, limit=10, include_narrower=True)` | typed edges `{relation_label, related_id, related_name, source, property}` to other items. `limit` caps the edges **per relation label**, so a drug's 87 interactions cannot crowd out its other edges. |
| `find_by_identifier(source, identifier, limit=5)` | reverse lookup: the items that carry an identifier, with `confidence_score` `0.95`. `source` is a `KnowledgeSource`, a label such as `"ICD-10-CM"`, or a property such as `"P486"`. A CURIE prefix is stripped where Wikidata stores the bare number (`CHEBI:15365` is matched as `15365`). |
| `get_synonyms(qid, languages=("en",))` | the item's aliases (`skos:altLabel`) in the given languages, de-duplicated. |
| `get_wikipedia_article(qid, language="en")` | `{title, url}`, plus `dbpedia_resource` for English: the bridge to the [DBpedia adapter](dbpedia_adapter.md), whose resource names are English Wikipedia titles. |

`get_relationships` follows these item-valued properties:

| Edge label | Wikidata properties |
|---|---|
| `is_a` | P279 subclass of, P171 parent taxon |
| `has_subclass` | direct subclasses (P279 in reverse; `include_narrower`) |
| `instance_of`, `part_of`, `has_part` | P31, P361, P527 |
| `has_symptom`, `treated_by`, `risk_factor`, `has_cause` | P780, P2176, P5642, P828 |
| `has_gene` | P2293 genetic association |
| `treats`, `may_prevent`, `active_ingredient_in` | P2175, P4954, P3780 |
| `interacts_with` | P769 significant drug interaction, P129 physically interacts with |
| `encodes`, `encoded_by` | P688, P702 |

`is_a` and `has_subclass` are taxonomic labels in term expansion; the rest are associative.

Live output for `Q1472` (Crohn's disease):

```
find_by_identifier("MESH", "D003424")      [('Q1472', "Crohn's disease")]
find_by_identifier("ICD-10-CM", "K50.1")   [('Q1472', "Crohn's disease"), ('Q18553712', "Crohn's colitis")]
find_by_identifier("CHEBI", "CHEBI:15365") [('Q18216', 'aspirin')]
get_mappings                               24 entries: ('DOID', 'DOID:8778'), ('HPO', 'HP:0100280'), ('ICD-10-CM', 'K50.1'), ...
get_relationships(limit=3)                 is_a inflammatory bowel diseases; has_symptom fatigue / diarrhea / abdominal pain;
                                           treated_by antibiotic / cholecalciferol / steroid; has_gene ATG16L1 / IL6 / SMAD3;
                                           risk_factor appendicitis / tonsillectomy; has_subclass ileitis / ileocolitis
get_synonyms                               ['Crohn', 'Crohn disease', 'regional enteritis', 'regional ileocolitis', ...]
get_wikipedia_article                      {'title': "Crohn's disease", 'url': 'https://en.wikipedia.org/wiki/Crohn%27s_disease',
                                            'dbpedia_resource': "http://dbpedia.org/resource/Crohn's_disease"}
```

```python
async with WikidataAdapter(LookupConfig()) as adapter:
    # MeSH descriptor -> Wikidata item -> identifiers in every other vocabulary
    (item,) = await adapter.find_by_identifier("MESH", "D003424")
    mappings = await adapter.get_mappings(item.primary_id)
    edges = await adapter.get_relationships(item.primary_id, limit=3)
    article = await adapter.get_wikipedia_article(item.primary_id)
```

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)), with a policy that follows the documented limits of the public Query Service ([user manual](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual)):

| Documented rule | What the adapter does |
|---|---|
| queries are cut off after 60 s | `min_request_timeout = 65`, so a query that finishes late is not aborted client-side and re-run |
| 5 parallel queries per IP | `max_concurrent_requests = 3` |
| 60 s of processing time per minute, 30 failed queries per minute | a timed-out query (HTTP 500) or network error is retried once after 2 s, not twice at once |
| HTTP 429 with `Retry-After`; clients that ignore it are banned | the pause is at least the `Retry-After` value (capped at 120 s) |
| a client must send a good `User-Agent` with contact information, or may be blocked | `AID-PAIS-Knowledge-Lookup/<version> (+<project URL>)` |

Other errors are logged; search returns `[]` and details return `None`. Through `CentralKnowledgeLookup` the per-source `timeout_per_source` still applies as an outer limit, so raise it (or call the adapter directly) for queries that need the full 60 s.

## See also

- [DBpedia adapter](dbpedia_adapter.md), [UMLS adapter](../core/umls_adapter.md)
- [All adapters](../README.md)
