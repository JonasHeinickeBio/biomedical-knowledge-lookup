---
description: Generic HL7 FHIR terminology server client (tx.fhir.org, Ontoserver, German MII or any $lookup/$expand server).
---

# FHIR terminology server adapter

A generic client for HL7 FHIR R4 terminology servers. One adapter reaches every code system the configured server hosts (SNOMED CT, LOINC, ICD-10 / ICD-10-CM / ICD-10-GM / ICD-11, ATC, RxNorm, UCUM, HPO, OPS ...) through the standard operations `CodeSystem/$lookup`, `ValueSet/$expand`, `CodeSystem/$validate-code` and `ConceptMap/$translate`. Point it at a different server with one environment variable. This is the route to the German MII terminology server (ICD-10-GM, OPS, LOINC, SNOMED CT, ATC), which speaks the same API.

| | |
|---|---|
| Source | `KnowledgeSource.FHIRTERMINOLOGY` |
| Class | `knowledge_lookup.adapters.FHIRTerminologyAdapter` |
| Requires | none for the default public server; optional credentials for protected servers |
| Identifiers | `<system>\|<code>` with an alias or a URI: `loinc\|2093-3`, `snomed\|84229001`, `http://loinc.org\|2093-3`; `<system>\|<code>\|<version>` pins a code system version |
| Upstream API | `https://tx.fhir.org/r4` (default, keyless), `FHIR_TERMINOLOGY_URL` to change |

## Configuration

All environment variables are optional; nothing is ever sent unless you set it.

| Variable | Meaning |
|---|---|
| `FHIR_TERMINOLOGY_URL` | Base URL. Default `https://tx.fhir.org/r4`. Also verified keyless: `https://r4.ontoserver.csiro.au/fhir` (CSIRO Ontoserver sandbox, SNOMED CT AU) |
| `FHIR_TERMINOLOGY_SYSTEMS` | Comma-separated code systems `search_concepts` queries by default, as aliases or URIs. `alias@version` pins a version, e.g. `icd10gm@2020,ops@2021,atc@2025.0.0`. Unset: SNOMED CT, ICD-10-CM and LOINC |
| `FHIR_TERMINOLOGY_TOKEN` | Sent as `Authorization: Bearer <token>` |
| `FHIR_TERMINOLOGY_USER` + `FHIR_TERMINOLOGY_PASSWORD` | HTTP Basic, used only when **both** are set and no token is set |

Credentials are refused for plain `http://` servers (except `localhost`), because they would travel unencrypted; a warning is logged. The token can alternatively be stored as `fhir_terminology_token` in the config's `api_keys`. A server that needs authentication answers 401/403 and the adapter logs a hint naming these variables; the authentication paths are covered by mocked unit tests, since the public servers do not require credentials (https://fhir.loinc.org answers 401 without them).

Aliases (case, hyphens and spaces are ignored, so `ICD-10-GM` = `icd10gm`):

| Alias | System URI |
|---|---|
| `loinc` | `http://loinc.org` |
| `snomed`, `snomedct`, `sct` | `http://snomed.info/sct` |
| `icd10` | `http://hl7.org/fhir/sid/icd-10` (WHO ICD-10) |
| `icd10cm` | `http://hl7.org/fhir/sid/icd-10-cm` |
| `icd10gm` | `http://fhir.de/CodeSystem/bfarm/icd-10-gm` |
| `icd11` | `http://id.who.int/icd/release/11/mms` |
| `ops` | `http://fhir.de/CodeSystem/bfarm/ops` |
| `atc` | `http://www.whocc.no/atc` |
| `rxnorm` | `http://www.nlm.nih.gov/research/umls/rxnorm` |
| `ucum` | `http://unitsofmeasure.org` |
| `hpo`, `hp` | `http://purl.obolibrary.org/obo/hp.owl` |
| `mondo` | `http://purl.obolibrary.org/obo/mondo.owl` |
| `cvx` | `http://hl7.org/fhir/sid/cvx` |

Any other system works by its URI.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import FHIRTerminologyAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with FHIRTerminologyAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("fatigue", limit=3):
            print(c.primary_id, c.primary_label)

        cfs = await adapter.get_concept_details("snomed|52702003")
        print(cfs.primary_label, cfs.concept_type, cfs.parents)

        for r in (await adapter.get_relationships("icd10cm|G93.3"))[:3]:
            print(r["relation_label"], r["related_id"], r["related_name"])

        print(await adapter.validate_code("snomed|84229001", display="Fatigue"))


