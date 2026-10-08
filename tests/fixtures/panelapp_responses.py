"""Trimmed real PanelApp responses (Genomics England, fetched 2026-10-08)."""

PANELS_PAGE = {
    "count": 4,
    "next": None,
    "previous": None,
    "results": [
        {
            "id": 477,
            "hash_id": None,
            "name": "Ataxia and cerebellar anomalies - childhood onset",
            "disease_group": "Neurology",
            "disease_sub_group": "",
            "status": "public",
            "version": "9.38",
            "version_created": "2026-10-07T13:21:42.431612Z",
            "relevant_disorders": ["Ataxia and cerebellar anomalies - narrow panel"],
            "stats": {"number_of_genes": 330, "number_of_strs": 16, "number_of_regions": 4},
            "types": [
                {
                    "name": "Component Of Super Panel",
                    "slug": "component-of-super-panel",
                    "description": "This panel is a component of a Super Panel",
                },
                {
                    "name": "GMS signed-off",
                    "slug": "gms-signed-off",
                    "description": "This panel has undergone review by a NHSE GMS disease "
                    "specialist group and processes to be signed-off for "
                    "use within the GMS.",
                },
            ],
        },
        {
            "id": 1213,
            "hash_id": None,
            "name": "Ataxia telangiectasia - mutation testing",
            "disease_group": "Neurology",
            "disease_sub_group": "",
            "status": "public",
            "version": "1.5",
            "version_created": "2026-08-12T16:08:13.969357Z",
            "relevant_disorders": ["R295", "GT65", "TP621"],
            "stats": {"number_of_genes": 1, "number_of_strs": 0, "number_of_regions": 0},
            "types": [
                {
                    "name": "GMS Rare Disease",
                    "slug": "gms-rare-disease",
                    "description": "This panel type is used for GMS panels that are not "
                    "virtual (i.e. could be a wet lab test)",
                },
                {
                    "name": "GMS signed-off",
                    "slug": "gms-signed-off",
                    "description": "This panel has undergone review by a NHSE GMS disease "
                    "specialist group and processes to be signed-off for "
                    "use within the GMS.",
                },
            ],
        },
        {
            "id": 20,
            "hash_id": "559a7d1022c1fc58ad67fc97",
            "name": "Hereditary ataxia",
            "disease_group": "Neurology and neurodevelopmental disorders",
            "disease_sub_group": "Motor Disorders of the CNS",
            "status": "public",
            "version": "1.345",
            "version_created": "2026-05-01T14:28:12.522359Z",
            "relevant_disorders": [],
            "stats": {"number_of_genes": 168, "number_of_strs": 14, "number_of_regions": 3},
            "types": [
                {
                    "name": "Rare Disease 100K",
                    "slug": "rare-disease-100k",
                    "description": "Rare Disease 100K",
                }
            ],
        },
        {
            "id": 158,
            "hash_id": "55b62bc422c1fc05fc7a1857",
            "name": "Familial breast cancer",
            "disease_group": "Tumour syndromes",
            "disease_sub_group": "Breast and endocrine",
            "status": "public",
            "version": "1.28",
            "version_created": "2025-11-23T17:04:04.323318Z",
            "relevant_disorders": ["Familial breast and or ovarian cancer"],
            "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
            "types": [
                {
                    "name": "Rare Disease 100K",
                    "slug": "rare-disease-100k",
                    "description": "Rare Disease 100K",
                }
            ],
        },
    ],
}

