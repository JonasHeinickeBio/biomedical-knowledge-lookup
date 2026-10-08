"""Trimmed real NIH RePORTER API v2 responses (recorded 2026-10-08).

Abstracts and term lists are shortened, and principal-investigator names are replaced by
placeholders (the live API publishes real names; the adapter keeps names only).
"""

SEARCH_MECFS = {
    "meta": {"total": 866, "offset": 0, "limit": 9},
    "results": [
        {
            "appl_id": 11232343,
            "fiscal_year": 2026,
            "project_num": "5R01NS131967-03",
            "organization": {
                "org_name": "UNIVERSITY OF ROCHESTER",
                "org_city": "ROCHESTER",
                "org_state": "NY",
                "org_country": "UNITED STATES",
                "dept_type": "BIOMEDICAL ENGINEERING",
                "primary_uei": "F27KDXZMF9Y8",
                "external_org_id": 7047101,
            },
            "activity_code": "R01",
            "award_amount": 451230,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 4", "is_contact_pi": True},
                {"full_name": "Test Investigator 5", "is_contact_pi": False},
            ],
            "agency_ic_admin": {
                "code": "NS",
                "abbreviation": "NINDS",
                "name": "National Institute of Neurological Disorders and Stroke",
                "admin_org_id": "12500053",
                "admin_funding_url": "",
            },
            "project_start_date": "2024-01-02T00:00:00",
            "project_end_date": "2028-11-30T00:00:00",
            "core_project_num": "R01NS131967",
            "abstract_text": "Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is "
            "a debilitating disease that affects approximately 1.5 million "
            "people in the U.S. Evidence exists for a genetic component to "
            "ME/CFS based on familiality studies performed by us and "
            "others, as well ...",
            "project_title": "Non-Invasive Multi-Modal Neuromonitoring in Adults Undergoing "
            "Extracorporeal Membrane Oxygenation",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11232343",
        },
        {
            "appl_id": 11501139,
            "fiscal_year": 2026,
            "project_num": "5U54AI178855-09",
            "organization": {
                "org_name": "CORNELL UNIVERSITY",
                "org_city": "ITHACA",
                "org_state": "NY",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "G56PUALJ3KT5",
                "external_org_id": 1514802,
            },
            "activity_code": "U54",
            "award_amount": 154859,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 6", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "AI",
                "abbreviation": "NIAID",
                "name": "National Institute of Allergy and Infectious Diseases",
                "admin_org_id": "12500003",
                "admin_funding_url": "",
            },
            "project_start_date": "2017-09-30T00:00:00",
            "project_end_date": "2028-03-31T00:00:00",
            "core_project_num": "U54AI178855",
            "abstract_text": "The primary objective of the Research Core is to provide "
            "access to high quality, state-of-the-art, efficient and "
            "cost-effective \n"
            "genomics technologies, as well as acting as a data integration "
            "hub for the Cornell ME/CFS Collaborative Research \n"
            "Center. ...",
            "project_title": "Research Core",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11501139",
        },
        {
            "appl_id": 11392371,
            "fiscal_year": 2026,
            "project_num": "5R01NS133905-04",
            "organization": {
                "org_name": "MASSACHUSETTS GENERAL HOSPITAL",
                "org_city": "BOSTON",
                "org_state": "MA",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "FLJ7DQKLL226",
                "external_org_id": 4907701,
            },
            "activity_code": "R01",
            "award_amount": 476515,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 7", "is_contact_pi": True},
                {"full_name": "Test Investigator 8", "is_contact_pi": False},
            ],
            "agency_ic_admin": {
                "code": "NS",
                "abbreviation": "NINDS",
                "name": "National Institute of Neurological Disorders and Stroke",
                "admin_org_id": "12500053",
                "admin_funding_url": "",
            },
            "project_start_date": "2023-09-01T00:00:00",
            "project_end_date": "2028-07-31T00:00:00",
            "core_project_num": "R01NS133905",
            "abstract_text": "ABSTRACT\n"
            "Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is "
            "a symptom-based diagnosis characterized\n"
            "by severe debilitating fatigue, cognitive dysfunction, and "
            "widespread pain. Most cases of ME/CFS begin with a\n"
            "viral infection or involve multiple ...",
            "project_title": "Mechanisms of Cognitive Control Impairment in ME/CFS and "
            "PASC-ME/CFS",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11392371",
        },
        {
            "appl_id": 11391125,
            "fiscal_year": 2026,
            "project_num": "5R01AI170850-05",
            "organization": {
                "org_name": "MASSACHUSETTS GENERAL HOSPITAL",
                "org_city": "BOSTON",
                "org_state": "MA",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "FLJ7DQKLL226",
                "external_org_id": 4907701,
            },
            "activity_code": "R01",
            "award_amount": 348246,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 9", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "AI",
                "abbreviation": "NIAID",
                "name": "National Institute of Allergy and Infectious Diseases",
                "admin_org_id": "12500003",
                "admin_funding_url": "",
            },
            "project_start_date": "2022-08-18T00:00:00",
            "project_end_date": "2027-07-31T00:00:00",
            "core_project_num": "R01AI170850",
            "abstract_text": "Abstract\n"
            "A hallmark of infection with SARS-CoV-2 is the unpredictable "
            "variation in individual health response from those\n"
            "who are asymptomatic to those with life-threatening and "
            "refractory respiratory illness, and finally those with long\n"
            "lasting symptoms, here ...",
            "project_title": "Long COVID as a putative subtype of chronic fatigue syndrome",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11391125",
        },
        {
            "appl_id": 11278151,
            "fiscal_year": 2026,
            "project_num": "1R01NS147100-01",
            "organization": {
                "org_name": "JOHNS HOPKINS UNIVERSITY",
                "org_city": "BALTIMORE",
                "org_state": "MD",
                "org_country": "UNITED STATES",
                "dept_type": "PEDIATRICS",
                "primary_uei": "FTMTDMBR29C7",
                "external_org_id": 4134401,
            },
            "activity_code": "R01",
            "award_amount": 633378,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 10", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "NS",
                "abbreviation": "NINDS",
                "name": "National Institute of Neurological Disorders and Stroke",
                "admin_org_id": "12500053",
                "admin_funding_url": "",
            },
            "project_start_date": "2026-04-16T00:00:00",
            "project_end_date": "2031-03-31T00:00:00",
            "core_project_num": "R01NS147100",
            "abstract_text": "PROJECT SUMMARY/ABSTRACT\n"
            "Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS), "
            "is a long-term disabling condition with a wide\n"
            "range of symptoms, often triggered by acute infection. The CDC "
            "estimates that in 2022, over 3.5 million\n"
            "Americans are living ...",
            "project_title": "Blood-Brain Barrier Integrity and Immune Dynamics in "
            "Neuropsychiatric Sequelae of Post-SARS-CoV-2 onset ME/CFS "
            "versus Pre-Pandemic ME/CFS Patients",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11278151",
        },
        {
            "appl_id": 11452057,
            "fiscal_year": 2026,
            "project_num": "1R21NS147200-01A1",
            "organization": {
                "org_name": "UNIVERSITY OF MICHIGAN AT ANN ARBOR",
                "org_city": "ANN ARBOR",
                "org_state": "MI",
                "org_country": "UNITED STATES",
                "dept_type": "MICROBIOLOGY/IMMUN/VIROLOGY",
                "primary_uei": "GNJ7BBP73WE9",
                "external_org_id": 1506502,
            },
            "activity_code": "R21",
            "award_amount": 429000,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 11", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "NS",
                "abbreviation": "NINDS",
                "name": "National Institute of Neurological Disorders and Stroke",
                "admin_org_id": "12500053",
                "admin_funding_url": "",
            },
            "project_start_date": "2026-09-11T00:00:00",
            "project_end_date": "2028-08-31T00:00:00",
            "core_project_num": "R21NS147200",
            "abstract_text": "Project Summary\n"
            "Nearly one in twelve American adults experiences persistent "
            "symptoms for at least one year following SARS-\n"
            "CoV-2 infection, defined as long COVID or post-acute sequelae "
            "of SARS-CoV-2 infection (PASC).\n"
            "Predominant symptoms—including fatigue and ...",
            "project_title": "Herpesvirus Reactivation as a Cause of Chronic Fatigue "
            "Following Coronavirus Infection",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11452057",
        },
    ],
}

