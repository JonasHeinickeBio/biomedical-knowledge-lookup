"""Real NLM Clinical Table Search Service responses recorded on 2026-10-08, keyed by the request that
produced them; replayed by the unit tests of the adapter. No network."""

from typing import Any
from urllib.parse import urlencode


def request_key(url: str, params: dict[str, Any] | None) -> str:
    """Stable key for a (url, params) pair, matching how the fixtures were recorded."""
    return url + "?" + urlencode(sorted((params or {}).items()))


RECORDED: dict[str, Any] = {
    "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search?cf=key_id&df=primary_name&ef=consumer_name%2Cicd10cm_codes%2Cicd10cm%2Cterm_icd9_code%2Cterm_icd9_text%2Csynonyms%2Cinfo_link_data&maxList=3&terms=fatigue": [
        2,
        ["2329", "12927"],
        {
            "consumer_name": ["Fatigue", "Chronic fatigue syndrome"],
            "icd10cm_codes": ["R53.83", "R53.82"],
            "icd10cm": [
                [{"code": "R53.83", "name": "Other fatigue"}],
                [{"code": "R53.82", "name": "Chronic fatigue, unspecified"}],
            ],
            "term_icd9_code": ["780.79", "780.71"],
            "term_icd9_text": ["Other malaise and fatigue", "Chronic fatigue syndrome"],
            "synonyms": [["loss of energy", "malaise", "tiredness"], []],
            "info_link_data": [
                [["http://www.nlm.nih.gov/medlineplus/fatigue.html", "Fatigue"]],
                [
                    [
                        "http://www.nlm.nih.gov/medlineplus/chronicfatiguesyndrome.html",
                        "Chronic Fatigue Syndrome",
                    ]
                ],
            ],
        },
        [["Fatigue"], ["Chronic fatigue syndrome"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/hpo/v3/search?cf=id&df=name&ef=definition%2Csynonym%2Cis_a%2Cxref%2Calt_id%2Cis_obsolete%2Ccomment&maxList=3&terms=fatigue": [
        8,
        ["HP:0012378", "HP:0012431", "HP:0012432"],
        {
            "definition": [
                "A subjective feeling of tiredness characterized by a lack of energy "
                "and motivation",
                "Intermittent and recurrent bouts of a subjective feeling of tiredness "
                "characterized by a lack of energy and motivation",
                "Subjective feeling of tiredness characterized by a lack of energy and "
                "motivation that persists for six months or longer",
            ],
            "synonym": [
                [
                    {"term": "Fatigue", "relation": "EXACT", "type": "layperson"},
                    {"term": "Tired", "relation": "EXACT", "type": "layperson"},
                    {"term": "Tiredness", "relation": "EXACT", "type": "layperson"},
                ],
                None,
                [
                    {
                        "term": "Chronic extreme exhaustion",
                        "relation": "EXACT",
                        "type": "layperson",
                    },
                    {
                        "term": "Chronic fatigue",
                        "relation": "EXACT",
                        "type": "layperson",
                        "xref": ["https://orcid.org/0000-0002-6548-5200"],
                    },
                ],
            ],
            "is_a": [
                [{"id": "HP:0025142", "name": "Constitutional symptom"}],
                [{"id": "HP:0012378", "name": "Fatigue"}],
                [{"id": "HP:0012378", "name": "Fatigue"}],
            ],
            "xref": [None, None, None],
            "alt_id": [None, None, None],
            "is_obsolete": [None, None, None],
            "comment": [
                "Fatigue is distinct from muscle weakness.",
                None,
                "Note that chronic fatigue can be a symptom of chronic fatigue syndrome "
                "(CFS), which is characterized by profound fatigue that is not improved by "
                "bed rest and that may be worsened by physical or mental activity. "
                "Symptoms of CFS may include weakness, muscle pain, impaired memory, "
                "impaired mental concentration, and insomnia, which can result in reduced "
                "participation in daily activities.",
            ],
        },
        [["Fatigue"], ["Episodic fatigue"], ["Chronic fatigue"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?cf=code&df=name&maxList=3&sf=code%2Cname&terms=fatigue": [
        49,
        ["R53.83", "G93.31", "R53.82"],
        None,
        [["Other fatigue"], ["Postviral fatigue syndrome"], ["Chronic fatigue, unspecified"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search?cf=LOINC_NUM&df=text&ef=LONG_COMMON_NAME%2CSHORTNAME%2CCOMPONENT%2CPROPERTY%2CMETHOD_TYP%2CCONSUMER_NAME%2Cdatatype%2CisCopyrighted&maxList=3&terms=fatigue": [
        107,
        ["64101-9", "70735-6", "65953-2"],
        {
            "LONG_COMMON_NAME": [
                "Fatigue --resting",
                "Functional Assessment of Chronic Illness Therapy-Fatigue "
                "Questionnaire -13 items - version 4 (FACIT - fatigue 13)",
                "Loss of energy or fatigue [DI-PAD]",
            ],
            "SHORTNAME": ["Fatigue resting", "", "Loss energy fatigue DI-PAD"],
            "COMPONENT": [
                "Fatigue^resting",
                "Functional assessment of chronic illness therapy - fatigue "
                "questionnaire -13 items - version 4",
                "Loss of energy or fatigue",
            ],
            "PROPERTY": ["Find", "-", "Find"],
            "METHOD_TYP": ["", "FACIT", "DI-PAD CGP V 1.4"],
            "CONSUMER_NAME": ["", "", ""],
            "datatype": ["CNE", None, "CNE"],
            "isCopyrighted": [False, True, False],
        },
        [
            ["Fatigue resting"],
            [
                "Functional assessment of chronic illness therapy - fatigue questionnaire -13 items - "
                "version 4"
            ],
            ["Loss energy fatigue DI-PAD"],
        ],
    ],
    "https://clinicaltables.nlm.nih.gov/api/disease_names/v3/search?cf=ConceptID&df=DiseaseName&maxList=3&terms=fatigue": [
        8,
        ["C0015672", "C0518656", "C5539444"],
        None,
        [["Fatigue"], ["Chronic fatigue"], ["Cognitive fatigue"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search?cf=code&df=title&ef=definition%2Ctype%2Cchapter%2Csource%2CindexTerm%2CbrowserUrl&maxList=3&terms=fatigue": [
        7,
        ["MG22", "8E49", "NF01.3"],
        {
            "definition": [
                "A feeling of exhaustion, lethargy, or decreased energy, usually "
                "experienced as a weakening or depletion of one's physical or mental "
                "resource and characterised by a decreased capacity for work and "
                "reduced efficiency in responding to stimuli. Fatigue is normal "
                "following a period of exertion, mental or physical, but sometimes may "
                "occur in the absence of such exertion as a symptom of health "
                "conditions.",
                "",
                "",
            ],
            "type": ["stem", "stem", "stem"],
            "chapter": ["21", "08", "22"],
            "source": [
                "http://id.who.int/icd/entity/1109546957",
                "http://id.who.int/icd/entity/569175314",
                "http://id.who.int/icd/entity/791667961",
            ],
            "indexTerm": [
                "Fatigue; General physical deterioration; Lethargy; decline NOS; "
                "decreased energy; exhaustion; functional decline; general debilitation; "
                "general debility; general decline; lack of vitality; lethargic; "
                "prostration; slow decline; weak; weakness NOS; worn out",
                "Postviral fatigue syndrome; Akureyri disease; Benign myalgic "
                "encephalomyelitis; CFS - [chronic fatigue syndrome]; Iceland disease; "
                "Icelandic disease; ME - [myalgic encephalomyelitis]; ME/CFS – [myalgic "
                "encephalomyelitis/chronic fatigue syndrome]; PVFS - [postviral fatigue "
                "syndrome]; chronic fatigue syndrome; epidemic neuromyasthenia; myalgic "
                "encephalomyelitis; myalgic encephalomyelitis syndrome; myalgic "
                "encephalomyelitis/chronic fatigue syndrome; neuromyasthenia",
                "Heat fatigue, transient; heat fatigue NOS; transient effects of heat fatigue",
            ],
            "browserUrl": [
                "https://icd.who.int/browse/2026-01/mms/en#1109546957",
                "https://icd.who.int/browse/2026-01/mms/en#569175314",
                "https://icd.who.int/browse/2026-01/mms/en#791667961",
            ],
        },
        [["Fatigue"], ["Postviral fatigue syndrome"], ["Heat fatigue, transient"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?cf=code&df=name&maxList=100&sf=code&terms=G93.32": [
        1,
        ["G93.32"],
        None,
        [["Myalgic encephalomyelitis/chronic fatigue syndrome"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?cf=code&df=name&maxList=100&sf=code&terms=U09.9": [
        1,
        ["U09.9"],
        None,
        [["Post COVID-19 condition, unspecified"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search?cf=key_id&df=primary_name&ef=consumer_name%2Cicd10cm_codes%2Cicd10cm%2Cterm_icd9_code%2Cterm_icd9_text%2Csynonyms%2Cinfo_link_data&maxList=100&sf=key_id&terms=12927": [
        1,
        ["12927"],
        {
            "consumer_name": ["Chronic fatigue syndrome"],
            "icd10cm_codes": ["R53.82"],
            "icd10cm": [[{"code": "R53.82", "name": "Chronic fatigue, unspecified"}]],
            "term_icd9_code": ["780.71"],
            "term_icd9_text": ["Chronic fatigue syndrome"],
            "synonyms": [[]],
            "info_link_data": [
                [
                    [
                        "http://www.nlm.nih.gov/medlineplus/chronicfatiguesyndrome.html",
                        "Chronic Fatigue Syndrome",
                    ]
                ]
            ],
        },
        [["Chronic fatigue syndrome"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search?cf=key_id&df=primary_name&ef=consumer_name%2Cicd10cm_codes%2Cicd10cm%2Cterm_icd9_code%2Cterm_icd9_text%2Csynonyms%2Cinfo_link_data&maxList=100&sf=key_id&terms=2143": [
        1,
        ["2143"],
        {
            "consumer_name": ["Diabetes mellitus (DM)"],
            "icd10cm_codes": ["E11.9"],
            "icd10cm": [
                [{"code": "E11.9", "name": "Type 2 diabetes mellitus without complications"}]
            ],
            "term_icd9_code": ["250.00"],
            "term_icd9_text": [
                "type II diabetes mellitus [non-insulin dependent type] [NIDDM "
                "type] [adult-onset type] or unspecified type, not stated as "
                "uncontrolled, without mention of complication"
            ],
            "synonyms": [["DM"]],
            "info_link_data": [[["http://www.nlm.nih.gov/medlineplus/diabetes.html", "Diabetes"]]],
        },
        [["Diabetes mellitus"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search?cf=LOINC_NUM&df=text&ef=LONG_COMMON_NAME%2CSHORTNAME%2CCOMPONENT%2CPROPERTY%2CMETHOD_TYP%2CCONSUMER_NAME%2Cdatatype%2CisCopyrighted&maxList=100&sf=LOINC_NUM&terms=70735-6": [
        1,
        ["70735-6"],
        {
            "LONG_COMMON_NAME": [
                "Functional Assessment of Chronic Illness Therapy-Fatigue "
                "Questionnaire -13 items - version 4 (FACIT - fatigue 13)"
            ],
            "SHORTNAME": [""],
            "COMPONENT": [
                "Functional assessment of chronic illness therapy - fatigue "
                "questionnaire -13 items - version 4"
            ],
            "PROPERTY": ["-"],
            "METHOD_TYP": ["FACIT"],
            "CONSUMER_NAME": [""],
            "datatype": [None],
            "isCopyrighted": [True],
        },
        [
            [
                "Functional assessment of chronic illness therapy - fatigue questionnaire -13 items - "
                "version 4"
            ]
        ],
    ],
    "https://clinicaltables.nlm.nih.gov/api/hpo/v3/search?cf=id&df=name&ef=definition%2Csynonym%2Cis_a%2Cxref%2Calt_id%2Cis_obsolete%2Ccomment&maxList=100&sf=id&terms=HP%3A0012432": [
        1,
        ["HP:0012432"],
        {
            "definition": [
                "Subjective feeling of tiredness characterized by a lack of energy and "
                "motivation that persists for six months or longer"
            ],
            "synonym": [
                [
                    {
                        "term": "Chronic extreme exhaustion",
                        "relation": "EXACT",
                        "type": "layperson",
                    },
                    {
                        "term": "Chronic fatigue",
                        "relation": "EXACT",
                        "type": "layperson",
                        "xref": ["https://orcid.org/0000-0002-6548-5200"],
                    },
                ]
            ],
            "is_a": [[{"id": "HP:0012378", "name": "Fatigue"}]],
            "xref": [None],
            "alt_id": [None],
            "is_obsolete": [None],
            "comment": [
                "Note that chronic fatigue can be a symptom of chronic fatigue syndrome "
                "(CFS), which is characterized by profound fatigue that is not improved by "
                "bed rest and that may be worsened by physical or mental activity. "
                "Symptoms of CFS may include weakness, muscle pain, impaired memory, "
                "impaired mental concentration, and insomnia, which can result in reduced "
                "participation in daily activities."
            ],
        },
        [["Chronic fatigue"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search?cf=code&df=title&ef=definition%2Ctype%2Cchapter%2Csource%2CindexTerm%2CbrowserUrl&maxList=100&sf=code&terms=MG22": [
        1,
        ["MG22"],
        {
            "definition": [
                "A feeling of exhaustion, lethargy, or decreased energy, usually "
                "experienced as a weakening or depletion of one's physical or mental "
                "resource and characterised by a decreased capacity for work and "
                "reduced efficiency in responding to stimuli. Fatigue is normal "
                "following a period of exertion, mental or physical, but sometimes may "
                "occur in the absence of such exertion as a symptom of health "
                "conditions."
            ],
            "type": ["stem"],
            "chapter": ["21"],
            "source": ["http://id.who.int/icd/entity/1109546957"],
            "indexTerm": [
                "Fatigue; General physical deterioration; Lethargy; decline NOS; "
                "decreased energy; exhaustion; functional decline; general debilitation; "
                "general debility; general decline; lack of vitality; lethargic; "
                "prostration; slow decline; weak; weakness NOS; worn out"
            ],
            "browserUrl": ["https://icd.who.int/browse/2026-01/mms/en#1109546957"],
        },
        [["Fatigue"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/disease_names/v3/search?cf=ConceptID&df=DiseaseName&maxList=100&sf=ConceptID&terms=C0015672": [
        1,
        ["C0015672"],
        None,
        [["Fatigue"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?cf=code&df=name&maxList=100&sf=code&terms=E11.9": [
        1,
        ["E11.9"],
        None,
        [["Type 2 diabetes mellitus without complications"]],
    ],
    "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?cf=code&df=name&maxList=3&sf=code%2Cname&terms=zzzzqqqq": [
        0,
        [],
        None,
        [],
    ],
}
