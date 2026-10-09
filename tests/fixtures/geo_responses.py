"""Trimmed real GEO (db=gds) E-utilities responses, recorded 2026-10-09."""

ESEARCH_CFS = {
    "header": {"type": "esearch", "version": "0.3"},
    "esearchresult": {
        "count": "30",
        "retmax": "5",
        "retstart": "0",
        "idlist": ["200327255", "200317067", "200304805", "200293840", "200269047"],
        "translationset": [
            {
                "from": "chronic fatigue syndrome",
                "to": '"fatigue syndrome, chronic"[MeSH Terms] OR '
                "chronic fatigue syndrome[All Fields]",
            }
        ],
        "translationstack": [
            {
                "term": '"fatigue syndrome, chronic"[MeSH Terms]',
                "field": "MeSH Terms",
                "count": "232",
                "explode": "Y",
            },
            {
                "term": "chronic fatigue syndrome[All Fields]",
                "field": "All Fields",
                "count": "180",
                "explode": "N",
            },
            "OR",
            "GROUP",
            {"term": "gse[ETYP]", "field": "ETYP", "count": "298105", "explode": "N"},
            "AND",
        ],
        "querytranslation": '("fatigue syndrome, chronic"[MeSH Terms] OR chronic '
        "fatigue syndrome[All Fields]) AND gse[ETYP]",
    },
}

ESEARCH_EMPTY = {
    "header": {"type": "esearch", "version": "0.3"},
    "esearchresult": {
        "count": "0",
        "retmax": "0",
        "retstart": "0",
        "idlist": [],
        "translationset": [],
        "querytranslation": "zzzzqqqqxx[All Fields] AND gse[ETYP]",
        "errorlist": {"phrasesnotfound": ["zzzzqqqqxx"], "fieldsnotfound": []},
        "warninglist": {
            "phrasesignored": [],
            "quotedphrasesnotfound": [],
            "outputmessages": ["No items found."],
        },
    },
}

GSE_ME = {
    "uid": "200327255",
    "accession": "GSE327255",
    "gds": "",
    "title": "PTPRN2 hypomethylation and PHB2-modulated miR-153-3p maturation reveal dual "
    "epigenetic mechanisms linked to symptom variability in Myalgic Encephalomyelitis",
    "summary": "Background: Myalgic encephalomyelitis (ME) is a chronic, debilitating condition "
    "increasingly linked to epigenetic changes. With its unclear pathophysiology and "
    "no validated diagnostic biomarkers, DNA methylation becomes of interest. "
    "Specifically, DNA methylation patterns in saliva, to study ME-related epigenetic "
    "changes. Methods: Saliva samples from 54 ME patients and 21 sedentary healthy "
    "controls were analyzed by DNA methylation array. Symptom assessment was conducted "
    "using validated questionnaires (SF-36, MFI-20, and DSQ). Results: A significant "
    "DNA hypomethylation at the CpG site cg19803194",
    "gpl": "21145",
    "gse": "327255",
    "taxon": "Homo sapiens",
    "entrytype": "GSE",
    "gdstype": "Methylation profiling by genome tiling array",
    "ptechtype": "",
    "valtype": "",
    "ssinfo": "",
    "subsetinfo": "",
    "pdat": "2026/04/22",
    "suppfile": "CSV, IDAT",
    "samples": [
        {"accession": "GSM9652321", "title": "Case 131"},
        {"accession": "GSM9652318", "title": "Case 119"},
        {"accession": "GSM9652301", "title": "Case 073"},
    ],
    "relations": [],
    "extrelations": [],
    "n_samples": 75,
    "seriestitle": "",
    "platformtitle": "",
    "platformtaxa": "",
    "samplestaxa": "",
    "pubmedids": ["42010606"],
    "projects": [],
    "ftplink": "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE327nnn/GSE327255/",
    "geo2r": "no",
    "bioproject": "PRJNA1450064",
}

