"""Nothing is imported until it is used.

``import knowledge_lookup`` used to load all 37 adapter modules plus pandas, rdflib,
tyto, curies, aiohttp and the ChEMBL client (which downloads an API schema on import
and crashed the package whenever ChEMBL was down). These tests run in fresh
interpreters because the unit-test session itself has everything imported already.
"""

import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.unit

import knowledge_lookup
from knowledge_lookup import adapters
from knowledge_lookup.adapters import AdapterRegistry
from knowledge_lookup.models import KnowledgeSource

HEAVY = [
    "aiohttp",
    "pydantic",
    "pandas",
    "numpy",
    "tyto",
    "rdflib",
    "requests",
    "curies",
    "bioservices",
    "chembl_webresource_client",
]


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestImportLoadsNothing:
    def test_package_import_loads_no_submodule_and_no_heavy_dependency(self):
        proc = _run(
            f"""
            import sys
            import knowledge_lookup
            submodules = [m for m in sys.modules if m.startswith("knowledge_lookup.")]
            assert submodules == [], submodules
            heavy = [m for m in {HEAVY!r} if m in sys.modules]
            assert heavy == [], heavy
            print("clean")
            """
        )
        assert proc.returncode == 0, proc.stderr
        assert "clean" in proc.stdout

    def test_one_adapter_loads_only_its_own_module(self):
        proc = _run(
            """
            import sys
            def loaded_adapters():
                prefix = "knowledge_lookup.adapters."
                return sorted(m[len(prefix):] for m in sys.modules if m.startswith(prefix))
            from knowledge_lookup import OLSAdapter
            from knowledge_lookup.adapters import ADAPTER_CLASSES
            from knowledge_lookup.models import KnowledgeSource
            assert loaded_adapters() == ["ols_adapter"], loaded_adapters()
            # membership / iteration / len do not import anything
            assert KnowledgeSource.HPO in ADAPTER_CLASSES and len(ADAPTER_CLASSES) >= 35
            list(ADAPTER_CLASSES)
            assert loaded_adapters() == ["ols_adapter"], loaded_adapters()
            assert ADAPTER_CLASSES[KnowledgeSource.OLS] is OLSAdapter
            print("ok")
            """
        )
        assert proc.returncode == 0, proc.stderr
        assert "ok" in proc.stdout

    def test_central_lookup_does_not_import_pandas_or_rdflib(self):
        proc = _run(
            """
            import sys
            from knowledge_lookup import CentralKnowledgeLookup
            for heavy in ("pandas", "numpy", "rdflib", "curies", "aiohttp", "requests", "tyto"):
                assert heavy not in sys.modules, heavy
            print("ok")
            """
        )
        assert proc.returncode == 0, proc.stderr
        assert "ok" in proc.stdout


class TestOnlyEnabledSourcesAreImported:
    def test_disabled_sources_are_never_imported(self):
        proc = _run(
            """
            import sys
            def loaded_adapters():
                prefix = "knowledge_lookup.adapters."
                return sorted(m[len(prefix):] for m in sys.modules if m.startswith(prefix))
            from knowledge_lookup import CentralKnowledgeLookup, LookupConfig, KnowledgeSource

            lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.OLS]))
            assert list(lookup.adapters) == [KnowledgeSource.OLS], list(lookup.adapters)
            assert loaded_adapters() == ["ols_adapter"], loaded_adapters()
            print("ok")
            """
        )
        assert proc.returncode == 0, proc.stderr
        assert "ok" in proc.stdout

    def test_a_broken_adapter_module_only_skips_that_source(self):
        proc = _run(
            """
            import importlib.abc, sys

            class Break(importlib.abc.MetaPathFinder):
                def find_spec(self, name, path=None, target=None):
                    if name == "knowledge_lookup.adapters.hpo_adapter":
                        raise RuntimeError("hpo client exploded on import")

            sys.meta_path.insert(0, Break())
            from knowledge_lookup import CentralKnowledgeLookup, LookupConfig, KnowledgeSource

            lookup = CentralKnowledgeLookup(
                LookupConfig(enabled_sources=[KnowledgeSource.HPO, KnowledgeSource.OLS])
            )
            assert KnowledgeSource.HPO not in lookup.adapters
            assert KnowledgeSource.OLS in lookup.adapters
            print("ok")
            """
        )
        assert proc.returncode == 0, proc.stderr
        assert "ok" in proc.stdout


