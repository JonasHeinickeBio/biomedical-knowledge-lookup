"""Sample CellMarker tables for the unit tests.

``HEADER_2_0`` and the first five rows (macrophage / abdomen) are real: they were read from
the head of CellMarker 2.0 ``Cell_marker_Human.xlsx`` with HTTP range requests on 2026-10-06
(title/journal columns shortened). The remaining rows keep the real column layout but are
hand-written (including the PMIDs) so immune cell types and ME/CFS-relevant markers can be
exercised; do not treat them as curated CellMarker content.
"""

# Real 2.0 header: note "uberonongology_id" (sic), "Genetype", "UNIPROTID".
HEADER_2_0 = [
    "species", "tissue_class", "tissue_type", "uberonongology_id", "cancer_type", "cell_type",
    "cell_name", "cellontology_id", "marker", "Symbol", "GeneID", "Genetype", "Genename",
    "UNIPROTID", "technology_seq", "marker_source", "PMID", "Title", "journal", "year",
]  # fmt: skip

_ABD = ["Human", "Abdomen", "Abdomen", "UBERON_0000916", "Normal", "Normal cell"]
_BLOOD = ["Human", "Blood", "Peripheral blood", "UBERON_0000178", "Normal", "Normal cell"]
_LN = ["Human", "Lymph node", "Lymph node", "UBERON_0000029", "Normal", "Normal cell"]
_TAIL = ["protein_coding"]


def _row(prefix, cell, cl, marker, symbol, gene_id, name, uniprot, tech, source, pmid):
    return [
        *prefix, cell, cl, marker, symbol, gene_id, "protein_coding", name, uniprot, tech,
        source, pmid, "Title", "Journal", "2020",
    ]  # fmt: skip


