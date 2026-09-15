---
description: ChEMBL bioactive molecules, drugs and targets, plus raw access to any ChEMBL endpoint (requires the chembl extra).
---

# ChEMBL adapter

Looks up molecules, drugs and targets in ChEMBL through `chembl_webresource_client`. A generic `query` method gives access to any other ChEMBL endpoint (activities, assays, mechanisms, indications, ...). Molecule concepts summarise key physicochemical properties and administration flags.

| | |
|---|---|
| Source | `KnowledgeSource.CHEMBL` |
| Class | `knowledge_lookup.adapters.ChEMBLAdapter` |
| Requires | `[chembl]` extra |
| Identifiers | ChEMBL ID of a molecule, drug or target, e.g. `CHEMBL25` |
| Upstream API | `https://www.ebi.ac.uk/chembl/api/data` (via `chembl_webresource_client`) |

{% hint style="warning" %}
**Requires the `[chembl]` extra.** Without it, `ChEMBLAdapter` is `None` and `KnowledgeSource.CHEMBL` is missing from `ADAPTER_CLASSES`.

The ChEMBL client is **synchronous**. The async methods (`search_concepts`, `get_concept_details`, `lookup_molecule`, `lookup_drug`, `lookup_target`, `query_async`) run it in a worker thread. `query`, `lookup_activity` and `get_activities_for_*` are plain synchronous methods and block while they run.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ChEMBLAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    if ChEMBLAdapter is None:
        raise SystemExit("Install the [chembl] extra to use ChEMBL")

    async with ChEMBLAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("aspirin", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        aspirin = await adapter.get_concept_details("CHEMBL25")
        print(aspirin.categories, aspirin.definitions[-1])

        # Raw bioactivity records. query_async runs the client in a worker thread
        # and fetches only `limit` rows.
        rows = await adapter.query_async(
            "activity",
            filters={"molecule_chembl_id": "CHEMBL25", "target_chembl_id": "CHEMBL221"},
            fields=["target_pref_name", "standard_type", "standard_value"],
            limit=2,
        )
        for row in rows:
            print(row["target_pref_name"], row["standard_type"], row["standard_value"])


asyncio.run(main())
```

Output:

```
CHEMBL25 ASPIRIN CHEMICAL
CHEMBL163612 PHENYLASPIRINATE CHEMICAL
CHEMBL499817 BROMOASPIRIN CHEMICAL
['Small molecule', 'Therapeutic', 'Natural Product', 'Oral'] Natural product
Prostaglandin G/H synthase 1 Inhibition 80.0
Prostaglandin G/H synthase 1 Inhibition 21.9
```

## Searching

`search_concepts(query, limit)` queries the `molecule`, `drug` and `target` endpoints in that order with `pref_name__icontains=<query>`. It stops as soon as `limit` results are collected, so results are usually all molecules.

**Molecules** become concepts like this:

| Field | Value |
|---|---|
| `primary_id` | `molecule_chembl_id` |
| `primary_label` | `pref_name`; falls back to the ChEMBL ID |
| `concept_type` | `CHEMICAL` |
| `definitions` | description (if any), `Type: <molecule_type>`, `Properties: MW: ..., Formula: ..., LogP: ..., PSA: ..., HBD: ..., HBA: ..., Aromatic rings: ..., RO3 compliant: ..., QED: ...`, `Structures: Has SMILES, Has InChI, Has InChI Key`, `Natural product` |
| `categories` | molecule type plus the flags `Therapeutic`, `Natural Product`, `Oral`, `Topical`, `Parenteral` |
| `synonyms` | empty (ChEMBL stores them as `molecule_synonyms` in `source_data`) |
| `identifiers` | one `CHEMBL` identifier, URL `https://www.ebi.ac.uk/chembl/compound_report_card/<id>/` |
| `sources` | `['CHEMBL']` |
| `confidence_score` | `0.0` (not set) |
| `source_data[CHEMBL]` | raw molecule record |

**Drugs** become `DRUG` concepts. They use `drug_chembl_id` (or `molecule_chembl_id`), the URL `https://www.ebi.ac.uk/chembl/drug/<id>/`, the description or drug type as definition, and the drug type as category. ChEMBL returns `drug_type` as a numeric code, so these come out as strings such as `1`.

**Targets** are typed `PROTEIN` only when `target_type` is exactly `PROTEIN`. ChEMBL uses values such as `SINGLE PROTEIN`, so targets usually come back as `UNKNOWN`. They use the URL `https://www.ebi.ac.uk/chembl/target_report_card/<id>/` and the target type as category.

Drug and target types are always passed through `map_category_to_ontology`, which runs extra OLS and BioOntology searches for each result. Molecule categories are only mapped when `LookupConfig.enable_ontology_mapping` is true.

## Concept details

`get_concept_details(chembl_id)` looks the ID up as a molecule, then as a drug (by `molecule_chembl_id`), then as a target, and converts the first match as described above. Molecule IDs resolve quickly. A target ID took about 7 seconds in testing, most of it spent mapping the target type through OLS and BioOntology.

## Source-specific methods

| Method | Description |
|---|---|
| `query(endpoint, filters=None, fields=None, limit=100) -> list[dict]` | Synchronous. Queries any client endpoint (`activity`, `assay`, `mechanism`, `drug_indication`, `target`, ...) with Django-style `filters` (`pref_name__icontains`, `standard_type`, ...) and a `fields` projection. Only `limit` records are fetched. Server and network errors are retried with backoff (up to four attempts). Raises `ValueError` for an unknown endpoint and returns `[]` for other errors |
| `async query_async(endpoint, filters=None, fields=None, limit=100) -> list[dict]` | The same query in a worker thread through the shared retry and circuit breaker. Raises `ValueError` for an unknown endpoint and re-raises the last API error instead of returning `[]` |
| `lookup_activity(filters=None, fields=None, limit=100)` | `query("activity", ...)` (synchronous) |
| `get_activities_for_molecule(molecule_id, limit=50)`, `get_activities_for_target(target_id, limit=50)` | activity records for one molecule or target (synchronous) |
| `async lookup_molecule`, `lookup_drug`, `lookup_target` (`filters=None, fields=None, limit=100`) | `query_async` on the endpoint, parsed into concepts as described under Searching. Must be awaited; they return `[]` on errors |
| `check_api_status(timeout=None) -> dict` | Synchronous. Fetches one record each from the `molecule` and `activity` endpoints in worker threads (`status` is a single-object resource and is listed as `status(not a list endpoint)`). Returns keys `available` (`True` if at least one probe answered), `status_code` (always `None`), `error` (the last failure), `endpoints_tested` (for example `molecule`, `activity(failed)`, `molecule(timed out)`) and `available_endpoints`. Probes still running after `timeout` seconds (default `timeout_per_source`) are reported as timed out; their threads finish in the background |
| `async map_category_to_ontology(category) -> str` | exact label or synonym match in OLS, then BioOntology; returns the input unchanged if nothing matches, or `"unknown"` for empty or non-string input |

ChEMBL ignores filter fields that an endpoint does not have and returns every record instead, so check field names against the endpoint (for example `https://www.ebi.ac.uk/chembl/api/data/drug/schema.json`).

## Rate limits and errors

The async methods run the client in a worker thread through `_thread_with_retry`, which applies the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). A slow ChEMBL query therefore does not hold up other sources in a parallel `CentralKnowledgeLookup` search, and `timeout_per_source` stops the wait (the worker thread still finishes its request in the background). The synchronous `query` uses its own backoff decorator and does not report to the circuit breaker. `chembl_webresource_client` caches responses locally, so repeated queries are fast.

`search_concepts` and `get_concept_details` log errors and return `[]` or `None`.

## See also

- [UniChem adapter](../chemicals/unichem_adapter.md): map ChEMBL IDs to DrugBank, PubChem, ChEBI
- [PubChem adapter](../chemicals/pubchem_adapter.md), [KEGG adapter](../pathways/kegg_adapter.md)
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): extras
