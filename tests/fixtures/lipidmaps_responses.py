"""Trimmed real LIPID MAPS responses (REST + SPARQL, fetched 2026-10-08) for unit tests."""

import json

# REST compound/lm_id/LMGP01010005/all (POPC) - body is a JSON string.
POPC = {
    "input": "LMGP01010005",
    "regno": "151",
    "lm_id": "LMGP01010005",
    "name": "PC 16:0/18:1(9Z)",
    "sys_name": "1-hexadecanoyl-2-(9Z-octadecenoyl)-sn-glycero-3-phosphocholine",
    "synonyms": "PC(16:0/18:1); Palmitoyloleoylphosphatidylcholine; POPC; PC(34:1)",
    "abbrev": "PC 34:1",
    "abbrev_chains": "PC 16:0_18:1",
    "core": "Glycerophospholipids [GP]",
    "main_class": "Glycerophosphocholines [GP01]",
    "sub_class": "Diacylglycerophosphocholines [GP0101]",
    "exactmass": "759.577806",
    "formula": "C42H82NO8P",
    "inchi": "InChI=1S/C42H82NO8P/c1-6-8-10-12",
    "inchi_key": "WTJKGGKOPKCXLL-VYOBOKEXSA-N",
    "hmdb_id": "HMDB0007972",
    "chebi_id": "73001",
    "pubchem_cid": "5497103",
    "smiles": "[C@](COP(=O)([O-])OCC[N+](C)(C)C)([H])(OC(CCCCCCC/C=C\\CCCCCCCC)=O)COC(CCCCCCCCCCCCCCC)=O",
}
POPC_BODY = json.dumps(POPC)

# REST compound/lm_id/LMST01010001/all (cholesterol)
CHOLESTEROL = {
    "input": "LMST01010001",
    "regno": "183",
    "lm_id": "LMST01010001",
    "name": "Cholesterol",
    "sys_name": "cholest-5-en-3beta-ol",
    "synonyms": "Cholesterol; Cholest-5-en-3-ol; Cholesteryl alcohol",
    "abbrev": "ST 27:1;O",
    "core": "Sterols [ST]",
    "main_class": "Sterols [ST01]",
    "sub_class": "Cholesterol and derivatives [ST0101]",
    "exactmass": "386.354866",
    "formula": "C27H46O",
    "inchi_key": "HVYWMOMLDIMFJA-DPAQBDIFSA-N",
    "kegg_id": "C00187",
    "hmdb_id": "HMDB0000067",
    "chebi_id": "16113",
    "lipidbank_id": "SST9061",
    "pubchem_cid": "5997",
}
CHOLESTEROL_BODY = json.dumps(CHOLESTEROL)

# REST compound/lm_id/LMGP01010005/classification
POPC_CLASSIFICATION = {
    "input": "LMGP01010005",
    "lm_id": "LMGP01010005",
    "name": "PC 16:0/18:1(9Z)",
    "sys_name": "1-hexadecanoyl-2-(9Z-octadecenoyl)-sn-glycero-3-phosphocholine",
    "core": "Glycerophospholipids [GP]",
    "main_class": "Glycerophosphocholines [GP01]",
    "sub_class": "Diacylglycerophosphocholines [GP0101]",
}
POPC_CLASSIFICATION_BODY = json.dumps(POPC_CLASSIFICATION)

# REST compound/abbrev/PC(34:1)/all - several hits come back as Row1..RowN
ABBREV_ROWS_BODY = json.dumps(
    {
        "Row1": {**POPC, "input": "PC(34:1)"},
        "Row2": {
            **POPC,
            "input": "PC(34:1)",
            "regno": "2848",
            "lm_id": "LMGP01010576",
            "name": "PC 16:0/18:1(11Z)",
        },
        "Row3": {**POPC, "input": "PC(34:1)"},  # duplicate id, must be collapsed
        "Row4": {"input": "PC(34:1)"},  # no lm_id: dropped
    }
)

