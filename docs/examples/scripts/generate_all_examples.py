#!/usr/bin/env python3
"""Generate the per-source example scripts in ``docs/examples/<category>/<source>/``.

Usage, from the repository root::

    python docs/examples/scripts/generate_all_examples.py

Every knowledge source is described once in :data:`SOURCES`: its category, a
query that returns results, an optional identifier for ``get_concept_details``
(only identifiers verified to resolve with that adapter), and what it needs to
run. Sources in :data:`HANDWRITTEN` have a hand-maintained example that the
generator never overwrites.

Each generated script is compiled before it is written, so a template mistake
fails here instead of producing a script that does not parse.

``generate_status.py`` imports :data:`SOURCES` to run the examples and write
``availability-status.md``.
"""

from __future__ import annotations

import json
import string
from pathlib import Path
from typing import NamedTuple

EXAMPLES_DIR = Path(__file__).resolve().parents[1]


class Source(NamedTuple):
    name: str
    """``KnowledgeSource`` member name, e.g. ``"OLS"``."""
    category: str
    title: str
    description: str
    query: str
    concept_id: str | None = None
    """Identifier passed to ``get_concept_details``; ``None`` skips that step."""
    requires: str | None = None
    """API key or optional extra the adapter needs, ``None`` for public sources."""
    usage: str | None = None
    """Extra usage hint written into the script's docstring."""
    issue: str | None = None
    """Known limitation, shown on the availability status page only."""

    @property
    def slug(self) -> str:
        return self.name.lower()

    @property
    def script(self) -> Path:
        return EXAMPLES_DIR / self.category / self.slug / f"{self.slug}_example.py"

    @property
    def output(self) -> Path:
        return self.script.with_name(f"{self.slug}_example_output.txt")


BIOPORTAL_KEY = "the BIOPORTAL_API_KEY environment variable"

