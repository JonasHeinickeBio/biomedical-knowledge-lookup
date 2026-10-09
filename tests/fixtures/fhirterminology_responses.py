"""Trimmed real responses of the FHIR terminology servers tx.fhir.org/r4 and the CSIRO
Ontoserver sandbox (captured 2026-10-09), used by tests/unit/test_fhirterminology_adapter.py.

Names ending in ``_ONTOSERVER`` / the ICD-10-GM, HPO and OPS entries come from
``https://r4.ontoserver.csiro.au/fhir``; the rest from ``https://tx.fhir.org/r4``.
Designation / child lists were shortened to keep the file small.
"""

METADATA_TXFHIR = {
    "resourceType": "CapabilityStatement",
    "id": "FhirServer",
    "url": "https://tx.fhir.org/r4/CapabilityStatement/tx",
    "version": "4.0.1-0.15.0",
    "name": "FHIRTerminologyServer",
    "title": "FHIR Terminology Server",
    "status": "active",
    "date": "2026-10-09T06:05:41.107Z",
    "kind": "instance",
    "software": {"name": "FHIRsmith", "version": "0.15.0", "releaseDate": "2026-10-08"},
    "implementation": {
        "description": "FHIR Server running at https://tx.fhir.org/r4",
        "url": "https://tx.fhir.org/r4",
    },
    "fhirVersion": "4.0.1",
    "rest": [
        {
            "mode": "server",
            "security": {"cors": True},
            "resource": [
                {
                    "type": "CodeSystem",
                    "interaction": [
                        {"code": "read", "documentation": "Read a code system"},
                        {"code": "search-type", "documentation": "Search the code systems"},
                    ],
                    "searchParam": [
                        {"name": "url", "type": "uri"},
                        {"name": "version", "type": "token"},
                        {"name": "name", "type": "string"},
                        {"name": "title", "type": "string"},
                        {"name": "status", "type": "token"},
                        {"name": "_id", "type": "token"},
                    ],
                    "operation": [
                        {
                            "name": "lookup",
                            "definition": "http://hl7.org/fhir/OperationDefinition/CodeSystem-lookup",
                        },
                        {
                            "name": "validate-code",
                            "definition": "http://hl7.org/fhir/OperationDefinition/CodeSystem-validate-code",
                        },
                        {
                            "name": "subsumes",
                            "definition": "http://hl7.org/fhir/OperationDefinition/CodeSystem-subsumes",
                        },
                    ],
                },
                {
                    "type": "ValueSet",
                    "interaction": [
                        {"code": "read", "documentation": "Read a ValueSet"},
                        {"code": "search-type", "documentation": "Search the value sets"},
                    ],
                    "searchParam": [
                        {"name": "url", "type": "uri"},
                        {"name": "version", "type": "token"},
                        {"name": "name", "type": "string"},
                        {"name": "title", "type": "string"},
                        {"name": "status", "type": "token"},
                        {"name": "_id", "type": "token"},
                    ],
                    "operation": [
                        {
                            "name": "expand",
                            "definition": "http://hl7.org/fhir/OperationDefinition/ValueSet-expand",
                        },
                        {
                            "name": "validate-code",
                            "definition": "http://hl7.org/fhir/OperationDefinition/ValueSet-validate-code",
                        },
                        {
                            "name": "compare",
                            "definition": "http://hl7.org/fhir/tools/OperationDefinition/ValueSet-compare",
                        },
                    ],
                },
                {
                    "type": "ConceptMap",
                    "interaction": [
                        {"code": "read", "documentation": "Read a ConceptMap"},
                        {"code": "search-type", "documentation": "Search the concept maps"},
                    ],
                    "searchParam": [
                        {"name": "url", "type": "uri"},
                        {"name": "version", "type": "token"},
                        {"name": "name", "type": "string"},
                        {"name": "title", "type": "string"},
                        {"name": "status", "type": "token"},
                        {"name": "_id", "type": "token"},
                    ],
                    "operation": [
                        {
                            "name": "translate",
                            "definition": "http://hl7.org/fhir/OperationDefinition/ConceptMap-translate",
                        }
                    ],
                },
            ],
            "interaction": [{"code": "transaction"}],
            "operation": [
                {
                    "name": "expand",
                    "definition": "http://hl7.org/fhir/OperationDefinition/ValueSet-expand",
                },
                {
                    "name": "lookup",
                    "definition": "http://hl7.org/fhir/OperationDefinition/CodeSystem-lookup",
                },
                {
                    "name": "subsumes",
                    "definition": "http://hl7.org/fhir/OperationDefinition/CodeSystem-subsumes",
                },
                {
                    "name": "validate-code",
                    "definition": "http://hl7.org/fhir/OperationDefinition/Resource-validate-code",
                },
                {
                    "name": "translate",
                    "definition": "http://hl7.org/fhir/OperationDefinition/ConceptMap-translate",
                },
                {
                    "name": "compare",
                    "definition": "http://hl7.org/fhir/tools/OperationDefinition/ValueSet-compare",
                },
                {
                    "name": "cache-control",
                    "definition": "http://hl7.org/fhir/tools/OperationDefinition/cache-control",
                },
                {
                    "name": "versions",
                    "definition": "http://hl7.org/fhir/OperationDefinition/fhir-versions",
                },
            ],
        }
    ],
}

