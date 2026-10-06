"""Trimmed real MyGene.info v3 responses (fetched 2026-10) for the MyGeneInfoAdapter tests.

BRCA1 uses list-valued alias and a single ``ensembl`` dict, CRP the single-value shapes
(alias str, pathway entries as dicts), TNF the multi-locus ``ensembl`` list.
"""

BRCA1_GENE = {
    "HGNC": "1100",
    "MIM": "113705",
    "_id": "672",
    "alias": ["BRCAI", "BRCC1", "BROVCA1", "FANCS", "IRIS", "PNCA4", "PPP1R53", "PSCP", "RNF53"],
    "ensembl": {"gene": "ENSG00000012048"},
    "entrezgene": "672",
    "homologene": {
        "genes": [
            [9031, 373983],
            [9544, 712634],
            [9598, 449497],
            [9606, 672],
            [9615, 403437],
            [9913, 353120],
            [10090, 12189],
            [10116, 497672],
        ],
        "id": 5276,
    },
    "map_location": "17q21.31",
    "name": "BRCA1 DNA repair associated",
    "other_names": [
        "BRCA1/BRCA2-containing complex, subunit 1",
        "Fanconi anemia, complementation group S",
        "RING finger protein 53",
    ],
    "pathway": {
        "biocarta": [
            {"id": "atmpathway", "name": "atm signaling pathway"},
            {
                "id": "atrbrcapathway",
                "name": "role of brca1 brca2 and atr in cancer susceptibility",
            },
            {"id": "bard1pathway", "name": "brca1 dependent ub ligase activity"},
        ],
        "kegg": [
            {"id": "hsa03440", "name": "Homologous recombination - Homo sapiens (human)"},
            {"id": "hsa03460", "name": "Fanconi anemia pathway - Homo sapiens (human)"},
            {"id": "hsa04120", "name": "Ubiquitin mediated proteolysis - Homo sapiens (human)"},
        ],
        "netpath": [
            {"id": "Pathway_AndrogenReceptor", "name": "AndrogenReceptor"},
            {"id": "Pathway_TGF_beta_Receptor", "name": "TGF_beta_Receptor"},
        ],
        "pid": [
            {"id": "ar_pathway", "name": "Coregulation of Androgen receptor activity"},
            {"id": "atf2_pathway", "name": "ATF-2 transcription factor network"},
            {"id": "atm_pathway", "name": "ATM pathway"},
        ],
        "wikipathways": [
            {"id": "WP138", "name": "Androgen receptor signaling pathway"},
            {"id": "WP1530", "name": "miRNA regulation of DNA damage response"},
            {"id": "WP2261", "name": "Glioblastoma signaling pathways"},
        ],
    },
    "pdb": [
        "1JM7",
        "1JNX",
        "1N5O",
        "1OQA",
        "1T15",
        "1T29",
        "1T2U",
        "1T2V",
        "1Y98",
        "2ING",
        "3COJ",
        "3K0H",
    ],
    "pharmgkb": "PA25411",
    "summary": "This gene encodes a 190 kD nuclear phosphoprotein that plays a role in "
    "maintaining genomic stability, and it also acts as a tumor suppressor. The BRCA1 "
    "gene contains 22 exons spanning about 110 kb of DNA. The encoded pro",
    "symbol": "BRCA1",
    "taxid": 9606,
    "type_of_gene": "protein-coding",
    "uniprot": {
        "Swiss-Prot": "P38398",
        "TrEMBL": [
            "B4DES0",
            "H0Y850",
            "A0ACM8QT95",
            "A0A9Y1QPT7",
            "A0A9Y1VR53",
            "E7EUM2",
            "E7ENB7",
            "E7EQW4",
            "A0A2R8Y7V5",
            "A0A9Y1VVD0",
            "H0Y8D8",
            "A0A9Y1VVE2",
        ],
    },
}

