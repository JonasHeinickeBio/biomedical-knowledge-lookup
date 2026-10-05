"""The ChEMBL client downloads the API schema when imported, so it must be imported lazily.

Regression: with the ``chembl`` extra installed, ``import knowledge_lookup`` crashed
whenever the ChEMBL API was down (HTTP 500 on ``/chembl/api/data/spore``), because
``adapters/chembl_adapter.py`` imported ``new_client`` at module level.
"""

import subprocess
import sys
import textwrap
import types
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.adapters.chembl_adapter import ChEMBLAdapter
from knowledge_lookup.models import LookupConfig


def _run(code: str, fake_package: bool = True, tmp_path=None) -> subprocess.CompletedProcess:
    """Run ``code`` in a fresh interpreter, optionally with a ChEMBL client that explodes on import."""
    env = None
    if fake_package:
        pkg = tmp_path / "chembl_webresource_client"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "new_client.py").write_text(
            "raise RuntimeError('Error getting schema ... with status 500')\n"
        )
        import os

        env = {
            **os.environ,
            "PYTHONPATH": f"{tmp_path}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
        }
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


class TestChEMBLDownDoesNotBreakImport:
    def test_package_imports_when_chembl_client_import_fails(self, tmp_path):
        proc = _run(
            """
            import knowledge_lookup
            from knowledge_lookup.adapters import ChEMBLAdapter, ADAPTER_CLASSES
            from knowledge_lookup.models import KnowledgeSource
            assert ChEMBLAdapter is not None
            assert ADAPTER_CLASSES[KnowledgeSource.CHEMBL] is ChEMBLAdapter
            print("imported OK")
            """,
            tmp_path=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        assert "imported OK" in proc.stdout

    def test_chembl_calls_fail_softly_while_it_is_down(self, tmp_path):
        proc = _run(
            """
            import asyncio
            from knowledge_lookup.adapters import ChEMBLAdapter
            from knowledge_lookup.models import LookupConfig

            adapter = ChEMBLAdapter(LookupConfig())
            assert asyncio.run(adapter.search_concepts("aspirin")) == []
            status = adapter.check_api_status()
            assert status["available"] is False
            assert "could not be loaded" in status["error"], status
            print("soft failure OK")
            """,
            tmp_path=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        assert "soft failure OK" in proc.stdout

    def test_adapter_is_skipped_when_the_extra_is_not_installed(self):
        proc = _run(
            """
            import importlib.abc, sys

            class Block(importlib.abc.MetaPathFinder):
                def find_spec(self, name, path=None, target=None):
                    if name.split(".")[0] == "chembl_webresource_client":
                        raise ModuleNotFoundError(name)

            sys.meta_path.insert(0, Block())
            from knowledge_lookup.adapters import ChEMBLAdapter, ADAPTER_CLASSES
            from knowledge_lookup.models import KnowledgeSource
            assert ChEMBLAdapter is None
            assert KnowledgeSource.CHEMBL not in ADAPTER_CLASSES
            print("skipped OK")
            """,
            fake_package=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert "skipped OK" in proc.stdout


class TestLazyClientProperty:
    @pytest.fixture
    def adapter(self):
        adapter = ChEMBLAdapter(LookupConfig())
        adapter._chembl_client = None
        return adapter

    @pytest.fixture
    def fake_new_client_module(self, monkeypatch):
        module = types.ModuleType("chembl_webresource_client.new_client")
        module.new_client = MagicMock(name="new_client")
        monkeypatch.setitem(sys.modules, "chembl_webresource_client.new_client", module)
        return module

    def test_client_is_imported_on_first_access_and_cached(self, adapter, fake_new_client_module):
        assert adapter._chembl_client is None
        assert adapter.chembl_client is fake_new_client_module.new_client
        assert adapter._chembl_client is fake_new_client_module.new_client
        # second access reuses the cached client
        fake_new_client_module.new_client = MagicMock(name="other")
        assert adapter.chembl_client is not fake_new_client_module.new_client

    def test_failed_import_is_not_cached(self, adapter, monkeypatch):
        class Exploding(types.ModuleType):
            def __getattr__(self, name):
                raise RuntimeError("ChEMBL is down")

        monkeypatch.setitem(
            sys.modules,
            "chembl_webresource_client.new_client",
            Exploding("chembl_webresource_client.new_client"),
        )
        with pytest.raises(RuntimeError, match="ChEMBL is down"):
            adapter.chembl_client
        assert adapter._chembl_client is None

        recovered = types.ModuleType("chembl_webresource_client.new_client")
        recovered.new_client = MagicMock(name="recovered")
        monkeypatch.setitem(sys.modules, "chembl_webresource_client.new_client", recovered)
        assert adapter.chembl_client is recovered.new_client

    def test_client_can_be_injected(self, adapter):
        client = MagicMock()
        adapter.chembl_client = client
        assert adapter.chembl_client is client

    @pytest.mark.asyncio
    async def test_query_async_loads_the_client_off_the_event_loop(
        self, adapter, fake_new_client_module
    ):
        import threading

        loop_thread = threading.get_ident()
        import_threads = []

        class Recording(types.ModuleType):
            def __getattr__(self, name):
                import_threads.append(threading.get_ident())
                return fake_new_client_module.new_client

        sys.modules["chembl_webresource_client.new_client"] = Recording("x")
        try:
            fake_new_client_module.new_client.molecule.filter.return_value = [{"a": 1}]
            fake_new_client_module.new_client.molecule.filter.return_value = MagicMock(
                __getitem__=lambda self, k: [{"a": 1}]
            )
            await adapter.query_async("molecule", filters={"pref_name__icontains": "x"}, limit=1)
        finally:
            sys.modules["chembl_webresource_client.new_client"] = fake_new_client_module
        assert import_threads, "client was never imported"
        assert loop_thread not in import_threads
