"""CTD bulk-file fixtures (``CTD_*.csv.gz`` text before gzip), release 2026-09-29.

Rows are REAL lines taken from the first 40 KB of the live files (HTTP Range request), except
the ones listed here, which are SYNTHETIC but follow the documented column layout exactly:

* CHEMICALS: the ``C112297`` row (only the name and id are filled in);
* DISEASES: ``Hyperkinesis`` and ``Epilepsy`` rows (name and MeSH id only);
* GENES and GENE_DISEASES: the whole content (those files are 123 MB and 3.2 GB, so no real
  sample containing a human gene or a curated row could be fetched with a prefix Range).
"""

import gzip
from pathlib import Path

CHEMICALS = """
# The Comparative Toxicogenomics Database (CTD) - http://ctdbase.org/
#   Copyright 2002-2012 MDI Biological Laboratory. All rights reserved.
#   Copyright 2012-2026 NC State University. All rights reserved.
#
#
# Use is subject to the terms set forth at http://ctdbase.org/about/legal.jsp
# These terms include:
#
#   1. All forms of publication (e.g., web sites, research papers, databases,
#      software applications, etc.) that use or rely on CTD data must cite CTD.
#      Citation guidelines: http://ctdbase.org/about/publications/#citing
#
# ...
#
# Fields:
# ChemicalName,ChemicalID,CasRN,PubChemCID,PubChemSID,DTXSID,InChIKey,Definition,ParentIDs,TreeNumbers,ParentTreeNumbers,MESHSynonyms,CTDCuratedSynonyms
#
0-acetylpantolactone,MESH:C014305,28227-36-3,,,,,,MESH:D015107,D02.540.150/C014305|D03.383.312.150/C014305,D02.540.150|D03.383.312.150,"2(3H)-Furanone, 3-(acetyloxy)dihydro-4,4-dimethyl-, (R)-",
10074-G5,MESH:C534883,,CID:2836600,SID:252090125,,,,MESH:D010069,D03.383.129.462.580/C534883,D03.383.129.462.580,,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",MESH:C112297,,,,,,,,,,,
"""

DISEASES = """
# The Comparative Toxicogenomics Database (CTD) - http://ctdbase.org/
#   Copyright 2002-2012 MDI Biological Laboratory. All rights reserved.
#   Copyright 2012-2026 NC State University. All rights reserved.
#
#
# Use is subject to the terms set forth at http://ctdbase.org/about/legal.jsp
# These terms include:
#
#   1. All forms of publication (e.g., web sites, research papers, databases,
#      software applications, etc.) that use or rely on CTD data must cite CTD.
#      Citation guidelines: http://ctdbase.org/about/publications/#citing
#
# ...
#
# Fields:
# DiseaseName,DiseaseID,AltDiseaseIDs,Definition,ParentIDs,TreeNumbers,ParentTreeNumbers,Synonyms,SlimMappings
#
17-Hydroxysteroid Dehydrogenase Deficiency,MESH:C537805,OMIM:264300,,MESH:D006177|MESH:D043202|MESH:D058490,C12.050.351.875.253.096/C537805|C12.200.706.316.096/C537805|C12.800.316.096/C537805|C16.131.939.316.096/C537805|C16.320.565.925/C537805|C17.800.090.875/C537805|C18.452.648.925/C537805|C19.391.119.096/C537805,C12.050.351.875.253.096|C12.200.706.316.096|C12.800.316.096|C16.131.939.316.096|C16.320.565.925|C17.800.090.875|C18.452.648.925|C19.391.119.096,"17 alpha ketosteroid reductase deficiency of testis|17-Beta Hydroxysteroid Dehydrogenase 3 Deficiency|17 Beta-hydroxysteroid dehydrogenase deficiency|17-Beta Hydroxysteroid Dehydrogenase III Deficiency|17-Ketosteroid Reductase Deficiency Of Testis|17-Ksr Deficiency|Male pseudohermaphroditism with gynecomastia|Neutral 17 beta-hydroxysteroid oxidoreductase deficiency|Neutral 17-Beta-Hydroxysteroid Oxidoreductase Deficiency|Pseudohermaphroditism, Male, with Gynecomastia|PSEUDOHERMAPHRODITISM, MALE, WITH GYNECOMASTIA POLYCYSTIC OVARY SYNDROME DUE TO 17-KETOSTEROID REDUCTASE DEFICIENCY, INCLUDED",Congenital abnormality|Endocrine system disease|Genetic disease (inborn)|Metabolic disease|Skin disease|Urogenital disease (female)|Urogenital disease (male)
18-Hydroxylase deficiency,MESH:C537806,OMIM:203400|OMIM:610600,,MESH:D006994,C19.053.500.480/C537806,C19.053.500.480,"18-alpha hydroxylase deficiency|18-HYDROXYLASE DEFICIENCY|18-Oxidase Deficiency|Aldosterone deficiency 1|Aldosterone deficiency due to defect in 18-hydroxylase|ALDOSTERONE DEFICIENCY DUE TO DEFECT IN STEROID 18-HYDROXYLASE|ALDOSTERONE DEFICIENCY DUE TO DEFICIENCY OF STEROID 18-OXIDASE|ALDOSTERONE DEFICIENCY I|ALDOSTERONE DEFICIENCY II|Aldosterone Deficiency Type I|Aldosterone Deficiency Type II|CMO I Deficiency|CMO II Deficiency|Corticosterone methyloxidase type 1 deficiency|Corticosterone Methyloxidase Type I Deficiency|Corticosterone Methyloxidase Type II Deficiency|FHHA1A|FHHA1B|HYPERRENINEMIC HYPOALDOSTERONISM, FAMILIAL, 1|Hyperreninemic Hypoaldosteronism, Familial, Type I|Steroid 18-Hydroxylase Deficiency|Steroid 18-Oxidase Deficiency",Endocrine system disease
Hyperkinesis,MESH:D006948,,,,,,,
Epilepsy,MESH:D004827,,,,,,,
"""

