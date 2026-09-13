#!/usr/bin/env python3
"""Demo: iterative synonym + abbreviation term expansion, on ME/CFS terms.

Runs `core.term_expansion.expand_and_search` (the engine behind
`CentralKnowledgeLookup.search_concepts_expanded`) for 10 real ME/CFS
(myalgic encephalomyelitis / chronic fatigue syndrome) terms against live
OLS + MONDO, so each term's search rounds, discovered synonyms/abbreviations,
and durably persisted expansion history can be inspected end to end.

Run with: poetry run python scripts/demo_expanded_lookup_mecfs.py
"""

import asyncio
import json
import os
import sys
import tempfile

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource  # noqa: E402
from knowledge_lookup.core.expansion_store import ExpansionStore  # noqa: E402
from knowledge_lookup.core.term_expansion import expand_and_search  # noqa: E402
from knowledge_lookup.models import LookupConfig  # noqa: E402

# ME/CFS has a famously tangled naming history — abbreviations, historical
# names, and closely related conditions — which makes it a good showcase
# for expansion: single-term search misses concepts under sibling names.
MECFS_TERMS = [
    "ME/CFS",
    "Chronic fatigue syndrome",
    "Myalgic encephalomyelitis",
    "CFS",
    "Post-exertional malaise",
    "PEM",
    "Chronic fatigue immune dysfunction syndrome",
    "Orthostatic intolerance",
    "POTS",
    "Brain fog",
]

SEARCH_SOURCES = [KnowledgeSource.OLS, KnowledgeSource.MONDO]

OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "mecfs_expansion_demo")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "mecfs_expansion_results.json")
DB_PATH = os.path.join(OUTPUT_DIR, "expansion_history.db")


async def run_term(lookup: CentralKnowledgeLookup, store: ExpansionStore, term: str) -> dict:
    result, trace = await expand_and_search(
        lookup,
        term,
        sources=SEARCH_SOURCES,
        max_results=10,
        max_rounds=2,
        max_terms_per_round=4,
        store=store,
    )

    concepts = result.concepts or []
    top_concepts = [
        {
            "label": c.primary_label,
            "id": c.primary_id,
            "synonyms": (c.synonyms or [])[:3],
        }
        for c in concepts[:5]
    ]

    return {
        "query": term,
        "run_id": trace.run_id,
        "rounds_run": trace.rounds_run,
        "stop_reason": trace.stop_reason,
        "terms_by_round": trace.terms_by_round,
        "total_concepts_found": len(concepts),
        "top_concepts": top_concepts,
    }


async def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("  ME/CFS Iterative Term Expansion Demo")
    print("=" * 70)
    print(f"  Terms:   {len(MECFS_TERMS)}")
    print(f"  Sources: {', '.join(s.value for s in SEARCH_SOURCES)}")
    print(f"  History: {DB_PATH}")
    print("=" * 70)

    config = LookupConfig(max_results_per_source=10, parallel_queries=True)
    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    store = ExpansionStore(DB_PATH)

    all_results = []
    try:
        for i, term in enumerate(MECFS_TERMS, 1):
            print(f"\n[{i}/{len(MECFS_TERMS)}] Expanding: {term!r}")
            entry = await run_term(lookup, store, term)
            all_results.append(entry)

            print(
                f"    rounds={entry['rounds_run']} "
                f"stop_reason={entry['stop_reason']} "
                f"concepts_found={entry['total_concepts_found']}"
            )
            for round_idx, round_terms in enumerate(entry["terms_by_round"]):
                if round_idx == 0:
                    continue  # round 0 is just the original query
                print(f"    round {round_idx} discovered: {round_terms}")
            for c in entry["top_concepts"][:3]:
                syn_str = f" (synonyms: {', '.join(c['synonyms'])})" if c["synonyms"] else ""
                print(f"      -> {c['label']} [{c['id']}]{syn_str}")
    finally:
        await lookup.close()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # ── Prove durability: reopen the store fresh, as a *new* object, and
    # read back everything just written — this is the point of ExpansionStore
    # over the evictable in-memory/disk cache: the record outlives this run.
    print(f"\n{'=' * 70}")
    print("  DURABLE PERSISTENCE CHECK (fresh ExpansionStore, same file)")
    print("=" * 70)
    reopened = ExpansionStore(DB_PATH)
    total_rounds_expanded = sum(1 for e in all_results if e["rounds_run"] > 1)
    for entry in all_results:
        if entry["run_id"] is None:
            continue
        run = reopened.get_run(entry["run_id"])
        terms = reopened.get_terms(entry["run_id"])
        print(
            f"  run #{entry['run_id']:<4} {run['original_query']!r:<50} "
            f"{len(terms)} terms recorded across {run['rounds_run']} round(s)"
        )

    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Terms searched:            {len(all_results)}")
    print(f"  Terms that actually expanded (>1 round): {total_rounds_expanded}")
    print(f"  Total concepts found:      {sum(e['total_concepts_found'] for e in all_results)}")
    print(f"\n  Full results: {OUTPUT_JSON}")
    print(f"  Expansion history DB:     {DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
