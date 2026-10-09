"""Trimmed real DOAJ v4 responses (fetched 2026-10-09) for the adapter tests."""

JOURNAL_PLOS = {
    "last_updated": "2026-09-17T10:51:00Z",
    "bibjson": {
        "editorial": {
            "review_process": ["Single anonymous peer review"],
            "review_url": "https://journals.plos.org/plosone/s/editorial-and-peer-review-process",
            "board_url": "https://journals.plos.org/plosone/static/editorial-board",
        },
        "pid_scheme": {"scheme": ["DOI"], "has_pid_scheme": True},
        "copyright": {
            "author_retains": True,
            "url": "https://journals.plos.org/plosone/s/licenses-and-copyright",
        },
        "keywords": [
            "science",
            "medicine",
            "engineering",
            "social sciences",
            "multidisciplinary sciences",
            "humanities",
        ],
        "plagiarism": {
            "detection": True,
            "url": "https://journals.plos.org/plosone/s/ethical-publishing-practice#loc-plagiarism",
        },
        "subject": [
            {"code": "R", "scheme": "LCC", "term": "Medicine"},
            {"code": "Q", "scheme": "LCC", "term": "Science"},
        ],
        "eissn": "1932-6203",
        "language": ["EN"],
        "title": "PLoS ONE",
        "article": {
            "license_display_example_url": "https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0146294",
            "license_display": ["Embed"],
        },
        "preservation": {
            "has_preservation": True,
            "service": ["CLOCKSS", "PMC"],
            "url": "https://portal.issn.org/resource/ISSN/1932-6203",
        },
        "license": [
            {
                "NC": False,
                "ND": False,
                "BY": True,
                "type": "CC BY",
                "SA": False,
                "url": "https://creativecommons.org/licenses/by/4.0/",
            }
        ],
        "ref": {
            "aims_scope": "https://journals.plos.org/plosone/s/journal-information",
            "journal": "https://journals.plos.org/plosone/",
            "oa_statement": "https://journals.plos.org/plosone/s/journal-information#loc-open-access",
            "author_instructions": "https://journals.plos.org/plosone/s/submission-guidelines",
            "license_terms": "https://journals.plos.org/plosone/s/licenses-and-copyright",
        },
        "oa_start": 2006,
        "alternative_title": "PLOS ONE",
        "apc": {
            "has_apc": True,
            "max": [{"price": 2477, "currency": "USD"}],
            "url": "https://plos.org/publish/fees/",
        },
        "other_charges": {"has_other_charges": False},
        "publication_time_weeks": 29,
        "deposit_policy": {
            "service": ["Open Policy Finder"],
            "url": "https://openpolicyfinder.jisc.ac.uk/id/publication/17599",
            "has_policy": True,
        },
        "publisher": {"country": "US", "name": "Public Library of Science (PLoS)"},
        "boai": True,
        "waiver": {"has_waiver": True, "url": "https://www.plos.org/fee-assistance"},
    },
    "admin": {"ticked": True},
    "id": "2fdf1470373343b7bd4f825179c685f5",
    "created_date": "2007-03-30T10:53:19Z",
}