LOOKUP_SNOMED_FATIGUE = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "name", "valueString": "SNOMED CT International Edition"},
        {"name": "code", "valueCode": "84229001"},
        {"name": "system", "valueUri": "http://snomed.info/sct"},
        {
            "name": "version",
            "valueString": "http://snomed.info/sct/900000000000207008/version/20250201",
        },
        {"name": "display", "valueString": "Fatigue"},
        {"name": "abstract", "valueBoolean": False},
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "inactive"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000013009",
                        "display": "Synonym",
                    },
                },
                {"name": "value", "valueString": "Fatigue"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000013009",
                        "display": "Synonym",
                    },
                },
                {"name": "status", "valueCode": "inactive"},
                {"name": "value", "valueString": "Tiredness"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000013009",
                        "display": "Synonym",
                    },
                },
                {"name": "value", "valueString": "Weariness"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000003001",
                        "display": "Fully specified name",
                    },
                },
                {"name": "value", "valueString": "Fatigue (finding)"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000550004",
                        "display": "Definition",
                    },
                },
                {
                    "name": "value",
                    "valueString": "Fatigue refers to a lack of energy, and it may be "
                    "either acute or chronic. Fatigue may result from "
                    "exertion, stress, and a wide variety of underlying "
                    "medical conditions, including infections, "
                    "malignancies, autoimmune disorders, anxiety, and "
                    "depression. It may also be an adverse effect of "
                    "medical treatments such as chemotherapy. Depending "
                    "on the underlying cause, fatigue may or may not be "
                    "relieved by rest.",
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "effectiveTime"},
                {"name": "value", "valueDateTime": "2002-01-31"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "359752005"},
                {"name": "description", "valueString": "Energy and stamina finding"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "105721009"},
                {"name": "description", "valueString": "General problem AND/OR complaint"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "224960004"},
                {"name": "description", "valueString": "Tired"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "13791008"},
                {"name": "description", "valueString": "Asthenia"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "420900006"},
                {
                    "name": "description",
                    "valueString": "Fatigue with AIDS (acquired immunodeficiency syndrome)",
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "442099003"},
                {"name": "description", "valueString": "Psychogenic fatigue"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "704369007"},
                {"name": "description", "valueString": "Fatigue due to treatment"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "module"},
                {"name": "value", "valueCode": "900000000000207008"},
                {"name": "description", "valueString": "SNOMED CT core"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "363714003"},
                {"name": "value", "valueCode": "359755007"},
                {"name": "description", "valueString": "Energy / stamina"},
                {"name": "code-display", "valueString": "Interprets"},
            ],
        },
    ],
}

