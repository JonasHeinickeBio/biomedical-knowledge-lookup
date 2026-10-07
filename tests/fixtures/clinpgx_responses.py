"""Trimmed real ClinPGx API responses captured live on 2026-10-07 for ClinPGxAdapter tests.

Bulky text (history, literature, markdown) was dropped; field names and values are as served.
"""

GENE_SEARCH = {
    "data": [
        {
            "objCls": "Gene",
            "id": "PA128",
            "symbol": "CYP2D6",
            "name": "cytochrome P450 family 2 subfamily D member 6",
            "alleleFile": "CYP2D6_allele_definition_table.xlsx",
            "alleleFunctionSource": "CPIC",
            "amp": True,
            "buildVersion": "GRCh38.p7",
            "cbStart": "q13.1",
            "cbStop": "q13.2",
            "chr": {"objCls": "Chromosome", "id": "PA525", "name": "chr22"},
            "chrStartPosB37": 42522501,
            "chrStartPosB38": 42125531,
            "chrStopPosB37": 42526883,
            "chrStopPosB38": 42130881,
            "cpicGene": True,
            "hasNonStandardHaplotypes": False,
            "hideHaplotypes": False,
            "history": [],
            "pharmVarGene": True,
            "strand": "minus",
            "usesStarAlleles": True,
            "vipCitation": {
                "id": 7144344,
                "title": "Cytochrome P450 2D6.",
                "_sameAs": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4373606",
                "authors": ["Owen Ryan P", "Sangkuhl Katrin", "Klein Teri E", "Altman Russ B"],
                "crossReferences": [
                    {
                        "id": 1449247412,
                        "resource": "PubMed Central",
                        "resourceId": "PMC4373606",
                        "_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4373606",
                    },
                    {
                        "id": 562114580,
                        "resource": "PubMed",
                        "resourceId": "19512959",
                        "_url": "https://www.ncbi.nlm.nih.gov/pubmed/19512959",
                    },
                    {
                        "id": 1449247413,
                        "resource": "DOI",
                        "resourceId": "10.1097/FPC.0b013e32832e0e97",
                        "_url": "https://doi.org/10.1097%2FFPC.0b013e32832e0e97",
                    },
                ],
                "day": -1,
                "journal": "Pharmacogenetics and genomics",
                "month": 7,
                "objCls": "Literature",
                "page": "559-62",
                "pediatric": False,
                "pgkbPublication": True,
                "pubDate": "2009-07-01",
                "pubmedMeshTerms": [],
                "terms": [
                    {
                        "id": 1454108640,
                        "resource": "ClinPGx Tags",
                        "term": "PharmGKB",
                        "termId": "pgkbTags:1454108640",
                    },
                    {
                        "id": 1451577482,
                        "resource": "PGx Paper Types",
                        "term": "Review",
                        "termId": "pgxPaperTypes:1451577482",
                    },
                ],
                "type": "Literature",
                "volume": "19",
                "year": 2009,
            },
            "vipId": "PA166170264",
            "vipSummary": {
                "id": 1448995144,
                "html": "<p>CYP2D6 is one of the key pharmacogenes involved in "
                "implementation of pharmacogenomics. It is highly "
                "polymorphic and involved in the metabolism of up to 25% of "
                "the drugs that are in common use in the clinic.</p>\n"
                "<ul>\n"
                "<li>It is involved in guidelines for <a "
                'href="/guidelineAnnotation/PA166104996">codeine</a> and '
                "other opioids, antidepressants, and tamoxifen <a "
                'href="/gene/PA128/prescribingInfo#guideline-annotations">go '
                "to list of all guidelines with CYP2D6</a>.</li>\n"
                '<li>the nomenclature has been set by <a rel="noopener '
                'noreferrer" href="https://www.pharmvar.org/gene/CYP2D6" '
                'target="_blank">PharmVar</a>.</li>\n'
                "<li>the AMP tier 1 alleles are <a "
                'href="/allele/PA165816577">CYP2D6*2</a>, <a '
                'href="/allele/PA165816578">CYP2D6*3</a>, <a '
                'href="/allele/PA165816579">CYP2D6*4</a>, <a '
                'href="/allele/PA165948092">CYP2D6*5</a>, <a '
                'href="/allele/PA165816581">CYP2D6*6</a>, <a '
                'href="/allele/PA165948317">CYP2D6*9</a>, <a '
                'href="/allele/PA165816582">CYP2D6*10</a>, <a '
                'href="/allele/PA165816583">CYP2D6*17</a>, <a '
                'href="/allele/PA165948318">CYP2D6*29</a>, <a '
                'href="/allele/PA165816584">CYP2D6*41</a>, CYP2D6 '
                "duplications and other copy number variants <a "
                'href="/ampAllelesToTest">see all alleles on the AMP '
                "recommended to test list</a>.</li>\n"
                "<li>See the <a "
                'href="/page/cyp2d6RefMaterials">Gene-specific Information '
                "Tables</a> for Allele Definitions (for which variants "
                "comprise which star alleles), Allele function assignments "
                "(normal function, no function, decreased or increased "
                "function etc) and Diplotype-Phenotype Table (for how the "
                "alleles combine to form metabolizer phenotypes for PM, NM, "
                "UM).</li>\n"
                "<li>CYP2D6 is the most studied CYP for phenoconversion, "
                "where a drug-drug interaction mimics a metabolizer "
                'phenotype. <a href="/chemical/PA450801">paroxetine</a>, <a '
                'href="/chemical/PA449673">fluoxetine</a> and <a '
                'href="/chemical/PA448687">bupropion</a> are strong '
                'inhibitors of CYP2D6 as per <a rel="noopener noreferrer" '
                'href="https://drug-interactions.medicine.iu.edu/MainTable.aspx" '
                'target="_blank">Flockhart Table</a>.</li>\n'
                "</ul>\n",
            },
            "vipTier": "Tier 1",
        }
    ],
    "status": "success",
}

