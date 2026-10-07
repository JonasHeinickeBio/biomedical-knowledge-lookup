"""
Knowledge Source Adapters Package

This package contains adapters for various knowledge sources.

Nothing is imported until it is needed. Adapter modules (and the client libraries
some of them wrap, which can do network I/O or hang while they import) are loaded
the first time an adapter class is accessed, either as an attribute
(``from knowledge_lookup.adapters import OLSAdapter``) or through
:data:`ADAPTER_CLASSES`. A broken or unreachable source therefore only affects its
own adapter, never ``import knowledge_lookup``.
"""

import importlib
import importlib.util
import sys
from collections.abc import Iterator, MutableMapping
from typing import TYPE_CHECKING, Any

from ..models import KnowledgeSource

if TYPE_CHECKING:
    from ..base import KnowledgeSourceAdapter

# Source -> (adapter module in this package, adapter class name).
_ADAPTER_SPECS: dict[KnowledgeSource, tuple[str, str]] = {
    KnowledgeSource.UNICHEM: ("unichem_adapter", "UniChemAdapter"),
    KnowledgeSource.BIOPORTAL: ("bioportal_adapter", "BioPortalAdapter"),
    KnowledgeSource.OLS: ("ols_adapter", "OLSAdapter"),
    KnowledgeSource.WIKIDATA: ("wikidata_adapter", "WikidataAdapter"),
    KnowledgeSource.TYTO: ("tyto_adapter", "TytoAdapter"),
    KnowledgeSource.ZOOMA: ("zooma_adapter", "ZoomaAdapter"),
    KnowledgeSource.BIOLINKER: ("biolinker_adapter", "BioLinkerAdapter"),
    KnowledgeSource.DBPEDIA: ("dbpedia_adapter", "DBpediaAdapter"),
    KnowledgeSource.OXO: ("oxo_adapter", "OxOAdapter"),
    KnowledgeSource.BIOONTOLOGY: ("bioontology_adapter", "BioOntologyAdapter"),
    KnowledgeSource.MONDO: ("mondo_adapter", "MondoAdapter"),
    KnowledgeSource.UNIPROT: ("uniprot_adapter", "UniProtAdapter"),
    KnowledgeSource.DISGENET: ("disgenet_adapter", "DisGeNETAdapter"),
    KnowledgeSource.OPENTARGETS: ("opentargets_adapter", "OpenTargetsAdapter"),
    KnowledgeSource.REACTOME: ("reactome_adapter", "ReactomeAdapter"),
    KnowledgeSource.PUBCHEM: ("pubchem_adapter", "PubChemAdapter"),
    KnowledgeSource.DRUGBANK: ("drugbank_adapter", "DrugBankAdapter"),
    KnowledgeSource.GENEONTOLOGY: ("geneontology_adapter", "GeneOntologyAdapter"),
    KnowledgeSource.HPO: ("hpo_adapter", "HPOAdapter"),
    KnowledgeSource.OBOFOUNDRY: ("obofoundry_adapter", "OBOFoundryAdapter"),
    KnowledgeSource.EBIOLS: ("ebiols_adapter", "EBIOLSAdapter"),
    KnowledgeSource.ENSEMBL: ("ensembl_adapter", "EnsemblAdapter"),
    KnowledgeSource.KEGG: ("kegg_adapter", "KEGGAdapter"),
    KnowledgeSource.QUICKGO: ("quickgo_adapter", "QuickGOAdapter"),
    KnowledgeSource.EUTILS: ("eutils_adapter", "EUtilsAdapter"),
    KnowledgeSource.EUROPEPMC: ("europepmc_adapter", "EuropePMCAdapter"),
    KnowledgeSource.HGNC: ("hgnc_adapter", "HGNCAdapter"),
    KnowledgeSource.OMIM: ("omim_adapter", "OMIMAdapter"),
    KnowledgeSource.CLINVAR: ("clinvar_adapter", "ClinVarAdapter"),
    KnowledgeSource.COSMIC: ("cosmic_adapter", "COSMICAdapter"),
    KnowledgeSource.PDB: ("pdb_adapter", "PDBAdapter"),
    KnowledgeSource.INTERPRO: ("interpro_adapter", "InterProAdapter"),
    KnowledgeSource.PFAM: ("pfam_adapter", "PfamAdapter"),
    KnowledgeSource.STRING: ("string_adapter", "STRINGAdapter"),
    KnowledgeSource.WIKIPATHWAYS: ("wikipathways_adapter", "WikiPathwaysAdapter"),
    KnowledgeSource.CHEMBL: ("chembl_adapter", "ChEMBLAdapter"),
    KnowledgeSource.UMLS: ("umls_adapter", "UMLSAdapter"),
    KnowledgeSource.MONARCH: ("monarch_adapter", "MonarchAdapter"),
    KnowledgeSource.HPOA: ("hpoa_adapter", "HPOAAdapter"),
    KnowledgeSource.NODENORM: ("nodenorm_adapter", "NodeNormAdapter"),
    KnowledgeSource.MESH: ("mesh_adapter", "MeSHAdapter"),
    KnowledgeSource.RXCLASS: ("rxclass_adapter", "RxClassAdapter"),
    KnowledgeSource.SNOMEDCT: ("snomedct_adapter", "SnomedCTAdapter"),
    KnowledgeSource.ICD11: ("icd11_adapter", "ICD11Adapter"),
    KnowledgeSource.ICD10GM: ("icd10gm_adapter", "ICD10GMAdapter"),
    KnowledgeSource.LOINC: ("loinc_adapter", "LoincAdapter"),
    KnowledgeSource.GWASCATALOG: ("gwascatalog_adapter", "GWASCatalogAdapter"),
    KnowledgeSource.CTD: ("ctd_adapter", "CTDAdapter"),
    KnowledgeSource.DGIDB: ("dgidb_adapter", "DGIdbAdapter"),
    KnowledgeSource.INTACT: ("intact_adapter", "IntActAdapter"),
    KnowledgeSource.PUBTATOR: ("pubtator_adapter", "PubTatorAdapter"),
    KnowledgeSource.CLINICALTRIALS: ("clinicaltrials_adapter", "ClinicalTrialsAdapter"),
    KnowledgeSource.SEMMEDDB: ("semmeddb_adapter", "SemMedDBAdapter"),
    KnowledgeSource.SIDER: ("sider_adapter", "SIDERAdapter"),
    KnowledgeSource.OFFSIDES: ("offsides_adapter", "OFFSIDESAdapter"),
    KnowledgeSource.HUMANPROTEINATLAS: ("hpa_adapter", "HumanProteinAtlasAdapter"),
    KnowledgeSource.CELLONTOLOGY: ("cellontology_adapter", "CellOntologyAdapter"),
    KnowledgeSource.CELLMARKER: ("cellmarker_adapter", "CellMarkerAdapter"),
    KnowledgeSource.CHEBI: ("chebi_adapter", "ChEBIAdapter"),
    KnowledgeSource.MYGENEINFO: ("mygeneinfo_adapter", "MyGeneInfoAdapter"),
    KnowledgeSource.LITCOVID: ("litcovid_adapter", "LitCovidAdapter"),
    KnowledgeSource.OPENALEX: ("openalex_adapter", "OpenAlexAdapter"),
    KnowledgeSource.OPENFDAEVENTS: ("openfdaevents_adapter", "OpenFDAEventsAdapter"),
    KnowledgeSource.ORPHANET: ("orphanet_adapter", "OrphanetAdapter"),
    KnowledgeSource.CLINGEN: ("clingen_adapter", "ClinGenAdapter"),
    KnowledgeSource.GENCC: ("gencc_adapter", "GenCCAdapter"),
    KnowledgeSource.MEDGEN: ("medgen_adapter", "MedGenAdapter"),
    KnowledgeSource.DOID: ("doid_adapter", "DiseaseOntologyAdapter"),
    KnowledgeSource.GTEX: ("gtex_adapter", "GTExAdapter"),
    KnowledgeSource.GNOMAD: ("gnomad_adapter", "GnomADAdapter"),
    KnowledgeSource.DBSNP: ("dbsnp_adapter", "DbSNPAdapter"),
    KnowledgeSource.ALPHAFOLD: ("alphafold_adapter", "AlphaFoldAdapter"),
    KnowledgeSource.RXNORM: ("rxnorm_adapter", "RxNormAdapter"),
    KnowledgeSource.CLINPGX: ("clinpgx_adapter", "ClinPGxAdapter"),
    KnowledgeSource.OPENFDALABELS: ("openfdalabels_adapter", "OpenFDALabelsAdapter"),
}

