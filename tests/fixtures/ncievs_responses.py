"""Real NCI EVS REST API responses recorded on 2026-10-08, keyed by the request that
produced them; replayed by the unit tests of the adapter. No network."""

from typing import Any
from urllib.parse import urlencode


def request_key(url: str, params: dict[str, Any] | None) -> str:
    """Stable key for a (url, params) pair, matching how the fixtures were recorded."""
    return url + "?" + urlencode(sorted((params or {}).items()))


RECORDED: dict[str, Any] = {
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/search?include=summary&pageSize=3&term=fatigue&type=contains": {
        "total": 438,
        "timeTaken": 39,
        "parameters": {
            "term": "fatigue",
            "type": "contains",
            "include": "summary",
            "fromRecord": 0,
            "pageSize": 3,
            "terminology": ["ncit"],
        },
        "concepts": [
            {
                "code": "C3036",
                "name": "Fatigue",
                "terminology": "ncit",
                "version": "26.09d",
                "conceptStatus": "DEFAULT",
                "leaf": False,
                "active": True,
                "synonyms": [
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "ACC/AHA",
                        "code": "VAR",
                        "subSource": "SARS2",
                    },
                    {
                        "name": "Fatigue (lassitude)",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "ACC/AHA",
                        "subSource": "PCC",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "SY",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "caDSR",
                    },
                    {
                        "name": "FATIGUE",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "CDISC",
                    },
                ],
                "definitions": [
                    {
                        "definition": "Overall tiredness and lack of energy.",
                        "code": "P97",
                        "type": "DEFINITION",
                        "source": "NCI",
                        "qualifiers": [{"code": "P381", "type": "attribution", "value": "NICHD"}],
                    },
                    {
                        "definition": "A condition marked by extreme tiredness "
                        "and inability to function due lack of "
                        "energy. Fatigue may be acute or chronic.",
                        "code": "P325",
                        "type": "ALT_DEFINITION",
                        "source": "NCI-GLOSS",
                    },
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "code": "P325",
                        "type": "ALT_DEFINITION",
                        "source": "CTCAE",
                    },
                ],
                "properties": [
                    {"code": "P106", "type": "Semantic_Type", "value": "Sign or Symptom"},
                    {"code": "P207", "type": "UMLS_CUI", "value": "C0015672"},
                    {"code": "oboInOwl:hasDbXref", "type": "xRef", "value": "IMDRF:E2312"},
                ],
            },
            {
                "code": "C146753",
                "name": "Fatigue, CTCAE",
                "terminology": "ncit",
                "version": "26.09d",
                "conceptStatus": "DEFAULT",
                "leaf": False,
                "active": True,
                "synonyms": [
                    {
                        "name": "Fatigue, CTCAE 5.0",
                        "termType": "SY",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "caDSR",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "CTCAE 5.0",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "CTCAE 6.0",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "GDC",
                    },
                ],
                "definitions": [
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "code": "P97",
                        "type": "DEFINITION",
                        "source": "NCI",
                        "qualifiers": [
                            {"code": "P381", "type": "attribution", "value": "CTCAE 5.0, 6.0"}
                        ],
                    },
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "code": "P325",
                        "type": "ALT_DEFINITION",
                        "source": "CTCAE 6.0",
                    },
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "code": "P325",
                        "type": "ALT_DEFINITION",
                        "source": "CTCAE 5.0",
                    },
                ],
                "properties": [
                    {"code": "P208", "type": "NCI_META_CUI", "value": "CL550640"},
                    {"code": "P106", "type": "Semantic_Type", "value": "Finding"},
                ],
            },
            {
                "code": "C122347",
                "name": "Fatigue Subordinate Domain",
                "terminology": "ncit",
                "version": "26.09d",
                "conceptStatus": "DEFAULT",
                "leaf": True,
                "active": True,
                "synonyms": [
                    {
                        "name": "Fatigue",
                        "termType": "SY",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "caDSR",
                    },
                    {
                        "name": "Fatigue Item Bank",
                        "termType": "SY",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "NCI",
                    },
                    {
                        "name": "Fatigue Subordinate Domain",
                        "termType": "PT",
                        "type": "FULL_SYN",
                        "typeCode": "P90",
                        "source": "NCI",
                    },
                    {
                        "name": "Fatigue Subordinate Domain",
                        "type": "Preferred_Name",
                        "typeCode": "P108",
                    },
                ],
                "definitions": [
                    {
                        "definition": "The collection of PROMIS item scales that "
                        "assess fatigue that is likely to decrease "
                        "an individual's ability to carry out "
                        "daily activities, including the ability "
                        "to work effectively and to function at "
                        "their usual level in family or social "
                        "roles.",
                        "code": "P97",
                        "type": "DEFINITION",
                        "source": "NCI",
                    }
                ],
                "properties": [
                    {"code": "P106", "type": "Semantic_Type", "value": "Functional Concept"},
                    {"code": "P207", "type": "UMLS_CUI", "value": "C4050243"},
                ],
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncim/search?include=summary&pageSize=3&term=fatigue&type=contains": {
        "total": 1140,
        "timeTaken": 60,
        "parameters": {
            "term": "fatigue",
            "type": "contains",
            "include": "summary",
            "fromRecord": 0,
            "pageSize": 3,
            "terminology": ["ncim"],
        },
        "concepts": [
            {
                "code": "C0015672",
                "name": "Fatigue",
                "terminology": "ncim",
                "version": "202608",
                "active": True,
                "synonyms": [
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "HPO",
                        "code": "HP:0012378",
                        "qualifiers": [
                            {"type": "DATE_CREATED", "value": "2013-10-15T08:52:04Z"},
                            {
                                "type": "HPO_COMMENT",
                                "value": "Fatigue is distinct from muscle weakness.",
                            },
                        ],
                    },
                    {
                        "name": "Fatigue",
                        "termType": "SY",
                        "type": "Preferred_Name",
                        "source": "HPO",
                        "code": "HP:0012378",
                        "qualifiers": [{"type": "SYN_QUALIFIER", "value": "layperson term"}],
                    },
                    {
                        "name": "Tired",
                        "termType": "SY",
                        "type": "Synonym",
                        "source": "HPO",
                        "code": "HP:0012378",
                        "qualifiers": [{"type": "SYN_QUALIFIER", "value": "layperson term"}],
                    },
                    {
                        "name": "Fatigue NOS",
                        "termType": "ET",
                        "type": "Synonym",
                        "source": "ICD10CM",
                        "code": "R53.83",
                    },
                    {
                        "name": "Lack of energy",
                        "termType": "ET",
                        "type": "Synonym",
                        "source": "ICD10CM",
                        "code": "R53.83",
                    },
                    {
                        "name": "Tiredness",
                        "termType": "ET",
                        "type": "Synonym",
                        "source": "ICD10CM",
                        "code": "R53.83",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "CN",
                        "type": "Preferred_Name",
                        "source": "LNC",
                        "code": "MTHU013358",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "LA",
                        "type": "Preferred_Name",
                        "source": "LNC",
                        "code": "LA7542-9",
                    },
                    {
                        "name": "Lack of energy",
                        "termType": "CN",
                        "type": "Synonym",
                        "source": "LNC",
                        "code": "MTHU068534",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "LLT",
                        "type": "Preferred_Name",
                        "source": "MDR",
                        "code": "10016256",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "MDR",
                        "code": "10016256",
                    },
                    {
                        "name": "Energy decreased",
                        "termType": "LLT",
                        "type": "Synonym",
                        "source": "MDR",
                        "code": "10057841",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "MEDLINEPLUS",
                        "code": "5324",
                        "qualifiers": [
                            {"type": "DATE_CREATED", "value": "03/08/2010"},
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Spanish https://medlineplus.gov/spanish/fatigue.html",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Japanese "
                                "https://medlineplus.gov/languages/fatigue.html#Japanese",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Ukrainian "
                                "https://medlineplus.gov/languages/fatigue.html#Ukrainian",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "French "
                                "https://medlineplus.gov/languages/fatigue.html#French",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Hindi "
                                "https://medlineplus.gov/languages/fatigue.html#Hindi",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Korean "
                                "https://medlineplus.gov/languages/fatigue.html#Korean",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Somali "
                                "https://medlineplus.gov/languages/fatigue.html#Somali",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Russian "
                                "https://medlineplus.gov/languages/fatigue.html#Russian",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Spanish "
                                "https://medlineplus.gov/languages/fatigue.html#Spanish",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Arabic "
                                "https://medlineplus.gov/languages/fatigue.html#Arabic",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Polish "
                                "https://medlineplus.gov/languages/fatigue.html#Polish",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Vietnamese "
                                "https://medlineplus.gov/languages/fatigue.html#Vietnamese",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Chinese, Simplified (Mandarin "
                                "dialect) "
                                "https://medlineplus.gov/languages/fatigue.html#Chinese, "
                                "Simplified (Mandarin dialect)",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Haitian Creole "
                                "https://medlineplus.gov/languages/fatigue.html#Haitian "
                                "Creole",
                            },
                            {
                                "type": "SOS",
                                "value": "Are you tired? Find out about "
                                "some of the common and uncommon "
                                "causes of fatigue and how to help "
                                "yourself. "
                                "https://medlineplus.gov/fatigue.html",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Portuguese "
                                "https://medlineplus.gov/languages/fatigue.html#Portuguese",
                            },
                            {
                                "type": "MP_OTHER_LANGUAGE_URL",
                                "value": "Tagalog "
                                "https://medlineplus.gov/languages/fatigue.html#Tagalog",
                            },
                        ],
                    },
                    {
                        "name": "Tiredness",
                        "termType": "SY",
                        "type": "Synonym",
                        "source": "MEDLINEPLUS",
                        "code": "5324",
                    },
                    {
                        "name": "Tiredness",
                        "termType": "ET",
                        "type": "Synonym",
                        "source": "MEDLINEPLUS",
                        "code": "5324",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "MH",
                        "type": "Preferred_Name",
                        "source": "MSH",
                        "code": "D005221",
                        "qualifiers": [
                            {"type": "DX", "value": "19660101"},
                            {
                                "type": "AQL",
                                "value": "BL CF CI CL CN CO DG DH DI DT EC "
                                "EH EM EN EP ET GE HI IM ME MI MO "
                                "NU PA PC PP PS PX RH RT SU TH UR "
                                "VE VI",
                            },
                            {
                                "type": "AN",
                                "value": "do not use for fatigue of "
                                "isolated muscle fibers in physiol "
                                "exper ( = MUSCLE FATIGUE)",
                            },
                            {"type": "DC", "value": "1"},
                            {"type": "FX", "value": "D001247"},
                            {"type": "MMR", "value": "19991103"},
                            {"type": "MN", "value": "C23.888.369"},
                            {"type": "TERMUI", "value": "T015996"},
                            {"type": "TH", "value": "POPLINE (1978)"},
                        ],
                    },
                    {
                        "name": "Tiredness",
                        "termType": "ET",
                        "type": "Synonym",
                        "source": "MTHICD9",
                        "code": "780.79",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "NCI",
                        "code": "C3036",
                    },
                    {
                        "name": "Lack of Energy",
                        "termType": "SY",
                        "type": "Synonym",
                        "source": "NCI",
                        "code": "C3036",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PTCS",
                        "type": "Preferred_Name",
                        "source": "OMIM",
                        "code": "MTHU010062",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "SNOMEDCT_US",
                        "code": "84229001",
                        "qualifiers": [
                            {"type": "TYPE_ID", "value": "900000000000013009"},
                            {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                        ],
                    },
                    {
                        "name": "Fatigue (finding)",
                        "termType": "FN",
                        "type": "Synonym",
                        "source": "SNOMEDCT_US",
                        "code": "84229001",
                        "qualifiers": [
                            {"type": "TYPE_ID", "value": "900000000000003001"},
                            {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                        ],
                    },
                    {
                        "name": "Lack of energy",
                        "termType": "PT",
                        "type": "Synonym",
                        "source": "SNOMEDCT_US",
                        "code": "248274002",
                        "qualifiers": [
                            {"type": "TYPE_ID", "value": "900000000000013009"},
                            {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                        ],
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "ACC-AHA",
                        "code": "VAR",
                    },
                    {
                        "name": "Fatigue (lassitude)",
                        "termType": "PT",
                        "type": "Synonym",
                        "source": "ACC-AHA",
                        "code": "C3036",
                    },
                    {
                        "name": "decreased energy",
                        "termType": "NP",
                        "type": "Synonym",
                        "source": "AOD",
                        "code": "0000021621",
                    },
                    {
                        "name": "fatigue",
                        "termType": "DE",
                        "type": "Synonym",
                        "source": "AOD",
                        "code": "0000001768",
                        "qualifiers": [{"type": "HN", "value": "ETOH descriptor 2000."}],
                    },
                ],
                "definitions": [
                    {
                        "definition": "<h3>What is fatigue?</h3> <p>Fatigue is a "
                        "feeling of weariness, tiredness, or lack "
                        "of energy. It can interfere with your "
                        "usual daily activities. Fatigue can be a "
                        "normal response to physical activity, "
                        "emotional <a "
                        'href="https://medlineplus.gov/stress.html">stress</a>, '
                        "boredom, or lack of sleep. But sometimes "
                        "it can be a sign of a mental or physical "
                        "condition. If you have been feeling tired "
                        "for weeks, contact your health care "
                        "provider. They can help you find out "
                        "what's causing your fatigue and recommend "
                        "ways to relieve it.</p>",
                        "type": "DEFINITION",
                        "source": "MEDLINEPLUS",
                    },
                    {
                        "definition": "A condition marked by extreme tiredness "
                        "and inability to function due lack of "
                        "energy. Fatigue may be acute or chronic.",
                        "type": "DEFINITION",
                        "source": "NCI-GLOSS",
                    },
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "type": "DEFINITION",
                        "source": "CTCAE",
                    },
                ],
                "properties": [{"type": "Semantic_Type", "value": "Sign or Symptom"}],
            },
            {
                "code": "CL412928",
                "name": "Fatigue fracture",
                "terminology": "ncim",
                "version": "202608",
                "active": True,
                "synonyms": [
                    {
                        "name": "Fatigue fracture",
                        "termType": "LLT",
                        "type": "Preferred_Name",
                        "source": "MDR",
                        "code": "10079025",
                    },
                    {
                        "name": "Fatigue fractures",
                        "termType": "PTCS",
                        "type": "Synonym",
                        "source": "OMIM",
                        "code": "MTHU033152",
                    },
                    {
                        "name": "fatigue",
                        "termType": "SY",
                        "type": "Synonym",
                        "source": "RADLEX",
                        "code": "RID6339",
                    },
                    {
                        "name": "fatigue fracture",
                        "termType": "PT",
                        "type": "Synonym",
                        "source": "RADLEX",
                        "code": "RID6339",
                    },
                ],
                "definitions": [
                    {
                        "definition": 'A "fatigue fracture" occurs when abnormal '
                        "stress is applied to bone with normal "
                        "elastic resistance.",
                        "type": "DEFINITION",
                        "source": "RADLEX",
                    }
                ],
                "properties": [{"type": "Semantic_Type", "value": "Injury or Poisoning"}],
            },
            {
                "code": "CL550640",
                "name": "Fatigue, CTCAE",
                "terminology": "ncim",
                "version": "202608",
                "active": True,
                "synonyms": [
                    {
                        "name": "Fatigue, CTCAE",
                        "termType": "PT",
                        "type": "Preferred_Name",
                        "source": "NCI",
                        "code": "C146753",
                    },
                    {
                        "name": "Fatigue, CTCAE_5",
                        "termType": "SY",
                        "type": "Synonym",
                        "source": "caDSR",
                        "code": "C146753",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Synonym",
                        "source": "CTCAE_5",
                        "code": "C146753",
                    },
                    {
                        "name": "Fatigue",
                        "termType": "PT",
                        "type": "Synonym",
                        "source": "GDC",
                        "code": "C146753",
                    },
                    {
                        "name": "Fatigue (Priority 2)",
                        "termType": "PT",
                        "type": "Synonym",
                        "source": "OORO",
                        "code": "C146753",
                    },
                ],
                "definitions": [
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "type": "DEFINITION",
                        "source": "CTCAE_5",
                    },
                    {
                        "definition": "A disorder characterized by a state of "
                        "generalized weakness with a pronounced "
                        "inability to summon sufficient energy to "
                        "accomplish daily activities.",
                        "type": "DEFINITION",
                        "source": "NCI",
                    },
                ],
                "properties": [{"type": "Semantic_Type", "value": "Finding"}],
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/search?include=summary&pageSize=3&term=zzzzqqqq&type=contains": {
        "total": 0,
        "timeTaken": 33,
        "parameters": {
            "term": "zzzzqqqq",
            "type": "contains",
            "include": "summary",
            "fromRecord": 0,
            "pageSize": 3,
            "terminology": ["ncit"],
        },
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/C3036?include=summary%2Cparents%2Cchildren": {
        "code": "C3036",
        "name": "Fatigue",
        "terminology": "ncit",
        "version": "26.09d",
        "conceptStatus": "DEFAULT",
        "leaf": False,
        "active": True,
        "synonyms": [
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "ACC/AHA",
                "code": "VAR",
                "subSource": "SARS2",
            },
            {
                "name": "Fatigue (lassitude)",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "ACC/AHA",
                "subSource": "PCC",
            },
            {
                "name": "Fatigue",
                "termType": "SY",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "caDSR",
            },
            {
                "name": "FATIGUE",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "CDISC",
            },
        ],
        "definitions": [
            {
                "definition": "Overall tiredness and lack of energy.",
                "code": "P97",
                "type": "DEFINITION",
                "source": "NCI",
                "qualifiers": [{"code": "P381", "type": "attribution", "value": "NICHD"}],
            },
            {
                "definition": "A condition marked by extreme tiredness and inability "
                "to function due lack of energy. Fatigue may be acute or "
                "chronic.",
                "code": "P325",
                "type": "ALT_DEFINITION",
                "source": "NCI-GLOSS",
            },
            {
                "definition": "A disorder characterized by a state of generalized "
                "weakness with a pronounced inability to summon "
                "sufficient energy to accomplish daily activities.",
                "code": "P325",
                "type": "ALT_DEFINITION",
                "source": "CTCAE",
            },
        ],
        "properties": [
            {"code": "P106", "type": "Semantic_Type", "value": "Sign or Symptom"},
            {"code": "P207", "type": "UMLS_CUI", "value": "C0015672"},
            {"code": "oboInOwl:hasDbXref", "type": "xRef", "value": "IMDRF:E2312"},
        ],
        "children": [
            {"code": "C5062", "name": "Cancer Fatigue", "leaf": True},
            {"code": "C180621", "name": "Exertional Fatigue", "leaf": True},
            {"code": "C181246", "name": "Exhaustion", "leaf": True},
            {"code": "C50556", "name": "Extreme Exhaustion", "leaf": True},
            {"code": "C34846", "name": "Nervous Debility", "leaf": True},
        ],
        "parents": [{"code": "C3858", "name": "Mental and Behavioral Signs and Symptoms"}],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/C3037?include=summary%2Cparents%2Cchildren": {
        "code": "C3037",
        "name": "Chronic Fatigue Syndrome",
        "terminology": "ncit",
        "version": "26.09d",
        "conceptStatus": "DEFAULT",
        "leaf": True,
        "active": True,
        "synonyms": [
            {
                "name": "Myalgic encephalomyelitis/chronic fatigue syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "ACC/AHA",
                "code": "AV",
                "subSource": "SARS2",
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "GDC",
            },
            {
                "name": "chronic fatigue syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "NCI-GLOSS",
                "code": "CDR0000468799",
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "NCI",
            },
        ],
        "definitions": [
            {
                "definition": "A syndrome of unknown etiology. Chronic fatigue "
                "syndrome (CFS) is a clinical diagnosis characterized by "
                "an unexplained persistent or relapsing chronic fatigue "
                "that is of at least six months' duration, is not the "
                "result of ongoing exertion, is not substantially "
                "alleviated by rest, and results in substantial "
                "reduction of previous levels of occupational, "
                "educational, social, or personal activities. Common "
                "concurrent symptoms of at least six months duration "
                "include impairment of memory or concentration, diffuse "
                "pain, sore throat, tender lymph nodes, headaches of a "
                "new type, pattern, or severity, and nonrestorative "
                "sleep. The etiology of CFS may be viral or immunologic. "
                "Neurasthenia and fibromyal",
                "code": "P97",
                "type": "DEFINITION",
                "source": "NCI",
            },
            {
                "definition": "A condition lasting for more than 6 months in which a "
                "person feels tired most of the time and may have "
                "trouble concentrating and carrying out daily "
                "activities. Other symptoms include sore throat, fever, "
                "muscle weakness, headache, and joint pain.",
                "code": "P325",
                "type": "ALT_DEFINITION",
                "source": "NCI-GLOSS",
            },
        ],
        "properties": [
            {"code": "P106", "type": "Semantic_Type", "value": "Disease or Syndrome"},
            {"code": "P207", "type": "UMLS_CUI", "value": "C0015674"},
        ],
        "parents": [{"code": "C3131", "name": "Immunodeficiency Syndrome"}],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncim/C0015672?include=summary%2Cparents%2Cchildren": {
        "code": "C0015672",
        "name": "Fatigue",
        "terminology": "ncim",
        "version": "202608",
        "active": True,
        "synonyms": [
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "HPO",
                "code": "HP:0012378",
                "qualifiers": [
                    {"type": "DATE_CREATED", "value": "2013-10-15T08:52:04Z"},
                    {"type": "HPO_COMMENT", "value": "Fatigue is distinct from muscle weakness."},
                ],
            },
            {
                "name": "Fatigue",
                "termType": "SY",
                "type": "Preferred_Name",
                "source": "HPO",
                "code": "HP:0012378",
                "qualifiers": [{"type": "SYN_QUALIFIER", "value": "layperson term"}],
            },
            {
                "name": "Tired",
                "termType": "SY",
                "type": "Synonym",
                "source": "HPO",
                "code": "HP:0012378",
                "qualifiers": [{"type": "SYN_QUALIFIER", "value": "layperson term"}],
            },
            {
                "name": "Fatigue NOS",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.83",
            },
            {
                "name": "Lack of energy",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.83",
            },
            {
                "name": "Tiredness",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.83",
            },
            {
                "name": "Fatigue",
                "termType": "CN",
                "type": "Preferred_Name",
                "source": "LNC",
                "code": "MTHU013358",
            },
            {
                "name": "Fatigue",
                "termType": "LA",
                "type": "Preferred_Name",
                "source": "LNC",
                "code": "LA7542-9",
            },
            {
                "name": "Lack of energy",
                "termType": "CN",
                "type": "Synonym",
                "source": "LNC",
                "code": "MTHU068534",
            },
            {
                "name": "Fatigue",
                "termType": "LLT",
                "type": "Preferred_Name",
                "source": "MDR",
                "code": "10016256",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "MDR",
                "code": "10016256",
            },
            {
                "name": "Energy decreased",
                "termType": "LLT",
                "type": "Synonym",
                "source": "MDR",
                "code": "10057841",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "MEDLINEPLUS",
                "code": "5324",
                "qualifiers": [
                    {"type": "DATE_CREATED", "value": "03/08/2010"},
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Spanish https://medlineplus.gov/spanish/fatigue.html",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Japanese "
                        "https://medlineplus.gov/languages/fatigue.html#Japanese",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Ukrainian "
                        "https://medlineplus.gov/languages/fatigue.html#Ukrainian",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "French https://medlineplus.gov/languages/fatigue.html#French",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Hindi https://medlineplus.gov/languages/fatigue.html#Hindi",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Korean https://medlineplus.gov/languages/fatigue.html#Korean",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Somali https://medlineplus.gov/languages/fatigue.html#Somali",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Russian https://medlineplus.gov/languages/fatigue.html#Russian",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Spanish https://medlineplus.gov/languages/fatigue.html#Spanish",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Arabic https://medlineplus.gov/languages/fatigue.html#Arabic",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Polish https://medlineplus.gov/languages/fatigue.html#Polish",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Vietnamese "
                        "https://medlineplus.gov/languages/fatigue.html#Vietnamese",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Chinese, Simplified (Mandarin dialect) "
                        "https://medlineplus.gov/languages/fatigue.html#Chinese, "
                        "Simplified (Mandarin dialect)",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Haitian Creole "
                        "https://medlineplus.gov/languages/fatigue.html#Haitian "
                        "Creole",
                    },
                    {
                        "type": "SOS",
                        "value": "Are you tired? Find out about some of the "
                        "common and uncommon causes of fatigue and how "
                        "to help yourself. "
                        "https://medlineplus.gov/fatigue.html",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Portuguese "
                        "https://medlineplus.gov/languages/fatigue.html#Portuguese",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Tagalog https://medlineplus.gov/languages/fatigue.html#Tagalog",
                    },
                ],
            },
            {
                "name": "Tiredness",
                "termType": "SY",
                "type": "Synonym",
                "source": "MEDLINEPLUS",
                "code": "5324",
            },
            {
                "name": "Tiredness",
                "termType": "ET",
                "type": "Synonym",
                "source": "MEDLINEPLUS",
                "code": "5324",
            },
            {
                "name": "Fatigue",
                "termType": "MH",
                "type": "Preferred_Name",
                "source": "MSH",
                "code": "D005221",
                "qualifiers": [
                    {"type": "DX", "value": "19660101"},
                    {
                        "type": "AQL",
                        "value": "BL CF CI CL CN CO DG DH DI DT EC EH EM EN EP ET "
                        "GE HI IM ME MI MO NU PA PC PP PS PX RH RT SU TH "
                        "UR VE VI",
                    },
                    {
                        "type": "AN",
                        "value": "do not use for fatigue of isolated muscle "
                        "fibers in physiol exper ( = MUSCLE FATIGUE)",
                    },
                    {"type": "DC", "value": "1"},
                    {"type": "FX", "value": "D001247"},
                    {"type": "MMR", "value": "19991103"},
                    {"type": "MN", "value": "C23.888.369"},
                    {"type": "TERMUI", "value": "T015996"},
                    {"type": "TH", "value": "POPLINE (1978)"},
                ],
            },
            {
                "name": "Tiredness",
                "termType": "ET",
                "type": "Synonym",
                "source": "MTHICD9",
                "code": "780.79",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "NCI",
                "code": "C3036",
            },
            {
                "name": "Lack of Energy",
                "termType": "SY",
                "type": "Synonym",
                "source": "NCI",
                "code": "C3036",
            },
            {
                "name": "Fatigue",
                "termType": "PTCS",
                "type": "Preferred_Name",
                "source": "OMIM",
                "code": "MTHU010062",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "SNOMEDCT_US",
                "code": "84229001",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Fatigue (finding)",
                "termType": "FN",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "84229001",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000003001"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Lack of energy",
                "termType": "PT",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "248274002",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "ACC-AHA",
                "code": "VAR",
            },
            {
                "name": "Fatigue (lassitude)",
                "termType": "PT",
                "type": "Synonym",
                "source": "ACC-AHA",
                "code": "C3036",
            },
            {
                "name": "decreased energy",
                "termType": "NP",
                "type": "Synonym",
                "source": "AOD",
                "code": "0000021621",
            },
            {
                "name": "fatigue",
                "termType": "DE",
                "type": "Synonym",
                "source": "AOD",
                "code": "0000001768",
                "qualifiers": [{"type": "HN", "value": "ETOH descriptor 2000."}],
            },
        ],
        "definitions": [
            {
                "definition": "<h3>What is fatigue?</h3> <p>Fatigue is a feeling of "
                "weariness, tiredness, or lack of energy. It can "
                "interfere with your usual daily activities. Fatigue can "
                "be a normal response to physical activity, emotional <a "
                'href="https://medlineplus.gov/stress.html">stress</a>, '
                "boredom, or lack of sleep. But sometimes it can be a "
                "sign of a mental or physical condition. If you have "
                "been feeling tired for weeks, contact your health care "
                "provider. They can help you find out what's causing "
                "your fatigue and recommend ways to relieve it.</p>",
                "type": "DEFINITION",
                "source": "MEDLINEPLUS",
            },
            {
                "definition": "A condition marked by extreme tiredness and inability "
                "to function due lack of energy. Fatigue may be acute or "
                "chronic.",
                "type": "DEFINITION",
                "source": "NCI-GLOSS",
            },
            {
                "definition": "A disorder characterized by a state of generalized "
                "weakness with a pronounced inability to summon "
                "sufficient energy to accomplish daily activities.",
                "type": "DEFINITION",
                "source": "CTCAE",
            },
        ],
        "properties": [{"type": "Semantic_Type", "value": "Sign or Symptom"}],
        "children": [
            {
                "code": "C1332836",
                "name": "Cancer Fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "NCI",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C1332836",
                "name": "Cancer Fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "SNOMEDCT_US",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C0015674",
                "name": "Chronic Fatigue Syndrome",
                "terminology": "ncim",
                "version": "202608",
                "source": "SNOMEDCT_US",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C0518656",
                "name": "Chronic fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "HPO",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C0518656",
                "name": "Chronic fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "MDR",
                "leaf": False,
            },
            {
                "code": "CL1765168",
                "name": "Cognitive fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "HPO",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
        ],
        "parents": [
            {
                "code": "C0004093",
                "name": "Asthenia",
                "terminology": "ncim",
                "version": "202608",
                "source": "MDR",
                "leaf": False,
            },
            {
                "code": "C0852192",
                "name": "Asthenic conditions",
                "terminology": "ncim",
                "version": "202608",
                "source": "MDR",
                "leaf": False,
            },
            {
                "code": "C1854373",
                "name": "Behavioral/psychiatric manifestations",
                "terminology": "ncim",
                "version": "202608",
                "source": "OMIM",
                "leaf": False,
            },
            {
                "code": "C0178520",
                "name": "body physical activity",
                "terminology": "ncim",
                "version": "202608",
                "source": "CSP",
                "leaf": False,
            },
            {
                "code": "C2242489",
                "name": "Cancer-Related Condition",
                "terminology": "ncim",
                "version": "202608",
                "source": "PDQ",
                "leaf": False,
            },
            {
                "code": "C3714787",
                "name": "Central Nervous System",
                "terminology": "ncim",
                "version": "202608",
                "source": "OMIM",
                "leaf": False,
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/C3036?include=parents%2Cchildren%2Croles%2CinverseRoles%2Cassociations%2CinverseAssociations": {
        "code": "C3036",
        "name": "Fatigue",
        "terminology": "ncit",
        "version": "26.09d",
        "conceptStatus": "DEFAULT",
        "leaf": False,
        "active": True,
        "children": [
            {"code": "C5062", "name": "Cancer Fatigue", "leaf": True},
            {"code": "C180621", "name": "Exertional Fatigue", "leaf": True},
            {"code": "C181246", "name": "Exhaustion", "leaf": True},
            {"code": "C50556", "name": "Extreme Exhaustion", "leaf": True},
            {"code": "C34846", "name": "Nervous Debility", "leaf": True},
        ],
        "parents": [{"code": "C3858", "name": "Mental and Behavioral Signs and Symptoms"}],
        "associations": [
            {
                "code": "A8",
                "type": "Concept_In_Subset",
                "relatedCode": "C191200",
                "relatedName": "ACC/AHA Cardiovascular and Noncardiovascular "
                "Complications of COVID-19 Terminology",
            },
            {
                "code": "A8",
                "type": "Concept_In_Subset",
                "relatedCode": "C191670",
                "relatedName": "ACC/AHA COVID-19 Appendix Variables",
            },
            {
                "code": "A8",
                "type": "Concept_In_Subset",
                "relatedCode": "C167409",
                "relatedName": "ACC/AHA Pediatric and Congenital Cardiology EHR Terminology",
            },
            {
                "code": "A8",
                "type": "Concept_In_Subset",
                "relatedCode": "C191385",
                "relatedName": "Appendix 6: Symptoms and Signs Terminology",
            },
            {
                "code": "A8",
                "type": "Concept_In_Subset",
                "relatedCode": "C119016",
                "relatedName": "CDISC SDTM Cardiovascular Findings About Results Terminology",
            },
            {
                "code": "A8",
                "type": "Concept_In_Subset",
                "relatedCode": "C66830",
                "relatedName": "CDISC SDTM Terminology",
            },
        ],
        "inverseAssociations": [
            {
                "code": "A39",
                "type": "Has_PCDC_HL_Authorized_Value",
                "relatedCode": "C41331",
                "relatedName": "Adverse Event",
            },
            {
                "code": "A39",
                "type": "Has_PCDC_HL_Authorized_Value",
                "relatedCode": "C4808",
                "relatedName": "Late Adverse Effect",
            },
            {
                "code": "A37",
                "type": "Has_SeroNet_Authorized_Value",
                "relatedCode": "C189195",
                "relatedName": "Post-COVID-19 Symptom",
            },
        ],
        "inverseRoles": [
            {
                "code": "R115",
                "type": "Disease_May_Have_Finding",
                "relatedCode": "C3173",
                "relatedName": "Accelerated Phase Chronic Myeloid Leukemia, BCR-ABL1 Positive",
            },
            {
                "code": "R115",
                "type": "Disease_May_Have_Finding",
                "relatedCode": "C9020",
                "relatedName": "Acute Myelomonocytic Leukemia with Abnormal Eosinophils",
            },
            {
                "code": "R115",
                "type": "Disease_May_Have_Finding",
                "relatedCode": "C42779",
                "relatedName": "Acute Myelomonocytic Leukemia without Abnormal Eosinophils",
            },
            {
                "code": "R115",
                "type": "Disease_May_Have_Finding",
                "relatedCode": "C7463",
                "relatedName": "Acute Myelomonocytic Leukemia",
            },
            {
                "code": "R115",
                "type": "Disease_May_Have_Finding",
                "relatedCode": "C4344",
                "relatedName": "Acute Panmyelosis with Myelofibrosis",
            },
            {
                "code": "R115",
                "type": "Disease_May_Have_Finding",
                "relatedCode": "C7962",
                "relatedName": "Adult Acute Myelomonocytic Leukemia",
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncim/C0015672?include=parents%2Cchildren%2Croles%2CinverseRoles%2Cassociations%2CinverseAssociations": {
        "code": "C0015672",
        "name": "Fatigue",
        "terminology": "ncim",
        "version": "202608",
        "active": True,
        "children": [
            {
                "code": "C1332836",
                "name": "Cancer Fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "NCI",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C1332836",
                "name": "Cancer Fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "SNOMEDCT_US",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C0015674",
                "name": "Chronic Fatigue Syndrome",
                "terminology": "ncim",
                "version": "202608",
                "source": "SNOMEDCT_US",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C0518656",
                "name": "Chronic fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "HPO",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
            {
                "code": "C0518656",
                "name": "Chronic fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "MDR",
                "leaf": False,
            },
            {
                "code": "CL1765168",
                "name": "Cognitive fatigue",
                "terminology": "ncim",
                "version": "202608",
                "source": "HPO",
                "leaf": False,
                "qualifiers": [{"type": "RELA", "value": "inverse_isa"}],
            },
        ],
        "parents": [
            {
                "code": "C0004093",
                "name": "Asthenia",
                "terminology": "ncim",
                "version": "202608",
                "source": "MDR",
                "leaf": False,
            },
            {
                "code": "C0852192",
                "name": "Asthenic conditions",
                "terminology": "ncim",
                "version": "202608",
                "source": "MDR",
                "leaf": False,
            },
            {
                "code": "C1854373",
                "name": "Behavioral/psychiatric manifestations",
                "terminology": "ncim",
                "version": "202608",
                "source": "OMIM",
                "leaf": False,
            },
            {
                "code": "C0178520",
                "name": "body physical activity",
                "terminology": "ncim",
                "version": "202608",
                "source": "CSP",
                "leaf": False,
            },
            {
                "code": "C2242489",
                "name": "Cancer-Related Condition",
                "terminology": "ncim",
                "version": "202608",
                "source": "PDQ",
                "leaf": False,
            },
            {
                "code": "C3714787",
                "name": "Central Nervous System",
                "terminology": "ncim",
                "version": "202608",
                "source": "OMIM",
                "leaf": False,
            },
        ],
        "associations": [
            {
                "type": "RO",
                "relatedCode": "CL1904895",
                "relatedName": "ACC-AHA Cardiovascular and Noncardiovascular "
                "Complications of COVID-19 Terminology",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Concept_In_Subset"}],
            },
            {
                "type": "RO",
                "relatedCode": "CL1905253",
                "relatedName": "ACC-AHA COVID-19 Appendix Variables",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Concept_In_Subset"}],
            },
            {
                "type": "RO",
                "relatedCode": "CL972588",
                "relatedName": "ACC-AHA Pediatric and Congenital Cardiology EHR Terminology",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Concept_In_Subset"}],
            },
            {
                "type": "RO",
                "relatedCode": "C0681636",
                "relatedName": "accident factor",
                "source": "AOD",
            },
            {
                "type": "RO",
                "relatedCode": "C0268603",
                "relatedName": "Acetyl-CoA: carboxylase deficiency",
                "source": "OMIM",
                "qualifiers": [{"type": "RELA", "value": "manifestation_of"}],
            },
            {
                "type": "RO",
                "relatedCode": "C1332156",
                "relatedName": "Acute Myelomonocytic Leukemia with Abnormal Eosinophils",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "May_Be_Finding_Of_Disease"}],
            },
        ],
        "inverseAssociations": [
            {
                "type": "RO",
                "relatedCode": "CL1904895",
                "relatedName": "ACC-AHA Cardiovascular and Noncardiovascular "
                "Complications of COVID-19 Terminology",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Subset_Includes_Concept"}],
            },
            {
                "type": "RO",
                "relatedCode": "CL1905253",
                "relatedName": "ACC-AHA COVID-19 Appendix Variables",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Subset_Includes_Concept"}],
            },
            {
                "type": "RO",
                "relatedCode": "CL972588",
                "relatedName": "ACC-AHA Pediatric and Congenital Cardiology EHR Terminology",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Subset_Includes_Concept"}],
            },
            {
                "type": "RO",
                "relatedCode": "C0681636",
                "relatedName": "accident factor",
                "source": "AOD",
            },
            {
                "type": "RO",
                "relatedCode": "C0268603",
                "relatedName": "Acetyl-CoA: carboxylase deficiency",
                "source": "OMIM",
                "qualifiers": [{"type": "RELA", "value": "has_manifestation"}],
            },
            {
                "type": "RO",
                "relatedCode": "C1332156",
                "relatedName": "Acute Myelomonocytic Leukemia with Abnormal Eosinophils",
                "source": "NCI",
                "qualifiers": [{"type": "RELA", "value": "Disease_May_Have_Finding"}],
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/C3037?include=synonyms%2Cmaps%2Cproperties": {
        "code": "C3037",
        "name": "Chronic Fatigue Syndrome",
        "terminology": "ncit",
        "version": "26.09d",
        "conceptStatus": "DEFAULT",
        "leaf": True,
        "active": True,
        "synonyms": [
            {
                "name": "Myalgic encephalomyelitis/chronic fatigue syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "ACC/AHA",
                "code": "AV",
                "subSource": "SARS2",
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "GDC",
            },
            {
                "name": "chronic fatigue syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "NCI-GLOSS",
                "code": "CDR0000468799",
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "PT",
                "type": "FULL_SYN",
                "typeCode": "P90",
                "source": "NCI",
            },
        ],
        "properties": [
            {"code": "P106", "type": "Semantic_Type", "value": "Disease or Syndrome"},
            {"code": "P207", "type": "UMLS_CUI", "value": "C0015674"},
        ],
        "maps": [
            {
                "type": "Has Synonym",
                "targetName": "Chronic Fatigue Syndrome",
                "targetTermType": "PT",
                "targetCode": "comorbidities",
                "targetTerminology": "GDC",
            },
            {
                "type": "Has Synonym",
                "targetName": "Chronic Fatigue Syndrome",
                "targetTermType": "PT",
                "targetCode": "risk_factors",
                "targetTerminology": "GDC",
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncim/C0015674?include=synonyms%2Cmaps": {
        "code": "C0015674",
        "name": "Chronic Fatigue Syndrome",
        "terminology": "ncim",
        "version": "202608",
        "active": True,
        "synonyms": [
            {
                "name": "Chronic fatigue syndrome",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "G93.32",
            },
            {
                "name": "Chronic fatigue, unspecified",
                "termType": "PT",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.82",
                "qualifiers": [
                    {
                        "type": "EXCLUDES1",
                        "value": "chronic fatigue syndrome (G93.32); myalgic "
                        "encephalomyelitis (G93.32); other post "
                        "infection and related fatigue syndromes "
                        "(G93.39); postviral fatigue syndrome (G93.31)",
                    },
                    {"type": "ORDER_NO", "value": "31113"},
                ],
            },
            {
                "name": "Chronic fatigue, unspecified",
                "termType": "AB",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.82",
            },
            {
                "name": "Postviral fatigue syndrome",
                "termType": "PT",
                "type": "Synonym",
                "source": "ICD10",
                "code": "G93.3",
            },
            {
                "name": "Chronic fatigue syndrome",
                "termType": "LLT",
                "type": "Synonym",
                "source": "MDR",
                "code": "10008874",
            },
            {
                "name": "Chronic fatigue syndrome",
                "termType": "PT",
                "type": "Synonym",
                "source": "MDR",
                "code": "10008874",
            },
            {
                "name": "ME",
                "termType": "OL",
                "type": "Synonym",
                "source": "MDR",
                "code": "10026978",
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "ET",
                "type": "Preferred_Name",
                "source": "MEDLINEPLUS",
                "code": "89",
            },
            {
                "name": "CFS",
                "termType": "ET",
                "type": "Synonym",
                "source": "MEDLINEPLUS",
                "code": "89",
            },
            {
                "name": "CFS",
                "termType": "SY",
                "type": "Synonym",
                "source": "MEDLINEPLUS",
                "code": "89",
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "ET",
                "type": "Preferred_Name",
                "source": "MSH",
                "code": "D015673",
                "qualifiers": [
                    {"type": "TH", "value": "NLM (1990)"},
                    {"type": "TERMUI", "value": "T046398"},
                ],
            },
            {
                "name": "CFIDS",
                "termType": "DEV",
                "type": "Synonym",
                "source": "MSH",
                "code": "D015673",
            },
            {
                "name": "Chronic Fatigue and Immune Dysfunction Syndrome",
                "termType": "ET",
                "type": "Synonym",
                "source": "MSH",
                "code": "D015673",
                "qualifiers": [
                    {"type": "TERMUI", "value": "T046404"},
                    {"type": "TH", "value": "NLM (1997)"},
                ],
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "NCI",
                "code": "C3037",
            },
            {
                "name": "Myalgic Encephalomyelitis",
                "termType": "SY",
                "type": "Synonym",
                "source": "NCI",
                "code": "C3037",
            },
            {
                "name": "Benign myalgic encephalomyelitis",
                "termType": "SY",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "52702003",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "CFS - Chronic fatigue syndrome",
                "termType": "SY",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "52702003",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000017005"},
                ],
            },
            {
                "name": "Chronic fatigue syndrome",
                "termType": "PT",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "52702003",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Myalgic encephalomyelitis/chronic fatigue syndrome",
                "termType": "PT",
                "type": "Synonym",
                "source": "ACC-AHA",
                "code": "AV",
            },
            {
                "name": "chronic fatigue and immune dysfunction syndrome",
                "termType": "NP",
                "type": "Synonym",
                "source": "AOD",
                "code": "0000023160",
            },
            {
                "name": "chronic fatigue syndrome",
                "termType": "DE",
                "type": "Synonym",
                "source": "AOD",
                "code": "0000004797",
                "qualifiers": [
                    {"type": "HN", "value": "Introduced 2000."},
                    {"type": "SOS", "value": "Etiology is suspected to be viral or immunologic"},
                ],
            },
            {
                "name": "CHRONIC FATIGUE SYNDROME",
                "termType": "PT",
                "type": "Synonym",
                "source": "COSTAR",
                "code": "U000137",
            },
        ],
        "maps": [
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10_2016_Mappings",
                "source": "snomedct_us",
                "sourceName": "Postviral fatigue syndrome",
                "sourceCode": "51771007",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10",
                "targetName": "Postviral fatigue syndrome",
                "targetTermType": "PT",
                "targetCode": "G93.3",
                "targetTerminology": "ICD10",
                "targetTerminologyVersion": "2016",
                "sortKey": "1101840",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Postviral fatigue syndrome",
                "sourceCode": "51771007",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10cm",
                "targetName": "Postviral fatigue syndrome",
                "targetTermType": "PT",
                "targetCode": "G93.31",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1201085",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Chronic fatigue syndrome",
                "sourceCode": "52702003",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10cm",
                "targetName": "Chronic fatigue, unspecified",
                "targetTermType": "PT",
                "targetCode": "R53.82",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1049814",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10_2016_Mappings",
                "source": "snomedct_us",
                "sourceName": "Chronic fatigue syndrome",
                "sourceCode": "52702003",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10",
                "targetName": "Postviral fatigue syndrome",
                "targetTermType": "PT",
                "targetCode": "G93.3",
                "targetTerminology": "ICD10",
                "targetTerminologyVersion": "2016",
                "sortKey": "1027217",
            },
        ],
    },
    "https://api-evsrest.nci.nih.gov/api/v1/concept/ncim/C0015672?include=synonyms%2Cmaps%2Cproperties": {
        "code": "C0015672",
        "name": "Fatigue",
        "terminology": "ncim",
        "version": "202608",
        "active": True,
        "synonyms": [
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "HPO",
                "code": "HP:0012378",
                "qualifiers": [
                    {"type": "DATE_CREATED", "value": "2013-10-15T08:52:04Z"},
                    {"type": "HPO_COMMENT", "value": "Fatigue is distinct from muscle weakness."},
                ],
            },
            {
                "name": "Fatigue",
                "termType": "SY",
                "type": "Preferred_Name",
                "source": "HPO",
                "code": "HP:0012378",
                "qualifiers": [{"type": "SYN_QUALIFIER", "value": "layperson term"}],
            },
            {
                "name": "Tired",
                "termType": "SY",
                "type": "Synonym",
                "source": "HPO",
                "code": "HP:0012378",
                "qualifiers": [{"type": "SYN_QUALIFIER", "value": "layperson term"}],
            },
            {
                "name": "Fatigue NOS",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.83",
            },
            {
                "name": "Lack of energy",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.83",
            },
            {
                "name": "Tiredness",
                "termType": "ET",
                "type": "Synonym",
                "source": "ICD10CM",
                "code": "R53.83",
            },
            {
                "name": "Fatigue",
                "termType": "CN",
                "type": "Preferred_Name",
                "source": "LNC",
                "code": "MTHU013358",
            },
            {
                "name": "Fatigue",
                "termType": "LA",
                "type": "Preferred_Name",
                "source": "LNC",
                "code": "LA7542-9",
            },
            {
                "name": "Lack of energy",
                "termType": "CN",
                "type": "Synonym",
                "source": "LNC",
                "code": "MTHU068534",
            },
            {
                "name": "Fatigue",
                "termType": "LLT",
                "type": "Preferred_Name",
                "source": "MDR",
                "code": "10016256",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "MDR",
                "code": "10016256",
            },
            {
                "name": "Energy decreased",
                "termType": "LLT",
                "type": "Synonym",
                "source": "MDR",
                "code": "10057841",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "MEDLINEPLUS",
                "code": "5324",
                "qualifiers": [
                    {"type": "DATE_CREATED", "value": "03/08/2010"},
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Spanish https://medlineplus.gov/spanish/fatigue.html",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Japanese "
                        "https://medlineplus.gov/languages/fatigue.html#Japanese",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Ukrainian "
                        "https://medlineplus.gov/languages/fatigue.html#Ukrainian",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "French https://medlineplus.gov/languages/fatigue.html#French",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Hindi https://medlineplus.gov/languages/fatigue.html#Hindi",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Korean https://medlineplus.gov/languages/fatigue.html#Korean",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Somali https://medlineplus.gov/languages/fatigue.html#Somali",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Russian https://medlineplus.gov/languages/fatigue.html#Russian",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Spanish https://medlineplus.gov/languages/fatigue.html#Spanish",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Arabic https://medlineplus.gov/languages/fatigue.html#Arabic",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Polish https://medlineplus.gov/languages/fatigue.html#Polish",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Vietnamese "
                        "https://medlineplus.gov/languages/fatigue.html#Vietnamese",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Chinese, Simplified (Mandarin dialect) "
                        "https://medlineplus.gov/languages/fatigue.html#Chinese, "
                        "Simplified (Mandarin dialect)",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Haitian Creole "
                        "https://medlineplus.gov/languages/fatigue.html#Haitian "
                        "Creole",
                    },
                    {
                        "type": "SOS",
                        "value": "Are you tired? Find out about some of the "
                        "common and uncommon causes of fatigue and how "
                        "to help yourself. "
                        "https://medlineplus.gov/fatigue.html",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Portuguese "
                        "https://medlineplus.gov/languages/fatigue.html#Portuguese",
                    },
                    {
                        "type": "MP_OTHER_LANGUAGE_URL",
                        "value": "Tagalog https://medlineplus.gov/languages/fatigue.html#Tagalog",
                    },
                ],
            },
            {
                "name": "Tiredness",
                "termType": "SY",
                "type": "Synonym",
                "source": "MEDLINEPLUS",
                "code": "5324",
            },
            {
                "name": "Tiredness",
                "termType": "ET",
                "type": "Synonym",
                "source": "MEDLINEPLUS",
                "code": "5324",
            },
            {
                "name": "Fatigue",
                "termType": "MH",
                "type": "Preferred_Name",
                "source": "MSH",
                "code": "D005221",
                "qualifiers": [
                    {"type": "DX", "value": "19660101"},
                    {
                        "type": "AQL",
                        "value": "BL CF CI CL CN CO DG DH DI DT EC EH EM EN EP ET "
                        "GE HI IM ME MI MO NU PA PC PP PS PX RH RT SU TH "
                        "UR VE VI",
                    },
                    {
                        "type": "AN",
                        "value": "do not use for fatigue of isolated muscle "
                        "fibers in physiol exper ( = MUSCLE FATIGUE)",
                    },
                    {"type": "DC", "value": "1"},
                    {"type": "FX", "value": "D001247"},
                    {"type": "MMR", "value": "19991103"},
                    {"type": "MN", "value": "C23.888.369"},
                    {"type": "TERMUI", "value": "T015996"},
                    {"type": "TH", "value": "POPLINE (1978)"},
                ],
            },
            {
                "name": "Tiredness",
                "termType": "ET",
                "type": "Synonym",
                "source": "MTHICD9",
                "code": "780.79",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "NCI",
                "code": "C3036",
            },
            {
                "name": "Lack of Energy",
                "termType": "SY",
                "type": "Synonym",
                "source": "NCI",
                "code": "C3036",
            },
            {
                "name": "Fatigue",
                "termType": "PTCS",
                "type": "Preferred_Name",
                "source": "OMIM",
                "code": "MTHU010062",
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "SNOMEDCT_US",
                "code": "84229001",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Fatigue (finding)",
                "termType": "FN",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "84229001",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000003001"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Lack of energy",
                "termType": "PT",
                "type": "Synonym",
                "source": "SNOMEDCT_US",
                "code": "248274002",
                "qualifiers": [
                    {"type": "TYPE_ID", "value": "900000000000013009"},
                    {"type": "CASE_SIGNIFICANCE_ID", "value": "900000000000448009"},
                ],
            },
            {
                "name": "Fatigue",
                "termType": "PT",
                "type": "Preferred_Name",
                "source": "ACC-AHA",
                "code": "VAR",
            },
            {
                "name": "Fatigue (lassitude)",
                "termType": "PT",
                "type": "Synonym",
                "source": "ACC-AHA",
                "code": "C3036",
            },
            {
                "name": "decreased energy",
                "termType": "NP",
                "type": "Synonym",
                "source": "AOD",
                "code": "0000021621",
            },
            {
                "name": "fatigue",
                "termType": "DE",
                "type": "Synonym",
                "source": "AOD",
                "code": "0000001768",
                "qualifiers": [{"type": "HN", "value": "ETOH descriptor 2000."}],
            },
        ],
        "properties": [{"type": "Semantic_Type", "value": "Sign or Symptom"}],
        "maps": [
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Lack of energy",
                "sourceCode": "248274002",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "IFA 214264003 &#x7C; Lethargy &#x7C; AND IFA 445518008 &#x7C; Age at "
                "onset of clinical finding (observable entity) &#x7C; >= 65.0 years",
                "target": "icd10cm",
                "targetName": "Age-related physical debility",
                "targetTermType": "PT",
                "targetCode": "R54",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1143124",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10_2016_Mappings",
                "source": "snomedct_us",
                "sourceName": "Lack of energy",
                "sourceCode": "248274002",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10",
                "targetName": "Malaise and fatigue",
                "targetTermType": "PT",
                "targetCode": "R53",
                "targetTerminology": "ICD10",
                "targetTerminologyVersion": "2016",
                "sortKey": "1073155",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Lack of energy",
                "sourceCode": "248274002",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "2",
                "group": "1",
                "rule": "IFA 214264003 &#x7C; Lethargy &#x7C;",
                "target": "icd10cm",
                "targetName": "Other fatigue",
                "targetTermType": "PT",
                "targetCode": "R53.83",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1143125",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Lack of energy",
                "sourceCode": "248274002",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "3",
                "group": "1",
                "rule": "OTHERWISE TRUE",
                "target": "icd10cm",
                "targetName": "Other fatigue",
                "targetTermType": "PT",
                "targetCode": "R53.83",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1143126",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Tired all the time",
                "sourceCode": "267032009",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10cm",
                "targetName": "Chronic fatigue, unspecified",
                "targetTermType": "PT",
                "targetCode": "R53.82",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1242582",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10_2016_Mappings",
                "source": "snomedct_us",
                "sourceName": "Tired all the time",
                "sourceCode": "267032009",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10",
                "targetName": "Malaise and fatigue",
                "targetTermType": "PT",
                "targetCode": "R53",
                "targetTerminology": "ICD10",
                "targetTerminologyVersion": "2016",
                "sortKey": "1121564",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10CM_2026_Mappings",
                "source": "snomedct_us",
                "sourceName": "Fatigue",
                "sourceCode": "84229001",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "IFA 445518008 &#x7C; Age at onset of clinical finding (observable "
                "entity) &#x7C; >= 65.0 years",
                "target": "icd10cm",
                "targetName": "Age-related physical debility",
                "targetTermType": "PT",
                "targetCode": "R54",
                "targetTerminology": "ICD10CM",
                "targetTerminologyVersion": "2026",
                "sortKey": "1096316",
            },
            {
                "mapsetCode": "SNOMEDCT_US_2026_03_01_to_ICD10_2016_Mappings",
                "source": "snomedct_us",
                "sourceName": "Fatigue",
                "sourceCode": "84229001",
                "sourceTerminology": "SNOMEDCT_US",
                "sourceTerminologyVersion": "2026_03_01",
                "type": "RO",
                "rank": "1",
                "group": "1",
                "rule": "TRUE",
                "target": "icd10",
                "targetName": "Malaise and fatigue",
                "targetTermType": "PT",
                "targetCode": "R53",
                "targetTerminology": "ICD10",
                "targetTerminologyVersion": "2016",
                "sortKey": "1050190",
            },
        ],
    },
}
