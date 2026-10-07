"""Trimmed real IntAct web-service and PSICQUIC responses (fetched 2026-10) for the IntActAdapter tests.

FIND_* are ``interactor/findInteractor`` payloads (fields the adapter does not read are dropped);
*_TAB25 / *_TAB27 are PSICQUIC MITAB rows for ``id:P38398`` (BRCA1) and ``id:P05231`` (IL6).
"""

FIND_BRCA1 = {
    "totalElements": 61,
    "content": [
        {
            "interactorAc": "EBI-349905",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 551,
        },
        {
            "interactorAc": "EBI-6876136",
            "interactorName": "Brca1",
            "interactorPreferredIdentifier": "P48754",
            "interactorDescription": "Breast cancer type 1 susceptibility protein homolog",
            "interactorType": "protein",
            "interactorSpecies": "Mus musculus",
            "interactorTaxId": 10090,
            "interactionCount": 22,
        },
        {
            "interactorAc": "EBI-34592130",
            "interactorName": "mrna_brca1",
            "interactorPreferredIdentifier": "ENST00000357654",
            "interactorDescription": "BRCA1 DNA repair associated",
            "interactorType": "mrna",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 15,
        },
        {
            "interactorAc": "EBI-1165296",
            "interactorName": "brca1.L",
            "interactorPreferredIdentifier": "Q90X96",
            "interactorDescription": "RING-type E3 ubiquitin transferase",
            "interactorType": "protein",
            "interactorSpecies": "Xenopus laevis (African clawed frog)",
            "interactorTaxId": 8355,
            "interactionCount": 8,
        },
        {
            "interactorAc": "EBI-21498346",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-1",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 11,
        },
        {
            "interactorAc": "EBI-3895496",
            "interactorName": "brc-1",
            "interactorPreferredIdentifier": "B6VQ60",
            "interactorDescription": "Breast cancer type 1 susceptibility protein homolog",
            "interactorType": "protein",
            "interactorSpecies": "Caenorhabditis elegans",
            "interactorTaxId": 6239,
            "interactionCount": 4,
        },
        {
            "interactorAc": "EBI-25833510",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-6",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 6,
        },
        {
            "interactorAc": "EBI-21713256",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-2",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 3,
        },
        {
            "interactorAc": "EBI-2015072",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-5",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 2,
        },
        {
            "interactorAc": "EBI-16414487",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "A5A751",
            "interactorDescription": "RING-type E3 ubiquitin transferase",
            "interactorType": "protein",
            "interactorSpecies": "Sus scrofa (Pig)",
            "interactorTaxId": 9823,
            "interactionCount": 1,
        },
        {
            "interactorAc": "EBI-15768175",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "Q90Z51",
            "interactorDescription": "RING-type E3 ubiquitin transferase",
            "interactorType": "protein",
            "interactorSpecies": "Gallus gallus (Chicken)",
            "interactorTaxId": 9031,
            "interactionCount": 1,
        },
        {
            "interactorAc": "EBI-9386048",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "Q9NQR3",
            "interactorDescription": None,
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 3,
        },
    ],
}

