"""Mock LOINC FHIR R4 responses for the LOINC adapter tests.

Shapes follow the FHIR R4 ``CodeSystem/$lookup`` (``Parameters``) and
``ValueSet/$expand`` (``ValueSet.expansion.contains``) specifications as served by
https://fhir.loinc.org. The server needs a loinc.org login, so these are hand-built
samples, not captured responses: the LP part codes are synthetic placeholders and the
designation ``use`` coding is an assumption (the adapter also accepts a plain display).
"""

EXPAND_CHOLESTEROL = {
    "resourceType": "ValueSet",
    "url": "http://loinc.org/vs",
    "expansion": {
        "total": 3,
        "contains": [
            {
                "system": "http://loinc.org",
                "code": "2093-3",
                "display": "Cholesterol [Mass/volume] in Serum or Plasma",
            },
            {
                "system": "http://loinc.org",
                "code": "2091-7",
                "display": "Cholesterol in LDL [Mass/volume] in Serum or Plasma by Direct assay",
                "contains": [
                    {"system": "http://loinc.org", "code": "13457-7", "display": "LDL calc"}
                ],
            },
            {"system": "http://loinc.org", "code": "2093-3", "display": "duplicate"},
            {"system": "http://loinc.org", "code": "", "display": "no code"},
            {"system": "http://loinc.org", "code": "9999-9"},
            "junk",
        ],
    },
}

EXPAND_EMPTY = {"resourceType": "ValueSet", "expansion": {"total": 0}}


def _coding(code, display):
    return {"system": "http://loinc.org", "code": code, "display": display}


LOOKUP_2093_3 = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "name", "valueString": "LOINC"},
        {"name": "version", "valueString": "2.78"},
        {"name": "display", "valueString": "Cholesterol [Mass/volume] in Serum or Plasma"},
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {"system": "http://loinc.org", "code": "LONG_COMMON_NAME"},
                },
                {"name": "value", "valueString": "Cholesterol [Mass/volume] in Serum or Plasma"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {"system": "http://loinc.org", "code": "SHORTNAME"},
                },
                {"name": "value", "valueString": "Cholest SerPl-mCnc"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {"name": "value", "valueString": "Total cholesterol"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "COMPONENT"},
                {"name": "value", "valueCoding": _coding("LP-SYN-1", "Cholesterol")},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "PROPERTY"},
                {"name": "value", "valueCoding": _coding("LP-SYN-2", "MCnc")},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "TIME_ASPCT"},
                {"name": "value", "valueCoding": _coding("LP-SYN-3", "Pt")},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "SYSTEM"},
                {"name": "value", "valueCoding": _coding("LP-SYN-4", "Ser/Plas")},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "SCALE_TYP"},
                {"name": "value", "valueCoding": _coding("LP-SYN-5", "Qn")},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "METHOD_TYP"},
                {"name": "value", "valueCoding": _coding("LP-SYN-6", "Photometry")},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "CLASS"},
                {"name": "value", "valueString": "CHEM"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "STATUS"},
                {"name": "value", "valueCode": "ACTIVE"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "DefinitionDescription"},
                {"name": "value", "valueString": "Total cholesterol in serum or plasma."},
            ],
        },
        {  # duplicate part value, empty value and a bad part must be ignored
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "COMPONENT"},
                {"name": "value", "valueCoding": _coding("LP-SYN-1", "Cholesterol")},
            ],
        },
        {"name": "property", "part": [{"name": "code", "valueCode": "EMPTY"}]},
        {"name": "property", "part": [{"name": "value", "valueString": "orphan"}]},
        "junk",
    ],
}

LOOKUP_WITH_HIERARCHY = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "display", "valueString": "Lipid panel"},
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "LP-SYN-PARENT"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCoding": _coding("2093-3", "Cholesterol")},
            ],
        },
    ],
}

OPERATION_OUTCOME = {
    "resourceType": "OperationOutcome",
    "issue": [{"severity": "error", "code": "not-found", "diagnostics": "Unknown code"}],
}
