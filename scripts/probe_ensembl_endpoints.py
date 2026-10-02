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
GENE = "ENSG00000254647"  # INS (11:2159779-2161209; ENSG00000133056 is PIK3C2B)
BRCA2 = "ENSG00000139618"
TAX_ID = 9606
CHROM, START, END = "11", 2159779, 2161209
REGION = f"{CHROM}:{START}-{END}"
SINGLE = f"{CHROM}:{START}-{START}"  # single-base region (VEP region / x-assembly map)
REF, ALT = "G", "A"  # reference base at START is G on the forward strand
RS = "rs1801270"  # CDKN1A S31R; has ClinVar + GWAS phenotypes
PMID = "33230300"  # GWAS catalog study on rs1801270 (PMC7610439)
PMCID = "PMC7610439"
HGVS = f"NC_000011.10:g.{START}{REF}>{ALT}"
GO_TERM = "GO:0006915"  # apoptotic process
BINDING_MATRIX_ID = "ENSPFM0001"  # regulation binding-matrix stable ID

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
    """Items from a GA4GH collection response or bare list.

    GA4GH search responses wrap the payload under a resource-specific key
    (``{"nextPageToken": ..., "datasets": [...]}``), not always ``items`` — so
    fall back to the first list-of-dicts value in the mapping.
    """
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return [i for i in data["items"] if isinstance(i, dict)]
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return [i for i in value if isinstance(i, dict)]
        return []
    if isinstance(data, list):
        return [i for i in data if isinstance(i, dict)]
    return []


def first_field(data: object, key: str) -> object:
    """First truthy value of ``key`` across response items (list or {items: [...]})."""
    for item in items_of(data):
        if item.get(key):
            return item[key]
    return None


def capture_callset_id(ctx: dict, data: object) -> None:
    """Harvest a callset id from a GA4GH variant's embedded ``calls``.

    15.12 has no ``POST /ga4gh/callsets/search``, so the only way to reach
    ``GET /ga4gh/callsets/:id`` is via the calls arrays inside variant
    responses.
    """
    for item in items_of(data):
        calls = item.get("calls") or item.get("call") or []
        if isinstance(calls, dict):
            calls = [calls]
        for call in calls:
            if isinstance(call, dict):
                cs_id = call.get("callSetId") or call.get("callsetId") or call.get("id")
                if cs_id:
                    ctx["ga4gh_cs"] = cs_id
                    return


# -- Probe table -------------------------------------------------------------
# Each probe: {"name", "build": fn(ctx) -> (method, path, query, body) | None,
#             "on_response": fn(ctx, data) (optional), "timeout": float (opt)}
# build() returns None to skip (reason recorded via the skip() helper below).


def _need(ctx: dict, key: str) -> bool:
    return ctx.get(key) not in (None, "")


def _harvest_lookup(ctx: dict, data: object) -> None:
    # expand=1 puts children under a capitalised "Transcript" key. Prefer a
    # transcript that actually has a translation (the first child of a gene is
    # often a non-coding isoform).
    children = (data or {}).get("Transcript") or (data or {}).get("transcripts") or []
    if not children:
        return
    chosen = next(
        (tx for tx in children if (tx.get("translation") or {}).get("id")),
        children[0],
    )
    ctx.update(
        transcript=chosen["id"],
        translation=(chosen.get("translation") or {}).get("id"),
    )


def _harvest_phen_acc(ctx: dict, data: object) -> None:
    for item in items_of(data):
        accessions = item.get("ontology_accessions") or []
        if accessions:
            # Last = most specific term (e.g. Orphanet:...); a broad root like
            # EFO:0000326 makes /phenotype/accession take >120 s.
            ctx["phen_acc"] = accessions[-1]
            return


