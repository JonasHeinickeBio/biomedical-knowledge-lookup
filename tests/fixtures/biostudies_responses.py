"""Trimmed real BioStudies / ArrayExpress responses (2026-10-09). File listings are removed,
author names and e-mail addresses are placeholders (the adapter must not copy them)."""

SEARCH_RESPONSE = {
    "page": 1,
    "pageSize": 3,
    "totalHits": 2412,
    "isTotalHitsExact": False,
    "sortBy": "relevance",
    "sortOrder": "descending",
    "suggestion": [],
    "expandedEfoTerms": [
        "tiredness",
        "chronic fatigue",
        "chronic extreme exhaustion",
        "tired",
        "exhaustion",
    ],
    "expandedSynonyms": ["tiredness", "fatigue", "tired"],
    "query": "chronic fatigue",
    "facets": None,
    "hits": [
        {
            "accession": "E-GEOD-59489",
            "type": "study",
            "title": "DNA methylation modifications associated with Chronic Fatigue Syndrome",
            "author": "Test Author One Test Author Two",
            "links": 2,
            "files": 26,
            "release_date": "2014-08-12",
            "views": 58,
            "isPublic": True,
            "content": "E-GEOD-59489 DNA methylation modifications associated with Chronic "
            "Fatigue Syndrome methylation ...",
        },
        {
            "accession": "E-GEOD-14577",
            "type": "study",
            "title": "Transcription profiling of human peripheral blood mononuclear cells "
            "(PMBCs) from male patients with post-viral chronic fatigue (n=8) and male "
            "healthy control subjects (n=7) to identify a gene signature for Chronic "
            "Fatigue Syndrome",
            "author": "Test Author One Test Author Two",
            "links": 3,
            "files": 32,
            "release_date": "2009-01-30",
            "views": 61,
            "isPublic": True,
            "content": "E-GEOD-14577 Transcription profiling of human peripheral blood "
            "mononuclear cells (PMBCs) from male ...",
        },
        {
            "accession": "E-GEOD-31187",
            "type": "study",
            "title": "Molecular signatures of peripheral blood mononuclear cells following "
            "chronic IFN-alpha: Relationship of OAS2 with Depression and Fatigue",
            "author": "Test Author One Test Author Two",
            "links": 3,
            "files": 23,
            "release_date": "2012-01-01",
            "views": 64,
            "isPublic": True,
            "content": "E-GEOD-31187 Molecular signatures of peripheral blood mononuclear cells "
            "following chronic ...",
        },
    ],
    "nextCursor": None,
    "tooManyExpansionTerms": False,
}

