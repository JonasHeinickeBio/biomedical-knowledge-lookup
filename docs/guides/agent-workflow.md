---
description: Run the LangGraph workflow that searches, filters, enriches and reviews concepts (optionally with an LLM) and exports the results.
---

# Agent workflow

`knowledge_lookup.agents` wraps the lookup library in a [LangGraph](https://langchain-ai.github.io/langgraph/) workflow. For a query it generates search variants, searches and filters concepts, gathers cross-references and UMLS CUIs, has the results reviewed by an LLM (or by rules), and exports a concept map. It needs the `agents` extra:

```bash
pip install "biomedical-knowledge-lookup[agents]"
```

## Pipeline

```
START -> preprocess -> expand -> lookup -> filter -> quality_gate -> detail_gather
      -> enrichment -> aggregate -> review

review   -> prune -> export -> END            score >= auto_approve_threshold, or iteration >= max_iterations
review   -> approval                          otherwise
approval -> prune -> export -> END            {"approved": True}
approval -> refine -> lookup (or prune)       {"approved": False, "refine": True, "notes": "..."}
approval -> END                               {"approved": False, "refine": False}
```

| Node | What it does |
| --- | --- |
| `preprocess` | Splits comma-separated queries into terms and adds variants: normalized text, umlaut expansions and German compound splits |
| `expand` | Runs [term expansion](term-expansion.md) on the original query against the selected sources (2 rounds, up to 8 new terms per round) and adds the discovered terms; UMLS abbreviation lookups run only when UMLS is selected (or no sources are given). The run is recorded in the `ExpansionStore` |
| `lookup` | Searches all terms (5 at a time) against the selected sources and merges the results; increments `iteration` |
| `filter` | Removes non-clinical concepts (questionnaire items, measurement scales, geographic locations), boosts clinically relevant types, re-ranks and keeps the best `max_results` concepts |
| `quality_gate` | Scores the filtered results, focusing on UMLS CUI coverage and source diversity |
| `detail_gather` | Searches each concept label in the available cross-reference sources (OLS, UMLS, BioPortal, Wikidata, MONDO, HPO) to collect identifiers, definitions and synonyms |
| `enrichment` | Looks up each concept label in UMLS and attaches its CUI; skipped when UMLS is not available |
| `aggregate` | Builds a text report of all concepts for the review |
| `review` | Builds a concept map (term, UMLS CUI, ontology IDs, type) and scores the results with an LLM, or with rules when no LLM is available |
| `approval` | Pauses for a human decision (LangGraph `interrupt`) |
| `refine` | Appends the user's notes to the query and rebuilds the search terms from it, as `preprocess` does, so the next `lookup` searches the refined text. Without new notes the same terms are searched again. Review suggestions are shown in the step detail and never added to the query |
| `prune` | Drops intermediate state before export |
| `export` | Writes JSON, CSV and/or Turtle files |

## Run the workflow from Python

{% code title="workflow.py" %}
```python
import asyncio

from knowledge_lookup.agents import run_workflow


async def main() -> None:
    result = await run_workflow(
        "seizure",
        sources=["HPO", "MONDO"],
        max_results=10,
        export_formats=["json", "csv"],
        export_path="workflow_output",
        auto_approve_threshold=0.0,  # export without pausing for approval
    )
    print(result["status"], result["review_score"])
    print(result["review_summary"])
    for entry in result["concept_map"][:5]:
        print(entry.get("term"), entry.get("umls_cui"), entry.get("ontology_ids", [])[:3])
    print(result["export_paths"])


asyncio.run(main())
```
{% endcode %}

`run_workflow(query, *, max_results=50, sources=None, concept_types=None, export_formats=None, export_path=None, max_iterations=3, auto_approve_threshold=0.8, checkpointer=None)`:

| Argument | Default | Meaning |
| --- | --- | --- |
| `query` | required | Search text; separate several terms with commas |
| `max_results` | `50` | Maximum results per search term, and the number of concepts kept after `filter` |
| `sources` | all | Source names (strings such as `"HPO"`, case-insensitive) for the `expand` and `lookup` steps |
| `concept_types` | none | Concept type names to keep, such as `"DISEASE"` |
| `export_formats` | `["json"]` | Any of `"json"`, `"csv"`, `"ttl"` |
| `export_path` | `<temp dir>/knowledge_lookup_export` | Directory for exported files, named after the query |
| `max_iterations` | `3` | Maximum number of lookup passes (initial search plus refinements) |
| `auto_approve_threshold` | `0.8` | Review score at or above which results are exported without asking |
| `checkpointer` | shared in-memory saver | LangGraph checkpointer that stores paused runs; see [Approval and refinement](#approval-and-refinement) |

The returned `dict` contains `thread_id`, `status`, `approval_request`, `result` (a `LookupResult` or `None`), `review_score`, `review_summary`, `review_strengths`, `review_weaknesses`, `review_suggestions`, `concept_map`, `llm_explanation`, `aggregated_context`, `export_paths`, `errors`, `steps` (one record per executed node with `agent`, `action`, `timestamp` and `detail`) and `iteration`. `status` is `"completed"`, `"failed"` or, when the run paused for a decision, `"awaiting_approval"`.

{% hint style="info" %}
**Runtime.** Each network step has a time budget: `expand` 45 s, `lookup` 60 s, `detail_gather` 45 s and `enrichment` 30 s (single cross-reference or UMLS searches time out after 15 s). Work that has not finished by then is dropped and noted in `steps` and `errors`, and the workflow continues with what it has. `sources` restricts `expand` and `lookup`; `detail_gather` and `enrichment` still query their cross-reference sources and UMLS when those are available. A query against one or two sources usually finishes in well under a minute; for example `"seizure"` with `sources=["HPO"]` took about 30 to 40 seconds including an LLM review. Without `sources`, every available adapter is searched and a run takes longer.
{% endhint %}

## LLM review

The review step uses the first LLM backend it finds in the environment:

| Backend | API key | Other variables (defaults) |
| --- | --- | --- |
| [Helmholtz Blablador](https://helmholtz-blablador.fz-juelich.de/) (OpenAI-compatible) | `BLABLADOR_API_KEY` | `BLABLADOR_API_BASE` (`https://api.helmholtz-blablador.fz-juelich.de/v1/`), `BLABLADOR_MODEL` (`alias-fast`) |
| OpenAI or any OpenAI-compatible API | `OPENAI_API_KEY` | `OPENAI_API_BASE`, `OPENAI_MODEL` (`gpt-4o-mini`) |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` (`claude-sonnet-4-20250514`) |

`load_llm_config()` shows which backend was picked. When a backend is configured, the LLM call is retried up to three times; if no backend is configured or all attempts fail, a rule-based review produces the score, strengths, weaknesses and suggestions instead. The concept map is always built by rules from the data.

## Approval and refinement

After `review`, the workflow exports automatically when `review_score >= auto_approve_threshold` or when `iteration >= max_iterations`. `iteration` counts lookup passes and is already 1 after the first search, so `max_iterations=1` never pauses. Otherwise the `approval` node interrupts and `run_workflow()` returns with `status == "awaiting_approval"`. `approval_request` then holds the query, the review, a preview of up to 15 concepts and a source breakdown. Nothing is exported yet. Resume the run with `resume_workflow(thread_id, decision)` and one of these decisions:

| Decision | Effect |
| --- | --- |
| `{"approved": True}` | Export the results |
| `{"approved": False, "refine": True, "notes": "..."}` | Append the notes to the query, search the terms built from the refined query (the `expand` step does not run again) and review again; the run can pause again |
| `{"approved": False, "refine": False}` | Stop without exporting |

{% code title="approval.py" %}
```python
import asyncio

from knowledge_lookup.agents import resume_workflow, run_workflow


async def main() -> None:
    result = await run_workflow("seizure", sources=["HPO"], max_results=10)
    while result["status"] == "awaiting_approval":
        request = result["approval_request"]
        print(request["review"]["score"], request["total_concepts"], "concepts")
        answer = input("Approve? [y/N] ").strip().lower()
        decision = {"approved": answer == "y", "refine": False}
        result = await resume_workflow(result["thread_id"], decision)
    print(result["status"], result["export_paths"])


asyncio.run(main())
```
{% endcode %}

Paused runs are stored in a checkpointer. By default `run_workflow()` and `resume_workflow()` share one in-memory `InMemorySaver` per Python process (`get_default_checkpointer()`), so a run can only be resumed from the process that started it. Runs that finish are removed from it. To keep paused runs elsewhere, pass the same LangGraph checkpointer to both functions as `checkpointer=`. `resume_workflow()` raises `ValueError` when the checkpointer has no run paused under that `thread_id`.

## Side effects

* Exported files are written to `export_path`, or to `knowledge_lookup_export` in the system temp directory.
* The expansion step records its run in `~/.cache/knowledge-lookup/expansion_history.db` (see [Term expansion](term-expansion.md)).

## Command line

The `workflow` command runs the same graph and asks for approval on the terminal when the run pauses:

```bash
knowledge-lookup workflow "seizure" --source HPO --format json --format csv --export-path results/ --auto-approve 0
```

See [Command-line interface](cli.md) for all options.

## Building blocks

| Name | Description |
| --- | --- |
| `build_workflow_graph(checkpointer=None)` | Compile the `StateGraph`; creates a new `InMemorySaver` when no checkpointer is given |
| `get_default_checkpointer()` | The in-memory checkpointer `run_workflow()` and `resume_workflow()` share by default |
| `LookupWorkflowState` | `TypedDict` describing the graph state |
| `lookup_result_to_dict(result)`, `dict_to_lookup_result(data)` | Serialize a `LookupResult` for the state and back |
| `make_step(agent, action, detail="", **extra)` | Create a step record |
| `load_llm_config()`, `call_llm(prompt, *, max_tokens=1024, temperature=0.2)` | LLM helpers used by the review step |

## Next steps

* [Term expansion](term-expansion.md)
* [Exporting results](exporting-results.md)
* [MCP server](mcp-server.md): let your own agent call the lookup tools directly
