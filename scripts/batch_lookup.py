#!/usr/bin/env python3
"""Batch lookup: process Symptom CSV through lookup + LLM review agent.

For each symptom term:
1. Searches across OLS, UMLS, BioPortal, Wikidata (parallel per-term)
2. Enriches with UMLS CUI (dedicated UMLS lookup)
3. LLM agent reviews each row: judges quality, gives suggestions, provides context
4. Writes enriched CSV + JSON with per-row LLM analysis
"""

import asyncio
import csv
import json
import os
import sys
import tempfile

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource  # noqa: E402

# Import LLM config
from knowledge_lookup.agents.config import call_llm  # noqa: E402
from knowledge_lookup.models import LookupConfig  # noqa: E402

# Override with: BATCH_LOOKUP_INPUT_CSV=/path/to/file.csv, or pass it as argv[1].
INPUT_CSV = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get(
        "BATCH_LOOKUP_INPUT_CSV",
        "/home/jhe24/AID-PAIS/CAIMed_KG_copy/Questionnaire/LongCovid_Final/csv/Symptoms_umls.csv",
    )
)
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "longcovid_batch_results")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "symptoms_with_llm_review.csv")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "symptoms_with_llm_review.json")

SEARCH_SOURCES = [
    KnowledgeSource.OLS,
    KnowledgeSource.UMLS,
    KnowledgeSource.BIOPORTAL,
    KnowledgeSource.WIKIDATA,
]

# Batch size for LLM review (terms per LLM call)
LLM_BATCH_SIZE = 10


def read_symptoms() -> list[dict]:
    """Read the symptom CSV."""
    symptoms = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symptoms.append(
                {
                    "label_de": row.get("label_de", "").strip(),
                    "label_en": row.get("label_en", "").strip(),
                    "original_cui": row.get("cui", "").strip(),
                    "umls_label": row.get("umls_label", "").strip(),
                    "umls_semantic_type": row.get("umls_semantic_type", "").strip(),
                }
            )
    return symptoms


async def search_single_term(
    lookup: CentralKnowledgeLookup,
    label_en: str,
) -> dict | None:
    """Search for a single English label across all sources."""
    if not label_en:
        return None

    try:
        result = await lookup.search_concepts(
            query=label_en,
            sources=SEARCH_SOURCES,
            max_results=5,
            parallel=True,
        )
    except Exception:
        return None

    if not result or not result.concepts:
        return None

    # Pick best concept (highest confidence)
    best = max(result.concepts, key=lambda c: c.confidence_score or 0)

    # Extract UMLS CUI from identifiers
    umls_cui = None
    for ident in best.identifiers or []:
        src = (
            str(ident.source).upper()
            if hasattr(ident.source, "upper")
            else str(ident.source).upper()
        )
        if src == "UMLS":
            umls_cui = ident.identifier
            break

    # If not found in identifiers, check primary_id
    if not umls_cui and best.primary_id and best.primary_id.startswith("C"):
        umls_cui = best.primary_id

    # --- Try dedicated UMLS enrichment if still no CUI ---
    if not umls_cui:
        try:
            umls_result = await lookup.search_concepts(
                query=label_en,
                sources=[KnowledgeSource.UMLS],
                max_results=2,
                parallel=False,
            )
            if umls_result and umls_result.concepts:
                uc = umls_result.concepts[0]
                if uc.primary_id and uc.primary_id.startswith("C"):
                    umls_cui = uc.primary_id
                    # Also pick up definitions
                    if not best.definitions and uc.definitions:
                        best.definitions = uc.definitions
                else:
                    for ident in uc.identifiers or []:
                        src = (
                            str(ident.source).upper()
                            if hasattr(ident.source, "upper")
                            else str(ident.source).upper()
                        )
                        if src == "UMLS":
                            umls_cui = ident.identifier
                            if not best.definitions and uc.definitions:
                                best.definitions = uc.definitions
                            break
        except Exception:
            pass

    # Extract all ontology IDs
    ontology_ids = set()
    for ident in best.identifiers or []:
        src = (
            str(ident.source).upper()
            if hasattr(ident.source, "upper")
            else str(getattr(ident.source, "value", "")).upper()
        )
        ontology_ids.add(f"{src}:{ident.identifier}")
    if best.primary_id:
        ontology_ids.add(best.primary_id)

    # Semantic types
    semantic_types = set()
    for t in best.semantic_types or []:
        semantic_types.add(str(t))
    if best.concept_type:
        semantic_types.add(str(best.concept_type))
    for c in best.categories or []:
        semantic_types.add(str(c))

    # Sources that contributed
    sources = [str(s) for s in (best.sources or [])]
    if not sources:
        sources = ["lookup"]

    return {
        "query_label": label_en,
        "label": best.primary_label or label_en,
        "umls_cui": umls_cui or "",
        "ontology_ids": sorted(ontology_ids)[:15],
        "semantic_types": sorted(semantic_types)[:8],
        "concept_type": str(best.concept_type) if best.concept_type else "",
        "confidence": round(best.confidence_score or 0, 3),
        "sources": sources,
        "primary_id": best.primary_id or "",
        "definitions": (best.definitions or [])[:3],
    }


