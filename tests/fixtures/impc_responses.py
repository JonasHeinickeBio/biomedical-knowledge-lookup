"""Trimmed real IMPC Solr responses (gene / mp / genotype-phenotype cores), fetched 2026-10-09."""

GENE_FBN1 = {
    "responseHeader": {"status": 0, "QTime": 51},
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {
                "chr_name": "2",
                "chr_strand": "-",
                "human_gene_symbol": ["FBN1"],
                "human_symbol_synonym": ["MFS1", "WMS", "MASS", "OCTD", "SGS", "FBN"],
                "marker_name": "fibrillin 1",
                "marker_symbol": "Fbn1",
                "marker_synonym": ["Fib-1"],
                "marker_type": "Gene",
                "mgi_accession_id": "MGI:95489",
                "mouse_production_status": "Mice Produced",
                "not_significant_top_level_mp_terms": [
                    "vision/eye phenotype",
                    "nervous system phenotype",
                ],
                "phenotype_status": "Phenotyping data available",
                "phenotyping_data_available": True,
                "seq_region_end": 125348417,
                "seq_region_start": 125142514,
                "significant_top_level_mp_terms": [
                    "mortality/aging",
                    "immune system phenotype",
                    "hematopoietic system phenotype",
                ],
            }
        ],
    },
}

# Brca1 is in the gene core but has no phenotyping data (the legacy probe returned this).
GENE_BRCA1 = {
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {
                "human_gene_symbol": ["BRCA1"],
                "human_symbol_synonym": ["PPP1R53", "FANCS", "RNF53", "BRCC1"],
                "marker_name": "breast cancer 1, early onset",
                "marker_symbol": "Brca1",
                "mgi_accession_id": "MGI:104537",
                "phenotyping_data_available": False,
            }
        ],
    }
}

# Human symbol INS matches two mouse paralogs; neither equals the query exactly as a
# mouse symbol, so ranking falls back to the human-ortholog match for both.
GENE_INS = {
    "response": {
        "numFound": 2,
        "start": 0,
        "docs": [
            {
                "human_gene_symbol": ["INS"],
                "marker_name": "insulin II",
                "marker_symbol": "Ins2",
                "mgi_accession_id": "MGI:96573",
                "phenotyping_data_available": False,
            },
            {
                "human_gene_symbol": ["INS"],
                "marker_name": "insulin I",
                "marker_symbol": "Ins1",
                "mgi_accession_id": "MGI:96572",
                "phenotyping_data_available": True,
            },
        ],
    }
}

GENE_FIBRILLIN = {
    "response": {
        "numFound": 2,
        "start": 0,
        "docs": [
            {
                "human_gene_symbol": ["FBN2"],
                "marker_name": "fibrillin 2",
                "marker_symbol": "Fbn2",
                "mgi_accession_id": "MGI:95490",
            },
            {
                "human_gene_symbol": ["FBN1"],
                "marker_name": "fibrillin 1",
                "marker_symbol": "Fbn1",
                "mgi_accession_id": "MGI:95489",
            },
        ],
    }
}

EMPTY = {"responseHeader": {"status": 0}, "response": {"numFound": 0, "start": 0, "docs": []}}

MP_SPLEEN_WEIGHT = {
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {
                "mp_definition": (
                    "greater than average weight of the organ that functions to filter blood "
                    "and to store red corpuscles and platelets"
                ),
                "mp_id": "MP:0004952",
                "mp_term": "increased spleen weight",
                "mp_term_synonym": ["increased splenic weight"],
                "parent_mp_id": ["MP:0000691", "MP:0004951"],
                "parent_mp_term": ["enlarged spleen", "abnormal spleen weight"],
                "top_level_mp_id": ["MP:0005397", "MP:0005387", "MP:0005378"],
                "top_level_mp_term": [
                    "hematopoietic system phenotype",
                    "immune system phenotype",
                    "growth/size/body region phenotype",
                ],
            }
        ],
    }
}

MP_SPLEEN_MORPHOLOGY = {
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {
                "mp_id": "MP:0000689",
                "mp_term": "abnormal spleen morphology",
                "parent_mp_id": ["MP:0002396", "MP:0002722"],
                "parent_mp_term": [
                    "abnormal hematopoietic system morphology/development",
                    "abnormal immune system organ morphology",
                ],
                "top_level_mp_term": ["hematopoietic system phenotype"],
            }
        ],
    }
}