GENE_MAX = {
    "data": {
        "objCls": "Gene",
        "id": "PA128",
        "symbol": "CYP2D6",
        "name": "cytochrome P450 family 2 subfamily D member 6",
        "alleleFile": "CYP2D6_allele_definition_table.xlsx",
        "alleleFunctionSource": "CPIC",
        "altNames": {
            "synonym": [
                "cytochrome P450 family 2 subfamily D member 6",
                "cytochrome P450, family 2, subfamily D, polypeptide 6",
            ],
            "symbol": [
                "CPD6",
                "CYP2D",
                "CYP2D7AP",
                "CYP2D7BP",
                "CYP2D7P2",
                "CYP2D8P2",
                "CYP2DL1",
                "P450-DB1",
                "P450C2D",
            ],
        },
        "amp": True,
        "buildVersion": "GRCh38.p7",
        "cbStart": "q13.1",
        "cbStop": "q13.2",
        "chr": {"objCls": "Chromosome", "id": "PA525", "name": "chr22", "version": 3},
        "chrStartPosB37": 42522501,
        "chrStartPosB38": 42125531,
        "chrStopPosB37": 42526883,
        "chrStopPosB38": 42130881,
        "cpicGene": True,
        "crossReferences": [
            {
                "id": 553242505,
                "resource": "Comparative Toxicogenomics Database",
                "resourceId": "1565",
                "_url": "http://ctdbase.org/detail.go?type=gene&acc=1565",
                "version": 0,
            },
            {
                "id": 132256032,
                "resource": "Ensembl",
                "resourceId": "ENSG00000100197",
                "_url": "https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000100197",
                "version": 0,
            },
            {
                "id": 73375,
                "resource": "GenAtlas",
                "resourceId": "CYP2D6",
                "_url": "http://genatlas.medecine.univ-paris5.fr/fiche.php?symbol=CYP2D6",
                "version": 1,
            },
            {
                "id": 1445332056,
                "resource": "GenBank",
                "resourceId": "AY545216.1",
                "_url": "https://www.ncbi.nlm.nih.gov/nuccore/AY545216.1",
                "version": 0,
            },
            {
                "id": 88303,
                "resource": "GeneCard",
                "resourceId": "CYP2D6",
                "_url": "https://www.genecards.org/cgi-bin/carddisp.pl?gene=CYP2D6",
                "version": 1,
            },
            {
                "id": 605873023,
                "resource": "HGNC",
                "resourceId": "HGNC:2625",
                "_url": "https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC%3A2625",
                "version": 1,
            },
            {
                "id": 605873080,
                "resource": "HumanCyc Gene",
                "resourceId": "HS01997",
                "_url": "http://biocyc.org/HUMAN/NEW-IMAGE?object=HS01997",
                "version": 0,
            },
            {
                "id": 560877840,
                "resource": "ModBase",
                "resourceId": "P10635",
                "_url": "http://salilab.org/modbase/search?modelflag=longest&databaseID=P10635",
                "version": 0,
            },
            {
                "id": 10749,
                "resource": "NCBI Gene",
                "resourceId": "1565",
                "_url": "https://www.ncbi.nlm.nih.gov/gene/1565",
                "version": 1,
            },
            {
                "id": 717,
                "resource": "OMIM",
                "resourceId": "124030",
                "_url": "https://omim.org/entry/124030",
                "version": 1,
            },
            {
                "id": 560556323,
                "resource": "OMIM",
                "resourceId": "608902",
                "_url": "https://omim.org/entry/608902",
                "version": 0,
            },
            {
                "id": 1451280333,
                "resource": "PharmVar Gene",
                "resourceId": "CYP2D6",
                "_url": "https://www.pharmvar.org/gene/CYP2D6",
                "version": 0,
            },
            {
                "id": 1451167850,
                "name": "NG_008376.4",
                "resource": "RefSeq DNA",
                "resourceId": "NG_008376.4",
                "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NG_008376.4",
                "version": 0,
            },
            {
                "id": 37278,
                "resource": "RefSeq Protein",
                "resourceId": "NP_000097",
                "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NP_000097",
                "version": 1,
            },
            {
                "id": 123170196,
                "resource": "RefSeq Protein",
                "resourceId": "NP_001020332",
                "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NP_001020332",
                "version": 1,
            },
            {
                "id": 46353,
                "resource": "RefSeq RNA",
                "resourceId": "NM_000106",
                "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NM_000106",
                "version": 1,
            },
            {
                "id": 123170193,
                "resource": "RefSeq RNA",
                "resourceId": "NM_001025161",
                "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NM_001025161",
                "version": 1,
            },
            {
                "id": 121670,
                "resource": "UCSC Genome Browser",
                "resourceId": "NM_000106",
                "_url": "https://genome.ucsc.edu/cgi-bin/hgTracks?Submit=Submit&position=NM_000106",
                "version": 1,
            },
            {
                "id": 605873078,
                "name": "Q6NWU0_HUMAN",
                "resource": "UniProtKB",
                "resourceId": "Q6NWU0",
                "_url": "https://www.uniprot.org/uniprot/Q6NWU0",
                "version": 1,
            },
            {
                "id": 605873076,
                "name": "Q6NXU8_HUMAN",
                "resource": "UniProtKB",
                "resourceId": "Q6NXU8",
                "_url": "https://www.uniprot.org/uniprot/Q6NXU8",
                "version": 1,
            },
        ],
        "hasNonStandardHaplotypes": False,
        "hideHaplotypes": False,
        "pharmVarGene": True,
        "strand": "minus",
        "usesStarAlleles": True,
        "version": 7891,
        "vipId": "PA166170264",
        "vipSummary": {
            "id": 1448995144,
            "html": "<p>CYP2D6 is one of the key pharmacogenes involved in "
            "implementation of pharmacogenomics. It is highly polymorphic "
            "and involved in the metabolism of up to 25% of the drugs "
            "that are in common use in the clinic.</p>\n"
            "<ul>\n"
            "<li>It is involved in guidelines for <a "
            'href="/guidelineAnnotation/PA166104996">codeine</a> and '
            "other opioids, antidepressants, and tamoxifen <a "
            'href="/gene/PA128/prescribingInfo#guideline-annotations">go '
            "to list of all guidelines with CYP2D6</a>.</li>\n"
            '<li>the nomenclature has been set by <a rel="noopener '
            'noreferrer" href="https://www.pharmvar.org/gene/CYP2D6" '
            'target="_blank">PharmVar</a>.</li>\n'
            "<li>the AMP tier 1 alleles are <a "
            'href="/allele/PA165816577">CYP2D6*2</a>, <a '
            'href="/allele/PA165816578">CYP2D6*3</a>, <a '
            'href="/allele/PA165816579">CYP2D6*4</a>, <a '
            'href="/allele/PA165948092">CYP2D6*5</a>, <a '
            'href="/allele/PA165816581">CYP2D6*6</a>, <a '
            'href="/allele/PA165948317">CYP2D6*9</a>, <a '
            'href="/allele/PA165816582">CYP2D6*10</a>, <a '
            'href="/allele/PA165816583">CYP2D6*17</a>, <a '
            'href="/allele/PA165948318">CYP2D6*29</a>, <a '
            'href="/allele/PA165816584">CYP2D6*41</a>, CYP2D6 '
            "duplications and other copy number variants <a "
            'href="/ampAllelesToTest">see all alleles on the AMP '
            "recommended to test list</a>.</li>\n"
            '<li>See the <a href="/page/cyp2d6RefMaterials">Gene-specific '
            "Information Tables</a> for Allele Definitions (for which "
            "variants comprise which star alleles), Allele function "
            "assignments (normal function, no function, decreased or "
            "increased function etc) and Diplotype-Phenotype Table (for "
            "how the alleles combine to form metabolizer phenotypes for "
            "PM, NM, UM).</li>\n"
            "<li>CYP2D6 is the most studied CYP for phenoconversion, "
            "where a drug-drug interaction mimics a metabolizer "
            'phenotype. <a href="/chemical/PA450801">paroxetine</a>, <a '
            'href="/chemical/PA449673">fluoxetine</a> and <a '
            'href="/chemical/PA448687">bupropion</a> are strong '
            'inhibitors of CYP2D6 as per <a rel="noopener noreferrer" '
            'href="https://drug-interactions.medicine.iu.edu/MainTable.aspx" '
            'target="_blank">Flockhart Table</a>.</li>\n'
            "</ul>\n",
        },
        "vipTier": "Tier 1",
    },
    "status": "success",
}

