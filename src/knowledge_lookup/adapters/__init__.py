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
from .umls_adapter import UMLSAdapter
from .unichem_adapter import UniChemAdapter
from .uniprot_adapter import UniProtAdapter
from .wikidata_adapter import WikidataAdapter
from .zooma_adapter import ZoomaAdapter

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
]
