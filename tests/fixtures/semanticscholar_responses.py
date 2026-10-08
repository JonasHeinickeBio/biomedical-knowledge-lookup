"""Trimmed real Semantic Scholar Graph API responses (recorded 2026-10-08).

PAPER_DAVIS, REFERENCES_DAVIS (first 5) and CITATIONS_DAVIS (first 5) are real responses for
DOI:10.1038/s41579-022-00846-2 (abstract shortened; the top-level ``citingPaperInfo`` block
of the references response, a copy of the paper itself, is dropped).
SEARCH_LONG_COVID could NOT be recorded live (paper/search answered HTTP 429 every time);
it follows the documented shape {total, offset, next, data: [paper...]} and reuses the real
paper record above plus one synthetic hit.
"""

PAPER_DAVIS = {
    "paperId": "e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6",
    "externalIds": {
        "PubMedCentral": "9839201",
        "DOI": "10.1038/s41579-022-00846-2",
        "CorpusId": 255800506,
        "PubMed": "36639608",
    },
    "corpusId": 255800506,
    "url": "https://www.semanticscholar.org/paper/e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6",
    "title": "Long COVID: major findings, mechanisms and recommendations",
    "venue": "Nature Reviews Microbiology",
    "year": 2023,
    "referenceCount": 223,
    "citationCount": 3472,
    "influentialCitationCount": 166,
    "isOpenAccess": True,
    "openAccessPdf": {
        "url": "https://www.nature.com/articles/s41579-022-00846-2.pdf",
        "status": "BRONZE",
        "license": None,
        "disclaimer": "Notice: Paper or abstract available at "
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC9839201 ...",
    },
    "fieldsOfStudy": ["Medicine"],
    "tldr": {
        "model": "tldr@v2.0.0",
        "text": "To strengthen long COVID research, future studies must account for biases "
        "and SARS-CoV-2 testing issues, build on viral-onset research, be inclusive "
        "of marginalized populations and meaningfully engage patients throughout the "
        "research process.",
    },
    "publicationTypes": ["Review", "JournalArticle"],
    "publicationDate": "2023-01-13",
    "authors": [
        {"authorId": "152162201", "name": "Hannah E. Davis"},
        {"authorId": "122252945", "name": "L. McCorkell"},
        {"authorId": "47522740", "name": "J. Vogel"},
        {"authorId": "144758045", "name": "E. Topol"},
    ],
    "abstract": "Long COVID is an often debilitating illness that occurs in at least 10% of "
    "severe acute respiratory syndrome coronavirus\xa02 (SARS-CoV-2) infections. More "
    "than 200 symptoms have been identified with impacts on multiple organ systems. "
    "At least 65 million individuals worldwide are estimated to have long COVID, with "
    "cases increasing daily. Biomedical research has made substantial progress in "
    "identifying various ...",
}

REFERENCES_DAVIS = {
    "offset": 0,
    "next": 5,
    "data": [
        {
            "isInfluential": False,
            "citedPaper": {
                "paperId": "fdb535c517dad226dff562fcc222d76b39695f11",
                "externalIds": {"DOI": "10.1101/2022.11.03.22281783", "CorpusId": 253350654},
                "title": "Nirmatrelvir and the Risk of Post-Acute Sequelae of COVID-19",
                "year": 2022,
            },
        },
        {
            "isInfluential": False,
            "citedPaper": {
                "paperId": "a029ef6b4632918d70296f95e71cf2820cec8fed",
                "externalIds": {
                    "PubMedCentral": "9671810",
                    "DOI": "10.1038/s41591-022-02051-3",
                    "CorpusId": 253458538,
                    "PubMed": "36357676",
                },
                "title": "Acute and postacute sequelae associated with SARS-CoV-2 reinfection",
                "year": 2022,
            },
        },
        {
            "isInfluential": False,
            "citedPaper": {
                "paperId": "d8a91108266de47190433b55bc268bd78c96968b",
                "externalIds": {
                    "PubMedCentral": "9699059",
                    "DOI": "10.3390/metabo12111026",
                    "CorpusId": 253175811,
                    "PubMed": "36355108",
                },
                "title": "Signatures of Mitochondrial Dysfunction and Impaired Fatty "
                "Acid Metabolism in Plasma of Patients with Post-Acute "
                "Sequelae of COVID-19 (PASC)",
                "year": 2022,
            },
        },
        {
            "isInfluential": False,
            "citedPaper": {
                "paperId": "2137d5a0d1c9c48f1c8df8a80cab2b92ad00ba59",
                "externalIds": {
                    "PubMedCentral": "9549814",
                    "DOI": "10.1186/s10020-022-00548-8",
                    "CorpusId": 252764854,
                    "PubMed": "36217108",
                },
                "title": "Elevated vascular transformation blood biomarkers in "
                "Long-COVID indicate angiogenesis as a key "
                "pathophysiological mechanism",
                "year": 2022,
            },
        },
        {
            "isInfluential": False,
            "citedPaper": {
                "paperId": "026beaeafd23587731175cb856d3aa4860075802",
                "externalIds": {
                    "PubMedCentral": "9602265",
                    "DOI": "10.3390/healthcare10102058",
                    "CorpusId": 253013739,
                    "PubMed": "36292504",
                },
                "title": "Orthostatic Intolerance in Long-Haul COVID after "
                "SARS-CoV-2: A Case-Control Comparison with Post-EBV and "
                "Insidious-Onset Myalgic Encephalomyelitis/Chronic Fatigue "
                "Syndrome Patients",
                "year": 2022,
            },
        },
    ],
}

