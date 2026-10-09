"""Trimmed real ISRCTN API responses (captured 2026-10-09) for
tests/unit/test_isrctn_adapter.py.

``https://www.isrctn.com/api/query/format/default?q=...&limit=...``. Contact persons (names,
e-mail, phone) were removed, long texts and trial centre lists shortened.
"""

SEARCH_MECFS = """\
<allTrials xmlns="http://www.67bricks.com/isrctn" totalCount="11">
  <fullTrial>
    <trial lastUpdated="2026-05-26T15:09:37.845816062Z" version="12" isPublished="true" publicIdentifierType="isrctn" publicIdentifierCanonical="ISRCTN15375673" publicIdentifierDateAssigned="2026-05-26T15:09:37.968497Z">
      <isrctn dateAssigned="2026-05-26T15:09:37.968497Z">15375673</isrctn>
      <trialDescription thirdPartyFilesAcknowledgement="true">
        <acknowledgment>true</acknowledgment>
        <title>Long Covid and myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) study</title>
        <scientificTitle>Health Effects fRom Infection sequelae: Tailoring services and Advancing GuidancE (HERITAGE) in Long Covid and myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)</scientificTitle>
        <acronym>HERITAGE</acronym>
        <studyHypothesis>HERITAGE aims to inform high-quality and cost-effective services for LC and ME/CFS. Below, we set out the research questions (RQ), objectives and key milestones for each of the three work packages (WPs).   

WP1 (RQ1): What is the ...</studyHypothesis>
        <plainEnglishSummary />
        <primaryOutcomes>
          <outcomeMeasure id="67a6cb11-0512-4135-8e16-3c668652fa83">
            <variable>The development of a national service framework (NSF) for Long COVID and ME/CFS.</variable>
            <method>The primary outcome measures that will be used in different work packages are WP1: DPROMs including; Yorkshire Rehabilitation Scale (YRS), DSQ-SF and FUNCAP27 to capture symptom burden as well as HERITAGE general health questionnaire to ...</method>
            <timepoints>For WP1&amp;2: Baseline, follow-ups at 3, 6, 9 and 12 months. For WP3: Participants invited for interviews will take part in one interview only, lasting up to 60 minutes. Interviews may be split into shorter sessions if preferred. The QIC will ...</timepoints>
          </outcomeMeasure>
        </primaryOutcomes>
        <primaryOutcome />
        <secondaryOutcomes>
          <outcomeMeasure id="56c3d1e1-8587-43b0-886b-e67669c60cfa">
            <variable>Symptom burden and functional impact in participants with Long Covid and/or ME/CFS</variable>
            <method>condition-specific patient-reported outcome measures, including the Yorkshire Rehabilitation Scale (YRS), DePaul Symptom Questionnaire – Short Form (DSQ SF), and FUNCAP27,</method>
            <timepoints>baseline and  3, 6, 9 and 12 months</timepoints>
          </outcomeMeasure>
          <outcomeMeasure id="ad542982-20d5-4d03-af1e-c4f8aad06466">
            <variable>Health-related quality of life</variable>
            <method>the EQ 5D 5L questionnaire to calculate quality adjusted life years (QALYs)</method>
            <timepoints>baseline and at 3, 6, 9 and 12 months</timepoints>
          </outcomeMeasure>
        </secondaryOutcomes>
        <secondaryOutcome>1. Diagnostic overlap between Long Covid and ME/CFS is assessed using participant-reported diagnostic information collected via the HERITAGE general health questionnaire at baseline and at 3, 6, 9 and 12 months
2. Healthcare utilisation ...</secondaryOutcome>
        <ethicsApprovalRequired>Ethics approval required</ethicsApprovalRequired>
      </trialDescription>
      <externalRefs>
        <doi>10.1186/ISRCTN15375673</doi>
        <eudraCTNumber />
        <irasNumber />
        <clinicalTrialsGovNumber />
        <protocolSerialNumber />
        <secondaryNumbers />
      </externalRefs>
      <trialDesign>
        <studyDesign />
        <primaryStudyDesign>Observational</primaryStudyDesign>
        <secondaryStudyDesign>Cohort study</secondaryStudyDesign>
        <trialTypes />
        <overallEndDate>2028-12-31T00:00:00.000Z</overallEndDate>
      </trialDesign>
      <participants>
        <recruitmentCountries>
          <country>United Kingdom</country>
          <country>England</country>
        </recruitmentCountries>
        <trialCentres>
          <trialCentre id="5740a9b7-e549-477b-8461-643510cbf8c3">
            <name>University Hospitals of Leicester NHS Trust</name>
            <city>Leicester</city>
            <state />
            <country>England</country>
          </trialCentre>
          <trialCentre id="29ae8703-7c38-4dcf-99f6-3b2a923162ef">
            <name>Hertfordshire Community NHS Trust</name>
            <city>Welwyn Garden City</city>
            <state />
            <country>England</country>
          </trialCentre>
        </trialCentres>
        <participantTypes />
        <healthyVolunteersAllowed>true</healthyVolunteersAllowed>
        <inclusion>Inclusion criteria for WP1 and WP2:
1. Aged 18 years and over
2. All genders
3. Ability to provide informed consent
4. Have had symptoms of persistent LC or ME/CFS for &gt;2 years

Clinic cohort:
1. Individuals who at study baseline, have ...</inclusion>
        <ageRange>Mixed</ageRange>
        <lowerAgeLimit unit="years" value="18.0">18 Years</lowerAgeLimit>
        <upperAgeLimit unit="years" value="100.0">100 Years</upperAgeLimit>
        <gender>All</gender>
        <targetEnrolment>3060</targetEnrolment>
        <totalFinalEnrolment>0</totalFinalEnrolment>
        <exclusion>Exclusion criteria for WP1 and WP2:

Clinic cohort:
1. Individuals who, during follow‑up, receive an alternative diagnosis or enter non‑HERITAGE specialist services will be withdrawn from follow‑up for WP1/WP2
2. Individuals will be ...</exclusion>
        <recruitmentStart>2026-05-01T00:00:00.000Z</recruitmentStart>
        <recruitmentEnd>2028-12-31T00:00:00.000Z</recruitmentEnd>
        <recruitmentStartStatusOverride />
        <recruitmentStatusOverride />
      </participants>
      <conditions>
        <condition>
          <description>Long Covid and myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)</description>
          <diseaseClass1>Other</diseaseClass1>
          <diseaseClass2 />
        </condition>
      </conditions>
      <interventions>
        <intervention>
          <description>The HERITAGE study will use a mixed‑methods design, combining quantitative and qualitative data from individuals with Long Covid (LC) and myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) recruited from four locality‑based ...</description>
          <interventionType>Other</interventionType>
          <phase />
          <drugNames />
        </intervention>
      </interventions>
      <results>
        <ipdSharingStatement />
        <dataPolicies>
          <dataPolicy>Not expected to be made available</dataPolicy>
        </dataPolicies>
        <publicationDetails />
        <publicationStage />
        <basicReport />
        <plainEnglishReport />
      </results>
      <parties>
        <funderId>b047404b-6c1f-43ee-b2d8-0775652ee711</funderId>
        <sponsorId>29572c25-4ddb-4ff1-851d-a3d7479dd6d1</sponsorId>
      </parties>
    </trial>
    <sponsor id="29572c25-4ddb-4ff1-851d-a3d7479dd6d1">
      <organisation>University of Leeds</organisation>
      <sponsorType />
      <rorId>https://ror.org/024mrxd33</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <funder id="b047404b-6c1f-43ee-b2d8-0775652ee711">
      <name>National Institute for Health and Care Research</name>
      <fundRef>http://dx.doi.org/10.13039/501100000272</fundRef>
    </funder>
  </fullTrial>
  <fullTrial>
    <trial lastUpdated="2026-04-10T15:04:33.082955579Z" version="16" isPublished="true" publicIdentifierType="isrctn" publicIdentifierCanonical="ISRCTN16025168" publicIdentifierDateAssigned="2026-03-27T09:59:26.561781Z">
      <isrctn dateAssigned="2026-03-27T09:59:26.561781Z">16025168</isrctn>
      <trialDescription thirdPartyFilesAcknowledgement="false">
        <acknowledgment>true</acknowledgment>
        <title>Multicentre study on coaching and point-of-care technologies for patients with myalgic encephalomyelitis/chronic fatigue syndrome</title>
        <scientificTitle>Multicentre study of the effectiveness of multimodal coaching interventions and the feasibility of point-of-care test device for improving the quality of life, functional capacity, and self-management in patients with myalgic encephalomyelitis/chronic fatigue syndrome</scientificTitle>
        <acronym />
        <studyHypothesis>To evaluate the effectiveness and feasibility of multi-modal coaching interventions and point-of-care test (PoCT) device use in improving the quality of life, functional capacity, and self-management in patients with ME/CFS.</studyHypothesis>
        <plainEnglishSummary>Plain English summary of protocol not provided at time of registration</plainEnglishSummary>
        <primaryOutcomes>
          <outcomeMeasure id="8d6e1b77-9c68-4abb-9e31-99f04b647818">
            <variable>Health-related quality of life (HRQoL)</variable>
            <method>SF-36, ED-5D-5L and EQ-VAS</method>
            <timepoints>baseline and post-intervention (12 weeks), with a follow-up at 3-6 months post-trial</timepoints>
          </outcomeMeasure>
        </primaryOutcomes>
        <primaryOutcome />
        <secondaryOutcomes />
        <secondaryOutcome />
        <ethicsApprovalRequired>Ethics approval required</ethicsApprovalRequired>
      </trialDescription>
      <externalRefs>
        <doi>10.1186/ISRCTN16025168</doi>
        <eudraCTNumber />
        <irasNumber />
        <clinicalTrialsGovNumber />
        <protocolSerialNumber>GA N° 101095654, THCS2025-404</protocolSerialNumber>
        <secondaryNumbers>
          <secondaryNumber id="785d3990-8ee7-4415-a8fe-5d51f8b441f8" numberType="EU Horizon Europe Research and Innovation Programme">GA N° 101095654</secondaryNumber>
          <secondaryNumber id="604ef281-5232-495e-b7f4-b3a4360d0082" numberType="Latvian Council of Science (Latvijas Zinātnes Padome)">THCS2025-404</secondaryNumber>
        </secondaryNumbers>
      </externalRefs>
      <trialDesign>
        <studyDesign />
        <primaryStudyDesign>Interventional</primaryStudyDesign>
        <interventionalTrialDesign>
          <allocation>Randomized controlled trial</allocation>
          <masking>Open (masking not used)</masking>
          <control>Active</control>
          <assignment>Parallel</assignment>
          <purposes>
            <purpose>Device feasibility</purpose>
            <purpose>Health services research</purpose>
            <purpose>Supportive care</purpose>
            <purpose>Treatment</purpose>
          </purposes>
        </interventionalTrialDesign>
        <secondaryStudyDesign>Not applicable</secondaryStudyDesign>
        <trialTypes />
        <overallEndDate>2028-08-31T00:00:00.000Z</overallEndDate>
      </trialDesign>
      <participants>
        <recruitmentCountries>
          <country>Canada</country>
          <country>France</country>
          <country>Italy</country>
          <country>Latvia</country>
        </recruitmentCountries>
        <trialCentres />
        <participantTypes />
        <healthyVolunteersAllowed>false</healthyVolunteersAllowed>
        <inclusion>1.	Age 18-75 years
2.	Diagnosis of ME/CFS according to International Consensus Criteria (ICC), or Canadian Consensus Criteria (CCC), or Institute of Medicine/National Academy of Medicine (IOM/NAM) criteria, or National Institute for Health ...</inclusion>
        <ageRange>Mixed</ageRange>
        <lowerAgeLimit unit="years" value="18.0">18 Years</lowerAgeLimit>
        <upperAgeLimit unit="years" value="75.0">75 Years</upperAgeLimit>
        <gender>All</gender>
        <targetEnrolment>210</targetEnrolment>
        <totalFinalEnrolment>0</totalFinalEnrolment>
        <exclusion>1.	Primary psychiatric disorders (e.g., schizophrenia, bipolar disorder)
2.	Severe comorbidities that interfere with participation
3.	Current participation in another interventional trial</exclusion>
        <recruitmentStart>2026-09-01T00:00:00.000Z</recruitmentStart>
        <recruitmentEnd>2028-02-29T00:00:00.000Z</recruitmentEnd>
        <recruitmentStartStatusOverride />
        <recruitmentStatusOverride />
      </participants>
      <conditions>
        <condition>
          <description>Improving the quality of life of patients with myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)</description>
          <diseaseClass1>Nervous System Diseases</diseaseClass1>
          <diseaseClass2 />
        </condition>
      </conditions>
      <interventions>
        <intervention>
          <description>Study Methodology and Interventions
This is a multicentre, mixed-design interventional study consisting of three study arms evaluating multimodal coaching interventions and the feasibility of a point-of-care testing (PoCT) device in ...</description>
          <interventionType>Mixed</interventionType>
          <phase />
          <drugNames />
        </intervention>
      </interventions>
      <results>
        <ipdSharingStatement />
        <dataPolicies>
          <dataPolicy>Not expected to be made available</dataPolicy>
        </dataPolicies>
        <publicationDetails />
        <publicationStage />
        <basicReport />
        <plainEnglishReport />
      </results>
      <parties>
        <funderId>ac97ca6e-5f99-4b1b-8f1f-bc5cf88e95f0</funderId>
        <funderId>300d71c6-5129-4388-92fa-fd2e6e9bbfc8</funderId>
        <funderId>7cece9a6-9047-414a-8b93-f31c4180f772</funderId>
        <funderId>5147d3fa-4759-444b-9603-158949015223</funderId>
        <funderId>6eef2f28-b88f-4c98-acfd-bc42eedfe067</funderId>
        <sponsorId>1302403a-876a-4569-a99a-2312e52a8d7d</sponsorId>
        <sponsorId>f013fca2-4693-4f8f-ad96-c6eca608ac3b</sponsorId>
        <sponsorId>591fba47-ffcb-492d-b2a9-def74216c7fd</sponsorId>
        <sponsorId>276fcdf3-6b58-498a-9b6b-1f90c5cdaefa</sponsorId>
      </parties>
    </trial>
    <sponsor id="1302403a-876a-4569-a99a-2312e52a8d7d">
      <organisation>Université Paris-Est Créteil</organisation>
      <sponsorType />
      <rorId>https://ror.org/05ggc9x40</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <sponsor id="f013fca2-4693-4f8f-ad96-c6eca608ac3b">
      <organisation>University of British Columbia</organisation>
      <sponsorType />
      <rorId>https://ror.org/03rmrcq20</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <sponsor id="591fba47-ffcb-492d-b2a9-def74216c7fd">
      <organisation>Institute for Microelectronics and Microsystems</organisation>
      <sponsorType />
      <rorId>https://ror.org/05vk2g845</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <sponsor id="276fcdf3-6b58-498a-9b6b-1f90c5cdaefa">
      <organisation>Riga Stradiņš University</organisation>
      <sponsorType />
      <rorId>https://ror.org/03nadks56</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <funder id="ac97ca6e-5f99-4b1b-8f1f-bc5cf88e95f0">
      <name>Agence Nationale de la Recherche</name>
      <fundRef>http://dx.doi.org/10.13039/501100001665</fundRef>
    </funder>
    <funder id="300d71c6-5129-4388-92fa-fd2e6e9bbfc8">
      <name>Canadian Institutes of Health Research</name>
      <fundRef>http://dx.doi.org/10.13039/501100000024</fundRef>
    </funder>
    <funder id="7cece9a6-9047-414a-8b93-f31c4180f772">
      <name>Ministero dell'Università e della Ricerca</name>
      <fundRef>http://dx.doi.org/10.13039/501100021856</fundRef>
    </funder>
    <funder id="5147d3fa-4759-444b-9603-158949015223">
      <name>Latvijas Zinātnes Padome</name>
      <fundRef>http://dx.doi.org/10.13039/501100005375</fundRef>
    </funder>
    <funder id="6eef2f28-b88f-4c98-acfd-bc42eedfe067">
      <name>HORIZON EUROPE Reforming and enhancing the European Research and Innovation system</name>
      <fundRef>http://dx.doi.org/10.13039/100018707</fundRef>
    </funder>
  </fullTrial>
  <fullTrial>
    <trial lastUpdated="2025-11-18T13:48:59.175253667Z" version="22" isPublished="true" publicIdentifierType="isrctn" publicIdentifierCanonical="ISRCTN16132141" publicIdentifierDateAssigned="2025-11-21T17:49:27.666966Z">
      <isrctn dateAssigned="2025-11-21T17:49:27.666966Z">16132141</isrctn>
      <trialDescription thirdPartyFilesAcknowledgement="false">
        <acknowledgment>true</acknowledgment>
        <title>Brain response to light stimulation in people with myalgic encephalomyelitis/chronic fatigue syndrome</title>
        <scientificTitle>Lactate response to light stimulation in people with myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)</scientificTitle>
        <acronym>OxLac</acronym>
        <studyHypothesis>1. Apply fMRS to explore differences in lactete concentrations between ME/CFS patients and healthy controls during activation with flashing lights; we expect the difference during activation will be more pronounced than at rest;
2. ...</studyHypothesis>
        <plainEnglishSummary />
        <primaryOutcomes>
          <outcomeMeasure id="d4fcd934-90ef-4c22-9686-df203934db88">
            <variable>Lactate concentration in the occipital cortex</variable>
            <method>functional magnetic resonance spectroscopy (fMRS)</method>
            <timepoints>baseline and after stimulation with a flashing checkerboard</timepoints>
          </outcomeMeasure>
        </primaryOutcomes>
        <primaryOutcome>Change in lactate concentration in the occipital cortex from basline to stimulation with flashing checkeboard using functional MRS - ME/CFS patients compared to healthy controls.</primaryOutcome>
        <secondaryOutcomes>
          <outcomeMeasure id="b7924ab4-49cf-4d87-9726-bde21e5b92b6">
            <variable>Resting lactate concentration in the anterior cingulate cortex</variable>
            <method>magnetic resonance spectroscopy (MRS)</method>
            <timepoints>baseline</timepoints>
          </outcomeMeasure>
        </secondaryOutcomes>
        <secondaryOutcome>Resting lactate concentration in the anterior cingulate cortex measured with MRS - ME/CFS patients compared to healthy controls.</secondaryOutcome>
        <ethicsApprovalRequired>Ethics approval required</ethicsApprovalRequired>
      </trialDescription>
      <externalRefs>
        <doi>10.1186/ISRCTN16132141</doi>
        <eudraCTNumber />
        <irasNumber />
        <clinicalTrialsGovNumber />
        <protocolSerialNumber />
        <secondaryNumbers />
      </externalRefs>
      <trialDesign>
        <studyDesign>Single-centre observational cross-sectional cohort study</studyDesign>
        <primaryStudyDesign>Observational</primaryStudyDesign>
        <secondaryStudyDesign>Case-control study</secondaryStudyDesign>
        <trialTypes>
          <trialType>Other</trialType>
        </trialTypes>
        <overallEndDate>2025-12-31T00:00:00.000Z</overallEndDate>
      </trialDesign>
      <participants>
        <recruitmentCountries>
          <country>United Kingdom</country>
          <country>England</country>
        </recruitmentCountries>
        <trialCentres>
          <trialCentre id="db26d851-a004-474e-ac21-d9467ed93471">
            <name>University of Oxford</name>
            <city>Oxford</city>
            <state />
            <country>England</country>
          </trialCentre>
        </trialCentres>
        <participantTypes>
          <participantType>Healthy volunteer</participantType>
          <participantType>Patient</participantType>
        </participantTypes>
        <healthyVolunteersAllowed>true</healthyVolunteersAllowed>
        <inclusion>1.	Males or females aged 18 years or over
2.	Willing and able to give informed consent to participate in the study
3.	Diagnosis of DSM-V major depression based on the affective disorder sections of the SCID-5. N.b. comorbid anxiety ...</inclusion>
        <ageRange>Mixed</ageRange>
        <lowerAgeLimit unit="years" value="18.0">18 Years</lowerAgeLimit>
        <upperAgeLimit unit="years" value="99.0">99 Years</upperAgeLimit>
        <gender>All</gender>
        <targetEnrolment>50</targetEnrolment>
        <totalFinalEnrolment>49</totalFinalEnrolment>
        <exclusion>1.	Clinical diagnosis of current or previous psychosis (including psychotic depression), bipolar disorder or Parkinson’s Disease
2.	Currently taking an antipsychotic medication
3.	Clinically significant current or previous impulse control ...</exclusion>
        <recruitmentStart>2024-09-23T00:00:00.000Z</recruitmentStart>
        <recruitmentEnd>2025-10-27T00:00:00.000Z</recruitmentEnd>
        <recruitmentStartStatusOverride />
        <recruitmentStatusOverride />
      </participants>
      <conditions>
        <condition>
          <description>Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)</description>
          <diseaseClass1>Nervous System Diseases</diseaseClass1>
          <diseaseClass2 />
        </condition>
      </conditions>
      <interventions>
        <intervention>
          <description>Participants undergo an MRI scan, which allows the measurement of lactate. During this scan, they undergo a simple task, which includes looking at the flickering checkerboard for 7.5 min; this is preceded and followed by 11 min of rest ...</description>
          <interventionType>Mixed</interventionType>
          <phase />
          <drugNames />
        </intervention>
      </interventions>
      <results>
        <ipdSharingStatement />
        <dataPolicies>
          <dataPolicy>Available on request</dataPolicy>
        </dataPolicies>
        <publicationDetails />
        <publicationStage />
        <basicReport />
        <plainEnglishReport />
      </results>
      <parties>
        <funderId>a6b2d17e-c267-410a-b6f6-2c6b0991db77</funderId>
        <sponsorId>e67df366-35b2-488e-a00d-17143d4ac807</sponsorId>
      </parties>
    </trial>
    <sponsor id="e67df366-35b2-488e-a00d-17143d4ac807">
      <organisation>University of Oxford</organisation>
      <sponsorType>Research organisation</sponsorType>
      <rorId>https://ror.org/052gg0110</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <funder id="a6b2d17e-c267-410a-b6f6-2c6b0991db77">
      <name>Medical Research Council</name>
      <fundRef>http://dx.doi.org/10.13039/501100000265</fundRef>
    </funder>
  </fullTrial>
</allTrials>
"""

