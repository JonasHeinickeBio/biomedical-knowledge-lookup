#!/usr/bin/env python3
"""Live probe of every Ensembl REST endpoint wrapped by EnsemblAdapter.

Fires one small, representative request at each endpoint, saves the raw
response to ``docs/adapters/proteins/ensembl_rest_responses/`` and writes
``manifest.json`` describing each response (status, size, top-level shape,
first item). Non-2xx bodies are saved too - error shapes are documented as
well.

The first probes resolve real IDs from live responses (transcript, cDNA,
CDS, translation, phenotype accession, GA4GH collection IDs), so the
ID-dependent endpoints are exercised with valid input.

Usage:
    poetry run python scripts/probe_ensembl_endpoints.py
    poetry run python scripts/probe_ensembl_endpoints.py --only vep --sleep 1
    poetry run python scripts/probe_ensembl_endpoints.py \
        --base-url https://useast.rest.ensembl.org

Exit code 0 when every probe returned 2xx (or was skipped), 1 otherwise.
"""

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import aiohttp

# -- Sample values -----------------------------------------------------------
# INS on chr11 (GRCh38), a small protein-coding gene with well-known variants.
SPECIES = "homo_sapiens"
GENE = "ENSG00000133056"  # INS
BRCA2 = "ENSG00000139618"
TAX_ID = 9606
CHROM, START, END = "11", 2159779, 2161209
REGION = f"{CHROM}:{START}-{END}"
RS = "rs1801270"  # INS G60D
HGVS = f"NC_000011.10:g.{START}A>G"
GO_TERM = "GO:0006915"  # apoptotic process

USER_AGENT = "biomedical-knowledge-lookup-probe/1.0"
MAX_SAVE_BYTES = 500_000


def qparams(**kw: object) -> dict[str, str]:
    """Mirror EnsemblAdapter._params(): content-type first, drop Nones."""
    q: dict[str, str] = {"content-type": "application/json"}
    for key, value in kw.items():
        if value is not None:
            q[key] = value if isinstance(value, str) else str(value)
    return q


@dataclass
class Result:
    name: str
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: object = None
    status: int = 0
    ok: bool = False
    bytes: int = 0
    elapsed_ms: int = 0
    shape: str = ""
    sample: object = None
    error: str = ""
    skipped: str = ""
    truncated: bool = False
    file: str = ""


