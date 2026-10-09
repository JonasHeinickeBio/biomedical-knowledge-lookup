"""Trimmed real Alliance of Genome Resources API responses (release 9.1.0), fetched 2026-10-09."""

SEARCH_BRCA1 = {
    "aggregations": [{"key": "species", "values": [{"key": "Homo sapiens", "total": 41}]}],
    "total": 136,
    "results": [
        {
            "id": "RGD:2218",
            "curie": "RGD:2218",
            "symbol": "Brca1",
            "name": "BRCA1, DNA repair associated",
            "species": "Rattus norvegicus",
            "soTermName": "protein_coding_gene",
            "synonyms": ["breast cancer 1, early onset", "BRCA-1", "Brca1"],
            "diseases": ["breast cancer", "ovarian cancer"],
            "automatedGeneDescription": "Enables chromatin binding activity.",
            "geneDescription": "Enables chromatin binding activity (MOD).",
            "crossReferences": ["UniProtKB:G3V8S5", "PANTHER:PTHR13763"],
            "category": "gene_search_result",
        },
        {
            "id": "HGNC:1100",
            "curie": "HGNC:1100",
            "symbol": "BRCA1",
            "name": "BRCA1 DNA repair associated",
            "species": "Homo sapiens",
            "soTermName": "protein_coding_gene",
            "synonyms": ["BRCC1", "RNF53", "BRCA1"],
            "diseases": ["breast cancer"],
            "automatedGeneDescription": "Enables ubiquitin protein ligase activity.",
            "crossReferences": ["NCBI_Gene:672", "ENSEMBL:ENSG00000012048"],
            "category": "gene_search_result",
        },
        {
            "id": "HGNC:58363",
            "symbol": "BRCA1-OT1",
            "name": "BRCA1 overlapping transcript 1",
            "species": "Homo sapiens",
            "soTermName": "ncRNA_gene",
            "category": "gene_search_result",
        },
        {
            "id": "MGI:104537",
            "symbol": "Brca1",
            "name": "breast cancer 1, early onset",
            "species": "Mus musculus",
            "soTermName": "protein_coding_gene",
            "synonyms": ["Brca1"],
            "category": "gene_search_result",
        },
        {"symbol": "NoId", "species": "Homo sapiens"},
        {"id": "HGNC:1", "species": "Homo sapiens"},
    ],
}

SEARCH_EMPTY = {"aggregations": [{"key": "species"}], "total": 0}

SEARCH_SOD1_ONLY_FLY = {
    "total": 1,
    "results": [
        {
            "id": "FB:FBgn0003462",
            "symbol": "Sod1",
            "name": "Superoxide dismutase 1",
            "species": "Drosophila melanogaster",
        }
    ],
}


def _uniprot(n):
    return [{"referencedCurie": f"UniProtKB:A0A{i:06d}"} for i in range(n)]


GENE_HGNC_BRCA1 = {
    "category": "gene_summary",
    "searchable": False,
    "gene": {
        "type": "Gene",
        "primaryExternalId": "HGNC:1100",
        "geneSymbol": {"formatText": "BRCA1", "displayText": "BRCA1"},
        "geneFullName": {
            "formatText": "BRCA1 DNA repair associated",
            "displayText": "BRCA1 DNA repair associated",
        },
        "geneSynonyms": [
            {"displayText": "BROVCA1"},
            {"displayText": "IRIS"},
            {"displayText": "BROVCA1"},
            {"displayText": "BRCA1"},
        ],
        "geneType": {"curie": "SO:0001217", "name": "protein_coding_gene"},
        "taxon": {"curie": "NCBITaxon:9606", "name": "Homo sapiens"},
        "relatedNotes": [
            {"noteType": {"name": "MOD_provided_gene_description"}, "freeText": "MOD text."},
            {"noteType": {"name": "automated_gene_description"}, "freeText": "Automated text."},
            "junk",
        ],
        "gcrpCrossReference": {"referencedCurie": "UniProtKB:P38398"},
        "crossReferences": [
            {"referencedCurie": "RGD:69132"},
            {"referencedCurie": "ENSEMBL:ENSG00000012048"},
            {"referencedCurie": "HGNC:1100"},
            {"referencedCurie": "NCBI_Gene:672"},
            {"referencedCurie": "OMIM:113705"},
            {"referencedCurie": "PANTHER:PTHR13763"},
            {"referencedCurie": "UniProtKB:P38398"},
            *_uniprot(8),
            {"referencedCurie": "BioGRID:1"},
            {"displayName": "no curie"},
            "junk",
        ],
        "geneGenomicLocationAssociations": [
            {
                "start": 43044292,
                "end": 43170327,
                "strand": "-",
                "geneGenomicLocationAssociationObject": {
                    "type": "AssemblyComponent",
                    "name": "17",
                },
            }
        ],
    },
}