IXNS = """
# The Comparative Toxicogenomics Database (CTD) - http://ctdbase.org/
#   Copyright 2002-2012 MDI Biological Laboratory. All rights reserved.
#   Copyright 2012-2026 NC State University. All rights reserved.
#
#
# Use is subject to the terms set forth at http://ctdbase.org/about/legal.jsp
# These terms include:
#
#   1. All forms of publication (e.g., web sites, research papers, databases,
#      software applications, etc.) that use or rely on CTD data must cite CTD.
#      Citation guidelines: http://ctdbase.org/about/publications/#citing
#
# ...
#
# Fields:
# ChemicalName,ChemicalID,CasRN,GeneSymbol,GeneID,GeneForms,Organism,OrganismID,Interaction,InteractionActions,PubMedIDs
#
10074-G5,C534883,,AR,367,protein,Homo sapiens,9606,10074-G5 affects the reaction [MYC protein results in increased expression of AR protein],affects^reaction|increases^expression,32184358
10074-G5,C534883,,AR,367,protein,Homo sapiens,9606,10074-G5 inhibits the reaction [EPHB2 protein modified form results in increased expression of AR protein],decreases^reaction|increases^expression,32184358
10074-G5,C534883,,AR,367,protein,Homo sapiens,9606,10074-G5 results in decreased expression of AR protein,decreases^expression,32184358
10074-G5,C534883,,AR,367,protein,Homo sapiens,9606,10074-G5 results in decreased expression of AR protein alternative form,decreases^expression,32184358
10074-G5,C534883,,EPHB2,2048,protein,Homo sapiens,9606,10074-G5 inhibits the reaction [EPHB2 protein modified form results in increased expression of AR protein],decreases^reaction|increases^expression,32184358
10074-G5,C534883,,EPHB2,2048,protein,Homo sapiens,9606,10074-G5 inhibits the reaction [EPHB2 protein modified form results in increased expression of MYC protein],decreases^reaction|increases^expression,32184358
10074-G5,C534883,,MAX,4149,protein,,,10074-G5 affects the folding of and results in decreased activity of [MYC protein binds to MAX protein],affects^binding|affects^folding|decreases^activity,26474287
10074-G5,C534883,,MAX,4149,protein,,,10074-G5 inhibits the reaction [MYC protein binds to MAX protein],affects^binding|decreases^reaction,26474287
10074-G5,C534883,,MYC,4609,protein,Homo sapiens,9606,10074-G5 affects the reaction [MYC protein results in increased expression of AR protein],affects^reaction|increases^expression,32184358
10074-G5,C534883,,MYC,4609,protein,Homo sapiens,9606,10074-G5 analog results in decreased expression of MYC protein,decreases^expression,26036281
10074-G5,C534883,,MYC,4609,protein,Homo sapiens,9606,10074-G5 inhibits the reaction [EPHB2 protein modified form results in increased expression of MYC protein],decreases^reaction|increases^expression,32184358
10074-G5,C534883,,MYC,4609,protein,Homo sapiens,9606,10074-G5 results in decreased activity of MYC protein,decreases^activity,25716159
10074-G5,C534883,,MYC,4609,protein,Homo sapiens,9606,10074-G5 results in decreased expression of MYC protein,decreases^expression,26036281|32184358
10074-G5,C534883,,MYC,4609,protein,,,10074-G5 affects the folding of and results in decreased activity of [MYC protein binds to MAX protein],affects^binding|affects^folding|decreases^activity,26474287
10074-G5,C534883,,MYC,4609,protein,,,10074-G5 inhibits the reaction [MYC protein binds to MAX protein],affects^binding|decreases^reaction,26474287
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,FOS,2353,protein,Mus musculus,10090,"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone inhibits the reaction [Valproic Acid inhibits the reaction [Kainic Acid results in increased expression of FOS protein]]",decreases^reaction|increases^expression,26348896
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,KCNQ1,3784,protein,,,"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone results in decreased activity of KCNQ1 protein",decreases^activity,18568022
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,KCNQ2,3785,protein,Homo sapiens,9606,"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone results in decreased activity of KCNQ2 protein",decreases^activity,35550413
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,KCNQ2,3785,protein,Mus musculus,10090,"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone affects the reaction [[Potassium results in increased activity of KCNQ2 protein] which results in increased import of Thallium]",affects^reaction|increases^activity|increases^import,15634793
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,KCNQ2,3785,protein,,,"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone inhibits the reaction [[KCNQ2 protein binds to KCNQ3 protein] which results in increased transport of Thallium]",affects^binding|decreases^reaction|increases^transport,20208034
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,KCNQ3,3786,protein,,,"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone inhibits the reaction [[KCNQ2 protein binds to KCNQ3 protein] which results in increased transport of Thallium]",affects^binding|decreases^reaction|increases^transport,20208034
"""

