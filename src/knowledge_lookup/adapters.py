"""
Adapter imports and adapter class mapping for CentralKnowledgeLookup.
"""

from .adapters.biolinker_adapter import BioLinkerAdapter
from .adapters.bioontology_adapter import BioOntologyAdapter
from .adapters.bioportal_adapter import BioPortalAdapter
from .adapters.dbpedia_adapter import DBpediaAdapter
from .adapters.disgenet_adapter import DisGeNETAdapter
from .adapters.drugbank_adapter import DrugBankAdapter
from .adapters.ebiols_adapter import EBIOLSAdapter
from .adapters.ensembl_adapter import EnsemblAdapter
from .adapters.geneontology_adapter import GeneOntologyAdapter
from .adapters.hpo_adapter import HPOAdapter
from .adapters.mondo_adapter import MondoAdapter
from .adapters.obofoundry_adapter import OBOFoundryAdapter
from .adapters.ols_adapter import OLSAdapter
from .adapters.opentargets_adapter import OpenTargetsAdapter
from .adapters.oxo_adapter import OxOAdapter
from .adapters.pubchem_adapter import PubChemAdapter
from .adapters.reactome_adapter import ReactomeAdapter
from .adapters.tyto_adapter import TytoAdapter
from .adapters.umls_adapter import UMLSAdapter
from .adapters.unichem_adapter import UniChemAdapter
from .adapters.uniprot_adapter import UniProtAdapter
from .adapters.wikidata_adapter import WikidataAdapter
from .adapters.zooma_adapter import ZoomaAdapter
from .models import KnowledgeSource

ADAPTER_CLASSES = {
    KnowledgeSource.UMLS: UMLSAdapter,
    KnowledgeSource.UNICHEM: UniChemAdapter,
    KnowledgeSource.BIOPORTAL: BioPortalAdapter,
    KnowledgeSource.OLS: OLSAdapter,
    KnowledgeSource.WIKIDATA: WikidataAdapter,
    KnowledgeSource.TYTO: TytoAdapter,
    KnowledgeSource.ZOOMA: ZoomaAdapter,
    KnowledgeSource.BIOLINKER: BioLinkerAdapter,
    KnowledgeSource.OXO: OxOAdapter,
    KnowledgeSource.MONDO: MondoAdapter,
    KnowledgeSource.UNIPROT: UniProtAdapter,
    KnowledgeSource.DBPEDIA: DBpediaAdapter,
    KnowledgeSource.BIOONTOLOGY: BioOntologyAdapter,
    KnowledgeSource.DISGENET: DisGeNETAdapter,
    KnowledgeSource.OPENTARGETS: OpenTargetsAdapter,
    KnowledgeSource.REACTOME: ReactomeAdapter,
    KnowledgeSource.PUBCHEM: PubChemAdapter,
    KnowledgeSource.DRUGBANK: DrugBankAdapter,
    KnowledgeSource.GO: GeneOntologyAdapter,
    KnowledgeSource.HPO: HPOAdapter,
    KnowledgeSource.OBOFOUNDRY: OBOFoundryAdapter,
    KnowledgeSource.EBIOLS: EBIOLSAdapter,
    KnowledgeSource.ENSEMBL: EnsemblAdapter,
    # Add more adapters as needed
}
