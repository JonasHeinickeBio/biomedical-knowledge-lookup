"""Trimmed real PubTator 3 API responses (captured 2026-10 from the live API)."""

# GET /entity/autocomplete/?query=BRCA1&limit=3  (no concept filter -> mixed types)
AUTOCOMPLETE_BRCA1 = [
    {
        "_id": "@GENE_BRCA1",
        "biotype": "gene",
        "db_id": "672",
        "db": "ncbi_gene",
        "name": "BRCA1",
        "description": "All Species",
        "match": "Matched on name <m>BRCA1</m>",
    },
    {
        "_id": "@GENE_BRCA1.L",
        "biotype": "gene",
        "db_id": "399391",
        "db": "ncbi_gene",
        "name": "brca1.L",
        "description": "All Species",
        "match": "Matched on name <m>brca1.L</m>",
    },
    {
        "_id": "@VARIANT_c.5382insC_BRCA1_human",
        "biotype": "variant",
        "db_id": "#672#c.5382insC",
        "db": "litvar",
        "name": "c.5382insC",
        "description": "BRCA1 (human)",
        "match": "Multiple matches",
    },
]

# GET /entity/autocomplete/?query=fatigue&concept=DISEASE&limit=3
AUTOCOMPLETE_FATIGUE_DISEASE = [
    {
        "_id": "@DISEASE_Fatigue",
        "biotype": "disease",
        "db_id": "D005221",
        "db": "ncbi_mesh",
        "name": "Fatigue",
        "match": "Matched on name <m>Fatigue</m>",
    },
    {
        "_id": "@DISEASE_Fatigue_Syndrome_Chronic",
        "biotype": "disease",
        "db_id": "D015673",
        "db": "ncbi_mesh",
        "name": "Fatigue Syndrome Chronic",
        "match": "Matched on name <m>Fatigue Syndrome Chronic</m>",
    },
    {
        "_id": "@DISEASE_Voice_Disorders",
        "biotype": "disease",
        "db_id": "D014832",
        "db": "ncbi_mesh",
        "name": "Voice Disorders",
        "match": "Matched on synonyms <m>Fatigue, Voice</m>",
    },
]

# GET /entity/autocomplete/?query=Fatigue Syndrome Chronic&concept=DISEASE&limit=20
AUTOCOMPLETE_CFS_EXACT = [AUTOCOMPLETE_FATIGUE_DISEASE[1]]

# GET /entity/autocomplete/?query=aspirin&concept=CHEMICAL&limit=2
AUTOCOMPLETE_ASPIRIN_CHEMICAL = [
    {
        "_id": "@CHEMICAL_Aspirin",
        "biotype": "chemical",
        "db_id": "D001241",
        "db": "ncbi_mesh",
        "name": "Aspirin",
        "match": "Matched on name <m>Aspirin</m>",
    },
]

# GET /entity/autocomplete/?query=c.68_69del&concept=VARIANT&limit=20
AUTOCOMPLETE_VARIANT = [
    {
        "_id": "@VARIANT_c.68_69del_BRCA1_human",
        "biotype": "variant",
        "db_id": "#672#c.68_69del",
        "db": "litvar",
        "name": "c.68_69del",
        "description": "BRCA1 (human)",
        "match": "Matched on name <m>c.68_69del</m>",
    },
    {
        "_id": "@VARIANT_c.68_69delAG_BRCA1_human",
        "biotype": "variant",
        "db_id": "rs386833395##",
        "db": "litvar",
        "name": "p.E23V",
        "description": "BRCA1 (human)",
        "match": "Matched on synonyms <m>c.68_69del</m>",
    },
]

# GET /search/?text=@DISEASE_Fatigue_Syndrome_Chronic&page=1  (2 of 10 articles, trimmed)
SEARCH_CFS = {
    "results": [
        {
            "_id": "35046929",
            "pmid": 35046929,
            "pmcid": "PMC8761622",
            "title": "The Gut Microbiome in Myalgic Encephalomyelitis (ME)/Chronic Fatigue "
            "Syndrome (CFS)",
            "journal": "Front Immunol",
            "authors": ["König RS", "Albrich WC"],
            "date": "2022-01-03T00:00:00Z",
            "doi": "10.3389/fimmu.2021.628741",
            "score": 264.72842,
            "text_hl": "The Gut Microbiome in @<m>DISEASE_Fatigue_Syndrome_Chronic</m> "
            "@DISEASE_MESH:D015673 @@@Myalgic Encephalomyelitis@@@",
        },
        {
            "_id": "35432363",
            "pmid": 35432363,
            "pmcid": "PMC9010344",
            "title": "Erratum: The Gut Microbiome in Myalgic Encephalomyelitis (ME)/Chronic "
            "Fatigue Syndrome (CFS)",
            "journal": "Front Immunol",
            "date": "2022-04-04T00:00:00Z",
            "doi": "10.3389/fimmu.2022.896230",
            "score": 250.1,
            "text_hl": "Erratum",
        },
    ],
    "page_size": 10,
    "current": 1,
    "count": 25513,
    "total_pages": 2552,
}