LOOKUP_SNOMED_CFS_ONTOSERVER = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "code", "valueCode": "52702003"},
        {"name": "display", "valueString": "Chronic fatigue syndrome"},
        {"name": "name", "valueString": "SNOMED Clinical Terms Australian extension"},
        {"name": "system", "valueUri": "http://snomed.info/sct"},
        {
            "name": "version",
            "valueString": "http://snomed.info/sct/32506021000036107/version/20260930",
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "609096000"},
                {
                    "name": "subproperty",
                    "part": [
                        {"name": "code", "valueCode": "363698007"},
                        {"name": "value", "valueCode": "25087005"},
                        {"name": "valueCode", "valueCode": "25087005"},
                    ],
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "609096000"},
                {
                    "name": "subproperty",
                    "part": [
                        {"name": "code", "valueCode": "363714003"},
                        {"name": "value", "valueCode": "359755007"},
                        {"name": "valueCode", "valueCode": "359755007"},
                    ],
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "609096000"},
                {
                    "name": "subproperty",
                    "part": [
                        {"name": "code", "valueCode": "263502005"},
                        {"name": "value", "valueCode": "90734009"},
                        {"name": "valueCode", "valueCode": "90734009"},
                    ],
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "inactive"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "84229001"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "128283000"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "sufficientlyDefined"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "effectiveTime"},
                {"name": "value", "valueString": "20020131"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "moduleId"},
                {"name": "value", "valueCode": "900000000000207008"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "normalFormTerse"},
                {
                    "name": "value",
                    "valueString": "<<<52702003:{363698007=25087005},{363714003=359755007},{263502005=90734009}",
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "normalForm"},
                {
                    "name": "value",
                    "valueString": "<<< 52702003|Chronic fatigue "
                    "syndrome|:{363698007|Finding "
                    "site|=25087005|Structure of nervous "
                    "system|},{363714003|Interprets|=359755007|Energy / "
                    "stamina|},{263502005|Clinical "
                    "course|=90734009|Chronic|}",
                },
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000013009",
                        "display": "Synonym",
                    },
                },
                {"name": "value", "valueString": "Benign myalgic encephalomyelitis"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000013009",
                        "display": "Synonym",
                    },
                },
                {"name": "value", "valueString": "CFS - Chronic fatigue syndrome"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                    },
                },
                {"name": "value", "valueString": "Chronic fatigue syndrome"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-x-sctlang-32570271-00003610-6"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                        "display": "Preferred For Language",
                    },
                },
                {"name": "value", "valueString": "Chronic fatigue syndrome"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-x-sctlang-90000000-00005090-07"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                        "display": "Preferred For Language",
                    },
                },
                {"name": "value", "valueString": "Chronic fatigue syndrome"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-x-sctlang-90000000-00005080-04"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                        "display": "Preferred For Language",
                    },
                },
                {"name": "value", "valueString": "Chronic fatigue syndrome"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://snomed.info/sct",
                        "code": "900000000000003001",
                        "display": "Fully specified name",
                    },
                },
                {"name": "value", "valueString": "Chronic fatigue syndrome (disorder)"},
            ],
        },
    ],
}

LOOKUP_LOINC_CHOLESTEROL = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "name", "valueString": "LOINC"},
        {"name": "code", "valueCode": "2093-3"},
        {"name": "system", "valueUri": "http://loinc.org"},
        {"name": "version", "valueString": "2.82"},
        {"name": "display", "valueString": "Cholesterol [Mass/volume] in Serum or Plasma"},
        {"name": "abstract", "valueBoolean": False},
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "inactive"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-US"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                        "display": "Preferred For Language",
                    },
                },
                {"name": "value", "valueString": "Cholesterol [Mass/volume] in Serum or Plasma"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-US"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://loinc.org",
                        "code": "LONG_COMMON_NAME",
                        "display": "LONG_COMMON_NAME",
                    },
                },
                {"name": "value", "valueString": "Cholesterol [Mass/volume] in Serum or Plasma"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "de-DE"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://loinc.org",
                        "code": "LONG_COMMON_NAME",
                        "display": "LONG_COMMON_NAME",
                    },
                },
                {
                    "name": "value",
                    "valueString": "Cholesterol [Masse/Volumen] in Serum oder Plasma",
                },
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-US"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://loinc.org",
                        "code": "SHORTNAME",
                        "display": "SHORTNAME",
                    },
                },
                {"name": "value", "valueString": "Cholest SerPl-mCnc"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-US"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://loinc.org",
                        "code": "ConsumerName",
                        "display": "ConsumerName",
                    },
                },
                {"name": "value", "valueString": "Cholesterol, Blood"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "CLASS"},
                {"name": "value", "valueCode": "LP7786-9"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "COMPONENT"},
                {"name": "value", "valueCode": "LP15493-7"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "PROPERTY"},
                {"name": "value", "valueCode": "LP6827-2"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "TIME_ASPCT"},
                {"name": "value", "valueCode": "LP6960-1"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "SYSTEM"},
                {"name": "value", "valueCode": "LP7576-4"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "SCALE_TYP"},
                {"name": "value", "valueCode": "LP7753-9"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "LP382412-7"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "CLASSTYPE"},
                {"name": "value", "valueString": "1"},
                {"name": "description", "valueString": "Laboratory class"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "ORDER_OBS"},
                {"name": "value", "valueString": "Both"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "EXAMPLE_UNITS"},
                {"name": "value", "valueString": "mg/dL"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "EXAMPLE_UCUM_UNITS"},
                {"name": "value", "valueString": "mg/dL"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "UNITSREQUIRED"},
                {"name": "value", "valueString": "Y"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "STATUS"},
                {"name": "value", "valueString": "ACTIVE"},
            ],
        },
    ],
}