def _categorize_match(entry: dict | None, original_cui: str) -> str:
    """Categorize how the found CUI relates to the original."""
    if entry is None:
        return "MISSING"
    if not entry["umls_cui"]:
        return "NO_CUI"
    if not original_cui:
        return "NEW"
    if entry["umls_cui"] == original_cui:
        return "EXACT"
    return "DIFFERENT"


async def _llm_review_batch(terms_batch: list[dict]) -> list[str]:
    """Run LLM review on a batch of term results.

    Returns list of analysis strings, one per term.
    """
    # Build context table for LLM
    rows_text = []
    for i, t in enumerate(terms_batch, 1):
        rows_text.append(
            f"[{i}] \"{t['query_label']}\" → \"{t['label']}\" "
            f"CUI:{t['umls_cui'] or '-'} "
            f"IDs:{', '.join(t['ontology_ids'][:5])} "
            f"Types:{', '.join(t['semantic_types'][:3]) or '-'} "
            f"Conf:{t['confidence']} "
            f"Sources:{', '.join(t['sources'][:3])}"
        )
    context = "\n".join(rows_text)

    prompt = f"""You are a biomedical ontology reviewer. Review {len(terms_batch)} symptom terms found via OLS/UMLS/BioPortal/Wikidata.

For EACH term, analyze: match_quality, cui_quality, ontology_coverage, suggestions, review_notes, confidence.

TERMS:
{context}

RESPOND WITH ONLY A VALID JSON ARRAY (no other text):
[
  {{"term_index": 1, "term": "...", "match_quality": "good|acceptable|poor|wrong", "cui_quality": "good|acceptable|poor", "ontology_coverage": "good|moderate|poor", "suggestions": "...", "review_notes": "...", "confidence": "high|medium|low"}},
  ...
]"""

    llm_output = await call_llm(prompt, max_tokens=4000, temperature=0.2)
    if llm_output is None:
        print(f"  ⚠ LLM returned None for batch ({len(terms_batch)} terms)")
        return []

    # Robust JSON extraction
    cleaned = llm_output.strip()

    # Strategy 1: Remove markdown code fences
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    # Strategy 2: Find JSON array (look for [...] at any depth)
    def _extract_json(text: str) -> str | None:
        """Try multiple strategies to extract valid JSON."""
        # Direct parse attempt
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Find outermost [...] block
        start = text.find("[")
        if start < 0:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        continue  # Try next possible block
        return None

    extracted = _extract_json(cleaned)
    if extracted is None:
        print(f"  ⚠ Could not extract JSON from LLM response (len={len(cleaned)})")
        return [
            f"LLM parse error: could not extract valid JSON from response ({len(llm_output)} chars)"
        ]

    try:
        reviews = json.loads(extracted)
        if not isinstance(reviews, list):
            return [f"LLM returned {type(reviews).__name__}, expected list"]

        result = []
        for r in reviews:
            if isinstance(r, dict):
                mq = r.get("match_quality", "unknown")
                cq = r.get("cui_quality", "unknown")
                cov = r.get("ontology_coverage", "unknown")
                sug = r.get("suggestions", "")
                notes = r.get("review_notes", "")
                conf = r.get("confidence", "medium")
                result.append(
                    f"Match:{mq} CUI:{cq} Coverage:{cov} "
                    f"Conf:{conf} | {notes} | Suggest: {sug}"
                )
            else:
                result.append(f"Match:unknown | review: {str(r)[:200]}")
        return result
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return [f"LLM parse error: {exc}"]


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Read symptoms
    symptoms = read_symptoms()
    print(f"Read {len(symptoms)} symptom rows")

    # Get unique English labels (preserving order)
    seen_labels: set[str] = set()
    unique_labels: list[str] = []
    for s in symptoms:
        label = s["label_en"].strip().lower()
        if label and label not in seen_labels:
            seen_labels.add(label)
            unique_labels.append(s["label_en"])

    print(f"Unique English labels: {len(unique_labels)}")

    # Initialize lookup
    print("Initializing CentralKnowledgeLookup (may take a moment)...")
    config = LookupConfig(
        max_results_per_source=8,
        parallel_queries=True,
        enable_deduplication=True,
        enable_source_health_tracking=False,
    )
    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    print(f"Ready. {len(lookup.adapters)} sources available.")

    try:
        # ── STEP 1: Search all terms ──
        all_entries: dict[str, dict] = {}

        for idx, label in enumerate(unique_labels, 1):
            if idx % 15 == 0:
                print(f"  Search: {idx}/{len(unique_labels)} ({100 * idx // len(unique_labels)}%)")

            entry = await search_single_term(lookup, label)
            if entry:
                all_entries[label.strip().lower()] = entry

        print(f"  Search complete: {len(all_entries)} / {len(unique_labels)} terms matched")

        # ── STEP 2: Run LLM review in batches ──
        term_list = list(all_entries.values())
        print(f"\nRunning LLM review for {len(term_list)} terms...")

        llm_reviews: list[str] = [""] * len(term_list)  # One per term
        for batch_start in range(0, len(term_list), LLM_BATCH_SIZE):
            batch = term_list[batch_start : batch_start + LLM_BATCH_SIZE]
            print(
                f"  LLM batch: {batch_start + 1}–{min(batch_start + LLM_BATCH_SIZE, len(term_list))} ({len(batch)} terms)"
            )

            batch_reviews = await _llm_review_batch(batch)
            for i, review in enumerate(batch_reviews):
                if batch_start + i < len(llm_reviews):
                    llm_reviews[batch_start + i] = review

            # Small delay between batches to avoid rate limits
            if batch_start + LLM_BATCH_SIZE < len(term_list):
                await asyncio.sleep(0.5)

        # Build term_index_review dict for matching
        term_review_map: dict[str, str] = {}
        for i, entry in enumerate(term_list):
            key = entry["query_label"].strip().lower()
            term_review_map[key] = llm_reviews[i] if i < len(llm_reviews) else ""

        llm_count = sum(1 for r in llm_reviews if r)
        print(f"  LLM reviews: {llm_count}/{len(term_list)} terms reviewed")

        # ── STEP 3: Build output rows ──
        output_rows = []
        exact = different = new = missing = no_cui = 0

        for s in symptoms:
            label_lower = s["label_en"].strip().lower()
            entry = all_entries.get(label_lower)
            match_type = _categorize_match(entry, s["original_cui"])

            if match_type == "EXACT":
                exact += 1
            elif match_type == "DIFFERENT":
                different += 1
            elif match_type == "NEW":
                new += 1
            elif match_type == "MISSING":
                missing += 1
            elif match_type == "NO_CUI":
                no_cui += 1

            row = {
                "label_de": s["label_de"],
                "label_en": s["label_en"],
                "original_cui": s["original_cui"],
                "original_umls_label": s["umls_label"],
                "original_umls_type": s["umls_semantic_type"],
                "found_cui": entry["umls_cui"] if entry else "",
                "found_label": entry["label"] if entry else "",
                "found_concept_type": entry["concept_type"] if entry else "",
                "found_semantic_types": "; ".join(entry["semantic_types"]) if entry else "",
                "found_ontology_ids": "; ".join(entry["ontology_ids"]) if entry else "",
                "confidence": entry["confidence"] if entry else "",
                "found_sources": "; ".join(entry["sources"]) if entry else "",
                "definitions": "; ".join(entry["definitions"]) if entry else "",
                "cui_match": match_type,
                "llm_review": term_review_map.get(label_lower, ""),
            }
            output_rows.append(row)

        # ── STEP 4: Write output ──
        fieldnames = [
            "label_de",
            "label_en",
            "original_cui",
            "original_umls_label",
            "original_umls_type",
            "cui_match",
            "found_cui",
            "found_label",
            "found_concept_type",
            "found_semantic_types",
            "found_ontology_ids",
            "confidence",
            "found_sources",
            "definitions",
            "llm_review",
        ]
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(output_rows, f, indent=2, ensure_ascii=False)

        # ── SUMMARY ──
        total = len(output_rows)
        print(f"\n{'='*60}")
        print("  RESULTS WRITTEN")
        print(f"{'='*60}")
        print(f"  Total rows:      {total}")
        print(f"  Exact CUI match: {exact:3d} ({100 * exact // max(total, 1)}%)")
        print(f"  Different CUI:   {different:3d} ({100 * different // max(total, 1)}%)")
        print(f"  New CUI found:   {new:3d}")
        print(f"  No CUI found:    {no_cui:3d}")
        print(f"  Missing:         {missing:3d}")
        print(f"  With LLM review: {llm_count}")
        print("\n  Outputs:")
        print(f"    CSV:  {OUTPUT_CSV}")
        print(f"    JSON: {OUTPUT_JSON}")

        # ── Show a few LLM reviews ──
        print(f"\n{'='*60}")
        print("  SAMPLE LLM REVIEWS")
        print(f"{'='*60}")
        for row in output_rows[:5]:
            print(f"\n  [{row['cui_match']}] {row['label_en']}")
            print(f"      CUI: {row['original_cui']} → {row['found_cui']}")
            print(f"      LLM: {row['llm_review'][:150]}")

    finally:
        await lookup.close()


if __name__ == "__main__":
    asyncio.run(main())
