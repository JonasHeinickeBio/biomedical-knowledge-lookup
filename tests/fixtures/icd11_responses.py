"""Mock ICD-API v2 responses for the ICD-11 adapter tests.

Shapes follow WHO's OpenAPI description (https://id.who.int/swagger/v2/swagger.json):
``ISearchResult`` / ``ISimpleEntity``, ``CodeInfo`` and ``LinearizationEntity`` with
JSON-LD ``{"@language", "@value"}`` text objects. The numeric entity ids below are
synthetic placeholders (the adapter was not run against the live, credential-gated API);
titles/codes (8E49 Postviral fatigue syndrome, 8E4 parent, RA02) follow ICD-11 MMS.
"""

TOKEN_RESPONSE = {
    "access_token": "tok-abc",
    "expires_in": 3600,
    "token_type": "Bearer",
}

RELEASE = "2025-01"
MMS = f"http://id.who.int/icd/release/11/{RELEASE}/mms"

SEARCH_RESPONSE = {
    "error": False,
    "errorMessage": None,
    "resultChopped": False,
    "destinationEntities": [
        {
            "id": f"{MMS}/111111111",
            "title": 'Postviral <em class="found">fatigue</em> syndrome',
            "stemId": f"{MMS}/111111111",
            "isLeaf": True,
            "chapter": "08",
            "theCode": "8E49",
            "score": 0.93,
            "matchingPVs": [{"propertyId": "Title", "label": "Postviral fatigue syndrome"}],
        },
        {
            "id": f"{MMS}/222222222",
            "title": "Fatigue",
            "stemId": f"{MMS}/222222222",
            "isLeaf": True,
            "chapter": "21",
            "theCode": "MG22",
            "score": 0.71,
            "matchingPVs": [],
        },
        {  # a block without a code is still returned by flat searches
            "id": f"{MMS}/333333333",
            "title": "Diseases of the nervous system",
            "stemId": f"{MMS}/333333333",
            "chapter": "08",
            "theCode": "",
            "score": 0.2,
        },
        {  # duplicate of the first hit
            "id": f"{MMS}/111111111",
            "title": "Postviral fatigue syndrome",
            "stemId": f"{MMS}/111111111",
            "theCode": "8E49",
            "score": 0.5,
        },
    ],
}

CODEINFO_8E49 = {
    "code": "8E49",
    "stemCode": "8E49",
    "stemId": f"{MMS}/111111111",
}

ENTITY_8E49 = {
    "@context": "http://id.who.int/icd/contexts/contextForLinearizationEntity.json",
    "@id": f"{MMS}/111111111",
    "title": {"@language": "en", "@value": "Postviral fatigue syndrome"},
    "definition": {
        "@language": "en",
        "@value": "A disorder characterised by prolonged fatigue following an infection.",
    },
    "source": "http://id.who.int/icd/entity/444444444",
    "code": "8E49",
    "classKind": "category",
    "parent": [f"{MMS}/555555555"],
    "child": [],
    "inclusion": [
        {"label": {"@language": "en", "@value": "Benign myalgic encephalomyelitis"}},
    ],
    "indexTerm": [
        {"label": {"@language": "en", "@value": "Postviral fatigue syndrome"}},
        {"label": {"@language": "en", "@value": "Chronic fatigue syndrome"}},
        {"label": {"@language": "en", "@value": "Old term"}, "deprecated": True},
    ],
}

ENTITY_8E4 = {
    "@id": f"{MMS}/555555555",
    "title": {"@language": "en", "@value": "Other specified diseases of the nervous system"},
    "code": "8E4",
    "classKind": "block",
    "parent": [f"{MMS}/666666666"],
    "child": [f"{MMS}/111111111", f"{MMS}/777777777"],
}

ENTITY_8E4A = {
    "@id": f"{MMS}/777777777",
    "title": {"@language": "en", "@value": "Another nervous system disease"},
    "code": "8E4A",
    "classKind": "category",
    "parent": [f"{MMS}/555555555"],
}

ENTITY_SYMPTOM_MG22 = {
    "@id": f"{MMS}/222222222",
    "title": {"@language": "en", "@value": "Fatigue"},
    "code": "MG22",
    "classKind": "category",
    "parent": [],
}

ENTITY_EXTENSION = {
    "@id": "http://id.who.int/icd/release/11/2025-01/mms/888888888",
    "title": {"@language": "en", "@value": "Mild"},
    "code": "XS5W",
    "parent": [],
}