LOOKUP_ICD10GM_G933 = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "code", "valueCode": "G93.3"},
        {
            "name": "definition",
            "valueString": "Chronisches Müdigkeitssyndrom [Chronic fatigue syndrome]",
        },
        {
            "name": "display",
            "valueString": "Chronisches Müdigkeitssyndrom [Chronic fatigue syndrome]",
        },
        {"name": "name", "valueString": "CodeSystemICD10GM2020"},
        {"name": "system", "valueUri": "http://fhir.de/CodeSystem/bfarm/icd-10-gm"},
        {"name": "version", "valueString": "2020"},
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "inactive"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "G93"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-AU"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                    },
                },
                {
                    "name": "value",
                    "valueString": "Chronisches Müdigkeitssyndrom [Chronic fatigue syndrome]",
                },
            ],
        },
    ],
}

LOOKUP_HPO_FATIGUE = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "code", "valueCode": "HP:0012378"},
        {"name": "display", "valueString": "Fatigue"},
        {"name": "name", "valueString": "human_phenotype_ontology_20201207"},
        {"name": "system", "valueUri": "http://purl.obolibrary.org/obo/hp.owl"},
        {"name": "version", "valueString": "20201207"},
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "inactive"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "HP:0025142"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "HP:0030973"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "HP:0012431"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "HP:0033236"},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "child"},
                {"name": "value", "valueCode": "HP:0012432"},
            ],
        },
        {
            "name": "designation",
            "part": [
                {"name": "language", "valueCode": "en-AU"},
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                    },
                },
                {"name": "value", "valueString": "Fatigue"},
            ],
        },
    ],
}

LOOKUP_ICD10CM_G9332 = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "name", "valueString": "ICD_10_CM"},
        {"name": "code", "valueCode": "G93.32"},
        {"name": "system", "valueUri": "http://hl7.org/fhir/sid/icd-10-cm"},
        {"name": "version", "valueString": "2026-04-01"},
        {"name": "display", "valueString": "Myalgic encephalomyelitis/chronic fatigue syndrome"},
        {"name": "abstract", "valueBoolean": False},
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "inactive"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "designation",
            "part": [
                {
                    "name": "use",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                        "code": "preferredForLanguage",
                        "display": "Preferred For Language",
                    },
                },
                {
                    "name": "value",
                    "valueString": "Myalgic encephalomyelitis/chronic fatigue syndrome",
                },
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "notSelectable"},
                {"name": "value", "valueBoolean": False},
            ],
        },
        {
            "name": "property",
            "part": [
                {"name": "code", "valueCode": "parent"},
                {"name": "value", "valueCode": "G93.3"},
                {"name": "description", "valueString": "Postviral and related fatigue syndromes"},
            ],
        },
    ],
}

EXPAND_SNOMED_FATIGUE = {
    "resourceType": "ValueSet",
    "url": "http://snomed.info/sct?fhir_vs",
    "name": "All SNOMED CT Concepts",
    "status": "active",
    "experimental": False,
    "expansion": {
        "identifier": "urn:uuid:168c4239-81b6-45d9-bb44-78e809924e79",
        "timestamp": "2026-10-09T16:07:50+10:00",
        "total": 137,
        "parameter": [
            {
                "name": "used-codesystem",
                "valueUri": "http://snomed.info/sct|http://snomed.info/sct/32506021000036107/version/20260930",
            },
            {
                "name": "version",
                "valueUri": "http://snomed.info/sct|http://snomed.info/sct/32506021000036107/version/20260930",
            },
            {"name": "filter", "valueString": "fatigue"},
            {"name": "count", "valueInteger": 3},
        ],
        "contains": [
            {"system": "http://snomed.info/sct", "code": "84229001", "display": "Fatigue"},
            {
                "extension": [
                    {
                        "url": "http://ontoserver.csiro.au/profiles/expansion",
                        "extension": [{"url": "inactive", "valueBoolean": True}],
                    }
                ],
                "system": "http://snomed.info/sct",
                "inactive": True,
                "code": "139126000",
                "display": "Fatigue",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "22171002",
                "display": "Neuromuscular fatigue",
            },
        ],
    },
}