PANEL_158_DETAIL = {
    "id": 158,
    "hash_id": "55b62bc422c1fc05fc7a1857",
    "name": "Familial breast cancer",
    "disease_group": "Tumour syndromes",
    "disease_sub_group": "Breast and endocrine",
    "status": "public",
    "version": "1.28",
    "version_created": "2025-11-23T17:04:04.323318Z",
    "relevant_disorders": ["Familial breast and or ovarian cancer"],
    "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
    "types": [
        {
            "name": "Rare Disease 100K",
            "slug": "rare-disease-100k",
            "description": "Rare Disease 100K",
        }
    ],
    "genes": [
        {
            "gene_data": {
                "alias": ["TEL1", "TELO1"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:795",
                "gene_name": "ATM serine/threonine kinase",
                "omim_gene": ["607585"],
                "alias_name": ["TEL1, telomere maintenance 1, homolog (S. cerevisiae)"],
                "gene_symbol": "ATM",
                "hgnc_symbol": "ATM",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {
                            "location": "11:108093211-108239829",
                            "ensembl_id": "ENSG00000149311",
                        }
                    },
                    "GRch38": {
                        "90": {
                            "location": "11:108222484-108369102",
                            "ensembl_id": "ENSG00000149311",
                        }
                    },
                },
                "hgnc_date_symbol_changed": "1995-07-07",
            },
            "entity_type": "gene",
            "entity_name": "ATM",
            "confidence_level": "3",
            "penetrance": "Incomplete",
            "mode_of_pathogenicity": "",
            "publications": ["19781682"],
            "evidence": ["Expert Review Green", "Emory Genetics Laboratory"],
            "phenotypes": ["{Breast cancer, susceptibility to}, OMIM:114480"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted",
            "tags": [],
            "transcript": None,
        },
        {
            "gene_data": {
                "alias": [],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:952",
                "gene_name": "BRCA1 associated RING domain 1",
                "omim_gene": ["601593"],
                "alias_name": None,
                "gene_symbol": "BARD1",
                "hgnc_symbol": "BARD1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {
                            "location": "2:215590370-215674428",
                            "ensembl_id": "ENSG00000138376",
                        }
                    },
                    "GRch38": {
                        "90": {
                            "location": "2:214725646-214809711",
                            "ensembl_id": "ENSG00000138376",
                        }
                    },
                },
                "hgnc_date_symbol_changed": "1998-08-05",
            },
            "entity_type": "gene",
            "entity_name": "BARD1",
            "confidence_level": "3",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": ["33471991", "37592023", "15342711"],
            "evidence": ["Expert Review Green", "Illumina TruGenome Clinical Sequencing Services"],
            "phenotypes": ["{Breast cancer, susceptibility to}, OMIM:114480"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted",
            "tags": [],
            "transcript": None,
        },
        {
            "gene_data": {
                "alias": ["FLJ12343", "MGC20625", "MGC21482", "MGC26740"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:33499",
                "gene_name": "ATR interacting protein",
                "omim_gene": ["606605"],
                "alias_name": None,
                "gene_symbol": "ATRIP",
                "hgnc_symbol": "ATRIP",
                "hgnc_release": "2017-11-03",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "3:48488114-48507115", "ensembl_id": "ENSG00000164053"}
                    },
                    "GRch38": {
                        "90": {"location": "3:48446710-48465716", "ensembl_id": "ENSG00000164053"}
                    },
                },
                "hgnc_date_symbol_changed": "2007-06-20",
            },
            "entity_type": "gene",
            "entity_name": "ATRIP",
            "confidence_level": "2",
            "penetrance": None,
            "mode_of_pathogenicity": None,
            "publications": ["36977412"],
            "evidence": ["Expert Review Amber", "Literature"],
            "phenotypes": ["Hereditary breast cancer"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, imprinted "
            "status unknown",
            "tags": [],
            "transcript": None,
        },
        {
            "gene_data": {
                "alias": ["AIS", "NR3C4", "SMAX1", "HUMARA"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:644",
                "gene_name": "androgen receptor",
                "omim_gene": ["313700"],
                "alias_name": ["testicular feminization", "Kennedy disease"],
                "gene_symbol": "AR",
                "hgnc_symbol": "AR",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "X:66764465-66950461", "ensembl_id": "ENSG00000169083"}
                    },
                    "GRch38": {
                        "90": {"location": "X:67544032-67730619", "ensembl_id": "ENSG00000169083"}
                    },
                },
                "hgnc_date_symbol_changed": "1986-01-01",
            },
            "entity_type": "gene",
            "entity_name": "AR",
            "confidence_level": "1",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": [],
            "evidence": ["Expert Review Red", "Radboud University Medical Center, Nijmegen"],
            "phenotypes": [
                "Androgen insensitivity, partial, with or without breast cancer, OMIM:312300"
            ],
            "mode_of_inheritance": "",
            "tags": [],
            "transcript": None,
        },
        {
            "gene_data": {
                "alias": ["OF", "BACH1", "FANCJ"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:20473",
                "gene_name": "BRCA1 interacting protein C-terminal helicase 1",
                "omim_gene": ["605882"],
                "alias_name": ["BRCA1/BRCA2-associated helicase 1"],
                "gene_symbol": "BRIP1",
                "hgnc_symbol": "BRIP1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "17:59758627-59940882", "ensembl_id": "ENSG00000136492"}
                    },
                    "GRch38": {
                        "90": {"location": "17:61681266-61863521", "ensembl_id": "ENSG00000136492"}
                    },
                },
                "hgnc_date_symbol_changed": "2003-04-11",
            },
            "entity_type": "gene",
            "entity_name": "BRIP1",
            "confidence_level": "1",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": [],
            "evidence": ["Expert Review Red", "Illumina TruGenome Clinical Sequencing Services"],
            "phenotypes": ["{Breast cancer, early-onset, susceptibility to}, OMIM:114480"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, imprinted "
            "status unknown",
            "tags": [],
            "transcript": None,
        },
    ],
    "strs": [],
    "regions": [],
}