asyncio.run(main())
```

Output (live against tx.fhir.org, 2026-10-09):

```
snomed|84229001 Fatigue
icd10cm|G93.3 Postviral and related fatigue syndromes
loinc|LA19104-1 0 - no fatigue
Chronic fatigue syndrome DISEASE ['snomed|84229001', 'snomed|128283000']
is_a icd10cm|G93 Other disorders of brain
has_subtype icd10cm|G93.31 Postviral fatigue syndrome
has_subtype icd10cm|G93.32 Myalgic encephalomyelitis/chronic fatigue syndrome
{'valid': True, 'display': 'Fatigue', 'message': None}
```

For a German MII server (ICD-10-GM, OPS, LOINC, SNOMED CT, ATC):

```bash
export FHIR_TERMINOLOGY_URL=https://<your-mii-terminology-server>/fhir
export FHIR_TERMINOLOGY_TOKEN=...            # or FHIR_TERMINOLOGY_USER / FHIR_TERMINOLOGY_PASSWORD
export FHIR_TERMINOLOGY_SYSTEMS=icd10gm,ops,loinc,snomed,atc
```

The BfArM terminology service at `terminologien.bfarm.de` was probed for this page but its FHIR base URL could not be determined (`/fhir/metadata` answered 404 and `/fhir/r4/metadata` 400), so no German production server is verified here. The CSIRO Ontoserver sandbox hosts the ICD-10-GM and OPS code systems with the same API and was used to verify the German paths (lookup, filtered search, pinned versions).

## Methods

| Method | Operation | Returns |
|---|---|---|
| `search_concepts(query, limit=20, systems=None)` | `ValueSet/$expand` with `filter` and `count` | thin concepts (label, id, `inactive` flag) from each system, interleaved so every system is represented within `limit`. `systems` takes aliases or URIs (`"loinc,atc"`, `["icd10gm@2020"]`). A query of the form `<system>\|<code>` returns that one concept |
| `get_concept_details(id)` | `CodeSystem/$lookup` | display, definition, designations as synonyms, SNOMED semantic tag, parents and children, properties in `source_data` |
| `get_relationships(id)` | `CodeSystem/$lookup` (`parent` / `child`) | `is_a` (to each parent) and `has_subtype` (to each child), `related_id` in the same `<alias>\|<code>` form |
| `get_mappings(id, target_system=None)` | `ConceptMap/$translate` | one mapping per match and ConceptMap; `mappingType` from the FHIR equivalence (`equal` and `equivalent` = `exactMatch`, `wider` = `broadMatch`, `narrower` = `narrowMatch`, `inexact` = `closeMatch`, `relatedto` = `relatedMatch`); `disjoint` matches are dropped |
| `validate_code(id, display=None)` | `CodeSystem/$validate-code` | `{"valid", "display", "message"}` |
| `list_code_systems(title=None, url=None, limit=50)` | `CodeSystem?...` | `{url, version, name, title}` per hosted system |
| `get_capabilities()` | `metadata?_summary=true` | server software, FHIR version, served resource types |

Concept details:

| Field | Value |
|---|---|
| `primary_id` | `<alias>\|<code>` (the full URI when no alias exists) |
| `primary_label` | `display` of the code |
| `concept_type` | by system: LOINC `OBSERVATION`, ICD `DISEASE`, OPS `PROCEDURE`, ATC/RxNorm `DRUG`, HPO `PHENOTYPE`. SNOMED CT uses the semantic tag of the fully specified name: disorder `DISEASE`, finding `SYMPTOM`, procedure `PROCEDURE`, substance `CHEMICAL`, medicinal product `DRUG`, body structure `ANATOMICAL_ENTITY`, organism `ORGANISM`, observable entity `OBSERVATION` |
| `synonyms` | active designations (inactive SNOMED descriptions and the definition are left out) in English, German or without a language tag; at most 50 |
| `definitions` | the `definition` parameter, or the SNOMED definition description |
| `parents` / `children` | ids from the `parent` / `child` properties |
| `identifiers` | `FHIRTERMINOLOGY`, plus a native `SNOMEDCT`, `LOINC`, `ICD10GM`, `ICD11`, `RXNORM`, `HPO` or `MONDO` identifier with the bare code |
| `source_data` | server URL, system, code, version, all other properties (`RELATEDNAMES2`/`normalForm` are dropped), all designations |

`$lookup` is sent with `property=*&property=parent&property=child`: Ontoserver returns no children for `*` alone, and tx.fhir.org returns no hierarchy for an explicit list that omits them.

## Which systems each public server answers

Verified live on 2026-10-09 with `$lookup` of a known code (ME/CFS-relevant where possible), `$expand` and `$translate`. "pin" means the server hosts several versions and the call fails without `@version` or a third id segment.

| System | tx.fhir.org/r4 (FHIRsmith 0.15.0) | r4.ontoserver.csiro.au/fhir (Ontoserver 6.29, sandbox) |
|---|---|---|
| SNOMED CT | yes, International edition 20250201; 84229001 Fatigue, children included | yes, Australian edition 20260930 |
| LOINC | yes, v2.82, with German (`de-DE`) names | yes |
| ICD-10 (WHO) | yes (`2019-covid-expanded`) | **404** |
| ICD-10-CM | yes, 2026-04-01 (G93.32 = ME/CFS) | yes, 2024 |
| ICD-10-GM | **422** (not hosted) | yes, versions 2014-2020; lookup of G93.3 works, search needs `icd10gm@2020` |
| OPS | **422** | yes, 2021 (search needs `ops@2021`) |
| ICD-11 MMS | yes (search results look unusual: `filter` matched unrelated codes) | yes, 2026-01 |
| ATC | yes, 2025 | **pin** (versions 2020-05, 20241015, 2025.0.0, 20250201); `atc@2025.0.0` works |
| RxNorm | yes | yes, 20231106 |
| UCUM | yes | yes |
| HPO | **422** | yes, 20201207 (the URL `http://purl.obolibrary.org/obo/hp.owl`; the URL `http://human-phenotype-ontology.org` is a 404) |
| MONDO | **422** | **404** |
| CVX | yes | yes |