EXPAND_LOINC_INLINE = {
    "resourceType": "ValueSet",
    "status": "active",
    "expansion": {
        "timestamp": "2026-10-09T06:08:22.128Z",
        "identifier": "urn:uuid:6c7dcbf5-48aa-4520-9892-9e3328dce36b",
        "parameter": [
            {"name": "filter", "valueString": "fatigue"},
            {"name": "count", "valueInteger": 3},
            {"name": "used-codesystem", "valueUri": "http://loinc.org|2.82"},
        ],
        "contains": [
            {"system": "http://loinc.org", "code": "LA19104-1", "display": "0 - no fatigue"},
            {
                "system": "http://loinc.org",
                "code": "LA19105-8",
                "display": "10 - fatigue as bad as you can imagine",
            },
            {
                "system": "http://loinc.org",
                "code": "LA21156-7",
                "display": "Alert fatigue/alarm fatigue",
            },
        ],
    },
}

EXPAND_ICD10GM_2020 = {
    "resourceType": "ValueSet",
    "status": "active",
    "expansion": {
        "identifier": "urn:uuid:22aeb660-1764-4b26-91f6-ab5825cee125",
        "timestamp": "2026-10-09T16:11:49+10:00",
        "total": 1,
        "parameter": [
            {
                "name": "used-codesystem",
                "valueUri": "http://fhir.de/CodeSystem/bfarm/icd-10-gm|2020",
            },
            {"name": "version", "valueUri": "http://fhir.de/CodeSystem/bfarm/icd-10-gm|2020"},
            {"name": "filter", "valueString": "Müdigkeit"},
            {"name": "count", "valueInteger": 3},
        ],
        "contains": [
            {
                "system": "http://fhir.de/CodeSystem/bfarm/icd-10-gm",
                "code": "G93.3",
                "display": "Chronisches Müdigkeitssyndrom [Chronic fatigue syndrome]",
            }
        ],
    },
}

EXPAND_HPO_DESIGNATIONS = {
    "resourceType": "ValueSet",
    "status": "active",
    "expansion": {
        "identifier": "urn:uuid:9a60ea95-1cd4-4f77-9bc4-2c65f099e25e",
        "timestamp": "2026-10-09T16:11:52+10:00",
        "total": 6,
        "parameter": [
            {
                "name": "used-codesystem",
                "valueUri": "http://purl.obolibrary.org/obo/hp.owl|20201207",
            },
            {"name": "version", "valueUri": "http://purl.obolibrary.org/obo/hp.owl|20201207"},
            {"name": "filter", "valueString": "fatigue"},
            {"name": "includeDesignations", "valueBoolean": True},
            {"name": "count", "valueInteger": 3},
        ],
        "contains": [
            {
                "system": "http://purl.obolibrary.org/obo/hp.owl",
                "code": "HP:0012378",
                "display": "Fatigue",
                "designation": [
                    {
                        "language": "en-AU",
                        "use": {
                            "system": "http://terminology.hl7.org/CodeSystem/hl7TermMaintInfra",
                            "code": "preferredForLanguage",
                        },
                        "value": "Fatigue",
                    }
                ],
            }
        ],
    },
}

OUTCOME_UNKNOWN_SYSTEM_422 = {
    "resourceType": "OperationOutcome",
    "issue": [
        {
            "severity": "error",
            "code": "not-found",
            "details": {
                "text": "CodeSystem not found: http://fhir.de/CodeSystem/bfarm/icd-10-gm",
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/tools/CodeSystem/tx-issue-type",
                        "code": "not-found",
                    }
                ],
            },
            "diagnostics": "CodeSystem not found: http://fhir.de/CodeSystem/bfarm/icd-10-gm",
        }
    ],
}

OUTCOME_CODE_NOT_FOUND_404 = {
    "resourceType": "OperationOutcome",
    "issue": [
        {
            "severity": "error",
            "code": "not-found",
            "details": {
                "text": "Unable to find code '0000' in http://snomed.info/sct version "
                "http://snomed.info/sct/900000000000207008/version/20250201 "
                "(Not a valid expression: Concept 0000 not found)",
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/tools/CodeSystem/tx-issue-type",
                        "code": "invalid-code",
                    }
                ],
            },
        }
    ],
}