MISS_BODY = "[]"
UNKNOWN_FIELD_BODY = (
    "This input item does not exist<br> Choose from: 'formula','regno','inchi_key','lm_id'"
)

# SPARQL name search ("palmitic acid"); the second row repeats the first lipid because
# every lipid carries two rdfs:label values.
SPARQL_NAME_SEARCH = {
    "head": {"vars": ["s", "name", "formula", "abbrev", "clsLabel"]},
    "results": {
        "bindings": [
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMFA01010001"},
                "name": {"type": "literal", "value": "Palmitic acid"},
                "formula": {"type": "literal", "value": "C16H32O2"},
                "abbrev": {"type": "literal", "value": "FA 16:0"},
                "clsLabel": {"type": "literal", "value": "Straight chain fatty acids [FA0101]"},
            },
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMFA01010001"},
                "name": {"type": "literal", "value": "Palmitic acid"},
            },
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMFA01010046"},
                "name": {"type": "literal", "value": "Palmitic acid(d3)"},
                "formula": {"type": "literal", "value": "C16H29D3O2"},
                "clsLabel": {"type": "literal", "value": "Straight chain fatty acids [FA0101]"},
            },
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/category/50101"},
                "name": {"type": "literal", "value": "not a lipid id"},
            },
            {"s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMFA01010047"}},
        ]
    },
}

SPARQL_EMPTY = {"head": {"vars": ["s"]}, "results": {"bindings": []}}


def sparql_labels(*labels: str) -> dict:
    """SPARQL result with one ``?l`` binding per category label."""
    return {
        "head": {"vars": ["l"]},
        "results": {"bindings": [{"l": {"type": "literal", "value": v}} for v in labels]},
    }


# SPARQL: labels of the sub class / main class / category nodes of ST0101
CLASS_LABELS_ST0101 = sparql_labels(
    "Cholesterol and derivatives [ST0101]", "Sterols [ST01]", "Sterol Lipids [ST]"
)

# SPARQL: members of ST0101 (two labels per lipid -> duplicate subject)
CLASS_MEMBERS_ST0101 = {
    "head": {"vars": ["s", "name"]},
    "results": {
        "bindings": [
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMST01010452"},
                "name": {"type": "literal", "value": "Colocynthenin E"},
            },
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMST01010535"},
                "name": {"type": "literal", "value": "Blechnoside A"},
            },
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMST01010535"},
                "name": {"type": "literal", "value": "3-O-(beta-D-glucopyranosyl)-cholestane"},
            },
            {
                "s": {"type": "uri", "value": "https://www.lipidmaps.org/rdf/LMST01010001"},
                "name": {"type": "literal", "value": "Cholesterol"},
            },
        ]
    },
}

# SPARQL: child classes of ST01 (label search for "[ST01")
CLASS_CHILDREN_ST01 = sparql_labels(
    "Sterols [ST01]",
    "Cholesterol and derivatives [ST0101]",
    "Spirostanols and derivatives [ST0108]",
    "Stigmasterols [ST0104]",
    "Something deeper [ST010101]",
)

# SPARQL: owl:equivalentClass of cholesterol
EQUIVALENT_CLASSES = {
    "head": {"vars": ["o"]},
    "results": {
        "bindings": [
            {"o": {"type": "uri", "value": "http://purl.obolibrary.org/obo/CHEBI_16113"}},
            {"o": {"type": "uri", "value": "https://swisslipids.org/rdf/SLM_000000287"}},
            {"o": {"type": "uri", "value": "https://example.org/other"}},
        ]
    },
}

# Metabolomics Workbench refmet/inchi_key/<key>/all
REFMET = {
    "inchi_key": "HVYWMOMLDIMFJA-DPAQBDIFSA-N",
    "name": "Cholesterol",
    "super_class": "Sterol Lipids",
    "refmet_id": "RM0135639",
}
