"""Trimmed real Crossref REST API responses (recorded live; see docs/adapters/literature)."""

WAKEFIELD_WORK = {
    "status": "ok",
    "message-type": "work",
    "message": {
        "DOI": "10.1016/s0140-6736(97)11096-0",
        "title": [
            "RETRACTED: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, "
            "and pervasive developmental disorder in children"
        ],
        "container-title": ["The Lancet"],
        "issued": {"date-parts": [[1998, 2]]},
        "published": {"date-parts": [[1998, 2]]},
        "author": [
            {
                "given": "AJ",
                "family": "Wakefield",
                "sequence": "first",
                "affiliation": [],
                "role": [{"vocabulary": "crossref", "role": "author"}],
            },
            {
                "given": "SH",
                "family": "Murch",
                "sequence": "additional",
                "affiliation": [],
                "role": [{"vocabulary": "crossref", "role": "author"}],
            },
            {
                "given": "A",
                "family": "Anthony",
                "sequence": "additional",
                "affiliation": [],
                "role": [{"vocabulary": "crossref", "role": "author"}],
            },
        ],
        "type": "journal-article",
        "publisher": "Elsevier BV",
        "is-referenced-by-count": 2035,
        "references-count": 26,
        "ISSN": ["0140-6736"],
        "issn-type": [{"value": "0140-6736", "type": "print"}],
        "volume": "351",
        "issue": "9103",
        "page": "637-641",
        "language": "en",
        "relation": {},
        "updated-by": [
            {
                "DOI": "10.1016/s0140-6736(04)15715-2",
                "type": "correction",
                "label": "Correction",
                "source": "retraction-watch",
                "updated": {
                    "date-parts": [[2004, 3, 6]],
                    "date-time": "2004-03-06T00:00:00Z",
                    "timestamp": 1078531200000,
                },
                "record-id": "17269",
            },
            {
                "DOI": "10.1016/s0140-6736(10)60175-4",
                "type": "retraction",
                "label": "Retraction",
                "source": "retraction-watch",
                "updated": {
                    "date-parts": [[2010, 2, 6]],
                    "date-time": "2010-02-06T00:00:00Z",
                    "timestamp": 1265414400000,
                },
                "record-id": "4036",
            },
        ],
        "license": [
            {
                "start": {
                    "date-parts": [[1998, 2, 1]],
                    "date-time": "1998-02-01T00:00:00Z",
                    "timestamp": 886291200000,
                },
                "content-version": "tdm",
                "delay-in-days": 0,
                "URL": "https://www.elsevier.com/tdm/userlicense/1.0/",
            }
        ],
        "subtitle": [],
        "reference": [
            {
                "key": "10.1016/S0140-6736(97)11096-0_bib1",
                "series-title": "Diagnostic and Statistical Manual of Mental Disorders (DSM-IV)",
                "year": "1994",
            },
            {
                "key": "10.1016/S0140-6736(97)11096-0_bib2",
                "doi-asserted-by": "crossref",
                "first-page": "311",
                "DOI": "10.1016/0009-8981(82)90018-3",
                "article-title": "A sensitive micromethod for the routine "
                "estimations of methylmalonic acid in body fluids "
                "and tissues using thin-layer chromatography.",
                "volume": "118",
                "author": "Bhatt",
                "year": "1982",
                "journal-title": "Clin Chem Acta",
            },
            {
                "key": "10.1016/S0140-6736(97)11096-0_bib4",
                "first-page": "146",
                "article-title": "Die Psychopathologie des coeliakakranken kindes.",
                "volume": "197",
                "author": "Asperger",
                "year": "1961",
                "journal-title": "Ann Paediatr",
            },
        ],
    },
}