GSE_LONGCOVID = {
    "uid": "200226260",
    "accession": "GSE226260",
    "gds": "",
    "title": "Long COVID involves activation of proinflammatory and immune exhaustion pathways",
    "summary": "Long COVID (LC) involves a spectrum of chronic symptoms after acute severe acute "
    "respiratory syndrome coronavirus 2 infection. Current hypotheses for the "
    "pathogenesis of LC include persistent virus, tissue damage, autoimmunity, "
    "endocrine insufficiency, immune dysfunction and complement activation. We "
    "performed immunological, virological, transcriptomic and proteomic analyses from "
    "a cohort of 142 individuals between 2020 and 2021, including uninfected controls "
    "(n\u2009=\u200935), acutely infected individuals (n\u2009=\u200954), convalescent "
    "controls (n\u2009=\u200924) and patients with LC (n\u2009=\u200928). The LC group "
    "was characterized by persistent immune activation and proinflammatory responses "
    "for more than 180 days after initial infection compared with convalescent "
    "controls, including upregulation of JAK-STAT, interleukin-6, complement, "
    "metabolism and T cell exhaustion pathways. Similar findings were observed in a "
    "second cohort enrolled between 2023 and 2024, including convalescent controls "
    "(n\u2009=\u200920) and patients with LC (n\u2009=\u200918). These data suggest "
    "that LC is characterized by persistent activation of chronic inflammatory "
    "pathways, suggesting new therapeutic targets and potential biomarkers of disease.",
    "gpl": "34284;24676",
    "gse": "226260",
    "taxon": "Homo sapiens",
    "entrytype": "GSE",
    "gdstype": "Expression profiling by high throughput sequencing",
    "ptechtype": "",
    "valtype": "",
    "ssinfo": "",
    "subsetinfo": "",
    "pdat": "2025/10/21",
    "suppfile": "CSV",
    "samples": [
        {"accession": "GSM8989260", "title": "BI4307.210.Recovered"},
        {"accession": "GSM8261095", "title": "p20169.s156_74_PT093"},
        {"accession": "GSM8261012", "title": "p20169.s037_112_PT052"},
    ],
    "relations": [],
    "extrelations": [
        {
            "relationtype": "SRA",
            "targetobject": "SRP424803",
            "targetftplink": "ftp://ftp-trace.ncbi.nlm.nih.gov/sra/sra-instant/reads/ByStudy/sra/SRP/SRP424/SRP424803/",
        }
    ],
    "n_samples": 331,
    "seriestitle": "",
    "platformtitle": "",
    "platformtaxa": "",
    "samplestaxa": "",
    "pubmedids": ["41388153"],
    "projects": [],
    "ftplink": "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE226nnn/GSE226260/",
    "geo2r": "no",
    "bioproject": "PRJNA939253",
}

GPL_EPIC = {
    "uid": "100021145",
    "accession": "GPL21145",
    "gds": "",
    "title": "Infinium MethylationEPIC",
    "summary": "See manufacturer's website",
    "gpl": "21145",
    "gse": "280206;328029;290136;187291;216906",
    "taxon": "Homo sapiens",
    "entrytype": "GPL",
    "gdstype": "",
    "ptechtype": "oligonucleotide beads",
    "valtype": "",
    "ssinfo": "",
    "subsetinfo": "",
    "pdat": "2015/11/16",
    "suppfile": "CSV",
    "samples": [],
    "relations": [{"relationtype": "Alternative to", "targetobject": "GPL23976"}],
    "extrelations": [],
    "n_samples": 107188,
    "seriestitle": "",
    "platformtitle": "",
    "platformtaxa": "",
    "samplestaxa": "",
    "pubmedids": [],
    "projects": [],
    "ftplink": "ftp://ftp.ncbi.nlm.nih.gov/geo/platforms/GPL21nnn/GPL21145/",
    "geo2r": "",
    "bioproject": "",
}

GSM_1 = {
    "uid": "300000001",
    "accession": "GSM1",
    "gds": "",
    "title": "Foreskin Fibroblasts",
    "summary": "mRNA of untreated foreskin fibroblasts",
    "gpl": "4",
    "gse": "506",
    "taxon": "Homo sapiens",
    "entrytype": "GSM",
    "gdstype": "",
    "ptechtype": "",
    "valtype": "",
    "ssinfo": "",
    "subsetinfo": "",
    "pdat": "2000/09/28",
    "suppfile": "",
    "samples": [],
    "relations": [],
    "extrelations": [],
    "n_samples": "",
    "seriestitle": "",
    "platformtitle": "",
    "platformtaxa": "",
    "samplestaxa": "",
    "pubmedids": [],
    "projects": [],
    "ftplink": "",
    "geo2r": "",
    "bioproject": "",
}

