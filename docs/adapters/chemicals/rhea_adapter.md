---
description: Rhea expert-curated biochemical reactions with ChEBI participants, EC numbers, GO terms and KEGG/MetaCyc/Reactome cross-references.
---

# Rhea adapter

Searches Rhea, the SIB reaction database that underlies UniProt's catalytic-activity annotation. Every reaction is balanced and its participants are ChEBI compounds, so the most useful query for metabolomics is the reverse lookup: give a ChEBI id (for example `CHEBI:16651`, (S)-lactate) and get every curated reaction that consumes or produces it.

| | |
|---|---|
| Source | `KnowledgeSource.RHEA` |
| Class | `knowledge_lookup.adapters.RheaAdapter` |
| Requires | none (keyless) |
| Identifiers | `RHEA:23444`, or the bare number `23444` |
| Upstream APIs | search `https://www.rhea-db.org/rhea`, SPARQL `https://sparql.rhea-db.org/sparql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import RheaAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with RheaAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("CHEBI:16651", limit=3):
            print(c.primary_id, c.primary_label)

        ldh = await adapter.get_concept_details("RHEA:23444")
        print(ldh.primary_label, ldh.categories)

        for rel in await adapter.get_relationships("RHEA:23444"):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])
        for m in await adapter.get_mappings("RHEA:23444"):
            print(m["toSource"], m["toId"])


asyncio.run(main())
```

Output (abridged):

```
RHEA:10960 (S)-lactate = (R)-lactate
RHEA:10984 (S)-lactate + oxaloacetate = (S)-malate + pyruvate
RHEA:14277 (S)-lactaldehyde + NAD(+) + H2O = (S)-lactate + NADH + 2 H(+)
(S)-lactate + NAD(+) = pyruvate + NADH + H(+) ['EC:1.1.1.27']
has_substrate CHEBI:16651 (S)-lactate
has_substrate CHEBI:57540 NAD(+)
has_product CHEBI:15378 H(+)
has_product CHEBI:57945 NADH
has_product CHEBI:15361 pyruvate
has_ec_number EC:1.1.1.27 EC:1.1.1.27
is_a RHEA:34555 a (2S)-2-hydroxycarboxylate + NAD(+) = a 2-oxocarboxylate + NADH + H(+)
has_directional_variant RHEA:23445 (S)-lactate + NAD(+) => pyruvate + NADH + H(+)
has_directional_variant RHEA:23446 pyruvate + NADH + H(+) => (S)-lactate + NAD(+)
has_bidirectional_variant RHEA:23447 (S)-lactate + NAD(+) <=> pyruvate + NADH + H(+)
has_go_term GO:0004459 L-lactate dehydrogenase (NAD+) activity
EC EC:1.1.1.27
KEGG R00703
MetaCyc L-LACTATE-DEHYDROGENASE-RXN
Reactome R-HSA-70510.8 (and two more)
GO GO:0004459
UniProt rhea:23444
```

## Reaction ids and variants

Rhea numbers reactions in blocks of four: the **master** reaction `N` (direction not stated, written with `=`), the two directional reactions `N+1` (left to right, `=>`) and `N+2` (right to left), and the bidirectional reaction `N+3` (`<=>`). Only master reactions are in the search index (`query=RHEA:23445` finds nothing); the variants are reached through SPARQL, which `get_concept_details`, `get_relationships` and `get_mappings` do automatically when given a variant id (the master is found by probing the four candidate ids). Master reactions have `semantic_types == ["master reaction"]`; variants have `directional reaction` or `bidirectional reaction`.

## Searching

`search_concepts(query, limit)` sends one request to the TSV search endpoint (`columns=rhea-id,equation,ec,chebi-id`, `limit` capped at 100):

| Query | Rhea query sent |
|---|---|
| `lactate`, `NAD(+) lactate` | free text (Lucene syntax characters blanked: `NAD lactate`) |
| `CHEBI:16651` | reactions with that compound as a participant |
| `EC:1.1.1.27` or `1.1.1.27` | `ec:1.1.1.27` |
| `RHEA:23444` or `23444` | exact reaction |

Free text matches participant names, equations, EC numbers and synonyms, in Rhea's relevance order. Rhea answers a query with unbalanced Lucene syntax (such as `a(b`) with a 500 HTML page, which is why special characters are stripped. A bare number is always read as a Rhea id; use `CHEBI:16651` for a ChEBI id. Results are de-duplicated (some queries list a reaction twice).

