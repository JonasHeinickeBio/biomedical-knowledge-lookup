"""Trimmed real NCBI Datasets taxonomy v2 responses (verified live 2026-10-08)."""

# taxon_suggest/SARS-CoV-2?tax_rank_filter=higher_taxon
SUGGEST_SARS = {
    "sci_name_and_ids": [
        {
            "sci_name": "Severe acute respiratory syndrome coronavirus",
            "tax_id": "2901879",
            "matched_term": "SARS-CoV",
            "group_name": "viruses",
        },
        {
            "sci_name": "Severe acute respiratory syndrome coronavirus 2",
            "tax_id": "2697049",
            "matched_term": "SARS-CoV-2",
            "group_name": "viruses",
        },
        {
            "sci_name": "Homo sapiens",
            "tax_id": "9606",
            "common_name": "human",
            "matched_term": "Homo sapiens",
            "rank": "SPECIES",
            "group_name": "primates",
        },
        # duplicate and malformed entries must be skipped
        {"sci_name": "Homo sapiens", "tax_id": "9606", "rank": "SPECIES"},
        {"sci_name": "", "tax_id": "1"},
        {"sci_name": "No id", "tax_id": "abc"},
    ]
}

# taxon/2697049/dataset_report (SARS-CoV-2: no rank, no children)
REPORT_SARS2 = {
    "reports": [
        {
            "taxonomy": {
                "tax_id": 2697049,
                "current_scientific_name": {
                    "name": "Severe acute respiratory syndrome coronavirus 2"
                },
                "group_name": "viruses",
                "classification": {
                    "kingdom": {"name": "Orthornavirae", "id": 2732396},
                    "phylum": {"name": "Pisuviricota", "id": 2732408},
                    "family": {"name": "Coronaviridae", "id": 11118},
                    "genus": {"name": "Betacoronavirus", "id": 694002},
                    "species": {"name": "Betacoronavirus pandemicum", "id": 3418604},
                    "realm": {"name": "Riboviria", "id": 2559587},
                },
                "parents": [1, 10239, 2559587, 11118, 694002, 3418604],
                "counts": [
                    {"type": "COUNT_TYPE_ASSEMBLY", "count": 12412},
                    {"type": "COUNT_TYPE_GENE", "count": 11},
                ],
                "genomic_moltype": "ssRNA(+)",
                "genetic_code": {"primary": {"id": 1, "name": "Standard"}},
            },
            "query": ["2697049"],
        }
    ],
    "total_count": 1,
}

# taxon/10376/dataset_report (EBV: merged id 47902, children)
REPORT_EBV = {
    "reports": [
        {
            "taxonomy": {
                "tax_id": 10376,
                "current_scientific_name": {"name": "human gammaherpesvirus 4"},
                "curator_common_name": "Epstein-Barr virus",
                "group_name": "viruses",
                "classification": {
                    "family": {"name": "Orthoherpesviridae", "id": 3044472},
                    "genus": {"name": "Lymphocryptovirus", "id": 10375},
                },
                "parents": [1, 10239, 3044472, 10375],
                "children": [12509, 31525, 777777],
                "counts": [{"type": "COUNT_TYPE_ASSEMBLY", "count": 586}, "junk"],
                "genomic_moltype": "dsDNA",
                "secondary_tax_ids": [47902],
            },
            "query": ["10376"],
        }
    ],
    "total_count": 1,
}

# taxon/{lineage and children}/dataset_report: returned in taxid order, not lineage order
REPORT_EBV_RELATED = {
    "reports": [
        {"taxonomy": {"tax_id": 1, "current_scientific_name": {"name": "root"}}},
        {
            "taxonomy": {
                "tax_id": 10239,
                "rank": "ACELLULAR_ROOT",
                "current_scientific_name": {"name": "Viruses"},
            }
        },
        {
            "taxonomy": {
                "tax_id": 10375,
                "rank": "GENUS",
                "current_scientific_name": {"name": "Lymphocryptovirus"},
            }
        },
        {
            "taxonomy": {
                "tax_id": 12509,
                "current_scientific_name": {"name": "Human herpesvirus 4 type 2"},
            }
        },
        {
            "taxonomy": {
                "tax_id": 31525,
                "current_scientific_name": {"name": "Human herpesvirus 4 strain CAO"},
            }
        },
        {
            "taxonomy": {
                "tax_id": 3044472,
                "rank": "FAMILY",
                "current_scientific_name": {"name": "Orthoherpesviridae"},
            }
        },
        {"taxonomy": {"tax_id": 5, "current_scientific_name": {}}},  # nameless: skipped as concept
        {"not_taxonomy": True},
    ],
    "total_count": 7,
}

# taxon/10376/name_report
NAME_REPORT_EBV = {
    "reports": [
        {
            "taxonomy": {
                "tax_id": "10376",
                "current_scientific_name": {
                    "name": "human gammaherpesvirus 4",
                    "informal_names": ["Epstein-Barr virus EBV", "Human herpesvirus 4"],
                },
                "group_name": "viruses",
                "curator_common_name": "Epstein-Barr virus",
                "other_common_names": ["HHV-4", "EBV", "Epstein Barr virus"],
            },
            "query": ["10376"],
        },
        "junk",
        {"taxonomy": "junk"},
    ],
    "total_count": 1,
}

# taxon/10376/links
LINKS_EBV = {"tax_id": "10376", "encyclopedia_of_life": "https://eol.org/pages/46699929"}
LINKS_SARS2 = {
    "tax_id": "2697049",
    "encyclopedia_of_life": "https://eol.org/pages/55550284",
    "wikipedia": "https://wikipedia.org/wiki/Severe_acute_respiratory_syndrome_coronavirus_2",
}

# unknown ids answer HTTP 200 with an errors entry and no reports
REPORT_EMPTY = {"total_count": 0}
SUGGEST_EMPTY = {}
