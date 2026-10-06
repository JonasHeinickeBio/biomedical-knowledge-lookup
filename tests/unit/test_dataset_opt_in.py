"""Dataset-backed sources never start a bulk download on their own.

HPO annotations (~36 MB), SIDER (~5.5 MB), OFFSIDES (~69 MB), CTD (~220 MB core) and
CellMarker only ``is_available()`` when their data is already on disk, a local path is
configured, or the user opted in (per-source ``<NAME>_DOWNLOAD=1`` or the global
``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1``). Otherwise a default multi-source lookup, or
``knowledge-lookup check all``, would download hundreds of MB without anyone agreeing.
"""

from pathlib import Path

import pytest

from knowledge_lookup.adapters.ctd_adapter import FILE_CHEMICALS, CTDAdapter
from knowledge_lookup.adapters.hpoa_adapter import HPOA_FILENAME, HPOAAdapter
from knowledge_lookup.adapters.offsides_adapter import OFFSIDES_FILENAME, OFFSIDESAdapter
from knowledge_lookup.adapters.sider_adapter import SIDERAdapter
from knowledge_lookup.models import LookupConfig

pytestmark = pytest.mark.unit

ENV_VARS = (
    "KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS",
    "KNOWLEDGE_LOOKUP_DATA_DIR",
    "HPOA_PATH",
    "HPOA_DOWNLOAD",
    "SIDER_DATA_DIR",
    "SIDER_DOWNLOAD",
    "OFFSIDES_PATH",
    "OFFSIDES_DOWNLOAD",
    "CTD_DATA_DIR",
    "CTD_DOWNLOAD",
)

# adapter class, its own opt-in variable, a file whose presence in the cache dir means "cached"
CASES = [
    pytest.param(HPOAAdapter, "HPOA_DOWNLOAD", HPOA_FILENAME, id="hpoa"),
    pytest.param(SIDERAdapter, "SIDER_DOWNLOAD", "meddra_all_se.tsv", id="sider"),
    pytest.param(OFFSIDESAdapter, "OFFSIDES_DOWNLOAD", OFFSIDES_FILENAME, id="offsides"),
    pytest.param(CTDAdapter, "CTD_DOWNLOAD", f"ctd/{FILE_CHEMICALS}", id="ctd"),
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.mark.parametrize(("adapter_class", "switch", "cached_name"), CASES)
class TestOptIn:
    def test_unavailable_by_default(self, adapter_class, switch, cached_name):
        assert adapter_class(LookupConfig()).is_available() is False

    def test_per_source_switch(self, adapter_class, switch, cached_name, monkeypatch):
        monkeypatch.setenv(switch, "1")
        assert adapter_class(LookupConfig()).is_available() is True

    def test_global_switch(self, adapter_class, switch, cached_name, monkeypatch):
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS", "true")
        assert adapter_class(LookupConfig()).is_available() is True

    def test_falsy_switch_does_not_enable(self, adapter_class, switch, cached_name, monkeypatch):
        monkeypatch.setenv(switch, "0")
        assert adapter_class(LookupConfig()).is_available() is False

    def test_data_already_cached(self, adapter_class, switch, cached_name, clean_environment):
        cached = Path(clean_environment) / cached_name
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"x")
        assert adapter_class(LookupConfig()).is_available() is True


def test_sider_local_directory_counts_as_consent(monkeypatch, tmp_path):
    monkeypatch.setenv("SIDER_DATA_DIR", str(tmp_path))
    assert SIDERAdapter(LookupConfig()).is_available() is True
    monkeypatch.setenv("SIDER_DATA_DIR", str(tmp_path / "missing"))
    assert SIDERAdapter(LookupConfig()).is_available() is False


def test_ctd_local_data_dir_with_core_file_counts_as_consent(monkeypatch, tmp_path):
    monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
    assert CTDAdapter(LookupConfig()).is_available() is False
    (tmp_path / FILE_CHEMICALS).write_bytes(b"x")
    assert CTDAdapter(LookupConfig()).is_available() is True
