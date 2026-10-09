"""Trimmed real PRIDE Archive v2 responses (2026-10-09). Texts are cut; submitter and lab-head
names, e-mail addresses and ORCIDs are placeholders (the adapter must not copy them)."""

SEARCH_RESPONSE = [
    {
        "accession": "PXD076216",
        "title": "Proteomic Signatures in Cerebrospinal Fluid and Their Clinical Associations in "
        "Patients with ME/CFS",
        "projectDescription": "This study evaluated the cerebrospinal fluid (CSF) proteomes from 31 "
        "patients diagnosed with myalgic encephalomyelitis/chronic fatigue "
        "syndrome (ME/CFS). We quantified 902 proteins, each expressed in at "
        "least eleven samples, and systematically categorized clinical factors "
        "relevant to ME/CFS ...",
        "dataProcessingProtocol": "Raw spectra were processed using MaxQuant (v2.2.0.0) and the "
        "Andromeda search engine against the UniProt human FASTA database "
        "(June 2022). Search parameters included a 4.5 ppm tolerance for "
        "precursor ions and 0.5 Da for MS/MS fragments. Trypsin was "
        "specified as the digestion enzyme, permitting up ...",
        "sampleProcessingProtocol": "CSF proteomic profiling was conducted using a QExactive Plus "
        "Orbitrap mass spectrometer (Thermo Fisher Scientific, Bremen, "
        "Germany) coupled to an EASY-nLC 1000 liquid chromatography "
        "system. Peptides were separated using a C18 pre-column (2 cm, "
        "100\u202fμm ID) and analytical column (10 cm, 75\u202fμm ID). A "
        "...",
        "projectTags": [],
        "keywords": [
            "Me/cfs",
            "Proteomics",
            "Lc-ms/ms",
            "Cerebrospinal fluid",
            "Myalgic encephalomyelitis",
            "Chronic fatigue syndrome",
        ],
        "doi": "",
        "submissionType": "PARTIAL",
        "publicationDate": "2026-04-05",
        "updatedDate": "2026-03-27",
        "submissionDate": "2026-03-27",
        "downloadCount": 0,
        "avgDownloadsPerFile": 0.0,
        "percentile": 0,
        "submitters": ["Test Submitter"],
        "labPIs": ["Test Labhead"],
        "affiliations": [
            "Analytical Chemistry and Neurochemistry, Department of Chemistry - BMC, "
            "Uppsala University, Uppsala, Sweden; The ME/CFS ..."
        ],
        "instruments": ["Q Exactive"],
        "softwares": ["MaxQuant"],
        "quantificationMethods": [],
        "sampleAttributes": [
            "Homo sapiens (Human)",
            "cerebrospinal fluid",
            "chronic fatigue syndrome",
        ],
        "organisms": ["Homo sapiens (human)"],
        "organismsPart": ["Cerebrospinal fluid"],
        "diseases": ["Chronic fatigue syndrome"],
        "references": [
            "Author A, Author B. Test title. Test J. 2026--pubMed:41932997--doi: "
            "10.1038/s41598-026-46965-1"
        ],
        "experimentTypes": ["Data-dependent acquisition"],
        "projectFileNames": ["sample_1.raw", "sample_2.raw", "sample_3.raw"],
        "highlights": {
            "projectDescription": [
                "This study evaluated the cerebrospinal fluid (CSF) "
                "proteomes from 31 patients diagnosed with myalgic "
                "encephalomyelitis/chronic <em>fatigue</em> syndrome "
                "(ME/CFS)."
            ],
            "diseases": ["Chronic <em>fatigue</em> syndrome"],
        },
    },
    {
        "accession": "PXD073644",
        "title": "Proteomic characterization of plasma extracellular vesicles of post-COVID-19 "
        "ME/CFS patients in comparison to healthy donors",
        "projectDescription": "Blood plasma derived extracellular Vesicles (EVs) could be important "
        "in mediating cell-to-cell-contact and thereby induce functional "
        "changes in targeted cell. This might help to understand "
        "pathomechanisms of disease such as post-infectious Myalgic "
        "Enceplhalomyelitis /Chronic Fatigue Syndrome ...",
        "dataProcessingProtocol": "The derived peak lists were analyzed against the human Swiss-Prot "
        "database using PEAKS Studio proteomics software version 10.6. The "
        "analysis was conducted with default settings in PEAKS Studio "
        "10.6, without merging scans. Peptides were identified by matching "
        "mass spectra and using the PEAKS DB ...",
        "sampleProcessingProtocol": "EV samples isolated by size exclusion chromatography "
        "(qEVoriginal/35 nm columns (IZON, Lyon, France) were prepared "
        "for proteomics analyses using the filter-aided sample "
        "preparation (FASP, Wiśniewski, J. N. et al. Nat Methods 6, "
        "359–362 (2009)). Briefly, samples were mixed with 200 µL of 8 M "
        "urea in ...",
        "projectTags": [],
        "keywords": ["Vesicle", "Pcme/cfs"],
        "doi": "",
        "otherOmicsLinks": ["geo:GSE317067"],
        "submissionType": "PARTIAL",
        "publicationDate": "2026-08-23",
        "updatedDate": "2026-01-27",
        "submissionDate": "2026-01-27",
        "downloadCount": 0,
        "avgDownloadsPerFile": 0.0,
        "percentile": 0,
        "submitters": ["Test Submitter"],
        "labPIs": ["Test Labhead"],
        "affiliations": ["Charité Universitätsmedizin Berlin Institute of Medical Immunology"],
        "instruments": ["impact II"],
        "softwares": [],
        "quantificationMethods": [],
        "sampleAttributes": ["blood plasma", "Homo sapiens (Human)", "chronic fatigue syndrome"],
        "organisms": ["Homo sapiens (human)"],
        "organismsPart": ["Extracellular vesicle", "Blood plasma"],
        "diseases": ["Chronic fatigue syndrome"],
        "references": [
            "Author A, Author B. Test title. Test J. 2026--pubMed:41828537--doi: "
            "10.3390/ijms27052314"
        ],
        "experimentTypes": ["Bottom-up proteomics"],
        "projectFileNames": ["sample_1.raw", "sample_2.raw", "sample_3.raw"],
        "highlights": {
            "projectDescription": [
                "This might help to understand pathomechanisms of "
                "disease such as post-infectious Myalgic "
                "Enceplhalomyelitis /Chronic <em>Fatigue</em> Syndrome "
                "(ME/CFS)."
            ],
            "diseases": ["Chronic <em>fatigue</em> syndrome"],
        },
    },
    {
        "accession": "PAD000026",
        "title": "Charting the Circulating Proteome in ME/CFS Using Cross System Profiling to "
        "Uncover Mechanistic Insights",
        "projectDescription": "This dataset contains processed aptamer-based serum proteomics data "
        "from ME/CFS patients and healthy controls, analyzed using the 7k "
        "SomaScan assay (v4.1) platform. It includes log2-transformed "
        "intensities for 7326 aptamers (6494 protein targets), cohort metadata "
        "(age range, sex, BMI category, ...",
        "dataProcessingProtocol": "Serum proteins were quantified using the SomaScan v4.1 platform "
        "(SomaLogic Inc., Boulder, CO). Data was received as normalized "
        "relative fluorescence units (RFU). SomaLogic normalization and "
        "hybridization controls were applied by the vendor, followed by "
        "hybridization signal calibration and median ...",
        "sampleProcessingProtocol": "Serum samples were obtained from participants in the RituxME "
        "and CycloME clinical trials and age- and sex-matched healthy "
        "controls. Inclusion criteria and clinical characterization "
        "followed Canadian ME/CFS guidelines. Eligible samples were "
        "randomly selected to reduce selection bias and stored at ...",
        "projectTags": [],
        "keywords": ["Me/cfs", "Serum"],
        "doi": "10.6019/PAD000026",
        "submissionType": "AFFINITY",
        "publicationDate": "2026-01-21",
        "updatedDate": "2026-01-09",
        "submissionDate": "2026-01-09",
        "downloadCount": 0,
        "avgDownloadsPerFile": 0.0,
        "percentile": 0,
        "submitters": ["Test Submitter"],
        "labPIs": ["Test Labhead"],
        "affiliations": [
            "University of Bergen, Faculty of Medicine, Department of Biomedicine, The "
            "Cell Metabolism Group - Bergen, Norway"
        ],
        "instruments": ["SomaScan assay v4.1"],
        "softwares": [],
        "quantificationMethods": ["Relative quantification"],
        "sampleAttributes": ["Homo sapiens (Human)", "blood serum", "chronic fatigue syndrome"],
        "organisms": ["Homo sapiens (human)"],
        "organismsPart": ["Blood serum"],
        "diseases": ["Chronic fatigue syndrome"],
        "references": [
            "Author A, Author B. Test title. Test J. 2026--pubMed:41785863--doi: "
            "10.1016/j.xcrm.2026.102647",
            "Author A, Author B. Test title. Test J. 2026--pubMed:0--doi: 10.2139/SSRN.5284518",
        ],
        "experimentTypes": ["SomaScan affinity proteomics", "Affinity proteomics"],
        "projectFileNames": ["sample_1.raw", "sample_2.raw", "sample_3.raw"],
        "highlights": {
            "diseases": ["Chronic <em>fatigue</em> syndrome"],
            "sampleAttributes": ["chronic <em>fatigue</em> syndrome"],
        },
    },
]