CITATIONS_DAVIS = {
    "offset": 0,
    "next": 5,
    "data": [
        {
            "isInfluential": False,
            "citingPaper": {
                "paperId": "ecd0efb7b10a44f381131d45e1fa0cb4acc9a0a2",
                "externalIds": {"DOI": "10.51952/9781447378938", "CorpusId": 292372169},
                "title": "Understanding the Complexity of Pacing in Long Covid",
                "year": 2026,
            },
        },
        {
            "isInfluential": False,
            "citingPaper": {
                "paperId": "c152b7cba910c0fe9850c2a3cb0b322c236c329e",
                "externalIds": {
                    "DOI": "10.1016/j.bbi.2026.107038",
                    "CorpusId": 292578094,
                    "PubMed": "42826923",
                },
                "title": "Choroid plexus enlargement in Post-COVID-19 syndrome is "
                "linked to Serum-Induced cytokine secretion in human "
                "hippocampal progenitors.",
                "year": 2026,
            },
        },
        {
            "isInfluential": False,
            "citingPaper": {
                "paperId": "1b2e3daf200744d2b00f64e516bcf7166b4e166a",
                "externalIds": {"DOI": "10.1016/j.mex.2026.104190", "CorpusId": 292625208},
                "title": "Simultaneous determination of serotonin and its precursor "
                "tryptophan in small volumes of human serum using HPLC-ECD",
                "year": 2026,
            },
        },
        {
            "isInfluential": False,
            "citingPaper": {
                "paperId": "2eda3f57cddca7b46804ca4014cf2f56bee6c7d2",
                "externalIds": {"DOI": "10.3390/covid6100172", "CorpusId": 292552546},
                "title": "Long COVID in Older Adults: A Geriatric Framework for "
                "Pathophysiology, Frailty, Functional Decline, and "
                "Clinical Management—A Narrative Review",
                "year": 2026,
            },
        },
        {
            "isInfluential": False,
            "citingPaper": {
                "paperId": "136d1b670d1708b7dc50710b76fd5ea0dd9db9cd",
                "externalIds": {"DOI": "10.3390/su18199956", "CorpusId": 292508270},
                "title": "Performance Determinants and Improvement Paths for "
                "Sustainable Marine Emergency Interconnection Under "
                "Persistent Public-Health Stress",
                "year": 2026,
            },
        },
    ],
}

SEARCH_LONG_COVID = {
    "total": 3,
    "offset": 0,
    "next": 3,
    "data": [
        {
            "paperId": "e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6",
            "externalIds": {
                "PubMedCentral": "9839201",
                "DOI": "10.1038/s41579-022-00846-2",
                "CorpusId": 255800506,
                "PubMed": "36639608",
            },
            "corpusId": 255800506,
            "url": "https://www.semanticscholar.org/paper/e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6",
            "title": "Long COVID: major findings, mechanisms and recommendations",
            "venue": "Nature Reviews Microbiology",
            "year": 2023,
            "referenceCount": 223,
            "citationCount": 3472,
            "influentialCitationCount": 166,
            "isOpenAccess": True,
            "openAccessPdf": {
                "url": "https://www.nature.com/articles/s41579-022-00846-2.pdf",
                "status": "BRONZE",
                "license": None,
                "disclaimer": "Notice: Paper or abstract available at "
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC9839201 "
                "...",
            },
            "fieldsOfStudy": ["Medicine"],
            "tldr": {
                "model": "tldr@v2.0.0",
                "text": "To strengthen long COVID research, future studies must account "
                "for biases and SARS-CoV-2 testing issues, build on viral-onset "
                "research, be inclusive of marginalized populations and "
                "meaningfully engage patients throughout the research process.",
            },
            "publicationTypes": ["Review", "JournalArticle"],
            "publicationDate": "2023-01-13",
            "authors": [
                {"authorId": "152162201", "name": "Hannah E. Davis"},
                {"authorId": "122252945", "name": "L. McCorkell"},
                {"authorId": "47522740", "name": "J. Vogel"},
                {"authorId": "144758045", "name": "E. Topol"},
            ],
            "abstract": "Long COVID is an often debilitating illness that occurs in at least "
            "10% of severe acute respiratory syndrome coronavirus\xa02 (SARS-CoV-2) "
            "infections. More than 200 symptoms have been identified with impacts "
            "on multiple organ systems. At least 65 million individuals worldwide "
            "are estimated to have long COVID, with cases increasing daily. "
            "Biomedical research has made substantial progress in identifying "
            "various ...",
        },
        {
            "paperId": "0000000000000000000000000000000000000000",
            "externalIds": {"CorpusId": 1},
            "corpusId": 255800506,
            "url": "https://www.semanticscholar.org/paper/e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6",
            "title": "Placeholder second hit",
            "venue": "Nature Reviews Microbiology",
            "year": 2023,
            "referenceCount": 223,
            "citationCount": 3472,
            "influentialCitationCount": 166,
            "isOpenAccess": True,
            "openAccessPdf": None,
            "fieldsOfStudy": ["Medicine"],
            "tldr": None,
            "publicationTypes": ["Review", "JournalArticle"],
            "publicationDate": "2023-01-13",
            "authors": [
                {"authorId": "152162201", "name": "Hannah E. Davis"},
                {"authorId": "122252945", "name": "L. McCorkell"},
                {"authorId": "47522740", "name": "J. Vogel"},
                {"authorId": "144758045", "name": "E. Topol"},
            ],
            "abstract": None,
        },
    ],
}