PROBES: list[dict] = [
    # -- Resolution probes (marked "core"; always run, even with --only) --------
    {
        "name": "info_ping",
        "core": True,
        "build": lambda ctx: ("GET", "/info/ping", qparams(), None),
    },
    {
        "name": "lookup_id",
        "core": True,
        "build": lambda ctx: ("GET", f"/lookup/id/{GENE}", qparams(expand=1), None),
        "on_response": _harvest_lookup,
    },
    {
        # Body must be {"ids": [...]}; a bare JSON array 500s server-side.
        "name": "lookup_ids_post",
        "core": True,
        "build": lambda ctx: ("POST", "/lookup/id", qparams(expand=1), {"ids": [GENE]}),
    },
    {
        "name": "phenotype_gene",
        "core": True,
        "build": lambda ctx: (
            "GET",
            f"/phenotype/gene/{SPECIES}/BRCA2",
            qparams(limit=3),
            None,
        ),
        "on_response": _harvest_phen_acc,
    },
    {
        "name": "ga4gh_datasets",
        "core": True,
        "build": lambda ctx: ("POST", "/ga4gh/datasets/search", qparams(), {"pageSize": 1}),
        "on_response": lambda ctx, data: (
            first_field(data, "id") and ctx.update(ga4gh_ds=first_field(data, "id"))
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
        "build": lambda ctx: ("GET", f"/info/assembly/{SPECIES}", qparams(bands=0), None),
    },
    {
        "name": "info_divisions",
        "build": lambda ctx: ("GET", "/info/divisions", qparams(), None),
    },
    {
        "name": "info_biotypes",
        "build": lambda ctx: ("GET", f"/info/biotypes/{SPECIES}", qparams(type="gene"), None),
    },
    {
        "name": "info_genomes",
        "build": lambda ctx: ("GET", f"/info/genomes/{SPECIES}", qparams(), None),
    },
    {
        # Populations moved under /info/variation/populations; LD-capable ones
        # feed the /ld probe via ctx["ld_pop"].
        "name": "info_populations",
        "build": lambda ctx: (
            "GET",
            f"/info/variation/populations/{SPECIES}",
            qparams(filter="LD"),
            None,
        ),
        "on_response": lambda ctx, data: (
            first_field(data, "name") and ctx.update(ld_pop=first_field(data, "name"))
        ),
    },
    {
        "name": "info_compara_methods",
        "build": lambda ctx: ("GET", "/info/compara/methods", qparams(), None),
        "on_response": lambda ctx, data: (
            first_field(data, "name") and ctx.update(compara_method=first_field(data, "name"))
        ),
    },
    {
        "name": "info_compara_species_sets",
        "build": lambda ctx: (
            ("GET", f"/info/compara/species_sets/{ctx['compara_method']}", qparams(), None)
            if _need(ctx, "compara_method")
            else None
        ),
        "skip_reason": "no compara method resolved",
    },
    {
        "name": "info_analysis",
        "build": lambda ctx: ("GET", f"/info/analysis/{SPECIES}", qparams(last=1), None),
    },
    {
        # No filter: 'clinical' is not a valid variation source for human (400 in 15.12).
        "name": "info_variation",
        "build": lambda ctx: ("GET", f"/info/variation/{SPECIES}", qparams(), None),
    },
    {
        "name": "info_eg_version",
        "build": lambda ctx: ("GET", "/info/eg_version", qparams(), None),
    },
    {
        "name": "info_external_dbs",
        "build": lambda ctx: ("GET", f"/info/external_dbs/{SPECIES}", qparams(), None),
    },
    {
        "name": "info_consequence_types",
        "build": lambda ctx: ("GET", "/info/variation/consequence_types", qparams(), None),
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
        "build": lambda ctx: (
            "GET",
            f"/cafe/genetree/member/id/{SPECIES}/{GENE}",
            qparams(),
            None,
        ),
    },
    {
        "name": "genetree",
        "build": lambda ctx: (
            "GET",
            f"/genetree/member/id/{SPECIES}/{GENE}",
            qparams(),
            None,
        ),
    },
    {
        "name": "alignment",
        "build": lambda ctx: (
            "GET",
            f"/alignment/region/{SPECIES}/{REGION}",
            qparams(species_set_group="mammals"),
            None,
        ),
        "timeout": 120,
    },
    {
        "name": "homology_symbol",
        "build": lambda ctx: (
            "GET",
            f"/homology/symbol/{SPECIES}/INS",
            qparams(type="orthologues", target_species="pan_troglodytes"),
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
        "build": lambda ctx: (
            "GET",
            f"/xrefs/name/{SPECIES}/BRCA2",
            qparams(dbname="uniprot"),
            None,
        ),
    },
    {
        "name": "xrefs_id",
        "build": lambda ctx: ("GET", f"/xrefs/id/{GENE}", qparams(), None),
    },
    # -- LD / lookup / map ---------------------------------------------------------
    {
        "name": "ld_region",
        "build": lambda ctx: (
            (
                "GET",
                f"/ld/{SPECIES}/region/{CHROM}:{START}..{END}/{quote(ctx['ld_pop'], safe='')}",
                qparams(r2=0.7),
                None,
            )
            if _need(ctx, "ld_pop")
            else None
        ),
        "skip_reason": "no LD population resolved",
        "timeout": 120,
    },
    {
        "name": "ld_id",
        "build": lambda ctx: (
            (
                "GET",
                f"/ld/{SPECIES}/{RS}/{quote(ctx['ld_pop'], safe='')}",
                qparams(window_size=500, r2=0.9),
                None,
            )
            if _need(ctx, "ld_pop")
            else None
        ),
        "skip_reason": "no LD population resolved",
        "timeout": 120,
    },
    {
        "name": "ld_pairwise",
        "build": lambda ctx: (
            (
                "GET",
                f"/ld/{SPECIES}/pairwise/{RS}/rs1059234",
                qparams(population_name=ctx["ld_pop"]),
                None,
            )
            if _need(ctx, "ld_pop")
            else None
        ),
        "skip_reason": "no LD population resolved",
        "timeout": 120,
    },
    {
        "name": "lookup_symbols",
        "build": lambda ctx: (
            "POST",
            f"/lookup/symbol/{SPECIES}",
            qparams(),
            {"symbols": ["INS", "TP53"]},
        ),
    },
    {
        "name": "map_cdna",
        "build": lambda ctx: (
            ("GET", f"/map/cdna/{ctx['transcript']}/100..200", qparams(), None)
            if _need(ctx, "transcript")
            else None
        ),
        "skip_reason": "no transcript resolved for GENE",
    },
    {
        "name": "map_cds",
        "build": lambda ctx: (
            ("GET", f"/map/cds/{ctx['transcript']}/90..150", qparams(), None)
            if _need(ctx, "transcript")
            else None
        ),
        "skip_reason": "no transcript resolved for GENE",
    },
    {
        "name": "map_translation",
        "build": lambda ctx: (
            ("GET", f"/map/translation/{ctx['translation']}/5..100", qparams(), None)
            if _need(ctx, "translation")
            else None
        ),
        "skip_reason": "no translation resolved for GENE",
    },
    {
        "name": "map_assemblies",
        "build": lambda ctx: (
            "GET",
            f"/map/{SPECIES}/GRCh38/{SINGLE}/GRCh37",
            qparams(),
            None,
        ),
    },
    # -- Ontology / taxonomy --------------------------------------------------------
    {
        "name": "ontology_name",
        "build": lambda ctx: ("GET", "/ontology/name/apoptosis", qparams(), None),
    },
    {
        "name": "ontology_ancestors",
        "build": lambda ctx: ("GET", f"/ontology/ancestors/{GO_TERM}", qparams(), None),
    },
    {
        "name": "ontology_descendants",
        "build": lambda ctx: ("GET", f"/ontology/descendants/{GO_TERM}", qparams(), None),
    },
    {
        "name": "ontology_chart",
        "build": lambda ctx: (
            "GET",
            f"/ontology/ancestors/chart/{GO_TERM}",
            qparams(),
            None,
        ),
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
        "name": "taxonomy_classification",
        "build": lambda ctx: ("GET", f"/taxonomy/classification/{TAX_ID}", qparams(), None),
    },
    # -- Overlap ----------------------------------------------------------------------
    {
        "name": "overlap_id",
        "build": lambda ctx: (
            "GET",
            f"/overlap/id/{GENE}",
            qparams(feature="variation", limit=5),
            None,
        ),
    },
    {
        "name": "overlap_region",
        "build": lambda ctx: (
            "GET",
            f"/overlap/region/{SPECIES}/{REGION}",
            qparams(feature="gene", limit=5),
            None,
        ),
    },
    {
        "name": "overlap_translation",
        "build": lambda ctx: (
            ("GET", f"/overlap/translation/{ctx['translation']}", qparams(), None)
            if _need(ctx, "translation")
            else None
        ),
        "skip_reason": "no translation resolved for GENE",
    },
    # -- Phenotype ----------------------------------------------------------------------
    {
        "name": "phenotype_accession",
        "build": lambda ctx: (
            (
                "GET",
                f"/phenotype/accession/{SPECIES}/{quote(ctx['phen_acc'], safe='')}",
                qparams(limit=5),
                None,
            )
            if _need(ctx, "phen_acc")
            else None
        ),
        "skip_reason": "no phenotype accession resolved for BRCA2",
    },
    {
        "name": "phenotypes_by_region",
        "build": lambda ctx: (
            "GET",
            f"/phenotype/region/{SPECIES}/{REGION}",
            qparams(limit=5),
            None,
        ),
    },
    {
        "name": "phenotypes_by_term",
        "build": lambda ctx: (
            "GET",
            f"/phenotype/term/{SPECIES}/breast%20cancer",
            qparams(limit=5),
            None,
        ),
        # Heavy full-text term query: observed >120 s on the live server.
        "timeout": 240,
    },
    # -- Regulation / sequence -----------------------------------------------------------
    {
        # Stable ID guessed from regulation build; verify on re-run.
        "name": "binding_matrix",
        "build": lambda ctx: (
            "GET",
            f"/species/{SPECIES}/binding_matrix/{BINDING_MATRIX_ID}",
            qparams(),
            None,
        ),
    },
    {
        "name": "sequences_cdna",
        "build": lambda ctx: (
            ("POST", "/sequence/id", qparams(type="cdna"), {"ids": [ctx["transcript"]]})
            if _need(ctx, "transcript")
            else None
        ),
        "skip_reason": "no transcript resolved for GENE",
    },
    {
        "name": "sequence_region",
        "build": lambda ctx: (
            "GET",
            f"/sequence/region/{SPECIES}/{REGION}",
            qparams(type="dna"),
            None,
        ),
    },
    {
        "name": "transcript_haplotypes",
        "build": lambda ctx: (
            ("GET", f"/transcript_haplotypes/{SPECIES}/{ctx['transcript']}", qparams(), None)
            if _need(ctx, "transcript")
            else None
        ),
        "skip_reason": "no transcript resolved for GENE",
    },
    # -- VEP -------------------------------------------------------------------------------
    {
        "name": "vep_id",
        "build": lambda ctx: ("GET", f"/vep/{SPECIES}/id/{RS}", qparams(), None),
        "timeout": 120,
    },
    {
        "name": "vep_hgvs",
        "build": lambda ctx: (
            "GET",
            f"/vep/{SPECIES}/hgvs/{quote(HGVS, safe='')}",
            qparams(),
            None,
        ),
        "timeout": 120,
    },
    {
        "name": "vep_region",
        "build": lambda ctx: (
            "GET",
            f"/vep/{SPECIES}/region/{SINGLE}/{ALT}",
            qparams(),
            None,
        ),
        "timeout": 120,
    },
    {
        "name": "vep_hgvs_post",
        "build": lambda ctx: (
            "POST",
            f"/vep/{SPECIES}/hgvs",
            qparams(),
            {"hgvs_notations": [HGVS]},
        ),
        "timeout": 120,
    },
    {
        "name": "vep_id_post",
        "build": lambda ctx: ("POST", f"/vep/{SPECIES}/id", qparams(), {"ids": [RS]}),
        "timeout": 120,
    },
    {
        "name": "vep_region_post",
        "build": lambda ctx: (
            "POST",
            f"/vep/{SPECIES}/region",
            qparams(),
            {"variants": [f"{CHROM} {START} {START} {REF}/{ALT} 1"]},
        ),
        "timeout": 120,
    },
    # -- Variation ----------------------------------------------------------------------------
    # Bare GET /variation was removed in 15.12; ids resolve via /variation/:species/:id.
    {
        "name": "variation_id",
        "build": lambda ctx: (
            "GET",
            f"/variation/{SPECIES}/{RS}",
            qparams(pops=1),
            None,
        ),
    },
    {
        "name": "variations_pmcid",
        "build": lambda ctx: (
            "GET",
            f"/variation/{SPECIES}/pmcid/{PMCID}",
            qparams(limit=3, offset=1),
            None,
        ),
        "timeout": 240,
    },
    {
        "name": "variations_pmid",
        "build": lambda ctx: (
            "GET",
            f"/variation/{SPECIES}/pmid/{PMID}",
            qparams(limit=3, offset=1),
            None,
        ),
        "timeout": 240,
    },
    {
        "name": "variant_recoder",
        "build": lambda ctx: (
            "GET",
            f"/variant_recoder/{SPECIES}/{RS}",
            qparams(),
            None,
        ),
    },
    {
        # 15.12 batch forms: POST with {"ids": [...]} against the species path.
        "name": "variations_batch_post",
        "build": lambda ctx: (
            "POST",
            f"/variation/{SPECIES}",
            qparams(),
            {"ids": [RS]},
        ),
    },
    {
        "name": "variant_recoder_batch_post",
        "build": lambda ctx: (
            "POST",
            f"/variant_recoder/{SPECIES}",
            qparams(),
            {"ids": [RS]},
        ),
    },
    # -- GA4GH ---------------------------------------------------------------------
    # Since 15.12 collections are reached via POST /ga4gh/<resource>/search with the
    # parent id in the JSON body; single resources answer to GET /ga4gh/<resource>/:id.
    # Callsets are the exception: there is NO callsets/search, their ids come from the
    # "calls" arrays embedded in variant responses (see capture_callset_id). Searches
    # need their parent/region keys: references -> referenceSetId, variants ->
    # variantSetId + referenceName/start/end, features -> featureSetId + region,
    # variantannotations -> variantAnnotationSetId + region.
    {
        "name": "ga4gh_references",
        "build": lambda ctx: (
            "POST",
            "/ga4gh/references/search",
            qparams(),
            {"referenceSetId": "GRCh38", "pageSize": 1},
        ),
        "timeout": 120,
        "on_response": lambda ctx, data: (
            first_field(data, "id") and ctx.update(ga4gh_ref=first_field(data, "id"))
        ),
    },
    {
        "name": "ga4gh_get_reference",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/references/{ctx['ga4gh_ref']}", qparams(), None)
            if _need(ctx, "ga4gh_ref")
            else None
        ),
        "skip_reason": "no GA4GH reference available",
    },
    {
        "name": "ga4gh_get_dataset",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/datasets/{ctx['ga4gh_ds']}", qparams(), None)
            if _need(ctx, "ga4gh_ds")
            else None
        ),
        "skip_reason": "no GA4GH dataset available",
    },
    {
        "name": "ga4gh_variantsets",
        "build": lambda ctx: (
            (
                "POST",
                "/ga4gh/variantsets/search",
                qparams(),
                {"datasetId": ctx["ga4gh_ds"], "pageSize": 1},
            )
            if _need(ctx, "ga4gh_ds")
            else None
        ),
        "skip_reason": "no GA4GH dataset available",
        "timeout": 120,
        "on_response": lambda ctx, data: (
            first_field(data, "id") and ctx.update(ga4gh_vs=first_field(data, "id"))
        ),
    },
    {
        "name": "ga4gh_variants",
        "build": lambda ctx: (
            (
                "POST",
                "/ga4gh/variants/search",
                qparams(),
                {
                    "variantSetId": ctx["ga4gh_vs"],
                    "referenceName": CHROM,
                    "start": START,
                    "end": END,
                    "pageSize": 1,
                },
            )
            if _need(ctx, "ga4gh_vs")
            else None
        ),
        "skip_reason": "no GA4GH variantset available",
        "timeout": 120,
        "on_response": lambda ctx, data: (
            first_field(data, "id") and ctx.update(ga4gh_v=first_field(data, "id")),
            capture_callset_id(ctx, data),
        ),
    },
    {
        # Featuresets live under the literal dataset id "Ensembl" (not the 1000
        # Genomes id datasets/search returns, which gives a 400).
        "name": "ga4gh_featuresets",
        "build": lambda ctx: (
            "POST",
            "/ga4gh/featuresets/search",
            qparams(),
            {"datasetId": "Ensembl", "pageSize": 1},
        ),
        "timeout": 120,
        "on_response": lambda ctx, data: (
            first_field(data, "id") and ctx.update(ga4gh_fs=first_field(data, "id"))
        ),
    },
    {
        # Slow (~50 s for a 1.4 kb window); needs the singular featureSetId.
        "name": "ga4gh_features",
        "build": lambda ctx: (
            (
                "POST",
                "/ga4gh/features/search",
                qparams(),
                {
                    "featureSetId": ctx["ga4gh_fs"],
                    "referenceName": CHROM,
                    "start": START,
                    "end": END,
                    "pageSize": 1,
                },
            )
            if _need(ctx, "ga4gh_fs")
            else None
        ),
        "skip_reason": "no GA4GH featureset available",
        "timeout": 180,
        "on_response": lambda ctx, data: (
            first_field(data, "id") and ctx.update(ga4gh_f=first_field(data, "id"))
        ),
    },
    {
        "name": "ga4gh_get_variantset",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/variantsets/{ctx['ga4gh_vs']}", qparams(), None)
            if _need(ctx, "ga4gh_vs")
            else None
        ),
        "skip_reason": "no GA4GH variantset available",
    },
    {
        "name": "ga4gh_get_variant",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/variants/{ctx['ga4gh_v']}", qparams(), None)
            if _need(ctx, "ga4gh_v")
            else None
        ),
        "skip_reason": "no GA4GH variant available",
    },
    {
        "name": "ga4gh_get_featureset",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/featuresets/{ctx['ga4gh_fs']}", qparams(), None)
            if _need(ctx, "ga4gh_fs")
            else None
        ),
        "skip_reason": "no GA4GH featureset available",
    },
    {
        "name": "ga4gh_get_feature",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/features/{ctx['ga4gh_f']}", qparams(), None)
            if _need(ctx, "ga4gh_f")
            else None
        ),
        "skip_reason": "no GA4GH feature available",
    },
    {
        "name": "ga4gh_get_callset",
        "build": lambda ctx: (
            ("GET", f"/ga4gh/callsets/{ctx['ga4gh_cs']}", qparams(), None)
            if _need(ctx, "ga4gh_cs")
            else None
        ),
        "skip_reason": "no callset id harvested from the variant response",
    },
    {
        "name": "ga4gh_variantannotations",
        "build": lambda ctx: (
            "POST",
            "/ga4gh/variantannotations/search",
            qparams(),
            {
                "variantAnnotationSetId": "Ensembl",
                "referenceName": CHROM,
                "start": START,
                "end": END,
                "pageSize": 1,
            },
        ),
        "timeout": 120,
    },
    {
        "name": "ga4gh_beacon",
        "build": lambda ctx: ("GET", "/ga4gh/beacon", qparams(), None),
    },
    {
        # Beacon v2. Omit datasetIds: the server rejects every id it advertises
        # ("Invalid datasetId"), and a JSON list is stringified to ARRAY(0x...).
        "name": "ga4gh_beacon_query",
        "build": lambda ctx: (
            "POST",
            "/ga4gh/beacon/query",
            qparams(),
            {
                "referenceName": CHROM,
                "start": START - 1,
                "referenceBases": REF,
                "alternateBases": ALT,
                "assemblyId": "GRCh38",
            },
        ),
        "timeout": 120,
    },
    {
        "name": "ga4gh_beacon_query_get",
        "build": lambda ctx: (
            "GET",
            "/ga4gh/beacon/query",
            qparams(
                referenceName=CHROM,
                start=START - 1,
                referenceBases=REF,
                alternateBases=ALT,
                assemblyId="GRCh38",
            ),
            None,
        ),
        "timeout": 120,
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
            if args.only and not probe.get("core") and not re.search(args.only, probe["name"]):
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
