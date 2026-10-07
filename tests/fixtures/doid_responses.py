"""Trimmed real OLS4 responses for the Disease Ontology (DOID), fetched 2026-10-07."""

_BASE = "http://www.ebi.ac.uk/ols4/api/ontologies/doid/terms/"
_CFS_ENC = "http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FDOID_8544"

# /search?q=chronic fatigue syndrome&ontology=doid&type=class (3 of 4 hits)
SEARCH_CFS = {
    "response": {
        "docs": [
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_8544",
                "synonym": [
                    "Myalgic encephalitis",
                    "Myalgic encephalomyelitis",
                    "Postviral fatigue syndrome",
                    "CFS",
                ],
                "short_form": "DOID_8544",
                "description": [
                    "No OMIM mapping, confirmed by DO. [LS].",
                    "A syndrome that involves prolonged and severe tiredness or weariness "
                    "that is unrelated to exertion, is not relieved by rest and for a minimum "
                    "of six months and is not directly caused by other conditions.",
                ],
                "label": "chronic fatigue syndrome",
                "obo_id": "DOID:8544",
            },
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_631",
                "synonym": [],
                "short_form": "DOID_631",
                "description": ["A syndrome that is is characterized by chronic widespread pain."],
                "label": "fibromyalgia",
                "obo_id": "DOID:631",
            },
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_0080848",
                "synonym": ["chronic COVID-19", "post-COVID syndrome", "PASC"],
                "short_form": "DOID_0080848",
                "description": ["A Coronavirus infectious disease with persistent symptoms."],
                "label": "long COVID",
                "obo_id": "DOID:0080848",
            },
            # Not a DOID class, and a duplicate: both must be skipped
            {
                "iri": "http://purl.obolibrary.org/obo/HP_0012378",
                "label": "Fatigue",
                "obo_id": "HP:0012378",
            },
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_631",
                "label": "fibromyalgia",
                "obo_id": "DOID:631",
            },
            # No label: skipped
            {"iri": "http://purl.obolibrary.org/obo/DOID_1", "obo_id": "DOID:1"},
        ],
        "numFound": 4,
        "start": 0,
    }
}

# /ontologies/doid/terms/{iri} for DOID:8544
TERM_CFS = {
    "iri": "http://purl.obolibrary.org/obo/DOID_8544",
    "lang": "en",
    "description": [
        "No OMIM mapping, confirmed by DO. [LS].",
        "A syndrome that involves prolonged and severe tiredness or weariness that is "
        "unrelated to exertion, is not relieved by rest and for a minimum of six months and "
        "is not directly caused by other conditions.",
    ],
    "synonyms": [
        "Myalgic encephalitis",
        "Myalgic encephalomyelitis",
        "Postviral fatigue syndrome",
        "CFS",
    ],
    "annotation": {
        "database_cross_reference": [
            "GARD:7121",
            "ICD10CM:G93.32",
            "ICD9CM:780.71",
            "MESH:D015673",
            "NCI:C3037",
            "SNOMEDCT_US_2025_09_01:193054000",
            "UMLS_CUI:C0015674",
        ],
        "has_obo_namespace": ["disease_ontology"],
        "id": ["DOID:8544"],
    },
    "label": "chronic fatigue syndrome",
    "ontology_name": "doid",
    "ontology_prefix": "DOID",
    "is_obsolete": False,
    "term_replaced_by": None,
    "is_defining_ontology": True,
    "has_children": False,
    "is_root": False,
    "short_form": "DOID_8544",
    "obo_id": "DOID:8544",
    "in_subset": ["DO_rare_slim", "NCIthesaurus"],
    "obo_xref": [
        {
            "database": "GARD",
            "id": "7121",
            "url": "https://rarediseases.info.nih.gov/?gard_id=7121",
        },
        {"database": "ICD10CM", "id": "G93.32", "url": None},
        {"database": "ICD9CM", "id": "780.71", "url": None},
        {"database": "MESH", "id": "D015673", "url": "http://id.nlm.nih.gov/mesh/D015673"},
        {"database": "NCI", "id": "C3037", "url": "http://purl.obolibrary.org/obo/NCIT_C3037"},
        {
            "database": "SNOMEDCT_US_2025_09_01",
            "id": "193054000",
            "url": "http://purl.bioontology.org/ontology/SNOMEDCT/193054000",
        },
        {
            "database": "UMLS_CUI",
            "id": "C0015674",
            "url": "https://uts.nlm.nih.gov/uts/umls/concept/C0015674",
        },
    ],
    "is_preferred_root": False,
    "_links": {
        "self": {"href": f"{_BASE}{_CFS_ENC}?lang=en"},
        "parents": {"href": f"{_BASE}{_CFS_ENC}/parents"},
        "children": {"href": f"{_BASE}{_CFS_ENC}/children"},
        "graph": {"href": f"{_BASE}{_CFS_ENC}/graph"},
    },
}

