#!/usr/bin/env python3
"""Render the JSON written by ``harvest_source_samples.py`` as a docs page.

Usage:
    poetry run python scripts/build_data_coverage_doc.py samples.json \
        --date 2026-10-09 --out docs/guides/data-coverage.md

The page is generated: edit this script (or the hand-written intro in
``INTRO``), not the output.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _source_taxonomy import TAXONOMY  # noqa: E402

from knowledge_lookup import KnowledgeSource  # noqa: E402
from knowledge_lookup.adapters import _ADAPTER_SPECS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DOCS = ROOT / "docs" / "adapters"

INTRO = """\
# What each source returns

This page shows **what works and what data comes back** from every knowledge source, measured
against the live APIs on {date}. For each source the harvest script ran one realistic query,
fetched the first hit, and then asked for its relationships and cross-references. Nothing on
this page is copied from vendor documentation: the numbers, identifiers and field names are what
the library actually received.

{summary}

Looking for the right source for a question? Start with [Which source for which question](choosing-sources.md); this page is the evidence behind it.

## Things the harvest showed

- **Search is lexical, so the first hit is not always the canonical entity.** ChEBI answers
  "aspirin" with *aspirin trelamine*, UniProt answers "BRCA1" with a plant protein, ClinVar answers
  with a variant in a different gene. Look at all hits, or fetch by exact identifier.
- **Identifier formats differ per source** (`HP:0001250`, `ENSG00000012048`, `PMID:42826492`,
  `snomed|84229001`, `1191`). Use `get_mappings()` or the [CURIE guide](curie-management.md) to
  move between them.
- **Some sources are dataset-backed** (HPOA, SIDER, OFFSIDES, CTD, GenCC, ClinGen). They answer
  from a local copy and download nothing unless you opt in with `<NAME>_DOWNLOAD=1`.
- **Edges and cross-references vary a lot.** Ontologies with rich graphs (NCI EVS: 134 edges, UMLS:
  100) and association databases (HPOA, Orphanet, OpenCitations, NIH RePORTER) return many typed
  edges; plain lookup services (HGNC, UniProt, PubChem, Wikidata) return none, only the record.

## How to read the tables

Every adapter turns its upstream response into the same `UnifiedConcept` model, so the columns
are the same for all sources.

| Column | Meaning |
|---|---|
| **Query** | the smoke-test query (the one `knowledge-lookup check` uses) |
| **Hits** | results returned by `search_concepts(query, limit=5)` and the time it took |
| **Details** | time for `get_concept_details()` on the first hit; ✓ when a record came back |
| **Edges** | `get_relationships()`: typed links to other records (parents, genes, drugs, papers ...) |
| **Maps** | `get_mappings()`: cross-references to identifiers in other vocabularies |
| **Filled fields** | which `UnifiedConcept` fields the details call populated, with item counts |

A `0` in Edges or Maps is not an error: many sources simply do not offer that kind of data
(a literature index has no cross-references, a gene nomenclature has no parent classes). The
tables for each category show what you can expect, and the linked adapter page lists the exact
parameters.

## Try it yourself

```bash
knowledge-lookup check HPO                        # search -> details -> relationships for one source
knowledge-lookup check all                        # every source (several minutes)
poetry run python scripts/harvest_source_samples.py --out samples.json   # the data behind this page
```

```python
import asyncio
from knowledge_lookup.adapters import HPOAdapter
from knowledge_lookup import LookupConfig

async def main():
    async with HPOAdapter(LookupConfig()) as hpo:
        hit = (await hpo.search_concepts("fatigue", limit=3))[0]
        concept = await hpo.get_concept_details(hit.primary_id)
        print(concept.primary_id, concept.primary_label, concept.synonyms[:3])
        for edge in (await hpo.get_relationships(hit.primary_id))[:3]:
            print(edge["relation_label"], edge["related_id"], edge["related_name"])
        for m in (await hpo.get_mappings(hit.primary_id))[:3]:
            print(m["toSource"], m["toId"])

asyncio.run(main())
```