FIND_TNF = {
    "totalElements": 235,
    "content": [
        {
            "interactorAc": "EBI-355744",
            "interactorName": "TRAF2",
            "interactorPreferredIdentifier": "Q12933",
            "interactorDescription": "TNF receptor-associated factor 2",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 1687,
        },
        {
            "interactorAc": "EBI-359977",
            "interactorName": "TNF",
            "interactorPreferredIdentifier": "P01375",
            "interactorDescription": "Tumor necrosis factor",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 450,
        },
        {
            "interactorAc": "EBI-527670",
            "interactorName": "TNFAIP3",
            "interactorPreferredIdentifier": "P21580",
            "interactorDescription": "Tumor necrosis factor alpha-induced protein 3",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 428,
        },
        {
            "interactorAc": "EBI-1374150",
            "interactorName": "Tnf",
            "interactorPreferredIdentifier": "P16599",
            "interactorDescription": "Tumor necrosis factor",
            "interactorType": "protein",
            "interactorSpecies": "Rattus norvegicus (Rat)",
            "interactorTaxId": 10116,
            "interactionCount": 94,
        },
        {
            "interactorAc": "EBI-10040832",
            "interactorName": "tnfa_human_gene",
            "interactorPreferredIdentifier": "ENSG00000204490",
            "interactorDescription": "Tumor necrosis factor",
            "interactorType": "gene",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 9,
        },
        {
            "interactorAc": "EBI-26489272",
            "interactorName": "tnfa_human_gene-1",
            "interactorPreferredIdentifier": "ENSG00000232810",
            "interactorDescription": "Tumor necrosis factor",
            "interactorType": "gene",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 8,
        },
        {
            "interactorAc": "EBI-16355546",
            "interactorName": "TNFSF15",
            "interactorPreferredIdentifier": "O95150",
            "interactorDescription": "Tumor necrosis factor ligand superfamily member 15",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 8,
        },
        {
            "interactorAc": "EBI-1563469",
            "interactorName": "Tnf",
            "interactorPreferredIdentifier": "P06804",
            "interactorDescription": "Tumor necrosis factor",
            "interactorType": "protein",
            "interactorSpecies": "Mus musculus",
            "interactorTaxId": 10090,
            "interactionCount": 2,
        },
    ],
}

FIND_P38398 = {
    "totalElements": 6,
    "content": [
        {
            "interactorAc": "EBI-349905",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 551,
        },
        {
            "interactorAc": "EBI-21498346",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-1",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 11,
        },
        {
            "interactorAc": "EBI-25833510",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-6",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 6,
        },
        {
            "interactorAc": "EBI-21713256",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-2",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 3,
        },
        {
            "interactorAc": "EBI-2015072",
            "interactorName": "BRCA1",
            "interactorPreferredIdentifier": "P38398-5",
            "interactorDescription": "Breast cancer type 1 susceptibility protein",
            "interactorType": "protein",
            "interactorSpecies": "Homo sapiens",
            "interactorTaxId": 9606,
            "interactionCount": 2,
        },
    ],
}

FIND_EMPTY = {"totalElements": 0, "content": []}