DETAIL_PXD076216 = {
    "accession": "PXD076216",
    "title": "Proteomic Signatures in Cerebrospinal Fluid and Their Clinical Associations in "
    "Patients with ME/CFS",
    "additionalAttributes": [],
    "projectDescription": "This study evaluated the cerebrospinal fluid (CSF) proteomes from 31 "
    "patients diagnosed with myalgic encephalomyelitis/chronic fatigue "
    "syndrome (ME/CFS). We quantified 902 proteins, each expressed in at "
    "least eleven samples, and systematically categorized clinical factors "
    "relevant to ME/CFS ...",
    "sampleProcessingProtocol": "CSF proteomic profiling was conducted using a QExactive Plus "
    "Orbitrap mass spectrometer (Thermo Fisher Scientific, Bremen, "
    "Germany) coupled to an EASY-nLC 1000 liquid chromatography "
    "system. Peptides were separated using a C18 pre-column (2 cm, "
    "100\u202fμm ID) and analytical column (10 cm, 75\u202fμm ID). A "
    "...",
    "dataProcessingProtocol": "Raw spectra were processed using MaxQuant (v2.2.0.0) and the "
    "Andromeda search engine against the UniProt human FASTA database "
    "(June 2022). Search parameters included a 4.5 ppm tolerance for "
    "precursor ions and 0.5 Da for MS/MS fragments. Trypsin was "
    "specified as the digestion enzyme, permitting up ...",
    "projectTags": [],
    "keywords": [
        "Cerebrospinal fluid",
        "Myalgic encephalomyelitis",
        "Chronic fatigue syndrome",
        "Proteomics",
        "Me/cfs",
        "Lc-ms/ms",
    ],
    "doi": "",
    "submissionType": "PARTIAL",
    "license": "Creative Commons Public Domain (CC0)",
    "submissionDate": "2026-03-27",
    "publicationDate": "2026-04-05",
    "submitters": [
        {
            "title": "Dr",
            "firstName": "Test",
            "lastName": "Submitter",
            "identifier": "1",
            "affiliation": "Test Institute",
            "email": "submitter@example.org",
            "country": "",
            "orcid": "0000-0000-0000-0000",
            "name": "Test Submitter",
            "id": "1",
        }
    ],
    "labPIs": [
        {
            "title": "Prof",
            "firstName": "Test",
            "lastName": "Labhead",
            "identifier": "2",
            "affiliation": "Test Institute",
            "email": "labhead@example.org",
            "country": "",
            "orcid": "",
            "name": "Test Labhead",
            "id": "2",
        }
    ],
    "instruments": [
        {"@type": "CvParam", "cvLabel": "MS", "accession": "MS:1001911", "name": "Q Exactive"}
    ],
    "softwares": [
        {"@type": "CvParam", "cvLabel": "MS", "accession": "MS:1001583", "name": "MaxQuant"}
    ],
    "experimentTypes": [
        {
            "@type": "CvParam",
            "cvLabel": "PRIDE",
            "accession": "PRIDE:0000627",
            "name": "Data-dependent acquisition",
        }
    ],
    "quantificationMethods": [],
    "countries": ["United States"],
    "sampleAttributes": [
        {
            "@type": "Tuple",
            "key": {"cvLabel": "EFO", "accession": "EFO:0000635", "name": "organism part"},
            "value": [
                {"cvLabel": "BTO", "accession": "BTO:0000237", "name": "cerebrospinal fluid"}
            ],
        },
        {
            "@type": "Tuple",
            "key": {"cvLabel": "EFO", "accession": "OBI:0100026", "name": "organism"},
            "value": [
                {"cvLabel": "NEWT", "accession": "NEWT:9606", "name": "Homo sapiens (Human)"}
            ],
        },
        {
            "@type": "Tuple",
            "key": {"cvLabel": "EFO", "accession": "EFO:0000408", "name": "disease"},
            "value": [
                {"cvLabel": "DOID", "accession": "DOID:8544", "name": "chronic fatigue syndrome"}
            ],
        },
    ],
    "organisms": [
        {
            "@type": "CvParam",
            "cvLabel": "NEWT",
            "accession": "NEWT:9606",
            "name": "Homo sapiens (human)",
        }
    ],
    "organismParts": [
        {
            "@type": "CvParam",
            "cvLabel": "BTO",
            "accession": "BTO:0000237",
            "name": "Cerebrospinal fluid",
        }
    ],
    "diseases": [
        {
            "@type": "CvParam",
            "cvLabel": "DOID",
            "accession": "DOID:8544",
            "name": "Chronic fatigue syndrome",
        }
    ],
    "references": [
        {
            "referenceLine": "Author A, Author B. Test title. Test J. 2026",
            "pubmedID": 41932997,
            "doi": "10.1038/s41598-026-46965-1",
        }
    ],
    "identifiedPTMStrings": [
        {
            "@type": "CvParam",
            "cvLabel": "MOD",
            "accession": "MOD:00425",
            "name": "monohydroxylated residue",
        },
        {
            "@type": "CvParam",
            "cvLabel": "MOD",
            "accession": "MOD:00394",
            "name": "acetylated residue",
        },
        {
            "@type": "CvParam",
            "cvLabel": "MOD",
            "accession": "MOD:00397",
            "name": "iodoacetamide derivatized residue",
        },
    ],
    "totalFileDownloads": 0,
}

