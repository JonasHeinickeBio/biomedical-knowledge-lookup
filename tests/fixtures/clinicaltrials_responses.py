"""Trimmed real ClinicalTrials.gov API v2 responses (captured 2026-10 from the live API)."""

# GET /studies/NCT07753122 (eligibility, contacts and outcomes trimmed away)
STUDY_ME_CFS_HYDROGEN = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT07753122",
            "briefTitle": "Controlled Trial of Hydrogen Water as a Treatment for Myalgic "
            "Encephalomyelitis/Chronic Fatigue Syndrome",
            "officialTitle": "Randomized Controlled Trial of Moderate Dose Hydrogen Water as a "
            "Treatment for ME/CFS",
            "acronym": "ME/CFS",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2026-08-15", "type": "ESTIMATED"},
            "completionDateStruct": {"date": "2027-07", "type": "ESTIMATED"},
            "lastUpdatePostDateStruct": {"date": "2026-08-07", "type": "ACTUAL"},
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Fred Friedberg", "class": "OTHER"}
        },
        "descriptionModule": {
            "briefSummary": "This is a 16-week controlled treatment trial of an over-the-counter "
            "supplement, hydrogen water, for individuals with ME/CFS patients."
        },
        "conditionsModule": {
            "conditions": ["Chronic Fatigue Syndrome (CFS)"],
            "keywords": ["chronic fatigue syndrome; ME/CFS; hydrogen water"],
        },
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["NA"],
            "enrollmentInfo": {"count": 80, "type": "ESTIMATED"},
        },
        "armsInterventionsModule": {
            "interventions": [
                {
                    "type": "DIETARY_SUPPLEMENT",
                    "name": "Placebo condition",
                    "description": "16 week intervention of magnesium pill without active "
                    "ingredient of molecular hydrogen.",
                    "armGroupLabels": ["Placebo condition"],
                },
                {
                    "type": "DIETARY_SUPPLEMENT",
                    "name": "Molecular hydrogen (magnesium tablet) 3x a day",
                    "armGroupLabels": ["Active hydrogen water intervention"],
                },
            ]
        },
    },
    "derivedSection": {
        "conditionBrowseModule": {
            "meshes": [{"id": "D015673", "term": "Fatigue Syndrome, Chronic"}]
        },
        "interventionBrowseModule": {"meshes": [{"id": "D006859", "term": "Hydrogen"}]},
    },
    "hasResults": False,
}

# Search entries (fields= restricted) for query.cond=long covid
STUDY_LONG_COVID_OBSERVATIONAL = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT07770022",
            "briefTitle": "Validation of Biomarkers for Long COVID in the LIINC Viral "
            "Immunopathogenesis and Persistence Repeat Donor Cohort (VIPER)",
            "officialTitle": "Validation of Biomarkers for Long COVID in the LIINC Viral "
            "Immunopathogenesis and Persistence Repeat Donor Cohort (VIPER)",
            "acronym": "VIPER",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2026-05-18"},
            "completionDateStruct": {"date": "2031-05-15"},
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "University of California, San Francisco"}
        },
        "conditionsModule": {"conditions": ["Long Covid"], "keywords": ["Long COVID"]},
        "designModule": {"studyType": "OBSERVATIONAL"},
        "armsInterventionsModule": {},
    },
    "derivedSection": {
        "conditionBrowseModule": {
            "meshes": [{"id": "D000094024", "term": "Post-Acute COVID-19 Syndrome"}]
        }
    },
    "hasResults": False,
}

STUDY_POST_COVID_DRUG = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT07298005",
            "briefTitle": "Sonlicromanol in Post-COVID",
            "acronym": "SON4PEM",
        },
        "statusModule": {"overallStatus": "RECRUITING"},
        "conditionsModule": {"conditions": ["Post COVID Condition"]},
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE2"],
            "enrollmentInfo": {"count": 80, "type": "ESTIMATED"},
        },
        "armsInterventionsModule": {
            "interventions": [
                {"type": "DRUG", "name": "Sonlicromanol", "description": "90mg twice daily"},
                {"type": "DRUG", "name": "Placebo"},
            ]
        },
    },
    "hasResults": False,
}

STUDY_EXPANDED_ACCESS = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT01111111", "briefTitle": "Compassionate use"},
        "designModule": {"studyType": "EXPANDED_ACCESS"},
    }
}

SEARCH_PAGE_1 = {
    "studies": [STUDY_LONG_COVID_OBSERVATIONAL, STUDY_POST_COVID_DRUG],
    "nextPageToken": "ZVNj7o2Elu8o3lpwSom5srbumpOQJJxqYvKm2_g",
}
SEARCH_PAGE_2 = {"studies": [STUDY_ME_CFS_HYDROGEN, STUDY_POST_COVID_DRUG]}
