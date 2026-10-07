---
description: LOINC laboratory and clinical observation codes through the Regenstrief FHIR R4 terminology server, with the six LOINC axes as typed relationships.
---

# LOINC adapter

Searches LOINC term names and looks up codes such as `2093-3` (Cholesterol [Mass/volume] in Serum or Plasma) or `718-7` (Hemoglobin [Mass/volume] in Blood) on the LOINC FHIR R4 terminology server. Useful for mapping registry laboratory variables to a standard code.

> **Not live-verified.** The server needs a free loinc.org login and none was used. The adapter follows the FHIR R4 `$lookup` / `$expand` specification and LOINC's public FHIR documentation, parses responses defensively, and is tested with mocked responses only. An unauthenticated browser request to `https://fhir.loinc.org/metadata` currently answers with an HTML login page (Authelia); the adapter treats an HTML answer like a rejected login and logs a hint.

| | |
|---|---|
| Source | `KnowledgeSource.LOINC` |
| Class | `knowledge_lookup.adapters.LoincAdapter` |
| Requires | `LOINC_USERNAME` and `LOINC_PASSWORD` (free account at <https://loinc.org>; also read from `config.get_api_key("loinc_username")` / `("loinc_password")`) |
| Identifiers | LOINC codes `2093-3`, `LOINC:2093-3` (LP part codes such as `LP15099-2` are accepted by `$lookup`) |
| Upstream API | `https://fhir.loinc.org` (HTTP Basic auth) |

`is_available()` is true only when both credentials are set.

## Required LOINC notice

LOINC is free to use under the [LOINC licence](https://loinc.org/license/), which requires the copyright notice to accompany any product, service or publication that includes LOINC content. Show this (or the current wording from the licence page) wherever LOINC codes or names from this adapter appear:

> This material contains content from LOINC (http://loinc.org). LOINC is copyright © 1995-*year*, Regenstrief Institute, Inc. and the Logical Observation Identifiers Names and Codes (LOINC) Committee and is available at no cost under the license at http://loinc.org/license. LOINC® is a registered United States trademark of Regenstrief Institute, Inc.

The adapter exposes the text as `knowledge_lookup.adapters.loinc_adapter.LOINC_COPYRIGHT_NOTICE` and stores it under `source_data["LOINC"]["copyright"]` of every concept. Accounts are personal: keep credentials out of source control (`.env` is git-ignored) and do not share them.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import LoincAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    # export LOINC_USERNAME=... LOINC_PASSWORD=...
    async with LoincAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("cholesterol", limit=3):
            print(concept.primary_id, concept.primary_label)

        term = await adapter.get_concept_details("2093-3")
        print(term.primary_label, term.synonyms)
        for edge in await adapter.get_relationships("2093-3"):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

## What each method returns

- **`search_concepts(query, limit)`** requests `ValueSet/$expand?url=http://loinc.org/vs&filter=<query>&count=<limit>` and reads `expansion.contains[]` (`system`, `code`, `display`; nested entries are flattened). Concepts are `OBSERVATION` typed with `confidence_score` 0.8 and only a label; use details for the rest. A query that is itself a LOINC code is resolved with `$lookup` instead.
- **`get_concept_details(code)`** requests `CodeSystem/$lookup?system=http://loinc.org&code=<code>` with `property=` for COMPONENT, PROPERTY, TIME_ASPCT, SYSTEM, SCALE_TYP, METHOD_TYP, CLASS, STATUS and DefinitionDescription, and parses the `Parameters` resource: the LONG_COMMON_NAME designation (else `display`) is the label; other designations and the display name become `synonyms`; `DefinitionDescription` becomes the definition; `categories` hold `class:<CLASS>` and `semantic_types` `specimen:<SYSTEM>`. All property values, designations and the server's code system `version` are kept in `source_data["LOINC"]`.
- **`get_relationships(code)`** turns the axis parts into typed edges: `has_component`, `has_property`, `has_time_aspect`, `has_system`, `has_scale`, `has_method`, `has_class`. `related_id` is the LP part code when the server returns a Coding, otherwise the plain value. `parent` / `child` properties, when present, become `is_a` / `has_subtype`. The `$lookup` result is cached per adapter so details plus relationships cost one request.
- **`get_mappings`** is not implemented.

## Errors and limits

A `401`/`403` is logged with a hint to check the credentials (never the credentials themselves) and returns `[]` / `None`; so does a server error, an `OperationOutcome` (unknown code) or an HTML login page. The shared retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)).

## Caveats

- The exact property names and value types returned by `fhir.loinc.org` (Coding versus string, designation `use` coding) could not be confirmed without an account; the parser accepts any `value[x]` type and both a designation `use` code of `LONG_COMMON_NAME` and a plain `display`. Please run `knowledge-lookup check LOINC` with your credentials once and report differences.
- Multi-axial hierarchy (`parent` / `child`) and answer lists are only exposed if the server returns them as properties.
- Search uses the server's text `filter`, so ranking and matching are the server's.

## See also

- [SNOMED CT adapter](snomedct_adapter.md), [ICD-11 adapter](icd11_adapter.md)
- [All adapters](../README.md)