# GET /search/?text=@DISEASE_MESH:D015673&page=1 -> highlighting is on the id token
SEARCH_BY_MESH = {
    "results": [
        {
            "_id": "35046929",
            "pmid": 35046929,
            "title": "The Gut Microbiome in Myalgic Encephalomyelitis (ME)/Chronic Fatigue "
            "Syndrome (CFS)",
            "text_hl": "The Gut Microbiome in @DISEASE_Fatigue_Syndrome_Chronic "
            "@<m>DISEASE_MESH:D015673</m> @@@Myalgic Encephalomyelitis@@@",
        }
    ],
    "total_pages": 1,
}

# GET /search/?text=@GENE_672&page=1
SEARCH_BY_GENE_ID = {
    "results": [
        {
            "_id": "34083286",
            "pmid": 34083286,
            "title": "BRCA1-BRCT Mutations Alter the Subcellular Localization of BRCA1 In Vitro.",
            "text_hl": "@GENE_BRCA1 @<m>GENE_672</m> @@@BRCA1@@@-BRCT Mutations Alter",
        }
    ],
    "total_pages": 1,
}

# GET /relations?e1=@DISEASE_Fatigue_Syndrome_Chronic  (first rows of 1228)
RELATIONS_CFS = [
    {
        "type": "treat",
        "source": "@CHEMICAL_Hydrocortisone",
        "target": "@DISEASE_Fatigue_Syndrome_Chronic",
        "publications": 47,
    },
    {
        "type": "associate",
        "source": "@DISEASE_Fatigue_Syndrome_Chronic",
        "target": "@GENE_RNASEL",
        "publications": 22,
    },
    {
        "type": "treat",
        "source": "@CHEMICAL_coenzyme_Q10",
        "target": "@DISEASE_Fatigue_Syndrome_Chronic",
        "publications": 22,
    },
    {
        "type": "stimulate",
        "source": "@DISEASE_Fatigue_Syndrome_Chronic",
        "target": "@GENE_TNF",
        "publications": 17,
    },
    {
        "type": "cause",
        "source": "@DISEASE_Fatigue_Syndrome_Chronic",
        "target": "@VARIANT_p.A1156T_SCN4A_human",
        "publications": 2,
    },
]

# GET /publications/export/biocjson?pmids=35046929 (annotations trimmed)
BIOC_35046929 = {
    "PubTator3": [
        {
            "_id": "35046929|None",
            "id": "35046929",
            "passages": [
                {
                    "text": "The Gut Microbiome in Myalgic Encephalomyelitis (ME)/Chronic Fatigue "
                    "Syndrome (CFS).",
                    "annotations": [
                        {
                            "id": "4",
                            "infons": {
                                "identifier": "MESH:D015673",
                                "type": "Disease",
                                "name": "Fatigue Syndrome Chronic",
                                "accession": "@DISEASE_Fatigue_Syndrome_Chronic",
                            },
                            "text": "Myalgic Encephalomyelitis",
                        },
                        {
                            "id": "5",
                            "infons": {
                                "identifier": "MESH:D015673",
                                "type": "Disease",
                                "name": "Fatigue Syndrome Chronic",
                                "accession": "@DISEASE_Fatigue_Syndrome_Chronic",
                            },
                            "text": "ME",
                        },
                        {
                            "id": "6",
                            "infons": {
                                "identifier": "MESH:D015673",
                                "type": "Disease",
                                "name": "Fatigue Syndrome Chronic",
                                "accession": "@DISEASE_Fatigue_Syndrome_Chronic",
                            },
                            "text": "ME",
                        },
                    ],
                }
            ],
        }
    ]
}
