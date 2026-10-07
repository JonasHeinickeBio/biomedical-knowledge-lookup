"""Download-once cache for bulk datasets that have no query API.

Several sources (HPO annotations, SIDER, OFFSIDES, CellMarker, ICD-10-GM, ...) are only
published as files. :func:`ensure_dataset` fetches such a file the first time it is needed,
keeps it under a cache directory and reuses it until it is older than ``max_age_days``.

Design notes:

* Nothing is downloaded at import time or when an adapter is constructed, only when
  :func:`ensure_dataset` is awaited by an adapter method that needs the data.
* The download goes to a ``.part`` file and is renamed on success, so an interrupted
  download never leaves a corrupt cache entry.
* ``.gz`` files are decompressed (``decompress=True``) and ``.zip`` archives are
  unpacked when ``member`` names the file to extract; the *usable* file is returned.
* If a refresh fails but an older copy exists, the stale copy is returned with a
  warning rather than failing the lookup.
* Locations: ``cache_dir`` argument, else ``$KNOWLEDGE_LOOKUP_DATA_DIR``, else
  ``~/.cache/knowledge_lookup/datasets``.
"""

import asyncio
import gzip
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR_ENV = "KNOWLEDGE_LOOKUP_DATA_DIR"
#: Setting this to 1/true/yes/on lets every dataset-backed source download its bulk files.
#: Each source also has its own switch (e.g. ``HPOA_DOWNLOAD``); see :func:`downloads_allowed`.
ALLOW_DOWNLOADS_ENV = "KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS"
_TRUTHY = {"1", "true", "yes", "on"}
_locks: dict[Path, asyncio.Lock] = {}


def default_cache_dir() -> Path:
    """Directory used for downloaded datasets when the caller does not pass one."""
    configured = os.environ.get(DATA_DIR_ENV)
    if configured:
        return Path(configured)
    return Path.home() / ".cache" / "knowledge_lookup" / "datasets"


def downloads_allowed(*source_env_vars: str) -> bool:
    """Whether the user has agreed to bulk dataset downloads.

    Dataset-backed adapters (HPO annotations, SIDER, OFFSIDES, CTD, ...) are only
    ``is_available()`` when their data is already on disk, a local path is configured, or
    this returns True, so a default multi-source lookup never starts a download of tens or
    hundreds of MB on its own. True when ``KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS`` or any of the
    given per-source variables is set to 1/true/yes/on.
    """
    return any(
        os.environ.get(name, "").strip().lower() in _TRUTHY
        for name in (ALLOW_DOWNLOADS_ENV, *source_env_vars)
    )


def _is_fresh(path: Path, max_age_days: float | None) -> bool:
    if not path.exists():
        return False
    if max_age_days is None:
        return True
    return (time.time() - path.stat().st_mtime) < max_age_days * 86400


async def _fetch(url: str, dest: Path, timeout: float, headers: dict[str, str] | None) -> None:
    """Stream ``url`` into ``dest``. Kept separate so tests can replace the network call."""
    import aiohttp  # deferred: only needed when a download actually happens

    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            with dest.open("wb") as handle:
                async for chunk in response.content.iter_chunked(1 << 20):
                    handle.write(chunk)


def _unpack(
    downloaded: Path, final: Path, member: str | None, decompress: bool, raw: bool = False
) -> None:
    """Turn the raw download into the file callers read (gunzip / extract one zip member)."""
    if raw:
        shutil.copyfile(downloaded, final)
    elif zipfile.is_zipfile(downloaded):
        with zipfile.ZipFile(downloaded) as archive:
            names = archive.namelist()
            chosen = member or (names[0] if len(names) == 1 else None)
            if chosen is None or chosen not in names:
                raise ValueError(f"zip archive needs member=...; contains {names[:10]}")
            with archive.open(chosen) as src, final.open("wb") as out:
                shutil.copyfileobj(src, out)
    elif decompress and downloaded.read_bytes()[:2] == b"\x1f\x8b":
        with gzip.open(downloaded, "rb") as src, final.open("wb") as out:
            shutil.copyfileobj(src, out)
    else:
        shutil.copyfile(downloaded, final)


async def ensure_dataset(
    url: str,
    *,
    filename: str | None = None,
    cache_dir: str | Path | None = None,
    max_age_days: float | None = 30,
    member: str | None = None,
    decompress: bool = True,
    raw: bool = False,
    timeout: float = 600.0,
    headers: dict[str, str] | None = None,
) -> Path:
    """Return a local copy of the dataset at ``url``, downloading it if needed.

    Args:
        url: where to download from.
        filename: name of the cached (usable) file; defaults to the last URL segment
            without a ``.gz`` suffix.
        cache_dir: override :func:`default_cache_dir`.
        max_age_days: re-download when the cached file is older; ``None`` = never refresh.
        member: file to extract when ``url`` is a zip archive with several entries.
        decompress: gunzip ``.gz`` downloads.
        raw: keep the download byte for byte. Needed for ``.xlsx`` and other formats that are
            zip containers but are meant to be read as one file.
        timeout: total seconds allowed for the download.
        headers: extra request headers.

    Raises:
        Exception: the download error when there is no cached copy to fall back on.
    """
    directory = Path(cache_dir) if cache_dir else default_cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    name = filename or url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".gz") or "dataset"
    final = directory / name

    lock = _locks.setdefault(final, asyncio.Lock())
    async with lock:
        if _is_fresh(final, max_age_days):
            return final
        part = directory / f"{name}.part"
        download = directory / f"{name}.download"
        try:
            logger.info(f"Downloading dataset {url} -> {final}")
            await _fetch(url, download, timeout, headers)
            _unpack(download, part, member, decompress, raw)
            part.replace(final)
            return final
        except Exception as exc:
            if final.exists():
                logger.warning(f"Could not refresh {url} ({exc}); using the cached copy")
                return final
            raise
        finally:
            download.unlink(missing_ok=True)
            part.unlink(missing_ok=True)