GENE_ZFIN_FGF8A = {
    "gene": {
        "primaryExternalId": "ZFIN:ZDB-GENE-990415-72",
        "geneSymbol": {"displayText": "fgf8a"},
        "geneFullName": {"displayText": "fibroblast growth factor 8a"},
        "taxon": {"curie": "NCBITaxon:7955", "name": "Danio rerio"},
        "relatedNotes": [
            {"noteType": {"name": "automated_gene_description"}, "freeText": "Automated only."}
        ],
        "crossReferences": [{"referencedCurie": "ZFIN:ZDB-GENE-990415-72"}],
    }
}

GENE_BARE = {"primaryExternalId": "MGI:1", "geneSymbol": {"displayText": "Abc1"}}


def _ortholog(gene_id, symbol, taxon, best="Yes", matched=("PANTHER",), not_matched=()):
    return {
        "category": "gene_to_gene_orthology",
        "stringencyFilter": "stringent",
        "geneToGeneOrthologyGenerated": {
            "subjectGene": {"primaryExternalId": "HGNC:1100"},
            "objectGene": {
                "primaryExternalId": gene_id,
                "geneSymbol": {"displayText": symbol},
                "taxon": {"name": taxon},
            },
            "isBestScore": {"name": best},
            "isBestScoreReverse": {"name": "Yes"},
            "confidence": {"name": "high"},
            "predictionMethodsMatched": [{"name": m} for m in matched],
            "predictionMethodsNotMatched": [{"name": m} for m in not_matched],
        },
    }


ORTHOLOGS_BRCA1 = {
    "total": 5,
    "returnedRecords": 4,
    "results": [
        _ortholog(
            "MGI:104537",
            "Brca1",
            "Mus musculus",
            matched=("Ensembl Compara", "OMA", "PANTHER"),
            not_matched=("PhylomeDB",),
        ),
        _ortholog("WB:WBGene00000264", "brc-1", "Caenorhabditis elegans", best="No"),
        {"category": "gene_to_gene_orthology", "geneToGeneOrthologyGenerated": {}},
        {"geneToGeneOrthologyGenerated": {"objectGene": {"geneSymbol": {"displayText": "x"}}}},
    ],
}


def _disease(doid, name, relation, evidence):
    return {
        "category": "gene_disease_annotation",
        "subject": {"primaryExternalId": "HGNC:1100"},
        "relation": {"name": relation},
        "object": {"curie": doid, "name": name},
        "evidenceCodes": [{"curie": "ECO:0000033", "abbreviation": evidence}] if evidence else [],
    }


DISEASES_BRCA1 = {
    "total": 30,
    "returnedRecords": 5,
    "results": [
        _disease("DOID:3458", "breast adenocarcinoma", "is_implicated_in", "IMP"),
        _disease("DOID:1612", "breast cancer", "is_marker_for", "IEP"),
        _disease("DOID:1612", "breast cancer", "is_marker_for", "IEP"),  # duplicate row
        _disease("DOID:1612", "breast cancer", "is_implicated_in", None),
        {"object": {"name": "no curie"}, "relation": {"name": "x"}},
        "junk",
    ],
}


def _phenotype(statement, curie, n_annotations=1, pubs=("PMID:1",)):
    terms = [{"curie": curie, "name": statement}] if curie else []
    return {
        "category": "gene_phenotype_annotation",
        "phenotypeStatement": statement,
        "primaryAnnotations": [{"phenotypeTerms": terms} for _ in range(n_annotations)],
        "pubmedPublications": [{"referencedCurie": p} for p in pubs],
    }


PHENOTYPES_BRCA1 = {
    "total": 166,
    "returnedRecords": 5,
    "results": [
        _phenotype("Abdominal distention", "HP:0003270", pubs=("ORPHA:168829",)),
        _phenotype(
            "Abdominal pain", "HP:0002027", n_annotations=3, pubs=tuple(f"P{i}" for i in range(8))
        ),
        _phenotype("Abdominal pain", "HP:0002027"),  # duplicate term
        _phenotype("free text only phenotype", None),
        {"phenotypeStatement": "", "primaryAnnotations": []},
        "junk",
    ],
}


def _interaction(subject, partner, symbol, kind="physical association"):
    return {
        "category": "gene_molecular_interaction",
        "geneMolecularInteraction": {
            "geneAssociationSubject": {
                "primaryExternalId": subject,
                "geneSymbol": {"displayText": "S"},
            },
            "geneGeneAssociationObject": {
                "primaryExternalId": partner,
                "geneSymbol": {"displayText": symbol},
            },
            "interactionType": {"curie": "MI:0915", "name": kind},
            "detectionMethod": {"curie": "MI:0004", "name": "affinity chromatography technology"},
            "interactionSource": {"curie": "MI:0463", "name": "biogrid"},
        },
    }


INTERACTIONS_BRCA1 = {
    "total": 2499,
    "returnedRecords": 6,
    "results": [
        _interaction("HGNC:1100", "HGNC:13666", "AAAS"),
        _interaction("HGNC:1100", "HGNC:13666", "AAAS"),  # same partner, other experiment
        _interaction("HGNC:20", "HGNC:1100", "BRCA1"),  # queried gene is the object
        _interaction("HGNC:1100", "HGNC:1100", "BRCA1"),  # self interaction
        _interaction("HGNC:1100", "", "nobody"),
        {"geneMolecularInteraction": "junk"},
    ],
}