OUTCOME_ATC_AMBIGUOUS_422 = {
    "resourceType": "OperationOutcome",
    "issue": [
        {
            "severity": "error",
            "code": "processing",
            "details": {
                "text": "Found more than one Resource with the same URL "
                "http://www.whocc.no/atc with date-like versions except for "
                "2020-05 and was unable to determine a default version using "
                "date-format versioning: [2020-05, 20241015, 2025.0.0, "
                "20250201]"
            },
            "diagnostics": "Found more than one Resource with the same URL "
            "http://www.whocc.no/atc with date-like versions except for 2020-05 "
            "and was unable to determine a default version using date-format "
            "versioning: [2020-05, 20241015, 2025.0.0, 20250201]",
        }
    ],
}

OUTCOME_IMPLICIT_VS_MISSING_404 = {
    "resourceType": "OperationOutcome",
    "issue": [
        {
            "severity": "error",
            "code": "not-found",
            "details": {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/tools/CodeSystem/tx-issue-type",
                        "code": "not-found",
                    }
                ],
                "text": "[8b6318ee-8764-4b57-9641-528fcb3b8d86]: Could not find value "
                "set http://fhir.de/CodeSystem/bfarm/icd-10-gm?fhir_vs and "
                "version null. If this is an implicit value set please make "
                "sure the url is correct. Implicit values sets for different "
                "code systems are specified in "
                "https://www.hl7.org/fhir/terminologies-systems.html.",
            },
            "diagnostics": "[8b6318ee-8764-4b57-9641-528fcb3b8d86]: Could not find value set "
            "http://fhir.de/CodeSystem/bfarm/icd-10-gm?fhir_vs and version "
            "null. If this is an implicit value set please make sure the url is "
            "correct. Implicit values sets for different code systems are "
            "specified in https://www.hl7.org/fhir/terminologies-systems.html.",
        },
        {
            "severity": "information",
            "code": "informational",
            "diagnostics": "X-Request-Id: 0753b61a-18fc-414d-9650-a42f4c728b25",
        },
    ],
}

TRANSLATE_SNOMED_ONTOSERVER = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "result", "valueBoolean": True},
        {
            "name": "match",
            "part": [
                {"name": "equivalence", "valueCode": "wider"},
                {
                    "name": "concept",
                    "valueCoding": {
                        "system": "http://hl7.org/fhir/sid/icd-10-am",
                        "code": "G93.3",
                    },
                },
                {
                    "name": "source",
                    "valueUri": "http://aehrc.com/fhir/ConceptMap/aehrc-snomap-starter",
                },
            ],
        },
        {
            "name": "match",
            "part": [
                {"name": "equivalence", "valueCode": "equal"},
                {
                    "name": "concept",
                    "valueCoding": {
                        "system": "http://terminology.hl7.org/CodeSystem/mdr",
                        "code": "10008874",
                        "display": "Chronic fatigue syndrome",
                    },
                },
                {
                    "name": "source",
                    "valueUri": "https://nzhts.digital.health.nz/fhir/ConceptMap/snomedct-meddra",
                },
            ],
        },
        {
            "name": "match",
            "part": [
                {"name": "equivalence", "valueCode": "equal"},
                {
                    "name": "concept",
                    "valueCoding": {"system": "http://read.info/readv2", "code": "Eu46000"},
                },
                {
                    "name": "source",
                    "valueUri": "https://nzhts.digital.health.nz/fhir/ConceptMap/snomed-read-acc-map",
                },
            ],
        },
        {
            "name": "match",
            "part": [
                {"name": "equivalence", "valueCode": "equal"},
                {
                    "name": "concept",
                    "valueCoding": {"system": "http://read.info/readv2", "code": "Eu46000"},
                },
                {
                    "name": "source",
                    "valueUri": "https://nzhts.digital.health.nz/fhir/ConceptMap/snomed-read-msd-map",
                },
            ],
        },
        {
            "name": "match",
            "part": [
                {"name": "equivalence", "valueCode": "equal"},
                {
                    "name": "concept",
                    "valueCoding": {"system": "http://read.info/readv2", "code": "F286.00"},
                },
                {
                    "name": "source",
                    "valueUri": "https://nzhts.digital.health.nz/fhir/ConceptMap/snomed-read-map",
                },
            ],
        },
        {
            "name": "match",
            "part": [
                {"name": "equivalence", "valueCode": "equal"},
                {
                    "name": "concept",
                    "valueCoding": {"system": "http://read.info/readv2", "code": "Eu46000"},
                },
                {
                    "name": "source",
                    "valueUri": "https://nzhts.digital.health.nz/fhir/ConceptMap/snomed-read-map",
                },
            ],
        },
    ],
}