class TestPackageAttributes:
    def test_public_names_resolve_lazily_and_are_cached(self):
        assert knowledge_lookup.CentralKnowledgeLookup.__name__ == "CentralKnowledgeLookup"
        assert "CentralKnowledgeLookup" in vars(knowledge_lookup)  # cached after first access
        assert knowledge_lookup.KnowledgeSource is KnowledgeSource

    def test_submodules_are_reachable_as_attributes(self):
        assert knowledge_lookup.adapters is adapters

    def test_unknown_attribute_raises_attribute_error(self):
        with pytest.raises(AttributeError, match="no attribute 'definitely_not_here'"):
            knowledge_lookup.definitely_not_here  # noqa: B018
        with pytest.raises(AttributeError):
            adapters.NotAnAdapter  # noqa: B018

    def test_dir_lists_lazy_names(self):
        assert {"CentralKnowledgeLookup", "OLSAdapter", "ADAPTER_CLASSES"} <= set(
            dir(knowledge_lookup)
        )
        assert {"OLSAdapter", "ChEMBLAdapter", "ADAPTER_CLASSES"} <= set(dir(adapters))

    def test_all_names_in___all___resolve(self):
        for name in knowledge_lookup.__all__:
            assert getattr(knowledge_lookup, name) is not None, name

    def test_curie_utils_converter_is_lazy(self):
        proc = _run(
            """
            import sys
            import knowledge_lookup.curie_utils as cu
            assert "curies" not in sys.modules
            Converter = cu.Converter
            assert "curies" in sys.modules and Converter.__name__ == "Converter"
            print("ok")
            """
        )
        assert proc.returncode == 0, proc.stderr
        assert "ok" in proc.stdout


class TestAdapterRegistry:
    SPECS = {
        KnowledgeSource.OLS: ("ols_adapter", "OLSAdapter"),
        KnowledgeSource.HPO: ("hpo_adapter", "HPOAdapter"),
    }

    def test_lists_sources_without_importing(self):
        registry = AdapterRegistry(self.SPECS)
        assert list(registry) == [KnowledgeSource.OLS, KnowledgeSource.HPO]
        assert len(registry) == 2
        assert KnowledgeSource.OLS in registry
        assert KnowledgeSource.MONDO not in registry
        assert registry._classes == {}

    def test_getitem_loads_and_caches(self):
        registry = AdapterRegistry(self.SPECS)
        assert registry[KnowledgeSource.OLS] is adapters.OLSAdapter
        assert set(registry._classes) == {KnowledgeSource.OLS}
        assert "1 loaded" in repr(registry)

    def test_unknown_source_is_a_key_error_and_get_returns_default(self):
        registry = AdapterRegistry(self.SPECS)
        with pytest.raises(KeyError):
            registry[KnowledgeSource.MONDO]
        assert registry.get(KnowledgeSource.MONDO) is None

    def test_can_register_replace_and_remove_adapters(self):
        class Custom:
            pass

        registry = AdapterRegistry(self.SPECS)
        registry[KnowledgeSource.MONDO] = Custom  # type: ignore[assignment]
        assert registry[KnowledgeSource.MONDO] is Custom
        assert KnowledgeSource.MONDO in registry
        registry[KnowledgeSource.OLS] = Custom  # type: ignore[assignment]
        assert registry[KnowledgeSource.OLS] is Custom
        del registry[KnowledgeSource.HPO]
        assert KnowledgeSource.HPO not in registry
        with pytest.raises(KeyError):
            del registry[KnowledgeSource.HPO]

    def test_optional_extra_sources_are_listed_only_when_installed(self, monkeypatch):
        monkeypatch.setattr(adapters, "_requirement_installed", lambda module: False)
        without_extra = AdapterRegistry(adapters._ADAPTER_SPECS)
        assert KnowledgeSource.CHEMBL not in without_extra
        assert KnowledgeSource.OLS in without_extra

        monkeypatch.setattr(adapters, "_requirement_installed", lambda module: True)
        assert KnowledgeSource.CHEMBL in AdapterRegistry(adapters._ADAPTER_SPECS)

    def test_registry_covers_every_adapter_class_exported(self):
        classes = {cls for _module, cls in adapters._ADAPTER_SPECS.values()}
        assert classes == set(adapters._CLASS_MODULES)
