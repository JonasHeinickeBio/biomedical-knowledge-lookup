"""Trimmed real MeSH responses (captured live from id.nlm.nih.gov, 2026-10-06)."""

LOOKUP_DESCRIPTOR_EXACT = [
    {"label": "Fatigue Syndrome, Chronic", "resource": "http://id.nlm.nih.gov/mesh/D015673"}
]

LOOKUP_DESCRIPTOR_CONTAINS_FATIGUE = [
    {"label": "Fatigue", "resource": "http://id.nlm.nih.gov/mesh/D005221"},
    {"label": "Fatigue Syndrome, Chronic", "resource": "http://id.nlm.nih.gov/mesh/D015673"},
    {"label": "Auditory Fatigue", "resource": "http://id.nlm.nih.gov/mesh/D001305"},
]

LOOKUP_TERM_LONG_COVID = [
    {"label": "Long COVID", "resource": "http://id.nlm.nih.gov/mesh/T001119073"},
    {"label": "long COVID brain fog", "resource": "http://id.nlm.nih.gov/mesh/T001135645"},
]

SPARQL_DETAILS = {
    "head": {"vars": ["d", "kind", "v", "via"]},
    "results": {
        "bindings": [
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000175"},
                "kind": {"type": "literal", "value": "label"},
                "v": {"type": "literal", "value": "diagnosis"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "label"},
                "v": {"type": "literal", "value": "Fatigue Syndrome, Chronic"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "label"},
                "v": {"type": "literal", "value": "[OBSOLETE] COVID-19"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "label"},
                "v": {"type": "literal", "value": "Post-Acute COVID-19 Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000175"},
                "kind": {"type": "literal", "value": "type"},
                "v": {"type": "literal", "value": "Qualifier"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "type"},
                "v": {"type": "literal", "value": "TopicalDescriptor"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "type"},
                "v": {"type": "literal", "value": "SCR_Disease"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "type"},
                "v": {"type": "literal", "value": "TopicalDescriptor"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000175"},
                "kind": {"type": "literal", "value": "scope"},
                "v": {
                    "type": "literal",
                    "value": "Used with diseases for all aspects of diagnosis, "
                    "including examination, differential diagnosis and "
                    "prognosis. Excludes diagnosis using imaging "
                    "techniques (e.g. radiography, scintigraphy, and "
                    "ultrasonography) for which diagnostic imaging is "
                    "used.",
                },
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "scope"},
                "v": {
                    "type": "literal",
                    "value": "A syndrome characterized by persistent or recurrent "
                    "fatigue, diffuse musculoskeletal pain, sleep "
                    "disturbances, and subjective cognitive impairment "
                    "of 6 months duration or longer. Symptoms are not "
                    "caused by ongoing exertion; are not relieved by "
                    "rest; and result in a substantial reduction of "
                    "previous levels of occupational, educational, "
                    "social, or personal activities. Minor alterations "
                    "of immune, ne",
                },
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "scope"},
                "v": {
                    "type": "literal",
                    "value": "Post acute stage of COVID-19 virus infection "
                    "including signs, symptoms, and conditions that "
                    "continue or develop after acute COVID-19 infection. "
                    "Persistent symptoms may include FATIGUE; DYSPNEA; "
                    "and MEMORY LOSS.",
                },
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "note"},
                "v": {
                    "type": "literal",
                    "value": "A viral disorder characterized by high FEVER; "
                    "COUGH; DYSPNEA; CHILLS; PERSISTENT TREMOR with "
                    "chills, MUSCLE PAIN; HEADACHE; SORE THROAT; and new "
                    "loss of taste or smell (see AGEUSIA and ANOSMIA) "
                    "and other symptoms of a VIRAL PNEUMONIA. A "
                    "coronavirus SARS-CoV-2 in the genus BETACORONAVIRUS "
                    "is the suspected agent.",
                },
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000175"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "Y04"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C23.550.291.500.392"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C05.651.310"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C10.668.364"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C10.586.500.600"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C23.550.291.500.829.375"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C01.748.610.763.500.500"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C01.925.705.500.500"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C01.925.782.600.550.200.163.500"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C08.381.677.807.500.500"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "tree"},
                "v": {"type": "literal", "value": "C08.730.610.763.500.500"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Systemic Exertion Intolerance Disease"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Myalgic Encephalomyelitis"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Encephalomyelitis, Myalgic"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Chronic Fatigue Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Postviral Fatigue Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {
                    "type": "literal",
                    "value": "Infectious Mononucleosis-Like Syndrome, Chronic",
                },
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Royal Free Disease"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {
                    "type": "literal",
                    "value": "Chronic Fatigue and Immune Dysfunction Syndrome",
                },
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Chronic Fatigue Disorder"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Chronic Fatigue-Fibromyalgia Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] 2019 novel coronavirus infection"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] 2019-nCoV infection"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] coronavirus disease 2019"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] coronavirus disease-19"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] 2019-nCoV disease"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] 2019 novel coronavirus disease"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "COVID19"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] COVID-19 pandemic"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] COVID-19 virus infection"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] COVID-19 virus disease"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "[OBSOLETE] SARS-CoV-2 infection"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post Acute COVID-19 Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post-COVID Conditions"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post-Acute Sequelae of SARS-CoV-2 Infection"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Long COVID"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Long-Haul COVID"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Long Haul COVID-19"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post-Acute Sequelae of COVID-19"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "PASC Post Acute Sequelae of COVID-19"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post COVID-19 Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post-Acute COVID-19 Sequelae"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "term"},
                "v": {"type": "literal", "value": "Post-COVID-19 Syndrome"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000175"},
                "kind": {"type": "literal", "value": "active"},
                "v": {"type": "literal", "value": "true"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D015673"},
                "kind": {"type": "literal", "value": "active"},
                "v": {"type": "literal", "value": "true"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/C000657245"},
                "kind": {"type": "literal", "value": "active"},
                "v": {"type": "literal", "value": "false"},
            },
            {
                "d": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000094024"},
                "kind": {"type": "literal", "value": "active"},
                "v": {"type": "literal", "value": "true"},
            },
        ]
    },
}