TRANSLATE_NO_CONCEPTMAP = {
    "resourceType": "Parameters",
    "parameter": [
        {
            "name": "message",
            "valueString": "No ConceptMap is available to translate from "
            "'http://snomed.info/sct' to "
            "'http://hl7.org/fhir/sid/icd-10-cm'",
        },
        {"name": "result", "valueBoolean": False},
    ],
}

VALIDATE_CODE_OK = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "result", "valueBoolean": True},
        {"name": "system", "valueUri": "http://snomed.info/sct"},
        {"name": "code", "valueCode": "84229001"},
        {
            "name": "version",
            "valueString": "http://snomed.info/sct/900000000000207008/version/20250201",
        },
        {"name": "display", "valueString": "Fatigue"},
    ],
}

VALIDATE_CODE_BAD = {
    "resourceType": "Parameters",
    "parameter": [
        {"name": "result", "valueBoolean": False},
        {"name": "system", "valueUri": "http://snomed.info/sct"},
        {"name": "code", "valueCode": "0000"},
        {
            "name": "message",
            "valueString": "Unknown code '0000' in the CodeSystem 'http://snomed.info/sct' "
            "version "
            "'http://snomed.info/sct/900000000000207008/version/20250201' "
            "(International Edition)",
        },
    ],
}

CODESYSTEM_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 6,
    "link": [
        {
            "relation": "self",
            "url": "https://tx.fhir.org/r4/CodeSystem?_elements=url%2Cversion%2Cname%2Ctitle%2Ccontent&title=ICD&_count=20&_offset=0",
        }
    ],
    "entry": [
        {
            "fullUrl": "https://tx.fhir.org/r4/CodeSystem/core-icd-10-procedures",
            "search": {"mode": "match"},
            "resource": {
                "resourceType": "CodeSystem",
                "id": "core-icd-10-procedures",
                "url": "http://hl7.org/fhir/sid/ex-icd-10-procedures",
                "version": "4.0.1",
                "name": "ICD-10ProcedureCodes",
                "title": "ICD-10 Procedure Codes",
                "content": "complete",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                        }
                    ]
                },
            },
        },
        {
            "fullUrl": "https://tx.fhir.org/r4/CodeSystem/tx-icd-10-cm",
            "search": {"mode": "match"},
            "resource": {
                "resourceType": "CodeSystem",
                "id": "tx-icd-10-cm",
                "url": "http://hl7.org/fhir/sid/icd-10-cm",
                "version": "2026-04-01",
                "name": "ICD_10_CM",
                "title": "International Classification of Diseases, Tenth Revision, "
                "Clinical Modification (ICD-10-CM)",
                "content": "complete",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                        }
                    ]
                },
            },
        },
        {
            "fullUrl": "https://tx.fhir.org/r4/CodeSystem/tx-icd-9-cm",
            "search": {"mode": "match"},
            "resource": {
                "resourceType": "CodeSystem",
                "id": "tx-icd-9-cm",
                "url": "http://hl7.org/fhir/sid/icd-9-cm",
                "version": "2015",
                "name": "ICD_9_CM",
                "title": "International Classification of Diseases, Ninth Revision, "
                "Clinical Modification (ICD-9-CM)",
                "content": "complete",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                        }
                    ]
                },
            },
        },
        {
            "fullUrl": "https://tx.fhir.org/r4/CodeSystem/tx-icd-o-3",
            "search": {"mode": "match"},
            "resource": {
                "resourceType": "CodeSystem",
                "id": "tx-icd-o-3",
                "url": "http://terminology.hl7.org/CodeSystem/icd-o-3",
                "version": "2000",
                "name": "ICD_O_3",
                "title": "ICD-O-3",
                "content": "fragment",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                        }
                    ]
                },
            },
        },
    ],
}
