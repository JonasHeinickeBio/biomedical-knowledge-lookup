"""Tests for the download-once dataset cache (the network call is replaced)."""

import gzip
import os
import time
import zipfile
from pathlib import Path

import pytest

from knowledge_lookup.utils import dataset_cache
from knowledge_lookup.utils.dataset_cache import default_cache_dir, ensure_dataset

pytestmark = pytest.mark.unit


@pytest.fixture
def fetch(monkeypatch):
    """Replace the network fetch; ``fetch.payload`` is written, ``fetch.calls`` records URLs."""

    class Fetch:
        payload = b"a\tb\n1\t2\n"
        calls: list[str]
        error: Exception | None = None

        def __init__(self):
            self.calls = []

    state = Fetch()

    async def fake(url, dest, timeout, headers):
        state.calls.append(url)
        if state.error:
            raise state.error
        dest.write_bytes(state.payload)

    monkeypatch.setattr(dataset_cache, "_fetch", fake)
    return state


@pytest.mark.asyncio
async def test_downloads_once_then_reuses_the_cache(tmp_path, fetch):
    first = await ensure_dataset("https://example.org/data/phenotype.hpoa", cache_dir=tmp_path)
    second = await ensure_dataset("https://example.org/data/phenotype.hpoa", cache_dir=tmp_path)
    assert first == second == tmp_path / "phenotype.hpoa"
    assert first.read_bytes() == fetch.payload
    assert len(fetch.calls) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["phenotype.hpoa"]  # no temp files


@pytest.mark.asyncio
async def test_gzip_is_decompressed_and_name_loses_the_gz_suffix(tmp_path, fetch):
    fetch.payload = gzip.compress(b"hello\n")
    path = await ensure_dataset("https://example.org/meddra_all_se.tsv.gz", cache_dir=tmp_path)
    assert path.name == "meddra_all_se.tsv"
    assert path.read_bytes() == b"hello\n"


@pytest.mark.asyncio
async def test_gzip_kept_when_decompress_is_false(tmp_path, fetch):
    fetch.payload = gzip.compress(b"hello\n")
    path = await ensure_dataset(
        "https://example.org/x.tsv.gz", cache_dir=tmp_path, filename="x.tsv.gz", decompress=False
    )
    assert path.read_bytes() == fetch.payload


@pytest.mark.asyncio
async def test_zip_member_is_extracted(tmp_path, fetch):
    archive = tmp_path / "src.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("a.txt", "AAA")
        z.writestr("b.txt", "BBB")
    fetch.payload = archive.read_bytes()
    path = await ensure_dataset(
        "https://example.org/bundle.zip",
        cache_dir=tmp_path / "c",
        member="b.txt",
        filename="b.txt",
    )
    assert path.read_text() == "BBB"


@pytest.mark.asyncio
async def test_zip_with_several_members_needs_member(tmp_path, fetch):
    archive = tmp_path / "src.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("a.txt", "A")
        z.writestr("b.txt", "B")
    fetch.payload = archive.read_bytes()
    with pytest.raises(ValueError, match="member"):
        await ensure_dataset("https://example.org/bundle.zip", cache_dir=tmp_path / "c")
    assert not list((tmp_path / "c").glob("*.part"))


@pytest.mark.asyncio
async def test_stale_file_is_refreshed(tmp_path, fetch):
    target = tmp_path / "d.tsv"
    target.write_bytes(b"old")
    old = time.time() - 40 * 86400
    os.utime(target, (old, old))
    path = await ensure_dataset("https://example.org/d.tsv", cache_dir=tmp_path, max_age_days=30)
    assert path.read_bytes() == fetch.payload
    assert fetch.calls == ["https://example.org/d.tsv"]


@pytest.mark.asyncio
async def test_failed_refresh_falls_back_to_the_stale_copy(tmp_path, fetch):
    target = tmp_path / "d.tsv"
    target.write_bytes(b"old")
    old = time.time() - 40 * 86400
    os.utime(target, (old, old))
    fetch.error = RuntimeError("503")
    path = await ensure_dataset("https://example.org/d.tsv", cache_dir=tmp_path, max_age_days=30)
    assert path.read_bytes() == b"old"


@pytest.mark.asyncio
async def test_failed_first_download_raises_and_leaves_nothing_behind(tmp_path, fetch):
    fetch.error = RuntimeError("503")
    with pytest.raises(RuntimeError, match="503"):
        await ensure_dataset("https://example.org/d.tsv", cache_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_max_age_none_never_refreshes(tmp_path, fetch):
    target = tmp_path / "d.tsv"
    target.write_bytes(b"old")
    ancient = time.time() - 3650 * 86400
    os.utime(target, (ancient, ancient))
    path = await ensure_dataset("https://example.org/d.tsv", cache_dir=tmp_path, max_age_days=None)
    assert path.read_bytes() == b"old"
    assert fetch.calls == []


def test_default_cache_dir_honours_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path))
    assert default_cache_dir() == tmp_path
    monkeypatch.delenv("KNOWLEDGE_LOOKUP_DATA_DIR")
    assert default_cache_dir() == Path.home() / ".cache" / "knowledge_lookup" / "datasets"