# Adapters that need an optional extra: source -> importable top-level module the
# adapter requires. Presence is decided with ``find_spec`` (no import, no network),
# so a core install does not list them. Their class names resolve to ``None`` when
# the extra is missing, as before.
_OPTIONAL_REQUIREMENTS: dict[KnowledgeSource, str] = {
    KnowledgeSource.CHEMBL: "chembl_webresource_client",
}

_CLASS_MODULES: dict[str, str] = {cls: module for module, cls in _ADAPTER_SPECS.values()}
_OPTIONAL_CLASSES = {
    _ADAPTER_SPECS[source][1]
    for source in (*_OPTIONAL_REQUIREMENTS, KnowledgeSource.UMLS)
    if source in _ADAPTER_SPECS
}


def _requirement_installed(module: str) -> bool:
    if module in sys.modules:
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _load_adapter_class(class_name: str) -> Any:
    """Import the adapter module for ``class_name`` and return the class.

    Returns ``None`` for the optional-extra adapters (ChEMBL, UMLS) when their
    module cannot be imported; any other import failure is a real error.
    """
    module = importlib.import_module(f".{_CLASS_MODULES[class_name]}", __name__)
    try:
        return getattr(module, class_name)
    except AttributeError:  # pragma: no cover - registry/module mismatch
        raise ImportError(f"{module.__name__} has no {class_name}") from None