JOURNAL_KARDIO = {
    "id": "7a59a028e6e14bf6843e91808c62fb96",
    "created_date": "2016-01-20T10:37:32Z",
    "last_updated": "2026-09-17T10:52:41Z",
    "last_manual_update": "2026-04-28T23:15:06Z",
    "es_type": "journal",
    "bibjson": {
        "alternative_title": "Kardiochirurgia i Torakochirurgia Polska",
        "boai": True,
        "eissn": "1897-4252",
        "pissn": "1731-5530",
        "publication_time_weeks": 16,
        "title": "Polish Journal of Thoracic and Cardiovascular Surgery",
        "oa_start": 2006,
        "apc": {
            "has_apc": False,
            "url": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/Publication-charge",
        },
        "article": {
            "license_display_example_url": "https://www.termedia.pl/The-impact-of-modular-cardiac-rehabilitation-on-quality-of-life-and-exercise-tolerance-in-patients-with-myocardial-infarction-and-COVID-19-infection,40,48513,1,1.html",
            "license_display": ["Embed"],
        },
        "copyright": {
            "author_retains": False,
            "url": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/Info",
        },
        "deposit_policy": {
            "has_policy": True,
            "url": "https://openpolicyfinder.jisc.ac.uk/publication/32742",
            "service": ["Open Policy Finder"],
        },
        "editorial": {
            "review_url": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/For-authors",
            "board_url": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/Board",
            "review_process": ["Double anonymous peer review"],
        },
        "institution": {"name": "Polish Society of Cardiothoracic Surgeons", "country": "PL"},
        "other_charges": {"has_other_charges": False},
        "pid_scheme": {"has_pid_scheme": True, "scheme": ["DOI"]},
        "plagiarism": {
            "detection": True,
            "url": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/Ethical-standards",
        },
        "preservation": {
            "has_preservation": True,
            "url": "https://pubmed.ncbi.nlm.nih.gov/?term=1897-4252",
            "service": ["PMC"],
        },
        "publisher": {"name": "Termedia Publishing House", "country": "PL"},
        "ref": {
            "oa_statement": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/Info",
            "journal": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40",
            "aims_scope": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/For-authors",
            "author_instructions": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/For-authors",
            "license_terms": "https://www.termedia.pl/Journal/Kardiochirurgia_i_Torakochirurgia_Polska-40/Info",
        },
        "waiver": {"has_waiver": False},
        "keywords": ["thoracic", "cardiovascular", "cardiology", "surgery"],
        "language": ["EN"],
        "license": [
            {
                "type": "CC BY-NC-SA",
                "BY": True,
                "NC": True,
                "ND": False,
                "SA": True,
                "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            }
        ],
        "subject": [
            {"code": "RD1-811", "scheme": "LCC", "term": "Surgery"},
            {"code": "RC31-1245", "scheme": "LCC", "term": "Internal medicine"},
        ],
    },
    "admin": {"in_doaj": True, "ticked": True},
}


ARTICLE_PLOS = {
    "last_updated": "2025-08-20T03:24:44Z",
    "bibjson": {
        "identifier": [
            {"id": "1932-6203", "type": "eissn"},
            {"id": "10.1371/journal.pone.0326790", "type": "doi"},
        ],
        "journal": {
            "volume": "20",
            "number": "6",
            "country": "US",
            "issns": ["1932-6203"],
            "publisher": "Public Library of Science (PLoS)",
            "language": ["EN"],
            "title": "PLoS ONE",
        },
        "month": "0",
        "year": "2025",
        "start_page": "e0326790",
        "subject": [
            {"code": "R", "scheme": "LCC", "term": "Medicine"},
            {"code": "Q", "scheme": "LCC", "term": "Science"},
        ],
        "author": [{"name": "Gregory Vallée"}, {"name": "David Xi"}],
        "link": [{"type": "fulltext", "url": "https://doi.org/10.1371/journal.pone.0326790"}],
        "abstract": "This is a 3.5-year single-center observational cohort study "
        "investigating the longitudinal impact of Long Covid on the physical "
        "and mental health of patients. Patients were assessed at 3 months, 1 "
        "year, and 3.5-years post-infection using the 12-item Short Form "
        "Survey, Patient Health Questionnaire-9,",
        "title": "Evaluating the longitudinal physical and psychological health effects "
        "of persistent long Covid 3.5 years after infection.",
    },
    "id": "b6810d1e6072415f92f9ef25cdb67524",
    "created_date": "2025-06-27T05:31:39Z",
}


JOURNAL_SEARCH = {
    "total": 1,
    "page": 1,
    "pageSize": 10,
    "timestamp": "2026-10-09T06:09:56.404508Z",
    "query": "PLoS ONE",
    "results": [
        {
            "last_updated": "2026-09-17T10:51:00Z",
            "bibjson": {
                "editorial": {
                    "review_process": ["Single anonymous peer review"],
                    "review_url": "https://journals.plos.org/plosone/s/editorial-and-peer-review-process",
                    "board_url": "https://journals.plos.org/plosone/static/editorial-board",
                },
                "pid_scheme": {"scheme": ["DOI"], "has_pid_scheme": True},
                "copyright": {
                    "author_retains": True,
                    "url": "https://journals.plos.org/plosone/s/licenses-and-copyright",
                },
                "keywords": [
                    "science",
                    "medicine",
                    "engineering",
                    "social sciences",
                    "multidisciplinary sciences",
                    "humanities",
                ],
                "plagiarism": {
                    "detection": True,
                    "url": "https://journals.plos.org/plosone/s/ethical-publishing-practice#loc-plagiarism",
                },
                "subject": [
                    {"code": "R", "scheme": "LCC", "term": "Medicine"},
                    {"code": "Q", "scheme": "LCC", "term": "Science"},
                ],
                "eissn": "1932-6203",
                "language": ["EN"],
                "title": "PLoS ONE",
                "article": {
                    "license_display_example_url": "https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0146294",
                    "license_display": ["Embed"],
                },
                "preservation": {
                    "has_preservation": True,
                    "service": ["CLOCKSS", "PMC"],
                    "url": "https://portal.issn.org/resource/ISSN/1932-6203",
                },
                "license": [
                    {
                        "NC": False,
                        "ND": False,
                        "BY": True,
                        "type": "CC BY",
                        "SA": False,
                        "url": "https://creativecommons.org/licenses/by/4.0/",
                    }
                ],
                "ref": {
                    "aims_scope": "https://journals.plos.org/plosone/s/journal-information",
                    "journal": "https://journals.plos.org/plosone/",
                    "oa_statement": "https://journals.plos.org/plosone/s/journal-information#loc-open-access",
                    "author_instructions": "https://journals.plos.org/plosone/s/submission-guidelines",
                    "license_terms": "https://journals.plos.org/plosone/s/licenses-and-copyright",
                },
                "oa_start": 2006,
                "alternative_title": "PLOS ONE",
                "apc": {
                    "has_apc": True,
                    "max": [{"price": 2477, "currency": "USD"}],
                    "url": "https://plos.org/publish/fees/",
                },
                "other_charges": {"has_other_charges": False},
                "publication_time_weeks": 29,
                "deposit_policy": {
                    "service": ["Open Policy Finder"],
                    "url": "https://openpolicyfinder.jisc.ac.uk/id/publication/17599",
                    "has_policy": True,
                },
                "publisher": {"country": "US", "name": "Public Library of Science (PLoS)"},
                "boai": True,
                "waiver": {"has_waiver": True, "url": "https://www.plos.org/fee-assistance"},
            },
            "admin": {"ticked": True},
            "id": "2fdf1470373343b7bd4f825179c685f5",
            "created_date": "2007-03-30T10:53:19Z",
        }
    ],
}


ARTICLE_SEARCH = {
    "total": 22601,
    "page": 1,
    "pageSize": 10,
    "timestamp": "2026-10-09T06:09:11.061888Z",
    "query": "long covid",
    "results": [
        {
            "last_updated": "2025-08-20T03:24:44Z",
            "bibjson": {
                "identifier": [
                    {"id": "1932-6203", "type": "eissn"},
                    {"id": "10.1371/journal.pone.0326790", "type": "doi"},
                ],
                "journal": {
                    "volume": "20",
                    "number": "6",
                    "country": "US",
                    "issns": ["1932-6203"],
                    "publisher": "Public Library of Science (PLoS)",
                    "language": ["EN"],
                    "title": "PLoS ONE",
                },
                "month": "0",
                "year": "2025",
                "start_page": "e0326790",
                "subject": [
                    {"code": "R", "scheme": "LCC", "term": "Medicine"},
                    {"code": "Q", "scheme": "LCC", "term": "Science"},
                ],
                "author": [{"name": "Gregory Vallée"}, {"name": "David Xi"}],
                "link": [
                    {"type": "fulltext", "url": "https://doi.org/10.1371/journal.pone.0326790"}
                ],
                "abstract": "This is a 3.5-year single-center observational cohort "
                "study investigating the longitudinal impact of Long "
                "Covid on the physical and mental health of patients. "
                "Patients were assessed at 3 months, 1 year, and "
                "3.5-years post-infection using the 12-item Short Form "
                "Survey, Patient Health Questionnaire-9,",
                "title": "Evaluating the longitudinal physical and psychological "
                "health effects of persistent long Covid 3.5 years after "
                "infection.",
            },
            "id": "b6810d1e6072415f92f9ef25cdb67524",
            "created_date": "2025-06-27T05:31:39Z",
        }
    ],
}


EMPTY_SEARCH = {
    "total": 0,
    "page": 1,
    "pageSize": 10,
    "timestamp": "2026-10-09T06:09:10.799800Z",
    "query": "chronic fatigue",
    "results": [],
}