SPARQL_RELATIONSHIPS = {
    "head": {"vars": ["kind", "r", "l"]},
    "results": {
        "bindings": [
            {
                "kind": {"type": "literal", "value": "broader"},
                "l": {"type": "literal", "value": "Signs and Symptoms"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D012816"},
            },
            {
                "kind": {"type": "literal", "value": "narrower"},
                "l": {"type": "literal", "value": "Mental Fatigue"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D005222"},
            },
            {
                "kind": {"type": "literal", "value": "narrower"},
                "l": {"type": "literal", "value": "Overtraining Syndrome"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000095027"},
            },
            {
                "kind": {"type": "literal", "value": "narrower"},
                "l": {"type": "literal", "value": "Emotional Exhaustion"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D000097815"},
            },
            {
                "kind": {"type": "literal", "value": "qualifier"},
                "l": {"type": "literal", "value": "diagnostic imaging"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000000981"},
            },
            {
                "kind": {"type": "literal", "value": "qualifier"},
                "l": {"type": "literal", "value": "blood"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000097"},
            },
            {
                "kind": {"type": "literal", "value": "qualifier"},
                "l": {"type": "literal", "value": "cerebrospinal fluid"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000134"},
            },
            {
                "kind": {"type": "literal", "value": "qualifier"},
                "l": {"type": "literal", "value": "chemically induced"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/Q000139"},
            },
            {
                "kind": {"type": "literal", "value": "see_also"},
                "l": {"type": "literal", "value": "Asthenia"},
                "r": {"type": "uri", "value": "http://id.nlm.nih.gov/mesh/D001247"},
            },
        ]
    },
}
