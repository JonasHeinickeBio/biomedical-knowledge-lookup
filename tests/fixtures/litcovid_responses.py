"""Trimmed real LitCovid responses (fetched 2026-10-07, see docs page)."""

SEARCH_LONG_COVID = {
    "results": [
        {
            "pmid": 34316076,
            "title": "Long COVID.",
            "journal": "Nat Immunol",
            "authors": ["Visan, Ioana"],
            "date": "2021-07-29T12:00:00Z",
            "_id": "34316076",
            "meta_date_publication": "2021 Aug",
            "meta_volume": "22",
            "meta_issue": "8",
            "meta_pages": "934-935",
            "e_condition": ["LongCovid"],
            "text_hl": "<m>Long COVID</m>.",
            "citations": {
                "NLM": "Visan, Ioana. Long COVID. Nat Immunol. 2021 "
                "Aug;22(8):934-935. PMID: 34316076"
            },
        },
        {
            "pmid": 35474919,
            "pmcid": "PMC9023042",
            "title": "[Long COVID?].",
            "journal": "Monatsschr Kinderheilkd",
            "authors": ["Kerbl, Reinhold"],
            "date": "2022-04-28T12:00:00Z",
            "_id": "35474919",
            "meta_date_publication": "2022",
            "meta_volume": "170",
            "meta_issue": "6",
            "meta_pages": "490-492",
            "e_condition": ["LongCovid"],
            "text_hl": "[<m>Long COVID</m>?].",
            "citations": {
                "NLM": "Kerbl, Reinhold. [Long COVID?]. Monatsschr Kinderheilkd. "
                "2022;170(6):490-492. PMID: 35474919"
            },
        },
        {
            "pmid": 36972723,
            "pmcid": "PMC10038666",
            "title": "Long COVID? What is that?",
            "journal": "Lancet Respir Med",
            "authors": ["Morgan, Jules"],
            "date": "2023-03-28T12:00:00Z",
            "_id": "36972723",
            "meta_date_publication": "2023 Jun",
            "meta_volume": "11",
            "meta_issue": "6",
            "meta_pages": "515-517",
            "e_condition": ["LongCovid"],
            "text_hl": "<m>Long COVID</m>? What is that?",
            "citations": {
                "NLM": "Morgan, Jules. Long COVID? What is that? Lancet Respir "
                "Med. 2023 Jun;11(6):515-517. PMID: 36972723"
            },
        },
    ],
    "facets": {
        "facet_fields": {
            "journal": [
                {"name": "J Clin Med", "type": "int", "value": 172},
                {"name": "PLoS One", "type": "int", "value": 151},
                {"name": "Sci Rep", "type": "int", "value": 148},
            ],
            "countries": [
                {"name": "United States", "type": "int", "value": 467},
                {"name": "United Kingdom", "type": "int", "value": 348},
                {"name": "China", "type": "int", "value": 231},
            ],
            "e_drugs": [
                {
                    "name": "nirmatrelvir and ritonavir drug combination",
                    "type": "int",
                    "value": 52,
                },
                {"name": "Carbon Monoxide", "type": "int", "value": 42},
                {"name": "Glucose", "type": "int", "value": 38},
            ],
            "e_strains": [
                {"name": "Omicron", "type": "int", "value": 191},
                {"name": "Delta", "type": "int", "value": 74},
                {"name": "Alpha", "type": "int", "value": 35},
            ],
        }
    },
    "page_size": 10,
    "current": 1,
    "count": 8030,
    "total_pages": 803,
    "phid": None,
}

SEARCH_LONG_COVID_PAGE2 = {
    "results": [
        {
            "pmid": 34820152,
            "pmcid": "PMC8606968",
            "title": "Addressing the Long COVID Crisis: Integrative Health and Long COVID.",
            "journal": "Glob Adv Health Med",
            "authors": ["Roth, Alan", "Chan, Pan San"],
            "date": "2021-11-26T12:00:00Z",
            "_id": "34820152",
            "meta_date_publication": "2021",
            "meta_volume": "10",
            "meta_pages": "21649561211056597",
            "countries": ["United States"],
            "e_condition": ["LongCovid"],
            "topics": ["Prevention"],
            "text_hl": "Addressing the <m>Long COVID</m> Crisis: Integrative Health and "
            "<m>Long COVID</m>.",
            "citations": {
                "NLM": "Roth, Alan, Chan, Pan San, Jonas, Wayne. Addressing the "
                "Long COVID Crisis: Integrative Health and Long COVID. Glob "
                "Adv Health Med. 2021;10:21649561211056597. PMID: "
                "34820152"
            },
        },
        {
            "pmid": 34428463,
            "pmcid": "PMC8379817",
            "title": "The Long COVID Conundrum.",
            "journal": "Am J Med",
            "authors": ["Gaffney, Adam W"],
            "date": "2021-08-25T12:00:00Z",
            "_id": "34428463",
            "meta_date_publication": "2022 Jan",
            "meta_volume": "135",
            "meta_issue": "1",
            "meta_pages": "5-6",
            "e_condition": ["LongCovid"],
            "text_hl": "The <m>Long COVID</m> Conundrum.",
            "citations": {
                "NLM": "Gaffney, Adam W. The Long COVID Conundrum. Am J Med. 2022 "
                "Jan;135(1):5-6. PMID: 34428463"
            },
        },
    ],
    "facets": {
        "facet_fields": {
            "journal": [
                {"name": "J Clin Med", "type": "int", "value": 172},
                {"name": "PLoS One", "type": "int", "value": 151},
                {"name": "Sci Rep", "type": "int", "value": 148},
            ],
            "countries": [
                {"name": "United States", "type": "int", "value": 467},
                {"name": "United Kingdom", "type": "int", "value": 348},
                {"name": "China", "type": "int", "value": 231},
            ],
            "e_drugs": [
                {
                    "name": "nirmatrelvir and ritonavir drug combination",
                    "type": "int",
                    "value": 52,
                },
                {"name": "Carbon Monoxide", "type": "int", "value": 42},
                {"name": "Glucose", "type": "int", "value": 38},
            ],
            "e_strains": [
                {"name": "Omicron", "type": "int", "value": 191},
                {"name": "Delta", "type": "int", "value": 74},
                {"name": "Alpha", "type": "int", "value": 35},
            ],
        }
    },
    "page_size": 10,
    "current": 2,
    "count": 8030,
    "total_pages": 803,
    "phid": None,
}