CHEMICAL_SEARCH = {
    "data": [
        {
            "objCls": "Chemical",
            "id": "PA449088",
            "name": "codeine",
            "inChi": "InChI=1S/C18H21NO3/c1-19-8-7-18-11-4-5-13(20)17(18)22-16-14(21-2)6-3-10(15(16)18)9-12(11)19/h3-6,11-13,17,20H,7-9H2,1-2H3/t11-,12+,13-,17-,18-/m0/s1",
            "pediatric": False,
            "smiles": "CN1CC[C@]23[C@@H]4[C@H]1CC5=C2C(=C(C=C5)OC)O[C@H]3[C@H](C=C4)O",
            "types": ["Prodrug"],
        }
    ],
    "status": "success",
}

CHEMICAL_MAX = {
    "data": {
        "objCls": "Chemical",
        "id": "PA449088",
        "name": "codeine",
        "altNames": {
            "generic": [
                "Codeine anhydrous",
                "L-Codeine",
                "Methylmorphine",
                "Morphine monomethyl ether",
                "Norcodeine, N-Methyl",
                "Norcodine, N-Methyl",
            ],
            "trade": ["Codicept", "Coducept"],
        },
        "components": [],
        "linkOuts": [
            {
                "id": 1452175274,
                "name": "codeine, combinations excl. psycholeptics",
                "resource": "ATC",
                "resourceId": "N02AA59",
                "_url": "https://www.whocc.no/atc_ddd_index/?showdescription=yes&code=N02AA59",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175275,
                "name": "codeine, combinations with psycholeptics",
                "resource": "ATC",
                "resourceId": "N02AA79",
                "_url": "https://www.whocc.no/atc_ddd_index/?showdescription=yes&code=N02AA79",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175276,
                "name": "codeine",
                "resource": "ATC",
                "resourceId": "R05DA04",
                "_url": "https://www.whocc.no/atc_ddd_index/?showdescription=yes&code=R05DA04",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175260,
                "resource": "ChEBI",
                "resourceId": "CHEBI:16714",
                "_url": "http://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI%3A16714",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175262,
                "resource": "ChemSpider",
                "resourceId": "4447447",
                "_url": "http://www.chemspider.com/Chemical-Structure.4447447.html",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175263,
                "resource": "ClinicalTrials.gov",
                "resourceId": "NCT01050400",
                "_url": "https://clinicaltrials.gov/ct2/show/NCT01050400",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175264,
                "resource": "ClinicalTrials.gov",
                "resourceId": "NCT01788254",
                "_url": "https://clinicaltrials.gov/ct2/show/NCT01788254",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175280,
                "name": "Analgesics",
                "resource": "ClinPGx Tags",
                "resourceId": "pgkbTags:1451995442",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175265,
                "resource": "DrugBank",
                "resourceId": "DB00318",
                "_url": "https://www.drugbank.ca/drugs/DB00318",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175266,
                "resource": "IUPHAR Ligand",
                "resourceId": "1673",
                "_url": "http://www.guidetopharmacology.org/GRAC/LigandDisplayForward?tab=summary&ligandId=1673",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175267,
                "resource": "KEGG Compound",
                "resourceId": "C06174",
                "_url": "https://www.kegg.jp/entry/C06174",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175273,
                "name": "Codeine",
                "resource": "MeSH",
                "resourceId": "D003061",
                "_url": "https://id.nlm.nih.gov/mesh/D003061",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175279,
                "name": "CODEINE",
                "resource": "NDF-RT",
                "resourceId": "N0000145894",
                "_url": "https://purl.bioontology.org/ontology/NDFRT/N0000145894",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175268,
                "resource": "PubChem Compound",
                "resourceId": "5284371",
                "_url": "https://pubchem.ncbi.nlm.nih.gov/compound/5284371",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175269,
                "resource": "PubChem Substance",
                "resourceId": "149398",
                "_url": "https://pubchem.ncbi.nlm.nih.gov/substance/149398",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175270,
                "resource": "PubChem Substance",
                "resourceId": "46507764",
                "_url": "https://pubchem.ncbi.nlm.nih.gov/substance/46507764",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175278,
                "name": "Codeine",
                "resource": "RxNorm",
                "resourceId": "2670",
                "_url": "https://purl.bioontology.org/ontology/RXNORM/2670",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175277,
                "name": "Codeine",
                "resource": "UMLS",
                "resourceId": "C0009214",
                "_url": "http://linkedlifedata.com/resource/umls/id/C0009214",
                "status": "Valid",
                "version": 0,
            },
            {
                "id": 1452175272,
                "resource": "URL",
                "resourceId": "http://en.wikipedia.org/wiki/Codeine",
                "_url": "http://en.wikipedia.org/wiki/Codeine",
                "status": "Valid",
                "version": 0,
            },
        ],
        "metabolites": [
            {
                "objCls": "Chemical",
                "id": "PA166131341",
                "name": "codeine-6-glucuronide",
                "version": 5,
            },
            {"objCls": "Chemical", "id": "PA450550", "name": "morphine", "version": 16},
            {"objCls": "Chemical", "id": "PA166131386", "name": "norcodeine", "version": 5},
        ],
        "pediatric": False,
        "types": ["Prodrug"],
        "version": 15,
    },
    "status": "success",
}