ROWS_2_0 = [
    # --- real (abdomen macrophages, PMID 31982413) ---
    _row(_ABD, "Macrophage", "CL_0000235", "MERTK", "MERTK", "10461", "MER proto-oncogene, tyrosine kinase", "Q12866", "None", "Experiment", "31982413"),
    _row(_ABD, "Macrophage", "CL_0000235", "CD16", "FCGR3A", "2215", "Fc fragment of IgG receptor IIIb", "O75015", "None", "Experiment", "31982413"),
    _row(_ABD, "Macrophage", "CL_0000235", "CD206", "MRC1", "4360", "mannose receptor C-type 1", "P22897", "None", "Experiment", "31982413"),
    _row(_ABD, "Macrophage", "CL_0000235", "CRIg", "VSIG4", "11326", "V-set and immunoglobulin domain containing 4", "Q9Y279", "None", "Experiment", "31982413"),
    _row(_ABD, "Macrophage", "CL_0000235", "CD163", "CD163", "9332", "CD163 molecule", "Q86VB7", "None", "Experiment", "31982413"),
    # --- synthetic rows with the real layout ---
    _row(_BLOOD, "T cell", "CL_0000084", "CD4", "CD4", "920", "CD4 molecule", "P01730", "Single-cell sequencing", "Experiment", "10000001"),
    _row(_LN, "T cell", "CL_0000084", "CD4", "CD4", "920", "CD4 molecule", "P01730", "Flow cytometry", "Review", "10000002"),
    _row(_LN, "T cell", "CL_0000084", "CD4", "CD4", "920", "CD4 molecule", "P01730", "Flow cytometry", "Review", "10000002"),
    _row(_BLOOD, "T cell", "CL_0000084", "CD3", "CD3E", "916", "CD3 epsilon subunit of T-cell receptor complex", "P07766", "FACS", "Experiment", "10000001"),
    _row(["Mouse", "Spleen", "Spleen", "UBERON_0002106", "Normal", "Normal cell"], "T cell", "CL_0000084", "CD4", "Cd4", "12504", "CD4 antigen", "P06332", "FACS", "Experiment", "10000003"),
    _row(["Human", "Breast", "Breast", "UBERON_0000310", "Breast cancer", "Cancer cell"], "T cell", "CL_0000084", "CD8", "CD8A", "925", "CD8 subunit alpha", "P01732", "Single-cell sequencing", "Experiment", "10000004"),
    _row(_BLOOD, "Natural killer cell", "CL_0000623", "CD56", "NCAM1", "4684", "neural cell adhesion molecule 1", "P13591", "FACS", "Experiment", "10000005"),
    _row(_BLOOD, "Natural killer cell", "CL_0000623", "CD16", "FCGR3A", "2215", "Fc fragment of IgG receptor IIIb", "O75015", "FACS", "Experiment", "10000005"),
    _row(_BLOOD, "Natural killer cell", "CL_0000623", "KLRD1", "KLRD1", "3824", "killer cell lectin like receptor D1", "Q13241", "Single-cell sequencing", "Experiment", "10000006"),
    _row(_BLOOD, "B cell", "CL_0000236", "CD20", "MS4A1", "931", "membrane spanning 4-domains A1", "P11836", "FACS", "Experiment", "10000007"),
    _row(_BLOOD, "B cell", "CL_0000236", "CD19", "CD19", "930", "CD19 molecule", "P15391", "FACS", "Experiment", "10000007"),
    _row(_BLOOD, "Monocyte", "CL_0000576", "CD14", "CD14", "929", "CD14 molecule", "P08571", "FACS", "Experiment", "10000008"),
    _row(_BLOOD, "Monocyte", "CL_0000576", "CD16", "FCGR3A", "2215", "Fc fragment of IgG receptor IIIb", "O75015;A0A0X1", "FACS", "Experiment", "10000009"),
    # no Cell Ontology id, alias differs from symbol
    _row(_BLOOD, "Exhausted T cell", "", "PD-1", "PDCD1", "5133", "programmed cell death 1", "Q15968", "FACS", "Experiment", "10000010"),
    # marker without an approved symbol (kept under the marker text)
    _row(_BLOOD, "Exhausted T cell", "", "RP11-620J15.3", "", "", "", "", "None", "Experiment", ""),
    # incomplete rows that must be ignored
    _row(_BLOOD, "", "CL_0000084", "CD4", "CD4", "920", "CD4 molecule", "P01730", "FACS", "Experiment", "10000011"),
    _row(_BLOOD, "T cell", "CL_0000084", "", "", "", "", "", "FACS", "Experiment", "10000011"),
]  # fmt: skip

# CellMarker 3.0 style TSV (header copied from human_cell_marker.zip; values as in the real
# file, where Entrez ids and PMIDs are written as floats).
HEADER_3_0 = (
    "species\ttissue_class\ttissue_type\tuberon_id\tdisease_category\tdisease\t"
    "cell_name_class\tcell_name\tcellontology_id\tmarker\tsymbol\tgene_id\tgene_type\t"
    "gene_name\tuniprot_id\ttechnology_seq\tmarker_source\tpmid\ttitle\tjournal\tyear\t"
    "series_id\tmethod_details"
)
TSV_3_0 = (
    HEADER_3_0
    + "\nHuman\tBone\tBone\tUBERON_0002481\tNormal\tNormal\tProgenitor cell\tProgenitor cell\t"
    "CL_0011026\tFANCL\tFANCL\t55120.0\tprotein_coding\tFA complementation group L\tQ9NW38\t"
    "Unknown\tMethod\t40670619.0\tTitle\tcommunications biology\t2025.0\tFigshare_40670619\tCelliD"
    + "\nHuman\tBone\tBone\tUBERON_0002481\tNormal\tNormal\tProgenitor cell\tProgenitor cell\t"
    "CL_0011026\tRP11-620J15.3\t\t\t\t\t\tUnknown\tMethod\t40670619.0\tTitle\tcommunications "
    "biology\t2025.0\tFigshare_40670619\tCelliD\n"
)