CHEM_DISEASES = """
# The Comparative Toxicogenomics Database (CTD) - http://ctdbase.org/
#   Copyright 2002-2012 MDI Biological Laboratory. All rights reserved.
#   Copyright 2012-2026 NC State University. All rights reserved.
#
#
# Use is subject to the terms set forth at http://ctdbase.org/about/legal.jsp
# These terms include:
#
#   1. All forms of publication (e.g., web sites, research papers, databases,
#      software applications, etc.) that use or rely on CTD data must cite CTD.
#      Citation guidelines: http://ctdbase.org/about/publications/#citing
#
# ...
#
# Fields:
# ChemicalName,ChemicalID,CasRN,DiseaseName,DiseaseID,DirectEvidence,InferenceGeneSymbol,InferenceScore,OmimIDs,PubMedIDs
#
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Adenocarcinoma,MESH:D000230,,KCNQ1,4.67,,23975432
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Amphetamine-Related Disorders,MESH:D019969,,FOS,4.18,,19689456
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Amyotrophic lateral sclerosis 1,MESH:C531617,,FOS,4.65,,11796754
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Anxiety Disorders,MESH:D001008,,FOS,3.70,,16488545
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Arthritis, Juvenile",MESH:D001171,,FOS,4.16,,19565504
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Atrial Fibrillation, Familial, 3",MESH:C563817,,KCNQ1,7.55,607554,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Beckwith-Wiedemann Syndrome,MESH:D001506,,KCNQ1,6.74,130650,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Brain Diseases,MESH:D001927,,KCNQ2,4.86,,27602407
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Brain Injuries,MESH:D001930,,FOS,3.73,,9630518
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Breast Neoplasms,MESH:D001943,,FOS,3.21,,16298037
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Carcinoma, Hepatocellular",MESH:D006528,,FOS,3.32,,28284560|9029167
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Carcinoma, Ovarian Epithelial",MESH:D000077216,,FOS,4.75,,28811376
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Cell Transformation, Neoplastic",MESH:D002471,,FOS,3.70,,8777434
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Cholestasis, Extrahepatic",MESH:D001651,,FOS,4.75,,28789951
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Cocaine-Related Disorders,MESH:D019970,,FOS,3.60,,17276011|18311559|19533625
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,DEVELOPMENTAL AND EPILEPTIC ENCEPHALOPATHY 7,OMIM:613720,,KCNQ2,7.68,613720,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Developmental Disabilities,MESH:D002658,,KCNQ2,5.49,,20805988|27602407
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Diabetes Mellitus, Type 2",MESH:D003924,,KCNQ1,4.57,,18711366|18711367|26551672
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Disease Models, Animal",MESH:D004195,,FOS,3.53,,27093858
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Endometriosis,MESH:D004715,,FOS,4.01,,23284138
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Epilepsy,MESH:D004827,,FOS,9.12,,15973680
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Epilepsy,MESH:D004827,,KCNQ2,9.12,,16464983|29942082
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Epilepsy, Benign Neonatal",MESH:D020936,,KCNQ2,7.34,,19380078|26910900
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Fibrous Dysplasia of Bone,MESH:D005357,,FOS,5.75,,7739708
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Hearing Loss, Noise-Induced",MESH:D006317,,KCNQ1,5.78,,16823764
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Heat Stroke,MESH:D018883,,FOS,4.84,,24039931
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Hemorrhage,MESH:D006470,,FOS,3.68,,7844257
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Hyperalgesia,MESH:D006930,,FOS,3.46,,27093858
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Hyperkinesis,MESH:D006948,marker/mechanism,,,,19098162
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Hyperkinesis,MESH:D006948,,FOS,3.61,,18355967
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Hypertension,MESH:D006973,,FOS,3.18,,12044476|24039778
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Infarction, Middle Cerebral Artery",MESH:D020244,,FOS,4.41,,12374626
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Intestinal Neoplasms,MESH:D007414,,KCNQ1,5.47,,23975432
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Jervell-Lange Nielsen Syndrome,MESH:D029593,,KCNQ1,7.20,220400,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"Liver Cirrhosis, Experimental",MESH:D008106,,FOS,3.22,,25380136
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Long QT Syndrome,MESH:D008133,,KCNQ1,4.83,,10868744|14510655|15028050|17467628|18329740|20513597|22910039
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Lung Neoplasms,MESH:D008175,,FOS,3.44,,16289808
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Nervous System Diseases,MESH:D009422,,FOS,8.45,,12890883
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Nervous System Diseases,MESH:D009422,,KCNQ2,8.45,,20805988
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Neurodevelopmental Disorders,MESH:D065886,,KCNQ2,5.33,,29942082
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Neurotoxicity Syndromes,MESH:D020258,,FOS,3.76,,19220411
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Obesity,MESH:D009765,,FOS,3.67,,27071101
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Reperfusion Injury,MESH:D015427,,FOS,3.87,,7922267
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Romano-Ward Syndrome,MESH:D029597,,KCNQ1,7.20,192500,15004216
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Seizures,MESH:D012640,marker/mechanism,,,,26348896
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Seizures,MESH:D012640,,FOS,6.45,,11955713|12946577|8923670|9630518
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Seizures,MESH:D012640,,KCNQ2,6.45,,27602407
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"SEIZURES, BENIGN FAMILIAL NEONATAL, 1",OMIM:121200,,KCNQ2,7.68,121200,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,"SEIZURES, BENIGN FAMILIAL NEONATAL, 2",OMIM:121201,,KCNQ3,7.79,121201,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Short QT Syndrome 2,MESH:C566505,,KCNQ1,7.55,609621,
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Status Epilepticus,MESH:D013226,,FOS,3.87,,16696126|18587450|18988310|7984056
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Substance Withdrawal Syndrome,MESH:D013375,,FOS,3.61,,15196791|15196794|18485423
"10,10-bis(4-pyridinylmethyl)-9(10H)-anthracenone",C112297,,Trigeminal Neuralgia,MESH:D014277,,FOS,5.00,,27093858
10074-G5,C534883,,Adenocarcinoma,MESH:D000230,,MYC,4.08,,26432044
10074-G5,C534883,,Adenocarcinoma of Lung,MESH:D000077192,,MYC,4.31,,26656844|27602772
10074-G5,C534883,,Alopecia,MESH:D000505,,AR,4.51,,15902657
10074-G5,C534883,,Androgen-Insensitivity Syndrome,MESH:D013734,,AR,6.89,300068|312300,1303262|8281139
10074-G5,C534883,,Astrocytoma,MESH:D001254,,AR,4.97,,24680642
"10,11-dihydroxy-N-n-propylnorapomorphine",C425777,,Hyperkinesis,MESH:D006948,marker/mechanism,,,,15765258
10-(fluoroethoxyphosphinyl)-N-(biotinamidopentyl)decanamide,C403065,,Hyperkinesis,MESH:D006948,,BCHE,3.65,,12019200
"""

