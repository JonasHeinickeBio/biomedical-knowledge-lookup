"""Trimmed real NCBI E-utilities (db=medgen) responses, fetched 2026-10-07."""

ESEARCH_CFS = {
    "header": {"type": "esearch", "version": "0.3"},
    "esearchresult": {
        "count": "1",
        "retmax": "1",
        "retstart": "0",
        "idlist": ["5130"],
        "translationset": [],
        "translationstack": [
            {
                "term": "chronic fatigue syndrome[All Fields]",
                "field": "All Fields",
                "count": "1",
                "explode": "N",
            },
            "GROUP",
        ],
        "querytranslation": "chronic fatigue syndrome[All Fields]",
    },
}

ESEARCH_EMPTY = {
    "header": {"type": "esearch", "version": "0.3"},
    "esearchresult": {"count": "0", "retmax": "0", "retstart": "0", "idlist": []},
}

DOC_CFS = {
    "uid": "5130",
    "conceptid": "C0015674",
    "title": "Myalgic encephalomeyelitis/chronic fatigue syndrome",
    "definition": {
        "value": "A syndrome of unknown etiology. Chronic fatigue syndrome (CFS) is a "
        "clinical diagnosis characterized by an unexplained persistent or "
        "relapsing chronic fatigue that is of at least six months'' duration, "
        "is not the result."
    },
    "semanticid": "T047",
    "semantictype": {"value": "Disease or Syndrome"},
    "suppressed": "",
    "conceptmeta": '<Names><Name SDUI="D015673" SCUI="M0024027" CODE="D015673" SAB="MSH" TTY="PM" '
    'type="syn">Chronic Fatigue Syndromes</Name><Name SDUI="D015673" '
    'SCUI="M0024027" CODE="D015673" SAB="MSH" TTY="MH" type="syn">Fatigue '
    'Syndrome, Chronic</Name><Name SCUI="C3037" CODE="C3037" SAB="NCI" TTY="SY" '
    'type="syn">Myalgic Encephalomyelitis</Name><Name SCUI="52702003" '
    'CODE="52702003" SAB="SNOMEDCT_US" TTY="SY" type="syn">Benign myalgic '
    'encephalomyelitis</Name><Name SCUI="52702003" CODE="52702003" '
    'SAB="SNOMEDCT_US" TTY="SY" type="syn">Iceland disease</Name><Name '
    'SCUI="C3037" CODE="C3037" SAB="NCI" TTY="PT" type="syn">Chronic Fatigue '
    'Syndrome</Name><Name SDUI="GTRT000046815" CODE="AN1482066" SAB="GTR" TTY="PT" '
    'type="preferred">Myalgic encephalomeyelitis/chronic fatigue '
    'syndrome</Name><Name SDUI="MONDO:0005404" SCUI="GTRT000046815" '
    'CODE="MONDO_0005404" SAB="MONDO" TTY="PT" type="syn">myalgic '
    'encephalomeyelitis/chronic fatigue syndrome</Name><Name SDUI="MONDO:0005404" '
    'SCUI="GTRT000046815" CODE="AN1605116" SAB="MONDO" TTY="SYN" '
    'type="syn">CFS</Name><Name SDUI="Orphanet_1983" SCUI="GTRT000046815" '
    'CODE="AN1791647" SAB="ORDO" TTY="PT" type="syn">NON RARE IN EUROPE: Chronic '
    'fatigue syndrome</Name><Name SDUI="Orphanet_1983" SCUI="GTRT000046815" '
    'CODE="AN1791733" SAB="ORDO" TTY="SYN" type="syn">Myalgic '
    'encephalomyelitis</Name><Name SDUI="GTRT000046815" CODE="AN1923590" SAB="GTR" '
    'TTY="SYN" type="syn">Chronic fatigue '
    'syndrome</Name></Names><Definitions><Definition source="NCI">A syndrome of '
    "unknown etiology. Chronic fatigue syndrome (CFS) is a clinical diagnosis "
    "characterized by an unexplained persistent or relapsing chronic fatigue that "
    "is of at least six months'' duration, is not the "
    "result.</Definition></Definitions><ModesOfInheritance "
    "/><PharmacologicResponse /><OMIM /><ClinicalFeatures "
    "/><PhenotypicAbnormalities /><RelatedDisorders /><SNOMEDCT><Name "
    'SAUI="496409016" SCUI="52702003" SAB="SNOMEDCT_US" TTY="SY">Myalgic '
    'encephalomyelitis syndrome</Name><Name SAUI="496410014" SCUI="52702003" '
    'SAB="SNOMEDCT_US" TTY="SY">ME - Myalgic '
    "encephalomyelitis</Name></SNOMEDCT><AssociatedGenes "
    '/><SemanticTypes><SemanticType TUI="T047">Disease or '
    "Syndrome</SemanticType></SemanticTypes>",
    "modificationdate": "",
    "merged": "",
}