Further operation differences:

- **Unknown code system or code:** tx.fhir.org answers 422 for an unknown system and 404 for an unknown code; Ontoserver answers 404 for both (and 422 for an ambiguous version). Both return an `OperationOutcome`; the adapter treats all of them as "not found" and returns `None` / `[]`.
- **Implicit value set** (`ValueSet/$expand?url=<system>?fhir_vs`): on tx.fhir.org only SNOMED CT; on Ontoserver SNOMED CT, ICD-10-CM and ICD-11. For every other system the adapter falls back to posting an inline `ValueSet` (`compose.include.system`, plus `version` when pinned), which both servers accept for every system they host. The mode that worked is remembered per system, so only the first search pays for the failed request. This is the only server-specific behaviour and it is generic FHIR (no server detection).
- **`ConceptMap/$translate`:** tx.fhir.org has ConceptMaps but none that cover SNOMED CT, ICD-10-CM or LOINC codes, so it answers "No ConceptMap is available" and the adapter returns `[]`. Ontoserver translates SNOMED CT without a target: 52702003 (Chronic fatigue syndrome) gives ICD-10-AM `G93.3` (`broadMatch`), MedDRA `10008874` (`exactMatch`) and Read v2 codes (`Eu46000`, `F286.00`, each from the ConceptMap that lists it). Mappings to ICD-10-CM or ICD-10-GM do not exist there.
- **Children:** Ontoserver's ICD-10-GM and OPS records expose only `parent`; SNOMED CT, ICD-10-CM and ATC expose `parent` and `child` on both servers, HPO (Ontoserver only) too. Parent/child names (`related_name`) are returned by tx.fhir.org only; Ontoserver edges fall back to the code.
- **Latency:** `$lookup` 0.4 s on tx.fhir.org, 0.9 s on Ontoserver (first call up to 3.7 s); `$expand` 0.4-3 s; 4-13 KB per lookup. The adapter spaces requests at 2 per second.
- **Capabilities:** `metadata?_summary=true` lists resource types only (4 KB on tx.fhir.org); the code system list is in `metadata?mode=terminology` (307 KB on tx.fhir.org, 889 KB on Ontoserver), which the adapter does not fetch. `list_code_systems(title=...)` uses `CodeSystem?title=...` instead; SNOMED CT and LOINC are built in and do not appear in that listing although `$lookup` works.

## Licence and usage

tx.fhir.org and the CSIRO sandbox are public services. The content they return is not free of conditions: **SNOMED CT** is licensed by SNOMED International and national release centres, **LOINC** by Regenstrief (free with a licence acceptance), **ICD-11** by WHO, and **ICD-10-GM / OPS** by BfArM. Using these code systems beyond what your own licence covers (for example SNOMED CT outside a member country or in a product) is your responsibility; the server operators note the same in their `ValueSet.copyright`. Do not hammer the public servers: the adapter waits 0.5 s between requests, and no bulk crawl is offered.

## Caveats

- Without a configured server list, `search_concepts` queries SNOMED CT, ICD-10-CM and LOINC; a system the server does not host costs one failed request (two for the implicit-then-inline attempt) and is skipped.
- The `filter` text is matched by the server (tokens and prefixes over display text and designations), so German servers need German terms (`Müdigkeit`), not `fatigue`.
- The ICD-10-GM and HPO versions on the Ontoserver sandbox are old (2020); a production MII server will carry current editions.
- Pinned versions are exact strings as the server lists them (`2020`, `2025.0.0`, a SNOMED version URI).
- `ConceptMap/$translate` is only as good as the maps the server has loaded.

## Live verification (2026-10-09)

`knowledge-lookup check FHIRTERMINOLOGY` passes against tx.fhir.org: search, details and relationships for `fatigue` (SNOMED CT 84229001 with its 2 parents and its children). A full pass over both servers exercised search with each alias, details for LOINC / SNOMED / ICD-10-GM / HPO / ATC, relationships, mappings, `$validate-code` (valid and invalid), `list_code_systems` and capabilities. Fixtures in `tests/fixtures/fhirterminology_responses.py` are trimmed copies of those responses.

## See also

- [LOINC adapter](loinc_adapter.md), [ICD-10-GM adapter](icd10gm_adapter.md), [SNOMED CT adapter](snomedct_adapter.md), [ICD-11 adapter](icd11_adapter.md): system-specific adapters for the same code systems
- [All adapters](../README.md)