IL6_GENE = {
    "HGNC": "6018",
    "MIM": "147620",
    "_id": "3569",
    "alias": ["BSF-2", "BSF2", "CDF", "HGF", "HSF", "IFN-beta-2", "IFNB2", "IL-6"],
    "ensembl": {"gene": "ENSG00000136244"},
    "entrezgene": "3569",
    "homologene": {
        "genes": [
            [9031, 395337],
            [9544, 705819],
            [9598, 463288],
            [9606, 3569],
            [9615, 403985],
            [10090, 16193],
            [10116, 24498],
        ],
        "id": 502,
    },
    "map_location": "7p15.3",
    "name": "interleukin 6",
    "other_names": [
        "B-cell differentiation factor",
        "B-cell stimulatory factor 2",
        "CTL differentiation factor",
    ],
    "pathway": {
        "biocarta": [
            {"id": "her2pathway", "name": "role of erbb2 in signal transduction and oncology"},
            {"id": "il10pathway", "name": "il-10 anti-inflammatory signaling pathway"},
            {"id": "il1rpathway", "name": "signal transduction through il1r"},
        ],
        "kegg": [
            {
                "id": "hsa04060",
                "name": "Cytokine-cytokine receptor interaction - Homo sapiens (human)",
            },
            {
                "id": "hsa04061",
                "name": "Viral protein interaction with cytokine and cytokine receptor "
                "- Homo sapiens (human)",
            },
            {"id": "hsa04066", "name": "HIF-1 signaling pathway - Homo sapiens (human)"},
        ],
        "netpath": {"id": "Pathway_IL6", "name": "IL6"},
        "pid": [
            {"id": "amb2_neutrophils_pathway", "name": "amb2 Integrin signaling"},
            {"id": "ap1_pathway", "name": "AP-1 transcription factor network"},
            {"id": "atf2_pathway", "name": "ATF-2 transcription factor network"},
        ],
        "wikipathways": [
            {"id": "WP1449", "name": "Regulation of toll-like receptor signaling pathway"},
            {"id": "WP15", "name": "Selenium Micronutrient Network"},
            {"id": "WP1533", "name": "Vitamin B12 metabolism"},
        ],
    },
    "pdb": [
        "1ALU",
        "1IL6",
        "1P9M",
        "2IL6",
        "4CNI",
        "4J4L",
        "4NI7",
        "4NI9",
        "4O9H",
        "4ZS7",
        "5FUC",
        "7NXZ",
    ],
    "pharmgkb": "PA198",
    "summary": "This gene encodes a cytokine that functions in inflammation and the maturation of "
    "B cells. In addition, the encoded protein has been shown to be an endogenous "
    "pyrogen capable of inducing fever in people with autoimmune d",
    "symbol": "IL6",
    "taxid": 9606,
    "type_of_gene": "protein-coding",
    "uniprot": {
        "Swiss-Prot": "P05231",
        "TrEMBL": [
            "B5MC21",
            "Q75MH2",
            "B4DVM1",
            "B4DNQ5",
            "B5MCZ3",
            "A0A8Q3SJL1",
            "A0ACI8V9J2",
            "F6VWX4",
            "B5MC14",
            "C9J5B0",
        ],
    },
}

CRP_GENE = {
    "HGNC": "2367",
    "MIM": "123260",
    "_id": "1401",
    "alias": "PTX1",
    "ensembl": {"gene": "ENSG00000132693"},
    "entrezgene": "1401",
    "homologene": {
        "genes": [
            [8364, 493537],
            [8364, 496665],
            [8364, 496737],
            [8364, 496764],
            [8364, 496975],
            [8364, 548444],
            [8364, 548590],
            [8364, 100135384],
            [8364, 100145348],
            [8364, 100216304],
            [8364, 100485832],
            [8364, 100486739],
            [8364, 100487769],
            [8364, 100489587],
            [8364, 100489659],
            [8364, 100489750],
            [8364, 100490829],
            [8364, 100494488],
            [8364, 100494645],
            [8364, 101730495],
            [9031, 429786],
            [9544, 719454],
            [9598, 457428],
            [9606, 1401],
            [9615, 488629],
            [9913, 527553],
            [10090, 12944],
            [10116, 25419],
        ],
        "id": 128039,
    },
    "map_location": "1q23.2",
    "name": "C-reactive protein",
    "other_names": ["C-reactive protein", "C-reactive protein, pentraxin-related", "pentraxin 1"],
    "pathway": {
        "netpath": {"id": "Pathway_Leptin", "name": "Leptin"},
        "pid": {"id": "il6_7pathway", "name": "IL6-mediated signaling events"},
        "wikipathways": [
            {"id": "WP15", "name": "Selenium Micronutrient Network"},
            {"id": "WP1533", "name": "Vitamin B12 metabolism"},
            {"id": "WP176", "name": "Folate Metabolism"},
        ],
    },
    "pdb": [
        "1B09",
        "1GNH",
        "1LJ7",
        "3L2Y",
        "3PVN",
        "3PVO",
        "7PK9",
        "7PKB",
        "7PKD",
        "7PKE",
        "7PKF",
        "7PKG",
    ],
    "pharmgkb": "PA120",
    "summary": "The protein encoded by this gene belongs to the pentraxin family which also "
    "includes serum amyloid P component protein and pentraxin 3. Pentraxins are "
    "involved in complement activation and amplification via communication",
    "symbol": "CRP",
    "taxid": 9606,
    "type_of_gene": "protein-coding",
    "uniprot": {"Swiss-Prot": "P02741", "TrEMBL": ["C9JRE9", "Q5VVP7"]},
}

