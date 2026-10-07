"""Real (trimmed) GWAS Catalog REST API v2 responses captured live from
https://www.ebi.ac.uk/gwas/rest/api/v2 (2026-10). Verbatim, except that the two ``*_COUNT``
fixtures keep only the ``page`` block (the tests only read ``page.totalElements``).
"""

SEARCH_FATIGUE = {
    "_embedded": {
        "efo_traits": [
            {
                "efo_trait": "fatigue",
                "uri": "http://purl.obolibrary.org/obo/HP_0012378",
                "efo_id": "HP_0012378",
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/efo-traits/HP_0012378"
                    }
                },
            },
            {
                "efo_trait": "myalgic encephalomeyelitis/chronic fatigue syndrome",
                "uri": "http://purl.obolibrary.org/obo/MONDO_0005404",
                "efo_id": "MONDO_0005404",
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/efo-traits/MONDO_0005404"
                    }
                },
            },
        ]
    },
    "_links": {
        "self": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/efo-traits?efo_trait=fatigue&page=0&size=5"
        }
    },
    "page": {"size": 5, "totalElements": 2, "totalPages": 1, "number": 0},
}

TRAIT_MECFS = {
    "efo_trait": "myalgic encephalomeyelitis/chronic fatigue syndrome",
    "uri": "http://purl.obolibrary.org/obo/MONDO_0005404",
    "efo_id": "MONDO_0005404",
    "_links": {
        "self": {"href": "https://www.ebi.ac.uk/gwas/rest/api/v2/efo-traits/MONDO_0005404"}
    },
}

ASSOCIATIONS_MECFS = {
    "_embedded": {
        "associations": [
            {
                "association_id": 226230222,
                "risk_frequency": "0.9987",
                "pvalue_description": "",
                "pvalue_mantissa": 6,
                "pvalue_exponent": -13,
                "multi_snp_haplotype": False,
                "snp_interaction": False,
                "range": "[2.46-2.54]",
                "beta": "2.498 unit decrease",
                "p_value": 6.000000000000001e-13,
                "efo_traits": [
                    {
                        "efo_id": "MONDO_0005404",
                        "efo_trait": "myalgic encephalomeyelitis/chronic fatigue syndrome",
                    }
                ],
                "reported_trait": ["Chronic fatigue syndrome (PheCode 798.1)"],
                "accession_id": "GCST90480593",
                "locations": ["8:84061029"],
                "mapped_genes": ["LINC01419", "TPM3P3"],
                "bg_efo_traits": [],
                "pubmed_id": "39024449",
                "first_author": "Verma A",
                "ci_lower": 2.46,
                "ci_upper": 2.54,
                "snp_effect_allele": ["rs141691232-G"],
                "snp_allele": [{"rs_id": "rs141691232", "effect_allele": "G"}],
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/226230222"
                    },
                    "loci": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/226230222/loci"
                    },
                    "snp": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs141691232"
                    },
                },
            },
            {
                "association_id": 226230098,
                "risk_frequency": "0.9993",
                "pvalue_description": "",
                "pvalue_mantissa": 1,
                "pvalue_exponent": -11,
                "multi_snp_haplotype": False,
                "snp_interaction": False,
                "range": "[2.87-2.94]",
                "beta": "2.905 unit decrease",
                "p_value": 1e-11,
                "efo_traits": [
                    {
                        "efo_id": "MONDO_0005404",
                        "efo_trait": "myalgic encephalomeyelitis/chronic fatigue syndrome",
                    }
                ],
                "reported_trait": ["Chronic fatigue syndrome (PheCode 798.1)"],
                "accession_id": "GCST90480593",
                "locations": ["7:35572254"],
                "mapped_genes": ["HERPUD2", "TBX20"],
                "bg_efo_traits": [],
                "pubmed_id": "39024449",
                "first_author": "Verma A",
                "ci_lower": 2.87,
                "ci_upper": 2.94,
                "snp_effect_allele": ["rs190241717-G"],
                "snp_allele": [{"rs_id": "rs190241717", "effect_allele": "G"}],
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/226230098"
                    },
                    "loci": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/226230098/loci"
                    },
                    "snp": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs190241717"
                    },
                },
            },
            {
                "association_id": 226230226,
                "risk_frequency": "0.9981",
                "pvalue_description": "",
                "pvalue_mantissa": 3,
                "pvalue_exponent": -11,
                "multi_snp_haplotype": False,
                "snp_interaction": False,
                "range": "[1.76-1.89]",
                "beta": "1.826 unit decrease",
                "p_value": 3e-11,
                "efo_traits": [
                    {
                        "efo_id": "MONDO_0005404",
                        "efo_trait": "myalgic encephalomeyelitis/chronic fatigue syndrome",
                    }
                ],
                "reported_trait": ["Chronic fatigue syndrome (PheCode 798.1)"],
                "accession_id": "GCST90480593",
                "locations": ["11:40748486"],
                "mapped_genes": ["LRRC4C"],
                "bg_efo_traits": [],
                "pubmed_id": "39024449",
                "first_author": "Verma A",
                "ci_lower": 1.76,
                "ci_upper": 1.89,
                "snp_effect_allele": ["rs189511601-A"],
                "snp_allele": [{"rs_id": "rs189511601", "effect_allele": "A"}],
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/226230226"
                    },
                    "loci": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/226230226/loci"
                    },
                    "snp": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs189511601"
                    },
                },
            },
        ]
    },
    "_links": {
        "first": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations?efo_id=MONDO_0005404&direction=asc&page=0&size=3&sort=p_value"
        },
        "self": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations?efo_id=MONDO_0005404&direction=asc&page=0&size=3&sort=p_value"
        },
        "next": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations?efo_id=MONDO_0005404&direction=asc&page=1&size=3&sort=p_value"
        },
        "last": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations?efo_id=MONDO_0005404&direction=asc&page=2&size=3&sort=p_value"
        },
    },
    "page": {"size": 3, "totalElements": 9, "totalPages": 3, "number": 0},
}