async def fetch(
    session: aiohttp.ClientSession,
    base_url: str,
    method: str,
    path: str,
    query: dict[str, str],
    body: object,
    timeout: float,
) -> tuple[int, str, dict[str, str], int]:
    """One request; retries once on 429 (30 s) or 5xx (5 s)."""
    url = base_url.rstrip("/") + path
    for attempt in (1, 2):
        try:
            async with session.request(
                method, url, params=query, json=body, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                text = await resp.text()
                headers = {k.lower(): v for k, v in resp.headers.items()}
                if resp.status == 429 and attempt == 1:
                    await asyncio.sleep(30)
                    continue
                if 500 <= resp.status < 600 and attempt == 1:
                    await asyncio.sleep(5)
                    continue
                return resp.status, text, headers, int(resp.content_length or 0)
        except (TimeoutError, aiohttp.ClientError) as exc:
            if attempt == 1:
                await asyncio.sleep(5)
                continue
            return 0, f"request failed: {exc!r}", {}, 0
    raise AssertionError("unreachable")


def summarize(data: object) -> tuple[str, object]:
    """(shape string, first item or the scalar itself)."""
    if isinstance(data, list):
        return f"list[{len(data)}]", data[0] if data else None
    if isinstance(data, dict):
        keys = ",".join(list(data.keys())[:12])
        return f"dict{{{keys}}}", data
    return type(data).__name__, data


def items_of(data: object) -> list[dict]:
    """Items from a GA4GH collection response ({items: [...]}) or bare list."""
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [i for i in data["items"] if isinstance(i, dict)]
    if isinstance(data, list):
        return [i for i in data if isinstance(i, dict)]
    return []


# -- Probe table -------------------------------------------------------------
# Each probe: {"name", "build": fn(ctx) -> (method, path, query, body) | None,
#             "on_response": fn(ctx, data) (optional), "timeout": float (opt)}
# build() returns None to skip (reason recorded via the skip() helper below).


def _need(ctx: dict, key: str) -> bool:
    return ctx.get(key) not in (None, "")


PROBES: list[dict] = [
    # -- Resolution probes (run first; fill ctx) ------------------------------
    {
        "name": "info_ping",
        "build": lambda ctx: ("GET", "/info/ping", qparams(), None),
    },
    {
        "name": "lookup_ids",
        "build": lambda ctx: ("POST", "/lookup/id", qparams(expand=1), [GENE]),
        "on_response": lambda ctx, data: (
            data
            and data.get("transcripts")
            and ctx.update(transcript=data["transcripts"][0]["id"])
            or None
        ),
    },
    {
        "name": "map_ids_cdna",
        "build": lambda ctx: (
            "POST",
            f"/map/{SPECIES}",
            qparams(),
            {"id": [GENE], "target": "cdna"},
        ),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(cdna=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "map_ids_cds",
        "build": lambda ctx: (
            "POST",
            f"/map/{SPECIES}",
            qparams(),
            {"id": [GENE], "target": "cds"},
        ),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(cds=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "map_ids_protein",
        "build": lambda ctx: (
            "POST",
            f"/map/{SPECIES}",
            qparams(),
            {"id": [GENE], "target": "protein"},
        ),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(translation=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "phenotypes",
        "build": lambda ctx: ("GET", "/phenotype", qparams(gene=BRCA2, limit=3), None),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(phen_acc=items_of(data)[0]["accession"])
        ),
    },
    {
        "name": "ga4gh_datasets",
        "build": lambda ctx: ("GET", "/ga4gh/datasets", qparams(limit=1), None),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_ds=items_of(data)[0]["id"])
        ),
    },
    # -- Information -----------------------------------------------------------
    {
        "name": "info_rest",
        "build": lambda ctx: ("GET", "/info/rest", qparams(), None),
    },
    {
        "name": "info_software",
        "build": lambda ctx: ("GET", "/info/software", qparams(), None),
    },
    {
        "name": "info_data",
        "build": lambda ctx: ("GET", "/info/data", qparams(), None),
    },
    {
        "name": "info_species",
        "build": lambda ctx: (
            "GET",
            "/info/species",
            qparams(species=SPECIES, format="list"),
            None,
        ),
    },
    {
        "name": "info_assembly",
        "build": lambda ctx: (
            "GET",
            "/info/assembly",
            qparams(species=SPECIES, format="list"),
            None,
        ),
    },
    {
        "name": "info_divisions",
        "build": lambda ctx: ("GET", "/info/divisions", qparams(), None),
    },
    {
        "name": "info_biotypes",
        "build": lambda ctx: (
            "GET",
            "/info/biotypes",
            qparams(type="gene", species=SPECIES),
            None,
        ),
    },
    {
        "name": "info_genomes",
        "build": lambda ctx: ("GET", "/info/genomes", qparams(tax_id=TAX_ID, format="list"), None),
    },
    {
        "name": "info_populations",
        "build": lambda ctx: (
            "GET",
            "/info/populations",
            qparams(tax_id=TAX_ID, format="list"),
            None,
        ),
    },
    {
        "name": "info_compara",
        "build": lambda ctx: ("GET", "/info/compara", qparams(), None),
    },
    {
        "name": "info_analysis",
        "build": lambda ctx: ("GET", "/info/analysis", qparams(species=SPECIES), None),
    },
    {
        "name": "info_variation",
        "build": lambda ctx: ("GET", "/info/variation", qparams(), None),
    },
    {
        "name": "archive",
        "build": lambda ctx: (
            ("GET", f"/archive/id/{ctx['archive_id']}", qparams(), None)
            if _need(ctx, "archive_id")
            else None
        ),
        "skip_reason": "no archive header seen in earlier responses",
    },
    # -- Comparative genomics ----------------------------------------------------
    {
        "name": "cafes",
        "build": lambda ctx: ("GET", f"/cafe/genetree/{SPECIES}", qparams(limit=5), None),
    },
    {
        "name": "genetree",
        "build": lambda ctx: ("GET", f"/genetree/{TAX_ID}", qparams(), None),
    },
    {
        "name": "alignment",
        "build": lambda ctx: (
            "GET",
            f"/alignment/region/{SPECIES}/{CHROM}/{START}/{END}/1000/1000",
            qparams(),
            None,
        ),
    },
    {
        "name": "homology_symbol",
        "build": lambda ctx: (
            "GET",
            f"/homology/symbol/{SPECIES}/INS",
            qparams(type="one2one", target_species="pan_troglodytes"),
            None,
        ),
    },
    {
        "name": "homology_id",
        "build": lambda ctx: (
            "GET",
            f"/homology/id/{SPECIES}/{GENE}",
            qparams(type="orthologues", limit=10),
            None,
        ),
    },
    {
        "name": "xrefs_name",
        "build": lambda ctx: ("GET", f"/xrefs/name/{SPECIES}/BRCA2/uniprot", qparams(), None),
    },
    {
        "name": "xrefs_id",
        "build": lambda ctx: ("GET", f"/xrefs/id/{GENE}", qparams(), None),
    },
    # -- LD / lookup / map ---------------------------------------------------------
    {
        "name": "ld",
        "build": lambda ctx: (
            "GET",
            f"/ld/{SPECIES}/{REGION}",
            qparams(window=2000, ld="r", limit=5, offset=1),
            None,
        ),
    },
    {
        "name": "lookup_symbols",
        "build": lambda ctx: ("POST", "/lookup/symbol", qparams(species=SPECIES), ["INS", "TP53"]),
    },
    {
        "name": "map_cdna",
        "build": lambda ctx: (
            ("GET", f"/map/cdna/{ctx['cdna']}", qparams(type="exon,transcript"), None)
            if _need(ctx, "cdna")
            else None
        ),
        "skip_reason": "no cDNA resolved for GENE",
    },
    {
        "name": "map_cds",
        "build": lambda ctx: (
            ("GET", f"/map/cds/{ctx['cds']}", qparams(type="exon"), None)
            if _need(ctx, "cds")
            else None
        ),
        "skip_reason": "no CDS resolved for GENE",
    },
    {
        "name": "map_translation",
        "build": lambda ctx: (
            ("GET", f"/map/translation/{ctx['translation']}", qparams(type="exon,cds"), None)
            if _need(ctx, "translation")
            else None
        ),
        "skip_reason": "no translation resolved for GENE",
    },
    {
        "name": "map_ids_genomic",
        "build": lambda ctx: (
            "POST",
            f"/map/{SPECIES}",
            qparams(),
            {"id": [GENE], "target": "genomic"},
        ),
    },
    # -- Ontology / taxonomy --------------------------------------------------------
    {
        "name": "ontology_go",
        "build": lambda ctx: ("GET", "/ontology/go", qparams(term="apoptosis"), None),
    },
    {
        "name": "ontology_parents",
        "build": lambda ctx: ("GET", f"/ontology/parents/{GO_TERM}", qparams(), None),
    },
    {
        "name": "ontology_id",
        "build": lambda ctx: ("GET", f"/ontology/id/{GO_TERM}", qparams(), None),
    },
    {
        "name": "taxonomy_id",
        "build": lambda ctx: ("GET", f"/taxonomy/id/{TAX_ID}", qparams(), None),
    },
    {
        "name": "taxonomy_name",
        "build": lambda ctx: ("GET", f"/taxonomy/name/{SPECIES}", qparams(), None),
    },
    {
        "name": "taxonomy_common",
        "build": lambda ctx: ("GET", "/taxonomy/common/Human", qparams(), None),
    },
    {
        "name": "taxonomy_root",
        "build": lambda ctx: ("GET", "/taxonomy/root", qparams(), None),
    },
    # -- Overlap ----------------------------------------------------------------------
    {
        "name": "overlap_ids",
        "build": lambda ctx: ("POST", "/overlap/id", qparams(), [GENE]),
    },
    {
        "name": "overlap_region",
        "build": lambda ctx: (
            "GET",
            f"/overlap/region/{SPECIES}/{CHROM}/{START}/{END}",
            qparams(up=0, down=0, limit=5),
            None,
        ),
    },
    {
        "name": "overlap_translations",
        "build": lambda ctx: (
            ("POST", "/overlap/translation", qparams(), [ctx["translation"]])
            if _need(ctx, "translation")
            else None
        ),
        "skip_reason": "no translation resolved for GENE",
    },
    # -- Phenotype ----------------------------------------------------------------------
    {
        "name": "phenotype",
        "build": lambda ctx: (
            ("GET", f"/phenotype/{quote(ctx['phen_acc'], safe='')}", qparams(), None)
            if _need(ctx, "phen_acc")
            else None
        ),
        "skip_reason": "no phenotype accession resolved for BRCA2",
    },
    {
        "name": "phenotype_by_accession",
        "build": lambda ctx: (
            ("GET", f"/phenotype/accession/{quote(ctx['phen_acc'], safe='')}", qparams(), None)
            if _need(ctx, "phen_acc")
            else None
        ),
        "skip_reason": "no phenotype accession resolved for BRCA2",
    },
    {
        "name": "phenotypes_by_region",
        "build": lambda ctx: (
            "GET",
            f"/phenotype/region/{SPECIES}/{CHROM}/{START}/{END}",
            qparams(),
            None,
        ),
    },
    {
        "name": "phenotypes_by_term",
        "build": lambda ctx: ("GET", "/phenotype/term/breast%20cancer", qparams(), None),
    },
    # -- Regulation / sequence -----------------------------------------------------------
    {
        "name": "binding_matrix",
        "build": lambda ctx: (
            "GET",
            f"/species/{SPECIES}/binding_matrix",
            qparams(feature="protein_coding", type="all", limit=3, offset=1),
            None,
        ),
    },
    {
        "name": "sequences_cdna",
        "build": lambda ctx: (
            ("POST", "/sequence/id", qparams(type="cdna"), [ctx["transcript"]])
            if _need(ctx, "transcript")
            else None
        ),
        "skip_reason": "no transcript resolved for GENE",
    },
    {
        "name": "sequence_region",
        "build": lambda ctx: (
            "GET",
            f"/sequence/region/{SPECIES}/{CHROM}/{START}/{END}",
            qparams(type="dna"),
            None,
        ),
    },
    {
        "name": "transcript_haplotypes",
        "build": lambda ctx: (
            ("GET", f"/transcript/{ctx['transcript']}/haplotypes", qparams(), None)
            if _need(ctx, "transcript")
            else None
        ),
        "skip_reason": "no transcript resolved for GENE",
    },
    # -- VEP -------------------------------------------------------------------------------
    {
        "name": "vep_ids",
        "build": lambda ctx: ("POST", f"/vep/{SPECIES}/id", qparams(), [RS]),
        "timeout": 120,
    },
    {
        "name": "vep_hgvs",
        "build": lambda ctx: ("POST", f"/vep/{SPECIES}/hgvs", qparams(), [HGVS]),
        "timeout": 120,
    },
    {
        "name": "vep_regions",
        "build": lambda ctx: ("POST", f"/vep/{SPECIES}/region", qparams(), [REGION]),
        "timeout": 120,
    },
    # -- Variation ----------------------------------------------------------------------------
    {
        "name": "variations",
        "build": lambda ctx: ("GET", "/variation", qparams(spid=SPECIES, limit=3, offset=0), None),
    },
    {
        "name": "variations_pmcid",
        "build": lambda ctx: (
            "GET",
            "/variation/pmcid/PMC1234567",
            qparams(limit=3, offset=1),
            None,
        ),
    },
    {
        "name": "variations_pmid",
        "build": lambda ctx: ("GET", "/variation/pmid/1234567", qparams(limit=3, offset=1), None),
    },
    {
        "name": "variant_recoder",
        "build": lambda ctx: (
            "GET",
            "/variant_recoder",
            qparams(spid=SPECIES, limit=3, offset=0),
            None,
        ),
    },
    # -- GA4GH (dependent probes resolve IDs from the collection list probes) ----------
    {
        "name": "ga4gh_referencesets",
        "build": lambda ctx: ("GET", "/ga4gh/referencesets", qparams(limit=1), None),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_refset=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "ga4gh_references",
        "build": lambda ctx: ("GET", "/ga4gh/references", qparams(limit=1), None),
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_ref=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "ga4gh_variantsets",
        "build": lambda ctx: (
            ("GET", "/ga4gh/variantsets", qparams(dataset=ctx["ga4gh_ds"], limit=1), None)
            if _need(ctx, "ga4gh_ds")
            else None
        ),
        "skip_reason": "no GA4GH dataset available",
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_vs=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "ga4gh_variants",
        "build": lambda ctx: (
            ("GET", "/ga4gh/variants", qparams(variantset=ctx["ga4gh_vs"], limit=1), None)
            if _need(ctx, "ga4gh_vs")
            else None
        ),
        "skip_reason": "no GA4GH variantset available",
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_v=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "ga4gh_featuresets",
        "build": lambda ctx: (
            ("GET", "/ga4gh/featuresets", qparams(dataset=ctx["ga4gh_ds"], limit=1), None)
            if _need(ctx, "ga4gh_ds")
            else None
        ),
        "skip_reason": "no GA4GH dataset available",
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_fs=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "ga4gh_callsets",
        "build": lambda ctx: (
            ("GET", "/ga4gh/callsets", qparams(dataset=ctx["ga4gh_ds"], limit=1), None)
            if _need(ctx, "ga4gh_ds")
            else None
        ),
        "skip_reason": "no GA4GH dataset available",
        "on_response": lambda ctx, data: (
            items_of(data) and ctx.update(ga4gh_cs=items_of(data)[0]["id"])
        ),
    },
    {
        "name": "ga4gh_searches",
        "build": lambda ctx: (
            ("GET", "/ga4gh/searches", qparams(dataset=ctx["ga4gh_ds"], limit=1), None)
            if _need(ctx, "ga4gh_ds")
            else None
        ),
        "skip_reason": "no GA4GH dataset available",
    },
    {
        "name": "ga4gh_beacon",
        "build": lambda ctx: (
            (
                "GET",
                "/ga4gh/beacon",
                qparams(dataset=ctx["ga4gh_ds"], variant=ctx["ga4gh_v"]),
                None,
            )
            if _need(ctx, "ga4gh_ds") and _need(ctx, "ga4gh_v")
            else None
        ),
        "skip_reason": "no GA4GH dataset/variant available",
    },
    {
        "name": "ga4gh_features",
        "build": lambda ctx: (
            ("GET", "/ga4gh/features", qparams(featureset=ctx["ga4gh_fs"], limit=1), None)
            if _need(ctx, "ga4gh_fs")
            else None
        ),
        "skip_reason": "no GA4GH featureset available",
    },
]


# -- Runner --------------------------------------------------------------------


def save_response(out_dir: Path, name: str, text: str) -> tuple[str, bool]:
    """Write the raw response; returns (file name, was truncated)."""
    if len(text.encode()) > MAX_SAVE_BYTES:
        text = text.encode()[:MAX_SAVE_BYTES].decode(errors="replace") + "\n... [truncated]"
        truncated = True
    else:
        truncated = False
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(text, encoding="utf-8")
    return f"{name}.json", truncated


def shorten_sample(sample: object, limit: int = 1500) -> object:
    """Shrink a sample for the manifest without ever emitting invalid JSON."""
    if sample is None:
        return None
    text = json.dumps(sample, default=str)
    if len(text) <= limit:
        return sample
    if isinstance(sample, list) and sample:
        for n in range(len(sample) - 1, 0, -1):
            text = json.dumps(sample[:n], default=str)
            if len(text) <= limit:
                return sample[:n]
    return text[: limit - 3] + "..."


async def run_probe(
    session: aiohttp.ClientSession,
    probe: dict,
    ctx: dict,
    args: argparse.Namespace,
    out_dir: Path,
) -> Result:
    spec = probe["build"](ctx)
    if spec is None:
        return Result(
            name=probe["name"],
            method="-",
            path="-",
            skipped=probe.get("skip_reason", "skipped"),
        )
    method, path, query, body = spec
    res = Result(name=probe["name"], method=method, path=path, query=query, body=body)
    timeout = probe.get("timeout", args.timeout)
    t0 = time.monotonic()
    status, text, headers, _ = await fetch(
        session, args.base_url, method, path, query, body, timeout
    )
    res.elapsed_ms = int((time.monotonic() - t0) * 1000)
    res.status = status
    res.bytes = len(text.encode())
    res.ok = 200 <= status < 300

    # Harvest the archive ID from any response header.
    for key, value in headers.items():
        if "archive" in key:
            ctx["archive_id"] = value
            break

    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = None

    if res.ok:
        res.shape, res.sample = summarize(data) if data is not None else ("empty", None)
        res.file, res.truncated = save_response(out_dir, res.name, text)
        on_response = probe.get("on_response")
        if on_response and data is not None:
            try:
                on_response(ctx, data)
            except (KeyError, IndexError, TypeError) as exc:
                print(f"  ! {res.name}: on_response failed: {exc!r}", file=sys.stderr)
    else:
        snippet = text[:200].replace("\n", " ")
        res.error = snippet
        res.file, res.truncated = save_response(out_dir, res.name, text)
    return res


def write_manifest(out_dir: Path, base_url: str, results: list[Result]) -> None:
    entries = []
    for res in results:
        entry: dict[str, object] = {
            "name": res.name,
            "method": res.method,
            "path": res.path,
            "query": res.query or None,
            "body": res.body,
            "status": res.status,
            "ok": res.ok,
            "bytes": res.bytes,
            "elapsed_ms": res.elapsed_ms,
            "shape": res.shape or None,
            "sample": shorten_sample(res.sample),
            "error": res.error or None,
            "skipped": res.skipped or None,
            "truncated": res.truncated,
            "file": res.file or None,
        }
        entries.append(entry)
    manifest = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "base_url": base_url,
        "results": entries,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8"
    )