SINGLE_ARTICLE_WITH_DRUGS = {
    "results": [
        {
            "pmid": 39472619,
            "pmcid": "PMC11522512",
            "title": "Nirmatrelvir plus ritonavir reduces COVID-19 hospitalization and "
            "prevents long COVID in adult outpatients.",
            "journal": "Sci Rep",
            "authors": [
                "Saheb Sharif-Askari, Fatemeh",
                "Ali Hussain Alsayed, Hawra",
                "Saheb Sharif-Askari, Narjes",
                "Al Sayed Hussain, Ali",
                "Al-Muhsen, Saleh",
                "Halwani, Rabih",
            ],
            "date": "2024-10-30T12:00:00Z",
            "_id": "39472619",
            "meta_date_publication": "2024 Oct 29",
            "meta_volume": "14",
            "meta_issue": "1",
            "meta_pages": "25901",
            "countries": ["United Arab Emirates", "Guatemala"],
            "e_strains": ["Omicron"],
            "e_condition": ["LongCovid"],
            "topics": ["Treatment"],
            "text_hl": None,
            "citations": {
                "NLM": "Saheb Sharif-Askari, Fatemeh, Ali Hussain Alsayed, Hawra, "
                "Saheb Sharif-Askari, Narjes, Al Sayed Hussain, Ali, "
                "Al-Muhsen, Saleh, Halwani, Rabih. Nirmatrelvir plus "
                "ritonavir reduces COVID-19 hospitalization and prevents "
                "long COVID in adult outpatients. Sci Rep. 2024 Oct "
                "29;14(1):25901. PMID: 39472619"
            },
        }
    ],
    "facets": {
        "facet_fields": {
            "journal": [{"name": "Sci Rep", "type": "int", "value": 1}],
            "countries": [
                {"name": "Guatemala", "type": "int", "value": 1},
                {"name": "United Arab Emirates", "type": "int", "value": 1},
            ],
            "e_drugs": [
                {"name": "Ritonavir", "type": "int", "value": 1},
                {"name": "nirmatrelvir and ritonavir drug combination", "type": "int", "value": 1},
            ],
            "e_strains": [{"name": "Omicron", "type": "int", "value": 1}],
        }
    },
    "page_size": 10,
    "current": 1,
    "count": 1,
    "total_pages": 1,
    "phid": None,
}

SINGLE_ARTICLE_WITH_VARIANTS = {
    "results": [
        {
            "pmid": 35330457,
            "pmcid": "PMC8955736",
            "title": "GSTO1, GSTO2 and ACE2 Polymorphisms Modify Susceptibility to "
            "Developing COVID-19.",
            "journal": "J Pers Med",
            "authors": [
                "Djukic, Tatjana",
                "Stevanovic, Goran",
                "Coric, Vesna",
                "Bukumiric, Zoran",
                "Pljesa-Ercegovac, Marija",
                "Matic, Marija",
                "Jerotic, Djurdja",
                "Todorovic, Nevena",
                "Asanin, Milika",
                "Ercegovac, Marko",
                "Ranin, Jovan",
                "Milosevic, Ivana",
                "Savic-Radojevic, Ana",
                "Simic, Tatjana",
            ],
            "date": "2022-03-26T12:00:00Z",
            "_id": "35330457",
            "meta_date_publication": "2022 Mar 14",
            "meta_volume": "12",
            "meta_issue": "3",
            "e_variants": ["rs4646116", "rs4925", "rs156697"],
            "topics": ["Mechanism", "Treatment"],
            "text_hl": None,
            "citations": {
                "NLM": "Djukic, Tatjana, Stevanovic, Goran, Coric, Vesna, "
                "Bukumiric, Zoran, Pljesa-Ercegovac, Marija, Matic, Marija, "
                "Jerotic, Djurdja, Todorovic, Nevena, Asanin, Milika, "
                "Ercegovac, Marko, Ranin, Jovan, Milosevic, Ivana, "
                "Savic-Radojevic, Ana, Simic, Tatjana. GSTO1, GSTO2 and "
                "ACE2 Polymorphisms Modify Susceptibility to Developing "
                "COVID-19. J Pers Med. 2022 Mar 14;12(3). PMID: 35330457"
            },
        }
    ],
    "facets": {
        "facet_fields": {
            "journal": [{"name": "J Pers Med", "type": "int", "value": 1}],
            "countries": [],
            "e_drugs": [{"name": "Ascorbic Acid", "type": "int", "value": 1}],
            "e_strains": [],
        }
    },
    "page_size": 10,
    "current": 1,
    "count": 1,
    "total_pages": 1,
    "phid": None,
}

TOPIC_DIAGNOSIS_COUNT = {"results": [], "count": 80725, "current": 1, "total_pages": 1}

EMPTY_RESPONSE = {
    "results": [],
    "facets": {},
    "page_size": 10,
    "current": 1,
    "count": 0,
    "total_pages": 0,
    "phid": None,
}