RECORD_PACE = """\
<allTrials xmlns="http://www.67bricks.com/isrctn" totalCount="1">
  <fullTrial>
    <trial lastUpdated="2015-11-03T11:48:02.697Z" version="48" isPublished="true" publicIdentifierType="isrctn" publicIdentifierCanonical="ISRCTN54285094" publicIdentifierDateAssigned="2003-05-22T00:00:00.000Z">
      <isrctn dateAssigned="2003-05-22T00:00:00.000Z">54285094</isrctn>
      <trialDescription thirdPartyFilesAcknowledgement="false">
        <acknowledgment>true</acknowledgment>
        <title>A randomised controlled trial of adaptive pacing, cognitive behaviour therapy, and graded exercise, as supplements to standardised specialist medical care versus standardised specialist medical care alone for patients with the chronic fatigue syndrome/myalgic encephalomyelitis or encephalopathy</title>
        <scientificTitle>A randomised controlled trial of adaptive pacing, cognitive behaviour therapy, and graded exercise, as supplements to standardised specialist medical care versus standardised specialist medical care alone for patients with the chronic fatigue syndrome/myalgic encephalomyelitis or encephalopathy</scientificTitle>
        <acronym>PACE: Pacing, Activity, and Cognitive behaviour therapy: a randomised Evaluation</acronym>
        <studyHypothesis>1. Are cognitive behaviour theraphy (CBT) and/or graded exercise therapy (GET) more effective than pacing in reducing both fatigue and disability?
2. Is pacing more effective than usual medical care?
3. Are there differential predictors of ...</studyHypothesis>
        <plainEnglishSummary>Not provided at time of registration</plainEnglishSummary>
        <primaryOutcomes />
        <primaryOutcome>1. Is APT and SSMC more effective than SSMC alone in reducing (i) fatigue, (ii) disability, or (iii) both?
2. Is CBT and SSMC more effective than APT and SSMC in reducing (i) fatigue, (ii) disability or (iii) both?
3. Is GET and SSMC more ...</primaryOutcome>
        <secondaryOutcomes />
        <secondaryOutcome>The secondary analyses are exploratory but we will be guided by previously published findings.
1. Do different treatments have differential effects on outcomes (i.e. fatigue versus physical disability)?
2. What baseline factors (other than ...</secondaryOutcome>
        <ethicsApprovalRequired>Old ethics approval format</ethicsApprovalRequired>
        <ethicsApproval>UK West Midlands Multicentre Research Ethics Committee, 31/03/2003</ethicsApproval>
      </trialDescription>
      <externalRefs>
        <doi>10.1186/ISRCTN54285094</doi>
        <eudraCTNumber />
        <irasNumber />
        <clinicalTrialsGovNumber />
        <protocolSerialNumber>G0200434</protocolSerialNumber>
        <secondaryNumbers>
          <secondaryNumber id="a6270677-7d93-41ea-b079-b0826a1f652b" numberType="Protocol serial number">G0200434</secondaryNumber>
        </secondaryNumbers>
      </externalRefs>
      <trialDesign>
        <studyDesign>Multicentre randomised controlled trial</studyDesign>
        <primaryStudyDesign>Interventional</primaryStudyDesign>
        <secondaryStudyDesign>Randomised controlled trial</secondaryStudyDesign>
        <trialTypes>
          <trialType>Treatment</trialType>
        </trialTypes>
        <overallEndDate>2011-07-01T00:00:00.000Z</overallEndDate>
      </trialDesign>
      <participants>
        <recruitmentCountries>
          <country>United Kingdom</country>
          <country>England</country>
        </recruitmentCountries>
        <trialCentres>
          <trialCentre id="d95d9bc3-ab00-4521-bc40-5995a62697c6">
            <name>St Bartholomew's Hospital</name>
            <city>London</city>
            <state />
            <country>United Kingdom</country>
          </trialCentre>
        </trialCentres>
        <participantTypes>
          <participantType>Patient</participantType>
        </participantTypes>
        <inclusion>Consent:
1. Both participant and clinician agree that randomisation is acceptable
2. The participant has given written informed consent

Eligibility:
3. The participant meets operationalised Oxford research diagnostic criteria for CFS
4. ...</inclusion>
        <ageRange>Adult</ageRange>
        <lowerAgeLimit unit="years" value="18.0">18 Years</lowerAgeLimit>
        <gender>All</gender>
        <targetEnrolment>600</targetEnrolment>
        <totalFinalEnrolment />
        <exclusion>1. All potential participants will be screened for medical exclusions, by history and physical examination. Appropriate investigations will be undertaken by either the referring doctor or the centre doctors (checked by the RN). Patients ...</exclusion>
        <recruitmentStart>2004-06-14T00:00:00.000Z</recruitmentStart>
        <recruitmentEnd>2008-11-28T00:00:00.000Z</recruitmentEnd>
        <recruitmentStartStatusOverride />
        <recruitmentStatusOverride />
      </participants>
      <conditions>
        <condition>
          <description>Symptoms and general pathology</description>
          <diseaseClass1>Mental and Behavioural Disorders</diseaseClass1>
          <diseaseClass2>Chronic fatigue syndrome (CFS)</diseaseClass2>
        </condition>
      </conditions>
      <interventions>
        <intervention>
          <description>PACE is a multicentre randomised controlled trial. The group assignment is parallel group.
1. Standardised Specialist Medical Care alone (SSMC) - manual guided advice from a secondary care clinic specialist in chronic fatigue
2. ...</description>
          <interventionType>Other</interventionType>
          <phase>Not Applicable</phase>
          <drugNames />
        </intervention>
      </interventions>
      <results>
        <ipdSharingStatement />
        <dataPolicies>
          <dataPolicy>Not provided at time of registration</dataPolicy>
        </dataPolicies>
        <publicationDetails>2011 Results article in http://www.ncbi.nlm.nih.gov/pubmed/21334061 results
2013 Results article in http://www.ncbi.nlm.nih.gov/pubmed/23363640 results
2014 Results article in http://www.ncbi.nlm.nih.gov/pubmed/23967878 results
2015 ...</publicationDetails>
        <publicationStage>Results</publicationStage>
        <basicReport />
        <plainEnglishReport />
      </results>
      <parties>
        <funderId>fd7020a6-5fbc-41c1-9f27-01f929545953</funderId>
        <funderId>c6d469ee-f890-4d95-99d4-258d82b374eb</funderId>
        <funderId>1d8a3766-3fa4-4fbd-bec7-a71cd71e656e</funderId>
        <funderId>0c3a405c-202b-44d2-9851-a73891fea0bc</funderId>
        <sponsorId>5fad628e-7e17-4452-8821-24c35d6f1bbc</sponsorId>
      </parties>
    </trial>
    <sponsor id="5fad628e-7e17-4452-8821-24c35d6f1bbc">
      <organisation>Queen Mary University of London (UK)</organisation>
      <sponsorType>University/education</sponsorType>
      <rorId>https://ror.org/026zzn846</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <funder id="fd7020a6-5fbc-41c1-9f27-01f929545953">
      <name>Medical Research Council (MRC) (UK)</name>
      <fundRef>http://dx.doi.org/10.13039/501100000265</fundRef>
    </funder>
    <funder id="c6d469ee-f890-4d95-99d4-258d82b374eb">
      <name>The Scottish Chief Scientist's Office (UK)</name>
    </funder>
    <funder id="1d8a3766-3fa4-4fbd-bec7-a71cd71e656e">
      <name>Department of Health in England and Wales (UK)</name>
    </funder>
    <funder id="0c3a405c-202b-44d2-9851-a73891fea0bc">
      <name>Department for Work and Pensions (UK)</name>
    </funder>
  </fullTrial>
</allTrials>
"""