Relationship dicts always carry `relation_label`, `related_id`, `related_name` and `source`;
mapping dicts carry `fromId`, `toId`, `fromSource`, `toSource`, `mappingType` and `confidence`.
Anything else a source offers (scores, evidence, counts) is an extra key on the same dict, and the
raw upstream record stays available as `concept.source_data`.
"""


def esc(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def doc_path(src_name: str) -> tuple[str, str] | None:
    """Return (category, relative link) of the adapter docs page, if one exists."""
    spec = _ADAPTER_SPECS.get(KnowledgeSource[src_name])
    if not spec:
        return None
    hits = list(ADAPTER_DOCS.glob(f"*/{spec[0]}.md"))
    if not hits:
        return None
    return hits[0].parent.name, f"../adapters/{hits[0].parent.name}/{hits[0].name}"


def name_of(row: dict) -> str:
    """Display name: the docs page title minus " adapter", else the enum value."""
    spec = _ADAPTER_SPECS.get(KnowledgeSource[row["source"]])
    if spec:
        for page in ADAPTER_DOCS.glob(f"*/{spec[0]}.md"):
            for line in page.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].removesuffix(" adapter").strip()
    return KnowledgeSource[row["source"]].value


def fmt_s(x: float | None) -> str:
    return "-" if x is None else f"{x:.1f} s"


def filled(row: dict) -> str:
    f = row.get("details", {}).get("filled", {})
    return ", ".join(f"{k} {v}" for k, v in f.items()) or "-"


# Failure causes found when the page was generated; update when rerunning.
KNOWN_FAILURES = {
    "CHEMBL": "ChEMBL's API answered HTTP 500 while the client loaded its schema (upstream outage)",
    "SNOMEDCT": "the public Snowstorm browser host was unreachable (time-out)",
    "EUTILS": "Python `requests` waited ~100 s on IPv6 on the test machine; works over IPv4",
}


def build(rows: list[dict], date: str) -> str:
    rows = [r for r in rows if KnowledgeSource[r["source"]] in _ADAPTER_SPECS]
    ok = [r for r in rows if r["status"] == "ok"]
    skipped = [r for r in rows if r["status"] == "skipped"]
    bad = [r for r in rows if r["status"] not in ("ok", "skipped")]
    with_edges = sum(1 for r in ok if r["relationships"]["count"])
    with_maps = sum(1 for r in ok if r["mappings"]["count"])
    summary = (
        f"**{len(rows)} sources** are registered. **{len(ok)} answered end to end** "
        f"(search, details), {with_edges} of them also returned relationships and {with_maps} "
        f"cross-references. {len(skipped)} were not tested because they need a key, a local file "
        f"or an opt-in download ([listed below](#not-tested-here)); {len(bad)} failed or returned "
        f"nothing ([listed below](#did-not-answer))."
    )
    out = [INTRO.format(date=date, summary=summary)]

    ok_by_name = {r["source"]: r for r in ok}
    for _key, title, blurb, members in TAXONOMY:
        group = [ok_by_name[n] for n in members.split() if n in ok_by_name]
        if not group:
            continue
        out.append(f"\n## {title}\n\n{blurb}\n")
        out.append(
            "| Source | Query | Hits | Details | Edges | Maps | Filled fields |\n"
            "|---|---|---|---|---|---|---|"
        )
        for r in group:
            dp = doc_path(r["source"])
            link = f"[{esc(name_of(r))}]({dp[1]})" if dp else esc(name_of(r))
            out.append(
                f"| {link} | `{esc(r['query'])}` | {r['search']['count']} "
                f"({fmt_s(r['search']['seconds'])}) | {fmt_s(r['details']['seconds'])} ✓ | "
                f"{r['relationships']['count']} | {r['mappings']['count']} | {esc(filled(r))} |"
            )
        out.append("\n**What comes back**\n")
        out.append(
            "| Source | First hit | Edge types | Mapping targets | Raw upstream fields |\n"
            "|---|---|---|---|---|"
        )
        for r in group:
            top = r["search"]["top"][0]
            edges = ", ".join(f"`{esc(p)}` ×{n}" for p, n in r["relationships"]["predicates"][:4])
            maps = ", ".join(f"{esc(t)} ×{n}" for t, n in r["mappings"]["targets"][:5])
            keys = ", ".join(f"`{esc(k)}`" for k in r["details"].get("raw_keys", [])[:8])
            out.append(
                f"| {esc(name_of(r))} | `{esc(top['id'])}` {esc(top['label'])} "
                f"({esc(top['type'])}) | {edges or '-'} | {maps or '-'} | {keys or '-'} |"
            )

    if skipped:
        out.append("\n## Not tested here\n")
        out.append(
            "These adapters are real, but they cannot run without something only you can "
            "provide (a licence key, a local file, or an explicit opt-in to a download).\n"
        )
        out.append("| Source | To enable |\n|---|---|")
        for r in skipped:
            out.append(f"| {esc(name_of(r))} | {esc(r.get('needs', ''))} |")

    if bad:
        out.append("\n## Did not answer\n")
        out.append(
            "These returned no usable result during the harvest. The cause is listed; "
            "most are upstream or network conditions rather than library bugs.\n"
        )
        out.append("| Source | Status | Detail |\n|---|---|---|")
        for r in bad:
            s = r.get("search", {})
            detail = (
                KNOWN_FAILURES.get(r["source"]) or s.get("error") or "search returned no results"
            )
            out.append(f"| {esc(name_of(r))} | {r['status']} | {esc(detail)} |")

    out.append(
        f"\n---\n*Generated {date} by `scripts/build_data_coverage_doc.py` from "
        "`scripts/harvest_source_samples.py`. Latencies come from one machine and one run; "
        "treat them as orders of magnitude.*\n"
    )
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples", type=Path)
    ap.add_argument("--date", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    rows = json.loads(args.samples.read_text(encoding="utf-8"))
    args.out.write_text(build(rows, args.date), encoding="utf-8")


if __name__ == "__main__":
    main()