SNP_RS1801270 = {
    "rs_id": "rs1801270",
    "merged": 0,
    "functional_class": "missense_variant",
    "last_update_date": "2025-10-05T17:37:35.807+00:00",
    "locations": [
        {"chromosome_name": "6", "chromosome_position": 36684194, "region": {"name": "6p21.2"}}
    ],
    "alleles": "C/A/T (forward)",
    "most_severe_consequence": "missense_variant",
    "mapped_genes": ["CDKN1A"],
    "_links": {
        "self": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs1801270"
        },
        "genomic_contexts": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs1801270/genomic-contexts{?sort,direction}",
            "templated": True,
        },
    },
}

ASSOCIATIONS_RS1801270 = {
    "_embedded": {
        "associations": [
            {
                "association_id": 117664966,
                "risk_frequency": "0.0659",
                "pvalue_description": "",
                "pvalue_mantissa": 2,
                "pvalue_exponent": -8,
                "multi_snp_haplotype": False,
                "snp_interaction": False,
                "range": "[0.11-0.24]",
                "beta": "0.17416422 mmHg decrease",
                "p_value": 2e-08,
                "efo_traits": [
                    {"efo_id": "EFO_0005763", "efo_trait": "pulse pressure measurement"}
                ],
                "reported_trait": ["Pulse pressure"],
                "accession_id": "GCST90292476",
                "locations": ["6:36684194"],
                "mapped_genes": ["CDKN1A"],
                "bg_efo_traits": [],
                "pubmed_id": "33230300",
                "first_author": "Surendran P",
                "ci_lower": 0.11,
                "ci_upper": 0.24,
                "snp_effect_allele": ["rs1801270-A"],
                "snp_allele": [{"rs_id": "rs1801270", "effect_allele": "A"}],
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/117664966"
                    },
                    "loci": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/117664966/loci"
                    },
                    "snp": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs1801270"
                    },
                },
            },
            {
                "association_id": 117661691,
                "risk_frequency": "0.0643",
                "pvalue_description": "",
                "pvalue_mantissa": 7,
                "pvalue_exponent": -8,
                "multi_snp_haplotype": False,
                "snp_interaction": False,
                "range": "[0.13-0.28]",
                "beta": "0.20539764 mmHg decrease",
                "p_value": 7e-08,
                "efo_traits": [
                    {"efo_id": "EFO_0005763", "efo_trait": "pulse pressure measurement"}
                ],
                "reported_trait": ["Pulse pressure"],
                "accession_id": "GCST90000061",
                "locations": ["6:36684194"],
                "mapped_genes": ["CDKN1A"],
                "bg_efo_traits": [],
                "pubmed_id": "33230300",
                "first_author": "Surendran P",
                "ci_lower": 0.13,
                "ci_upper": 0.28,
                "snp_effect_allele": ["rs1801270-A"],
                "snp_allele": [{"rs_id": "rs1801270", "effect_allele": "A"}],
                "_links": {
                    "self": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/117661691"
                    },
                    "loci": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations/117661691/loci"
                    },
                    "snp": {
                        "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/single-nucleotide-polymorphisms/rs1801270"
                    },
                },
            },
        ]
    },
    "_links": {
        "self": {
            "href": "https://www.ebi.ac.uk/gwas/rest/api/v2/associations?rs_id=rs1801270&page=0&size=5"
        }
    },
    "page": {"size": 5, "totalElements": 2, "totalPages": 1, "number": 0},
}

STUDIES_MECFS_COUNT = {
    "_links": {},
    "page": {"size": 1, "totalElements": 19, "totalPages": 19, "number": 0},
}

ASSOCIATIONS_MECFS_COUNT = {
    "_links": {},
    "page": {"size": 1, "totalElements": 9, "totalPages": 9, "number": 0},
}

EMPTY_PAGE = {"_links": {}, "page": {"size": 20, "totalElements": 0, "totalPages": 0, "number": 0}}
