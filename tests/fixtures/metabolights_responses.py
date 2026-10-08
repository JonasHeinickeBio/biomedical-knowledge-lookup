"""Trimmed real MetaboLights / EBI Search responses (verified live 2026-10-08)."""

# EBI Search: ({q}) AND id:MTBLS*   (fields: name, description, organism, technology_type ...)
SEARCH_STUDIES_MECFS = {
    "hitCount": 1,
    "entries": [
        {
            "id": "MTBLS161",
            "source": "metabolights",
            "fields": {
                "name": [
                    "Metabolic profiling reveals anomalous energy metabolism and oxidative "
                    "stress pathways in chronic fatigue syndrome patients"
                ],
                "description": [
                    "Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is a "
                    "debilitating long-term multisystem disorder."
                ],
                "organism": ["Homo sapiens", "Homo sapiens"],
                "technology_type": ["NMR spectroscopy"],
                "study_factor": ["Chronic Fatigue Syndrome"],
                "publication_date": ["20150608"],
            },
        },
        {"id": "MTBLS999", "source": "metabolights", "fields": {"name": []}},  # nameless
        {"id": "", "source": "metabolights", "fields": {"name": ["no id"]}},
        "junk",
    ],
    "facets": [],
}

SEARCH_STUDIES_LONG_COVID = {
    "hitCount": 3,
    "entries": [
        {
            "id": "MTBLS14790",
            "fields": {
                "name": ["Brain corticogenesis promotes SARS-CoV-2 neuro-glial tropism"],
                "technology_type": ["mass spectrometry assay"],
            },
        },
        {
            "id": "MTBLS11718",
            "fields": {
                "name": ["Gut microecology of long COVID persisting for 2 years"],
                "technology_type": ["mass spectrometry assay"],
            },
        },
        {
            "id": "MTBLS7919",
            "fields": {"name": ["Delayed gut microbiota maturation in the first year of life"]},
        },
    ],
}

# EBI Search: (lactate) AND id:MTBLC*
SEARCH_COMPOUNDS_LACTATE = {
    "hitCount": 13,
    "entries": [
        {
            "id": "MTBLC16004",
            "source": "metabolights",
            "fields": {"name": ["(R)-lactate"], "description": []},
        },
        {
            "id": "MTBLC16651",
            "source": "metabolights",
            "fields": {
                "name": ["(S)-lactate"],
                "description": ["An optically active form of lactate having (S)-configuration."],
            },
        },
        {"id": "MTBLC17282", "fields": {"name": ["3-(indol-3-yl)lactate"]}},
    ],
}

NO_HITS = {"hitCount": 0, "entries": [], "facets": []}

# EBI Search entry/MTBLS161
ENTRY_MTBLS161 = {
    "entries": [
        {
            "id": "MTBLS161",
            "source": "metabolights",
            "fields": {
                "name": [
                    "Metabolic profiling reveals anomalous energy metabolism and oxidative "
                    "stress pathways in chronic fatigue syndrome patients"
                ],
                "description": ["Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)."],
                "organism": ["Homo sapiens", "Homo sapiens"],
                "technology_type": ["NMR spectroscopy"],
                "study_factor": ["Chronic Fatigue Syndrome"],
                "study_design": ["Chronic Fatigue Syndrome", "Glycolysis Pathway"],
                "publication": [
                    "Metabolic profiling reveals anomalous energy metabolism and oxidative "
                    "stress pathways in Chronic Fatigue Syndrome patients. "
                    "10.1007/s11306-015-0816-5."
                ],
                "PUBMED": [],
                "submission_date": ["20150123"],
                "publication_date": ["20150608"],
                "study_status": ["Public"],
                "tissue": [],
                "instrument_platform": ["Bruker"],
                "TAXONOMY": [],
                "METABOLIGHTS": ["MTBLC16797", "MTBLC15366", "MTBLC422", "MTBLC15366"],
            },
        }
    ]
}

# a study with a PubMed id and annotated taxonomy
ENTRY_MTBLS3707 = {
    "entries": [
        {
            "id": "MTBLS3707",
            "fields": {
                "name": ["SCP4-STK35/PDIK1L complex is a dual phospho-catalytic signaling"],
                "organism": ["Homo sapiens", "Mus musculus", "Homo sapiens"],
                "TAXONOMY": ["NCBI:9606", "NEWT:10090"],
                "PUBMED": ["35021089"],
                "publication": [
                    "SCP4-STK35/PDIK1L complex is a dual phospho-catalytic signaling "
                    "dependency in acute myeloid leukemia. 10.1016/j.celrep.2021.110233. "
                    "PMID:35021089"
                ],
                "METABOLIGHTS": ["MTBLC16651"],
            },
        }
    ]
}

# entry/MTBLC16797,MTBLC15366,MTBLC422 (names for a study's compound list)
ENTRY_COMPOUND_NAMES = {
    "entries": [
        {"id": "MTBLC422", "fields": {"name": ["(S)-lactic acid"]}},
        {"id": "MTBLC16797", "fields": {"name": ["1-methylnicotinamide"]}},
        # MTBLC15366 is omitted: unknown ids are silently dropped by the service
    ]
}

# EBI Search: "CHEBI:422" AND id:MTBLS*  (studies that report the compound)
SEARCH_STUDIES_FOR_CHEBI_422 = {
    "hitCount": 143,
    "entries": [
        {"id": "MTBLS15528", "fields": {"name": ["Integrated Multi-omics Analysis of Biliary"]}},
        {"id": "MTBLS14089", "fields": {"name": ["The accumulation of methylglyoxal"]}},
    ],
}

# ws/compounds/MTBLC16651
COMPOUND_MTBLC16651 = {
    "content": {
        "id": 1009714,
        "organism": [],
        "ObjectType": "compound",
        "accession": "MTBLC16651",
        "name": "(S)-lactate",
        "description": "An optically active form of lactate having (S)-configuration.",
        "inchi": "InChI=1S/C3H6O3/c1-2(4)3(5)6/h2,4H,1H3,(H,5,6)/p-1/t2-/m0/s1",
        "inchikey": "JVTAAEKCZFNVCJ-REOHCLBHSA-M",
        "chebiId": "CHEBI:16651",
        "formula": "C3H5O3",
        "iupacNames": "(2S)-2-hydroxypropanoate; (S)-lactate",
        "studyStatus": "PUBLIC",
        "hasLiterature": False,
        "hasReactions": True,
        "hasSpecies": True,
        "hasPathways": True,
        "hasNMR": False,
        "hasMS": False,
        "metSpecies": [
            {"species": "reference compound", "taxon": "bao:BAO_0002092"},
            {"species": "Homo sapiens", "taxon": None},
            {"species": "Escherichia coli", "taxon": "NCBI:562"},
            {"species": "Salmonella typhimurium", "taxon": "NEWT:90371"},
            {"species": "Arabidopsis thaliana", "taxon": None},
        ],
        "crossReference": [
            {"accession": "MTBLS8", "db": {"name": "MTBLS"}},
            {"accession": "CHEBI:16651", "db": {"name": "ChEBI"}},
        ],
    },
    "message": None,
    "err": None,
}

# a compound record without optional parts
COMPOUND_MINIMAL = {"content": {"accession": "MTBLC1", "name": "tiny", "metSpecies": None}}
