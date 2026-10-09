"""Trimmed real Enrichr responses (IL6 TNF IL1B CXCL8 CRP IFNG IL10), fetched 2026-10-09."""

DATASET_STATISTICS = {
    "statistics": [
        {
            "geneCoverage": 13362,
            "genesPerTerm": 275,
            "libraryName": "Genome_Browser_PWMs",
            "numTerms": 615,
            "categoryId": 1,
        },
        {"libraryName": "KEGG_2026", "numTerms": 345, "genesPerTerm": 100},
        {"noLibraryName": True},
        "junk",
    ],
    "categories": [],
}

ADD_LIST = '{\n"shortId": "de884570802902123951074e8b7a6586",\n"userListId": 139566674\n}'

# [rank, term, p-value, odds ratio, combined score, overlapping genes, adjusted p, old p, old adj p]
ENRICH_KEGG = {
    "KEGG_2026": [
        [
            2,
            "AMOEBIASIS",
            9.352582580771553e-14,
            1270.1489361702127,
            38105.15242218447,
            ["IL10", "IL6", "CXCL8", "IFNG", "IL1B", "TNF"],
            3.3276578585454918e-12,
            0,
            0,
        ],
        [
            1,
            "MALARIA",
            1.249267546276384e-15,
            2720.318181818182,
            93351.03441797469,
            ["IL10", "IL6", "CXCL8", "IFNG", "IL1B", "TNF"],
            1.1118481161859818e-13,
            0,
            0,
        ],
        [3, "SHORT ROW", 0.5, 1.0, 1.0],
        "junk",
        [4, 7, 0.5, 1.0, 1.0, [], 0.5],
        [
            5,
            "WEAK TERM",
            0.04,
            1.5,
            2.0,
            ["IL6"],
            0.3,
            0,
            0,
        ],
    ]
}

ENRICH_HPO = {
    "Human_Phenotype_Ontology": [
        [
            1,
            "Abnormality of the pericardium (HP:0001697)",
            6.577640515487366e-05,
            234.81176470588235,
            2261.0610369428987,
            ["IL10", "IL6"],
            0.0018558477957004884,
            0,
            0,
        ]
    ]
}

ENRICH_GO = {
    "GO_Biological_Process_2025": [
        [
            1,
            "Regulation of Interleukin-6 Production (GO:0032675)",
            1.0e-10,
            456.1,
            9000.0,
            ["IL10", "IL6", "TNF"],
            3.185553998576132e-08,
            0,
            0,
        ],
        [
            2,
            "Positive Regulation Of Cytokine Production (GO:0001819)",
            1.0e-9,
            300.0,
            5000.0,
            ["IL6", "TNF"],
            4.0e-07,
            0,
            0,
        ],
    ]
}

# geneSetLibrary?mode=text: "<term>\t<empty description>\t<gene>\t<gene>..."; the HPO line
# and the weighted line check the "GENE,weight" handling and blank cells.
LIBRARY_TEXT_KEGG = (
    "MALARIA\t\tACKR1\tSOS1\tTHBS3\tIL6\tTLR2\n"
    "AMOEBIASIS\t\tIL6\tTNF\t\tCXCL8\n"
    "WEIGHTED TERM\t\tIL6,1.0\tTNF,0.5\n"
    "BROKEN LINE\n"
    "\t\tNOTERM\n"
)

GENEMAP_BRCA1 = {
    "gene": {
        "GeneSigDB": ["18535662-TableS2d", "17072343-Table1"],
        "KEGG_2026": [
            "UBIQUITIN MEDIATED PROTEOLYSIS",
            "PI3K-AKT SIGNALING PATHWAY",
            "HOMOLOGOUS RECOMBINATION",
        ],
        "Human_Phenotype_Ontology": [
            "Abnormality of the peritoneum (HP:0002585)",
            "Constipation (HP:0002019)",
        ],
        "NotAList": "x",
    },
    "descriptions": [{"name": "GeneSigDB", "description": "x"}],
}

GENEMAP_EMPTY = {"gene": {}, "descriptions": []}
