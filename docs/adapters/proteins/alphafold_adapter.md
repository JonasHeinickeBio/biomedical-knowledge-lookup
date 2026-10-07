---
description: AlphaFold DB predicted protein structures: pLDDT confidence, model and PAE URLs, UniProt mapping and links to experimental PDB structures.
---

# AlphaFold DB adapter

Looks up AlphaFold Protein Structure Database entries (EMBL-EBI and Google DeepMind) by UniProt accession, AlphaFold entry id or human gene symbol. A concept is the predicted structure of one protein: global pLDDT, the share of residues in each confidence band, and the URLs of the model, PAE and confidence files. Structure files are **never downloaded**; only URLs are returned.

| | |
|---|---|
| Source | `KnowledgeSource.ALPHAFOLD` |
| Class | `knowledge_lookup.adapters.AlphaFoldAdapter` |
| Requires | none (no key) |
| Identifiers | UniProt accession `P38398` (isoform `P38398-2` allowed), AlphaFold entry id `AF-P38398-F1` (`AF-P38398-2-F1` for an isoform), or a gene symbol / protein name (resolved to a human UniProt accession) |
| Upstream APIs | `https://alphafold.ebi.ac.uk/api/prediction/{id}`; `https://rest.uniprot.org/uniprotkb/search` and `/{accession}` for symbol resolution and PDB links |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import AlphaFoldAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


async def main():
    async with AlphaFoldAdapter(LookupConfig()) as adapter:
        concept = (await adapter.search_concepts("BRCA1", limit=1))[0]
        print(concept.primary_id, "-", concept.definitions[0])
        urls = concept.source_data[KnowledgeSource.ALPHAFOLD]["urls"]
        print(urls["model_cif"])

        for edge in await adapter.get_relationships("P38398", limit=6):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

Output (live, October 2026):

```
AF-P38398-F1 - AlphaFold v6 predicted structure of BRCA1_HUMAN (Homo sapiens), 1863 residues, mean pLDDT 41.6 (80% very low confidence)
https://alphafold.ebi.ac.uk/files/AF-P38398-F1-model_v6.cif
has_predicted_structure AF-P38398-F1 AlphaFold model AF-P38398-F1 (v6)
has_predicted_structure AF-P38398-8-F1 AlphaFold model AF-P38398-8-F1 (v6)
has_predicted_structure AF-P38398-7-F1 AlphaFold model AF-P38398-7-F1 (v6)
has_experimental_structure 1T15 PDB 1T15 (X-ray, 1.85 A)
has_experimental_structure 1T29 PDB 1T29 (X-ray, 2.30 A)
has_experimental_structure 1JNX PDB 1JNX (X-ray, 2.50 A)
```

(80% of BRCA1 residues are in the very-low-confidence band, which pulls the mean pLDDT down.)

## Searching and resolving ids

`search_concepts(query, limit)`:

1. A UniProt accession or AF entry id goes straight to `/api/prediction/{id}`.
2. Anything else is resolved to human (taxon 9606) UniProt accessions with the UniProt REST search. A gene-like token (`BRCA1`) tries `gene_exact:BRCA1 AND organism_id:9606 AND reviewed:true`, then the same query without `reviewed:true`; a phrase (`breast cancer type 1`) uses a free-text query restricted to reviewed human entries. Reviewed (Swiss-Prot) entries come first on purpose: the unreviewed first hit for `BRCA1` is a TrEMBL fragment (E7ENB7).
3. At most `min(limit, 5)` accessions are then looked up in AlphaFold DB (one request each).

Other organisms: pass the UniProt accession directly, or set `adapter.organism_id` (default `9606`). Disease and symptom words match nothing meaningful; the source is protein-centric.

## Concept details

`get_concept_details(id)` returns the canonical-sequence entry for an accession or symbol, or exactly the entry asked for when given an entry id. Isoform models (BRCA1 has 8 entries) are listed in `source_data["ALPHAFOLD"]["other_entries"]`.

| Field | Value |
|---|---|
| `primary_id` | AlphaFold entry id, e.g. `AF-P38398-F1` |
| `primary_label` | UniProt protein name |
| `concept_type` | `PROTEIN`; `categories` = organism |
| `synonyms` | gene, UniProt entry name (`BRCA1_HUMAN`), accession, entry id |
| `identifiers` | `ALPHAFOLD` (entry page URL) and `UNIPROT` |
| `definitions` | one line with model version, residues, mean pLDDT and the very-low-confidence share |
| `source_data["ALPHAFOLD"]` | `global_plddt`, `plddt_fractions` (`very_low` < 50, `low` 50-70, `confident` 70-90, `very_high` > 90), `sequence_length`, `model_version` (6), `all_versions`, `model_created`, `tool`, `reviewed`, `reference_proteome`, `sequence_checksum`, `urls` (`model_cif`, `model_pdb`, `model_bcif`, `pae_image`, `pae_json`, `plddt_json`, `msa`, `alphamissense_csv`, `page`), `other_entries` |

The full amino-acid sequence is deliberately not copied (it makes the response ~30 KB); get it from UniProt.

## Relationships and mappings

| Call | Result |
|---|---|
| `get_relationships(protein, limit=10)` | `has_predicted_structure` per AlphaFold model (id, `global_plddt`, `model_url`, `pae_image_url`, `page_url`) and `has_experimental_structure` per PDB cross-reference from the UniProt record (`method`, `resolution`, `chains`, RCSB `page_url`, best resolution first, NMR last). The limit is shared: up to half goes to PDB structures. The PDB part costs one extra UniProt request and is silently omitted if UniProt is unreachable |
| `get_mappings(accession or symbol)` | UniProt accession -> every AlphaFold entry (`mappingType: has_predicted_structure`) |
| `get_mappings("AF-...")` | entry id -> UniProt accession (`predicted_structure_of`) |

## Rate limits, versions, licence, errors

No rate limit is published for either service. A search is 1-2 UniProt calls plus up to 5 AlphaFold calls; details, mappings and relationships are 1-2 calls. Measured latency: AlphaFold prediction 0.1-0.6 s, UniProt search 0.4-1.5 s typically, but spikes of 10-30 s were seen on `rest.uniprot.org` during testing (free-text and unreviewed queries are the slow ones). If this matters, pass accessions.

The current model version is v6 (BRCA1 entry created 2025-08-01); file URLs embed the version and always come from the response. Predictions are released under CC BY 4.0; cite Jumper et al. 2021 and Varadi et al. 2024. An accession without a model returns HTTP 404 and an invalid identifier HTTP 400; both give `None` / `[]` here, as do network errors.

## See also

- [UniProt adapter](../core/uniprot_adapter.md), [HGNC adapter](hgnc_adapter.md)
