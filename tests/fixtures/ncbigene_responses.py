"""Trimmed real responses of the NCBI Datasets v2 gene API (captured 2026-10-09) for
tests/unit/test_ncbigene_adapter.py.

``gene/symbol/BRCA1/taxon/9606``, ``gene/symbol/BRCC1/taxon/9606`` (alias shared by two genes),
``gene/id/672,3105,7157``, ``gene/taxon/9606/dataset_report?query=breast cancer``,
``gene/symbol/Brca1/taxon/10090``, ``gene/id/672/product_report`` and
``gene/id/672/orthologs?taxon_filter=10090``. Gene Ontology lists, annotations and the transcript
list (368 in the real answer) were shortened.
"""

GENE_BRCA1 = {
    "reports": [
        {
            "gene": {
                "gene_id": "672",
                "symbol": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_005905.2",
                            "range": [{"begin": "92501", "end": "173689", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["17"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:1100"},
                "swiss_prot_accessions": ["P38398"],
                "ensembl_gene_ids": ["ENSG00000012048"],
                "omim_ids": ["113705"],
                "synonyms": [
                    "IRIS",
                    "PSCP",
                    "BRCAI",
                    "BRCC1",
                    "FANCS",
                    "PNCA4",
                    "RNF53",
                    "BROVCA1",
                    "PPP1R53",
                ],
                "alternate_names": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "Fanconi anemia, complementation group S",
                    "RING finger protein 53",
                    "breast and ovarian cancer susceptibility protein 1",
                    "breast cancer 1, early onset",
                    "breast cancer type 1 susceptibility protein",
                    "early onset breast cancer 1",
                    "protein phosphatase 1, regulatory subunit 53",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.11",
                                "sequence_name": "17",
                                "genomic_range": {
                                    "begin": "43044295",
                                    "end": "43170327",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    },
                    {
                        "assembly_accession": "GCF_009914755.1",
                        "assembly_name": "T2T-CHM13v2.0",
                        "annotation_name": "GCF_009914755.1-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_060941.1",
                                "sequence_name": "17",
                                "genomic_range": {
                                    "begin": "43902857",
                                    "end": "44029084",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    },
                ],
                "transcript_count": 368,
                "protein_count": 368,
                "transcript_type_counts": [{"type": "PROTEIN_CODING", "count": 368}],
                "gene_groups": [{"id": "672", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "This gene encodes a 190 kD nuclear "
                        "phosphoprotein that plays a role in "
                        "maintaining genomic stability, and it also "
                        "acts as a tumor suppressor. The BRCA1 gene "
                        "contains 22 exons spanning about 110 kb of "
                        "DNA. The encoded protein combines with "
                        "other tumor suppressors, DNA damage "
                        "sensors, and signal transducers to form a "
                        "large multi-subunit protein complex known "
                        "as the BRCA1-associated genome "
                        "surveillance complex (BASC). This gene "
                        "product associates with RNA polymerase II, "
                        "and through the C-terminal domain, also "
                        "interacts with histone deacetylase "
                        "complexes. This protein thus plays a role "
                        "in transcription, DNA repair of "
                        "double-stranded breaks, and recombination. "
                        "Mutations in this gene are responsible for "
                        "approximately 40% of inherited breast "
                        "cancers and more than 80% of inherited "
                        "breast and ovarian cancers. Alternative "
                        "splicing plays a role in modulating the "
                        "subcellular localization and physiological "
                        "function of this gene. Many alternatively "
                        "spliced transcript variants, some of which "
                        "are disease-associated mutations, have "
                        "been described for this gene, but the "
                        "full-length natures of only some of these "
                        "variants has been described. A related "
                        "pseudogene, which is also located on "
                        "chromosome 17, has been identified. "
                        "[provided by RefSeq, May 2020]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        },
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "TAS",
                            "qualifier": "enables",
                            "reference": {"pmids": ["9662397"]},
                        },
                        {
                            "name": "RNA binding",
                            "go_id": "GO:0003723",
                            "evidence_code": "IDA",
                            "qualifier": "enables",
                            "reference": {"pmids": ["12419249"]},
                        },
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IEA",
                            "qualifier": "involved_in",
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "NAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["16651405"]},
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "TAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["10910365"]},
                        },
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IBA",
                            "qualifier": "part_of",
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IDA",
                            "qualifier": "part_of",
                            "reference": {
                                "pmids": [
                                    "17525340",
                                    "17525341",
                                    "17525342",
                                    "19261748",
                                    "19261749",
                                ]
                            },
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "NAS",
                            "qualifier": "part_of",
                            "reference": {"pmids": ["20656689"]},
                        },
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "17q21.31"}],
            },
            "query": ["BRCA1"],
        }
    ],
    "total_count": 1,
}

