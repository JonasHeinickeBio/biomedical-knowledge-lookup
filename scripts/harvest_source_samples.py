#!/usr/bin/env python3
"""Query every knowledge source live and record what each one actually returns.

For each source this runs search -> details -> relationships -> mappings with the
same smoke-test query ``knowledge-lookup check`` uses, and stores a compact
summary: latency, top hits, which ``UnifiedConcept`` fields were filled, the
relationship predicates and mapping targets seen, and the raw upstream keys.
``scripts/build_data_coverage_doc.py`` turns that JSON into
``docs/guides/data-coverage.md``.

Usage:
    poetry run python scripts/harvest_source_samples.py --out samples.json
    poetry run python scripts/harvest_source_samples.py --only HPO,MONDO --out s.json

Sources that need credentials or an opt-in dataset are recorded as ``skipped``.
Requests are sequential per source and capped at ``--concurrency`` sources at a
time, so no upstream sees more than a handful of requests.
"""

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.__main__ import _CHECK_CREDENTIALS, _CHECK_DEFAULT_QUERY, _CHECK_QUERIES

TIMEOUT = 60.0
FIELDS = (
    "synonyms",
    "definitions",
    "identifiers",
    "parents",
    "children",
    "related",
    "mappings",
    "categories",
    "semantic_types",
)


def _clip(text: Any, n: int = 160) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _concept_row(c: Any) -> dict[str, Any]:
    return {"id": c.primary_id, "label": _clip(c.primary_label, 90), "type": str(c.concept_type)}


async def _timed(coro: Any) -> tuple[Any, float, str | None]:
    t0 = time.monotonic()
    try:
        return await asyncio.wait_for(coro, TIMEOUT), time.monotonic() - t0, None
    except Exception as exc:  # noqa: BLE001 - record any failure, the harvest must go on
        return None, time.monotonic() - t0, f"{type(exc).__name__}: {_clip(exc, 120)}"


async def harvest_one(lkp: CentralKnowledgeLookup, src: KnowledgeSource) -> dict[str, Any]:
    query = _CHECK_QUERIES.get(src, _CHECK_DEFAULT_QUERY)
    out: dict[str, Any] = {"source": src.name, "query": query}
    adapter = lkp._get_adapter(src)
    if adapter is None:
        out["status"] = "skipped"
        out["needs"] = _CHECK_CREDENTIALS.get(src, "credentials or optional dependency")
        return out

    hits, secs, err = await _timed(adapter.search_concepts(query, limit=5))
    out["search"] = {"seconds": round(secs, 2), "count": len(hits or []), "error": err}
    out["search"]["top"] = [_concept_row(c) for c in (hits or [])[:3]]
    if not hits:
        out["status"] = "failed" if err else "empty"
        return out

    first = hits[0]
    detail, secs, err = await _timed(adapter.get_concept_details(first.primary_id))
    out["details"] = {"seconds": round(secs, 2), "ok": detail is not None, "error": err}
    if detail is not None:
        out["details"]["filled"] = {
            f: len(getattr(detail, f) or []) for f in FIELDS if getattr(detail, f, None)
        }
        if detail.definitions:
            out["details"]["definition"] = _clip(detail.definitions[0])
        if detail.synonyms:
            out["details"]["synonyms"] = [_clip(s, 50) for s in detail.synonyms[:4]]
        raw = detail.source_data or {}
        keys: list[str] = []
        for v in raw.values():
            if isinstance(v, dict):
                keys = list(v)[:14]
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                keys = list(v[0])[:14]
        out["details"]["raw_keys"] = keys
        out["details"]["identifiers"] = [
            f"{i.source}:{i.identifier}" for i in (detail.identifiers or [])[:5]
        ]

    rels, secs, err = await _timed(adapter.get_relationships(first.primary_id))
    rels = rels or []
    preds = Counter(str(r.get("relation_label", "?")) for r in rels if isinstance(r, dict))
    out["relationships"] = {
        "seconds": round(secs, 2),
        "count": len(rels),
        "error": err,
        "predicates": preds.most_common(6),
        "sample": [
            f"{r.get('relation_label')} -> {r.get('related_id')} ({_clip(r.get('related_name'), 50)})"
            for r in rels[:3]
            if isinstance(r, dict)
        ],
    }

    maps, secs, err = await _timed(adapter.get_mappings(first.primary_id))
    maps = maps or []

    # UMLS predates the fromId/toId contract and returns {source, source_id, ...}
    def tgt(m: dict[str, Any]) -> str:
        return str(m.get("toSource") or m.get("source") or "?")

    def tid(m: dict[str, Any]) -> str:
        return str(m.get("toId") or m.get("source_id") or "?")

    targets = Counter(tgt(m) for m in maps if isinstance(m, dict))
    out["mappings"] = {
        "seconds": round(secs, 2),
        "count": len(maps),
        "error": err,
        "targets": targets.most_common(8),
        "sample": [f"{tgt(m)}:{tid(m)}" for m in maps[:3] if isinstance(m, dict)],
    }
    out["first_id"] = first.primary_id
    out["status"] = "ok" if detail is not None else "partial"
    return out


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", help="comma-separated KnowledgeSource names")
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()

    sources = list(KnowledgeSource)
    if args.only:
        wanted = {s.strip().upper() for s in args.only.split(",")}
        sources = [s for s in sources if s.name in wanted]

    lkp = CentralKnowledgeLookup(LookupConfig(enabled_sources=sources))
    sem = asyncio.Semaphore(args.concurrency)
    results: list[dict[str, Any]] = []

    async def run(src: KnowledgeSource) -> None:
        async with sem:
            row = await harvest_one(lkp, src)
            results.append(row)
            print(f"{row['status']:8} {src.name}", flush=True)

    try:
        await asyncio.gather(*(run(s) for s in sources))
    finally:
        await lkp.close()
    results.sort(key=lambda r: r["source"])
    args.out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