DOC_MARFAN = {
    "uid": "44287",
    "conceptid": "C0024796",
    "title": "Marfan syndrome",
    "definition": {
        "value": "FBN1-related Marfan syndrome (Marfan syndrome), a systemic disorder "
        "of connective tissue with a high degree of clinical variability, "
        "comprises a broad phenotypic continuum ranging from mild (features "
        "of Marfan syndrome."
    },
    "semanticid": "T047",
    "semantictype": {"value": "Disease or Syndrome"},
    "suppressed": "",
    "conceptmeta": '<Names><Name SDUI="D008382" SCUI="M0013029" CODE="D008382" SAB="MSH" TTY="MH" '
    'type="syn">Marfan Syndrome</Name><Name SDUI="D008382" SCUI="M0013029" '
    'CODE="D008382" SAB="MSH" TTY="PM" type="syn">Marfans Syndrome</Name><Name '
    'SDUI="154700" CODE="154700" SAB="OMIM" TTY="PT" type="syn">MARFAN '
    'SYNDROME</Name><Name SDUI="154700" CODE="154700" SAB="OMIM" TTY="ACR" '
    'type="syn">MFS</Name><Name SCUI="C34807" CODE="C34807" SAB="NCI" TTY="PT" '
    'type="syn">Marfan Syndrome</Name><Name SCUI="C34807" CODE="C34807" SAB="NCI" '
    'TTY="SY" type="syn">Marfan\'s Syndrome</Name><Name SCUI="19346006" '
    'CODE="19346006" SAB="SNOMEDCT_US" TTY="SY" type="preferred">Marfan '
    'syndrome</Name><Name SCUI="19346006" CODE="19346006" SAB="SNOMEDCT_US" '
    'TTY="PT" type="syn">Marfan\'s syndrome</Name><Name SDUI="GTRT000002645" '
    'CODE="AN0086584" SAB="GTR" TTY="PT" type="preferred">Marfan '
    'syndrome</Name><Name SDUI="GTRT000002645" CODE="AN0086585" SAB="GTR" '
    'TTY="SYN" type="syn">MARFAN SYNDROME, TYPE I</Name><Name '
    'SDUI="Orphanet_284963" SCUI="GTRT000002645" CODE="AN0463737" SAB="ORDO" '
    'TTY="SYN" type="syn">MFS1</Name><Name SDUI="Orphanet_558" '
    'SCUI="GTRT000002645" CODE="AN0468520" SAB="ORDO" TTY="SYN" '
    'type="syn">MFS</Name><Name SDUI="MONDO:0007947" SCUI="GTRT000002645" '
    'CODE="MONDO_0007947" SAB="MONDO" TTY="PT" type="preferred">Marfan '
    'syndrome</Name><Name SDUI="MONDO:0007947" SCUI="GTRT000002645" '
    'CODE="AN1589293" SAB="MONDO" TTY="SYN" type="syn">Marfan\'s '
    'syndrome</Name><Name SDUI="NBK1335" SCUI="GTRT000002645" CODE="NBK1335" '
    'SAB="GENEREVIEWS" TTY="PT" type="syn">FBN1-Related Marfan '
    "Syndrome</Name></Names><Definitions><Definition "
    'source="GeneReviews">FBN1-related Marfan syndrome (Marfan syndrome), a '
    "systemic disorder of connective tissue with a high degree of clinical "
    "variability, comprises a broad phenotypic continuum ranging from mild "
    "(features of Marfan "
    "syndrome.</Definition></Definitions><Chromosome>15</Chromosome><Cytogenetic>15q21.1</Cytogenetic><ModesOfInheritance><ModeOfInheritance "
    'uid="141047" CUI="C0443147" TUI="T170"><Name>Autosomal dominant '
    "inheritance</Name><SemanticType>Intellectual "
    "Product</SemanticType><Definition>A mode of inheritance that is observed for "
    "traits related to a gene encoded on one of the autosomes (i.e., the human "
    "chromosomes 1-22) in which a trait manifests in heterozygotes. In the context "
    "of medical genetics, "
    "an.</Definition><SAB>ORDO</SAB></ModeOfInheritance></ModesOfInheritance><PharmacologicResponse "
    '/><OMIM><MIM>154700</MIM></OMIM><ClinicalFeatures><ClinicalFeature uid="8153" '
    'CUI="C0003504" TUI="T047" SDUI="HP:0001659"><Name>Aortic '
    "regurgitation</Name><SemanticType>Disease or "
    "Syndrome</SemanticType><Definition>An insufficiency of the aortic valve, "
    "leading to regurgitation (backward flow) of blood from the aorta into the "
    'left ventricle.</Definition></ClinicalFeature><ClinicalFeature uid="2047" '
    'CUI="C0003706" TUI="T019" '
    'SDUI="HP:0001166"><Name>Arachnodactyly</Name><SemanticType>Congenital '
    "Abnormality</SemanticType><Definition>Abnormally long and slender fingers "
    '(spider fingers).</Definition></ClinicalFeature><ClinicalFeature uid="2473" '
    'CUI="C0004106" TUI="T047" '
    'SDUI="HP:0000483"><Name>Astigmatism</Name><SemanticType>Disease or '
    "Syndrome</SemanticType><Definition>Astigmatism (from the Greek 'a' meaning "
    "absence and 'stigma' meaning point) is a condition in which the parallel rays "
    "of light entering the eye through the refractive media are not focused on a "
    "single point. Both "
    "cornea.</Definition></ClinicalFeature></ClinicalFeatures><PhenotypicAbnormalities "
    '/><RelatedDisorders /><SNOMEDCT><Name SAUI="2839233010" SCUI="19346006" '
    'SAB="SNOMEDCT_US" TTY="SY">Marfan syndrome</Name><Name SAUI="32612014" '
    'SCUI="19346006" SAB="SNOMEDCT_US" TTY="PT">Marfan\'s '
    'syndrome</Name></SNOMEDCT><AssociatedGenes><Gene gene_id="2200" '
    'chromosome="15" '
    'cytogen_loc="15q21.1">FBN1</Gene></AssociatedGenes><ORDO><HierarchyUrl>http://www.orpha.net/consor/cgi-bin/Disease_Classif.php?lng=EN&amp;data_id=156&amp;PatId=109&amp;search=Disease_Classif_Simple&amp;new=1</HierarchyUrl></ORDO><SemanticTypes><SemanticType '
    'TUI="T047">Disease or Syndrome</SemanticType></SemanticTypes>',
    "modificationdate": "",
    "merged": "",
}

