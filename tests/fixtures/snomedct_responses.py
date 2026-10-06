"""SYNTHETIC Snowstorm responses for the SNOMED CT adapter tests.

These are NOT captured from a live server (browser.ihtsdotools.org refused connections
from the development network). They mirror the field layout of Snowstorm's documented
REST/JSON schema (``items``/``total`` pages, ``ConceptMini`` objects with ``fsn``/``pt``,
browser concepts with ``descriptions`` and ``relationships``). Concept IDs 84229001 and
52448006 and the attribute type IDs 116680003 (Is a) and 363698007 (Finding site) are
real SCTIDs; parent/child targets and terms are illustrative. Replace with captured
responses once the server is reachable.
"""

FATIGUE_MINI = {
    "conceptId": "84229001",
    "active": True,
    "definitionStatus": "PRIMITIVE",
    "moduleId": "900000000000207008",
    "fsn": {"term": "Fatigue (finding)", "lang": "en"},
    "pt": {"term": "Fatigue", "lang": "en"},
    "id": "84229001",
}

DEMENTIA_MINI = {
    "conceptId": "52448006",
    "active": True,
    "definitionStatus": "PRIMITIVE",
    "moduleId": "900000000000207008",
    "fsn": {"term": "Dementia (disorder)", "lang": "en"},
    "pt": {"term": "Dementia", "lang": "en"},
    "id": "52448006",
}

DESCRIPTION_SEARCH_FATIGUE = {
    "items": [
        {
            "active": True,
            "term": "Tiredness",
            "conceptId": "84229001",
            "languageCode": "en",
            "typeId": "900000000000013009",
            "descriptionId": "1",
            "concept": FATIGUE_MINI,
        },
        {  # same concept matched through a second synonym: must be de-duplicated
            "active": True,
            "term": "Fatigue",
            "conceptId": "84229001",
            "languageCode": "en",
            "typeId": "900000000000013009",
            "descriptionId": "2",
            "concept": FATIGUE_MINI,
        },
        {
            "active": True,
            "term": "Dementia",
            "conceptId": "52448006",
            "languageCode": "en",
            "typeId": "900000000000013009",
            "descriptionId": "3",
            "concept": DEMENTIA_MINI,
        },
        {  # concept object missing: falls back to the item's own conceptId/term
            "active": True,
            "term": "Orphan term",
            "conceptId": "111111111",
            "languageCode": "en",
            "descriptionId": "4",
        },
    ],
    "total": 4,
    "limit": 10,
    "offset": 0,
}

BROWSER_FATIGUE = {
    "conceptId": "84229001",
    "active": True,
    "definitionStatus": "PRIMITIVE",
    "moduleId": "900000000000207008",
    "effectiveTime": "20020131",
    "fsn": {"term": "Fatigue (finding)", "lang": "en"},
    "pt": {"term": "Fatigue", "lang": "en"},
    "descriptions": [
        {"active": True, "type": "FSN", "lang": "en", "term": "Fatigue (finding)"},
        {"active": True, "type": "SYNONYM", "lang": "en", "term": "Fatigue"},
        {"active": True, "type": "SYNONYM", "lang": "en", "term": "Tiredness"},
        {"active": True, "type": "SYNONYM", "lang": "en", "term": "Lack of energy"},
        {"active": False, "type": "SYNONYM", "lang": "en", "term": "Retired synonym"},
        {"active": True, "type": "SYNONYM", "lang": "es", "term": "Fatiga"},
        {
            "active": True,
            "type": "TEXT_DEFINITION",
            "lang": "en",
            "term": "Feeling of exhaustion.",
        },
        {"active": True, "type": "SYNONYM", "lang": "en", "term": ""},
    ],
    "relationships": [
        {
            "active": True,
            "characteristicType": "INFERRED_RELATIONSHIP",
            "groupId": 0,
            "typeId": "116680003",
            "type": {
                "conceptId": "116680003",
                "fsn": {"term": "Is a (attribute)"},
                "pt": {"term": "Is a"},
            },
            "target": {
                "conceptId": "404684003",
                "fsn": {"term": "Clinical finding (finding)"},
                "pt": {"term": "Clinical finding"},
            },
        },
        {  # stated duplicate of the above: must be ignored
            "active": True,
            "characteristicType": "STATED_RELATIONSHIP",
            "groupId": 0,
            "typeId": "116680003",
            "type": {"conceptId": "116680003", "pt": {"term": "Is a"}},
            "target": {"conceptId": "404684003", "pt": {"term": "Clinical finding"}},
        },
        {
            "active": True,
            "characteristicType": "INFERRED_RELATIONSHIP",
            "groupId": 1,
            "typeId": "363698007",
            "type": {
                "conceptId": "363698007",
                "fsn": {"term": "Finding site (attribute)"},
                "pt": {"term": "Finding site"},
            },
            "target": {
                "conceptId": "113343008",
                "fsn": {"term": "Structure of muscle (body structure)"},
                "pt": {"term": "Muscle structure"},
            },
        },
        {
            "active": False,
            "characteristicType": "INFERRED_RELATIONSHIP",
            "groupId": 0,
            "typeId": "116680003",
            "type": {"conceptId": "116680003", "pt": {"term": "Is a"}},
            "target": {"conceptId": "999999999", "pt": {"term": "Inactive parent"}},
        },
        {
            "active": True,
            "characteristicType": "INFERRED_RELATIONSHIP",
            "typeId": "1",
        },  # no target
    ],
}

CHILDREN_FATIGUE = [
    {
        "conceptId": "272060000",
        "active": True,
        "fsn": {"term": "Chronic fatigue (finding)"},
        "pt": {"term": "Chronic fatigue"},
    },
    {"conceptId": "272061001", "active": True, "fsn": {"term": "Acute fatigue (finding)"}},
    {"active": True, "fsn": {"term": "No id"}},
]

ICD10_MEMBERS = {
    "items": [
        {
            "active": True,
            "refsetId": "447562003",
            "referencedComponentId": "52448006",
            "additionalFields": {
                "mapGroup": "1",
                "mapPriority": "1",
                "mapRule": "",
                "mapAdvice": "ALWAYS F03.9",
                "mapTarget": "F03.9",
            },
        },
        {  # duplicate target: de-duplicated
            "active": True,
            "refsetId": "447562003",
            "additionalFields": {"mapTarget": "F03.9"},
        },
        {"active": True, "refsetId": "447562003", "additionalFields": {"mapTarget": ""}},
        {"active": True, "refsetId": "447562003", "additionalFields": {"mapTarget": "G30.9"}},
    ],
    "total": 4,
}
