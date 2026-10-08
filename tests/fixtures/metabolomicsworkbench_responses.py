"""Trimmed real Metabolomics Workbench REST responses (verified live 2026-10-08)."""

_LICENSE = {
    "version": "1",
    "revision_no": "1",
    "license": "CC BY 4.0",
    "study_url": "https:\\/\\/www.metabolomicsworkbench.org\\/data\\/DRCCMetadata.php?StudyID=X",
}

# study/study_title/chronic fatigue/summary: several hits come as an object keyed "1", "2" ...
STUDY_SEARCH_MECFS = {
    "1": {
        "study_id": "ST004941",
        "study_title": (
            "Depleted Fecal Serotonin and Altered Tryptophan Metabolism in Patients with "
            "Myalgic Encephalomyelitis/Chronic Fatigue Syndrome"
        ),
        "species": "Homo sapiens",
        "institute": "National Center of Neurology and Psychiatry, Japan",
        "analysis_type": "LC-MS",
        "number_of_samples": "30",
        "submission_date": "2026-06-18",
        "release_date": "2026-07-10",
        **_LICENSE,
    },
    "2": {
        "study_id": "ST002003",
        "study_title": (
            "A case-control study on plasma metabolomics analysis in Myalgic "
            "encephalomyelitis/chronic fatigue syndrome (ME/CFS) (Part 4)"
        ),
        "species": "Homo sapiens",
        "institute": "Columbia University",
        "analysis_type": "LC-MS",
        "number_of_samples": "197",
        "submission_date": "2021-11-24",
        "release_date": "2021-12-08",
        **_LICENSE,
    },
    "3": {"study_id": "", "study_title": "no id"},
    "4": {"study_id": "ST002003", "study_title": "duplicate id is dropped"},
}

# a single hit is a flat object
STUDY_LONG_COVID = {
    "study_id": "ST003103",
    "study_title": (
        "Reinforcing the Evidence of Mitochondrial Dysfunction in Long COVID Patients using a "
        "Multiplatform Mass Spectrometry-based Metabolomics Approach"
    ),
    "species": "Homo sapiens",
    "institute": "Universidad CEU San Pablo",
    "analysis_type": "GC-MS/LC-MS",
    "number_of_samples": "92",
    "submission_date": "2024-02-23",
    "release_date": "2024-03-25",
    **_LICENSE,
}

# study_id is a prefix match: ST0020 returns every ST0020xx study
STUDY_PREFIX_MATCH = {
    "1": {"study_id": "ST002099", "study_title": "hepatitis stool"},
    "2": STUDY_SEARCH_MECFS["2"],
}

DISEASE_LONG_COVID = {"Study ID": "ST003103", "Disease": "COVID-19"}
DISEASE_NONE: list = []  # studies without a disease annotation answer []

# refmet/match/lactate
REFMET_MATCH_LACTATE = {
    "refmet_name": "Lactic acid",
    "formula": "C3H6O3",
    "exactmass": "90.0317",
    "super_class": "Organic acids",
    "main_class": "Short-chain acids",
    "sub_class": "Short-chain acids",
    "refmet_id": "RM0135904",
}
REFMET_MATCH_NONE = {
    "refmet_name": "-",
    "formula": "-",
    "exactmass": "-",
    "super_class": "-",
    "main_class": "-",
    "sub_class": "-",
    "refmet_id": "-",
}

# refmet/refmet_id/RM0135904/all
REFMET_LACTIC_ACID = {
    "refmet_id": "RM0135904",
    "name": "Lactic acid",
    "pubchem_cid": "107689",
    "inchi_key": "JVTAAEKCZFNVCJ-REOHCLBHSA-N",
    "exactmass": "90.031695",
    "formula": "C3H6O3",
    "super_class": "Organic acids",
    "main_class": "Short-chain acids",
    "sub_class": "Short-chain acids",
    "smiles": "C[C@@H](C(=O)O)O",
    "regno": "37125",
}

# compound/regno/37125/all
COMPOUND_LACTIC_ACID = {
    "regno": "37125",
    "formula": "C3H6O3",
    "exactmass": "90.031694",
    "inchi_key": "JVTAAEKCZFNVCJ-REOHCLBHSA-N",
    "name": "L-Lactic acid",
    "sys_name": "(2S)-2-hydroxypropanoic acid",
    "pubchem_cid": "107689",
    "hmdb_id": "HMDB0000190",
    "kegg_id": "C00186",
    "chebi_id": "422",
    "metacyc_id": "L-LACTATE",
    "smiles": "C[C@@H](C(=O)O)O",
}

# refmet/name/MG 18:0/0:0/0:0/all: lipid class entry with a negative regno (no compound record)
REFMET_MG = {
    "name": "MG 18:0/0:0/0:0",
    "exactmass": "358.308310",
    "formula": "C21H42O4",
    "super_class": "Glycerolipids",
    "main_class": "Monoradylglycerols",
    "sub_class": "MAG",
    "regno": "-13",
    "refmet_id": "RM0134397",
}

# study/study_id/ST004941/metabolites (feature rows repeat per analysis)
STUDY_METABOLITES = {
    "1": {
        "study_id": "ST004941",
        "analysis_id": "AN008374",
        "analysis_summary": "Reversed phase UNSPECIFIED ION MODE",
        "metabolite_name": "3-Hydroxyanthranilic acid",
        "refmet_name": "3-Hydroxyanthranilic acid",
    },
    "2": {
        "study_id": "ST004941",
        "analysis_id": "AN008374",
        "metabolite_name": "5-Hydroxyindole-3-acetic acid",
        "refmet_name": "5-Hydroxyindoleacetic acid",
    },
    "3": {
        "study_id": "ST004941",
        "analysis_id": "AN008375",
        "metabolite_name": "3-hydroxyanthranilate",
        "refmet_name": "3-Hydroxyanthranilic acid",
    },
    "4": {"study_id": "ST004941", "analysis_id": "AN008374", "refmet_name": ""},
    "5": {"study_id": "ST004941", "analysis_id": "AN008374", "refmet_name": "Standard"},
    "6": {"study_id": "ST004941", "analysis_id": "AN008374", "refmet_name": "-"},
    "7": {"study_id": "ST004941", "analysis_id": "AN008374", "refmet_name": "Tryptophan"},
    "8": {"study_id": "ST009999", "analysis_id": "AN000001", "refmet_name": "Other study"},
}

# study/refmet_name/Lactic acid/summary (one row per study; ascending ids)
STUDIES_FOR_LACTIC_ACID = {
    str(i + 1): {"refmet_name": "Lactic acid", "kegg_id": "C00186", "study_id": sid}
    for i, sid in enumerate(["ST000001", "ST000002", "ST003103", "ST002003", "ST003103"])
}