PARENTS_CFS = {"_embedded": {"terms": [{"label": "syndrome", "obo_id": "DOID:225"}]}}

# Term with children (diabetes mellitus) for the children branch
TERM_DM = {
    "iri": "http://purl.obolibrary.org/obo/DOID_9351",
    "label": "diabetes mellitus",
    "obo_id": "DOID:9351",
    "short_form": "DOID_9351",
    "description": ["A glucose metabolism disease with chronic hyperglycaemia."],
    "synonyms": ["diabetes"],
    "has_children": True,
    "is_obsolete": False,
    "obo_xref": [{"database": "MIM", "id": "125853", "url": None}],
    "_links": {
        "parents": {
            "href": f"{_BASE}http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FDOID_9351/parents"
        },
        "children": {
            "href": f"{_BASE}http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FDOID_9351/children"
        },
    },
}
PARENTS_DM = {"_embedded": {"terms": [{"label": "glucose metabolism disease"}]}}
CHILDREN_DM = {
    "_embedded": {
        "terms": [{"label": "type 1 diabetes mellitus"}, {"label": "type 2 diabetes mellitus"}]
    }
}

# /graph for DOID:2841 (asthma): trimmed to a parent, a child, typed relations and inverse ones
_D = "http://purl.obolibrary.org/obo/"
GRAPH_ASTHMA = {
    "nodes": [
        {"iri": f"{_D}DOID_2841", "label": "asthma"},
        {"iri": f"{_D}DOID_1176", "label": "bronchial disease"},
        {"iri": f"{_D}DOID_9498", "label": "chronic asthma"},
        {"iri": f"{_D}HP_0002099", "label": "Abnormal respiratory system physiology"},
        {"iri": f"{_D}SYMP_0000614", "label": "wheezing"},
        {"iri": f"{_D}SYMP_0000615", "label": "cough"},
        {"iri": f"{_D}DOID_1827", "label": "Churg-Strauss syndrome"},
        {"iri": f"{_D}MIM_600807", "label": "susceptibility to asthma"},
    ],
    "edges": [
        {
            "source": f"{_D}DOID_2841",
            "target": f"{_D}DOID_1176",
            "uri": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
            "label": "subClassOf",
        },
        {
            "source": f"{_D}DOID_9498",
            "target": f"{_D}DOID_2841",
            "uri": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
            "label": "subClassOf",
        },
        {
            "source": f"{_D}DOID_2841",
            "target": f"{_D}HP_0002099",
            "uri": f"{_D}RO_0002200",
            "label": "has phenotype",
        },
        {
            "source": f"{_D}DOID_2841",
            "target": f"{_D}SYMP_0000614",
            "uri": f"{_D}RO_0002452",
            "label": "has symptom",
        },
        {
            "source": f"{_D}DOID_2841",
            "target": f"{_D}SYMP_0000615",
            "uri": f"{_D}RO_0002452",
            "label": "has symptom",
        },
        # exact duplicate edge
        {
            "source": f"{_D}DOID_2841",
            "target": f"{_D}SYMP_0000615",
            "uri": f"{_D}RO_0002452",
            "label": "has symptom",
        },
        {
            "source": f"{_D}DOID_1827",
            "target": f"{_D}DOID_2841",
            "uri": f"{_D}RO_0002564",
            "label": "disease has feature",
        },
        {
            "source": f"{_D}MIM_600807",
            "target": f"{_D}DOID_2841",
            "uri": f"{_D}RO_0003304",
            "label": "contributes to condition",
        },
        # unrelated to the term, self loop and unlabeled edges: all skipped
        {
            "source": f"{_D}DOID_1176",
            "target": f"{_D}DOID_9498",
            "uri": "x",
            "label": "other",
        },
        {"source": f"{_D}DOID_2841", "target": f"{_D}DOID_2841", "uri": "x", "label": "self"},
        {"source": f"{_D}DOID_2841", "target": f"{_D}DOID_1176", "uri": "x", "label": ""},
    ],
}