SOURCES: tuple[Source, ...] = (
    # --- core ---------------------------------------------------------------
    Source(
        "CHEMBL",
        "core",
        "ChEMBL",
        "ChEMBL bioactive molecules, drugs and targets.",
        "aspirin",
        "CHEMBL25",
        requires="the [chembl] extra",
        issue="Multi-word and target searches (e.g. EGFR) can exceed the 30-second "
        "per-source timeout and return nothing; molecule names and ChEMBL IDs are fast.",
    ),
    Source(
        "DISGENET",
        "core",
        "DisGeNET",
        "DisGeNET gene-disease associations.",
        "asthma",
        requires="the DISGENET_API_KEY environment variable",
        usage="Queries can be a disease name, a gene symbol (CDK2) or an NCBI gene ID (1017).",
        issue="Academic DisGeNET accounts only see curated sources; searches can return "
        "no associations.",
    ),
    Source(
        "MONDO",
        "core",
        "Mondo",
        "Mondo Disease Ontology.",
        "diabetes",
        "MONDO:0005148",
    ),
    Source(
        "OLS",
        "core",
        "OLS",
        "EBI Ontology Lookup Service: 250+ ontologies (DOID, EFO, NCIT, UBERON, CHEBI, ...).",
        "cancer",
        "http://purl.obolibrary.org/obo/DOID_162",
        usage="get_concept_details expects the full term IRI.",
    ),
    Source(
        "OPENTARGETS",
        "core",
        "Open Targets",
        "Open Targets Platform targets, diseases and drugs.",
        "BRCA1",
        "ENSG00000012048",
        usage="get_concept_details takes an Ensembl gene ID.",
    ),
    Source(
        "UMLS",
        "core",
        "UMLS",
        "UMLS Metathesaurus: search with source and semantic-type filters, bulk search, "
        "mappings, relationships and streaming iterators.",
        "diabetes",
        "C0011849",
        requires="the [umls] extra and the UMLS_API_KEY environment variable",
    ),
    # --- chemicals ----------------------------------------------------------
    Source(
        "DRUGBANK",
        "chemicals",
        "DrugBank",
        "DrugBank drugs, looked up through MyChem.info.",
        "aspirin",
        issue="MyChem.info returns names, synonyms and identifiers only (no descriptions); "
        "its DrugBank data is licensed CC BY-NC 4.0.",
    ),
    Source(
        "PUBCHEM",
        "chemicals",
        "PubChem",
        "PubChem compounds (CIDs).",
        "aspirin",
        "2244",
    ),
    Source(
        "UNICHEM",
        "chemicals",
        "UniChem",
        "UniChem chemical cross-references.",
        "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        "161671",
        requires="the [bioservices] extra",
        usage="Search by InChIKey; get_concept_details takes a UniChem compound ID (UCI).",
    ),
    # --- phenotypes ---------------------------------------------------------
    Source(
        "CLINVAR",
        "phenotypes",
        "ClinVar",
        "ClinVar variants and their clinical significance.",
        "BRCA1",
        "17661",
        usage="get_concept_details takes a ClinVar variation ID.",
    ),
    Source(
        "GENEONTOLOGY",
        "phenotypes",
        "Gene Ontology",
        "Gene Ontology terms.",
        "apoptosis",
        "GO:0006915",
    ),
    Source(
        "HPO",
        "phenotypes",
        "HPO",
        "Human Phenotype Ontology.",
        "seizure",
        "HP:0001250",
    ),
    Source(
        "OMIM",
        "phenotypes",
        "OMIM",
        "OMIM Mendelian disorders and genes.",
        "cystic fibrosis",
        "219700",
        requires="the OMIM_API_KEY environment variable",
    ),
    Source(
        "QUICKGO",
        "phenotypes",
        "QuickGO",
        "EBI QuickGO Gene Ontology terms and annotations.",
        "apoptosis",
        "GO:0006915",
        requires="the [bioservices] extra",
    ),
    # --- proteins -----------------------------------------------------------
    Source(
        "ENSEMBL",
        "proteins",
        "Ensembl",
        "Ensembl human genes, searched by gene symbol.",
        "TP53",
        "ENSG00000141510",
        issue="The symbol search is slow (often 30 seconds or more) and sometimes returns "
        "nothing; get_concept_details is fast.",
    ),
    Source(
        "HGNC",
        "proteins",
        "HGNC",
        "HGNC human gene nomenclature.",
        "BRCA1",
        "HGNC:1100",
    ),
    Source(
        "UNIPROT",
        "proteins",
        "UniProt",
        "UniProtKB proteins.",
        "insulin",
        "P01308",
    ),
    # --- pathways -----------------------------------------------------------
    Source(
        "KEGG",
        "pathways",
        "KEGG",
        "KEGG diseases and drugs.",
        "diabetes",
        "H00409",
    ),
    Source(
        "REACTOME",
        "pathways",
        "Reactome",
        "Reactome pathways and reactions.",
        "apoptosis",
        "R-HSA-109581",
    ),
    # --- ontologies ---------------------------------------------------------
    Source(
        "BIOONTOLOGY",
        "ontologies",
        "BioOntology",
        "NCBO BioOntology search API.",
        "melanoma",
        requires=BIOPORTAL_KEY,
    ),
    Source(
        "BIOPORTAL",
        "ontologies",
        "BioPortal",
        "NCBO BioPortal: 1000+ ontologies (SNOMED CT, MeSH, ICD, ...).",
        "melanoma",
        requires=BIOPORTAL_KEY,
    ),
    Source(
        "EBIOLS",
        "ontologies",
        "EBI OLS",
        "EMBL-EBI OLS (a variant of the OLS adapter).",
        "cancer",
        "http://purl.obolibrary.org/obo/MONDO_0004992",
        usage="get_concept_details expects the full term IRI.",
    ),
    Source(
        "OBOFOUNDRY",
        "ontologies",
        "OBO Foundry",
        "OBO Foundry ontologies.",
        "cancer",
    ),
    Source(
        "ZOOMA",
        "ontologies",
        "ZOOMA",
        "EBI ZOOMA text-to-ontology annotation.",
        "breast cancer",
    ),
    # --- families -----------------------------------------------------------
    Source(
        "INTERPRO",
        "families",
        "InterPro",
        "InterPro protein families and domains.",
        "kinase",
        "IPR000719",
    ),
    Source(
        "PDB",
        "families",
        "PDB",
        "RCSB Protein Data Bank structures.",
        "hemoglobin",
        "4HHB",
    ),
    Source(
        "PFAM",
        "families",
        "Pfam",
        "Pfam protein families.",
        "kinase",
        "PF00069",
    ),
    Source(
        "STRING",
        "families",
        "STRING",
        "STRING protein-protein interaction network proteins.",
        "TP53",
    ),
    # --- literature ---------------------------------------------------------
    Source(
        "EUROPEPMC",
        "literature",
        "Europe PMC",
        "Europe PMC literature search.",
        "CRISPR",
        "33203879",
        usage="get_concept_details takes a bare PubMed ID.",
    ),
    Source(
        "EUTILS",
        "literature",
        "NCBI E-utilities",
        "NCBI E-utilities (PubMed, Gene, Protein).",
        "BRCA1",
        "GeneID:672",
        requires="the [bioservices] extra",
    ),
    # --- other --------------------------------------------------------------
    Source(
        "BIOLINKER",
        "other",
        "BioLinker",
        "BioLinker entity linking.",
        "cancer",
    ),
    Source(
        "COSMIC",
        "other",
        "COSMIC",
        "COSMIC somatic cancer mutations. COSMIC has no public query API.",
        "BRAF",
        requires="COSMIC account credentials in the COSMIC_API_KEY environment variable",
        issue="COSMIC offers no query API (only credential-gated file downloads); the REST "
        "endpoint answers 404 even with credentials, so no results are returned.",
    ),
    Source(
        "DBPEDIA",
        "other",
        "DBpedia",
        "DBpedia resources (general knowledge).",
        "aspirin",
        "Aspirin",
    ),
    Source(
        "OXO",
        "other",
        "OxO",
        "EBI OxO ontology cross-reference mappings.",
        "MONDO:0005148",
        "MONDO:0005148",
        usage="Search with a CURIE; the concept's mappings list its cross-references.",
    ),
    Source(
        "TYTO",
        "other",
        "Tyto",
        "Tyto term lookup in the SO, SBO and NCIT ontologies.",
        "promoter",
        "http://purl.obolibrary.org/obo/SO_0000167",
        requires="the [tyto] extra",
        usage="Search is an exact-label lookup; get_concept_details takes a term IRI.",
        issue="Search matches exact labels only; a label that is ambiguous within an "
        "ontology is skipped, and tyto logs an error for it.",
    ),
    Source(
        "WIKIDATA",
        "other",
        "Wikidata",
        "Wikidata items.",
        "aspirin",
        "Q18216",
    ),
)