DOC_HBOC = {
    "uid": "382914",
    "conceptid": "C2676676",
    "title": "Breast-ovarian cancer, familial, susceptibility to, 1",
    "definition": {
        "value": "BRCA1- and BRCA2-associated hereditary breast and ovarian cancer "
        "(HBOC) is characterized by an increased risk for female and male "
        "breast cancer, ovarian cancer (including fallopian tube and primary "
        "peritoneal cancers),."
    },
    "semanticid": "T033",
    "semantictype": {"value": "Finding"},
    "suppressed": "",
    "conceptmeta": '<Names><Name SDUI="604370" CODE="604370" SAB="OMIM" TTY="PT" '
    'type="syn">BREAST-OVARIAN CANCER, FAMILIAL, SUSCEPTIBILITY TO, 1</Name><Name '
    'SDUI="604370" CODE="604370" SAB="OMIM" TTY="ACR" '
    'type="syn">BROVCA1</Name><Name SDUI="GTRT000004711" CODE="AN0093493" '
    'SAB="GTR" TTY="PT" type="preferred">Breast-ovarian cancer, familial, '
    'susceptibility to, 1</Name><Name SDUI="GTRT000004711" CODE="AN0195163" '
    'SAB="GTR" TTY="SYN" type="syn">OVARIAN CANCER, SUSCEPTIBILITY TO</Name><Name '
    'SDUI="MONDO:0011450" SCUI="GTRT000004711" CODE="MONDO_0011450" SAB="MONDO" '
    'TTY="PT" type="syn">breast-ovarian cancer, familial, susceptibility to, '
    '1</Name><Name SDUI="MONDO:0011450" SCUI="GTRT000004711" CODE="AN1603331" '
    'SAB="MONDO" TTY="SYN" type="syn">BROVCA1</Name><Name SDUI="NBK1247" '
    'SCUI="GTRT000004711" CODE="NBK1247" SAB="GENEREVIEWS" TTY="PT" '
    'type="syn">BRCA1 Hereditary Breast and Ovarian '
    'Cancer</Name></Names><Definitions><Definition source="GeneReviews">BRCA1- and '
    "BRCA2-associated hereditary breast and ovarian cancer (HBOC) is characterized "
    "by an increased risk for female and male breast cancer, ovarian cancer "
    "(including fallopian tube and primary peritoneal "
    "cancers),.</Definition></Definitions><Chromosome>17</Chromosome><Cytogenetic>17q21.31</Cytogenetic><ModesOfInheritance "
    "/><PharmacologicResponse "
    "/><OMIM><MIM>604370</MIM></OMIM><ClinicalFeatures><ClinicalFeature "
    'uid="146260" CUI="C0678222" TUI="T191" SDUI="HP:0003002"><Name>Breast '
    "carcinoma</Name><SemanticType>Neoplastic "
    "Process</SemanticType><Definition>The presence of a carcinoma of the "
    'breast.</Definition></ClinicalFeature><ClinicalFeature uid="181539" '
    'CUI="C0919267" TUI="T191" SDUI="HP:0100615"><Name>Ovarian '
    "neoplasm</Name><SemanticType>Neoplastic Process</SemanticType><Definition>A "
    "tumor (abnormal growth of tissue) of the "
    "ovary.</Definition></ClinicalFeature></ClinicalFeatures><PhenotypicAbnormalities "
    '/><RelatedDisorders /><SNOMEDCT /><AssociatedGenes><Gene gene_id="672" '
    'chromosome="17" '
    'cytogen_loc="17q21.31">BRCA1</Gene></AssociatedGenes><SemanticTypes><SemanticType '
    'TUI="T033">Finding</SemanticType></SemanticTypes>',
    "modificationdate": "",
    "merged": "",
}

