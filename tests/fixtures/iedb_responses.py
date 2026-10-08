"""Trimmed real IEDB IQ-API (PostgREST) responses, fetched 2026-10-08, for unit tests."""

# epitope_search?structure_id=in.(68,1309147,2711844)&select=<light columns>
LIGHT_68 = {
    "structure_id": 68,
    "structure_iri": "IEDB_EPITOPE:68",
    "structure_type": "Linear peptide",
    "linear_sequence": "AAAYFVGYLK",
    "linear_sequence_length": 10,
    "structure_descriptions": ["AAAYFVGYLK"],
    "parent_source_antigen_iris": ["UNIPROT:P59594"],
    "parent_source_antigen_names": ["Spike glycoprotein (UniProt:P59594)"],
    "parent_source_antigen_source_org_iris": ["NCBITaxon:227984"],
    "parent_source_antigen_source_org_names": [
        "SARS coronavirus Tor2 (Severe acute respiratory syndrome-related coronavirus Tor2)"
    ],
}
LIGHT_YLQ = {
    "structure_id": 1309147,
    "structure_iri": "IEDB_EPITOPE:1309147",
    "structure_type": "Linear peptide",
    "linear_sequence": "YLQPRTFLL",
    "linear_sequence_length": 9,
    "structure_descriptions": ["YLQPRTFLL"],
    "parent_source_antigen_iris": ["UNIPROT:P0DTC2"],
    "parent_source_antigen_names": ["Spike glycoprotein (UniProt:P0DTC2)"],
    "parent_source_antigen_source_org_iris": ["NCBITaxon:2697049"],
    "parent_source_antigen_source_org_names": ["SARS-CoV2"],
}
# discontinuous epitope: no linear_sequence, several descriptions, no organism names
LIGHT_DISCONTINUOUS = {
    "structure_id": 2711844,
    "structure_iri": "IEDB_EPITOPE:2711844",
    "structure_type": "Discontinuous peptide",
    "linear_sequence": None,
    "linear_sequence_length": None,
    "structure_descriptions": ["A123, G142, Y144", "A123 G142 Y144"],
    "parent_source_antigen_iris": ["UNIPROT:P0DTC2", "UNIPROT:P59594"],
    "parent_source_antigen_names": [
        "Spike glycoprotein (UniProt:P0DTC2)",
        "Two components:Spike glycoprotein (UniProt:P0DTC2) & Spike glycoprotein (UniProt:P0DTC2)",
    ],
    "parent_source_antigen_source_org_iris": ["NCBITaxon:2697049", "NCBITaxon:227984"],
    "parent_source_antigen_source_org_names": ["SARS-CoV2", "SARS coronavirus Tor2"],
}
LIGHT_ROWS = [LIGHT_YLQ, LIGHT_68, LIGHT_DISCONTINUOUS]
NO_ID_ROW = {"structure_id": "not-an-int"}

# epitope_export?and=(...)&select=structure_id - one row per epitope x molecule x organism
EXPORT_ROWS = [
    {"structure_id": 68},
    {"structure_id": 68},
    {"structure_id": 1309147},
    {"structure_id": None},
    {"structure_id": 2711844},
    {"structure_id": 1309147},
]

