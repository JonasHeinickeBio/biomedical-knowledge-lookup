"""Trimmed real RxNav / RxClass responses (captured live from rxnav.nlm.nih.gov, 2026-10-06)."""

ALL_CLASSES = {
    "rxclassMinConceptList": {
        "rxclassMinConcept": [
            {
                "classId": "0",
                "className": "Anatomical Therapeutic Chemical",
                "classType": "ATC1-4",
            },
            {
                "classId": "A",
                "className": "ALIMENTARY TRACT AND METABOLISM",
                "classType": "ATC1-4",
            },
            {
                "classId": "A01AD",
                "className": "Other agents for local oral treatment",
                "classType": "ATC1-4",
            },
            {
                "classId": "A03D",
                "className": "ANTISPASMODICS IN COMBINATION WITH ANALGESICS",
                "classType": "ATC1-4",
            },
            {
                "classId": "A03DA",
                "className": "Synthetic anticholinergic agents in combination with analgesics",
                "classType": "ATC1-4",
            },
            {
                "classId": "A03DB",
                "className": "Belladonna and derivatives in combination with analgesics",
                "classType": "ATC1-4",
            },
            {
                "classId": "A03DC",
                "className": "Other antispasmodics in combination with analgesics",
                "classType": "ATC1-4",
            },
            {"classId": "B", "className": "BLOOD AND BLOOD FORMING ORGANS", "classType": "ATC1-4"},
            {
                "classId": "B01AC",
                "className": "Platelet aggregation inhibitors excl. heparin",
                "classType": "ATC1-4",
            },
            {"classId": "C", "className": "CARDIOVASCULAR SYSTEM", "classType": "ATC1-4"},
            {"classId": "C01EB", "className": "Other cardiac preparations", "classType": "ATC1-4"},
            {
                "classId": "G",
                "className": "GENITO URINARY SYSTEM AND SEX HORMONES",
                "classType": "ATC1-4",
            },
            {
                "classId": "G02CC",
                "className": "Antiinflammatory products for vaginal administration",
                "classType": "ATC1-4",
            },
            {"classId": "M", "className": "MUSCULO-SKELETAL SYSTEM", "classType": "ATC1-4"},
            {"classId": "M01AE", "className": "Propionic acid derivatives", "classType": "ATC1-4"},
            {
                "classId": "M02AA",
                "className": "Antiinflammatory preparations, non-steroids for topical use",
                "classType": "ATC1-4",
            },
            {"classId": "N", "className": "NERVOUS SYSTEM", "classType": "ATC1-4"},
            {"classId": "N01", "className": "ANESTHETICS", "classType": "ATC1-4"},
            {"classId": "N02", "className": "ANALGESICS", "classType": "ATC1-4"},
            {"classId": "N02A", "className": "OPIOIDS", "classType": "ATC1-4"},
            {"classId": "N02AA", "className": "Natural opium alkaloids", "classType": "ATC1-4"},
            {
                "classId": "N02AB",
                "className": "Phenylpiperidine derivatives",
                "classType": "ATC1-4",
            },
            {
                "classId": "N02AC",
                "className": "Diphenylpropylamine derivatives",
                "classType": "ATC1-4",
            },
            {"classId": "N02AD", "className": "Benzomorphan derivatives", "classType": "ATC1-4"},
            {"classId": "N02AE", "className": "Oripavine derivatives", "classType": "ATC1-4"},
            {"classId": "N02AF", "className": "Morphinan derivatives", "classType": "ATC1-4"},
            {
                "classId": "N02AG",
                "className": "Opioids in combination with antispasmodics",
                "classType": "ATC1-4",
            },
            {
                "classId": "N02AJ",
                "className": "Opioids in combination with non-opioid analgesics",
                "classType": "ATC1-4",
            },
            {"classId": "N02AX", "className": "Other opioids", "classType": "ATC1-4"},
            {
                "classId": "N02B",
                "className": "OTHER ANALGESICS AND ANTIPYRETICS",
                "classType": "ATC1-4",
            },
            {
                "classId": "N02BA",
                "className": "Salicylic acid and derivatives",
                "classType": "ATC1-4",
            },
            {"classId": "N02BB", "className": "Pyrazolones", "classType": "ATC1-4"},
            {"classId": "N02BE", "className": "Anilides", "classType": "ATC1-4"},
            {"classId": "N02BF", "className": "Gabapentinoids", "classType": "ATC1-4"},
            {
                "classId": "N02BG",
                "className": "Other analgesics and antipyretics",
                "classType": "ATC1-4",
            },
            {"classId": "N02C", "className": "ANTIMIGRAINE PREPARATIONS", "classType": "ATC1-4"},
            {"classId": "N02CA", "className": "Ergot alkaloids", "classType": "ATC1-4"},
            {"classId": "N02CB", "className": "Corticosteroid derivatives", "classType": "ATC1-4"},
            {
                "classId": "N02CC",
                "className": "Selective serotonin (5HT1) agonists",
                "classType": "ATC1-4",
            },
            {
                "classId": "N02CD",
                "className": "Calcitonin gene-related peptide (CGRP) antagonists",
                "classType": "ATC1-4",
            },
            {
                "classId": "N02CX",
                "className": "Other antimigraine preparations",
                "classType": "ATC1-4",
            },
            {"classId": "N03", "className": "ANTIEPILEPTICS", "classType": "ATC1-4"},
            {"classId": "R", "className": "RESPIRATORY SYSTEM", "classType": "ATC1-4"},
            {"classId": "R02AX", "className": "Other throat preparations", "classType": "ATC1-4"},
            {"classId": "S", "className": "SENSORY ORGANS", "classType": "ATC1-4"},
            {"classId": "S02DA", "className": "Analgesics and anesthetics", "classType": "ATC1-4"},
        ]
    }
}

