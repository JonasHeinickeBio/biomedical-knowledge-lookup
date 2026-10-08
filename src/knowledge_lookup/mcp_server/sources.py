"""
Knowledge-source catalog and identifier routing for the MCP server.

``CentralKnowledgeLookup.get_concept_details`` without a source asks *every*
adapter and waits for all of them; adapters that wrap synchronous clients can
block the event loop for minutes on an unknown ID. The server instead routes an
identifier to the source(s) that can actually resolve it — by CURIE prefix, OBO
PURL, or the shape of a bare accession — and falls back to an exact-ID search
in OLS when routing finds nothing.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

from ..core.central_lookup import _CURIE_PREFIX_TO_SOURCE
from ..models import KnowledgeSource

# Every source with an adapter (see ``adapters.ADAPTER_CLASSES``). Spelled out as a
# Literal so tool input schemas list exactly the names a model may pass.
SourceName = Literal[
    "ALPHAFOLD",
    "BIOLINKER",
    "BIOONTOLOGY",
    "BIOPORTAL",
    "BIORXIV",
    "CELLMARKER",
    "CELLONTOLOGY",
    "CELLXGENE",
    "CHEBI",
    "CHEMBL",
    "CLINGEN",
    "CLINICALTABLES",
    "CLINICALTRIALS",
    "CLINPGX",
    "CLINVAR",
    "COSMIC",
    "CROSSREF",
    "CTD",
    "DBPEDIA",
    "DBSNP",
    "DGIDB",
    "DISGENET",
    "DOID",
    "DRUGBANK",
    "EBIOLS",
    "ENSEMBL",
    "EQTLCATALOGUE",
    "EUROPEPMC",
    "EUTILS",
    "GENCC",
    "GENEONTOLOGY",
    "GNOMAD",
    "GTEX",
    "GWASCATALOG",
    "HGNC",
    "HPO",
    "HPOA",
    "HUMANPROTEINATLAS",
    "ICD10GM",
    "ICD11",
    "IEDB",
    "INTACT",
    "INTERPRO",
    "KEGG",
    "LIPIDMAPS",
    "LITCOVID",
    "LOINC",
    "MEDGEN",
    "MEDLINEPLUS",
    "MESH",
    "METABOLIGHTS",
    "METABOLOMICSWORKBENCH",
    "MONARCH",
    "MONDO",
    "MYGENEINFO",
    "MYGENEINFO",
    "NCBITAXONOMY",
    "NCIEVS",
    "NIHREPORTER",
    "NODENORM",
    "OBOFOUNDRY",
    "OFFSIDES",
    "OLS",
    "OMIM",
    "OPENALEX",
    "OPENCITATIONS",
    "OPENFDAEVENTS",
    "OPENFDALABELS",
    "OPENTARGETS",
    "ORPHANET",
    "OXO",
    "PANELAPP",
    "PDB",
    "PFAM",
    "PUBCHEM",
    "PUBTATOR",
    "QUICKGO",
    "REACTOME",
    "RHEA",
    "RXCLASS",
    "RXNORM",
    "SEMANTICSCHOLAR",
    "SEMMEDDB",
    "SIDER",
    "SNOMEDCT",
    "STRING",
    "TYTO",
    "UMLS",
    "UNICHEM",
    "UNIPROT",
    "WIKIDATA",
    "WIKIPATHWAYS",
    "ZOOMA",
]


class SourceSpec(NamedTuple):
    description: str
    requires: str | None = None


SOURCE_CATALOG: dict[KnowledgeSource, SourceSpec] = {
    KnowledgeSource.OLS: SourceSpec(
        "EBI Ontology Lookup Service: 250+ ontologies (DOID, EFO, NCIT, UBERON, CHEBI, ...)"
    ),
    KnowledgeSource.MONDO: SourceSpec("Mondo Disease Ontology, e.g. MONDO:0005148"),
    KnowledgeSource.HPO: SourceSpec("Human Phenotype Ontology, e.g. HP:0001250"),
    KnowledgeSource.GENEONTOLOGY: SourceSpec("Gene Ontology terms, e.g. GO:0008150"),
    KnowledgeSource.HGNC: SourceSpec("HGNC human gene nomenclature, e.g. HGNC:1100 (BRCA1)"),
    KnowledgeSource.UNIPROT: SourceSpec("UniProtKB proteins, e.g. P38398"),
    KnowledgeSource.ENSEMBL: SourceSpec("Ensembl genes and transcripts, e.g. ENSG00000012048"),
    KnowledgeSource.PUBCHEM: SourceSpec("PubChem compounds (CIDs)"),
    KnowledgeSource.CHEMBL: SourceSpec(
        "ChEMBL bioactive molecules and drugs, e.g. CHEMBL25", "the [chembl] extra"
    ),
    KnowledgeSource.REACTOME: SourceSpec("Reactome pathways, e.g. R-HSA-1640170"),
    KnowledgeSource.UMLS: SourceSpec(
        "UMLS Metathesaurus concepts (CUIs, e.g. C0011849) spanning SNOMED CT, MeSH, ICD, ...",
        "the [umls] extra and the UMLS_API_KEY environment variable",
    ),
    KnowledgeSource.BIOPORTAL: SourceSpec(
        "NCBO BioPortal: 1000+ ontologies (SNOMED CT, MeSH, ICD, ...)",
        "the BIOPORTAL_API_KEY environment variable",
    ),
    KnowledgeSource.BIOONTOLOGY: SourceSpec(
        "NCBO BioOntology search API", "the BIOPORTAL_API_KEY environment variable"
    ),
    KnowledgeSource.OXO: SourceSpec("EBI OxO ontology cross-reference mappings"),
    KnowledgeSource.ZOOMA: SourceSpec("EBI ZOOMA text-to-ontology annotation"),
    KnowledgeSource.EBIOLS: SourceSpec("EMBL-EBI OLS (a variant of the OLS adapter)"),
    KnowledgeSource.OBOFOUNDRY: SourceSpec("OBO Foundry ontology registry"),
    KnowledgeSource.TYTO: SourceSpec("Tyto ontology term lookup", "the [tyto] extra"),
    KnowledgeSource.WIKIDATA: SourceSpec("Wikidata items, e.g. Q12136"),
    KnowledgeSource.DBPEDIA: SourceSpec("DBpedia resources (general knowledge)"),
    KnowledgeSource.BIOLINKER: SourceSpec("BioLinker entity linking"),
    KnowledgeSource.DISGENET: SourceSpec(
        "DisGeNET gene-disease associations", "the DISGENET_API_KEY environment variable"
    ),
    KnowledgeSource.OPENTARGETS: SourceSpec("Open Targets target-disease evidence"),
    KnowledgeSource.DRUGBANK: SourceSpec("DrugBank drugs, e.g. DB00945"),
    KnowledgeSource.UNICHEM: SourceSpec(
        "UniChem chemical cross-references", "the [bioservices] extra"
    ),
    KnowledgeSource.KEGG: SourceSpec("KEGG diseases, drugs and pathways"),
    KnowledgeSource.QUICKGO: SourceSpec("EBI QuickGO annotations", "the [bioservices] extra"),
    KnowledgeSource.EUTILS: SourceSpec(
        "NCBI E-utilities (PubMed, Gene, MeSH)", "the [bioservices] extra"
    ),
    KnowledgeSource.EUROPEPMC: SourceSpec("Europe PMC literature"),
    KnowledgeSource.OMIM: SourceSpec(
        "OMIM Mendelian disorders and genes", "the OMIM_API_KEY environment variable"
    ),
    KnowledgeSource.CLINVAR: SourceSpec("ClinVar variants and clinical significance"),
    KnowledgeSource.COSMIC: SourceSpec("COSMIC somatic cancer mutations"),
    KnowledgeSource.PDB: SourceSpec("RCSB Protein Data Bank structures"),
    KnowledgeSource.INTERPRO: SourceSpec("InterPro protein families and domains, e.g. IPR000719"),
    KnowledgeSource.PFAM: SourceSpec("Pfam protein families, e.g. PF00069"),
    KnowledgeSource.STRING: SourceSpec("STRING protein-protein interactions"),
    KnowledgeSource.WIKIPATHWAYS: SourceSpec(
        "WikiPathways community-curated pathways, e.g. WP4262"
    ),
    KnowledgeSource.MONARCH: SourceSpec(
        "Monarch Initiative gene-disease-phenotype associations (HPO, MONDO, OMIM, Orphanet)",
    ),
    KnowledgeSource.HPOA: SourceSpec(
        "HPO disease-to-phenotype annotations with frequency (phenotype.hpoa, ~36 MB download)",
        "opt-in download: HPOA_DOWNLOAD=1, or a local file (HPOA_PATH)",
    ),
    KnowledgeSource.NODENORM: SourceSpec(
        "NCATS Translator Node Normalizer / Name Resolver: equivalent identifiers across MONDO, HP, UMLS, MeSH, NCBIGene",
    ),
    KnowledgeSource.MESH: SourceSpec(
        "NLM Medical Subject Headings descriptors and tree hierarchy, e.g. D003920",
    ),
    KnowledgeSource.RXCLASS: SourceSpec(
        "ATC and other drug classes via NLM RxNav RxClass",
    ),
    KnowledgeSource.SNOMEDCT: SourceSpec(
        "SNOMED CT concepts and hierarchy via Snowstorm (SNOMED licence applies; the public instance is for light use, set SNOMED_SNOWSTORM_URL for your own server)",
    ),
    KnowledgeSource.ICD11: SourceSpec(
        "WHO ICD-11 entities and codes",
        "the ICD11_CLIENT_ID and ICD11_CLIENT_SECRET environment variables",
    ),
    KnowledgeSource.ICD10GM: SourceSpec(
        "German ICD-10-GM classification (BfArM), e.g. G93.3",
        "the BfArM ICD-10-GM ClaML file (ICD10GM_CLAML_PATH, or ICD10GM_URL for a download you choose)",
    ),
    KnowledgeSource.LOINC: SourceSpec(
        "LOINC laboratory and clinical observation codes",
        "the LOINC_USERNAME and LOINC_PASSWORD environment variables",
    ),
    KnowledgeSource.GWASCATALOG: SourceSpec(
        "NHGRI-EBI GWAS Catalog traits, studies and variant-trait associations",
    ),
    KnowledgeSource.CTD: SourceSpec(
        "Comparative Toxicogenomics Database chemical-gene-disease links (non-commercial use)",
        "opt-in download (~220 MB core reports): CTD_DOWNLOAD=1, or CTD_DATA_DIR",
    ),
    KnowledgeSource.DGIDB: SourceSpec(
        "DGIdb aggregated drug-gene interactions",
    ),
    KnowledgeSource.INTACT: SourceSpec(
        "IntAct curated experimental molecular interactions",
    ),
    KnowledgeSource.PUBTATOR: SourceSpec(
        "PubTator 3 literature entities and relations for PubMed/PMC",
    ),
    KnowledgeSource.CLINICALTRIALS: SourceSpec(
        "ClinicalTrials.gov registered studies, conditions and interventions",
    ),
    KnowledgeSource.SEMMEDDB: SourceSpec(
        "SemMedDB subject-predicate-object relations from PubMed (local export; UMLS licence)",
        "a SQLite database built with `knowledge-lookup semmeddb-build` (SEMMEDDB_PATH)",
    ),
    KnowledgeSource.SIDER: SourceSpec(
        "SIDER drug side effects (dataset, CC BY-SA 4.0; frozen in 2016)",
        "opt-in download (~5.5 MB): SIDER_DOWNLOAD=1, or SIDER_DATA_DIR",
    ),
    KnowledgeSource.OFFSIDES: SourceSpec(
        "OFFSIDES off-label drug side effects from adverse event reports (statistical signals)",
        "opt-in download (~69 MB): OFFSIDES_DOWNLOAD=1, or OFFSIDES_PATH",
    ),
    KnowledgeSource.HUMANPROTEINATLAS: SourceSpec(
        "Human Protein Atlas tissue and blood protein expression (CC BY 4.0)",
    ),
    KnowledgeSource.CELLONTOLOGY: SourceSpec(
        "Cell Ontology cell types, e.g. CL:0000084",
    ),
    KnowledgeSource.CELLMARKER: SourceSpec(
        "CellMarker cell-type marker genes (dataset file you provide)",
        "a data file: CELLMARKER_PATH, or CELLMARKER_URL",
    ),
    KnowledgeSource.CHEBI: SourceSpec(
        "ChEBI chemical entities and ontology, e.g. CHEBI:15365",
    ),
    KnowledgeSource.MYGENEINFO: SourceSpec(
        "MyGene.info gene annotation and identifier cross-references",
    ),
    KnowledgeSource.LITCOVID: SourceSpec(
        "NCBI LitCovid COVID-19 and Long COVID literature with topics and entities",
    ),
    KnowledgeSource.OPENALEX: SourceSpec(
        "OpenAlex scholarly works, authors, topics and citation links (keyless budget ~100 searches/day; free key = 10x)",
    ),
    KnowledgeSource.OPENFDAEVENTS: SourceSpec(
        "FDA adverse event reports (FAERS) by drug and reaction via openFDA: spontaneous reports, no causality (1,000 requests/day without a key)",
    ),
    KnowledgeSource.ORPHANET: SourceSpec(
        "Orphanet rare-disease nosology, genes, prevalence and HPO phenotypes (Orphadata)",
    ),
    KnowledgeSource.CLINGEN: SourceSpec(
        "ClinGen gene-disease validity and dosage sensitivity (CSV exports; CC0)",
        "opt-in download (~1.4 MB): CLINGEN_DOWNLOAD=1, or CLINGEN_PATH",
    ),
    KnowledgeSource.GENCC: SourceSpec(
        "GenCC harmonised gene-disease validity submissions (CSV export)",
        "opt-in download (~28 MB): GENCC_DOWNLOAD=1, or GENCC_PATH",
    ),
    KnowledgeSource.MEDGEN: SourceSpec(
        "NCBI MedGen medical-condition concepts with UMLS CUIs and cross-references",
    ),
    KnowledgeSource.DOID: SourceSpec(
        "Human Disease Ontology (DOID) terms and hierarchy",
    ),
    KnowledgeSource.GTEX: SourceSpec(
        "GTEx tissue gene expression and eQTLs",
    ),
    KnowledgeSource.GNOMAD: SourceSpec(
        "gnomAD population variant frequencies and gene constraint (GraphQL)",
    ),
    KnowledgeSource.DBSNP: SourceSpec(
        "NCBI dbSNP reference SNPs (rsIDs): alleles, frequencies and clinical significance",
    ),
    KnowledgeSource.ALPHAFOLD: SourceSpec(
        "AlphaFold DB predicted protein structures and confidence",
    ),
    KnowledgeSource.RXNORM: SourceSpec(
        "NLM RxNorm drug concepts (ingredients, brands, clinical drugs) and relations",
    ),
    KnowledgeSource.CLINPGX: SourceSpec(
        "ClinPGx/PharmGKB genes, drugs, variants and clinical annotations (CC BY-SA)",
    ),
    KnowledgeSource.OPENFDALABELS: SourceSpec(
        "FDA structured drug labels (indications, warnings, adverse reactions) via openFDA",
    ),
    KnowledgeSource.CLINICALTABLES: SourceSpec(
        "NLM Clinical Table Search Service: ICD-10-CM, LOINC items, conditions and other code tables",
    ),
    KnowledgeSource.NCIEVS: SourceSpec(
        "NCI Thesaurus and other NCI EVS terminologies via the EVS REST API (NCIM, SNOMED CT and MedDRA texts carry non-commercial restrictions)",
    ),
    KnowledgeSource.MEDLINEPLUS: SourceSpec(
        "MedlinePlus consumer health information by condition, ICD-10-CM or SNOMED CT code",
    ),
    KnowledgeSource.NCBITAXONOMY: SourceSpec(
        "NCBI Taxonomy organisms, viruses and lineages (SARS-CoV-2, EBV, ...)",
    ),
    KnowledgeSource.METABOLOMICSWORKBENCH: SourceSpec(
        "Metabolomics Workbench metabolites, studies and RefMet names",
    ),
    KnowledgeSource.METABOLIGHTS: SourceSpec(
        "EMBL-EBI MetaboLights metabolomics studies and reference metabolites",
    ),
    KnowledgeSource.LIPIDMAPS: SourceSpec(
        "LIPID MAPS lipid structures and classification",
    ),
    KnowledgeSource.RHEA: SourceSpec(
        "Rhea expert-curated biochemical reactions with ChEBI participants",
    ),
    KnowledgeSource.IEDB: SourceSpec(
        "Immune Epitope Database: epitopes, assays and MHC restriction",
    ),
    KnowledgeSource.CELLXGENE: SourceSpec(
        "CZ CELLxGENE Discover single-cell datasets, tissues and cell types",
    ),
    KnowledgeSource.PANELAPP: SourceSpec(
        "Genomics England PanelApp expert-reviewed gene panels (terms exclude commercial and diagnostic use)",
    ),
    KnowledgeSource.EQTLCATALOGUE: SourceSpec(
        "eQTL Catalogue dataset, study and tissue metadata only (its association API was retired)",
    ),
    KnowledgeSource.CROSSREF: SourceSpec(
        "Crossref DOI metadata, references and retraction/correction notices",
    ),
    KnowledgeSource.BIORXIV: SourceSpec(
        "bioRxiv and medRxiv preprints (many Long COVID papers appear here first)",
    ),
    KnowledgeSource.OPENCITATIONS: SourceSpec(
        "OpenCitations open citation links between DOIs",
    ),
    KnowledgeSource.NIHREPORTER: SourceSpec(
        "NIH RePORTER funded research projects and publications",
    ),
    KnowledgeSource.SEMANTICSCHOLAR: SourceSpec(
        "Semantic Scholar papers, citations and TLDR summaries (keyless search is heavily rate limited; a free key is recommended)",
    ),
}

# Searched when a tool call names no sources: fast, keyless (or key-gated but
# high-value) terminologies. Unavailable ones are skipped at call time. ChEMBL is
# left out on purpose: its substring queries routinely take tens of seconds.
DEFAULT_SEARCH_SOURCES: tuple[KnowledgeSource, ...] = (
    KnowledgeSource.OLS,
    KnowledgeSource.MONDO,
    KnowledgeSource.HPO,
    KnowledgeSource.GENEONTOLOGY,
    KnowledgeSource.HGNC,
    KnowledgeSource.UNIPROT,
    KnowledgeSource.PUBCHEM,
    KnowledgeSource.REACTOME,
    KnowledgeSource.UMLS,
    KnowledgeSource.BIOPORTAL,
)

_SOURCE_ALIASES = {
    "GO": "GENEONTOLOGY",
    "GENE_ONTOLOGY": "GENEONTOLOGY",
    "HP": "HPO",
    "EBI_OLS": "EBIOLS",
    "OPEN_TARGETS": "OPENTARGETS",
    "EUROPE_PMC": "EUROPEPMC",
    "UNIPROTKB": "UNIPROT",
}


def normalize_source_name(value: object) -> object:
    """Case-/separator-insensitive source names plus common aliases ('go' -> GENEONTOLOGY)."""
    if not isinstance(value, str):
        return value
    key = value.strip().upper().replace("-", "_").replace(" ", "_")
    return _SOURCE_ALIASES.get(key, key)


def parse_source_names(raw: str) -> list[KnowledgeSource]:
    """Parse a comma-separated source list (CLI flags / environment variables)."""
    sources = []
    for part in raw.split(","):
        if part.strip():
            sources.append(KnowledgeSource(normalize_source_name(part)))
    return sources


# Prefixes the library map lacks but that have a dedicated adapter.
_EXTRA_PREFIX_ROUTES: dict[str, KnowledgeSource] = {
    "HGNC": KnowledgeSource.HGNC,
    "INTERPRO": KnowledgeSource.INTERPRO,
    "PFAM": KnowledgeSource.PFAM,
    "PDB": KnowledgeSource.PDB,
    "MIM": KnowledgeSource.OMIM,
    "WIKIPATHWAYS": KnowledgeSource.WIKIPATHWAYS,
    "WP": KnowledgeSource.WIKIPATHWAYS,
}

# Adapters whose get_concept_details wants the full CURIE ("HP:0001250"); the
# rest of the routed adapters want the bare local ID ("P38398", "C0011849").
_CURIE_ID_SOURCES = frozenset(
    {
        KnowledgeSource.HPO,
        KnowledgeSource.MONDO,
        KnowledgeSource.GENEONTOLOGY,
        KnowledgeSource.HGNC,
    }
)

# OBO-style CURIEs (PREFIX:digits) resolve through OLS via their OBO PURL.
_OBO_CURIE = re.compile(r"^([A-Za-z][A-Za-z0-9]*):(\d+)$")

# Bare accessions whose shape identifies the source. Order matters where shapes
# overlap (a Wikidata Q-number can also look like a UniProt accession).
_BARE_ID_PATTERNS: tuple[tuple[re.Pattern[str], KnowledgeSource], ...] = (
    (re.compile(r"^C\d{7}$"), KnowledgeSource.UMLS),
    (re.compile(r"^Q\d+$"), KnowledgeSource.WIKIDATA),
    (re.compile(r"^ENS[A-Z]*[EGPT]\d{11}(\.\d+)?$"), KnowledgeSource.ENSEMBL),
    (re.compile(r"^R-[A-Z]{3}-\d+(\.\d+)?$"), KnowledgeSource.REACTOME),
    (re.compile(r"^WP\d+$", re.IGNORECASE), KnowledgeSource.WIKIPATHWAYS),
    (re.compile(r"^CHEMBL\d+$", re.IGNORECASE), KnowledgeSource.CHEMBL),
    (re.compile(r"^DB\d{5}$"), KnowledgeSource.DRUGBANK),
    (re.compile(r"^IPR\d{6}$"), KnowledgeSource.INTERPRO),
    (re.compile(r"^PF\d{5}$"), KnowledgeSource.PFAM),
    (
        re.compile(
            r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})(-\d+)?$"
        ),
        KnowledgeSource.UNIPROT,
    ),
)


def route_identifier(identifier: str) -> list[tuple[KnowledgeSource, str]]:
    """Ordered ``(source, id_to_send)`` candidates for resolving *identifier*.

    Most specific first. Adapters disagree on whether they want the full CURIE
    or the bare local ID (HPO wants ``HP:0001250``, UniProt wants ``P38398``),
    so each routed source gets the form its adapter expects.
    """
    ident = identifier.strip()
    candidates: list[tuple[KnowledgeSource, str]] = []

    if "://" in ident:
        candidates.append((KnowledgeSource.OLS, ident))
    elif ":" in ident:
        prefix, _, local = ident.partition(":")
        key = prefix.upper()
        routed = _EXTRA_PREFIX_ROUTES.get(key) or _CURIE_PREFIX_TO_SOURCE.get(key)
        # OLS only resolves IRIs (added below) and OxO has no concept records
        if (
            routed is not None
            and routed not in (KnowledgeSource.OLS, KnowledgeSource.OXO)
            and local
        ):
            candidates.append((routed, ident if routed in _CURIE_ID_SOURCES else local))
        if _OBO_CURIE.match(ident):
            candidates.append(
                (KnowledgeSource.OLS, f"http://purl.obolibrary.org/obo/{key}_{local}")
            )
    else:
        candidates.extend(
            (source, ident) for pattern, source in _BARE_ID_PATTERNS if pattern.match(ident)
        )

    return list(dict.fromkeys(candidates))