DOC_FATIGUE = {
    "uid": "41971",
    "conceptid": "C0015672",
    "title": "Fatigue",
    "definition": {
        "value": "A subjective feeling of tiredness characterized by a lack of energy "
        "and motivation."
    },
    "semanticid": "T184",
    "semantictype": {"value": "Sign or Symptom"},
    "suppressed": "",
    "conceptmeta": '<Names><Name SDUI="D005221" SCUI="M0008254" CODE="D005221" SAB="MSH" TTY="MH" '
    'type="preferred">Fatigue</Name><Name SDUI="MTHU010062" CODE="MTHU010062" '
    'SAB="OMIM" TTY="PTCS" type="preferred">Fatigue</Name><Name SCUI="84229001" '
    'CODE="84229001" SAB="SNOMEDCT_US" TTY="PT" '
    'type="preferred">Fatigue</Name><Name SCUI="248274002" CODE="248274002" '
    'SAB="SNOMEDCT_US" TTY="PT" type="syn">Lack of energy</Name><Name SCUI="C3036" '
    'CODE="C3036" SAB="NCI" TTY="PT" type="preferred">Fatigue</Name><Name '
    'SCUI="C3036" CODE="C3036" SAB="NCI" TTY="SY" type="syn">Lack of '
    'Energy</Name><Name SDUI="HP:0012378" SCUI="GTRT000030260" CODE="HP:0012378" '
    'SAB="HPO" TTY="PT" type="preferred">Fatigue</Name><Name SDUI="GTRT000030260" '
    'CODE="AN0481148" SAB="GTR" TTY="PT" type="preferred">Fatigue</Name><Name '
    'SDUI="HP:0012378" SCUI="GTRT000030260" CODE="HP:0012378" SAB="HPO" TTY="SYN" '
    'type="preferred">Fatigue</Name></Names><Definitions><Definition '
    'source="HPO">A subjective feeling of tiredness characterized by a lack of '
    "energy and motivation.</Definition></Definitions><ModesOfInheritance "
    "/><PharmacologicResponse /><OMIM /><ClinicalFeatures "
    "/><PhenotypicAbnormalities /><RelatedDisorders /><SNOMEDCT><Name "
    'SAUI="139690015" SCUI="84229001" SAB="SNOMEDCT_US" '
    'TTY="PT">Fatigue</Name><Name SAUI="2475941011" SCUI="248274002" '
    'SAB="SNOMEDCT_US" TTY="SY">Lacking in '
    "energy</Name></SNOMEDCT><AssociatedGenes /><SemanticTypes><SemanticType "
    'TUI="T184">Sign or Symptom</SemanticType></SemanticTypes>',
    "modificationdate": "",
    "merged": "",
}

