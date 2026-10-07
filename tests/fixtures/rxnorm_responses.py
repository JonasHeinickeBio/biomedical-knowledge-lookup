"""Trimmed real RxNav (RxNorm) responses captured live on 2026-10-07 for RxNormAdapter tests.

Hand-written entries (marked in the tests by their names: PROPERTIES_ADVIL*, PROPERTIES_PIN,
PROPERTIES_SCDC, PROPERTIES_FLUOXETINE, RELATED_ADVIL) copy the exact field layout of real
responses seen live; PROPERTIES_PIN carries a made-up UMLS CUI to exercise that branch.
"""

EXACT_ASPIRIN = {"idGroup": {"rxnormId": ["1191"]}}

EXACT_ADVIL = {"idGroup": {"rxnormId": ["153010"]}}

EXACT_NONE = {"idGroup": {}}

PROPERTIES_ASPIRIN = {
    "properties": {
        "rxcui": "1191",
        "name": "aspirin",
        "synonym": "",
        "tty": "IN",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_ADVIL = {
    "properties": {
        "rxcui": "153010",
        "name": "Advil",
        "synonym": "",
        "tty": "BN",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_ASPIRIN_81 = {
    "properties": {
        "rxcui": "243670",
        "name": "aspirin 81 MG Oral Tablet",
        "synonym": "ASA 81 MG Oral Tablet",
        "tty": "SCD",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_ADVIL_TABLET = {
    "properties": {
        "rxcui": "153008",
        "name": "ibuprofen 200 MG Oral Tablet [Advil]",
        "synonym": "Advil 200 MG Oral Tablet",
        "tty": "SBD",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_ORAL_TABLET = {
    "properties": {
        "rxcui": "317541",
        "name": "Oral Tablet",
        "synonym": "",
        "tty": "DF",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_PIN = {
    "properties": {
        "rxcui": "314293",
        "name": "acetylsalicylate sodium",
        "synonym": "",
        "tty": "PIN",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "C0000001",
    }
}

PROPERTIES_FLUOXETINE = {
    "properties": {
        "rxcui": "4493",
        "name": "fluoxetine",
        "synonym": "",
        "tty": "IN",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_SCDC = {
    "properties": {
        "rxcui": "316074",
        "name": "ibuprofen 200 MG",
        "synonym": "",
        "tty": "SCDC",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
}

PROPERTIES_MISSING = {}

DRUGS_ASPIRIN = {
    "drugGroup": {
        "name": None,
        "conceptGroup": [
            {
                "tty": "BPCK",
                "conceptProperties": [
                    {
                        "rxcui": "2047428",
                        "name": "{100 (acetaminophen 250 MG / "
                        "aspirin 250 MG / caffeine 65 "
                        "MG Oral Tablet [Excedrin]) / "
                        "24 (acetaminophen 250 MG / "
                        "aspirin 250 MG / "
                        "diphenhydramine citrate 38 MG "
                        "Oral Tablet [Excedrin PM "
                        "Triple Action]) } Pack "
                        "[Excedrin PM Triple Action "
                        "Caplets and Excedrin Extra "
                        "Strength Pain Reliever]",
                        "synonym": "Excedrin PM Triple Action "
                        "Caplets and Excedrin Extra "
                        "Strength Pain Reliever Kit",
                        "tty": "BPCK",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
            {
                "tty": "SBD",
                "conceptProperties": [
                    {
                        "rxcui": "1052416",
                        "name": "acetaminophen 250 MG / "
                        "aspirin 250 MG / caffeine 65 "
                        "MG Oral Tablet [Pamprin Max "
                        "Formula]",
                        "synonym": "APAP 250 MG / ASA 250 MG / "
                        "Caffeine 65 MG Oral Tablet "
                        "[Pamprin Max Formula]",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "1052678",
                        "name": "aspirin 81 MG Delayed Release Oral Tablet [Miniprin]",
                        "synonym": "Miniprin 81 MG Delayed Release Oral Tablet",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                ],
            },
            {
                "tty": "SCD",
                "conceptProperties": [
                    {
                        "rxcui": "103863",
                        "name": "aspirin 150 MG Rectal Suppository",
                        "synonym": "ASA 150 MG Rectal Suppository",
                        "tty": "SCD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "103954",
                        "name": "aspirin 75 MG Delayed Release Oral Tablet",
                        "synonym": "ASA 75 MG Delayed Release Oral Tablet",
                        "tty": "SCD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                ],
            },
        ],
    }
}

DRUGS_NONE = {"drugGroup": {"name": None}}

APPROX_FLUOXETIN = {
    "approximateGroup": {
        "inputTerm": None,
        "candidate": [
            {
                "rxcui": "4493",
                "rxaui": "10326783",
                "score": "12.33076286315918",
                "rank": "1",
                "source": "GS",
            },
            {
                "rxcui": "4493",
                "rxaui": "12253888",
                "score": "12.33076286315918",
                "rank": "1",
                "name": "fluoxetine",
                "source": "RXNORM",
            },
            {
                "rxcui": "4493",
                "rxaui": "137571",
                "score": "12.33076286315918",
                "rank": "1",
                "source": "MMSL",
            },
        ],
    }
}

APPROX_WEAK = {
    "approximateGroup": {
        "inputTerm": None,
        "candidate": [
            {
                "rxcui": "21009",
                "rxaui": "10280908",
                "score": "7.937132692337036",
                "rank": "1",
                "name": "Chromic Chloride",
                "source": "USP",
            },
            {
                "rxcui": "90402",
                "rxaui": "12254023",
                "score": "7.937132692337036",
                "rank": "1",
                "name": "chromic sulfate",
                "source": "RXNORM",
            },
        ],
    }
}

APPROX_EMPTY = {"approximateGroup": {"inputTerm": None}}

RELATED_ASPIRIN = {
    "relatedGroup": {
        "rxcui": None,
        "conceptGroup": [
            {
                "tty": "BN",
                "conceptProperties": [
                    {
                        "rxcui": "1052413",
                        "name": "Pamprin Max Formula",
                        "synonym": "",
                        "tty": "BN",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "1053324",
                        "name": "Stanback Headache Powder Reformulated Jan 2011",
                        "synonym": "",
                        "tty": "BN",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "1247393",
                        "name": "BC Arthritis",
                        "synonym": "",
                        "tty": "BN",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                ],
            },
            {
                "tty": "PIN",
                "conceptProperties": [
                    {
                        "rxcui": "314293",
                        "name": "acetylsalicylate sodium",
                        "synonym": "",
                        "tty": "PIN",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
            {
                "tty": "SBD",
                "conceptProperties": [
                    {
                        "rxcui": "1052416",
                        "name": "acetaminophen 250 MG / "
                        "aspirin 250 MG / caffeine "
                        "65 MG Oral Tablet [Pamprin "
                        "Max Formula]",
                        "synonym": "APAP 250 MG / ASA 250 "
                        "MG / Caffeine 65 MG "
                        "Oral Tablet [Pamprin "
                        "Max Formula]",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "1052678",
                        "name": "aspirin 81 MG Delayed Release Oral Tablet [Miniprin]",
                        "synonym": "Miniprin 81 MG Delayed Release Oral Tablet",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "1053327",
                        "name": "aspirin 845 MG / caffeine "
                        "65 MG Oral Powder "
                        "[Stanback Headache Powder "
                        "Reformulated Jan 2011]",
                        "synonym": "ASA 845 MG / Caffeine "
                        "65 MG Oral Powder "
                        "[Stanback Headache "
                        "Powder Reformulated Jan "
                        "2011]",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                ],
            },
            {
                "tty": "SCD",
                "conceptProperties": [
                    {
                        "rxcui": "103863",
                        "name": "aspirin 150 MG Rectal Suppository",
                        "synonym": "ASA 150 MG Rectal Suppository",
                        "tty": "SCD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "103954",
                        "name": "aspirin 75 MG Delayed Release Oral Tablet",
                        "synonym": "ASA 75 MG Delayed Release Oral Tablet",
                        "tty": "SCD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                    {
                        "rxcui": "104474",
                        "name": "aspirin 75 MG Oral Tablet",
                        "synonym": "ASA 75 MG Oral Tablet",
                        "tty": "SCD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    },
                ],
            },
        ],
    }
}

RELATED_ADVIL = {
    "relatedGroup": {
        "rxcui": None,
        "conceptGroup": [
            {
                "tty": "IN",
                "conceptProperties": [
                    {
                        "rxcui": "5640",
                        "name": "ibuprofen",
                        "synonym": "",
                        "tty": "IN",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
            {
                "tty": "SBD",
                "conceptProperties": [
                    {
                        "rxcui": "153008",
                        "name": "ibuprofen 200 MG Oral Tablet [Advil]",
                        "synonym": "Advil 200 MG Oral Tablet",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
        ],
    }
}

RELATED_ASPIRIN_81 = {
    "relatedGroup": {
        "rxcui": None,
        "conceptGroup": [
            {
                "tty": "DF",
                "conceptProperties": [
                    {
                        "rxcui": "317541",
                        "name": "Oral Tablet",
                        "synonym": "",
                        "tty": "DF",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
            {
                "tty": "IN",
                "conceptProperties": [
                    {
                        "rxcui": "1191",
                        "name": "aspirin",
                        "synonym": "",
                        "tty": "IN",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
            {
                "tty": "SBD",
                "conceptProperties": [
                    {
                        "rxcui": "724444",
                        "name": "aspirin 81 MG Oral Tablet [Anacin Aspirin Regimen]",
                        "synonym": "Anacin Aspirin Regimen 81 MG Oral Tablet",
                        "tty": "SBD",
                        "language": "ENG",
                        "suppress": "N",
                        "umlscui": "",
                    }
                ],
            },
        ],
    }
}

RELATED_EMPTY = {"relatedGroup": {"rxcui": None, "conceptGroup": [{"tty": "IN"}]}}

CODES_ASPIRIN = {
    "propConceptGroup": {
        "propConcept": [
            {"propCategory": "CODES", "propName": "ATC", "propValue": "A01AD05"},
            {"propCategory": "CODES", "propName": "ATC", "propValue": "B01AC06"},
            {"propCategory": "CODES", "propName": "ATC", "propValue": "N02BA01"},
            {"propCategory": "CODES", "propName": "DRUGBANK", "propValue": "DB00945"},
            {"propCategory": "CODES", "propName": "RxCUI", "propValue": "1191"},
            {"propCategory": "CODES", "propName": "SNOMEDCT", "propValue": "387458008"},
            {"propCategory": "CODES", "propName": "SNOMEDCT", "propValue": "7947003"},
            {"propCategory": "CODES", "propName": "UNII_CODE", "propValue": "R16CO5Y76E"},
            {"propCategory": "CODES", "propName": "USP", "propValue": "m6240"},
            {"propCategory": "CODES", "propName": "VUID", "propValue": "4017536"},
            {
                "propCategory": "CODES",
                "propName": "SPL_SET_ID",
                "propValue": "0039fee5-35a8-429b-a1cf-7b4bf1f8a6e7",
            },
            {
                "propCategory": "CODES",
                "propName": "SPL_SET_ID",
                "propValue": "0058175f-3474-40c3-a046-6cfaec86d84b",
            },
        ]
    }
}

CODES_EMPTY = {}

NDCS_ASPIRIN_81 = {
    "ndcGroup": {
        "rxcui": None,
        "ndcList": {
            "ndc": [
                "21130048112",
                "21130048120",
                "21130048132",
                "21130048150",
                "71800004002",
                "84324001701",
            ]
        },
    }
}

NDCS_EMPTY = {"ndcGroup": {"rxcui": None, "ndcList": {}}}