async def main(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    ctx: dict = {}
    results: list[Result] = [
        Result(
            name="INFO",
            method="-",
            path="-",
            skipped=f"probe {args.base_url}; gene {GENE}; region {REGION}",
        )
    ]
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        for probe in PROBES:
            if args.no_ga4gh and probe["name"].startswith("ga4gh"):
                results.append(
                    Result(name=probe["name"], method="-", path="-", skipped="--no-ga4gh")
                )
                continue
            if args.only and not re.search(args.only, probe["name"]):
                continue
            res = await run_probe(session, probe, ctx, args, out_dir)
            results.append(res)
            status = res.skipped or f"{res.status} {res.shape or res.error}"
            print(
                f"{res.name:<26} {res.method:<4} {res.path:<52} {status:<40} {res.elapsed_ms} ms"
            )
            await asyncio.sleep(args.sleep)

    write_manifest(out_dir, args.base_url, results)
    n_ok = sum(1 for r in results if r.ok)
    n_skip = sum(1 for r in results if r.skipped)
    n_fail = sum(1 for r in results if not r.ok and not r.skipped and r.name != "INFO")
    print(f"\n{out_dir}\n  ok: {n_ok}  skipped: {n_skip}  failed: {n_fail}")
    return 0 if n_fail == 0 else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="https://rest.ensembl.org")
    parser.add_argument(
        "--out-dir", default=str(repo / "docs/adapters/proteins/ensembl_rest_responses")
    )
    parser.add_argument("--only", default="", help="run only probes whose name matches this regex")
    parser.add_argument("--sleep", type=float, default=0.5, help="pause between probes (s)")
    parser.add_argument("--timeout", type=float, default=60, help="per-request timeout (s)")
    parser.add_argument("--no-ga4gh", action="store_true", help="skip all GA4GH probes")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
