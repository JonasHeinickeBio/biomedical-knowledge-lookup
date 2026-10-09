"""Synthetic Unpaywall responses for the adapter tests.

NOT captured from the live service: the API requires a contact e-mail the user chooses and
none was available while the adapter was written. The records follow the documented DOI
object and OA location schema (https://unpaywall.org/data-format) and use placeholder DOIs
under the 10.1234 prefix. Only ``ERROR_422`` is a real response (verified 2026-10-09).
"""

ERROR_422 = {
    "HTTP_status_code": 422,
    "error": True,
    "message": "Email address required in API call, see http://unpaywall.org/products/api",
}

ERROR_404 = {
    "HTTP_status_code": 404,
    "error": True,
    "message": "'10.1234/unknown' isn't in Unpaywall (but if you think it should be, let us know)",
}

PMC_LOCATION = {
    "evidence": "oa repository (via OAI-PMH doi match)",
    "host_type": "repository",
    "is_best": True,
    "license": None,
    "oa_date": "2023-02-17",
    "pmh_id": "oai:pubmedcentral.nih.gov:9999999",
    "repository_institution": "pubmedcentral.nih.gov",
    "updated": "2024-05-02T10:11:12.131415",
    "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9999999",
    "url_for_landing_page": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9999999",
    "url_for_pdf": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9999999/pdf",
    "version": "acceptedVersion",
    "endpoint_id": "b5e840539009389b1a6",
}

PREPRINT_LOCATION = {
    "evidence": "oa repository (via OAI-PMH title and first author match)",
    "host_type": "repository",
    "is_best": False,
    "license": "cc-by-nc",
    "oa_date": None,
    "pmh_id": "oai:arXiv.org:2301.00001",
    "repository_institution": "Cornell University - arXiv",
    "updated": "2024-04-01T00:00:00.000000",
    "url": "http://arxiv.org/pdf/2301.00001",
    "url_for_landing_page": "http://arxiv.org/abs/2301.00001",
    "url_for_pdf": "http://arxiv.org/pdf/2301.00001",
    "version": "submittedVersion",
}

GREEN_WORK = {
    "best_oa_location": PMC_LOCATION,
    "data_standard": 2,
    "doi": "10.1234/green.2023.001",
    "doi_url": "https://doi.org/10.1234/green.2023.001",
    "first_oa_location": PMC_LOCATION,
    "genre": "journal-article",
    "has_repository_copy": True,
    "is_oa": True,
    "is_paratext": False,
    "journal_is_in_doaj": False,
    "journal_is_oa": False,
    "journal_issn_l": "1234-5678",
    "journal_issns": "1234-5678,8765-4321",
    "journal_name": "Journal of Synthetic Examples",
    "oa_locations": [PMC_LOCATION, PREPRINT_LOCATION, dict(PMC_LOCATION)],
    "oa_locations_embargoed": [{"url": "https://example.org/embargoed", "host_type": "publisher"}],
    "oa_status": "green",
    "published_date": "2023-01-13",
    "publisher": "Example Publisher Ltd",
    "title": "A synthetic study of fatigue after infection",
    "updated": "2024-05-02T10:11:12.131415",
    "year": 2023,
    "z_authors": [
        {
            "family": "Doe",
            "given": "Jane",
            "sequence": "first",
            "ORCID": "http://orcid.org/0000-0000-0000-0001",
        },
        {"family": "Roe", "given": "Richard", "sequence": "additional"},
        {"name": "Consortium for Examples"},
    ],
}

GOLD_LOCATION = {
    "evidence": "open (via crossref license)",
    "host_type": "publisher",
    "is_best": True,
    "license": "cc-by",
    "oa_date": "2024-03-01",
    "pmh_id": None,
    "repository_institution": None,
    "updated": "2024-05-02T10:11:12.131415",
    "url": "https://example.org/gold/paper.pdf",
    "url_for_landing_page": "https://doi.org/10.1234/gold.2024.002",
    "url_for_pdf": "https://example.org/gold/paper.pdf",
    "version": "publishedVersion",
}

GOLD_WORK = {
    "best_oa_location": GOLD_LOCATION,
    "data_standard": 2,
    "doi": "10.1234/gold.2024.002",
    "doi_url": "https://doi.org/10.1234/gold.2024.002",
    "first_oa_location": GOLD_LOCATION,
    "genre": "journal-article",
    "has_repository_copy": False,
    "is_oa": True,
    "is_paratext": False,
    "journal_is_in_doaj": True,
    "journal_is_oa": True,
    "journal_issn_l": "2345-6789",
    "journal_issns": "2345-6789",
    "journal_name": "Open Examples",
    "oa_locations": [GOLD_LOCATION],
    "oa_locations_embargoed": [],
    "oa_status": "gold",
    "published_date": "2024-03-01",
    "publisher": "Open Publisher",
    "title": "An open synthetic study",
    "updated": "2024-05-02T10:11:12.131415",
    "year": 2024,
    "z_authors": None,
}

CLOSED_WORK = {
    "best_oa_location": None,
    "data_standard": 2,
    "doi": "10.1234/closed.2020.003",
    "doi_url": "https://doi.org/10.1234/closed.2020.003",
    "first_oa_location": None,
    "genre": "journal-article",
    "has_repository_copy": False,
    "is_oa": False,
    "is_paratext": False,
    "journal_is_in_doaj": False,
    "journal_is_oa": False,
    "journal_issn_l": None,
    "journal_issns": None,
    "journal_name": "Closed Examples",
    "oa_locations": [],
    "oa_locations_embargoed": [],
    "oa_status": "closed",
    "published_date": "2020-06-01",
    "publisher": None,
    "title": "A paywalled synthetic study",
    "updated": "2024-05-02T10:11:12.131415",
    "year": 2020,
    "z_authors": [],
}