MP_LETHARGY = {
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [{"mp_id": "MP:0005202", "mp_term": "lethargy"}],
    }
}


def _call(**kw):
    base = {
        "allele_symbol": "Fbn1<em1(IMPC)H>",
        "life_stage_name": "Early adult",
        "marker_accession_id": "MGI:95489",
        "marker_symbol": "Fbn1",
        "assertion_type": "automatic",
    }
    base.update(kw)
    return base


# Fbn1, grouped by mp_term_id (group.limit=5): 6 calls in 5 groups; the viability call has
# p_value 0.0 (underflow) and sorts first.
GP_FBN1_GROUPED = {
    "grouped": {
        "mp_term_id": {
            "matches": 6,
            "ngroups": 5,
            "groups": [
                {
                    "groupValue": "MP:0011110",
                    "doclist": {
                        "numFound": 1,
                        "docs": [
                            _call(
                                mp_term_id="MP:0011110",
                                mp_term_name="preweaning lethality, incomplete penetrance",
                                p_value=0.0,
                                effect_size=1.0,
                                zygosity="homozygote",
                                sex="not_considered",
                                parameter_name="Viability Outcome",
                                top_level_mp_term_name=["mortality/aging"],
                            )
                        ],
                    },
                },
                {
                    "groupValue": "MP:0004952",
                    "doclist": {
                        "numFound": 2,
                        "docs": [
                            _call(
                                mp_term_id="MP:0004952",
                                mp_term_name="increased spleen weight",
                                p_value=1.45602538533913e-30,
                                effect_size=0.125835597215145,
                                zygosity="heterozygote",
                                sex="male",
                                parameter_name="Spleen weight",
                                top_level_mp_term_name=[
                                    "hematopoietic system phenotype",
                                    "immune system phenotype",
                                ],
                            ),
                            _call(
                                mp_term_id="MP:0004952",
                                mp_term_name="increased spleen weight",
                                p_value=2.0e-12,
                                zygosity="homozygote",
                                sex="female",
                                parameter_name="Spleen weight",
                            ),
                        ],
                    },
                },
                {
                    "groupValue": "MP:0000219",
                    "doclist": {
                        "numFound": 1,
                        "docs": [
                            _call(
                                mp_term_id="MP:0000219",
                                mp_term_name="increased neutrophil cell number",
                                p_value=6.92901328666457e-07,
                                effect_size=8.57896924432006,
                                zygosity="heterozygote",
                                sex="male",
                                parameter_name="Neutrophil differential count",
                            )
                        ],
                    },
                },
                {"groupValue": "MP:EMPTY", "doclist": {"numFound": 0, "docs": []}},
                {
                    "groupValue": "NOID",
                    "doclist": {"numFound": 1, "docs": [{"marker_symbol": "Fbn1"}]},
                },
            ],
        }
    }
}

# MP:0000689 (abnormal spleen morphology) with its descendants, grouped by gene.
GP_SPLEEN_GROUPED = {
    "grouped": {
        "marker_accession_id": {
            "matches": 1750,
            "ngroups": 858,
            "groups": [
                {
                    "groupValue": "MGI:1914072",
                    "doclist": {
                        "numFound": 3,
                        "docs": [
                            {
                                "marker_accession_id": "MGI:1914072",
                                "marker_symbol": "Fbxo25",
                                "mp_term_id": "MP:0000689",
                                "mp_term_name": "abnormal spleen morphology",
                                "p_value": 0.0,
                                "zygosity": "homozygote",
                                "sex": "female",
                            }
                        ],
                    },
                },
                {
                    "groupValue": "MGI:1920455",
                    "doclist": {
                        "numFound": 1,
                        "docs": [
                            {
                                "marker_accession_id": "MGI:1920455",
                                "marker_symbol": "C9orf72",
                                "mp_term_id": "MP:0004952",
                                "mp_term_name": "increased spleen weight",
                                "p_value": 2.51718581939126e-64,
                                "effect_size": 0.17484454978443,
                                "zygosity": "homozygote",
                                "sex": "male",
                            }
                        ],
                    },
                },
                {"groupValue": "x", "doclist": {"docs": [{"marker_symbol": "NoId"}]}},
            ],
        }
    }
}