CHEMICAL_MIN = {
    "data": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
    "status": "success",
}

VARIANT_SEARCH = {
    "data": [
        {
            "objCls": "Variant",
            "id": "PA166156104",
            "symbol": "rs3892097",
            "name": "rs3892097",
            "changeClassification": "Splice Acceptor",
            "clinicalSignificance": "drug-response",
            "history": [],
            "lastUpdatedFromDbsnp": "2020-06-18T20:49:03.110258-07:00",
            "obsolete": False,
            "rare": False,
            "raritySource": "gnomAD v4",
            "terms": [],
            "type": "SNP",
        }
    ],
    "status": "success",
}

VARIANT_MAX = {
    "data": {
        "objCls": "Variant",
        "id": "PA166156104",
        "symbol": "rs3892097",
        "name": "rs3892097",
        "altNames": {
            "synonym": [
                "CYP2D6(B)",
                "CYP2D6*4",
                "NC_000022.10:g.42524947C=",
                "NC_000022.10:g.42524947C>T",
                "NC_000022.11:g.42128945C=",
                "NC_000022.11:g.42128945C>T",
                "NG_008376.3:g.6047G=",
                "NG_008376.3:g.6047G>A",
                "NM_000106.5:c.506-1A>G",
                "NM_000106.5:c.506-1G>A",
                "NM_001025161.2:c.353-1A>G",
                "NM_001025161.2:c.353-1G>A",
                "NT_187682.1:g.51286C=",
                "NT_187682.1:g.51286C>T",
                "NW_004504305.1:g.51272T=",
                "NW_004504305.1:g.51272T>C",
                "NW_009646208.1:g.14511C=",
                "NW_009646208.1:g.14511C>T",
                "XM_005278353.1:c.363-2A>G",
                "XM_005278353.1:c.363-2G>A",
                "XM_005278354.1:c.207-2A>G",
                "XM_005278354.1:c.207-2G>A",
                "XM_005278354.3:c.207-2A>G",
                "XM_005278354.3:c.207-2G>A",
                "XM_011529966.1:c.506-1A>G",
                "XM_011529966.1:c.506-1G>A",
                "XM_011529967.1:c.506-1A>G",
                "XM_011529967.1:c.506-1G>A",
                "XM_011529968.1:c.506-1A>G",
                "XM_011529968.1:c.506-1G>A",
                "XM_011529969.1:c.363-2A>G",
                "XM_011529969.1:c.363-2G>A",
                "XM_011529970.1:c.353-1A>G",
                "XM_011529970.1:c.353-1G>A",
                "XM_011529971.1:c.363-2A>G",
                "XM_011529971.1:c.363-2G>A",
                "XM_011529972.1:c.506-1A>G",
                "XM_011529972.1:c.506-1G>A",
                "XM_011547541.1:c.207-2A>G",
                "XM_011547541.1:c.207-2G>A",
                "XM_011547750.1:c.363-2A>G",
                "XM_011547750.1:c.363-2G>A",
                "XM_011547751.1:c.290-1A>G",
                "XM_011547751.1:c.290-1G>A",
                "XM_011547756.1:c.-1090C>T",
                "XM_011547756.1:c.-1090T>C",
                "XM_011548819.1:c.207-2A>G",
                "XM_011548819.1:c.207-2G>A",
                "XR_430455.2:n.-926C>T",
                "XR_430455.2:n.-926T>C",
                "XR_952745.1:n.1663-1A>G",
                "XR_952745.1:n.1663-1G>A",
                "rs1800716",
                "rs28371711",
                "rs60082401",
                "rs606231227",
            ]
        },
        "changeClassification": "Splice Acceptor",
        "clinicalSignificance": "drug-response",
        "crossReferences": [
            {
                "id": 1448049775,
                "resource": "dbSNP",
                "resourceId": "rs3892097",
                "_url": "https://www.ncbi.nlm.nih.gov/snp/rs3892097",
                "version": 0,
            },
            {
                "id": 1448103429,
                "name": "NM_000106.5(CYP2D6):c.506-1G>A",
                "resource": "ClinVar",
                "resourceId": "16889",
                "_url": "https://www.ncbi.nlm.nih.gov/clinvar/?term=16889",
                "version": 0,
            },
        ],
        "lastUpdatedFromDbsnp": "2020-06-18T20:49:03.110258-07:00",
        "obsolete": False,
        "rare": False,
        "raritySource": "gnomAD v4",
        "relatedGenes": [
            {
                "objCls": "Gene",
                "id": "PA128",
                "symbol": "CYP2D6",
                "name": "cytochrome P450 family 2 subfamily D member 6",
                "version": 7891,
            }
        ],
        "type": "SNP",
        "version": 7,
    },
    "status": "success",
}