PROJECTS_R01AI170850 = {
    "meta": {"total": 6, "offset": 0, "limit": 100},
    "results": [
        {
            "appl_id": 11391125,
            "fiscal_year": 2026,
            "project_num": "5R01AI170850-05",
            "organization": {
                "org_name": "MASSACHUSETTS GENERAL HOSPITAL",
                "org_city": "BOSTON",
                "org_state": "MA",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "FLJ7DQKLL226",
                "external_org_id": 4907701,
            },
            "activity_code": "R01",
            "award_amount": 348246,
            "is_active": True,
            "principal_investigators": [
                {"full_name": "Test Investigator 1", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "AI",
                "abbreviation": "NIAID",
                "name": "National Institute of Allergy and Infectious Diseases",
                "admin_org_id": "12500003",
                "admin_funding_url": "",
            },
            "agency_ic_fundings": [
                {
                    "fy": 2026,
                    "code": "AI",
                    "name": "National Institute of Allergy and Infectious Diseases",
                    "abbreviation": "NIAID",
                    "total_cost": 348246.0,
                    "direct_cost_ic": 207289.0,
                    "indirect_cost_ic": 140957.0,
                }
            ],
            "spending_categories": None,
            "project_start_date": "2022-08-18T00:00:00",
            "project_end_date": "2027-07-31T00:00:00",
            "core_project_num": "R01AI170850",
            "pref_terms": "2019-nCoV;Affect;Allergy;Autoimmune;Autoimmunity;Biological;COVID-19;COVID-19 "
            "impact",
            "abstract_text": "Abstract\n"
            "A hallmark of infection with SARS-CoV-2 is the unpredictable "
            "variation in individual health response from those\n"
            "who are asymptomatic to those with life-threatening and "
            "refractory respiratory illness, and finally those with long\n"
            "lasting symptoms, here ...",
            "project_title": "Long COVID as a putative subtype of chronic fatigue syndrome",
            "phr_text": "Narrative\n"
            "A subset of individuals with SARS-COVID-2 infection suffer from "
            "long term consequences (Long COVID). The\n"
            "core symptoms are remarkably similar to chronic fatigue syndrome "
            "(CFS) including debilitating fatigue and\n"
            "dysautonomia. The disease onset shows ...",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11391125",
        },
        {
            "appl_id": 11143218,
            "fiscal_year": 2025,
            "project_num": "5R01AI170850-04",
            "organization": {
                "org_name": "MASSACHUSETTS GENERAL HOSPITAL",
                "org_city": "BOSTON",
                "org_state": "MA",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "FLJ7DQKLL226",
                "external_org_id": 4907701,
            },
            "activity_code": "R01",
            "award_amount": 349946,
            "is_active": False,
            "principal_investigators": [
                {"full_name": "Test Investigator 2", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "AI",
                "abbreviation": "NIAID",
                "name": "National Institute of Allergy and Infectious Diseases",
                "admin_org_id": "12500003",
                "admin_funding_url": "",
            },
            "agency_ic_fundings": [
                {
                    "fy": 2025,
                    "code": "AI",
                    "name": "National Institute of Allergy and Infectious Diseases",
                    "abbreviation": "NIAID",
                    "total_cost": 349946.0,
                    "direct_cost_ic": 208301.0,
                    "indirect_cost_ic": 141645.0,
                }
            ],
            "spending_categories": [5680, 170, 176, 4835, 246, 276, 338, 5194, 701],
            "project_start_date": "2022-08-18T00:00:00",
            "project_end_date": "2027-07-31T00:00:00",
            "core_project_num": "R01AI170850",
            "pref_terms": "2019-nCoV;Affect;Allergy;Autoimmune;Autoimmunity;Biological;COVID-19;COVID-19 "
            "impact",
            "abstract_text": "Abstract\n"
            "A hallmark of infection with SARS-CoV-2 is the unpredictable "
            "variation in individual health response from those\n"
            "who are asymptomatic to those with life-threatening and "
            "refractory respiratory illness, and finally those with long\n"
            "lasting symptoms, here ...",
            "project_title": "Long COVID as a putative subtype of chronic fatigue syndrome",
            "phr_text": "Narrative\n"
            "A subset of individuals with SARS-COVID-2 infection suffer from "
            "long term consequences (Long COVID). The\n"
            "core symptoms are remarkably similar to chronic fatigue syndrome "
            "(CFS) including debilitating fatigue and\n"
            "dysautonomia. The disease onset shows ...",
            "spending_categories_desc": "Biodefense and Related Countermeasures; Chronic "
            "Fatigue Syndrome (ME/CFS); Clinical Research; "
            "Coronaviruses; Emerging Infectious Diseases; "
            "Genetics; Infectious Diseases; Post-Acute Sequelae "
            "of SARS-CoV-2 infection (PASC) including Long "
            "COVID; Prevention",
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11143218",
        },
        {
            "appl_id": 11381943,
            "fiscal_year": 2025,
            "project_num": "3R01AI170850-04S1",
            "organization": {
                "org_name": "MASSACHUSETTS GENERAL HOSPITAL",
                "org_city": "BOSTON",
                "org_state": "MA",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "FLJ7DQKLL226",
                "external_org_id": 4907701,
            },
            "activity_code": "R01",
            "award_amount": 412109,
            "is_active": False,
            "principal_investigators": [
                {"full_name": "Test Investigator 3", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "AI",
                "abbreviation": "NIAID",
                "name": "National Institute of Allergy and Infectious Diseases",
                "admin_org_id": "12500003",
                "admin_funding_url": "",
            },
            "agency_ic_fundings": [
                {
                    "fy": 2025,
                    "code": "AI",
                    "name": "National Institute of Allergy and Infectious Diseases",
                    "abbreviation": "NIAID",
                    "total_cost": 412109.0,
                    "direct_cost_ic": 249763.0,
                    "indirect_cost_ic": 162346.0,
                }
            ],
            "spending_categories": [5680, 170, 176, 4835, 246, 276, 338, 5194, 701],
            "project_start_date": "2022-08-18T00:00:00",
            "project_end_date": "2027-07-31T00:00:00",
            "core_project_num": "R01AI170850",
            "pref_terms": "2019-nCoV;Affect;Allergy;Autoimmune;Autoimmunity;Biological;COVID-19;COVID-19 "
            "impact",
            "abstract_text": "Abstract\n"
            "A hallmark of infection with SARS-CoV-2 is the unpredictable "
            "variation in individual health response from those\n"
            "who are asymptomatic to those with life-threatening and "
            "refractory respiratory illness, and finally those with long\n"
            "lasting symptoms, here ...",
            "project_title": "Long COVID as a putative subtype of chronic fatigue syndrome",
            "phr_text": "Narrative\n"
            "A subset of individuals with SARS-COVID-2 infection suffer from "
            "long term consequences (Long COVID). The\n"
            "core symptoms are remarkably similar to chronic fatigue syndrome "
            "(CFS) including debilitating fatigue and\n"
            "dysautonomia. The disease onset shows ...",
            "spending_categories_desc": "Biodefense and Related Countermeasures; Chronic "
            "Fatigue Syndrome (ME/CFS); Clinical Research; "
            "Coronaviruses; Emerging Infectious Diseases; "
            "Genetics; Infectious Diseases; Post-Acute Sequelae "
            "of SARS-CoV-2 infection (PASC) including Long "
            "COVID; Prevention",
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/11381943",
        },
    ],
}

PROJECT_BY_FULL_NUMBER = {
    "meta": {"total": 1, "offset": 0, "limit": 1},
    "results": [{"project_num": "5R01AI170850-05", "core_project_num": "R01AI170850"}],
}

PUBLICATIONS_R01AI170850 = {
    "meta": {"total": 12, "offset": 0, "limit": 100},
    "results": [
        {"coreproject": "R01AI170850", "pmid": 39962082, "applid": 11391125},
        {"coreproject": "R01AI170850", "pmid": 40399555, "applid": 11391125},
        {"coreproject": "R01AI170850", "pmid": 37982563, "applid": 11391125},
        {"coreproject": "R01AI170850", "pmid": 38413574, "applid": 11391125},
        {"coreproject": "R01AI170850", "pmid": 37301713, "applid": 11391125},
    ],
    "facet_results": [],
}

SEARCH_RECOVER_2023 = {
    "meta": {"total": 25, "offset": 0, "limit": 9},
    "results": [
        {
            "appl_id": 10745102,
            "fiscal_year": 2023,
            "project_num": "2UG3OD023305-08",
            "organization": {
                "org_name": "NEW YORK UNIVERSITY SCHOOL OF MEDICINE",
                "org_city": "NEW YORK",
                "org_state": "NY",
                "org_country": "UNITED STATES",
                "dept_type": "PEDIATRICS",
                "primary_uei": "M5SZJ6VHUHN8",
                "external_org_id": 5998304,
            },
            "activity_code": "UG3",
            "award_amount": 8599294,
            "is_active": False,
            "principal_investigators": [
                {"full_name": "Test Investigator 12", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "OD",
                "abbreviation": "OD",
                "name": "NIH Office of the Director",
                "admin_org_id": "12500055",
                "admin_funding_url": "",
            },
            "project_start_date": "2016-09-21T00:00:00",
            "project_end_date": "2025-05-31T00:00:00",
            "core_project_num": "UG3OD023305",
            "abstract_text": "PROJECT SUMMARY\n"
            "NYU Grossman School of Medicine (NYUGSOM) presents an "
            "application for: (1) ongoing enrollment of\n"
            "pregnancies, conceiving partners and their children from the "
            "NYU Children’s Health and Environment Study\n"
            "(NYU CHES, UG3/UH3OD023305) into the ...",
            "project_title": "The NYU Children’s Health & Environment Study: an ECHO Cohort",
            "spending_categories_desc": "Clinical Research; Coronaviruses; Coronaviruses "
            "Disparities and At-Risk Populations; Endocrine "
            "Disruptors; Health Disparities Research; Health "
            "Disparities and Racial or Ethnic Minority Health "
            "Research; Infertility; Pediatric; Pregnancy; "
            "Prevention",
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/10745102",
        },
        {
            "appl_id": 10677678,
            "fiscal_year": 2023,
            "project_num": "5U54GM104940-08",
            "organization": {
                "org_name": "LSU PENNINGTON BIOMEDICAL RESEARCH CTR",
                "org_city": "BATON ROUGE",
                "org_state": "LA",
                "org_country": "UNITED STATES",
                "dept_type": "NONE",
                "primary_uei": "MWYVQTQ32ME5",
                "external_org_id": 577909,
            },
            "activity_code": "U54",
            "award_amount": 4000000,
            "is_active": False,
            "principal_investigators": [
                {"full_name": "Test Investigator 13", "is_contact_pi": True}
            ],
            "agency_ic_admin": {
                "code": "GM",
                "abbreviation": "NIGMS",
                "name": "National Institute of General Medical Sciences",
                "admin_org_id": "12500024",
                "admin_funding_url": "",
            },
            "project_start_date": "2012-08-15T00:00:00",
            "project_end_date": "2027-06-30T00:00:00",
            "core_project_num": "U54GM104940",
            "abstract_text": "Project Summary: Overall\n"
            " The Louisiana Clinical and Translational Science (LA CaTS) "
            "Center is a consortium of the major academic\n"
            "and biomedical research centers in the State of Louisiana. "
            "Pennington Biomedical Research Center is the lead\n"
            "institution and will ...",
            "project_title": "Louisiana Clinical and Translational Science Center",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/10677678",
        },
        {
            "appl_id": 10675577,
            "fiscal_year": 2023,
            "project_num": "5U54GM115516-07",
            "organization": {
                "org_name": "MAINEHEALTH",
                "org_city": "PORTLAND",
                "org_state": "ME",
                "org_country": "UNITED STATES",
                "dept_type": None,
                "primary_uei": "MAYKB1LWD5U9",
                "external_org_id": 4757601,
            },
            "activity_code": "U54",
            "award_amount": 3999495,
            "is_active": False,
            "principal_investigators": [
                {"full_name": "Test Investigator 14", "is_contact_pi": True},
                {"full_name": "Test Investigator 15", "is_contact_pi": False},
            ],
            "agency_ic_admin": {
                "code": "GM",
                "abbreviation": "NIGMS",
                "name": "National Institute of General Medical Sciences",
                "admin_org_id": "12500024",
                "admin_funding_url": "",
            },
            "project_start_date": "2017-07-03T00:00:00",
            "project_end_date": "2027-06-30T00:00:00",
            "core_project_num": "U54GM115516",
            "abstract_text": "The long-term goal of the Northern New England Clinical and "
            "Translational Research Network (NNE-CTR),\n"
            "composed of MaineHealth, the University of Vermont, and the "
            "University of Southern Maine, is to sustain a\n"
            "clinical and translational research infrastructure ...",
            "project_title": "Northern New England Clinical and Translational Research Network",
            "spending_categories_desc": None,
            "covid_response": None,
            "project_detail_url": "https://reporter.nih.gov/project-details/10675577",
        },
    ],
}

EMPTY_RESULT = {"meta": {"total": 0, "offset": 0, "limit": 100}, "results": []}
