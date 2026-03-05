"""
Mock API responses for testing adapters.
"""

# OLS (Ontology Lookup Service) responses
OLS_SEARCH_RESPONSE = {
    "_embedded": {
        "terms": [
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_9351",
                "label": "diabetes mellitus",
                "description": ["A metabolic disease characterized by high blood sugar"],
                "synonyms": ["diabetes", "DM", "diabetes disease"],
                "ontology_name": "doid",
                "ontology_prefix": "DOID",
                "type": "class",
            },
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_8778",
                "label": "type 1 diabetes mellitus",
                "description": ["An autoimmune form of diabetes mellitus"],
                "synonyms": ["T1DM", "juvenile diabetes"],
                "ontology_name": "doid",
                "ontology_prefix": "DOID",
            },
        ]
    },
    "page": {"size": 20, "totalElements": 2, "totalPages": 1, "number": 0},
}

OLS_CONCEPT_DETAILS = {
    "iri": "http://purl.obolibrary.org/obo/DOID_9351",
    "label": "diabetes mellitus",
    "description": ["A metabolic disease characterized by high blood sugar"],
    "synonyms": ["diabetes", "DM"],
    "ontology_name": "doid",
    "ontology_prefix": "DOID",
    "has_children": True,
    "is_defining_ontology": True,
}

# BioPortal responses
BIOPORTAL_SEARCH_RESPONSE = {
    "collection": [
        {
            "@id": "http://purl.bioontology.org/ontology/SNOMEDCT/73211009",
            "prefLabel": "Diabetes mellitus",
            "synonym": ["Diabetes", "DM", "Diabetes disease"],
            "definition": ["A metabolic disease"],
            "cui": ["C0011849"],
            "semanticType": ["Disease or Syndrome"],
            "obsolete": False,
        }
    ],
    "pageCount": 1,
    "page": 1,
}

BIOPORTAL_CONCEPT_DETAILS = {
    "@id": "http://purl.bioontology.org/ontology/SNOMEDCT/73211009",
    "prefLabel": "Diabetes mellitus",
    "synonym": ["Diabetes", "DM"],
    "definition": ["A metabolic disease"],
    "notation": "73211009",
    "cui": ["C0011849"],
    "semanticType": ["Disease or Syndrome"],
}

# UMLS responses
UMLS_SEARCH_RESPONSE = {
    "result": {
        "results": [
            {
                "ui": "C0011849",
                "name": "Diabetes Mellitus",
                "rootSource": "MTH",
                "uri": "https://uts-ws.nlm.nih.gov/rest/content/2021AB/CUI/C0011849",
                "semanticTypes": [
                    {"name": "Disease or Syndrome", "uri": "T047"}
                ],
            },
            {
                "ui": "C0011854",
                "name": "Type 1 Diabetes Mellitus",
                "rootSource": "MTH",
                "semanticTypes": [
                    {"name": "Disease or Syndrome", "uri": "T047"}
                ],
            },
        ]
    }
}

UMLS_CONCEPT_DETAILS = {
    "result": {
        "classType": "Concept",
        "ui": "C0011849",
        "name": "Diabetes Mellitus",
        "atomCount": 257,
        "definitions": "A metabolic disorder characterized by high blood glucose",
        "semanticTypes": [{"name": "Disease or Syndrome", "uri": "T047"}],
    }
}

# ChEMBL responses
CHEMBL_SEARCH_RESPONSE = {
    "molecules": [
        {
            "molecule_chembl_id": "CHEMBL1234",
            "pref_name": "Metformin",
            "molecule_type": "Small molecule",
            "molecule_synonyms": [
                {"molecule_synonym": "Glucophage"},
                {"molecule_synonym": "Dimethylbiguanide"},
            ],
            "max_phase": 4,
        },
        {
            "molecule_chembl_id": "CHEMBL5678",
            "pref_name": "Insulin",
            "molecule_type": "Protein",
            "max_phase": 4,
        },
    ],
    "page_meta": {"limit": 20, "offset": 0, "total_count": 2},
}