DETAIL_PXD001357 = {
    "accession": "PXD001357",
    "title": "Direct evidence of milk consumption from ancient human dental calculus, St Helena",
    "additionalAttributes": [],
    "projectDescription": "This study investigated the consumption of milk products in the "
    "archaeological record, utilizing human dental calculus as a reservoir "
    "of dietary proteins from archaeological samples from across Eurasia. "
    "Protein extraction and generation of tryptic peptides from dental "
    "calculus was performed using a ...",
    "sampleProcessingProtocol": "Tryptic peptides were extracted from decalcified dental calculus "
    "using a filter-aided sample preparation (FASP) protocol modified "
    "for degraded samples. Samples from St Helena were analyzed by "
    "tandem mass spectrometry at the Central Proteomics Facility, "
    "Target Discovery Institute, Oxford using a ...",
    "dataProcessingProtocol": "Raw MS/MS spectra were converted to searchable Mascot generic "
    "format using Proteowizard version 3.0.4743 using the 200 most "
    "intense peaks in each MS/MS spectrum. MS/MS ion database searching "
    "was performed on Mascot (Matrix ScienceTM, version 2.4.01), "
    "against all available sequences in UniProt and ...",
    "projectTags": ["Technical", "Metaproteomics"],
    "keywords": ["Human", "Beta-lactoglobulin", "Dental calculus", "Dental plaque", "Lc-ms/ms"],
    "doi": "10.6019/PXD001357",
    "submissionType": "COMPLETE",
    "license": "EBI terms of use",
    "submissionDate": "2014-10-15",
    "publicationDate": "2015-02-25",
    "submitters": [
        {
            "title": "Dr",
            "firstName": "Test",
            "lastName": "Submitter",
            "identifier": "1",
            "affiliation": "Test Institute",
            "email": "submitter@example.org",
            "country": "",
            "orcid": "0000-0000-0000-0000",
            "name": "Test Submitter",
            "id": "1",
        }
    ],
    "labPIs": [
        {
            "title": "Prof",
            "firstName": "Test",
            "lastName": "Labhead",
            "identifier": "2",
            "affiliation": "Test Institute",
            "email": "labhead@example.org",
            "country": "",
            "orcid": "",
            "name": "Test Labhead",
            "id": "2",
        }
    ],
    "instruments": [
        {
            "@type": "CvParam",
            "cvLabel": "MS",
            "accession": "MS:1001910",
            "name": "LTQ Orbitrap Elite",
            "value": "",
        },
        {
            "@type": "CvParam",
            "cvLabel": "MS",
            "accession": "MS:1001911",
            "name": "Q Exactive",
            "value": "",
        },
    ],
    "softwares": [
        {"@type": "CvParam", "cvLabel": "MS", "accession": "MS:1001207", "name": "Mascot"}
    ],
    "experimentTypes": [
        {
            "@type": "CvParam",
            "cvLabel": "PRIDE",
            "accession": "PRIDE:0000429",
            "name": "Shotgun proteomics",
        }
    ],
    "quantificationMethods": [],
    "countries": ["United Kingdom"],
    "sampleAttributes": [
        {
            "@type": "Tuple",
            "key": {"cvLabel": "EFO", "accession": "EFO:0000635", "name": "organism part"},
            "value": [
                {
                    "cvLabel": "BTO",
                    "accession": "BTO:0000338",
                    "name": "dental plaque",
                    "value": "",
                }
            ],
        },
        {
            "@type": "Tuple",
            "key": {"cvLabel": "EFO", "accession": "OBI:0100026", "name": "organism"},
            "value": [
                {
                    "cvLabel": "NEWT",
                    "accession": "NEWT:9606",
                    "name": "Homo sapiens (Human)",
                    "value": "",
                }
            ],
        },
    ],
    "organisms": [
        {
            "@type": "CvParam",
            "cvLabel": "NEWT",
            "accession": "NEWT:9606",
            "name": "Homo sapiens (human)",
            "value": "",
        }
    ],
    "organismParts": [
        {
            "@type": "CvParam",
            "cvLabel": "BTO",
            "accession": "BTO:0000338",
            "name": "Dental plaque",
            "value": "",
        }
    ],
    "diseases": [],
    "references": [
        {
            "referenceLine": "Author A, Author B. Test title. Test J. 2026",
            "pubmedID": 25429530,
            "doi": "10.1038/srep07104",
        }
    ],
    "identifiedPTMStrings": [
        {
            "@type": "CvParam",
            "cvLabel": "UNIMOD",
            "accession": "UNIMOD:28",
            "name": "Gln->pyro-Glu",
            "value": "",
        },
        {
            "@type": "CvParam",
            "cvLabel": "UNIMOD",
            "accession": "UNIMOD:7",
            "name": "Deamidated",
            "value": "",
        },
        {
            "@type": "CvParam",
            "cvLabel": "UNIMOD",
            "accession": "UNIMOD:4",
            "name": "Carbamidomethyl",
            "value": "",
        },
    ],
    "totalFileDownloads": 29298,
    "otherOmicsLinks": [
        "pride.project:PXD001360",
        "pride.project:PXD001362",
        "px:PXD001361",
        "pride.project:PXD001361",
        "px:PXD001360",
        "px:PXD001359",
        "pride.project:PXD001359",
        "px:PXD001362",
    ],
}

SEARCH_EMPTY = []