RECORD_CPMS_NCT = """\
<allTrials xmlns="http://www.67bricks.com/isrctn" totalCount="1">
  <fullTrial>
    <trial lastUpdated="2026-09-30T14:08:37.63458888Z" version="23" isPublished="true" publicIdentifierType="isrctn" publicIdentifierCanonical="ISRCTN62918594" publicIdentifierDateAssigned="2026-06-25T15:29:43.155978Z">
      <isrctn dateAssigned="2026-06-25T15:29:43.155978Z">62918594</isrctn>
      <trialDescription thirdPartyFilesAcknowledgement="false">
        <acknowledgment>true</acknowledgment>
        <title>A Phase I/IIa trial of HMBD-001 in advanced HER3-positive solid tumours</title>
        <scientificTitle>A Cancer Research UK Phase I/IIa open-label, dose escalation and expansion trial of HMBD-001 (an anti-HER3 monoclonal antibody) given intravenously as a single agent and in combination in patients with advanced HER3-positive solid tumours</scientificTitle>
        <acronym />
        <studyHypothesis>Primary Objectives:
1.	To propose a recommended dose and schedule for Phase II evaluation (RP2D) of HMBD-001 as a single agent
2.	To establish the maximum tolerated dose or maximum administered dose of HMBD 001 in patients with advanced ...</studyHypothesis>
        <plainEnglishSummary />
        <primaryOutcomes />
        <primaryOutcome>1.	Number of patients who experienced Dose Limiting Toxicities (DLTs) (Part A)
DLTs graded for severity using the National Cancer Institute (NCI) Common Terminology Criteria for Adverse Events (CTCAE) version (v) 5.0, measured by count of ...</primaryOutcome>
        <secondaryOutcomes />
        <secondaryOutcome>1.	ORR within six cycles of HMBD-001 (Part A) 
Proportion of patients who achieve a best response of CR or PR, based on RECIST v1.1 and/or PCWG3 Criteria as applicable, within six cycles of HMBD-001 monotherapy.
[Time Frame: From baseline ...</secondaryOutcome>
        <ethicsApprovalRequired>Ethics approval required</ethicsApprovalRequired>
      </trialDescription>
      <externalRefs>
        <doi>10.1186/ISRCTN62918594</doi>
        <eudraCTNumber>2020-005891-36</eudraCTNumber>
        <irasNumber>298897</irasNumber>
        <clinicalTrialsGovNumber>NCT05057013</clinicalTrialsGovNumber>
        <protocolSerialNumber>CPMS: 49816, CRUKD/22/002</protocolSerialNumber>
        <secondaryNumbers>
          <secondaryNumber id="8562b532-a363-4436-a84d-10354259b06f" numberType="nct" canonicalSecondaryNumber="NCT05057013">NCT05057013</secondaryNumber>
          <secondaryNumber id="17fa6467-c004-4f5c-8e3e-d5a84682467a" numberType="ctis" canonicalSecondaryNumber="CTIS2020-005891-36-00">2020-005891-36</secondaryNumber>
          <secondaryNumber id="36d8f496-d5a0-45fc-bb35-7567a58b825d" numberType="iras" canonicalSecondaryNumber="IRAS298897">298897</secondaryNumber>
          <secondaryNumber id="ab8b22a7-fc99-4555-aed3-770b3c4a3b35" numberType="cpms" canonicalSecondaryNumber="CPMS49816">49816</secondaryNumber>
          <secondaryNumber id="2838db7c-b732-42aa-be0f-b497dea1a79e" numberType="Protocol serial number">CRUKD/22/002</secondaryNumber>
        </secondaryNumbers>
      </externalRefs>
      <trialDesign>
        <studyDesign />
        <primaryStudyDesign>Interventional</primaryStudyDesign>
        <interventionalTrialDesign>
          <allocation>Non-randomized controlled trial</allocation>
          <masking>Open (masking not used)</masking>
          <control>Active</control>
          <assignment>Parallel</assignment>
          <purposes>
            <purpose>Treatment</purpose>
          </purposes>
        </interventionalTrialDesign>
        <secondaryStudyDesign>Not applicable</secondaryStudyDesign>
        <trialTypes>
          <trialType>Treatment</trialType>
        </trialTypes>
        <overallEndDate>2025-09-10T00:00:00.000Z</overallEndDate>
      </trialDesign>
      <participants>
        <recruitmentCountries>
          <country>United Kingdom</country>
          <country>England</country>
        </recruitmentCountries>
        <trialCentres>
          <trialCentre id="04931bfa-220c-41d1-b430-571b00c4e299">
            <name>Royal Marsden NHS Foundation Trust</name>
            <city>London</city>
            <state />
            <country>England</country>
          </trialCentre>
          <trialCentre id="c287dcb9-9117-440d-ac67-2bb09a8164ef">
            <name>Churchill Hospital</name>
            <city>Oxford</city>
            <state />
            <country>England</country>
          </trialCentre>
        </trialCentres>
        <participantTypes>
          <participantType>Patient</participantType>
        </participantTypes>
        <healthyVolunteersAllowed>false</healthyVolunteersAllowed>
        <inclusion>1.	Written (signed and dated) informed consent and be capable of co-operating with HMBD-001 administration and follow-up. 

2.	Part A: Monotherapy Dose Escalation 
Histologically confirmed advanced or metastatic solid tumours resistant or ...</inclusion>
        <ageRange>Mixed</ageRange>
        <lowerAgeLimit unit="years" value="16.0">16 Years</lowerAgeLimit>
        <upperAgeLimit unit="years" value="110.0">110 Years</upperAgeLimit>
        <gender>All</gender>
        <targetEnrolment>81</targetEnrolment>
        <totalFinalEnrolment>25</totalFinalEnrolment>
        <exclusion>1.	Radiotherapy (except for palliative reasons), chemotherapy, endocrine therapy (with the exceptions of life-long hormone suppression such as luteinising hormone-releasing hormone [LHRH] agents in prostate cancer and patients that are ...</exclusion>
        <recruitmentStart>2021-10-07T00:00:00.000Z</recruitmentStart>
        <recruitmentEnd>2024-08-19T00:00:00.000Z</recruitmentEnd>
        <recruitmentStartStatusOverride />
        <recruitmentStatusOverride />
      </participants>
      <conditions>
        <condition>
          <description>Bladder Cancer
Triple Negative Breast Cancer 
Castration-resistant Prostate Cancer (metastatic) 
Cervical Cancer
RAS Wild Type Colorectal Cancer 
Endometrial Cancer 
Gastric Cancer 
Hepatocellular Carcinoma 
Melanoma 
Non-small Cell Lung ...</description>
          <diseaseClass1>Cancer</diseaseClass1>
          <diseaseClass2 />
        </condition>
      </conditions>
      <interventions>
        <intervention>
          <description>This is an open label, multi-centre, first in human, Phase I/IIa adaptive design trial with initial single patient intrapatient dose escalation followed by inter-patient dose escalation to determine the recommended Phase II dose (RP2D) of ...</description>
          <interventionType>Drug</interventionType>
          <phase>Phase I/II</phase>
          <drugNames>HMBD-001</drugNames>
        </intervention>
      </interventions>
      <results>
        <ipdSharingStatement />
        <dataPolicies>
          <dataPolicy>Available on request</dataPolicy>
        </dataPolicies>
        <publicationDetails>2023 Abstract results in https://doi.org/10.1016/j.annonc.2023.09.1873 (added 30/09/2026)
2023 Abstract results in https://doi.org/10.1016/j.annonc.2023.09.1874 (added 30/09/2026)</publicationDetails>
        <publicationStage>Results</publicationStage>
        <basicReport>Basic results see attached file ISRCTN62918594_BasicResults_12Aug2026.pdf (added 01/09/2026)</basicReport>
        <plainEnglishReport />
      </results>
      <parties>
        <funderId>ffeef156-c094-4c52-a8d3-a22c2a7ade0a</funderId>
        <sponsorId>69a1ab93-7d0c-4f79-ae62-790c46e4948b</sponsorId>
      </parties>
    </trial>
    <sponsor id="69a1ab93-7d0c-4f79-ae62-790c46e4948b">
      <organisation>Cancer Research UK</organisation>
      <sponsorType>Charity</sponsorType>
      <rorId>https://ror.org/054225q67</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <funder id="ffeef156-c094-4c52-a8d3-a22c2a7ade0a">
      <name>Cancer Research UK</name>
    </funder>
  </fullTrial>
</allTrials>
"""