GENES_ALIAS_BRCC1 = {
    "reports": [
        {
            "gene": {
                "gene_id": "672",
                "symbol": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_005905.2",
                            "range": [{"begin": "92501", "end": "173689", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["17"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:1100"},
                "swiss_prot_accessions": ["P38398"],
                "ensembl_gene_ids": ["ENSG00000012048"],
                "omim_ids": ["113705"],
                "synonyms": [
                    "IRIS",
                    "PSCP",
                    "BRCAI",
                    "BRCC1",
                    "FANCS",
                    "PNCA4",
                    "RNF53",
                    "BROVCA1",
                    "PPP1R53",
                ],
                "alternate_names": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "Fanconi anemia, complementation group S",
                    "RING finger protein 53",
                    "breast and ovarian cancer susceptibility protein 1",
                    "breast cancer 1, early onset",
                    "breast cancer type 1 susceptibility protein",
                    "early onset breast cancer 1",
                    "protein phosphatase 1, regulatory subunit 53",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.11",
                                "sequence_name": "17",
                                "genomic_range": {
                                    "begin": "43044295",
                                    "end": "43170327",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 368,
                "protein_count": 368,
                "transcript_type_counts": [{"type": "PROTEIN_CODING", "count": 368}],
                "gene_groups": [{"id": "672", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "This gene encodes a 190 kD nuclear "
                        "phosphoprotein that plays a role in "
                        "maintaining genomic stability, and it also "
                        "acts as a tumor suppressor. The BRCA1 gene "
                        "contains 22 exons spanning about 110 kb of "
                        "DNA. The encoded protein combines with "
                        "other tumor suppressors, DNA damage "
                        "sensors, and signal transducers to form a "
                        "large multi-subunit protein complex known "
                        "as the BRCA1-associated genome "
                        "surveillance complex (BASC). This gene "
                        "product associates with RNA polymerase II, "
                        "and through the C-terminal domain, also "
                        "interacts with histone deacetylase "
                        "complexes. This protein thus plays a role "
                        "in transcription, DNA repair of "
                        "double-stranded breaks, and recombination. "
                        "Mutations in this gene are responsible for "
                        "approximately 40% of inherited breast "
                        "cancers and more than 80% of inherited "
                        "breast and ovarian cancers. Alternative "
                        "splicing plays a role in modulating the "
                        "subcellular localization and physiological "
                        "function of this gene. Many alternatively "
                        "spliced transcript variants, some of which "
                        "are disease-associated mutations, have "
                        "been described for this gene, but the "
                        "full-length natures of only some of these "
                        "variants has been described. A related "
                        "pseudogene, which is also located on "
                        "chromosome 17, has been identified. "
                        "[provided by RefSeq, May 2020]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        },
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "TAS",
                            "qualifier": "enables",
                            "reference": {"pmids": ["9662397"]},
                        },
                        {
                            "name": "RNA binding",
                            "go_id": "GO:0003723",
                            "evidence_code": "IDA",
                            "qualifier": "enables",
                            "reference": {"pmids": ["12419249"]},
                        },
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IEA",
                            "qualifier": "involved_in",
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "NAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["16651405"]},
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "TAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["10910365"]},
                        },
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IBA",
                            "qualifier": "part_of",
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IDA",
                            "qualifier": "part_of",
                            "reference": {
                                "pmids": [
                                    "17525340",
                                    "17525341",
                                    "17525342",
                                    "19261748",
                                    "19261749",
                                ]
                            },
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "NAS",
                            "qualifier": "part_of",
                            "reference": {"pmids": ["20656689"]},
                        },
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "17q21.31"}],
            },
            "query": ["BRCC1"],
        },
        {
            "gene": {
                "gene_id": "79664",
                "symbol": "ICE2",
                "description": "interactor of little elongation complex ELL subunit 2",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_054881.1",
                            "range": [{"begin": "5019", "end": "64552", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["15"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:29885"},
                "swiss_prot_accessions": ["Q659A1"],
                "ensembl_gene_ids": ["ENSG00000128915"],
                "omim_ids": ["610835"],
                "synonyms": ["BRCC1", "NARG2"],
                "alternate_names": [
                    "NMDA receptor regulated 2",
                    "NMDA receptor-regulated gene 2",
                    "NMDA receptor-regulated protein 2",
                    "breast cancer cell 1",
                    "interactor of little elongator complex ELL subunit 2",
                    "little elongation complex subunit 2",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000015.10",
                                "sequence_name": "15",
                                "genomic_range": {
                                    "begin": "60419609",
                                    "end": "60479142",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 23,
                "protein_count": 22,
                "transcript_type_counts": [
                    {"type": "PROTEIN_CODING", "count": 3},
                    {"type": "NON_CODING", "count": 1},
                    {"type": "PROTEIN_CODING_MODEL", "count": 19},
                ],
                "gene_groups": [{"id": "79664", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "This gene encodes a protein component of "
                        "the little elongation complex (LEC), which "
                        "plays a role in small nuclear RNA (snRNA) "
                        "transcription. The LEC regulates snRNA "
                        "transcription by enhancing both RNA "
                        "Polymerase II occupancy and "
                        "transcriptional elongation. The encoded "
                        "protein and other LEC components have been "
                        "shown to localize to Cajal bodies, which "
                        "are sites of ribonucleoprotein (RNP) "
                        "complex assembly. Pseudogenes of this gene "
                        "have been identified on chromosomes 3 and "
                        "4. [provided by RefSeq, May 2017]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "protein binding",
                            "go_id": "GO:0005515",
                            "evidence_code": "IPI",
                            "qualifier": "enables",
                            "reference": {"pmids": ["21729782", "22195968", "23932780"]},
                        }
                    ],
                    "biological_processes": [
                        {
                            "name": "positive "
                            "regulation of "
                            "snRNA "
                            "transcription by "
                            "RNA polymerase II",
                            "go_id": "GO:1905382",
                            "evidence_code": "NAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["23932780"]},
                        },
                        {
                            "name": "positive regulation of transcription by RNA polymerase III",
                            "go_id": "GO:0045945",
                            "evidence_code": "IBA",
                            "qualifier": "involved_in",
                        },
                        {
                            "name": "positive regulation of transcription by RNA polymerase III",
                            "go_id": "GO:0045945",
                            "evidence_code": "IMP",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["23932780"]},
                        },
                    ],
                    "cellular_components": [
                        {
                            "name": "Cajal body",
                            "go_id": "GO:0015030",
                            "evidence_code": "IDA",
                            "qualifier": "located_in",
                            "reference": {"pmids": ["23932780"]},
                        },
                        {
                            "name": "euchromatin",
                            "go_id": "GO:0000791",
                            "evidence_code": "IDA",
                            "qualifier": "located_in",
                            "reference": {"pmids": ["22195968", "23932780"]},
                        },
                        {
                            "name": "histone locus body",
                            "go_id": "GO:0035363",
                            "evidence_code": "IDA",
                            "qualifier": "located_in",
                            "reference": {"pmids": ["23932780"]},
                        },
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "15q22.2"}],
            },
            "query": ["BRCC1"],
        },
    ],
    "total_count": 2,
}

GENES_BY_ID = {
    "reports": [
        {
            "gene": {
                "gene_id": "7157",
                "symbol": "TP53",
                "description": "tumor protein p53",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_017013.2",
                            "range": [{"begin": "5001", "end": "24149", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["17"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:11998"},
                "swiss_prot_accessions": ["P04637"],
                "ensembl_gene_ids": ["ENSG00000141510"],
                "omim_ids": ["191170"],
                "synonyms": ["P53", "BCC7", "LFS1", "BMFS5", "TRP53"],
                "alternate_names": [
                    "antigen NY-CO-13",
                    "cellular tumor antigen p53",
                    "mutant tumor protein 53",
                    "phosphoprotein p53",
                    "transformation-related protein 53",
                    "tumor protein 53",
                    "tumor supressor p53",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.11",
                                "sequence_name": "17",
                                "genomic_range": {
                                    "begin": "7668421",
                                    "end": "7687490",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 26,
                "protein_count": 25,
                "transcript_type_counts": [
                    {"type": "PROTEIN_CODING", "count": 25},
                    {"type": "NON_CODING", "count": 1},
                ],
                "gene_groups": [{"id": "7157", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "This gene encodes a tumor suppressor "
                        "protein containing transcriptional "
                        "activation, DNA binding, and "
                        "oligomerization domains. The encoded "
                        "protein responds to diverse cellular "
                        "stresses to regulate expression of target "
                        "genes, thereby inducing cell cycle arrest, "
                        "apoptosis, senescence, DNA repair, or "
                        "changes in metabolism. Mutations in this "
                        "gene are associated with a variety of "
                        "human cancers, including hereditary "
                        "cancers such as Li-Fraumeni syndrome. "
                        "Alternative splicing of this gene and the "
                        "use of alternate promoters result in "
                        "multiple transcript variants and isoforms. "
                        "Additional isoforms have also been shown "
                        "to result from the use of alternate "
                        "translation initiation codons from "
                        "identical transcript variants (PMIDs: "
                        "12032546, 20937277). [provided by RefSeq, "
                        "Dec 2016]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "14-3-3 protein binding",
                            "go_id": "GO:0071889",
                            "evidence_code": "EXP",
                            "qualifier": "enables",
                            "reference": {"pmids": ["20206173"]},
                        }
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IDA",
                            "qualifier": "acts_upstream_of_or_within",
                            "reference": {"pmids": ["14744935"]},
                        }
                    ],
                    "cellular_components": [
                        {
                            "name": "PML body",
                            "go_id": "GO:0016605",
                            "evidence_code": "IDA",
                            "qualifier": "located_in",
                            "reference": {"pmids": ["12006491", "22869143"]},
                        }
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "17p13.1"}],
            },
            "query": ["7157"],
        },
        {
            "gene": {
                "gene_id": "672",
                "symbol": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_005905.2",
                            "range": [{"begin": "92501", "end": "173689", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["17"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:1100"},
                "swiss_prot_accessions": ["P38398"],
                "ensembl_gene_ids": ["ENSG00000012048"],
                "omim_ids": ["113705"],
                "synonyms": [
                    "IRIS",
                    "PSCP",
                    "BRCAI",
                    "BRCC1",
                    "FANCS",
                    "PNCA4",
                    "RNF53",
                    "BROVCA1",
                    "PPP1R53",
                ],
                "alternate_names": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "Fanconi anemia, complementation group S",
                    "RING finger protein 53",
                    "breast and ovarian cancer susceptibility protein 1",
                    "breast cancer 1, early onset",
                    "breast cancer type 1 susceptibility protein",
                    "early onset breast cancer 1",
                    "protein phosphatase 1, regulatory subunit 53",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.11",
                                "sequence_name": "17",
                                "genomic_range": {
                                    "begin": "43044295",
                                    "end": "43170327",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 368,
                "protein_count": 368,
                "transcript_type_counts": [{"type": "PROTEIN_CODING", "count": 368}],
                "gene_groups": [{"id": "672", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "This gene encodes a 190 kD nuclear "
                        "phosphoprotein that plays a role in "
                        "maintaining genomic stability, and it also "
                        "acts as a tumor suppressor. The BRCA1 gene "
                        "contains 22 exons spanning about 110 kb of "
                        "DNA. The encoded protein combines with "
                        "other tumor suppressors, DNA damage "
                        "sensors, and signal transducers to form a "
                        "large multi-subunit protein complex known "
                        "as the BRCA1-associated genome "
                        "surveillance complex (BASC). This gene "
                        "product associates with RNA polymerase II, "
                        "and through the C-terminal domain, also "
                        "interacts with histone deacetylase "
                        "complexes. This protein thus plays a role "
                        "in transcription, DNA repair of "
                        "double-stranded breaks, and recombination. "
                        "Mutations in this gene are responsible for "
                        "approximately 40% of inherited breast "
                        "cancers and more than 80% of inherited "
                        "breast and ovarian cancers. Alternative "
                        "splicing plays a role in modulating the "
                        "subcellular localization and physiological "
                        "function of this gene. Many alternatively "
                        "spliced transcript variants, some of which "
                        "are disease-associated mutations, have "
                        "been described for this gene, but the "
                        "full-length natures of only some of these "
                        "variants has been described. A related "
                        "pseudogene, which is also located on "
                        "chromosome 17, has been identified. "
                        "[provided by RefSeq, May 2020]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        }
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IEA",
                            "qualifier": "involved_in",
                        }
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IBA",
                            "qualifier": "part_of",
                        }
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "17q21.31"}],
            },
            "query": ["672"],
        },
        {
            "gene": {
                "gene_id": "3105",
                "symbol": "HLA-A",
                "description": "major histocompatibility complex, class I, A",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "plus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_029217.3",
                            "range": [{"begin": "5002", "end": "8340", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["6"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:4931"},
                "swiss_prot_accessions": ["P04439"],
                "ensembl_gene_ids": ["ENSG00000206503"],
                "omim_ids": ["142800"],
                "synonyms": ["HLAA"],
                "alternate_names": [
                    "HLA class I histocompatibility antigen, A alpha chain",
                    "HLA class I histocompatibility antigen, A-1 alpha chain",
                    "MHC class I antigen HLA-A heavy chain",
                    "leukocyte antigen class I-A",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000006.12",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "29942532",
                                    "end": "29945870",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_113891.3",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1421892",
                                    "end": "1425307",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_167244.2",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1200217",
                                    "end": "1203632",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_167245.2",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1198085",
                                    "end": "1201438",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_167246.2",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1197074",
                                    "end": "1200428",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_167247.2",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1286642",
                                    "end": "1289974",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_167248.2",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1197429",
                                    "end": "1200858",
                                    "orientation": "plus",
                                },
                            },
                            {
                                "genomic_accession_version": "NT_167249.2",
                                "sequence_name": "6",
                                "genomic_range": {
                                    "begin": "1240346",
                                    "end": "1243700",
                                    "orientation": "plus",
                                },
                            },
                        ],
                    }
                ],
                "transcript_count": 4,
                "protein_count": 4,
                "transcript_type_counts": [
                    {"type": "PROTEIN_CODING", "count": 2},
                    {"type": "PROTEIN_CODING_MODEL", "count": 2},
                ],
                "summary": [
                    {
                        "description": "HLA-A belongs to the HLA class I heavy "
                        "chain paralogues. This class I molecule is "
                        "a heterodimer consisting of a heavy chain "
                        "and a light chain (beta-2 microglobulin). "
                        "The heavy chain is anchored in the "
                        "membrane. Class I molecules play a central "
                        "role in the immune system by presenting "
                        "peptides derived from the endoplasmic "
                        "reticulum lumen so that they can be "
                        "recognized by cytotoxic T cells. They are "
                        "expressed in nearly all cells. The heavy "
                        "chain is approximately 45 kDa and its gene "
                        "contains 8 exons. Exon 1 encodes the "
                        "leader peptide, exons 2 and 3 encode the "
                        "alpha1 and alpha2 domains, which both bind "
                        "the peptide, exon 4 encodes the alpha3 "
                        "domain, exon 5 encodes the transmembrane "
                        "region, and exons 6 and 7 encode the "
                        "cytoplasmic tail. Polymorphisms within "
                        "exon 2 and exon 3 are responsible for the "
                        "peptide binding specificity of each class "
                        "one molecule. Typing for these "
                        "polymorphisms is routinely done for bone "
                        "marrow and kidney transplantation. More "
                        "than 6000 HLA-A alleles have been "
                        "described. The HLA system plays an "
                        "important role in the occurrence and "
                        "outcome of infectious diseases, including "
                        "those caused by the malaria parasite, the "
                        "human immunodeficiency virus (HIV), and "
                        "the severe acute respiratory syndrome "
                        "coronavirus (SARS-CoV). The structural "
                        "spike and the nucleocapsid proteins of the "
                        "novel coronavirus SARS-CoV-2, which causes "
                        "coronavirus disease 2019 (COVID-19), are "
                        "reported to contain multiple Class I "
                        "epitopes with predicted HLA restrictions. "
                        "Individual HLA genetic variation may help "
                        "explain different immune responses to a "
                        "virus across a population.[provided by "
                        "RefSeq, Aug 2020]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "CD8 receptor binding",
                            "go_id": "GO:0042610",
                            "evidence_code": "IDA",
                            "qualifier": "enables",
                            "reference": {"pmids": ["2784196"]},
                        }
                    ],
                    "biological_processes": [
                        {
                            "name": "CD8-positive, alpha-beta T cell activation",
                            "go_id": "GO:0036037",
                            "evidence_code": "IDA",
                            "qualifier": "involved_in",
                            "reference": {
                                "pmids": [
                                    "1402688",
                                    "2784196",
                                    "7504010",
                                    "8630735",
                                    "12138174",
                                    "17189421",
                                    "20364150",
                                ]
                            },
                        }
                    ],
                    "cellular_components": [
                        {
                            "name": "ER to Golgi transport vesicle membrane",
                            "go_id": "GO:0012507",
                            "evidence_code": "IEA",
                            "qualifier": "located_in",
                        }
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "6p22.1"}],
            },
            "query": ["3105"],
        },
    ],
    "total_count": 3,
}

TEXT_SEARCH_BREAST_CANCER = {
    "reports": [
        {
            "gene": {
                "gene_id": "672",
                "symbol": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_005905.2",
                            "range": [{"begin": "92501", "end": "173689", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["17"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:1100"},
                "swiss_prot_accessions": ["P38398"],
                "ensembl_gene_ids": ["ENSG00000012048"],
                "omim_ids": ["113705"],
                "synonyms": [
                    "IRIS",
                    "PSCP",
                    "BRCAI",
                    "BRCC1",
                    "FANCS",
                    "PNCA4",
                    "RNF53",
                    "BROVCA1",
                    "PPP1R53",
                ],
                "alternate_names": [
                    "BRCA1/BRCA2-containing complex, subunit 1",
                    "Fanconi anemia, complementation group S",
                    "RING finger protein 53",
                    "breast and ovarian cancer susceptibility protein 1",
                    "breast cancer 1, early onset",
                    "breast cancer type 1 susceptibility protein",
                    "early onset breast cancer 1",
                    "protein phosphatase 1, regulatory subunit 53",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.11",
                                "sequence_name": "17",
                                "genomic_range": {
                                    "begin": "43044295",
                                    "end": "43170327",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 368,
                "protein_count": 368,
                "transcript_type_counts": [{"type": "PROTEIN_CODING", "count": 368}],
                "gene_groups": [{"id": "672", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "This gene encodes a 190 kD nuclear "
                        "phosphoprotein that plays a role in "
                        "maintaining genomic stability, and it also "
                        "acts as a tumor suppressor. The BRCA1 gene "
                        "contains 22 exons spanning about 110 kb of "
                        "DNA. The encoded protein combines with "
                        "other tumor suppressors, DNA damage "
                        "sensors, and signal transducers to form a "
                        "large multi-subunit protein complex known "
                        "as the BRCA1-associated genome "
                        "surveillance complex (BASC). This gene "
                        "product associates with RNA polymerase II, "
                        "and through the C-terminal domain, also "
                        "interacts with histone deacetylase "
                        "complexes. This protein thus plays a role "
                        "in transcription, DNA repair of "
                        "double-stranded breaks, and recombination. "
                        "Mutations in this gene are responsible for "
                        "approximately 40% of inherited breast "
                        "cancers and more than 80% of inherited "
                        "breast and ovarian cancers. Alternative "
                        "splicing plays a role in modulating the "
                        "subcellular localization and physiological "
                        "function of this gene. Many alternatively "
                        "spliced transcript variants, some of which "
                        "are disease-associated mutations, have "
                        "been described for this gene, but the "
                        "full-length natures of only some of these "
                        "variants has been described. A related "
                        "pseudogene, which is also located on "
                        "chromosome 17, has been identified. "
                        "[provided by RefSeq, May 2020]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        }
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IEA",
                            "qualifier": "involved_in",
                        }
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IBA",
                            "qualifier": "part_of",
                        }
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "17q21.31"}],
            },
            "query": ["breast cancer type 1 susceptibility protein"],
        },
        {
            "gene": {
                "gene_id": "675",
                "symbol": "BRCA2",
                "description": "BRCA2 DNA repair associated",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "plus",
                "reference_standards": [
                    {
                        "gene_range": {
                            "accession_version": "NG_012772.3",
                            "range": [{"begin": "5001", "end": "89193", "orientation": "plus"}],
                        },
                        "type": "REFSEQ_GENE",
                    }
                ],
                "chromosomes": ["13"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:1101"},
                "swiss_prot_accessions": ["P51587"],
                "ensembl_gene_ids": ["ENSG00000139618"],
                "omim_ids": ["600185"],
                "synonyms": [
                    "FAD",
                    "FACD",
                    "FAD1",
                    "GLM3",
                    "BRCC2",
                    "FANCD",
                    "PNCA2",
                    "FANCD1",
                    "XRCC11",
                    "BROVCA2",
                ],
                "alternate_names": [
                    "BRCA1/BRCA2-containing complex, subunit 2",
                    "BRCA2 DNA repair associated protein",
                    "DNA repair-associated BRCA2",
                    "Fanconi anemia group D1 protein",
                    "breast and ovarian cancer susceptibility gene, early onset",
                    "breast and ovarian cancer susceptibility protein 2",
                    "breast cancer 2 tumor suppressor",
                    "breast cancer 2, early onset",
                    "breast cancer type 2 susceptibility protein",
                    "mutant BRCA2",
                    "mutant DNA repair-associated protein 2",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000013.11",
                                "sequence_name": "13",
                                "genomic_range": {
                                    "begin": "32315077",
                                    "end": "32400268",
                                    "orientation": "plus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 7,
                "protein_count": 6,
                "transcript_type_counts": [
                    {"type": "PROTEIN_CODING", "count": 6},
                    {"type": "NON_CODING", "count": 1},
                ],
                "gene_groups": [{"id": "675", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "The product of this gene in involved in "
                        "maintenance of genome stability. It is "
                        "involved in double-strand break repair "
                        "pathways during mitotic and meiotic "
                        "homologous recombination and functions in "
                        "protecting DNA replication forks. The "
                        "encoded protein contains sites for "
                        "interactions with PALB2 and EMSY and an "
                        "N-terminal DNA binding domain. It also "
                        "contains a RAD51 binding domain with "
                        "multiple components. It has multiple BRC "
                        "repeats, an alpha helix domain, "
                        "oligonucleotide binding folds, and a "
                        "tower-like domain. It has a nuclear "
                        "localization signal and a phosphorylation "
                        "site for cyclin-dependent kinase. The "
                        "C-terminus of the protein can bind "
                        "single-stranded and double-stranded DNA. "
                        "The product of this gene interacts with "
                        "multiple proteins, including RAD51. It is "
                        "involved in recruiting RAD51 filaments to "
                        "DNA double-strand break sites and also in "
                        "cytoplasmic division. It also acts as a "
                        "tumor suppressor. Mutations in this gene "
                        "or decreased expression have been "
                        "implicated in multiple tumor types, "
                        "including breast, ovarian, pancreatic, "
                        "prostate and other cancers. [provided by "
                        "RefSeq, May 2026]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "double-stranded DNA binding",
                            "go_id": "GO:0003690",
                            "evidence_code": "IDA",
                            "qualifier": "enables",
                            "reference": {"pmids": ["37499663"]},
                        }
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IDA",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["12442171"]},
                        }
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA2-MAGE-D1 complex",
                            "go_id": "GO:0033593",
                            "evidence_code": "IDA",
                            "qualifier": "part_of",
                            "reference": {"pmids": ["15930293"]},
                        }
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "13q13.1"}],
            },
            "query": ["breast cancer type 2 susceptibility protein"],
        },
        {
            "gene": {
                "gene_id": "1485",
                "symbol": "CTAG1B",
                "description": "cancer/testis antigen 1B",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "chromosomes": ["X"],
                "nomenclature_authority": {"authority": "HGNC", "identifier": "HGNC:2491"},
                "swiss_prot_accessions": ["P78358"],
                "ensembl_gene_ids": ["ENSG00000184033"],
                "omim_ids": ["300156"],
                "synonyms": ["CTAG", "ESO1", "CT6.1", "CTAG1", "LAGE-2", "LAGE2B", "NY-ESO-1"],
                "alternate_names": [
                    "New York esophageal squamous cell carcinoma 1",
                    "autoimmunogenic cancer/testis antigen NY-ESO-1",
                    "cancer antigen 3",
                    "cancer/testis antigen 1",
                    "cancer/testis antigen 6.1",
                    "l antigen family member 2",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001405.40",
                        "assembly_name": "GRCh38.p14",
                        "annotation_name": "GCF_000001405.40-RS_2025_08",
                        "annotation_release_date": "2025-08-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000023.11",
                                "sequence_name": "X",
                                "genomic_range": {
                                    "begin": "154617609",
                                    "end": "154619282",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 1,
                "protein_count": 1,
                "transcript_type_counts": [{"type": "PROTEIN_CODING", "count": 1}],
                "summary": [
                    {
                        "description": "The protein encoded by this gene is an "
                        "antigen that is overexpressed in many "
                        "cancers but that is also expressed in "
                        "normal testis. This gene is found in a "
                        "duplicated region of the X-chromosome and "
                        "therefore has a neighboring gene of "
                        "identical sequence. [provided by RefSeq, "
                        "Jan 2012]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "GOA",
                    "molecular_functions": [
                        {
                            "name": "identical protein binding",
                            "go_id": "GO:0042802",
                            "evidence_code": "IPI",
                            "qualifier": "enables",
                            "reference": {"pmids": ["32296183"]},
                        }
                    ],
                    "cellular_components": [
                        {
                            "name": "cytoplasm",
                            "go_id": "GO:0005737",
                            "evidence_code": "IDA",
                            "qualifier": "located_in",
                            "reference": {"pmids": ["31429579"]},
                        }
                    ],
                },
                "map_locations": [{"map_type": "Cytogenetic", "map_value": "Xq28"}],
            },
            "query": ["cancer/testis antigen 1", "cancer/testis antigen 1b"],
        },
    ],
    "total_count": 63,
    "next_page_token": "eNrj4o02MTUz1lEwMrUwNY0FABVTAvc",
}

GENE_MOUSE_BRCA1 = {
    "reports": [
        {
            "gene": {
                "gene_id": "12189",
                "symbol": "Brca1",
                "description": "breast cancer 1, early onset",
                "tax_id": "10090",
                "taxname": "Mus musculus",
                "common_name": "house mouse",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "chromosomes": ["11"],
                "nomenclature_authority": {"authority": "MGI", "identifier": "MGI:104537"},
                "swiss_prot_accessions": ["P48754"],
                "ensembl_gene_ids": ["ENSMUSG00000017146"],
                "alternate_names": [
                    "RING-type E3 ubiquitin transferase BRCA1",
                    "breast and ovarian cancer susceptibility protein",
                    "breast cancer associated 1",
                    "breast cancer type 1 susceptibility protein homolog",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001635.27",
                        "assembly_name": "GRCm39",
                        "annotation_name": "GCF_000001635.27-RS_2024_02",
                        "annotation_release_date": "2024-02-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000077.7",
                                "sequence_name": "11",
                                "genomic_range": {
                                    "begin": "101379587",
                                    "end": "101442808",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 6,
                "protein_count": 5,
                "transcript_type_counts": [
                    {"type": "PROTEIN_CODING", "count": 1},
                    {"type": "PROTEIN_CODING_MODEL", "count": 4},
                    {"type": "NON_CODING_MODEL", "count": 1},
                ],
                "gene_groups": [{"id": "672", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "Enables damaged DNA binding activity; "
                        "transcription cis-regulatory region "
                        "binding activity; and transcription "
                        "coactivator activity. Involved in "
                        "double-strand break repair and positive "
                        "regulation of transcription by RNA "
                        "polymerase II. Acts upstream of with a "
                        "positive effect on negative regulation of "
                        "gene expression via chromosomal CpG island "
                        "methylation. Acts upstream of or within "
                        "several processes, including centrosome "
                        "cycle; mitotic G2/M transition checkpoint; "
                        "and random inactivation of X chromosome. "
                        "Located in XY body; condensed nuclear "
                        "chromosome; and cytoplasm. Is expressed in "
                        "several structures, including alimentary "
                        "system; brain; genitourinary system; "
                        "hemolymphoid system; and integumental "
                        "system. Used to study breast cancer. Human "
                        "ortholog(s) of this gene implicated in "
                        "several diseases, including Fanconi anemia "
                        "complementation group S; breast cancer "
                        "(multiple); cervix uteri carcinoma in "
                        "situ; gastrointestinal system cancer "
                        "(multiple); and reproductive organ cancer "
                        "(multiple). Orthologous to human BRCA1 "
                        "(BRCA1 DNA repair associated). [provided "
                        "by Alliance of Genome Resources, Jun "
                        "2026]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "MGI",
                    "molecular_functions": [
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        },
                        {
                            "name": "RNA binding",
                            "go_id": "GO:0003723",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        },
                        {
                            "name": "RNA binding",
                            "go_id": "GO:0003723",
                            "evidence_code": "ISO",
                            "qualifier": "enables",
                            "reference": {"pmids": ["12419249"]},
                        },
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IEA",
                            "qualifier": "involved_in",
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IMP",
                            "qualifier": "acts_upstream_of_or_within",
                            "reference": {"pmids": ["23271346"]},
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "NAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["16651405"]},
                        },
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IBA",
                            "qualifier": "part_of",
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IEA",
                            "qualifier": "part_of",
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "ISO",
                            "qualifier": "part_of",
                        },
                    ],
                },
                "map_locations": [
                    {"map_type": "Genetic", "map_value": "11 65.18 cM"},
                    {"map_type": "Cytogenetic", "map_value": "11 D"},
                ],
            },
            "query": ["Brca1"],
        }
    ],
    "total_count": 1,
}

PRODUCT_REPORT_BRCA1 = {
    "reports": [
        {
            "product": {
                "gene_id": "672",
                "symbol": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "tax_id": "9606",
                "taxname": "Homo sapiens",
                "common_name": "human",
                "type": "PROTEIN_CODING",
                "transcripts": [
                    {
                        "accession_version": "NM_001407571.1",
                        "name": "transcript variant 6",
                        "length": 7152,
                        "protein": {
                            "accession_version": "NP_001394500.1",
                            "name": "breast cancer type 1 susceptibility protein",
                            "length": 1792,
                            "isoform_name": "isoform 6",
                        },
                        "type": "PROTEIN_CODING",
                    },
                    {
                        "accession_version": "NM_007294.4",
                        "name": "transcript variant 1",
                        "length": 7088,
                        "ensembl_transcript": "ENST00000357654.9",
                        "protein": {
                            "accession_version": "NP_009225.1",
                            "name": "breast cancer type 1 susceptibility protein",
                            "length": 1863,
                            "isoform_name": "isoform 1",
                            "ensembl_protein": "ENSP00000350283.3",
                        },
                        "type": "PROTEIN_CODING",
                        "select_category": "MANE_SELECT",
                    },
                    {
                        "accession_version": "NM_001407581.1",
                        "name": "transcript variant 7",
                        "length": 7154,
                        "ensembl_transcript": "ENST00000644379.3",
                        "protein": {
                            "accession_version": "NP_001394510.1",
                            "name": "breast cancer type 1 susceptibility protein",
                            "length": 1885,
                            "isoform_name": "isoform 7",
                            "ensembl_protein": "ENSP00000496570.2",
                        },
                        "type": "PROTEIN_CODING",
                    },
                    {
                        "accession_version": "NM_001407582.1",
                        "name": "transcript variant 8",
                        "length": 7243,
                        "protein": {
                            "accession_version": "NP_001394511.1",
                            "name": "breast cancer type 1 susceptibility protein",
                            "length": 1885,
                            "isoform_name": "isoform 7",
                        },
                        "type": "PROTEIN_CODING",
                    },
                ],
                "transcript_count": 368,
                "protein_count": 368,
                "transcript_type_counts": [{"type": "PROTEIN_CODING", "count": 368}],
            },
            "query": ["672"],
        }
    ],
    "total_count": 1,
}

ORTHOLOGS_BRCA1_MOUSE = {
    "reports": [
        {
            "gene": {
                "gene_id": "12189",
                "symbol": "Brca1",
                "description": "breast cancer 1, early onset",
                "tax_id": "10090",
                "taxname": "Mus musculus",
                "common_name": "house mouse",
                "type": "PROTEIN_CODING",
                "orientation": "minus",
                "chromosomes": ["11"],
                "nomenclature_authority": {"authority": "MGI", "identifier": "MGI:104537"},
                "swiss_prot_accessions": ["P48754"],
                "ensembl_gene_ids": ["ENSMUSG00000017146"],
                "alternate_names": [
                    "RING-type E3 ubiquitin transferase BRCA1",
                    "breast and ovarian cancer susceptibility protein",
                    "breast cancer associated 1",
                    "breast cancer type 1 susceptibility protein homolog",
                ],
                "annotations": [
                    {
                        "assembly_accession": "GCF_000001635.27",
                        "assembly_name": "GRCm39",
                        "annotation_name": "GCF_000001635.27-RS_2024_02",
                        "annotation_release_date": "2024-02-01",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000077.7",
                                "sequence_name": "11",
                                "genomic_range": {
                                    "begin": "101379587",
                                    "end": "101442808",
                                    "orientation": "minus",
                                },
                            }
                        ],
                    }
                ],
                "transcript_count": 6,
                "protein_count": 5,
                "transcript_type_counts": [
                    {"type": "PROTEIN_CODING", "count": 1},
                    {"type": "PROTEIN_CODING_MODEL", "count": 4},
                    {"type": "NON_CODING_MODEL", "count": 1},
                ],
                "gene_groups": [{"id": "672", "method": "NCBI Ortholog"}],
                "summary": [
                    {
                        "description": "Enables damaged DNA binding activity; "
                        "transcription cis-regulatory region "
                        "binding activity; and transcription "
                        "coactivator activity. Involved in "
                        "double-strand break repair and positive "
                        "regulation of transcription by RNA "
                        "polymerase II. Acts upstream of with a "
                        "positive effect on negative regulation of "
                        "gene expression via chromosomal CpG island "
                        "methylation. Acts upstream of or within "
                        "several processes, including centrosome "
                        "cycle; mitotic G2/M transition checkpoint; "
                        "and random inactivation of X chromosome. "
                        "Located in XY body; condensed nuclear "
                        "chromosome; and cytoplasm. Is expressed in "
                        "several structures, including alimentary "
                        "system; brain; genitourinary system; "
                        "hemolymphoid system; and integumental "
                        "system. Used to study breast cancer. Human "
                        "ortholog(s) of this gene implicated in "
                        "several diseases, including Fanconi anemia "
                        "complementation group S; breast cancer "
                        "(multiple); cervix uteri carcinoma in "
                        "situ; gastrointestinal system cancer "
                        "(multiple); and reproductive organ cancer "
                        "(multiple). Orthologous to human BRCA1 "
                        "(BRCA1 DNA repair associated). [provided "
                        "by Alliance of Genome Resources, Jun "
                        "2026]"
                    }
                ],
                "gene_ontology": {
                    "assigned_by": "MGI",
                    "molecular_functions": [
                        {
                            "name": "DNA binding",
                            "go_id": "GO:0003677",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        },
                        {
                            "name": "RNA binding",
                            "go_id": "GO:0003723",
                            "evidence_code": "IEA",
                            "qualifier": "enables",
                        },
                        {
                            "name": "RNA binding",
                            "go_id": "GO:0003723",
                            "evidence_code": "ISO",
                            "qualifier": "enables",
                            "reference": {"pmids": ["12419249"]},
                        },
                    ],
                    "biological_processes": [
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IEA",
                            "qualifier": "involved_in",
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "IMP",
                            "qualifier": "acts_upstream_of_or_within",
                            "reference": {"pmids": ["23271346"]},
                        },
                        {
                            "name": "DNA damage response",
                            "go_id": "GO:0006974",
                            "evidence_code": "NAS",
                            "qualifier": "involved_in",
                            "reference": {"pmids": ["16651405"]},
                        },
                    ],
                    "cellular_components": [
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IBA",
                            "qualifier": "part_of",
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "IEA",
                            "qualifier": "part_of",
                        },
                        {
                            "name": "BRCA1-A complex",
                            "go_id": "GO:0070531",
                            "evidence_code": "ISO",
                            "qualifier": "part_of",
                        },
                    ],
                },
                "map_locations": [
                    {"map_type": "Genetic", "map_value": "11 65.18 cM"},
                    {"map_type": "Cytogenetic", "map_value": "11 D"},
                ],
            },
            "query": ["672"],
        }
    ],
    "total_count": 1,
}

EMPTY_RESULT = {}

ERROR_BAD_REQUEST = {
    "error": "Bad Request",
    "code": 400,
    "message": "Invalid argument type ('parameter: gene_ids') provided. (For more help, see the "
    "NCBI Datasets Documentation at https://www.ncbi.nlm.nih.gov/datasets/docs/)",
}
