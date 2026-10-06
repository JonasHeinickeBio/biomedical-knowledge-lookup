"""Real (trimmed) DGIdb v5 GraphQL responses captured live from https://dgidb.org/api/graphql.

Captured 2026-10 with the queries issued by ``DGIdbAdapter``; long interaction / alias lists
were truncated, nothing else was altered.
"""

SEARCH_GENE_BRCA1 = {
    "data": {
        "genes": {
            "nodes": [
                {
                    "name": "BRCA1",
                    "conceptId": "hgnc:1100",
                    "longName": "BRCA1 DNA repair associated",
                    "geneAliases": [
                        {"alias": "BRCA1 DNA REPAIR ASSOCIATED"},
                        {"alias": "FANCS"},
                        {"alias": "RNF53"},
                        {"alias": "PPP1R53"},
                        {"alias": "BRCC1"},
                        {"alias": "ENSEMBL:ENSG00000012048"},
                        {"alias": "NCBIGENE:672"},
                        {"alias": "PUBMED:1676470"},
                        {"alias": "ORPHANET:119068"},
                        {"alias": "PUBMED:25472942"},
                        {"alias": "CCDS:CCDS11453"},
                        {"alias": "CCDS:CCDS11456"},
                        {"alias": "VEGA:OTTHUMG00000157426"},
                        {"alias": "REFSEQ:NM_007294"},
                        {"alias": "CCDS:CCDS11455"},
                        {"alias": "CCDS:CCDS11459"},
                        {"alias": "UNIPROT:P38398"},
                        {"alias": "ENA.EMBL:U14680"},
                        {"alias": "OMIM:113705"},
                        {"alias": "COSMIC:BRCA1"},
                        {"alias": "CCDS:CCDS11454"},
                        {"alias": "UCSC:UC002ICT.4"},
                        {"alias": "BROVCA1"},
                        {"alias": "PSCP"},
                        {"alias": "IRIS"},
                        {"alias": "BRCAI"},
                        {"alias": "PNCA4"},
                        {"alias": "BRCA1, DNA REPAIR ASSOCIATED"},
                        {"alias": "PHARMGKB.GENE:PA25411"},
                        {"alias": "CIVIC.GID:6"},
                        {"alias": "NCBI.GENE:672"},
                        {"alias": "BREAST CANCER TYPE 1 SUSCEPTIBILITY PROTEIN"},
                    ],
                }
            ]
        }
    }
}

SEARCH_DRUG_MODAFINIL = {
    "data": {
        "drugs": {
            "nodes": [
                {
                    "name": "MODAFINIL",
                    "conceptId": "rxcui:30125",
                    "approved": True,
                    "drugAliases": [
                        {"alias": "ARMODAFINIL"},
                        {"alias": "CHEMBL:CHEMBL1373"},
                        {"alias": "DRUGBANK:DB06413"},
                        {"alias": "TTD.DRUG:D07HQC"},
                        {"alias": "TTD.DRUG:D0J5RN"},
                        {"alias": "PHARMGKB.DRUG:PA450530"},
                        {"alias": "CHEMBL:CHEMBL1201192"},
                        {"alias": "DRUGBANK:DB00745"},
                        {"alias": "NCIT:C26661"},
                    ],
                }
            ]
        }
    }
}