TNF_GENE = {
    "HGNC": "11892",
    "MIM": "191160",
    "_id": "7124",
    "alias": ["DIF", "IMD127", "TNF-alpha", "TNFA", "TNFSF2", "TNLG1F"],
    "ensembl": [
        {"gene": "ENSG00000228849"},
        {"gene": "ENSG00000223952"},
        {"gene": "ENSG00000228321"},
    ],
    "entrezgene": "7124",
    "homologene": {
        "genes": [
            [8364, 100134991],
            [9544, 715467],
            [9598, 494186],
            [9606, 7124],
            [9615, 403922],
            [9913, 280943],
            [10090, 21926],
            [10116, 24835],
        ],
        "id": 496,
    },
    "map_location": "6p21.33",
    "name": "tumor necrosis factor",
    "other_names": ["APC1 protein", "TNF, macrophage-derived", "TNF, monocyte-derived"],
    "pathway": {
        "biocarta": [
            {
                "id": "cdmacpathway",
                "name": "cadmium induces dna synthesis and proliferation in macrophages",
            },
            {"id": "ceramidepathway", "name": "ceramide signaling pathway"},
            {"id": "hivnefpathway", "name": "hiv-1 nef: negative effector of fas and tnf"},
        ],
        "kegg": [
            {"id": "hsa04010", "name": "MAPK signaling pathway - Homo sapiens (human)"},
            {
                "id": "hsa04060",
                "name": "Cytokine-cytokine receptor interaction - Homo sapiens (human)",
            },
            {
                "id": "hsa04061",
                "name": "Viral protein interaction with cytokine and cytokine receptor "
                "- Homo sapiens (human)",
            },
        ],
        "netpath": [
            {"id": "Pathway_TNFalpha", "name": "TNFalpha"},
            {"id": "Pathway_TWEAK", "name": "TWEAK"},
        ],
        "pid": [
            {"id": "amb2_neutrophils_pathway", "name": "amb2 Integrin signaling"},
            {
                "id": "angiopoietinreceptor_pathway",
                "name": "Angiopoietin receptor Tie2-mediated signaling",
            },
            {"id": "anthraxpathway", "name": "Cellular roles of Anthrax toxin"},
        ],
        "smpdb": {"id": "SMP00358", "name": "Fc Epsilon Receptor I Signaling in Mast Cells"},
        "wikipathways": [
            {"id": "WP129", "name": "Matrix Metalloproteinases"},
            {"id": "WP1449", "name": "Regulation of toll-like receptor signaling pathway"},
            {"id": "WP15", "name": "Selenium Micronutrient Network"},
        ],
    },
    "pdb": [
        "1A8M",
        "1TNF",
        "2AZ5",
        "2E7A",
        "2TUN",
        "2ZJC",
        "2ZPX",
        "3ALQ",
        "3IT8",
        "3L9J",
        "3WD5",
        "4G3Y",
    ],
    "pharmgkb": "PA435",
    "summary": "This gene encodes a multifunctional proinflammatory cytokine that belongs to the "
    "tumor necrosis factor (TNF) superfamily. This cytokine is mainly secreted by "
    "macrophages. It can bind to, and thus functions through its re",
    "symbol": "TNF",
    "taxid": 9606,
    "type_of_gene": "protein-coding",
    "uniprot": {"Swiss-Prot": "P01375", "TrEMBL": ["A0A8V8TNL2", "Q5STB3"]},
}

SEARCH_BRCA1 = {
    "took": 9,
    "total": 45,
    "max_score": 145.1008,
    "hits": [
        {
            "HGNC": "1100",
            "_id": "672",
            "_score": 145.1008,
            "entrezgene": "672",
            "name": "BRCA1 DNA repair associated",
            "symbol": "BRCA1",
            "taxid": 9606,
            "type_of_gene": "protein-coding",
        },
        {
            "HGNC": "1099",
            "_id": "8315",
            "_score": 59.867004,
            "entrezgene": "8315",
            "name": "BRCA1 associated protein",
            "symbol": "BRAP",
            "taxid": 9606,
            "type_of_gene": "protein-coding",
        },
        {
            "_id": "111589215",
            "_score": 59.867004,
            "entrezgene": "111589215",
            "name": "BRCA1 promoter region",
            "symbol": "LOC111589215",
            "taxid": 9606,
            "type_of_gene": "biological-region",
        },
    ],
}

SEARCH_EMPTY = {"took": 1, "total": 0, "max_score": None, "hits": []}

ORTHOLOG_SYMBOLS = {
    "took": 3,
    "total": 4,
    "max_score": 23.003933,
    "hits": [
        {"_id": "12189", "_score": 23.003933, "symbol": "Brca1"},
        {"_id": "497672", "_score": 21.234402, "symbol": "Brca1"},
        {"_id": "449497", "_score": 17.695333, "symbol": "BRCA1"},
        {"_id": "373983", "_score": 17.695333, "symbol": "BRCA1"},
    ],
}

# A gene whose pathway data comes from Reactome (rare in MyGene.info; CD300LD, Entrez 100131439)
REACTOME_GENE = {
    "_id": "100131439",
    "entrezgene": "100131439",
    "symbol": "CD300LD",
    "name": "CD300 molecule like family member d",
    "taxid": 9606,
    "pathway": {
        "reactome": [
            {"id": "R-HSA-1280218", "name": "Adaptive Immune System"},
            {"id": "R-HSA-168256", "name": "Immune System"},
        ]
    },
}
