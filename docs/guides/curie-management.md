---
description: Parse, validate and normalize CURIEs and URIs with Bioregistry, and convert identifiers to curies references.
---

# CURIE management

`knowledge_lookup.curie_utils` wraps [Bioregistry](https://bioregistry.io/) and the [curies](https://github.com/biopragmatics/curies) library to work with compact identifiers:

* a **CURIE** is a prefixed identifier such as `DOID:9351`
* a **URI** is the full form, such as `http://purl.obolibrary.org/obo/DOID_9351`

These utilities need the `curie` extra:

```bash
pip install "biomedical-knowledge-lookup[curie]"
```

Without it, the functions degrade instead of raising: parsing and normalization return `None`, validation returns `False` and `get_prefix_mapping()` returns `{}`.

## Quick tour

{% code title="curies_demo.py" %}
```python
from knowledge_lookup.curie_utils import (
    get_converter,
    get_prefix_mapping,
    normalize_curie,
    normalize_identifier,
    parse_curie_or_uri,
    validate_curie_pattern,
    validate_prefix,
)

# Parse a CURIE or a URI into (prefix, local identifier)
print(parse_curie_or_uri("DOID:9351"))                                 # ('doid', '9351')
print(parse_curie_or_uri("http://purl.obolibrary.org/obo/DOID_9351"))  # ('doid', '9351')
print(parse_curie_or_uri("not-a-valid-identifier"))                    # None

# Is the prefix (or one of its synonyms) registered? Case-insensitive.
print(validate_prefix("DOID"), validate_prefix("invalid_prefix"))      # True False

# Does the local identifier match the prefix's regular expression?
print(validate_curie_pattern("doid", "9351"))                          # True
print(validate_curie_pattern("doid", "invalid!"))                      # False

# Standardize to Bioregistry's canonical (lower-case) prefix
print(normalize_curie("DOID:9351"))       # doid:9351
print(normalize_curie("NOT-A-PREFIX:1"))  # NOT-A-PREFIX:1 (unregistered: returned unchanged)
print(normalize_identifier("go", "0008150"))  # 0008150

# Prefix synonyms map to canonical prefixes
print(get_prefix_mapping()["DOID"])  # doid

# Expand and compress with the shared curies Converter
converter = get_converter()
print(converter.expand("DOID:9351"))                                  # http://purl.obolibrary.org/obo/DOID_9351
print(converter.compress("http://purl.obolibrary.org/obo/DOID_9351"))  # doid:9351
```
{% endcode %}

{% hint style="info" %}
`normalize_curie()` only standardizes the prefix. It does not map an identifier to a different vocabulary (for example DOID to MONDO). For cross-vocabulary mappings use `CentralKnowledgeLookup.find_mappings()`; see [Searching concepts](searching-concepts.md).
{% endhint %}

## Function reference

All functions are importable from `knowledge_lookup.curie_utils`.

| Function | Returns | Notes |
| --- | --- | --- |
| `parse_curie_or_uri(identifier)` | `(prefix, identifier)` or `None` | Prefix is the canonical Bioregistry prefix |
| `validate_prefix(prefix)` | `bool` | Accepts synonyms, case-insensitive |
| `validate_curie_pattern(prefix, identifier)` | `bool` | `False` if the prefix has no pattern |
| `normalize_curie(curie)` | `str` or `None` | Canonical CURIE; unregistered prefixes returned unchanged |
| `normalize_identifier(prefix, identifier)` | `str` or `None` | Canonical local identifier as defined by Bioregistry |
| `get_prefix_mapping()` | `dict[str, str]` | Every registered prefix and synonym (several thousand) to its canonical prefix; values are prefixes, not URIs |
| `get_converter()` / `get_bioregistry_converter()` | `curies.Converter` or `None` | Use `.expand()`, `.compress()`, `.prefix_map` for URIs |
| `create_local_converter(prefix_map)` | `curies.Converter` | Build a converter from `{"doid": "http://purl.obolibrary.org/obo/DOID_"}`-style URI prefixes |
| `get_source_prefix_mapping()` | `dict[str, str]` | `KnowledgeSource` value to Bioregistry prefix, e.g. `"HPO"` to `"hp"`; falls back to the lower-cased source name |
| `concept_identifier_to_reference(dict)` | `curies.Reference` or `None` | For plain `{"source": ..., "identifier": ...}` dicts |
| `reference_to_concept_identifier(reference)` | `dict` | `source` upper-cased, `label` and `url` unset |

## Convert `ConceptIdentifier` objects

`ConceptIdentifier`, the identifier model attached to every `UnifiedConcept`, converts to and from `curies.Reference`:

```python
from knowledge_lookup import ConceptIdentifier, KnowledgeSource

identifier = ConceptIdentifier(
    source=KnowledgeSource.MONDO,
    identifier="0005015",
    label="diabetes mellitus",
)

reference = identifier.to_curies_reference()  # Reference(prefix='mondo', identifier='0005015')
print(str(identifier))                         # mondo:0005015
print(ConceptIdentifier.from_curies_reference(reference))
# source='MONDO' identifier='0005015' label=None url=None
```

The prefix is the lower-cased source name, which is not always the Bioregistry prefix for that vocabulary (the HPO source, for instance, uses the `hp` prefix in Bioregistry). `to_curies_reference()` returns `None` when `curies` is not installed.

## How the rest of the library uses CURIEs

* `CentralKnowledgeLookup` builds a source-to-prefix map with `get_source_prefix_mapping()` at start-up, but it does not parse queries as CURIEs, normalize result identifiers or de-duplicate by CURIE. `search_concepts("DOID:9351")` sends the literal string to each source.
* Identifiers keep each source's native form (`MONDO_0005148` from a MONDO search, `HP:0001250` from HPO). Normalize them yourself if you need a uniform format.
* The [MCP server](mcp-server.md) uses Bioregistry offline in `biomed_validate_curie` and routes identifiers to adapters by prefix.

To handle CURIE input yourself, validate it before looking it up:

```python
from knowledge_lookup import KnowledgeSource
from knowledge_lookup.curie_utils import parse_curie_or_uri, validate_curie_pattern

parsed = parse_curie_or_uri("HP:0001250")
if parsed and validate_curie_pattern(*parsed):
    concept = await lookup.get_concept_details("HP:0001250", source=KnowledgeSource.HPO)
```

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Every function returns `None`, `False` or `{}` | The `curie` extra is not installed |
| `normalize_curie()` returns the input unchanged | The prefix is not registered in Bioregistry |
| `parse_curie_or_uri()` returns `None` | The string is neither a CURIE with a known prefix nor a URI with a known URI prefix |

## Next steps

* [Searching concepts](searching-concepts.md): resolving and mapping identifiers
* [Bioregistry](https://bioregistry.io/) and [curies documentation](https://curies.readthedocs.io/)