DETAILS_GENE_BRCA1 = {
    "data": {
        "genes": {
            "nodes": [
                {
                    "name": "BRCA1",
                    "conceptId": "hgnc:1100",
                    "longName": "BRCA1 DNA repair associated",
                    "geneAliases": [
                        {"alias": "BRCA1 DNA REPAIR ASSOCIATED"},
                        {"alias": "FANCS"},
                        {"alias": "RNF53"},
                        {"alias": "PPP1R53"},
                        {"alias": "BRCC1"},
                        {"alias": "ENSEMBL:ENSG00000012048"},
                        {"alias": "NCBIGENE:672"},
                        {"alias": "PUBMED:1676470"},
                        {"alias": "ORPHANET:119068"},
                        {"alias": "PUBMED:25472942"},
                        {"alias": "CCDS:CCDS11453"},
                        {"alias": "CCDS:CCDS11456"},
                        {"alias": "VEGA:OTTHUMG00000157426"},
                        {"alias": "REFSEQ:NM_007294"},
                        {"alias": "CCDS:CCDS11455"},
                        {"alias": "CCDS:CCDS11459"},
                        {"alias": "UNIPROT:P38398"},
                        {"alias": "ENA.EMBL:U14680"},
                        {"alias": "OMIM:113705"},
                        {"alias": "COSMIC:BRCA1"},
                        {"alias": "CCDS:CCDS11454"},
                        {"alias": "UCSC:UC002ICT.4"},
                        {"alias": "BROVCA1"},
                        {"alias": "PSCP"},
                        {"alias": "IRIS"},
                        {"alias": "BRCAI"},
                        {"alias": "PNCA4"},
                        {"alias": "BRCA1, DNA REPAIR ASSOCIATED"},
                        {"alias": "PHARMGKB.GENE:PA25411"},
                        {"alias": "CIVIC.GID:6"},
                        {"alias": "NCBI.GENE:672"},
                        {"alias": "BREAST CANCER TYPE 1 SUSCEPTIBILITY PROTEIN"},
                    ],
                    "geneCategories": [
                        {"name": "DRUGGABLE GENOME"},
                        {"name": "ENZYME"},
                        {"name": "DRUG RESISTANCE"},
                        {"name": "CLINICALLY ACTIONABLE"},
                        {"name": "TUMOR SUPPRESSOR"},
                        {"name": "DNA REPAIR"},
                    ],
                    "interactions": [
                        {"id": "698d16e1-29fd-47ab-a587-93c652801a14"},
                        {"id": "9d0f25be-c32c-4119-b848-12f56fbe59e2"},
                        {"id": "10c90e7f-2fc6-427f-a798-34e60562adb3"},
                        {"id": "ced3b0d9-7fbd-4923-9263-527716d72f55"},
                        {"id": "2cc676b6-0437-4576-a583-74af32b9e96a"},
                    ],
                }
            ]
        }
    }
}

DETAILS_DRUG_MODAFINIL = {
    "data": {
        "drugs": {
            "nodes": [
                {
                    "name": "MODAFINIL",
                    "conceptId": "rxcui:30125",
                    "approved": True,
                    "drugAliases": [
                        {"alias": "ARMODAFINIL"},
                        {"alias": "CHEMBL:CHEMBL1373"},
                        {"alias": "DRUGBANK:DB06413"},
                        {"alias": "TTD.DRUG:D07HQC"},
                        {"alias": "TTD.DRUG:D0J5RN"},
                        {"alias": "PHARMGKB.DRUG:PA450530"},
                        {"alias": "CHEMBL:CHEMBL1201192"},
                        {"alias": "DRUGBANK:DB00745"},
                        {"alias": "NCIT:C26661"},
                    ],
                    "drugAttributes": [
                        {"name": "Drug Class", "value": "Small molecule"},
                        {"name": "Indication", "value": "central nervous system stimulant"},
                    ],
                    "interactions": [
                        {"id": "6672d748-52d3-4656-a647-70aa453dbdc9"},
                        {"id": "59b4e077-4720-4d96-b92d-237e368da9ed"},
                        {"id": "e8c6a184-4102-4457-a23e-66f4218b5637"},
                        {"id": "fb9dcd90-5c96-4269-a4b1-c9965cf74135"},
                        {"id": "a3a059f7-488b-4edd-8403-f114060c19f6"},
                        {"id": "5aae46d3-7a4b-4cf5-978d-d931ddf97ddb"},
                        {"id": "e5ef3263-e131-423d-babf-46810f2b869a"},
                        {"id": "f08e575d-62d4-4894-bd4a-31be488edaa7"},
                    ],
                }
            ]
        }
    }
}