PANEL_158_GREEN_GENES = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "gene_data": {
                "alias": ["TEL1", "TELO1"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:795",
                "gene_name": "ATM serine/threonine kinase",
                "omim_gene": ["607585"],
                "alias_name": ["TEL1, telomere maintenance 1, homolog (S. cerevisiae)"],
                "gene_symbol": "ATM",
                "hgnc_symbol": "ATM",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {
                            "location": "11:108093211-108239829",
                            "ensembl_id": "ENSG00000149311",
                        }
                    },
                    "GRch38": {
                        "90": {
                            "location": "11:108222484-108369102",
                            "ensembl_id": "ENSG00000149311",
                        }
                    },
                },
                "hgnc_date_symbol_changed": "1995-07-07",
            },
            "entity_type": "gene",
            "entity_name": "ATM",
            "confidence_level": "3",
            "penetrance": "Incomplete",
            "mode_of_pathogenicity": "",
            "publications": ["19781682"],
            "evidence": ["Expert Review Green", "Emory Genetics Laboratory"],
            "phenotypes": ["{Breast cancer, susceptibility to}, OMIM:114480"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted",
            "tags": [],
            "transcript": None,
            "panel": {
                "id": 158,
                "hash_id": "55b62bc422c1fc05fc7a1857",
                "name": "Familial breast cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.28",
                "version_created": "2025-11-23T17:04:04.323318Z",
                "relevant_disorders": ["Familial breast and or ovarian cancer"],
                "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
        },
        {
            "gene_data": {
                "alias": [],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:952",
                "gene_name": "BRCA1 associated RING domain 1",
                "omim_gene": ["601593"],
                "alias_name": None,
                "gene_symbol": "BARD1",
                "hgnc_symbol": "BARD1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {
                            "location": "2:215590370-215674428",
                            "ensembl_id": "ENSG00000138376",
                        }
                    },
                    "GRch38": {
                        "90": {
                            "location": "2:214725646-214809711",
                            "ensembl_id": "ENSG00000138376",
                        }
                    },
                },
                "hgnc_date_symbol_changed": "1998-08-05",
            },
            "entity_type": "gene",
            "entity_name": "BARD1",
            "confidence_level": "3",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": ["33471991", "37592023", "15342711"],
            "evidence": ["Expert Review Green", "Illumina TruGenome Clinical Sequencing Services"],
            "phenotypes": ["{Breast cancer, susceptibility to}, OMIM:114480"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted",
            "tags": [],
            "transcript": None,
            "panel": {
                "id": 158,
                "hash_id": "55b62bc422c1fc05fc7a1857",
                "name": "Familial breast cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.28",
                "version_created": "2025-11-23T17:04:04.323318Z",
                "relevant_disorders": ["Familial breast and or ovarian cancer"],
                "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
        },
    ],
}