BY_RXCUI_ASPIRIN = {
    "rxclassDrugInfoList": {
        "rxclassDrugInfo": [
            {
                "minConcept": {"name": "aspirin", "rxcui": "1191", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "A01AD",
                    "className": "Other agents for local oral treatment",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "aspirin", "rxcui": "1191", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "B01AC",
                    "className": "Platelet aggregation inhibitors excl. heparin",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "aspirin", "rxcui": "1191", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "N02BA",
                    "className": "Salicylic acid and derivatives",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "aspirin / codeine", "rxcui": "135095", "tty": "MIN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "N02AJ",
                    "className": "Opioids in combination with non-opioid analgesics",
                    "classType": "ATC1-4",
                },
            },
        ]
    }
}

BY_DRUGNAME_ADVIL = {
    "rxclassDrugInfoList": {
        "rxclassDrugInfo": [
            {
                "minConcept": {"name": "ibuprofen", "rxcui": "5640", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "C01EB",
                    "className": "Other cardiac preparations",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "ibuprofen", "rxcui": "5640", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "G02CC",
                    "className": "Antiinflammatory products for vaginal administration",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "ibuprofen", "rxcui": "5640", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "M01AE",
                    "className": "Propionic acid derivatives",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "ibuprofen", "rxcui": "5640", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "M02AA",
                    "className": "Antiinflammatory preparations, non-steroids for topical use",
                    "classType": "ATC1-4",
                },
            },
            {
                "minConcept": {"name": "ibuprofen", "rxcui": "5640", "tty": "IN"},
                "rela": "",
                "relaSource": "ATC",
                "rxclassMinConceptItem": {
                    "classId": "R02AX",
                    "className": "Other throat preparations",
                    "classType": "ATC1-4",
                },
            },
        ]
    }
}

CLASS_MEMBERS_N02BA = {
    "drugMemberGroup": {
        "drugMember": [
            {
                "minConcept": {"name": "aspirin", "rxcui": "1191", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA01"},
                    {"attrName": "SourceName", "attrValue": "acetylsalicylic acid"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "benorilate", "rxcui": "1372", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA10"},
                    {"attrName": "SourceName", "attrValue": "benorilate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "aloxiprin", "rxcui": "17393", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA02"},
                    {"attrName": "SourceName", "attrValue": "aloxiprin"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "choline salicylate", "rxcui": "20974", "tty": "PIN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA03"},
                    {"attrName": "SourceName", "attrValue": "choline salicylate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "potassium salicylate", "rxcui": "235418", "tty": "PIN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA12"},
                    {"attrName": "SourceName", "attrValue": "potassium salicylate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "morpholine salicylate", "rxcui": "236348", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA08"},
                    {"attrName": "SourceName", "attrValue": "morpholine salicylate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "ethenzamide", "rxcui": "24468", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA07"},
                    {"attrName": "SourceName", "attrValue": "ethenzamide"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {
                    "name": "imidazole-2-hydroxybenzoate",
                    "rxcui": "27438",
                    "tty": "IN",
                },
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA16"},
                    {"attrName": "SourceName", "attrValue": "imidazole salicylate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "diflunisal", "rxcui": "3393", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA11"},
                    {"attrName": "SourceName", "attrValue": "diflunisal"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "salsalate", "rxcui": "36108", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA06"},
                    {"attrName": "SourceName", "attrValue": "salsalate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "salicylamide", "rxcui": "9518", "tty": "IN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA05"},
                    {"attrName": "SourceName", "attrValue": "salicylamide"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
            {
                "minConcept": {"name": "sodium salicylate", "rxcui": "9907", "tty": "PIN"},
                "nodeAttr": [
                    {"attrName": "SourceId", "attrValue": "N02BA04"},
                    {"attrName": "SourceName", "attrValue": "sodium salicylate"},
                    {"attrName": "Relation", "attrValue": "DIRECT"},
                ],
            },
        ]
    }
}

PROPERTIES_ASPIRIN = {
    "properties": {
        "language": "ENG",
        "name": "aspirin",
        "rxcui": "1191",
        "suppress": "N",
        "synonym": "",
        "tty": "IN",
        "umlscui": "",
    }
}

RXCUI_IBUPROFEN = {"idGroup": {"rxnormId": ["5640"]}}

APPROXIMATE_FLUOXETIN = {
    "approximateGroup": {
        "candidate": [
            {
                "rank": "1",
                "rxaui": "10326783",
                "rxcui": "4493",
                "score": "12.082275390625",
                "source": "GS",
            },
            {
                "name": "fluoxetine",
                "rank": "1",
                "rxaui": "12253888",
                "rxcui": "4493",
                "score": "12.082275390625",
                "source": "RXNORM",
            },
        ],
        "inputTerm": None,
    }
}

APPROXIMATE_ASPRIN_WEAK = {
    "approximateGroup": {
        "candidate": [
            {
                "rank": "1",
                "rxaui": "1161308",
                "rxcui": "313782",
                "score": "5.519745212594296",
                "source": "MMSL",
            }
        ],
        "inputTerm": None,
    }
}

EMPTY = {}