# epitope_search?structure_id=eq.1309147&select=<detail columns>  (assay id lists shortened)
DETAIL_YLQ = {
    **LIGHT_YLQ,
    "curated_source_antigens": [
        {
            "accession": "BCN86353.1",
            "name": "surface glycoprotein [Severe acute respiratory syndrome coronavirus 2]",
            "iri": "GENPEPT:BCN86353.1",
            "starting_position": 278,
            "ending_position": 286,
            "source_organism_name": "SARS-CoV2",
            "source_organism_iri": "NCBITaxon:2697049",
        },
        {
            "accession": "P0DTC2.1",
            "name": "Spike glycoprotein",
            "iri": "UNIPROT:P0DTC2.1",
            "starting_position": 269,
            "ending_position": 277,
            "source_organism_name": "Homo sapiens (human)",
            "source_organism_iri": "NCBITaxon:9606",
        },
        # IEDB files GenBank proteins under UNIPROT: too
        {
            "accession": "QHD43416.1",
            "name": "Spike glycoprotein",
            "iri": "UNIPROT:QHD43416.1",
            "starting_position": 269,
            "ending_position": 277,
            "source_organism_name": "SARS-CoV2",
            "source_organism_iri": "NCBITaxon:2697049",
        },
        # duplicate (same iri and positions) is collapsed, junk entries ignored
        {
            "accession": "QHD43416.1",
            "name": "Spike glycoprotein",
            "iri": "UNIPROT:QHD43416.1",
            "starting_position": 269,
            "ending_position": 277,
            "source_organism_name": "SARS-CoV2",
            "source_organism_iri": "NCBITaxon:2697049",
        },
        "junk",
        {"name": "no iri"},
    ],
    "source_organism_iris": ["NCBITaxon:2697049", "NCBITaxon:9606", "taxon:10002334"],
    "source_organism_names": ["Homo sapiens (human)", "SARS-CoV2", "SARS-CoV2 Omicron"],
    "host_organism_iris": ["NCBITaxon:9606", "taxon:10000000"],
    "host_organism_names": ["Homo sapiens (human)", "Mus musculus BALB/c"],
    "mhc_allele_iris": ["MRO:0001006", "MRO:0001007"],
    "mhc_allele_names": ["HLA-A*01:01", "HLA-A*02:01", "HLA-A2"],
    "mhc_classes": ["I", "non classical"],
    "disease_iris": ["DOID:0080600", "ONTIE:0003423"],
    "disease_names": ["asymptomatic COVID-19 infection", "COVID-19"],
    "tcell_ids": [12156787, 12156801, 12156814],
    "bcell_ids": None,
    "elution_ids": [12394252, 12893490],
    "pdb_ids": ["7n1a", "7n1f"],
    "chebi_ids": ["15377", "CHEBI:16236"],
    "pubmed_ids": [str(32913053 + i) for i in range(40)],
    "epitope_structures_defined": ["Epitope containing region/antigenic site"],
}

# epitope_summary?structure_id=eq.1309147
SUMMARY = [
    {
        "structure_id": 1309147,
        "structure_iri": "IEDB_EPITOPE:1309147",
        "epitope_summary": (
            "YLQPRTFLL is a linear peptidic epitope (epitope ID 1309147) studied as part of "
            "Spike glycoprotein (UniProt:P0DTC2) from SARS-CoV2.  This epitope has been studied "
            "in 78 publication(s)."
        ),
    }
]

# antigen_search?parent_source_antigen_iri=eq.UNIPROT:P0DTC2
ANTIGEN_SPIKE = [
    {
        "parent_source_antigen_iri": "UNIPROT:P0DTC2",
        "parent_source_antigen_names": [
            "Spike glycoprotein (UniProt:P0DTC2)",
            "Two components:Spike glycoprotein (UniProt:P0DTC2) & Spike glycoprotein (UniProt:P0DTC2)",
            "S1 subunit (UniProt:P0DTC2)",
        ],
        "parent_source_antigen_source_org_iri": "NCBITaxon:2697049",
        "parent_source_antigen_source_org_name": "SARS-CoV2",
    }
]
ANTIGEN_NO_NAME = [
    {
        "parent_source_antigen_iri": "UNIPROT:P03211",
        "parent_source_antigen_names": None,
        "parent_source_antigen_source_org_iri": None,
        "parent_source_antigen_source_org_name": None,
    }
]

# PostgREST error object (HTTP 404)
PGRST_ERROR = {
    "code": "42883",
    "details": None,
    "hint": "No operator matches the given name and argument types.",
    "message": "operator does not exist: character varying[] ~~* unknown",
}
