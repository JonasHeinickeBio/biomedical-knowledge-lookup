---
description: Short definitions of the biomedical identifiers, vocabularies and library terms used in these docs.
---

# Glossary

## Identifiers

| Term | Meaning | Example |
|---|---|---|
| **CURIE** | compact URI: `prefix:local-id`. The library accepts and returns CURIEs wherever it can; see [CURIE management](../guides/curie-management.md) | `HP:0001250` |
| **CUI** | UMLS Concept Unique Identifier, shared by synonymous terms across vocabularies | `C0015674` |
| **IRI / URI** | the full web identifier a CURIE abbreviates | `http://purl.obolibrary.org/obo/HP_0001250` |
| **Accession** | an identifier issued by a database | `GSE327255`, `PXD076216`, `P38398` |
| **Cross-reference (xref)** | a statement that two identifiers in different vocabularies denote the same or a similar thing. `get_mappings()` returns these | MONDO:0005148 and DOID:9352 |
| **rsID** | dbSNP identifier of a variant | `rs1801133` |
| **DOI / PMID / PMCID** | identifiers of a paper: publisher DOI, PubMed ID, PubMed Central ID | `10.1038/s41586-020-2012-7` |

## Vocabularies

| Term | What it is |
|---|---|
| **Ontology** | a controlled vocabulary with defined relations between terms (MONDO, HPO, GO, Cell Ontology) |
| **Terminology / code system** | a coding standard used in records and registries (ICD-10-GM, ICD-11, SNOMED CT, LOINC, ATC) |
| **MONDO, DOID** | disease ontologies; MONDO merges many disease vocabularies |
| **HPO** | Human Phenotype Ontology: symptoms and signs. *HPO annotations* (`phenotype.hpoa`) link diseases to those phenotypes with frequencies |
| **MeSH** | NLM Medical Subject Headings, used to index PubMed |
| **ICD-10-GM** | German modification of ICD-10, used for registry coding in Germany |
| **SNOMED CT** | clinical terminology of fine-grained concepts and relations; licence applies |
| **LOINC** | codes for laboratory tests and clinical observations |
| **ATC** | WHO Anatomical Therapeutic Chemical drug classification; reached through RxClass |
| **RxNorm** | normalised names for clinical drugs |
| **UMLS** | NLM Unified Medical Language System: a metathesaurus that links many vocabularies by CUI |
| **FHIR terminology server** | an HL7 FHIR service that serves code systems through `$lookup` and `$expand` |
| **RefMet** | standardised metabolite names used by Metabolomics Workbench |

## Library terms

| Term | Meaning |
|---|---|
| **Adapter** | the class that talks to one source and returns `UnifiedConcept` objects; see [Adapters](../adapters/README.md) |
| **Source** | a member of `KnowledgeSource`; each has one adapter |
| **`UnifiedConcept`** | the common result model: id, label, type, synonyms, definitions, identifiers, relations and the raw `source_data` |
| **Relationship** | a typed edge from `get_relationships()`, a dict with `relation_label`, `related_id`, `related_name`, `source` |
| **Mapping** | a cross-reference from `get_mappings()`, a dict with `fromId`, `toId`, `fromSource`, `toSource` |
| **Opt-in dataset** | a source backed by a downloadable file; unavailable until you set `<NAME>_DOWNLOAD=1` or give a path |
| **Circuit breaker** | per-source guard that skips a source after repeated failures; see [Configuration](../getting-started/configuration.md) |
| **MCP** | Model Context Protocol, the interface through which AI assistants call tools; see [MCP server](../guides/mcp-server.md) |