PANEL_158_AMBER_GENES = {
    "count": 1,
    "next": None,
    "previous": None,
    "results": [
        {
            "gene_data": {
                "alias": ["FLJ12343", "MGC20625", "MGC21482", "MGC26740"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:33499",
                "gene_name": "ATR interacting protein",
                "omim_gene": ["606605"],
                "alias_name": None,
                "gene_symbol": "ATRIP",
                "hgnc_symbol": "ATRIP",
                "hgnc_release": "2017-11-03",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "3:48488114-48507115", "ensembl_id": "ENSG00000164053"}
                    },
                    "GRch38": {
                        "90": {"location": "3:48446710-48465716", "ensembl_id": "ENSG00000164053"}
                    },
                },
                "hgnc_date_symbol_changed": "2007-06-20",
            },
            "entity_type": "gene",
            "entity_name": "ATRIP",
            "confidence_level": "2",
            "penetrance": None,
            "mode_of_pathogenicity": None,
            "publications": ["36977412"],
            "evidence": ["Expert Review Amber", "Literature"],
            "phenotypes": ["Hereditary breast cancer"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, imprinted "
            "status unknown",
            "tags": [],
            "transcript": None,
            "panel": {
                "id": 158,
                "hash_id": "55b62bc422c1fc05fc7a1857",
                "name": "Familial breast cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.28",
                "version_created": "2025-11-23T17:04:04.323318Z",
                "relevant_disorders": ["Familial breast and or ovarian cancer"],
                "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
        }
    ],
}

PANEL_158_RED_GENES = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "gene_data": {
                "alias": ["AIS", "NR3C4", "SMAX1", "HUMARA"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:644",
                "gene_name": "androgen receptor",
                "omim_gene": ["313700"],
                "alias_name": ["testicular feminization", "Kennedy disease"],
                "gene_symbol": "AR",
                "hgnc_symbol": "AR",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "X:66764465-66950461", "ensembl_id": "ENSG00000169083"}
                    },
                    "GRch38": {
                        "90": {"location": "X:67544032-67730619", "ensembl_id": "ENSG00000169083"}
                    },
                },
                "hgnc_date_symbol_changed": "1986-01-01",
            },
            "entity_type": "gene",
            "entity_name": "AR",
            "confidence_level": "1",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": [],
            "evidence": ["Expert Review Red", "Radboud University Medical Center, Nijmegen"],
            "phenotypes": [
                "Androgen insensitivity, partial, with or without breast cancer, OMIM:312300"
            ],
            "mode_of_inheritance": "",
            "tags": [],
            "transcript": None,
            "panel": {
                "id": 158,
                "hash_id": "55b62bc422c1fc05fc7a1857",
                "name": "Familial breast cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.28",
                "version_created": "2025-11-23T17:04:04.323318Z",
                "relevant_disorders": ["Familial breast and or ovarian cancer"],
                "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
        },
        {
            "gene_data": {
                "alias": ["OF", "BACH1", "FANCJ"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:20473",
                "gene_name": "BRCA1 interacting protein C-terminal helicase 1",
                "omim_gene": ["605882"],
                "alias_name": ["BRCA1/BRCA2-associated helicase 1"],
                "gene_symbol": "BRIP1",
                "hgnc_symbol": "BRIP1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "17:59758627-59940882", "ensembl_id": "ENSG00000136492"}
                    },
                    "GRch38": {
                        "90": {"location": "17:61681266-61863521", "ensembl_id": "ENSG00000136492"}
                    },
                },
                "hgnc_date_symbol_changed": "2003-04-11",
            },
            "entity_type": "gene",
            "entity_name": "BRIP1",
            "confidence_level": "1",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": [],
            "evidence": ["Expert Review Red", "Illumina TruGenome Clinical Sequencing Services"],
            "phenotypes": ["{Breast cancer, early-onset, susceptibility to}, OMIM:114480"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, imprinted "
            "status unknown",
            "tags": [],
            "transcript": None,
            "panel": {
                "id": 158,
                "hash_id": "55b62bc422c1fc05fc7a1857",
                "name": "Familial breast cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.28",
                "version_created": "2025-11-23T17:04:04.323318Z",
                "relevant_disorders": ["Familial breast and or ovarian cancer"],
                "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
        },
    ],
}