HAPLOTYPE_SEARCH = {
    "data": [
        {
            "objCls": "StarAllele",
            "id": "PA165816579",
            "symbol": "CYP2D6*4",
            "name": "*4",
            "gene": {
                "objCls": "Gene",
                "id": "PA128",
                "symbol": "CYP2D6",
                "name": "cytochrome P450 family 2 subfamily D member 6",
            },
            "reference": False,
        }
    ],
    "status": "success",
}

HAPLOTYPES_OF_GENE = {
    "data": [
        {
            "objCls": "StarAllele",
            "id": "PA166123345",
            "symbol": "CYP2D6*105",
            "name": "*105",
            "gene": {
                "objCls": "Gene",
                "id": "PA128",
                "symbol": "CYP2D6",
                "name": "cytochrome P450 family 2 subfamily D member 6",
            },
            "reference": False,
        },
        {
            "objCls": "StarAllele",
            "id": "PA166170941",
            "symbol": "CYP2D6*106",
            "name": "*106",
            "gene": {
                "objCls": "Gene",
                "id": "PA128",
                "symbol": "CYP2D6",
                "name": "cytochrome P450 family 2 subfamily D member 6",
            },
            "reference": False,
        },
        {
            "objCls": "StarAllele",
            "id": "PA165971619",
            "symbol": "CYP2D6*64",
            "name": "*64",
            "gene": {
                "objCls": "Gene",
                "id": "PA128",
                "symbol": "CYP2D6",
                "name": "cytochrome P450 family 2 subfamily D member 6",
            },
            "reference": False,
        },
    ],
    "status": "success",
}