CHEMBL_MOLECULE_DETAILS = {
    "molecule_chembl_id": "CHEMBL1234",
    "pref_name": "Metformin",
    "molecule_type": "Small molecule",
    "molecule_properties": {
        "molecular_weight": 129.16,
        "cx_logp": -0.64,
        "aromatic_rings": 0,
    },
    "molecule_synonyms": [
        {"molecule_synonym": "Glucophage"},
        {"molecule_synonym": "Dimethylbiguanide"},
    ],
}

# DisGeNET responses
DISGENET_SEARCH_RESPONSE = [
    {
        "geneSymbol": "INS",
        "geneid": "3630",
        "diseaseId": "C0011849",
        "diseaseName": "Diabetes Mellitus",
        "score": 0.92,
        "source": "UNIPROT;CTD_human",
        "associationType": "GeneticVariation",
    },
    {
        "geneSymbol": "INSR",
        "geneid": "3643",
        "diseaseId": "C0011849",
        "diseaseName": "Diabetes Mellitus",
        "score": 0.88,
        "source": "CTD_human",
        "associationType": "Biomarker",
    },
]

# UniProt responses
UNIPROT_SEARCH_RESPONSE = {
    "results": [
        {
            "primaryAccession": "P01308",
            "uniProtkbId": "INS_HUMAN",
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Insulin"}}
            },
            "genes": [{"geneName": {"value": "INS"}}],
            "organism": {"scientificName": "Homo sapiens"},
        }
    ]
}

# Ensembl responses
ENSEMBL_GENE_RESPONSE = {
    "id": "ENSG00000133056",
    "display_name": "INS",
    "description": "insulin [Source:HGNC Symbol;Acc:HGNC:6081]",
    "biotype": "protein_coding",
    "species": "homo_sapiens",
    "start": 2159779,
    "end": 2161209,
    "strand": -1,
    "seq_region_name": "11",
}

# PubChem responses
PUBCHEM_COMPOUND_RESPONSE = {
    "PC_Compounds": [
        {
            "id": {"id": {"cid": 4091}},
            "props": [
                {"urn": {"label": "IUPAC Name"}, "value": {"sval": "metformin"}},
                {
                    "urn": {"label": "Molecular Formula"},
                    "value": {"sval": "C4H11N5"},
                },
                {
                    "urn": {"label": "Molecular Weight"},
                    "value": {"fval": 129.16},
                },
            ],
        }
    ]
}

# Reactome responses
REACTOME_PATHWAY_RESPONSE = {
    "displayName": "Insulin signaling",
    "stId": "R-HSA-74752",
    "name": ["Insulin signaling pathway"],
    "type": "Pathway",
    "species": "Homo sapiens",
}

# Gene Ontology responses
GO_TERM_RESPONSE = {
    "id": "GO:0005576",
    "label": "extracellular region",
    "definition": "The space external to the outermost structure of a cell",
    "synonyms": ["extracellular", "extracellular space"],
    "namespace": "cellular_component",
}

# HPO (Human Phenotype Ontology) responses
HPO_TERM_RESPONSE = {
    "id": "HP:0000819",
    "name": "Diabetes mellitus",
    "definition": "A metabolic disease characterized by abnormally high blood sugar",
    "synonyms": ["Diabetes"],
    "xrefs": [{"database": "UMLS", "id": "C0011849"}],
}

# Wikidata responses
WIKIDATA_ENTITY_RESPONSE = {
    "entities": {
        "Q12206": {
            "id": "Q12206",
            "labels": {"en": {"language": "en", "value": "diabetes mellitus"}},
            "descriptions": {
                "en": {"language": "en", "value": "group of metabolic disorders"}
            },
            "aliases": {"en": [{"language": "en", "value": "diabetes"}]},
        }
    }
}

# Error responses
ERROR_RESPONSE_404 = {"error": "Not Found", "status": 404}

ERROR_RESPONSE_500 = {"error": "Internal Server Error", "status": 500}

ERROR_RESPONSE_TIMEOUT = {"error": "Request Timeout", "status": 408}

ERROR_RESPONSE_RATE_LIMIT = {
    "error": "Rate Limit Exceeded",
    "status": 429,
    "retry_after": 60,
}