NATURE_WORK = {
    "status": "ok",
    "message-type": "work",
    "message": {
        "DOI": "10.1038/s41586-020-2012-7",
        "title": ["A pneumonia outbreak associated with a new coronavirus of probable bat origin"],
        "container-title": ["Nature"],
        "issued": {"date-parts": [[2020, 2, 3]]},
        "published": {"date-parts": [[2020, 2, 3]]},
        "author": [
            {
                "given": "Peng",
                "family": "Zhou",
                "sequence": "first",
                "affiliation": [],
                "role": [{"vocabulary": "crossref", "role": "author"}],
            },
            {
                "given": "Xing-Lou",
                "family": "Yang",
                "sequence": "additional",
                "affiliation": [],
                "role": [{"vocabulary": "crossref", "role": "author"}],
            },
        ],
        "type": "journal-article",
        "publisher": "Springer Science and Business Media LLC",
        "is-referenced-by-count": 17529,
        "references-count": 16,
        "ISSN": ["0028-0836", "1476-4687"],
        "issn-type": [
            {"value": "0028-0836", "type": "print"},
            {"value": "1476-4687", "type": "electronic"},
        ],
        "volume": "579",
        "issue": "7798",
        "page": "270-273",
        "language": "en",
        "relation": {
            "has-preprint": [
                {"id-type": "doi", "id": "10.1101/2020.01.22.914952", "asserted-by": "object"}
            ],
            "has-review": [
                {
                    "id-type": "doi",
                    "id": "10.14293/S2199-1006.1.SOR-UNCAT.ATFIGJ.v1.RPNIMV",
                    "asserted-by": "object",
                },
                {"id-type": "doi", "id": "10.3410/f.737304963.793571621", "asserted-by": "object"},
            ],
        },
        "updated-by": [
            {
                "DOI": "10.1038/s41586-020-2951-z",
                "type": "addendum",
                "label": "Addendum",
                "source": "publisher",
                "updated": {
                    "date-parts": [[2020, 11, 17]],
                    "date-time": "2020-11-17T00:00:00Z",
                    "timestamp": 1605571200000,
                },
            }
        ],
        "license": [
            {
                "start": {
                    "date-parts": [[2020, 2, 3]],
                    "date-time": "2020-02-03T00:00:00Z",
                    "timestamp": 1580688000000,
                },
                "content-version": "tdm",
                "delay-in-days": 0,
                "URL": "https://creativecommons.org/licenses/by/4.0",
            },
            {
                "start": {
                    "date-parts": [[2020, 2, 3]],
                    "date-time": "2020-02-03T00:00:00Z",
                    "timestamp": 1580688000000,
                },
                "content-version": "vor",
                "delay-in-days": 0,
                "URL": "https://creativecommons.org/licenses/by/4.0",
            },
        ],
        "subtitle": [],
        "abstract": "<jats:title>Abstract</jats:title>\n"
        "                  <jats:p>\n"
        "                    Since the outbreak of severe acute respiratory "
        "syndrome (SARS) 18\xa0years ago, a large number of SARS-related "
        "coronaviruses (SARSr-CoVs).",
        "alternative-id": ["2012"],
        "reference": [
            {
                "key": "2012_CR1",
                "doi-asserted-by": "crossref",
                "first-page": "676",
                "DOI": "10.1126/science.1118391",
                "volume": "310",
                "author": "W Li",
                "year": "2005",
                "unstructured": "Li, W. et al. Bats are natural reservoirs of "
                "SARS-like coronaviruses. Science 310, 676–679 "
                "(2005).",
                "journal-title": "Science",
            },
            {
                "key": "2012_CR2",
                "doi-asserted-by": "crossref",
                "first-page": "535",
                "DOI": "10.1038/nature12711",
                "volume": "503",
                "author": "X-Y Ge",
                "year": "2013",
                "unstructured": "Ge, X.-Y. et al. Isolation and characterization "
                "of a bat SARS-like coronavirus that uses the ACE2 "
                "receptor. Nature 503, 535–538 (2013).",
                "journal-title": "Nature",
            },
            {
                "key": "2012_CR3",
                "first-page": "989",
                "volume": "19",
                "author": "L Yang",
                "year": "2013",
                "unstructured": "Yang, L. et al. Novel SARS-like betacoronaviruses "
                "in bats, China, 2011. Emerg. Infect. Dis. 19, "
                "989–991 (2013).",
                "journal-title": "Emerg. Infect. Dis.",
            },
        ],
    },
}

RETRACTION_NOTICE = {
    "status": "ok",
    "message-type": "work",
    "message": {
        "DOI": "10.1016/s0140-6736(10)60175-4",
        "title": [
            "Retraction—Ileal-lymphoid-nodular hyperplasia, non-specific colitis, "
            "and pervasive developmental disorder in children"
        ],
        "type": "journal-article",
        "issued": {"date-parts": [[2010, 2]]},
        "container-title": ["The Lancet"],
        "publisher": "Elsevier BV",
        "update-to": [
            {
                "DOI": "10.1016/s0140-6736(97)11096-0",
                "type": "retraction",
                "label": "Retraction",
                "source": "retraction-watch",
                "updated": {
                    "date-parts": [[2010, 2, 6]],
                    "date-time": "2010-02-06T00:00:00Z",
                    "timestamp": 1265414400000,
                },
                "record-id": "4036",
            }
        ],
        "ISSN": ["0140-6736"],
    },
}

SEARCH_RESPONSE = {
    "status": "ok",
    "message-type": "work-list",
    "message": {
        "facets": {},
        "total-results": 2340354,
        "items": [
            {
                "publisher": "Exon Publications",
                "abstract": "<jats:p>Long COVID, also known as post-acute sequelae of "
                "SARS-CoV-2 infection (PASC), is a condition where "
                "individuals experience persistent symptoms and health "
                "issues long after the acute phase of COVID-19. This "
                "article aims to provide an overview of long COVID, "
                "covering who is at risk, its</jats:p>",
                "DOI": "10.36255/long-covid-public-education",
                "type": "book-chapter",
                "is-referenced-by-count": 0,
                "title": ["Long COVID: Public Education"],
                "container-title": ["Long COVID"],
                "score": 17.926765,
                "issued": {"date-parts": [[2024, 7, 7]]},
                "references-count": 0,
            },
            {
                "publisher": "Wiley",
                "DOI": "10.1002/9781119891338.ch1",
                "type": "other",
                "is-referenced-by-count": 0,
                "title": ["Long‐COVID Disease or Long‐COVID Syndrome?"],
                "container-title": ["Unravelling Long COVID"],
                "score": 17.64752,
                "issued": {"date-parts": [[2022, 11, 18]]},
                "references-count": 35,
            },
        ],
        "items-per-page": 3,
        "query": {"start-index": 0, "search-terms": "long covid"},
    },
}

AGENCY_RESPONSE = {
    "status": "ok",
    "message-type": "work-agency",
    "message-version": "1.0.0",
    "message": {
        "DOI": "10.1016/s0140-6736(97)11096-0",
        "agency": {"id": "crossref", "label": "Crossref"},
    },
}
