"""
Knowledge Source Adapters Package

This package contains adapters for various knowledge sources.
"""

# Import statement order is important due to dependencies
from .biolinker_adapter import BioLinkerAdapter
from .bioontology_adapter import BioOntologyAdapter
from .bioportal_adapter import BioPortalAdapter
from .dbpedia_adapter import DBpediaAdapter
from .disgenet_adapter import DisGeNETAdapter
from .drugbank_adapter import DrugBankAdapter
from .ebiols_adapter import EBIOLSAdapter
from .ensembl_adapter import EnsemblAdapter
from .geneontology_adapter import GeneOntologyAdapter
from .hpo_adapter import HPOAdapter
from .kegg_adapter import KEGGAdapter
from .mondo_adapter import MondoAdapter
from .obofoundry_adapter import OBOFoundryAdapter
from .ols_adapter import OLSAdapter
from .opentargets_adapter import OpenTargetsAdapter
from .oxo_adapter import OxOAdapter
from .pubchem_adapter import PubChemAdapter
from .quickgo_adapter import QuickGOAdapter
from .reactome_adapter import ReactomeAdapter
from .tyto_adapter import TytoAdapter
from .umls_adapter import UMLSAdapter
from .unichem_adapter import UniChemAdapter
from .uniprot_adapter import UniProtAdapter
from .wikidata_adapter import WikidataAdapter
from .zooma_adapter import ZoomaAdapter

# Note: UMLS adapter requires umls-client dependency

__all__ = [
    "UMLSAdapter",
    "UniChemAdapter",
    "BioPortalAdapter",
    "OLSAdapter",
    "WikidataAdapter",
    "BioLinkerAdapter",
    "DBpediaAdapter",
    "OxOAdapter",
    "BioOntologyAdapter",
    "MondoAdapter",
    "UniProtAdapter",
    "DisGeNETAdapter",
    "OpenTargetsAdapter",
    "ReactomeAdapter",
    "PubChemAdapter",
    "DrugBankAdapter",
    "GeneOntologyAdapter",
    "HPOAdapter",
    "OBOFoundryAdapter",
    "EBIOLSAdapter",
    "EnsemblAdapter",
    "KEGGAdapter",
    "QuickGOAdapter",
    "ZoomaAdapter",
    "TytoAdapter",
]

# Adapter class mappings for CentralKnowledgeLookup
from ..models import KnowledgeSource

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
    KnowledgeSource.GENEONTOLOGY: GeneOntologyAdapter,
    KnowledgeSource.HPO: HPOAdapter,
    KnowledgeSource.OBOFOUNDRY: OBOFoundryAdapter,
    KnowledgeSource.EBIOLS: EBIOLSAdapter,
    KnowledgeSource.ENSEMBL: EnsemblAdapter,
    KnowledgeSource.KEGG: KEGGAdapter,
    KnowledgeSource.QUICKGO: QuickGOAdapter,
    # Add more adapters as needed
}