GENES = """
# The Comparative Toxicogenomics Database (CTD) - http://ctdbase.org/
#   Copyright 2002-2012 MDI Biological Laboratory. All rights reserved.
#   Copyright 2012-2026 NC State University. All rights reserved.
#
#
# Use is subject to the terms set forth at http://ctdbase.org/about/legal.jsp
# These terms include:
#
#   1. All forms of publication (e.g., web sites, research papers, databases,
#      software applications, etc.) that use or rely on CTD data must cite CTD.
#      Citation guidelines: http://ctdbase.org/about/publications/#citing
#
# ...
#
# Fields:
# GeneSymbol,GeneName,GeneID,AltGeneIDs,Synonyms,BioGRIDIDs,PharmGKBIDs,UniProtIDs
#
AR,androgen receptor,367,,AIS|DHTR|HUMARA|KD|NR3C4|SBMA|TFM,,PA1665|PA24,P10275
"""

GENE_DISEASES = """
# The Comparative Toxicogenomics Database (CTD) - http://ctdbase.org/
#   Copyright 2002-2012 MDI Biological Laboratory. All rights reserved.
#   Copyright 2012-2026 NC State University. All rights reserved.
#
#
# Use is subject to the terms set forth at http://ctdbase.org/about/legal.jsp
# These terms include:
#
#   1. All forms of publication (e.g., web sites, research papers, databases,
#      software applications, etc.) that use or rely on CTD data must cite CTD.
#      Citation guidelines: http://ctdbase.org/about/publications/#citing
#
# ...
#
# Fields:
# GeneSymbol,GeneID,DiseaseName,DiseaseID,DirectEvidence,InferenceChemicalName,InferenceScore,OmimIDs,PubMedIDs
#
AR,367,Hyperkinesis,MESH:D006948,marker/mechanism,,,,11111111|22222222
AR,367,Epilepsy,MESH:D004827,therapeutic,,,,33333333
AR,367,Adenocarcinoma,MESH:D000230,,Some Chemical,5.5,,44444444
"""


REQUIRED_FILES = {
    "CTD_chemicals.csv.gz": CHEMICALS,
    "CTD_diseases.csv.gz": DISEASES,
    "CTD_chem_gene_ixns.csv.gz": IXNS,
    "CTD_chemicals_diseases.csv.gz": CHEM_DISEASES,
}
OPTIONAL_FILES = {
    "CTD_genes.csv.gz": GENES,
    "CTD_genes_diseases.csv.gz": GENE_DISEASES,
}


def write_ctd_files(directory, optional=False):
    """Write the fixtures as gzipped CTD reports into ``directory``."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = dict(REQUIRED_FILES)
    if optional:
        files.update(OPTIONAL_FILES)
    for name, text in files.items():
        with gzip.open(directory / name, "wt", encoding="utf-8") as handle:
            handle.write(text.lstrip("\n"))
    return directory