BRCA1_GENE_RECORDS = {
    "count": 4,
    "next": None,
    "previous": None,
    "results": [
        {
            "gene_data": {
                "alias": ["RNF53", "BRCC1", "PPP1R53", "FANCS"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:1100",
                "gene_name": "BRCA1, DNA repair associated",
                "omim_gene": ["113705"],
                "alias_name": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "protein phosphatase 1, regulatory subunit 53",
                    "Fanconi anemia, complementation group S",
                ],
                "gene_symbol": "BRCA1",
                "hgnc_symbol": "BRCA1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "17:41196312-41277500", "ensembl_id": "ENSG00000012048"}
                    },
                    "GRch38": {
                        "90": {"location": "17:43044295-43170245", "ensembl_id": "ENSG00000012048"}
                    },
                },
                "hgnc_date_symbol_changed": "1991-02-20",
            },
            "entity_type": "gene",
            "entity_name": "BRCA1",
            "confidence_level": "3",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": [],
            "evidence": ["Expert Review Green", "Eligibility statement prior genetic testing"],
            "phenotypes": ["{Breast-ovarian cancer, familial, 1}, OMIM:604370"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted",
            "tags": ["watchlist_moi"],
            "panel": {
                "id": 158,
                "hash_id": "55b62bc422c1fc05fc7a1857",
                "name": "Familial breast cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.28",
                "version_created": "2025-11-23T17:04:04.323318Z",
                "relevant_disorders": ["Familial breast and or ovarian cancer"],
                "stats": {"number_of_genes": 27, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
            "transcript": None,
        },
        {
            "gene_data": {
                "alias": ["RNF53", "BRCC1", "PPP1R53", "FANCS"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:1100",
                "gene_name": "BRCA1, DNA repair associated",
                "omim_gene": ["113705"],
                "alias_name": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "protein phosphatase 1, regulatory subunit 53",
                    "Fanconi anemia, complementation group S",
                ],
                "gene_symbol": "BRCA1",
                "hgnc_symbol": "BRCA1",
                "hgnc_release": "2017-11-03",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "17:41196312-41277500", "ensembl_id": "ENSG00000012048"}
                    },
                    "GRch38": {
                        "90": {"location": "17:43044295-43170245", "ensembl_id": "ENSG00000012048"}
                    },
                },
                "hgnc_date_symbol_changed": "1991-02-20",
            },
            "entity_type": "gene",
            "entity_name": "BRCA1",
            "confidence_level": "3",
            "penetrance": None,
            "mode_of_pathogenicity": None,
            "publications": [],
            "evidence": ["Expert list", "Expert Review Green"],
            "phenotypes": [
                "{Breast-ovarian cancer, familial, 1}, OMIM:604370",
                "Breast and ovarian cancer predisposition",
                "Adult only",
            ],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, imprinted "
            "status unknown",
            "tags": ["adult-onset"],
            "panel": {
                "id": 399,
                "hash_id": None,
                "name": "Additional findings health related",
                "disease_group": "",
                "disease_sub_group": "",
                "status": "public",
                "version": "0.116",
                "version_created": "2025-10-13T20:24:54.630497Z",
                "relevant_disorders": [],
                "stats": {"number_of_genes": 14, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Additional Findings",
                        "slug": "additional-findings",
                        "description": "This is a gene panel that maybe used for "
                        "additional findings.",
                    }
                ],
            },
            "transcript": ["ENST00000357654.8", "NM_007294.3"],
        },
        {
            "gene_data": {
                "alias": ["RNF53", "BRCC1", "PPP1R53", "FANCS"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:1100",
                "gene_name": "BRCA1, DNA repair associated",
                "omim_gene": ["113705"],
                "alias_name": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "protein phosphatase 1, regulatory subunit 53",
                    "Fanconi anemia, complementation group S",
                ],
                "gene_symbol": "BRCA1",
                "hgnc_symbol": "BRCA1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "17:41196312-41277500", "ensembl_id": "ENSG00000012048"}
                    },
                    "GRch38": {
                        "90": {"location": "17:43044295-43170245", "ensembl_id": "ENSG00000012048"}
                    },
                },
                "hgnc_date_symbol_changed": "1991-02-20",
            },
            "entity_type": "gene",
            "entity_name": "BRCA1",
            "confidence_level": "2",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": [
                "27989354",
                "27899188",
                "27742670",
                "27433846",
                "27317574",
                "27306910 - standardized incidence ratios (SIRs) were used to "
                "compare the observed incidence of 20 primary cancer sites to "
                "the expected incidence of each cancer based on the calculated "
                "risk estimates according to each subject's age, sex, and "
                "ethnicity. BRCA1 families had increased SIRs for breast and "
                "ovarian cancer (p < .001) and decreased SIRs for kidney, lung, "
                "prostate, and thyroid cancer and non-Hodgkin's lymphoma (p < "
                ".001)",
                "27188668",
                "26926928",
                "26360800 - no increased risk",
                "26236408 - literature review indicating there is conflicting reports",
                "22516946",
                "28031937",
            ],
            "evidence": ["Expert Review Amber", "Expert list"],
            "phenotypes": ["Prostate cancer, MONDO:0008315"],
            "mode_of_inheritance": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted",
            "tags": [],
            "panel": {
                "id": 318,
                "hash_id": "5763f2bf8f620350a1996047",
                "name": "Familial prostate cancer",
                "disease_group": "",
                "disease_sub_group": "",
                "status": "public",
                "version": "1.4",
                "version_created": "2025-11-23T17:11:23.782466Z",
                "relevant_disorders": [],
                "stats": {"number_of_genes": 14, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
            "transcript": None,
        },
        {
            "gene_data": {
                "alias": ["RNF53", "BRCC1", "PPP1R53", "FANCS"],
                "biotype": "protein_coding",
                "hgnc_id": "HGNC:1100",
                "gene_name": "BRCA1, DNA repair associated",
                "omim_gene": ["113705"],
                "alias_name": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "protein phosphatase 1, regulatory subunit 53",
                    "Fanconi anemia, complementation group S",
                ],
                "gene_symbol": "BRCA1",
                "hgnc_symbol": "BRCA1",
                "hgnc_release": "2017-11-03T00:00:00",
                "ensembl_genes": {
                    "GRch37": {
                        "82": {"location": "17:41196312-41277500", "ensembl_id": "ENSG00000012048"}
                    },
                    "GRch38": {
                        "90": {"location": "17:43044295-43170245", "ensembl_id": "ENSG00000012048"}
                    },
                },
                "hgnc_date_symbol_changed": "1991-02-20",
            },
            "entity_type": "gene",
            "entity_name": "BRCA1",
            "confidence_level": "1",
            "penetrance": "Complete",
            "mode_of_pathogenicity": "",
            "publications": ["26530882"],
            "evidence": ["Literature"],
            "phenotypes": ["Non-medullary thyroid cancer"],
            "mode_of_inheritance": "Unknown",
            "tags": [],
            "panel": {
                "id": 171,
                "hash_id": "576cd7ca8f6203609632be82",
                "name": "Inherited non-medullary thyroid cancer",
                "disease_group": "Tumour syndromes",
                "disease_sub_group": "Breast and endocrine",
                "status": "public",
                "version": "1.8",
                "version_created": "2025-11-23T17:26:22.213617Z",
                "relevant_disorders": [],
                "stats": {"number_of_genes": 30, "number_of_strs": 0, "number_of_regions": 0},
                "types": [
                    {
                        "name": "Rare Disease 100K",
                        "slug": "rare-disease-100k",
                        "description": "Rare Disease 100K",
                    }
                ],
            },
            "transcript": None,
        },
    ],
}

HGNC_FETCH_BRCA1 = {
    "responseHeader": {"status": 0, "QTime": 1},
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {"hgnc_id": "HGNC:1100", "symbol": "BRCA1", "name": "BRCA1 DNA repair associated"}
        ],
    },
}