RELATIONSHIPS_DRUG_MODAFINIL = {
    "data": {
        "drugs": {
            "nodes": [
                {
                    "name": "MODAFINIL",
                    "conceptId": "rxcui:30125",
                    "approved": True,
                    "interactions": [
                        {
                            "gene": {
                                "name": "CYP1A2",
                                "conceptId": "hgnc:2596",
                                "longName": "cytochrome P450 family 1 subfamily A member 2",
                            },
                            "interactionScore": 0.02265924207760391,
                            "evidenceScore": 2,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "DTC"}],
                            "publications": [{"pmid": 22931300}],
                        },
                        {
                            "gene": {
                                "name": "ABCB1",
                                "conceptId": "hgnc:40",
                                "longName": "ATP binding cassette subfamily B member 1",
                            },
                            "interactionScore": 0.06331577690584059,
                            "evidenceScore": 2,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "PharmGKB"}],
                            "publications": [{"pmid": 26757307}],
                        },
                        {
                            "gene": {
                                "name": "CYP2C19",
                                "conceptId": "hgnc:2621",
                                "longName": "cytochrome P450 family 2 subfamily C member 19",
                            },
                            "interactionScore": 0.02774213285811463,
                            "evidenceScore": 2,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "DTC"}],
                            "publications": [{"pmid": 22931300}],
                        },
                        {
                            "gene": {
                                "name": "CYP3A4",
                                "conceptId": "hgnc:2637",
                                "longName": "cytochrome P450 family 3 subfamily A member 4",
                            },
                            "interactionScore": 0.01493566294957187,
                            "evidenceScore": 2,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "DTC"}],
                            "publications": [{"pmid": 22931300}],
                        },
                        {
                            "gene": {
                                "name": "CYP2D6",
                                "conceptId": "hgnc:2625",
                                "longName": "cytochrome P450 family "
                                "2 subfamily D member 6 "
                                "(gene/pseudogene)",
                            },
                            "interactionScore": 0.05414483376972456,
                            "evidenceScore": 5,
                            "interactionTypes": [],
                            "sources": [
                                {"sourceDbName": "DTC"},
                                {"sourceDbName": "NCI"},
                                {"sourceDbName": "FDA"},
                            ],
                            "publications": [{"pmid": 22931300}, {"pmid": 10820139}],
                        },
                        {
                            "gene": {
                                "name": "SLC6A3",
                                "conceptId": "hgnc:11049",
                                "longName": "solute carrier family 6 member 3",
                            },
                            "interactionScore": 0.2512594437972281,
                            "evidenceScore": 3,
                            "interactionTypes": [
                                {"type": "inhibitor", "directionality": "INHIBITORY"}
                            ],
                            "sources": [
                                {"sourceDbName": "TdgClinicalTrial"},
                                {"sourceDbName": "TTD"},
                                {"sourceDbName": "ChEMBL"},
                            ],
                            "publications": [],
                        },
                        {
                            "gene": {
                                "name": "ADRA1D",
                                "conceptId": "hgnc:280",
                                "longName": "adrenoceptor alpha 1D",
                            },
                            "interactionScore": 0.1236728726478568,
                            "evidenceScore": 2,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "TTD"}],
                            "publications": [{"pmid": 19300566}],
                        },
                        {
                            "gene": {
                                "name": "CYP2C9",
                                "conceptId": "hgnc:2623",
                                "longName": "cytochrome P450 family 2 subfamily C member 9",
                            },
                            "interactionScore": 0.03035091140669881,
                            "evidenceScore": 2,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "DTC"}],
                            "publications": [{"pmid": 22931300}],
                        },
                    ],
                }
            ]
        }
    }
}

RELATIONSHIPS_GENE_BRCA1 = {
    "data": {
        "genes": {
            "nodes": [
                {
                    "name": "BRCA1",
                    "conceptId": "hgnc:1100",
                    "longName": "BRCA1 DNA repair associated",
                    "interactions": [
                        {
                            "drug": {
                                "name": "7-HYDROXY ISOFLAVONE",
                                "conceptId": "chembl:CHEMBL491981",
                                "approved": False,
                            },
                            "interactionScore": 0.1150695423767015,
                            "evidenceScore": 1,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "DTC"}],
                            "publications": [],
                        },
                        {
                            "drug": {
                                "name": "OLAPARIB",
                                "conceptId": "rxcui:1597582",
                                "approved": True,
                            },
                            "interactionScore": 0.2484456028587875,
                            "evidenceScore": 19,
                            "interactionTypes": [],
                            "sources": [
                                {"sourceDbName": "PharmGKB"},
                                {"sourceDbName": "ClearityFoundationBiomarkers"},
                                {"sourceDbName": "CGI"},
                                {"sourceDbName": "OncoKB"},
                                {"sourceDbName": "CIViC"},
                            ],
                            "publications": [
                                {"pmid": 28578601},
                                {"pmid": 30797618},
                                {"pmid": 31157963},
                            ],
                        },
                        {
                            "drug": {
                                "name": "PLATINUM COMPOUND",
                                "conceptId": "ncit:C1450",
                                "approved": False,
                            },
                            "interactionScore": 0.2157553919563154,
                            "evidenceScore": 3,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "CIViC"}],
                            "publications": [{"pmid": 21920589}, {"pmid": 24240112}],
                        },
                        {
                            "drug": {
                                "name": "DAIDZIN",
                                "conceptId": "chembl:CHEMBL486422",
                                "approved": False,
                            },
                            "interactionScore": 0.191782570627836,
                            "evidenceScore": 1,
                            "interactionTypes": [],
                            "sources": [{"sourceDbName": "DTC"}],
                            "publications": [],
                        },
                    ],
                }
            ]
        }
    }
}

EMPTY_NODES = {"data": {"genes": {"nodes": []}}}

GRAPHQL_ERROR = {"errors": [{"message": "Field 'nope' doesn't exist on type 'Query'"}]}