CLINICAL_ANNOTATIONS_GENE = {
    "data": [
        {
            "id": 1183618159,
            "accessionId": "PA166135161",
            "levelOfEvidence": {
                "id": 827923054,
                "resource": "Level of Evidence",
                "term": "2A",
                "termId": "levelsOfEvidence:827923054",
            },
            "location": {
                "id": 1451338972,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*3, CYP2D6*4, CYP2D6*5, CYP2D6*6, CYP2D6*10",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*3, CYP2D6*4, CYP2D6*5, CYP2D6*6, CYP2D6*10; tramadol; "
            "Pain (level 2A Dosage)",
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA451735", "name": "tramadol"}],
            "relatedChemicalsLogic": "Or",
            "relatedGuidelines": [],
            "relatedLabels": [],
            "types": ["Dosage"],
        },
        {
            "id": 1448999816,
            "accessionId": "PA166170554",
            "levelOfEvidence": {
                "id": 827923056,
                "resource": "Level of Evidence",
                "term": "3",
                "termId": "levelsOfEvidence:827923056",
            },
            "location": {
                "id": 1451282300,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*87, CYP2D6*88, CYP2D6*89, CYP2D6*90, "
                "CYP2D6*91, CYP2D6*93, CYP2D6*94, CYP2D6*95, CYP2D6*97, "
                "CYP2D6*98",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*87, CYP2D6*88, CYP2D6*89, CYP2D6*90, CYP2D6*91, "
            "CYP2D6*93, CYP2D6*94, CYP2D6*95, CYP2D6*97, CYP2D6*98; amitriptyline "
            "(level 3 Metabolism/PK)",
            "relatedChemicals": [
                {"objCls": "Chemical", "id": "PA448385", "name": "amitriptyline"}
            ],
            "relatedChemicalsLogic": "Or",
            "relatedGuidelines": [],
            "relatedLabels": [],
            "types": ["Metabolism/PK"],
        },
        {
            "id": 1451288220,
            "accessionId": "PA166226241",
            "levelOfEvidence": {
                "id": 827923052,
                "resource": "Level of Evidence",
                "term": "1A",
                "termId": "levelsOfEvidence:827923052",
            },
            "location": {
                "id": 1451645160,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*4, CYP2D6*5, CYP2D6*6, CYP2D6*17, CYP2D6*40",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*4, CYP2D6*5, CYP2D6*6, CYP2D6*17, CYP2D6*40; codeine; "
            "Pain (level 1A Efficacy)",
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedChemicalsLogic": "Or",
            "relatedGuidelines": [
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166104996",
                    "name": "Annotation of CPIC Clinical Guideline for codeine and CYP2D6",
                },
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166104970",
                    "name": "Annotation of DPWG Clinical Guideline for codeine and CYP2D6",
                },
            ],
            "relatedLabels": [],
            "types": ["Efficacy"],
        },
        {
            "id": 1451154980,
            "accessionId": "PA166211481",
            "levelOfEvidence": {
                "id": 827923052,
                "resource": "Level of Evidence",
                "term": "1A",
                "termId": "levelsOfEvidence:827923052",
            },
            "location": {
                "id": 1451645200,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*3, CYP2D6*4, CYP2D6*5, CYP2D6*6, "
                "CYP2D6*10, CYP2D6*17",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*3, CYP2D6*4, CYP2D6*5, CYP2D6*6, CYP2D6*10, CYP2D6*17; "
            "tramadol; Pain and Pain, Postoperative (level 1A Efficacy)",
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA451735", "name": "tramadol"}],
            "relatedChemicalsLogic": "Or",
            "relatedGuidelines": [
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166228101",
                    "name": "Annotation of CPIC Clinical Guideline for tramadol and CYP2D6",
                },
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166104959",
                    "name": "Annotation of DPWG Clinical Guideline for tramadol and CYP2D6",
                },
            ],
            "relatedLabels": [],
            "types": ["Efficacy"],
        },
        {
            "id": 1451259580,
            "accessionId": "PA166223141",
            "levelOfEvidence": {
                "id": 827923052,
                "resource": "Level of Evidence",
                "term": "1A",
                "termId": "levelsOfEvidence:827923052",
            },
            "location": {
                "id": 1451421384,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*2, CYP2D6*3, CYP2D6*4, CYP2D6*5, "
                "CYP2D6*6, CYP2D6*10, CYP2D6*41",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*1xN, CYP2D6*2, CYP2D6*3, CYP2D6*4, CYP2D6*5, CYP2D6*6, "
            "CYP2D6*10, CYP2D6*41; amitriptyline; Depressive Disorder (level 1A "
            "Toxicity)",
            "relatedChemicals": [
                {"objCls": "Chemical", "id": "PA448385", "name": "amitriptyline"}
            ],
            "relatedChemicalsLogic": "Or",
            "relatedGuidelines": [
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166105006",
                    "name": "Annotation of CPIC Clinical Guideline for "
                    "amitriptyline and CYP2C19, CYP2D6",
                },
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166104982",
                    "name": "Annotation of DPWG Clinical Guideline for amitriptyline and CYP2D6",
                },
            ],
            "relatedLabels": [],
            "types": ["Toxicity"],
        },
        {
            "id": 1451152821,
            "accessionId": "PA166210901",
            "levelOfEvidence": {
                "id": 827923056,
                "resource": "Level of Evidence",
                "term": "3",
                "termId": "levelsOfEvidence:827923056",
            },
            "location": {
                "id": 1451152822,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*3, CYP2D6*4",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*3, CYP2D6*4; codeine; Opioid-Related Disorders (level 3 "
            "Toxicity)",
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedChemicalsLogic": "Or",
            "relatedGuidelines": [],
            "relatedLabels": [],
            "types": ["Toxicity"],
        },
    ],
    "status": "success",
}