RECORD_GEFAPIXANT = """\
<allTrials xmlns="http://www.67bricks.com/isrctn" totalCount="1">
  <fullTrial>
    <trial lastUpdated="2026-08-04T13:22:23.340961015Z" version="12" isPublished="true" publicIdentifierType="isrctn" publicIdentifierCanonical="ISRCTN38597726" publicIdentifierDateAssigned="2026-08-04T14:10:18.681944Z">
      <isrctn dateAssigned="2026-08-04T14:10:18.681944Z">38597726</isrctn>
      <trialDescription thirdPartyFilesAcknowledgement="true">
        <acknowledgment>true</acknowledgment>
        <title>Gefapixant and breathing control in long COVID</title>
        <scientificTitle>Targeting the carotid chemoreflex via purinergic receptors in patients with long COVID and persistent breathing difficulties</scientificTitle>
        <acronym />
        <studyHypothesis>Aim 1: To determine whether a single dose of a P2X3 receptor antagonist; oral dose of gefapixant: 45 mg) reduces carotid chemoreceptor sensitivity in long COVID patients versus a placebo.
Aim 2: To determine whether gefapixant, a single ...</studyHypothesis>
        <plainEnglishSummary />
        <primaryOutcomes>
          <outcomeMeasure id="30a489bf-1142-4c00-a81c-de7406bdb5f7">
            <variable>Hypoxic ventilatory response (HVR) at rest</variable>
            <method>chemoreflex sensitivity, calculated as the increase in minute ventilation divided by the SpO2% (termed the hypoxic ventilatory response or HVR and expressed as L/min/SpO2%),</method>
            <timepoints>2-3 hours after taking gefapixant or placebo</timepoints>
          </outcomeMeasure>
        </primaryOutcomes>
        <primaryOutcome />
        <secondaryOutcomes />
        <secondaryOutcome>1. Resting normoxic tidal volume measured with spirometry, 2-3 hours after taking gefapixant or placebo
2. Resting end-tidal pressure of carbon dioxide (PETCO₂) measured with spirometry, 2-3 hours after taking gefapixant or placebo
3. ...</secondaryOutcome>
        <ethicsApprovalRequired>Ethics approval required</ethicsApprovalRequired>
      </trialDescription>
      <externalRefs>
        <doi>10.1186/ISRCTN38597726</doi>
        <eudraCTNumber />
        <irasNumber />
        <clinicalTrialsGovNumber />
        <protocolSerialNumber />
        <secondaryNumbers />
      </externalRefs>
      <trialDesign>
        <studyDesign />
        <primaryStudyDesign>Interventional</primaryStudyDesign>
        <interventionalTrialDesign>
          <allocation>Randomized controlled trial</allocation>
          <masking>Blinded (masking used)</masking>
          <control>Placebo</control>
          <assignment>Crossover</assignment>
          <purposes>
            <purpose>Basic science</purpose>
          </purposes>
        </interventionalTrialDesign>
        <secondaryStudyDesign>Not applicable</secondaryStudyDesign>
        <trialTypes />
        <overallEndDate>2028-01-05T00:00:00.000Z</overallEndDate>
      </trialDesign>
      <participants>
        <recruitmentCountries>
          <country>United Kingdom</country>
          <country>England</country>
        </recruitmentCountries>
        <trialCentres>
          <trialCentre id="c83b2377-0b66-43df-9b8e-dad24feb8934">
            <name>NIHR Bristol Clinical Research Facility</name>
            <city>Bristol</city>
            <state />
            <country>England</country>
          </trialCentre>
        </trialCentres>
        <participantTypes />
        <healthyVolunteersAllowed>false</healthyVolunteersAllowed>
        <inclusion>1. 18-75 years old
2. Self-reported positive PCR or antibody test before vaccination
3. Not hospitalised for any COVID-19 infection
4. Breathlessness affecting their daily lives, measured by Modified Yorkshire COVID-19 Rehabilitation Scale ...</inclusion>
        <ageRange>Mixed</ageRange>
        <lowerAgeLimit unit="years" value="18.0">18 Years</lowerAgeLimit>
        <upperAgeLimit unit="years" value="75.0">75 Years</upperAgeLimit>
        <gender>All</gender>
        <targetEnrolment>34</targetEnrolment>
        <totalFinalEnrolment>0</totalFinalEnrolment>
        <exclusion>1. Body mass index ≥35 kg/m²
2. Diagnosed with severe asthma or uncontrolled asthma
3. Pregnancy/breastfeeding women
4. Ongoing requirement of oxygen therapy 
5. Moderate anaemia (Hb &lt;100 g/dl)
6. Taking antihypertensive, nitrate, steroid ...</exclusion>
        <recruitmentStart>2026-11-02T00:00:00.000Z</recruitmentStart>
        <recruitmentEnd>2028-01-03T00:00:00.000Z</recruitmentEnd>
        <recruitmentStartStatusOverride />
        <recruitmentStatusOverride />
      </participants>
      <conditions>
        <condition>
          <description>People with long-COVID and breathlessness that affects daily life</description>
          <diseaseClass1>Infections and Infestations</diseaseClass1>
          <diseaseClass2 />
        </condition>
      </conditions>
      <interventions>
        <intervention>
          <description>A single dose of oral gefapixant (45 mg) tablet will be used as a mechanistic tool to investigate whether P2X3 receptors contribute to carotid chemoreflex hyperactivity in patients with long-COVID

We will randomise using Sealed Envelope. ...</description>
          <interventionType>Drug</interventionType>
          <phase>Not Applicable</phase>
          <drugNames>Gefapixant</drugNames>
        </intervention>
      </interventions>
      <results>
        <ipdSharingStatement />
        <dataPolicies>
          <dataPolicy>Not expected to be made available</dataPolicy>
        </dataPolicies>
        <publicationDetails />
        <publicationStage />
        <basicReport />
        <plainEnglishReport />
      </results>
      <parties>
        <funderId>ace608c7-647f-48b6-8343-9ef0e8b8316f</funderId>
        <sponsorId>304af7b4-6c0c-4e6e-b2fd-85028531e0ba</sponsorId>
      </parties>
    </trial>
    <sponsor id="304af7b4-6c0c-4e6e-b2fd-85028531e0ba">
      <organisation>University of Bristol</organisation>
      <sponsorType />
      <rorId>https://ror.org/0524sp257</rorId>
      <commercialStatus>Non-commercial</commercialStatus>
    </sponsor>
    <funder id="ace608c7-647f-48b6-8343-9ef0e8b8316f">
      <name>Medical Research Council</name>
      <fundRef>http://dx.doi.org/10.13039/501100000265</fundRef>
    </funder>
  </fullTrial>
</allTrials>
"""

EMPTY_RESULT = """<allTrials totalCount="0" xmlns="http://www.67bricks.com/isrctn"></allTrials>"""
