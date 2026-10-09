"""Shared grouping of the knowledge sources into reader-facing domains.

Used by ``build_source_index.py`` (README, docs landing page, adapter index and
SUMMARY) and ``build_data_coverage_doc.py``. Every adapter must appear in exactly
one group; ``build_source_index.py`` fails otherwise, so a new source cannot be
forgotten. The doc pages stay in their historical ``docs/adapters/<dir>/``
folders (moving them would break inbound links); the groups only drive navigation.
"""

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DOCS = ROOT / "docs" / "adapters"

# (key, title, one-line blurb, source names in display order)
TAXONOMY: list[tuple[str, str, str, list[str]]] = [
    (
        "ontology-services",
        "Ontology services and mappings",
        "Search hundreds of ontologies at once and translate identifiers between them.",
        "OLS EBIOLS BIOPORTAL BIOONTOLOGY OBOFOUNDRY ZOOMA OXO NODENORM UMLS TYTO BIOLINKER",
    ),
    (
        "terminologies",
        "Clinical terminologies and coding",
        "The code systems used in registries and health records.",
        "MESH SNOMEDCT ICD11 ICD10GM LOINC NCIEVS CLINICALTABLES FHIRTERMINOLOGY NCBITAXONOMY",
    ),
    (
        "diseases",
        "Diseases and phenotypes",
        "Disease ontologies, phenotype annotations and gene-disease evidence.",
        "MONDO DOID HPO HPOA ORPHANET OMIM MEDGEN MONARCH MEDLINEPLUS GENCC CLINGEN PANELAPP "
        "DISGENET OPENTARGETS GWASCATALOG",
    ),
    (
        "genes",
        "Genes, variants and expression",
        "Gene records, variants, population frequencies and tissue expression.",
        "HGNC NCBIGENE MYGENEINFO ENSEMBL CLINVAR DBSNP GNOMAD COSMIC GTEX HUMANPROTEINATLAS "
        "EQTLCATALOGUE GENEONTOLOGY QUICKGO IMPC ALLIANCE",
    ),
    (
        "proteins",
        "Proteins, structures and interactions",
        "Protein records, predicted and solved structures, families and interaction networks.",
        "UNIPROT ALPHAFOLD PDB INTERPRO PFAM STRING INTACT",
    ),
    (
        "drugs",
        "Drugs and pharmacology",
        "Drug names and classes, targets, labels, adverse events and toxicogenomics.",
        "DRUGBANK RXNORM RXCLASS CHEMBL DGIDB CLINPGX OPENFDALABELS OPENFDAEVENTS SIDER OFFSIDES CTD",
    ),
    (
        "chemistry",
        "Chemicals and metabolites",
        "Small molecules, lipids, reactions and metabolomics studies.",
        "PUBCHEM CHEBI UNICHEM LIPIDMAPS RHEA METABOLOMICSWORKBENCH METABOLIGHTS",
    ),
    (
        "pathways",
        "Pathways and enrichment",
        "Curated pathways and gene-set enrichment.",
        "REACTOME KEGG WIKIPATHWAYS ENRICHR",
    ),
    (
        "immunology",
        "Immunology and cell types",
        "Cell types, marker genes, single-cell datasets and epitopes.",
        "CELLONTOLOGY CELLMARKER CELLXGENE IEDB",
    ),
    (
        "literature",
        "Literature and citations",
        "Papers, preprints, citation links, text-mined entities and open-access status.",
        "EUROPEPMC EUTILS PUBTATOR LITCOVID OPENALEX SEMANTICSCHOLAR SEMMEDDB CROSSREF BIORXIV "
        "OPENCITATIONS UNPAYWALL DOAJ OPENAIRE",
    ),
    (
        "studies",
        "Trials, grants and datasets",
        "Clinical-trial registries, funded projects and public omics datasets.",
        "CLINICALTRIALS ISRCTN NIHREPORTER GEO OMICSDI BIOSTUDIES PRIDE ZENODO",
    ),
    (
        "general",
        "General knowledge",
        "Broad knowledge graphs for names and facts that specialist sources lack.",
        "WIKIDATA DBPEDIA",
    ),
]


@dataclass
class SourceMeta:
    name: str  # enum member name
    title: str  # display name (docs page H1 minus " adapter")
    path: str  # docs path relative to docs/, e.g. adapters/core/mondo_adapter.md
    description: str
    requires: str
    identifiers: str
    group: str

    @property
    def short_description(self) -> str:
        return shorten(self.description, 120)

    @property
    def access(self) -> str:
        """Short access label for compact tables."""
        r = self.requires.lower()
        if "opt-in" in r or "_download" in r:
            return "Opt-in download"
        if re.search(r"api_key|client_id|username|e-mail|email", r):
            return "Key or login"
        if re.search(r"file|database|_path", r):
            return "Local file"
        if "extra" in r or r.startswith("`["):
            return "Extra"
        return "Open"


def shorten(text: str, n: int) -> str:
    text = " ".join(text.split())
    first = re.split(r"(?<=[a-z0-9\)])\. ", text)[0].rstrip(".")
    if len(first) <= n:
        return first
    cut = first[: n - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:( ") + "…"


def _info_row(lines: list[str], label_re: str) -> str:
    for line in lines:
        m = re.match(rf"\|\s*({label_re})\s*\|\s*(.*?)\s*\|\s*$", line)
        if m:
            return m.group(2)
    return ""


def load_sources() -> list[SourceMeta]:
    from knowledge_lookup import KnowledgeSource
    from knowledge_lookup.adapters import _ADAPTER_SPECS

    names = {s.name for s in KnowledgeSource if s in _ADAPTER_SPECS}
    seen: dict[str, str] = {}
    for key, _title, _blurb, members in TAXONOMY:
        for n in members.split():
            if n in seen:
                raise SystemExit(f"{n} is in two groups: {seen[n]} and {key}")
            seen[n] = key
    missing, extra = names - set(seen), set(seen) - names
    if missing or extra:
        raise SystemExit(f"taxonomy mismatch: missing={sorted(missing)} unknown={sorted(extra)}")

    out: list[SourceMeta] = []
    for key, _title, _blurb, members in TAXONOMY:
        for n in members.split():
            module = _ADAPTER_SPECS[KnowledgeSource[n]][0]
            page = next(ADAPTER_DOCS.glob(f"*/{module}.md"))
            text = page.read_text(encoding="utf-8")
            lines = text.splitlines()
            desc = re.search(r"^description:\s*(.+)$", text, re.M)
            h1 = re.search(r"^# (.+)$", text, re.M)
            out.append(
                SourceMeta(
                    name=n,
                    title=(h1.group(1) if h1 else n).removesuffix(" adapter").strip(),
                    path=page.relative_to(ROOT / "docs").as_posix(),
                    description=desc.group(1).strip().strip("'\"") if desc else "",
                    requires=_info_row(lines, "Requires") or "none",
                    identifiers=_info_row(lines, "Identifiers?"),
                    group=key,
                )
            )
    return out