STUDY_GEOD_16059 = {
    "accno": "E-GEOD-16059",
    "attributes": [
        {
            "name": "Title",
            "value": "Gene Expression in Peripheral Blood Leucocytes in Monozygotic Twins "
            "Discordant for Chronic Fatigue",
        },
        {"name": "ReleaseDate", "value": "2009-05-12"},
        {"name": "RootPath", "value": "E-GEOD-16059"},
        {"name": "AttachTo", "value": "ArrayExpress"},
    ],
    "section": {
        "accno": "s-E-GEOD-16059",
        "type": "Study",
        "attributes": [
            {
                "name": "Title",
                "value": "Gene Expression in Peripheral Blood Leucocytes in "
                "Monozygotic Twins Discordant for Chronic Fatigue",
            },
            {
                "name": "Study type",
                "value": "transcription profiling by array",
                "valqual": [
                    {"name": "Ontology", "value": "EFO"},
                    {"name": "TermId", "value": "EFO_0002768"},
                ],
            },
            {"name": "Organism", "value": "Homo sapiens"},
            {
                "name": "Description",
                "value": "Background. Chronic fatiguing illness remains a poorly "
                "understood syndrome of unknown pathogenesis. We "
                "attempted to identify biomarkers for chronic fatiguing "
                "illness using microarrays to query the transcriptome in "
                "peripheral blood leukocytes. Methods. Cases were 44 "
                "individuals who were clinically ...",
            },
        ],
        "links": [[{"url": "GSE16059", "attributes": [{"name": "Type", "value": "GEO"}]}]],
        "subsections": [
            [
                {
                    "accno": "P-GSE16059-1",
                    "type": "Protocols",
                    "attributes": [
                        {"name": "Name", "value": "P-GSE16059-1"},
                        {"name": "Type", "value": "bioassay_data_transformation"},
                        {
                            "name": "Description",
                            "value": "ID_REF = <br>VALUE = SAM normalized intensity values",
                        },
                    ],
                }
            ],
            {
                "type": "Author",
                "attributes": [
                    {"name": "Name", "value": "Test Author 1"},
                    {"name": "Email", "value": "author1@example.org"},
                    {"name": "Role", "value": "submitter"},
                ],
            },
            {
                "type": "Author",
                "attributes": [
                    {"name": "Name", "value": "Test Author 2"},
                    {"name": "Email", "value": "author2@example.org"},
                    {"name": "Role", "value": "investigator"},
                ],
            },
            {
                "type": "Author",
                "attributes": [
                    {"name": "Name", "value": "Test Author 3"},
                    {"name": "Email", "value": "author3@example.org"},
                    {"name": "Role", "value": "investigator"},
                ],
            },
            {
                "accno": "o1",
                "type": "Organization",
                "attributes": [
                    {"name": "Name", "value": "UNC Chapel Hill"},
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "19503787",
                "type": "Publication",
                "attributes": [
                    {
                        "name": "Title",
                        "value": "Gene expression in peripheral blood "
                        "leukocytes in monozygotic twins "
                        "discordant for chronic fatigue: no "
                        "evidence of a biomarker.",
                    },
                    {"name": "Authors", "value": "Author A, Author B"},
                    {"name": "DOI", "value": "10.1371/journal.pone.0005805"},
                ],
                "links": [
                    {
                        "url": "10.1371/journal.pone.0005805",
                        "attributes": [{"name": "Type", "value": "DOI"}],
                    }
                ],
            },
            {
                "accno": "s-samples-factors-E-GEOD-16059",
                "type": "Samples",
                "attributes": [
                    {"name": "Sample count", "value": "88"},
                    {
                        "name": "Experimental Factors",
                        "value": "DIAGNONSIS",
                        "valqual": [{"name": "TermName", "value": "diagnonsis"}],
                    },
                    {
                        "name": "Experimental Factors",
                        "value": "SEX",
                        "valqual": [{"name": "TermName", "value": "sex"}],
                    },
                    {
                        "name": "Experimental Factors",
                        "value": "TWIN PAIR",
                        "valqual": [{"name": "TermName", "value": "twin pair"}],
                    },
                ],
                "subsections": [],
            },
            {
                "accno": "s-assays-data-E-GEOD-16059",
                "type": "Assays and Data",
                "attributes": [
                    {"name": "Technology", "value": "Array assay"},
                    {"name": "Assay by Molecule", "value": "RNA assay"},
                ],
                "subsections": [],
            },
            {
                "accno": "score-E-GEOD-16059",
                "type": "MIAME Score",
                "attributes": [
                    {"name": "Platforms", "value": "-"},
                    {"name": "Protocols", "value": "*"},
                    {"name": "Processed", "value": "*"},
                    {"name": "Raw", "value": "*"},
                    {"name": "Variables", "value": "*"},
                ],
            },
        ],
    },
    "type": "submission",
}

INFO_GEOD_16059 = {
    "files": 178,
    "httpLink": "https://ftp.ebi.ac.uk/biostudies/fire/E-GEOD-/059/E-GEOD-16059",
    "ftpLink": "ftp://ftp.ebi.ac.uk/biostudies/fire/E-GEOD-/059/E-GEOD-16059",
    "globusLink": "https://app.globus.org/file-manager?origin_id=47772002-3e5b-4fd3-b97c-18cee38d6df2&origin_path=/biostudies/fire/E-GEOD-/059/E-GEOD-16059",
    "isPublic": True,
    "relPath": "E-GEOD-/059/E-GEOD-16059",
    "hasZippedFolders": True,
    "views": 0,
    "released": 1242086400000,
    "modified": 1691250665774,
    "sections": ["mt-E-GEOD-16059", "raw-data"],
    "sectionFileCounts": {"mt-E-GEOD-16059": 2, "processed-data": 88, "raw-data": 88},
}

STUDY_MTAB_14669 = {
    "accno": "E-MTAB-14669",
    "attributes": [
        {
            "name": "Title",
            "value": "Spatial Transcriptomics of the Epipharynx in Long COVID: Exploring "
            "SARS-CoV-2 Signalling Pathways and the Therapeutic Potential of "
            "Epipharyngeal Abrasive Therapy",
        },
        {"name": "ReleaseDate", "value": "2025-02-24"},
        {"name": "RootPath", "value": "E-MTAB-14669"},
        {"name": "AttachTo", "value": "ArrayExpress"},
    ],
    "section": {
        "accno": "s-E-MTAB-14669",
        "type": "Study",
        "attributes": [
            {
                "name": "Title",
                "value": "Spatial Transcriptomics of the Epipharynx in Long "
                "COVID: Exploring SARS-CoV-2 Signalling Pathways and the "
                "Therapeutic Potential of Epipharyngeal Abrasive "
                "Therapy",
            },
            {
                "name": "Study type",
                "value": "spatial transcriptomics by high-throughput sequencing",
                "valqual": [
                    {"name": "Ontology", "value": "EFO"},
                    {"name": "TermId", "value": "EFO_0030005"},
                ],
            },
            {"name": "Organism", "value": "Homo sapiens"},
            {
                "name": "Description",
                "value": "10X VisiumHD spatial transcriptomics of epipharynx from "
                "three patients with long COVID and two control "
                "individuals without COVID-19.",
            },
        ],
        "links": [[{"url": "ERP166883", "attributes": [{"name": "Type", "value": "ENA"}]}]],
        "subsections": [
            [
                {
                    "accno": "P-MTAB-149555",
                    "type": "Protocols",
                    "attributes": [
                        {"name": "Name", "value": "P-MTAB-149555"},
                        {
                            "name": "Type",
                            "value": "sample collection protocol",
                            "valqual": [
                                {"name": "Ontology", "value": "EFO"},
                                {"name": "TermId", "value": "EFO_0005518"},
                            ],
                        },
                        {
                            "name": "Description",
                            "value": "Tissues were fixed in 10% neutral "
                            "buffered formalin and embedded in "
                            "paraffin. FFPE tissue sections were "
                            "cut at a ...",
                        },
                        {"name": "Hardware"},
                        {"name": "Software"},
                    ],
                }
            ],
            {
                "type": "Author",
                "attributes": [
                    {"name": "Name", "value": "Test Author 1"},
                    {"name": "Email", "value": "author1@example.org"},
                    {"name": "Role", "value": "submitter"},
                ],
            },
            {
                "type": "Author",
                "attributes": [
                    {"name": "Name", "value": "Test Author 2"},
                    {"name": "Email", "value": "author2@example.org"},
                    {"name": "Role", "value": "investigator"},
                ],
            },
            {
                "type": "Author",
                "attributes": [
                    {"name": "Name", "value": "Test Author 3"},
                    {"name": "Email", "value": "author3@example.org"},
                    {"name": "Role", "value": "investigator"},
                ],
            },
            {
                "accno": "o1",
                "type": "Organization",
                "attributes": [
                    {
                        "name": "Name",
                        "value": "Section of Otolaryngology, Department "
                        "of Medicine, Fukuoka Dental College",
                    },
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o2",
                "type": "Organization",
                "attributes": [
                    {
                        "name": "Name",
                        "value": "Section of Pathology, Department of "
                        "Morphological Biology, Division of "
                        "Biomedical Sciences, Fukuoka Dental "
                        "College",
                    },
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o3",
                "type": "Organization",
                "attributes": [
                    {"name": "Name", "value": "Department of Otolaryngology, Faculty of Medicine"},
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o4",
                "type": "Organization",
                "attributes": [
                    {
                        "name": "Name",
                        "value": "Section of Otolaryngology, Department "
                        "of Medicine, Fukuoka Dental College",
                    },
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o5",
                "type": "Organization",
                "attributes": [
                    {
                        "name": "Name",
                        "value": "Department of Cell Biology, Faculty of "
                        "Medicine, Fukuoka University",
                    },
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o6",
                "type": "Organization",
                "attributes": [
                    {"name": "Name", "value": "CyberomiX Ltd,"},
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o7",
                "type": "Organization",
                "attributes": [
                    {"name": "Name", "value": "CyberomiX Ltd,"},
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o8",
                "type": "Organization",
                "attributes": [
                    {"name": "Name", "value": "CyberomiX Ltd,"},
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o9",
                "type": "Organization",
                "attributes": [
                    {"name": "Name", "value": "CyberomiX Ltd,"},
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o10",
                "type": "Organization",
                "attributes": [
                    {
                        "name": "Name",
                        "value": "Department of Innovative Head & Neck "
                        "Cancer Research and Treatment, "
                        "Asahikawa Medical University",
                    },
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "accno": "o11",
                "type": "Organization",
                "attributes": [
                    {
                        "name": "Name",
                        "value": "Section of Otolaryngology, Department "
                        "of Medicine, Fukuoka Dental College",
                    },
                    {"name": "Address", "value": "Test address"},
                ],
            },
            {
                "type": "Publication",
                "attributes": [
                    {
                        "name": "Title",
                        "value": "Spatial transcriptomics of the "
                        "epipharynx in long COVID identifies "
                        "SARS-CoV-2 signalling pathways and the "
                        "therapeutic potential of ...",
                    },
                    {"name": "Authors", "value": "Author A, Author B"},
                ],
            },
            {
                "accno": "s-samples-factors-E-MTAB-14669",
                "type": "Samples",
                "attributes": [
                    {"name": "Sample count", "value": "2"},
                    {
                        "name": "Experimental Factors",
                        "value": "disease",
                        "valqual": [{"name": "TermName", "value": "disease"}],
                    },
                ],
                "subsections": [],
            },
            {
                "accno": "s-assays-data-E-MTAB-14669",
                "type": "Assays and Data",
                "attributes": [
                    {"name": "Assay count", "value": "2"},
                    {"name": "Technology", "value": "Sequencing assay"},
                    {"name": "Assay by Molecule", "value": "RNA assay"},
                ],
                "subsections": [],
            },
            {
                "accno": "score-E-MTAB-14669",
                "type": "MINSEQE Score",
                "attributes": [
                    {"name": "Exp. Design", "value": "-"},
                    {"name": "Protocols", "value": "*"},
                    {"name": "Variables", "value": "*"},
                    {"name": "Processed", "value": "*"},
                    {"name": "Raw", "value": "*"},
                ],
            },
        ],
    },
    "type": "submission",
}

INFO_MTAB_14669 = {
    "files": 10,
    "httpLink": "https://ftp.ebi.ac.uk/biostudies/fire/E-MTAB-/669/E-MTAB-14669",
    "isPublic": True,
    "released": 1740355200000,
}

SEARCH_EMPTY = {
    "page": 1,
    "pageSize": 5,
    "totalHits": 0,
    "isTotalHitsExact": True,
    "sortBy": "relevance",
    "sortOrder": "descending",
    "suggestion": [],
    "expandedEfoTerms": [],
    "expandedSynonyms": [],
    "query": "zzzqqqnothing",
    "facets": None,
    "hits": [],
    "nextCursor": None,
    "tooManyExpansionTerms": False,
}

NOT_FOUND = {"errorMessage": "Study not found"}