HANDWRITTEN = frozenset({"UMLS"})

TEMPLATE = string.Template(
    r'''"""
${title} example: search${details_title}.

${description}${usage}

Requirements: ${requirements}.

Run from the repository root:

    python docs/examples/${category}/${slug}/${slug}_example.py

Generated by docs/examples/scripts/generate_all_examples.py; edit the generator, not this file.
"""

import asyncio
import logging
import textwrap

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup

SOURCE = KnowledgeSource.${name}
QUERY = ${query}
${concept_id_line}

async def main() -> None:
    lookup = create_knowledge_lookup(enabled_sources=[SOURCE])
    try:
        # The factory always returns a lookup object. An adapter that lacks its API
        # key or optional extra is simply not registered in lookup.adapters.
        if SOURCE not in lookup.adapters:
            print(f"SKIPPED: the {SOURCE.value} adapter is not available.")
            print("It needs ${needs}.")
            print("\nSummary: skipped")
            return
        print(f"The {SOURCE.value} adapter is available.")

        print(f"\nSearching {SOURCE.value} for {QUERY!r} ...")
        result = await lookup.search_concepts(QUERY, sources=[SOURCE], max_results=5)
        print(f"Found {result.total_found} concept(s) in {result.execution_time:.1f}s")
        for source, message in result.errors.items():
            print(f"  Error from {source}: {message}")
        for number, concept in enumerate(result.concepts, start=1):
            print(f"\n  {number}. {concept.primary_label}")
            print(f"     ID:         {concept.primary_id}")
            print(f"     Type:       {concept.concept_type}")
            print(f"     Confidence: {concept.confidence_score}")
            for definition in concept.definitions[:1]:
                print(f"     Definition: {textwrap.shorten(definition, 100)}")
            for mapping in concept.mappings[:3]:
                target = mapping.to_concept
                print(f"     Mapping:    {target.identifier} ({target.source})")
        if not result.concepts:
            print("  No results. The service may be down or its API may have changed.")
${details_block}${details_summary}
    finally:
        await lookup.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main())
    except Exception as exc:  # show a readable message instead of a traceback
        raise SystemExit(f"ERROR: {type(exc).__name__}: {exc}") from None
'''
)