Each result is a `MOLECULAR_FUNCTION` concept (a reaction is the catalytic activity that UniProt and GO describe; the model has no reaction type) labelled with the equation, with EC numbers in `categories` and the participant ChEBI ids in `source_data`.

## Concept details

`get_concept_details("RHEA:23444")` makes two requests: the TSV search with the full column set and the JSON format for curation status.

| Field | Value |
|---|---|
| `primary_label` | equation as curated, e.g. `(S)-lactate + NAD(+) = pyruvate + NADH + H(+)` |
| `categories` | EC numbers |
| `definitions` | Rhea comment, when there is one |
| `identifiers` | `RHEA` (URL), `KEGG` reaction id, `REACTOME` reaction ids, `GO` term |
| `source_data[RHEA]` | `equation`, `ec`, `chebi_ids`, `chebi_names`, `pubmed`, `go`, `kegg`, `metacyc`, `reactome`, `uniprot_count`, `status`, `balanced`, `transport` |

For a directional or bidirectional id the concept comes from SPARQL (equation, direction `L-R`/`R-L`/`bidirectional`, status, EC numbers) and `parents` holds the master id.

## Relationships

`get_relationships(concept_id, limit=50)` uses SPARQL for the structure and one TSV request for GO:

| `relation_label` | Meaning |
|---|---|
| `has_substrate` / `has_product` | ChEBI participants of the left / right side, with `side` (`L`/`R`) and `stoichiometry` (an integer, or `"N"` for polymers). A master or bidirectional reaction is reversible, so "substrate" means the left side as written; for a right-to-left variant the sides are swapped |
| `has_ec_number` | `EC:` numbers (the name is the number) |
| `is_a` | the generic Rhea reaction this one specialises (e.g. `RHEA:34555`, "a (2S)-2-hydroxycarboxylate + NAD(+) = ...") |
| `has_directional_variant` / `has_bidirectional_variant` | the other reactions of the block, with `direction` (`L-R`, `R-L`, `bidirectional`) |
| `variant_of` | for a variant id, the master reaction |
| `has_go_term` | GO molecular-function term (master only) |

Participants of generic or polymer compounds keep their Rhea accessions (`GENERIC:...`, `POLYMER:...`). If the SPARQL endpoint fails, the call returns `[]`.

## Mappings

`get_mappings` reads one TSV row: `EC`, `KEGG` (reaction id), `MetaCyc`, `Reactome` (reaction ids, usually several), `EcoCyc`, `M-CSA`, `GO`, and `UniProt` with `mappingType: "enzyme_count"`, `count` set to the number of UniProtKB enzymes annotated with the reaction and `toId` the UniProt query that lists them (`rhea:23444`; omitted when the count is zero). Prefixes such as `KEGG:` are removed from the ids.

## Rate limits, licence and errors

No limit is published; requests are spaced 0.5 s apart and use the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Rhea is CC BY 4.0; cite Bansal et al., *Nucleic Acids Res.* 2022. Interface methods log errors and return `[]` / `None`. The per-request timeout is 45 s.

## Caveats

- **Cloudflare**: the single-record download `https://www.rhea-db.org/rhea/10000.json` (the `.rxn`/`.rdf` forms were not tried) answers a Cloudflare "Just a moment" challenge page to scripted clients, so they are not used. The search endpoint and the SPARQL endpoint are not challenged. If the search endpoint starts returning HTML the adapter raises internally and the interface methods return empty results.
- The SPARQL endpoint occasionally stalls (one 60 s timeout was seen while probing); only `get_relationships` and variant-id lookups depend on it.
- Unknown `columns` are dropped silently from the TSV header, so a typo in a column name shows up only as a missing field.

## Live verification (2026-10-08)

`knowledge-lookup check RHEA` passes. Measured: TSV search 0.35 to 0.8 s (up to 3.5 s for common terms), SPARQL 0.2 to 1 s warm and about 2.4 s cold, `get_concept_details` 0.9 s, `get_relationships` for a master reaction 3.4 s (three requests plus throttling), `get_mappings` 0.5 s. Responses are small (a full reaction row is about 600 bytes; the participant query returns about 2 KB).

## See also

- [ChEBI adapter](chebi_adapter.md), [Reactome adapter](../pathways/reactome_adapter.md)
- [All adapters](../README.md)
