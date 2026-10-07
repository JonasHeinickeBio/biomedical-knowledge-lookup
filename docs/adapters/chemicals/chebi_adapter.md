---
description: ChEBI chemical entities with definitions, formula/mass/structure, ontology relations (including roles) and database cross-references.
---

# ChEBI adapter

Searches and fetches Chemical Entities of Biological Interest (ChEBI) through the EBI ChEBI public REST API (the replacement for the retired SOAP and `ws` services). Besides identity and structure, ChEBI's *roles* (`non-steroidal anti-inflammatory drug`, `antipyretic`, `antioxidant`, `human metabolite`, ...) are useful for classifying substances in drug, supplement and metabolite lists.

| | |
|---|---|
| Source | `KnowledgeSource.CHEBI` |
| Class | `knowledge_lookup.adapters.ChEBIAdapter` |
| Requires | none |
| Identifiers | `CHEBI:15365`, `chebi:15365`, `CHEBI_15365`, bare `15365` or the OBO IRI |
| Upstream API | `https://www.ebi.ac.uk/chebi/backend/api/public` (OpenAPI schema at `.../chebi/backend/api/schema/`) |
| Licence | ChEBI data is CC BY 4.0 |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ChEBIAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ChEBIAdapter(LookupConfig()) as adapter:
        print([c.primary_label for c in await adapter.search_concepts("metformin", limit=3)])

        aspirin = await adapter.get_concept_details("CHEBI:15365")
        data = aspirin.source_data["CHEBI"]
        print(aspirin.primary_label, data["formula"], data["inchikey"])
        print([c for c in aspirin.categories if c.startswith("role:")][:3])

        for rel in await adapter.get_relationships("CHEBI:15365", limit=5):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])

        print([(m["toSource"], m["toId"]) for m in await adapter.get_mappings("CHEBI:15365")][:5])


asyncio.run(main())
```

Output (live, 2026-10-06):

```
['metformin', 'metformin(2+)', 'metformin hydrochloride']
acetylsalicylic acid C9H8O4 BSYNRYMUTXBXSQ-UHFFFAOYSA-N
['role: geroprotector', 'role: non-steroidal anti-inflammatory drug', 'role: antiviral agent']
is_a CHEBI:22723 benzoic acids
is_a CHEBI:140310 phenyl acetates
is_a CHEBI:26596 salicylates
has_role CHEBI:35475 non-steroidal anti-inflammatory drug
has_role CHEBI:35481 non-narcotic analgesic
[('DrugCentral', '74'), ('PDBeChem', 'AIN'), ('Wikipedia', 'Aspirin'), ('KEGG COMPOUND', 'C01405'), ('MetaCyc', 'CPD-524')]
```

## Searching

`search_concepts(query, limit)` calls `es_search/?term=&size=` (Elasticsearch over names, synonyms and IDs; `term` can be `CHEBI:15365` or `15365`). Each hit contains name, accession, stars, formula, mass, SMILES, InChIKey; no definition. `concept_type` is `CHEMICAL`; `confidence_score` is 0.9 for 3-star (fully curated) and 0.75 for 2-star (preliminary) entries.

Ranking quirk: the search is plain relevance, so a query that is only a *synonym* of the compound you want ranks low. `aspirin` returns "aspirin trelamine" and the aspirin-triggered resolvins before `CHEBI:15365` "acetylsalicylic acid" (position 13 of 26). The adapter fetches up to `3 x limit` hits (15 to 50) and moves hits whose name equals the query to the front (`metformin` -> `CHEBI:6801` first), otherwise keeps the ChEBI order. For synonyms, search by the ChEBI name (`acetylsalicylic acid`) or an ID, or raise `limit`.

## Concept details

`get_concept_details(concept_id)` is one request to `compound/{number}/`.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `CHEBI:15365` / ChEBI name with HTML markup removed (`coenzyme Q10`) |
| `definitions` | the ChEBI definition |
| `synonyms` | INN, synonyms, IUPAC name and brand names, deduplicated, at most 100 |
| `parents` / `children` | labels of direct `is a` neighbours |
| `categories` | `role: <name>` for every role in ChEBI's role classification (biological, chemical and application roles) |
| `source_data[CHEBI]` | `stars`, `formula`, `mass`, `monoisotopic_mass`, `charge`, `smiles`, `inchi`, `inchikey`, `secondary_ids`, `roles`, `modified_on` |
| `identifiers` | the ChEBI ID with a link |

The concept type stays `CHEMICAL` even for drugs, to match how the OLS adapter classifies ChEBI terms and keep `concept_types` filters consistent; use the `role:` categories to recognise drugs.

## Relationships

`get_relationships(concept_id, limit=25)` combines `ontology/parents/{id}/` (outgoing) and `ontology/children/{id}/` (incoming):

| `relation_label` | Meaning |
|---|---|
| `is_a`, `has_role`, `has_functional_parent`, `is_conjugate_acid_of`, `is_conjugate_base_of`, `is_enantiomer_of`, `has_part`, ... | ChEBI's relation type in snake_case, outgoing |
| `has_subclass` | entities that are `is a` this one |
| `inverse_<relation>` | other incoming relations, e.g. `inverse_has_functional_parent` |

Outgoing edges are listed `is_a`, then `has_role`, then everything else, followed by incoming edges; the total is capped by `limit`. Items carry `direction`. Aspirin has 40 outgoing edges (mostly roles), so raise `limit` if you want all roles.

## Mappings

`get_mappings(concept_id)` maps the `database_accessions` of the compound: manual cross-references (DrugBank, KEGG COMPOUND/DRUG, HMDB, DrugCentral, PDBeChem, MetaCyc, LINCS, Wikipedia, ...), CAS numbers (`toSource: "CAS"`, deduplicated across suppliers) and registry numbers (Reaxys, Gmelin, Beilstein). PubMed citations are not mappings and are skipped. PubChem CIDs are only present when ChEBI curates one for the entity (not the case for aspirin, metformin or coenzyme Q10 at the time of writing); use the UniChem or PubChem adapters for those.

## Rate limits and caveats

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); typical latency 0.3 to 2 s. Unknown IDs answer HTTP 404 and yield `None` / `[]`.

- ChEBI names are the chemical entity's name, not always the drug name (`acetylsalicylic acid`, `(R)-carnitine`); ionic forms are separate entries (`metformin(1+)`).
- Names and relation names may contain HTML tags; the adapter strips them.

## See also

- [UniChem adapter](unichem_adapter.md), [PubChem adapter](pubchem_adapter.md), [DrugBank adapter](drugbank_adapter.md)
- [All adapters](../README.md)