CLINICAL_ANNOTATIONS_CHEMICAL = {
    "data": [
        {
            "id": 1183616718,
            "accessionId": "PA166135140",
            "levelOfEvidence": {
                "id": 827923052,
                "resource": "Level of Evidence",
                "synonyms": [],
                "term": "1A",
                "termId": "levelsOfEvidence:827923052",
                "valid": True,
            },
            "location": {
                "id": 1454089956,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*2, CYP2D6*3, CYP2D6*4, CYP2D6*5, "
                "CYP2D6*6, CYP2D6*10, CYP2D6*17, CYP2D6*29, CYP2D6*36, "
                "CYP2D6*41",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*1xN, CYP2D6*2, CYP2D6*2xN, CYP2D6*3, CYP2D6*4, CYP2D6*5, "
            "CYP2D6*6, CYP2D6*10, CYP2D6*17, CYP2D6*29, CYP2D6*36, CYP2D6*41; codeine "
            "(level 1A Metabolism/PK)",
            "objCls": "SummaryAnnotation",
            "overrideLevel": False,
            "pediatric": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedChemicalsLogic": "Or",
            "relatedDiseases": [],
            "relatedGuidelines": [
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166104996",
                    "name": "Annotation of CPIC Clinical Guideline for codeine and CYP2D6",
                },
                {
                    "objCls": "GuidelineAnnotation",
                    "id": "PA166104970",
                    "name": "Annotation of DPWG Clinical Guideline for codeine and CYP2D6",
                },
            ],
            "relatedLabels": [],
            "score": 215.5625,
            "types": ["Metabolism/PK"],
        },
        {
            "id": 1446903007,
            "accessionId": "PA166136443",
            "levelOfEvidence": {
                "id": 827923056,
                "resource": "Level of Evidence",
                "synonyms": [],
                "term": "3",
                "termId": "levelsOfEvidence:827923056",
                "valid": True,
            },
            "location": {
                "id": 1446903012,
                "buildVersion": "hg38",
                "chromosomeId": "PA529",
                "chromosomeName": "chr4",
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "rs7439366",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA361",
                        "symbol": "UGT2B7",
                        "name": "UDP glucuronosyltransferase family 2 member B7",
                    }
                ],
                "gpPosition": 69964338,
                "refSeqCrossReference": {
                    "id": 1444703558,
                    "resource": "RefSeq RNA",
                    "resourceId": "NM_001074.2",
                    "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NM_001074.2",
                },
                "refSeqPosition": 802,
                "rsid": "rs7439366",
                "tagGene": False,
                "type": "SNP",
                "variant": {
                    "objCls": "Variant",
                    "id": "PA166156619",
                    "symbol": "rs7439366",
                    "name": "rs7439366",
                },
            },
            "name": "rs7439366 (UGT2B7); codeine (level 3 Dosage)",
            "objCls": "SummaryAnnotation",
            "overrideLevel": False,
            "pediatric": False,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedChemicalsLogic": "Or",
            "relatedDiseases": [],
            "relatedGuidelines": [],
            "relatedLabels": [],
            "score": 2.25,
            "types": ["Dosage"],
        },
        {
            "id": 1444704818,
            "accessionId": "PA166136329",
            "levelOfEvidence": {
                "id": 827923056,
                "resource": "Level of Evidence",
                "synonyms": [],
                "term": "3",
                "termId": "levelsOfEvidence:827923056",
                "valid": True,
            },
            "location": {
                "id": 1449751995,
                "buildVersion": "GRCh37.p13",
                "chromosomeId": "PA534",
                "chromosomeName": "chr7",
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "rs1045642",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA267",
                        "symbol": "ABCB1",
                        "name": "ATP binding cassette subfamily B member 1",
                    }
                ],
                "gpPosition": 87138645,
                "refSeqCrossReference": {
                    "id": 1444698471,
                    "resource": "RefSeq RNA",
                    "resourceId": "NM_000927.4",
                    "_url": "https://www.ncbi.nlm.nih.gov/nuccore/NM_000927.4",
                },
                "refSeqPosition": 3435,
                "rsid": "rs1045642",
                "tagGene": False,
                "type": "SNP",
                "variant": {
                    "objCls": "Variant",
                    "id": "PA166157284",
                    "symbol": "rs1045642",
                    "name": "rs1045642",
                },
            },
            "name": "rs1045642 (ABCB1); codeine (level 3 Toxicity)",
            "objCls": "SummaryAnnotation",
            "overrideLevel": False,
            "pediatric": False,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedChemicalsLogic": "Or",
            "relatedDiseases": [],
            "relatedGuidelines": [],
            "relatedLabels": [],
            "score": 2.5,
            "types": ["Toxicity"],
        },
        {
            "id": 1448999385,
            "accessionId": "PA166170540",
            "levelOfEvidence": {
                "id": 827923056,
                "resource": "Level of Evidence",
                "synonyms": [],
                "term": "3",
                "termId": "levelsOfEvidence:827923056",
                "valid": True,
            },
            "location": {
                "id": 1453104067,
                "copyNumber": "1",
                "diplotypes": [],
                "displayName": "CYP2D6*1, CYP2D6*24",
                "genes": [
                    {
                        "objCls": "Gene",
                        "id": "PA128",
                        "symbol": "CYP2D6",
                        "name": "cytochrome P450 family 2 subfamily D member 6",
                    }
                ],
                "gpPosition": -1,
                "refSeqPosition": -1,
                "tagGene": False,
                "type": "haplotype",
            },
            "name": "CYP2D6*1, CYP2D6*24; codeine or N-desmethyltamoxifen (level 3 Metabolism/PK)",
            "objCls": "SummaryAnnotation",
            "overrideLevel": False,
            "pediatric": False,
            "relatedChemicals": [
                {"objCls": "Chemical", "id": "PA449088", "name": "codeine"},
                {"objCls": "Chemical", "id": "PA166127651", "name": "N-desmethyltamoxifen"},
            ],
            "relatedChemicalsLogic": "Or",
            "relatedDiseases": [],
            "relatedGuidelines": [],
            "relatedLabels": [],
            "score": 0.0,
            "types": ["Metabolism/PK"],
        },
    ],
    "status": "success",
}