GDS_5435 = {
    "uid": "5435",
    "accession": "GDS5435",
    "gds": "5435",
    "title": "Dietary palatinose effect on liver",
    "summary": "Analysis of liver from C57Bl/6J males fed isocaloric diets containing sucrose or "
    "palatinose. Sucrose is a high glycemic index (GI) sugar; palatinose is a low GI "
    "sugar. Results provide insight into molecular mechanisms underlying the role of "
    "sucrose in the development of non-alcoholic fatty liver.",
    "gpl": "6885",
    "gse": "54723",
    "taxon": "Mus musculus",
    "entrytype": "GDS",
    "gdstype": "Expression profiling by array",
    "ptechtype": "",
    "valtype": "count",
    "ssinfo": "protocol;protocol",
    "subsetinfo": "2 protocol",
    "pdat": "2014/12/05",
    "suppfile": "",
    "samples": [
        {
            "accession": "GSM1322809",
            "title": "Liver tissue from mice fed with a sucrose-containing diet for 22 "
            "weeks, biological replicate 1",
        },
        {
            "accession": "GSM1322810",
            "title": "Liver tissue from mice fed with a sucrose-containing diet for 22 "
            "weeks, biological replicate 2",
        },
    ],
    "relations": [],
    "extrelations": [],
    "n_samples": 14,
    "seriestitle": "Nutritional Strategy to Prevent Fatty Liver and Insulin Resistance "
    "Independent of Obesity by Reducing GIP Responses",
    "platformtitle": "Illumina MouseRef-8 v2.0 expression beadchip",
    "platformtaxa": "Mus musculus",
    "samplestaxa": "Mus musculus",
    "pubmedids": ["25348610"],
    "projects": [],
    "ftplink": "ftp://ftp.ncbi.nlm.nih.gov/geo/datasets/GDS5nnn/GDS5435/",
    "geo2r": "",
    "bioproject": "PRJNA237500",
}

GSE_HAMSTER = {
    "uid": "200292461",
    "accession": "GSE292461",
    "gds": "",
    "title": "Single-dose cathepsin\u202fL CRISPR nanotherapy mitigates long COVID–like lung "
    "damage in hamsters",
    "summary": "We investigate the long-term cellular response in the lungs of golden Syrian "
    "hamsters 31 days after SARS-CoV-2 infection.",
    "gpl": "35692",
    "gse": "292461",
    "taxon": "Mesocricetus auratus",
    "entrytype": "GSE",
    "gdstype": "Expression profiling by high throughput sequencing",
    "ptechtype": "",
    "valtype": "",
    "ssinfo": "",
    "subsetinfo": "",
    "pdat": "2025/08/25",
    "suppfile": "H5",
    "samples": [
        {"accession": "GSM8859532", "title": "Caudal lung cells, control, biol rep 1"},
        {"accession": "GSM8859535", "title": "Caudal lung cells, Ctsl treated, biol rep 1"},
    ],
    "relations": [],
    "extrelations": [],
    "n_samples": 6,
    "seriestitle": "",
    "platformtitle": "",
    "platformtaxa": "",
    "samplestaxa": "",
    "pubmedids": ["41019839"],
    "projects": [],
    "ftplink": "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE292nnn/GSE292461/",
    "geo2r": "no",
    "bioproject": "PRJNA1238820",
}

ESUMMARY_ERROR = {
    "header": {"type": "esummary", "version": "0.3"},
    "result": {
        "uids": ["999999999"],
        "999999999": {"uid": "999999999", "error": "cannot get document summary"},
    },
}

ELINK_TAXONOMY = {
    "header": {"type": "elink", "version": "0.3"},
    "linksets": [
        {
            "dbfrom": "gds",
            "ids": ["200226260"],
            "linksetdbs": [{"dbto": "taxonomy", "linkname": "gds_taxonomy", "links": ["9606"]}],
        }
    ],
}