BRCA1_TAB25 = (
    "uniprotkb:P38398\tuniprotkb:Q9BX63\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-3509650|uniprotkb:Q3MJE2|uniprotkb:Q8NCI5|uniprotkb:A0A024QZ45|ensembl:ENSP00000259008.2|ensembl:ENSP00000506943.1|ensembl:ENSP00000508303.1\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:fancj_human(display_long)|uniprotkb:DNA 5'-3' helicase FANCJ(gene name "
    "synonym)|uniprotkb:BRIP1(gene name)|psi-mi:BRIP1(display_short)|uniprotkb:BACH1(gene name "
    "synonym)|uniprotkb:FANCJ(gene name synonym)|uniprotkb:BRCA1-associated C-terminal helicase "
    "1(gene name synonym)|uniprotkb:BRCA1-interacting protein C-terminal helicase 1(gene name "
    'synonym)\tpsi-mi:"MI:0676"(tandem affinity purification)\tWang et al. (2007)\t'
    "pubmed:17525340|imex:IM-19729\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0914"(association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-1263518|imex:IM-19729-4\tintact-miscore:0.98\n'
    "uniprotkb:P38398\tuniprotkb:Q9BX63\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-3509650|uniprotkb:Q3MJE2|uniprotkb:Q8NCI5|uniprotkb:A0A024QZ45|ensembl:ENSP00000259008.2|ensembl:ENSP00000506943.1|ensembl:ENSP00000508303.1\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:fancj_human(display_long)|uniprotkb:DNA 5'-3' helicase FANCJ(gene name "
    "synonym)|uniprotkb:BRIP1(gene name)|psi-mi:BRIP1(display_short)|uniprotkb:BACH1(gene name "
    "synonym)|uniprotkb:FANCJ(gene name synonym)|uniprotkb:BRCA1-associated C-terminal helicase "
    "1(gene name synonym)|uniprotkb:BRCA1-interacting protein C-terminal helicase 1(gene name "
    'synonym)\tpsi-mi:"MI:0006"(anti bait coimmunoprecipitation)\tWang et al. (2007)\t'
    "pubmed:17525340|imex:IM-19729\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-1263655|imex:IM-19729-12\tintact-miscore:0.98\n'
    "uniprotkb:P38398\tuniprotkb:Q9BX63\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-3509650|uniprotkb:Q3MJE2|uniprotkb:Q8NCI5|uniprotkb:A0A024QZ45|ensembl:ENSP00000259008.2|ensembl:ENSP00000506943.1|ensembl:ENSP00000508303.1\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:fancj_human(display_long)|uniprotkb:DNA 5'-3' helicase FANCJ(gene name "
    "synonym)|uniprotkb:BRIP1(gene name)|psi-mi:BRIP1(display_short)|uniprotkb:BACH1(gene name "
    "synonym)|uniprotkb:FANCJ(gene name synonym)|uniprotkb:BRCA1-associated C-terminal helicase "
    "1(gene name synonym)|uniprotkb:BRCA1-interacting protein C-terminal helicase 1(gene name "
    'synonym)\tpsi-mi:"MI:0006"(anti bait coimmunoprecipitation)\tWang et al. (2007)\t'
    "pubmed:17525340|imex:IM-19729\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0914"(association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-1263667|imex:IM-19729-14\tintact-miscore:0.98\n'
    "uniprotkb:P38398\tuniprotkb:Q99728\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-473181|uniprotkb:O43574|uniprotkb:Q53SS5|uniprotkb:F6MDH7|uniprotkb:F6MDH8|uniprotkb:F6MDH9|ensembl:ENSP00000260947.4\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:bard1_human(display_long)|uniprotkb:BARD1(gene "
    "name)|psi-mi:BARD1(display_short)|uniprotkb:RING-type E3 ubiquitin transferase BARD1(gene "
    'name synonym)\tpsi-mi:"MI:0006"(anti bait coimmunoprecipitation)\tLi et al. (2013)\t'
    "imex:IM-20842|pubmed:23680151\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0914"(association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-6692117|imex:IM-20842-2\tintact-miscore:0.96\n'
    "uniprotkb:P38398\tuniprotkb:Q99728\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-473181|uniprotkb:O43574|uniprotkb:Q53SS5|uniprotkb:F6MDH7|uniprotkb:F6MDH8|uniprotkb:F6MDH9|ensembl:ENSP00000260947.4\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:bard1_human(display_long)|uniprotkb:BARD1(gene "
    "name)|psi-mi:BARD1(display_short)|uniprotkb:RING-type E3 ubiquitin transferase BARD1(gene "
    'name synonym)\tpsi-mi:"MI:0007"(anti tag coimmunoprecipitation)\tHuttlin et al. (2021)\t'
    "pubmed:33961781|imex:IM-29278|doi:10.1016/j.cell.2021.04.011\t"
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0915"(physical association)\tpsi-mi:"MI:0469"(IntAct)\t'
    "intact:EBI-54799680|imex:IM-29278-17241\tintact-miscore:0.96\n"
    "uniprotkb:P38398\tuniprotkb:Q99708\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-745715|uniprotkb:A6NKN2|intact:EBI-1263531|uniprotkb:A8K8W6|uniprotkb:E7ETY1|uniprotkb:O75371|uniprotkb:Q8NHQ3|ensembl:ENSP00000323050.5|ensembl:ENSP00000382628.2\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:ctip_human(display_long)|uniprotkb:RBBP8(gene "
    "name)|psi-mi:RBBP8(display_short)|uniprotkb:CTIP(gene name "
    "synonym)|uniprotkb:CtBP-interacting protein(gene name "
    "synonym)|uniprotkb:Retinoblastoma-binding protein 8(gene name "
    "synonym)|uniprotkb:Retinoblastoma-interacting protein and myosin-like(gene name "
    "synonym)|uniprotkb:Sporulation in the absence of SPO11 protein 2 homolog(gene name synonym)\t"
    'psi-mi:"MI:0676"(tandem affinity purification)\tWang et al. (2007)\t'
    "pubmed:17525340|imex:IM-19729\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0914"(association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-1263518|imex:IM-19729-4\tintact-miscore:0.93\n'
    "uniprotkb:P38398\tuniprotkb:Q99708\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-745715|uniprotkb:A6NKN2|intact:EBI-1263531|uniprotkb:A8K8W6|uniprotkb:E7ETY1|uniprotkb:O75371|uniprotkb:Q8NHQ3|ensembl:ENSP00000323050.5|ensembl:ENSP00000382628.2\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:ctip_human(display_long)|uniprotkb:RBBP8(gene "
    "name)|psi-mi:RBBP8(display_short)|uniprotkb:CTIP(gene name "
    "synonym)|uniprotkb:CtBP-interacting protein(gene name "
    "synonym)|uniprotkb:Retinoblastoma-binding protein 8(gene name "
    "synonym)|uniprotkb:Retinoblastoma-interacting protein and myosin-like(gene name "
    "synonym)|uniprotkb:Sporulation in the absence of SPO11 protein 2 homolog(gene name synonym)\t"
    'psi-mi:"MI:0006"(anti bait coimmunoprecipitation)\tWang et al. (2007)\t'
    "pubmed:17525340|imex:IM-19729\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-1263660|imex:IM-19729-13\tintact-miscore:0.93\n'
    "uniprotkb:P03372\tuniprotkb:P38398\t"
    "intact:EBI-78473|uniprotkb:Q6MZQ9|uniprotkb:Q13511|uniprotkb:Q14276|uniprotkb:Q9NU51|uniprotkb:Q9UDZ7|uniprotkb:Q9UIS7|intact:EBI-28988800|uniprotkb:Q5T5H7|ensembl:ENSP00000206249.3|ensembl:ENSP00000342630.5|ensembl:ENSP00000387500.1|ensembl:ENSP00000405330.1\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "psi-mi:esr1_human(display_long)|uniprotkb:ESR1(gene "
    "name)|psi-mi:ESR1(display_short)|uniprotkb:ESR(gene name synonym)|uniprotkb:NR3A1(gene name "
    "synonym)|uniprotkb:Estradiol receptor(gene name synonym)|uniprotkb:ER-alpha(gene name "
    "synonym)|uniprotkb:Nuclear receptor subfamily 3 group A member 1(gene name synonym)\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    'synonym)\tpsi-mi:"MI:0096"(pull down)\tMa et al. (2005)\tpubmed:15674350|imex:IM-19371\t'
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0407"(direct interaction)\tpsi-mi:"MI:0469"(IntAct)\t'
    "intact:EBI-1017529|imex:IM-19371-1\tintact-miscore:0.81\n"
    "uniprotkb:P38398\tuniprotkb:P03372\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-78473|uniprotkb:Q6MZQ9|uniprotkb:Q13511|uniprotkb:Q14276|uniprotkb:Q9NU51|uniprotkb:Q9UDZ7|uniprotkb:Q9UIS7|intact:EBI-28988800|uniprotkb:Q5T5H7|ensembl:ENSP00000206249.3|ensembl:ENSP00000342630.5|ensembl:ENSP00000387500.1|ensembl:ENSP00000405330.1\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:esr1_human(display_long)|uniprotkb:ESR1(gene "
    "name)|psi-mi:ESR1(display_short)|uniprotkb:ESR(gene name synonym)|uniprotkb:NR3A1(gene name "
    "synonym)|uniprotkb:Estradiol receptor(gene name synonym)|uniprotkb:ER-alpha(gene name "
    "synonym)|uniprotkb:Nuclear receptor subfamily 3 group A member 1(gene name synonym)\t"
    'psi-mi:"MI:0096"(pull down)\tMa et al. (2005)\tpubmed:15674350|imex:IM-19371\t'
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0407"(direct interaction)\tpsi-mi:"MI:0469"(IntAct)\t'
    "intact:EBI-1024834|imex:IM-19371-2\tintact-miscore:0.81\n"
    "uniprotkb:P38398\tuniprotkb:Q9GZX5\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-396421|uniprotkb:Q9HAQ4|uniprotkb:Q96G73|ensembl:ENSP00000243644.3\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:zn350_human(display_long)|uniprotkb:Zinc finger protein ZBRK1(gene name "
    "synonym)|uniprotkb:Zinc finger and BRCA1-interacting protein with a KRAB domain 1(gene name "
    "synonym)|uniprotkb:KRAB zinc finger protein ZFQR(gene name synonym)|uniprotkb:ZNF350(gene "
    'name)|psi-mi:ZNF350(display_short)|uniprotkb:ZBRK1(gene name synonym)\tpsi-mi:"MI:0018"(two '
    "hybrid)\tZheng et al. (2000)\tpubmed:11090615\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-396776\tintact-miscore:0.58\n'
    "uniprotkb:P38398\tuniprotkb:Q9GZX5\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-396421|uniprotkb:Q9HAQ4|uniprotkb:Q96G73|ensembl:ENSP00000243644.3\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    "synonym)\tpsi-mi:zn350_human(display_long)|uniprotkb:Zinc finger protein ZBRK1(gene name "
    "synonym)|uniprotkb:Zinc finger and BRCA1-interacting protein with a KRAB domain 1(gene name "
    "synonym)|uniprotkb:KRAB zinc finger protein ZFQR(gene name synonym)|uniprotkb:ZNF350(gene "
    'name)|psi-mi:ZNF350(display_short)|uniprotkb:ZBRK1(gene name synonym)\tpsi-mi:"MI:0096"(pull '
    "down)\tZheng et al. (2000)\tpubmed:11090615\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-396786\tintact-miscore:0.58\n'
    "uniprotkb:Q9GZX5\tuniprotkb:P38398\t"
    "intact:EBI-396421|uniprotkb:Q9HAQ4|uniprotkb:Q96G73|ensembl:ENSP00000243644.3\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "psi-mi:zn350_human(display_long)|uniprotkb:Zinc finger protein ZBRK1(gene name "
    "synonym)|uniprotkb:Zinc finger and BRCA1-interacting protein with a KRAB domain 1(gene name "
    "synonym)|uniprotkb:KRAB zinc finger protein ZFQR(gene name synonym)|uniprotkb:ZNF350(gene "
    "name)|psi-mi:ZNF350(display_short)|uniprotkb:ZBRK1(gene name synonym)\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    'synonym)\tpsi-mi:"MI:0019"(coimmunoprecipitation)\tZheng et al. (2000)\tpubmed:11090615\t'
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0915"(physical association)\tpsi-mi:"MI:0469"(IntAct)\tintact:EBI-396795\t'
    "intact-miscore:0.58\n"
    "intact:EBI-2694074\tuniprotkb:P38398\t-\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "psi-mi:mdm2_human_probe(display_short)|psi-mi:EBI-2694074(display_long)\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    'synonym)\tpsi-mi:"MI:0096"(pull down)\tKu et al. (2009)\tpubmed:19505873|imex:IM-20483\t'
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0914"(association)\tpsi-mi:"MI:0469"(IntAct)\tintact:EBI-2795123|imex:IM-20483-1\t'
    "intact-miscore:0.35\n"
    "ensembl:ENSG00000096717\tuniprotkb:P38398\tintact:EBI-6267604\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "psi-mi:sir1_human_gene(display_short)|psi-mi:ENSG00000096717(display_long)\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene "
    "name)|psi-mi:BRCA1(display_short)|uniprotkb:RNF53(gene name synonym)|uniprotkb:RING finger "
    "protein 53(gene name synonym)|uniprotkb:RING-type E3 ubiquitin transferase BRCA1(gene name "
    'synonym)\tpsi-mi:"MI:0402"(chromatin immunoprecipitation assay)\tTanikawa et al. (2011)\t'
    "imex:IM-17677|pubmed:21407215\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0914"(association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-6267606|imex:IM-17677-9\tintact-miscore:0.35\n'
)

IL6_TAB25 = (
    "uniprotkb:P05231\tuniprotkb:P08887\t"
    "intact:EBI-720533|uniprotkb:Q9UCU4|uniprotkb:Q9UCU2|uniprotkb:Q9UCU3|ensembl:ENSP00000258743.5|ensembl:ENSP00000385675.1\t"
    "intact:EBI-299383|uniprotkb:Q16202|uniprotkb:Q53EQ7|uniprotkb:Q5FWG2|uniprotkb:Q5VZ23|uniprotkb:B2R6V4|uniprotkb:A8KAE8|ensembl:ENSP00000357470.3\t"
    "psi-mi:il6_human(display_long)|uniprotkb:B-cell stimulatory factor 2(gene name "
    "synonym)|uniprotkb:Interferon beta-2(gene name synonym)|uniprotkb:Hybridoma growth "
    "factor(gene name synonym)|uniprotkb:CTL differentiation factor(gene name "
    "synonym)|uniprotkb:IL6(gene name)|psi-mi:IL6(display_short)|uniprotkb:IFNB2(gene name "
    "synonym)\tpsi-mi:il6ra_human(display_long)|uniprotkb:IL6R(gene "
    "name)|psi-mi:IL6R(display_short)|uniprotkb:IL-6R 1(gene name synonym)|uniprotkb:Membrane "
    'glycoprotein 80(gene name synonym)\tpsi-mi:"MI:0114"(x-ray crystallography)\tBoulanger et '
    "al. (2003)\tpubmed:12829785\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-1036752|rcsb pdb:1P9M\tintact-miscore:0.91\n'
    "uniprotkb:P08887\tuniprotkb:P05231\t"
    "intact:EBI-299383|uniprotkb:Q16202|uniprotkb:Q53EQ7|uniprotkb:Q5FWG2|uniprotkb:Q5VZ23|uniprotkb:B2R6V4|uniprotkb:A8KAE8|ensembl:ENSP00000357470.3\t"
    "intact:EBI-720533|uniprotkb:Q9UCU4|uniprotkb:Q9UCU2|uniprotkb:Q9UCU3|ensembl:ENSP00000258743.5|ensembl:ENSP00000385675.1\t"
    "psi-mi:il6ra_human(display_long)|uniprotkb:IL6R(gene "
    "name)|psi-mi:IL6R(display_short)|uniprotkb:IL-6R 1(gene name synonym)|uniprotkb:Membrane "
    "glycoprotein 80(gene name synonym)\tpsi-mi:il6_human(display_long)|uniprotkb:B-cell "
    "stimulatory factor 2(gene name synonym)|uniprotkb:Interferon beta-2(gene name "
    "synonym)|uniprotkb:Hybridoma growth factor(gene name synonym)|uniprotkb:CTL differentiation "
    "factor(gene name synonym)|uniprotkb:IL6(gene "
    'name)|psi-mi:IL6(display_short)|uniprotkb:IFNB2(gene name synonym)\tpsi-mi:"MI:0107"(surface '
    "plasmon resonance)\tLarsen et al. (2017)\timex:IM-27618|pubmed:28265003\t"
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0407"(direct interaction)\tpsi-mi:"MI:0469"(IntAct)\t'
    "intact:EBI-25299566|imex:IM-27618-21\tintact-miscore:0.91\n"
    "uniprotkb:P05231\tuniprotkb:P08887\t"
    "intact:EBI-720533|uniprotkb:Q9UCU4|uniprotkb:Q9UCU2|uniprotkb:Q9UCU3|ensembl:ENSP00000258743.5|ensembl:ENSP00000385675.1\t"
    "intact:EBI-299383|uniprotkb:Q16202|uniprotkb:Q53EQ7|uniprotkb:Q5FWG2|uniprotkb:Q5VZ23|uniprotkb:B2R6V4|uniprotkb:A8KAE8|ensembl:ENSP00000357470.3\t"
    "psi-mi:il6_human(display_long)|uniprotkb:B-cell stimulatory factor 2(gene name "
    "synonym)|uniprotkb:Interferon beta-2(gene name synonym)|uniprotkb:Hybridoma growth "
    "factor(gene name synonym)|uniprotkb:CTL differentiation factor(gene name "
    "synonym)|uniprotkb:IL6(gene name)|psi-mi:IL6(display_short)|uniprotkb:IFNB2(gene name "
    "synonym)\tpsi-mi:il6ra_human(display_long)|uniprotkb:IL6R(gene "
    "name)|psi-mi:IL6R(display_short)|uniprotkb:IL-6R 1(gene name synonym)|uniprotkb:Membrane "
    'glycoprotein 80(gene name synonym)\tpsi-mi:"MI:0040"(electron microscopy)\tSkiniotis et al. '
    "(2008)\timex:IM-25071|pubmed:18775332\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-11667967|imex:IM-25071-16\tintact-miscore:0.91\n'
    "uniprotkb:P05231\tuniprotkb:P08887-PRO_0000450730\t"
    "intact:EBI-720533|uniprotkb:Q9UCU4|uniprotkb:Q9UCU2|uniprotkb:Q9UCU3|ensembl:ENSP00000258743.5|ensembl:ENSP00000385675.1\t"
    "intact:EBI-52312520\tpsi-mi:il6_human(display_long)|uniprotkb:B-cell stimulatory factor "
    "2(gene name synonym)|uniprotkb:Interferon beta-2(gene name synonym)|uniprotkb:Hybridoma "
    "growth factor(gene name synonym)|uniprotkb:CTL differentiation factor(gene name "
    "synonym)|uniprotkb:IL6(gene name)|psi-mi:IL6(display_short)|uniprotkb:IFNB2(gene name "
    "synonym)\tpsi-mi:p08887-pro_0000450730(display_long)|uniprotkb:IL6R(gene "
    "name)|psi-mi:IL6R(display_short)|uniprotkb:IL-6R 1(gene name synonym)|uniprotkb:Membrane "
    'glycoprotein 80(gene name synonym)\tpsi-mi:"MI:0071"(molecular sieving)\tWard et al. (1996)\t'
    "imex:IM-30026|pubmed:8702737\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0407"(direct interaction)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-52312516|imex:IM-30026-3\tintact-miscore:0.60\n'
    "uniprotkb:P08887-PRO_0000450730\tuniprotkb:P05231\tintact:EBI-52312520\t"
    "intact:EBI-720533|uniprotkb:Q9UCU4|uniprotkb:Q9UCU2|uniprotkb:Q9UCU3|ensembl:ENSP00000258743.5|ensembl:ENSP00000385675.1\t"
    "psi-mi:p08887-pro_0000450730(display_long)|uniprotkb:IL6R(gene "
    "name)|psi-mi:IL6R(display_short)|uniprotkb:IL-6R 1(gene name synonym)|uniprotkb:Membrane "
    "glycoprotein 80(gene name synonym)\tpsi-mi:il6_human(display_long)|uniprotkb:B-cell "
    "stimulatory factor 2(gene name synonym)|uniprotkb:Interferon beta-2(gene name "
    "synonym)|uniprotkb:Hybridoma growth factor(gene name synonym)|uniprotkb:CTL differentiation "
    "factor(gene name synonym)|uniprotkb:IL6(gene "
    'name)|psi-mi:IL6(display_short)|uniprotkb:IFNB2(gene name synonym)\tpsi-mi:"MI:0107"(surface '
    "plasmon resonance)\tWard et al. (1996)\timex:IM-30026|pubmed:8702737\t"
    "taxid:9606(human)|taxid:9606(Homo sapiens)\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'psi-mi:"MI:0407"(direct interaction)\tpsi-mi:"MI:0469"(IntAct)\t'
    "intact:EBI-52314862|imex:IM-30026-11\tintact-miscore:0.60\n"
)

BRCA1_TAB27 = (
    "uniprotkb:P38398\tuniprotkb:Q9GZX5\t"
    "intact:EBI-349905|uniprotkb:Q3LRJ0|uniprotkb:O15129|uniprotkb:Q7KYU9|ensembl:ENSP00000350283.3|ensembl:ENSP00000419103.2|ensembl:ENSP00000419274.2|ensembl:ENSP00000478114.2|ensembl:ENSP00000518978.1|uniprotkb:Q3LRJ6|uniprotkb:Q6IN79|uniprotkb:Q1RMC1|uniprotkb:E9PFZ0\t"
    "intact:EBI-396421|uniprotkb:Q9HAQ4|uniprotkb:Q96G73|ensembl:ENSP00000243644.3\t"
    "psi-mi:brca1_human(display_long)|uniprotkb:BRCA1(gene name)|\t"
    'psi-mi:zn350_human(display_long)|uniprotkb:Zinc finger prote\tpsi-mi:"MI:0018"(two hybrid)\t'
    "Zheng et al. (2000)\tpubmed:11090615\ttaxid:9606(human)|taxid:9606(Homo sapiens)\t"
    'taxid:9606(human)|taxid:9606(Homo sapiens)\tpsi-mi:"MI:0915"(physical association)\t'
    'psi-mi:"MI:0469"(IntAct)\tintact:EBI-396776\tintact-miscore:0.58\t-\t'
    'psi-mi:"MI:0499"(unspecified role)\tpsi-mi:"MI:0499"(unspecified role)\t'
    'psi-mi:"MI:0498"(prey)\tpsi-mi:"MI:0496"(bait)\tpsi-mi:"MI:0326"(protein)\t'
    'psi-mi:"MI:0326"(protein)\t'
    "ensembl:ENSG00000012048.26(gene)|ensembl:ENST00000357654.9(transcript)|ensembl:ENST00000470026.6(transcript)|ensembl:ENST00000494123.6(transcript)|ensembl:ENST00000618469.2(transcript)|ensembl:ENST00000713676.1(transcript)|interpro:IPR001357(BRCT)|interpro:IPR001841(Zinc "
    "finger, RING-type)|interpro:IPR011364(BRCA1)|interpro:IPR013083(Zinc finger, "
    "RING/FYVE/PHD-type)|interpro:IPR017907|interpro:IPR018957|interpro:IPR025994|interpro:IPR031099|interpro:IPR036420|mint:P38398|rcsb "
    "pdb:1JM7|rcsb pdb:1JNX|rcsb pdb:1N5O|rcsb pdb:1OQA|rcsb pdb:1T15|rcsb pdb:1T29|rcsb "
    "pdb:1T2U|rcsb pdb:1T2V|rcsb pdb:1Y98|rcsb pdb:2ING|rcsb pdb:3COJ|rcsb "
    'pdb:3K0H|reactome:R-HSA-1221632|reactome:R-HSA-3108214|reactome:R-HSA-5685938|reactome:R-HSA-5685942|reactome:R-HSA-5689901|reactome:R-HSA-5693554|reactome:R-HSA-5693565|reactome:R-HSA-5693568|reactome:R-HSA-5693571|reactome:R-HSA-5693579|reactome:R-HSA-5693607|reactome:R-HSA-5693616|refseq:NP_001394512.1|refseq:NP_001394514.1|refseq:NP_001394522.1|refseq:NP_001394523.1|refseq:NP_001394525.1|refseq:NP_001394526.1|refseq:NP_001394527.1|refseq:NP_001394531.1|refseq:NP_001394532.1|refseq:NP_001394534.1|refseq:NP_001394621.1|refseq:NP_001394623.1|dip:DIP-5971N|panther:PTHR13763(orthology-group)|efo:"Orphanet:1331"|efo:"Orphanet:1333"|efo:"Orphanet:145"|efo:"Orphanet:168829"|efo:"Orphanet:227535"|efo:"Orphanet:70567"|efo:"Orphanet:84"\t'
    "ensembl:ENSG00000256683.7(gene)|ensembl:ENST00000243644.9(transcript)|interpro:IPR001909(Krueppel-associated  "
    "box)|interpro:IPR013087(Zinc finger, C2H2-type/integrase, "
    "DNA-binding)|interpro:IPR036051|interpro:IPR036236|interpro:IPR050527|mint:Q9GZX5|reactome:R-HSA-212436|reactome:R-HSA-3899300|refseq:NP_067645.3|refseq:XP_016882587.1|refseq:XP_016882588.1|refseq:XP_016882589.1|refseq:XP_047295140.1|refseq:XP_047295141.1|refseq:XP_054177635.1|refseq:XP_054177636.1|refseq:XP_054177637.1|refseq:XP_054177638.1|panther:PTHR24404(orthology-group)\t"
    '-\t-\t-\t-\ttaxid:4932(yeasx)|taxid:4932("Saccharomyces cerevisiae (Baker\'s yeast)")\t-\t'
    "2004/07/30\t2026/01/11\trogid:Tx+5uS8dERqc0lhPZ0ZIKQaifXM9606\t"
    "rogid:n3L44uqErawnnBhZCDI2B7hnZxQ9606\t"
    "intact-crc:B08C2837329EDF9F|rigid:3jiAsWT8rNCKvGtxXJKbMmTYW3E\tfalse\tbinding-associated "
    'region:341-748\t-\t-\t-\tpsi-mi:"MI:0396"(predetermined participant)\t'
    'psi-mi:"MI:0396"(predetermined participant)\n'
)