def __getattr__(name: str) -> Any:
    """Lazily resolve adapter classes (PEP 562) and cache them as module attributes."""
    if name in _CLASS_MODULES:
        try:
            cls = _load_adapter_class(name)
        except ImportError:
            if name not in _OPTIONAL_CLASSES:
                raise
            cls = None
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), *_CLASS_MODULES})


class AdapterRegistry(MutableMapping[KnowledgeSource, "type[KnowledgeSourceAdapter]"]):
    """``KnowledgeSource`` -> adapter class, importing each class on first access.

    Membership, ``len`` and iteration use only the static table, so ``in``,
    ``keys()`` and ``list(registry)`` import nothing. ``registry[source]``,
    ``get``, ``values()`` and ``items()`` import the adapter module(s) they touch
    and raise ``ImportError`` if a module cannot be imported. Sources whose
    optional extra is not installed are not listed. Classes may also be
    registered or replaced at runtime (``registry[source] = MyAdapter``).
    """

    def __init__(self, specs: dict[KnowledgeSource, tuple[str, str]]):
        self._specs = {
            source: spec
            for source, spec in specs.items()
            if source not in _OPTIONAL_REQUIREMENTS
            or _requirement_installed(_OPTIONAL_REQUIREMENTS[source])
        }
        self._classes: dict[KnowledgeSource, type[KnowledgeSourceAdapter]] = {}

    def _keys(self) -> list[KnowledgeSource]:
        return [*self._specs, *(s for s in self._classes if s not in self._specs)]

    def __getitem__(self, source: KnowledgeSource) -> "type[KnowledgeSourceAdapter]":
        if source in self._classes:
            return self._classes[source]
        if source not in self._specs:
            raise KeyError(source)
        cls = getattr(sys.modules[__name__], self._specs[source][1])
        if cls is None:
            raise KeyError(source)
        self._classes[source] = cls
        return cls

    def __setitem__(self, source: KnowledgeSource, cls: "type[KnowledgeSourceAdapter]") -> None:
        self._classes[source] = cls

    def __delitem__(self, source: KnowledgeSource) -> None:
        if source not in self._specs and source not in self._classes:
            raise KeyError(source)
        self._specs.pop(source, None)
        self._classes.pop(source, None)

    def __contains__(self, source: object) -> bool:
        return source in self._specs or source in self._classes

    def __iter__(self) -> Iterator[KnowledgeSource]:
        return iter(self._keys())

    def __len__(self) -> int:
        return len(self._keys())

    def __repr__(self) -> str:
        loaded = sum(1 for s in self._keys() if s in self._classes)
        return f"<AdapterRegistry {len(self)} sources, {loaded} loaded>"


ADAPTER_CLASSES = AdapterRegistry(_ADAPTER_SPECS)

__all__ = [*sorted(_CLASS_MODULES), "AdapterRegistry", "ADAPTER_CLASSES"]