DOC_WARFARIN = {
    "uid": "148193",
    "conceptid": "C0750384",
    "title": "Warfarin response",
    "definition": {
        "value": "Warfarin is an oral anti-coagulant used world-wide to treat and "
        "prevent thrombotic disorders.  While it is highly effective, it has "
        "a very narrow therapeutic index making it difficult to dose "
        "correctly.  Genetic variant."
    },
    "semanticid": "T033",
    "semantictype": {"value": "Finding"},
    "suppressed": "",
    "conceptmeta": '<Names><Name SDUI="122700" CODE="122700" SAB="OMIM" TTY="PT" '
    'type="syn">COUMARIN RESISTANCE</Name><Name SDUI="C563039" SCUI="M0563339" '
    'CODE="C563039" SAB="MSH" TTY="CE" type="syn">Coumarin, Poor Metabolism '
    'Of</Name><Name SDUI="C563039" SCUI="M0563339" CODE="C563039" SAB="MSH" '
    'TTY="NM" type="syn">Coumarin Resistance</Name><Name SDUI="122700" '
    'CODE="122700" SAB="OMIM" TTY="ETAL" type="syn">COUMARIN, POOR METABOLISM '
    'OF</Name><Name SDUI="GTRT000016477" CODE="AN0202668" SAB="GTR" TTY="PT" '
    'type="preferred">Warfarin response</Name><Name SDUI="GTRT000016477" '
    'CODE="AN0266715" SAB="GTR" TTY="SYN" type="syn">COUMARIN '
    'SENSITIVITY</Name><Name SDUI="MONDO:0007390" SCUI="GTRT000016477" '
    'CODE="MONDO_0007390" SAB="MONDO" TTY="PT" type="syn">coumarin '
    'resistance</Name><Name SDUI="MONDO:0007390" SCUI="GTRT000016477" '
    'CODE="AN1596464" SAB="MONDO" TTY="SYN" type="syn">coumarin '
    'resistance</Name></Names><Definitions><Definition source="ClinPGx">Warfarin '
    "is an oral anti-coagulant used world-wide to treat and prevent thrombotic "
    "disorders.  While it is highly effective, it has a very narrow therapeutic "
    "index making it difficult to dose correctly.  Genetic "
    "variant.</Definition></Definitions><Chromosome>10</Chromosome><Cytogenetic>10q23.33</Cytogenetic><ModesOfInheritance "
    '/><PharmacologicResponse><Drug uid="22695" CUI="C0043031" '
    'TUI="T121"><Name>Warfarin</Name><SemanticType>Pharmacologic '
    'Substance</SemanticType><Definition source="NCI">A synthetic anticoagulant. '
    "Warfarin inhibits the regeneration of vitamin K1 epoxide and so the synthesis "
    "of vitamin K dependent clotting factors, which include Factors II, VII, IX "
    "and X, and the anticoagulant proteins "
    "C.</Definition></Drug></PharmacologicResponse><OMIM><MIM>122700</MIM></OMIM><ClinicalFeatures><ClinicalFeature "
    'uid="163092" CUI="C0850715" TUI="T033" SDUI="HP:0001871"><Name>Abnormality of '
    "blood and blood-forming "
    "tissues</Name><SemanticType>Finding</SemanticType><Definition>An abnormality "
    "of the hematopoietic "
    "system.</Definition></ClinicalFeature></ClinicalFeatures><PhenotypicAbnormalities "
    '/><RelatedDisorders /><SNOMEDCT /><AssociatedGenes><Gene gene_id="1559" '
    'chromosome="10" cytogen_loc="10q23.33">CYP2C9</Gene><Gene gene_id="1548" '
    'chromosome="19" cytogen_loc="19q13.2">CYP2A6</Gene><Gene gene_id="79001" '
    'chromosome="16" '
    'cytogen_loc="16p11.2">VKORC1</Gene></AssociatedGenes><SemanticTypes><SemanticType '
    'TUI="T033">Finding</SemanticType></SemanticTypes>',
    "modificationdate": "",
    "merged": "",
}

DOC_ERROR = {"uid": "8393999999", "error": "cannot get document summary"}