DETAILS_BLOCK = r"""
        print(f"\nFetching details for {CONCEPT_ID!r} ...")
        details = await lookup.get_concept_details(CONCEPT_ID, source=SOURCE)
        if details is None:
            print("  Not found, or the service did not answer.")
        else:
            print(f"  Label:      {details.primary_label}")
            print(f"  ID:         {details.primary_id}")
            print(f"  Type:       {details.concept_type}")
            if details.synonyms:
                print(f"  Synonyms:   {', '.join(map(str, details.synonyms[:5]))}")
            for definition in details.definitions[:1]:
                print(f"  Definition: {textwrap.shorten(definition, 200)}")
            for identifier in details.identifiers[:3]:
                print(f"  Identifier: {identifier.identifier} ({identifier.source})")
"""


SUMMARY_WITH_DETAILS = r"""
        found = "found" if details else "not found"
        print(f"\nSummary: search={result.total_found} details={found}")"""

SUMMARY_SEARCH_ONLY = r"""
        print(f"\nSummary: search={result.total_found}")"""


def python_string(value: str) -> str:
    """A double-quoted Python literal (json.dumps output is valid Python for str)."""
    return json.dumps(value, ensure_ascii=False)


def render(source: Source) -> str:
    """Return the example script for *source*."""
    has_details = source.concept_id is not None
    concept_id_line = f"CONCEPT_ID = {python_string(source.concept_id)}\n" if has_details else ""
    return TEMPLATE.substitute(
        title=source.title,
        details_title=" and concept details" if has_details else "",
        description=source.description,
        usage=f"\n\n{source.usage}" if source.usage else "",
        requirements=source.requires or "none, this is a public API",
        category=source.category,
        slug=source.slug,
        name=source.name,
        query=python_string(source.query),
        concept_id_line=concept_id_line,
        needs=source.requires or "no API key or extra; check your installation",
        details_block=DETAILS_BLOCK if has_details else "",
        details_summary=SUMMARY_WITH_DETAILS if has_details else SUMMARY_SEARCH_ONLY,
    )


def main() -> None:
    written = 0
    for source in SOURCES:
        if source.name in HANDWRITTEN:
            print(f"kept      {source.script.relative_to(EXAMPLES_DIR)} (hand-written)")
            continue
        code = render(source)
        compile(code, str(source.script), "exec")  # fail loudly on a template error
        source.script.parent.mkdir(parents=True, exist_ok=True)
        source.script.write_text(code, encoding="utf-8")
        written += 1
        print(f"generated {source.script.relative_to(EXAMPLES_DIR)}")
    print(f"\n{written} example scripts written to {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