GUIDELINES_GENE = {
    "data": [
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166104992",
            "name": "Annotation of DPWG Clinical Guideline for zuclopenthixol and CYP2D6",
            "alternateDrugAvailable": False,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": True,
            "hasTestingInfo": True,
            "otherPrescribingGuidance": False,
            "pediatric": False,
            "recommendation": True,
            "relatedChemicals": [
                {"objCls": "Chemical", "id": "PA452629", "name": "zuclopenthixol"}
            ],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "DPWG",
        },
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166104996",
            "name": "Annotation of CPIC Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "descriptiveVideoId": "pfovk7flpoM",
            "dosingInformation": False,
            "hasTestingInfo": False,
            "otherPrescribingGuidance": True,
            "pediatric": True,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "CPIC",
        },
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166122666",
            "name": "Annotation of CPNDS Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": False,
            "hasTestingInfo": True,
            "otherPrescribingGuidance": False,
            "pediatric": False,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "CPNDS",
        },
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166104970",
            "name": "Annotation of DPWG Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": True,
            "hasTestingInfo": True,
            "otherPrescribingGuidance": True,
            "pediatric": True,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "DPWG",
        },
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166122666",
            "name": "Annotation of CPNDS Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": False,
            "hasTestingInfo": True,
            "otherPrescribingGuidance": False,
            "pediatric": False,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "CPNDS",
        },
    ],
    "status": "success",
}

GUIDELINES_CHEMICAL = {
    "data": [
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166104970",
            "name": "Annotation of DPWG Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": True,
            "hasTestingInfo": True,
            "otherPrescribingGuidance": True,
            "pediatric": True,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "DPWG",
        },
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166104996",
            "name": "Annotation of CPIC Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "descriptiveVideoId": "pfovk7flpoM",
            "dosingInformation": False,
            "hasTestingInfo": False,
            "otherPrescribingGuidance": True,
            "pediatric": True,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "CPIC",
        },
        {
            "objCls": "GuidelineAnnotation",
            "id": "PA166122666",
            "name": "Annotation of CPNDS Clinical Guideline for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": False,
            "hasTestingInfo": True,
            "otherPrescribingGuidance": False,
            "pediatric": False,
            "recommendation": True,
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "CPNDS",
        },
    ],
    "status": "success",
}

DRUG_LABELS_CHEMICAL = {
    "data": [
        {
            "objCls": "LabelAnnotation",
            "id": "PA166104916",
            "name": "Annotation of FDA Drug Label for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "biomarkerStatus": "On FDA Biomarker List",
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": False,
            "highlightedLabelLink": "Codeine_01_09_19_FDA.pdf",
            "indication": False,
            "labelDocumentAvailable": True,
            "otherPrescribingGuidance": False,
            "pediatric": True,
            "pgxRelated": True,
            "prescribingGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "FDA",
            "testing": {
                "id": 1183672111,
                "resource": "Genetic Testing Level",
                "synonyms": [],
                "term": "Actionable PGx",
                "termId": "geneTestLevel:1183672111",
                "valid": True,
            },
        },
        {
            "objCls": "LabelAnnotation",
            "id": "PA166184126",
            "name": "Annotation of Swissmedic Drug Label for codeine and CYP2D6",
            "alternateDrugAvailable": True,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": False,
            "indication": False,
            "labelDocumentAvailable": True,
            "otherPrescribingGuidance": False,
            "pediatric": False,
            "pgxRelated": True,
            "prescribingGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "Swissmedic",
            "testing": {
                "id": 1183672111,
                "resource": "Genetic Testing Level",
                "synonyms": [],
                "term": "Actionable PGx",
                "termId": "geneTestLevel:1183672111",
                "valid": True,
            },
        },
        {
            "objCls": "LabelAnnotation",
            "id": "PA166160226",
            "name": "Annotation of PMDA Drug Label for codeine and CYP2D6",
            "alternateDrugAvailable": False,
            "cancerGenome": False,
            "crossReferences": [],
            "dosingInformation": False,
            "indication": False,
            "labelDocumentAvailable": True,
            "otherPrescribingGuidance": False,
            "pediatric": False,
            "pgxRelated": True,
            "prescribingGenes": [],
            "relatedChemicals": [{"objCls": "Chemical", "id": "PA449088", "name": "codeine"}],
            "relatedGenes": [
                {
                    "objCls": "Gene",
                    "id": "PA128",
                    "symbol": "CYP2D6",
                    "name": "cytochrome P450 family 2 subfamily D member 6",
                }
            ],
            "source": "PMDA",
            "testing": {
                "id": 1183672111,
                "resource": "Genetic Testing Level",
                "synonyms": [],
                "term": "Actionable PGx",
                "termId": "geneTestLevel:1183672111",
                "valid": True,
            },
        },
    ],
    "status": "success",
}

GENE_MIN = {
    "data": {
        "objCls": "Gene",
        "id": "PA128",
        "symbol": "CYP2D6",
        "name": "cytochrome P450 family 2 subfamily D member 6",
    },
    "status": "success",
}

NOT_FOUND = {"status": "fail", "data": {"errors": [{"message": "No results matching criteria."}]}}
