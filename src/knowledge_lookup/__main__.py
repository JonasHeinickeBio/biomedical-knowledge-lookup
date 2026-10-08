#!/usr/bin/env python3
"""
Command-line interface for Biomedical Knowledge Lookup.

A unified tool for biological concept lookup across multiple biomedical knowledge sources.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from knowledge_lookup import (
    CentralKnowledgeLookup,
    KnowledgeSource,
    LookupResult,
    __description__,
    __version__,
)
from knowledge_lookup.cache import init_cache
from knowledge_lookup.mcp_server.sources import SOURCE_CATALOG, normalize_source_name

if TYPE_CHECKING:
    from knowledge_lookup.adapters.umls_adapter import UMLSAdapter

app = typer.Typer(
    name="biomedical-knowledge-lookup",
    help="Unified biological concept lookup across biomedical knowledge sources",
    add_completion=False,
)

console = Console()


@app.callback()
def callback():
    """
    Biomedical Knowledge Lookup CLI

    Search for biological concepts across 37 biomedical knowledge sources.
    """
    pass


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (e.g., 'diabetes', 'BRCA1')"),
    sources: list[str] | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Knowledge sources to search (default: all available)",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of results in total (split across the selected sources)",
    ),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
    cache_dir: str | None = typer.Option(
        None,
        "--cache-dir",
        help="Directory for the on-disk adapter cache (default: in-memory cache only)",
    ),
    partial: bool = typer.Option(
        False, "--partial", "-p", help="Enable partial/fuzzy matching (UMLS adapter)"
    ),
    expand: bool = typer.Option(
        False,
        "--expand",
        "-e",
        help="Iteratively expand the query with synonyms/long-forms discovered from results "
        "and search each new term (uses search_concepts_expanded)",
    ),
    relationships: bool = typer.Option(
        False,
        "--relationships",
        help="With --expand, also traverse relationship edges (STRING interactions, KEGG "
        "pathways, DisGeNET/Open Targets associations) and search their named targets "
        "(implies --expand)",
    ),
    expand_hierarchy: bool = typer.Option(
        False,
        "--expand-hierarchy",
        help="With --expand, traverse only taxonomic class<->member edges (OLS narrower/"
        "broader, UMLS parent/child) so a class term surfaces its members (implies --expand)",
    ),
):
    """
    Search for biological concepts across knowledge sources.
    """
    try:
        # Configure the global cache before the lookup system picks it up
        if cache_dir:
            init_cache(disk_cache_dir=cache_dir)

        # Initialize lookup system
        lookup = CentralKnowledgeLookup()

        # Convert source strings to KnowledgeSource enums
        if sources:
            source_enums = []
            for source in sources:
                try:
                    source_enums.append(KnowledgeSource(source.upper()))
                except ValueError:
                    console.print(f"[red]Error:[/red] Unknown source '{source}'")
                    console.print(
                        f"Available sources: {', '.join([s.value for s in KnowledgeSource])}"
                    )
                    raise typer.Exit(1) from None
        else:
            source_enums = None

        # Perform search
        console.print(f"[bold blue]Searching for:[/bold blue] {query}")
        if source_enums:
            console.print(
                f"[bold blue]Sources:[/bold blue] {', '.join([s.value for s in source_enums])}"
            )

        async def do_search(lkp: CentralKnowledgeLookup) -> LookupResult:
            try:
                if partial and (source_enums is None or KnowledgeSource.UMLS in source_enums):
                    # Direct UMLS adapter call with partial_search enabled
                    umls_adapter = lkp._get_adapter(KnowledgeSource.UMLS)
                    if umls_adapter and umls_adapter.is_available():
                        umls_adapter_casted = cast("UMLSAdapter", umls_adapter)
                        umls_concepts = await umls_adapter_casted.search_concepts(
                            query, limit=limit, partial_search=True
                        )
                        result = LookupResult(query=query)
                        result.add_concepts(umls_concepts, KnowledgeSource.UMLS)
                        return result
                if expand or relationships or expand_hierarchy:
                    if expand_hierarchy:
                        from knowledge_lookup.core.term_expansion import (
                            hierarchy_relationship_sources,
                        )

                        return await lkp.search_concepts_expanded(
                            query=query,
                            sources=source_enums,
                            max_results=limit,
                            relationships=True,
                            relationship_sources=hierarchy_relationship_sources(lkp),
                        )
                    if relationships:
                        return await lkp.search_concepts_expanded(
                            query=query,
                            sources=source_enums,
                            max_results=limit,
                            relationships=True,
                        )
                    return await lkp.search_concepts_expanded(
                        query=query,
                        sources=source_enums,
                        max_results=limit,
                    )
                return await lkp.search_concepts(
                    query=query,
                    sources=source_enums,
                    max_results=limit,
                )
            finally:
                await lkp.close()

        results = asyncio.run(do_search(lookup))

        if not results.concepts:
            console.print("[yellow]No results found.[/yellow]")
            return

        # Output results
        if output == "json":
            output_data = {
                "query": query,
                "sources": [
                    str(getattr(s, "value", s))
                    for s in (source_enums or results.sources_queried or [])
                ],
                "total_results": len(results.concepts),
                "results": [
                    {
                        "id": r.primary_id,
                        "name": r.primary_label,
                        "description": r.definitions[0] if r.definitions else None,
                        "source": r.sources[0] if r.sources else None,
                        "type": r.concept_type,
                        "uri": None,
                        "score": r.confidence_score,
                    }
                    for r in results.concepts
                ],
            }
            console.print_json(json.dumps(output_data, indent=2))

        elif output == "csv":
            import csv
            import sys

            writer = csv.writer(sys.stdout)
            writer.writerow(["ID", "Name", "Description", "Source", "Type", "URI", "Score"])

            for result in results.concepts:
                writer.writerow(
                    [
                        result.primary_id,
                        result.primary_label,
                        (result.definitions[0] if result.definitions else ""),
                        result.sources[0] if result.sources else "",
                        result.concept_type,
                        "",
                        result.confidence_score,
                    ]
                )

        else:  # table format
            table = Table(title=f"Search Results for '{query}'")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="bold")
            table.add_column("Source", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Description", max_width=50)

            for result in results.concepts:
                table.add_row(
                    result.primary_id,
                    result.primary_label,
                    result.sources[0] if result.sources else "",
                    result.concept_type,
                    (
                        (result.definitions[0] if result.definitions else "")
                        if len(result.definitions[0] if result.definitions else "") <= 50
                        else ((result.definitions[0] if result.definitions else "")[:47] + "...")
                    ),
                )

            console.print(table)
            console.print(f"\n[bold green]Total results:[/bold green] {len(results.concepts)}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1) from e


def _get_concept_umls_cui(concept) -> str | None:
    """Extract UMLS CUI from a concept's identifiers."""
    if not concept.identifiers:
        return None
    for ident in concept.identifiers:
        if ident.source == KnowledgeSource.UMLS:
            return ident.identifier
    # Fallback: check source_data for umls_cui
    if concept.source_data:
        for val in concept.source_data.values():
            if isinstance(val, dict) and "umls_cui" in val:
                return val["umls_cui"]
    return None


@app.command()
def workflow(
    query: str = typer.Argument(..., help="Search query for the agent workflow"),
    sources: list[str] | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Knowledge sources for term expansion and the main lookup (default: all available)",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum results per search term; also the number of concepts kept after filtering",
    ),
    export_formats: list[str] = typer.Option(
        ["json"], "--format", "-f", help="Export formats (json, csv, ttl)"
    ),
    export_path: str | None = typer.Option(
        None, "--export-path", "-e", help="Export directory path"
    ),
    max_iterations: int = typer.Option(
        3, "--max-iter", help="Maximum lookup passes (initial search plus refinements)"
    ),
    auto_approve: float = typer.Option(0.8, "--auto-approve", help="Auto-approve threshold (0-1)"),
    concept_types: list[str] | None = typer.Option(
        None, "--type", "-t", help="Filter by concept types"
    ),
    relationships: bool = typer.Option(
        False,
        "--relationships",
        help="Expand the search with relationship edges (interactions, pathways, class members)",
    ),
    evidence: bool = typer.Option(
        False,
        "--evidence",
        help="Attach top Europe PMC papers for the leading concepts",
    ),
    auto_rounds: int = typer.Option(
        1,
        "--auto-rounds",
        min=0,
        help="Autonomous follow-up searches when results are empty, thin or a source failed "
        "(0 disables)",
    ),
):
    """
    Run the intelligent agent workflow with review and approval.

    Supports multi-term queries: separate terms by comma to search each
    independently against all sources, then aggregate results.

    Examples:
      knowledge-lookup workflow "diabetes" --source OLS --source UMLS
      knowledge-lookup workflow "Gliederschmerzen, body ache" --format json --format csv
      knowledge-lookup workflow "BRCA1, BRCA2, TP53" --limit 10 --auto-approve 0.7

    The workflow performs:
    1. Parallel lookup across knowledge sources, with autonomous follow-up
       searches when results are empty or thin
    2. Type-aware cross-source detail gathering (IDs, definitions, types, synonyms)
    3. UMLS CUI enrichment
    4. Optional relationship edges (--relationships) and literature evidence (--evidence)
    5. LLM-powered quality review (or rule-based fallback)
    6. Human approval gate (or auto-approve if score is high enough)
    7. Optional refinement rounds based on feedback
    8. Export to configured formats with concept map output
    """
    from knowledge_lookup.agents import resume_workflow, run_workflow

    console.print(f"[bold blue]Starting agent workflow for:[/bold blue] {query}")

    async def _run():
        return await run_workflow(
            query=query,
            max_results=limit,
            sources=sources,
            concept_types=concept_types,
            export_formats=export_formats,
            export_path=export_path,
            max_iterations=max_iterations,
            auto_approve_threshold=auto_approve,
            include_relationships=relationships,
            include_evidence=evidence,
            max_auto_rounds=auto_rounds,
        )

    result = asyncio.run(_run())
    _print_review(result, auto_approve)

    # Ask for a decision while the workflow waits at the approval gate; a
    # refinement searches again and can pause again (up to --max-iter passes).
    rejected = False
    while result.get("status") == "awaiting_approval":
        console.print("\n[bold yellow]Workflow paused for approval.[/bold yellow]")
        console.print(f"Thread ID: {result['thread_id']}")
        try:
            decision = _prompt_approval_decision()
        except typer.Abort:
            console.print(
                "\n[yellow]No approval decision received (input closed); stopping without "
                "export. Pass --auto-approve 0 to export without asking.[/yellow]"
            )
            raise typer.Exit(1) from None
        rejected = not decision.get("approved") and not decision.get("refine")
        result = asyncio.run(resume_workflow(result["thread_id"], decision))
        if result.get("status") == "awaiting_approval":
            _print_review(result, auto_approve)

    # Display final results
    if rejected:
        console.print("\n[bold yellow]Results rejected; nothing was exported.[/bold yellow]")
    elif result.get("status") == "completed":
        console.print("\n[bold green]Workflow completed![/bold green]")

        # Show concept map in final output
        concept_map = result.get("concept_map") or []
        if concept_map:
            console.print(f"[bold]Concept Map ({len(concept_map)} concepts):[/bold]")
            map_table = Table()
            map_table.add_column("#", style="dim")
            map_table.add_column("Term", style="bold")
            map_table.add_column("UMLS CUI", style="magenta")
            map_table.add_column("Ontology IDs", style="cyan")
            map_table.add_column("Type", style="yellow")
            for i, entry in enumerate(concept_map, 1):
                term = entry.get("term", "")
                cui = entry.get("umls_cui", "") or "—"
                ids = ", ".join(entry.get("ontology_ids", [])[:6])
                if len(entry.get("ontology_ids", [])) > 6:
                    ids += f" … (+{len(entry['ontology_ids']) - 6} more)"
                ptype = entry.get("primary_type", "") or "—"
                map_table.add_row(str(i), term, cui, ids, ptype)
            console.print(map_table)
        else:
            res = result.get("result")
            if res and res.concepts:
                console.print(f"[bold]Results: {len(res.concepts)} concepts[/bold]")
                table = Table()
                table.add_column("ID", style="cyan")
                table.add_column("Label", style="bold")
                table.add_column("UMLS CUI", style="magenta")
                table.add_column("Confidence", style="green")
                for c in res.concepts[:10]:
                    umls_cui = _get_concept_umls_cui(c)
                    table.add_row(
                        c.primary_id,
                        c.primary_label or "",
                        umls_cui or "-",
                        f"{c.confidence_score:.2f}" if c.confidence_score else "",
                    )
                console.print(table)

        # Show LLM explanation
        llm_explanation = result.get("llm_explanation") or ""
        if llm_explanation:
            console.print("\n[bold]LLM Explanation:[/bold]")
            console.print(f"{llm_explanation[:800]}{'…' if len(llm_explanation) > 800 else ''}")

        if result.get("export_paths"):
            console.print("[bold]Exported to:[/bold]")
            for path in result["export_paths"]:
                console.print(f"  [green]{path}[/green]")
    elif result.get("status") == "failed":
        console.print("\n[bold red]Workflow failed![/bold red]")
        for err in result.get("errors", []):
            console.print(f"  [red]{err}[/red]")

    # Show steps
    if result.get("steps"):
        console.print("\n[bold]Workflow steps:[/bold]")
        for step in result["steps"]:
            console.print(
                f"  [cyan]{step.get('agent', '?')}[/cyan] - "
                f"{step.get('action', '?')}: {step.get('detail', '')}"
            )


def _prompt_approval_decision() -> dict:
    """Ask the user for an approval decision (raises ``typer.Abort`` on closed input)."""
    if typer.confirm("Do you approve these results?"):
        return {"approved": True}
    if typer.confirm("Would you like to refine the search?"):
        notes = typer.prompt("Enter refinement notes (or press Enter to skip)", default="")
        return {"approved": False, "refine": True, "notes": notes}
    return {"approved": False, "refine": False}


def _print_review(result: dict, auto_approve: float) -> None:
    """Print the review score, concept map, explanation and review notes."""
    # Display concept map (term → CUI → ontology IDs → type)
    concept_map = result.get("summary", {}).get("concept_map") or result.get("concept_map") or []
    llm_explanation = (
        result.get("summary", {}).get("llm_explanation") or result.get("llm_explanation") or ""
    )

    # Display review
    if result.get("review_score") is not None:
        score = result["review_score"]
        color = "green" if score >= auto_approve else "yellow" if score >= 0.5 else "red"
        console.print(f"\n[bold {color}]Review Score: {score:.2f}[/bold {color}]")
        if result.get("review_summary"):
            console.print(f"[dim]{result['review_summary']}[/dim]")

    # Show what the agentic expansion did
    if result.get("auto_rounds"):
        console.print(f"[dim]Autonomous follow-up round(s): {result['auto_rounds']}[/dim]")
    if result.get("relationship_edges"):
        console.print(f"[dim]Relationship edges: {len(result['relationship_edges'])}[/dim]")
    evidence = result.get("literature_evidence") or []
    if evidence:
        papers = sum(len(e.get("papers") or []) for e in evidence)
        console.print(
            f"[dim]Literature evidence: {papers} paper(s) for {len(evidence)} concept(s)[/dim]"
        )

    # Show concept map
    if concept_map:
        console.print("\n[bold]Concept Map:[/bold]")
        map_table = Table()
        map_table.add_column("Term", style="bold", no_wrap=True)
        map_table.add_column("UMLS CUI", style="magenta")
        map_table.add_column("Ontology IDs", style="cyan")
        map_table.add_column("Type", style="yellow")
        for entry in concept_map[:15]:
            term = entry.get("term", "")
            cui = entry.get("umls_cui", "") or "—"
            ids = ", ".join(entry.get("ontology_ids", [])[:5])
            if len(entry.get("ontology_ids", [])) > 5:
                ids += f" … (+{len(entry['ontology_ids']) - 5} more)"
            ptype = entry.get("primary_type", "") or "—"
            map_table.add_row(term, cui, ids, ptype)
        console.print(map_table)

    # Show LLM explanation
    if llm_explanation:
        console.print("\n[bold]LLM Explanation:[/bold]")
        console.print(f"{llm_explanation[:500]}{'…' if len(llm_explanation) > 500 else ''}")

    # Show strengths/weaknesses
    if result.get("review_strengths"):
        console.print("\n[bold green]Strengths:[/bold green]")
        for s in result["review_strengths"]:
            console.print(f"  [green]✓[/green] {s}")
    if result.get("review_weaknesses"):
        console.print("\n[bold red]Weaknesses:[/bold red]")
        for w in result["review_weaknesses"]:
            console.print(f"  [red]✗[/red] {w}")
    if result.get("review_suggestions"):
        console.print("\n[bold yellow]Suggestions:[/bold yellow]")
        for s in result["review_suggestions"]:
            console.print(f"  [yellow]→[/yellow] {s}")


@app.command()
def sources():
    """
    List all knowledge sources with an adapter and whether they are available here.
    """
    lookup = CentralKnowledgeLookup()
    available = {s for s in SOURCE_CATALOG if lookup._get_adapter(s)}

    table = Table(title="Knowledge Sources")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Requires", style="yellow")
    table.add_column("Available", no_wrap=True)

    for source, spec in sorted(SOURCE_CATALOG.items(), key=lambda item: item[0].value):
        table.add_row(
            source.value,
            escape(spec.description),
            escape(spec.requires or "-"),  # "[chembl] extra" is not Rich markup
            "[green]yes[/green]" if source in available else "[red]no[/red]",
        )

    console.print(table)
    console.print(
        f"\n[dim]{len(available)}/{len(SOURCE_CATALOG)} sources available in this environment[/dim]"
    )


async def _time_call(coro: Any) -> tuple[bool, Any, float, str | None]:
    """Await *coro*, returning ``(ok, result, elapsed_seconds, error_message)``."""
    start = time.perf_counter()
    try:
        result = await coro
        return True, result, time.perf_counter() - start, None
    except Exception as e:  # noqa: BLE001 - reported to the user, not swallowed
        return False, None, time.perf_counter() - start, str(e)


# Smoke-test query used when ``check --query`` is not given. Most sources answer
# "BRCA1", but some only index chemistry, phenotypes, diseases or exact ontology
# labels, and UniChem searches by identifier (here aspirin's InChIKey).
_CHECK_DEFAULT_QUERY = "BRCA1"
_CHECK_QUERIES: dict[KnowledgeSource, str] = {
    KnowledgeSource.DRUGBANK: "aspirin",
    KnowledgeSource.PUBCHEM: "aspirin",
    KnowledgeSource.UNICHEM: "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    KnowledgeSource.HPO: "seizure",
    KnowledgeSource.KEGG: "diabetes",
    KnowledgeSource.TYTO: "gene",
    KnowledgeSource.INTERPRO: "kinase",
    KnowledgeSource.PFAM: "kinase",
    KnowledgeSource.ZOOMA: "diabetes",
    KnowledgeSource.OBOFOUNDRY: "diabetes",
    KnowledgeSource.HPOA: "marfan",  # rare diseases only: ME/CFS is not in phenotype.hpoa
    KnowledgeSource.NODENORM: "diabetes mellitus",
    KnowledgeSource.MESH: "chronic fatigue syndrome",
    KnowledgeSource.RXCLASS: "aspirin",
    KnowledgeSource.SNOMEDCT: "fatigue",
    KnowledgeSource.ICD11: "fatigue",
    KnowledgeSource.ICD10GM: "fatigue",
    KnowledgeSource.LOINC: "hemoglobin",
    KnowledgeSource.GWASCATALOG: "chronic fatigue syndrome",
    KnowledgeSource.CTD: "aspirin",
    KnowledgeSource.CLINICALTRIALS: "long covid",
    KnowledgeSource.SEMMEDDB: "fatigue",
    KnowledgeSource.SIDER: "aspirin",
    KnowledgeSource.OFFSIDES: "aspirin",
    KnowledgeSource.CELLONTOLOGY: "T cell",
    KnowledgeSource.CELLMARKER: "CD4",
    KnowledgeSource.CHEBI: "aspirin",
    KnowledgeSource.LITCOVID: "long covid",
    KnowledgeSource.OPENALEX: "chronic fatigue syndrome",
    KnowledgeSource.OPENFDAEVENTS: "aspirin",
    KnowledgeSource.ORPHANET: "marfan",
    KnowledgeSource.MEDGEN: "chronic fatigue syndrome",
    KnowledgeSource.DOID: "diabetes mellitus",
    KnowledgeSource.DBSNP: "rs1801133",
    KnowledgeSource.RXNORM: "aspirin",
    KnowledgeSource.CLINPGX: "CYP2D6",
    KnowledgeSource.OPENFDALABELS: "aspirin",
    KnowledgeSource.CLINICALTABLES: "fatigue",
    KnowledgeSource.NCIEVS: "fatigue",
    KnowledgeSource.MEDLINEPLUS: "chronic fatigue syndrome",
    KnowledgeSource.NCBITAXONOMY: "SARS-CoV-2",
    KnowledgeSource.METABOLOMICSWORKBENCH: "lactate",
    KnowledgeSource.METABOLIGHTS: "chronic fatigue",
    KnowledgeSource.LIPIDMAPS: "cholesterol",
    KnowledgeSource.RHEA: "lactate",
    KnowledgeSource.IEDB: "spike",
    KnowledgeSource.CELLXGENE: "natural killer cell",
    KnowledgeSource.PANELAPP: "ataxia",
    KnowledgeSource.CROSSREF: "long covid",
    KnowledgeSource.BIORXIV: "long covid",
    KnowledgeSource.OPENCITATIONS: "10.1038/s41586-020-2012-7",
    KnowledgeSource.NIHREPORTER: "myalgic encephalomyelitis",
    KnowledgeSource.SEMANTICSCHOLAR: "long covid",
}


# Sources whose adapter only exists once credentials are configured. ``check``
# reports these as skipped (naming the variable) instead of failed.
_CHECK_CREDENTIALS: dict[KnowledgeSource, str] = {
    KnowledgeSource.OMIM: "OMIM_API_KEY",
    KnowledgeSource.COSMIC: "COSMIC_API_KEY",
    KnowledgeSource.ICD11: "ICD11_CLIENT_ID",
    KnowledgeSource.LOINC: "LOINC_USERNAME",
    KnowledgeSource.SEMMEDDB: "SEMMEDDB_PATH (build the file with `knowledge-lookup semmeddb-build`)",
    KnowledgeSource.ICD10GM: "ICD10GM_CLAML_PATH",
    # dataset-backed sources are opt-in so nothing downloads without consent
    KnowledgeSource.HPOA: "HPOA_DOWNLOAD=1 (downloads ~36 MB) or HPOA_PATH",
    KnowledgeSource.SIDER: "SIDER_DOWNLOAD=1 (downloads ~5.5 MB) or SIDER_DATA_DIR",
    KnowledgeSource.OFFSIDES: "OFFSIDES_DOWNLOAD=1 (downloads ~69 MB) or OFFSIDES_PATH",
    KnowledgeSource.CTD: "CTD_DOWNLOAD=1 (downloads ~220 MB) or CTD_DATA_DIR",
    KnowledgeSource.CELLMARKER: "CELLMARKER_PATH or CELLMARKER_URL",
    KnowledgeSource.CLINGEN: "CLINGEN_DOWNLOAD=1 (downloads ~1.4 MB) or CLINGEN_PATH",
    KnowledgeSource.GENCC: "GENCC_DOWNLOAD=1 (downloads ~28 MB) or GENCC_PATH",
}


async def _check_source(
    lkp: CentralKnowledgeLookup,
    source: KnowledgeSource,
    query: str,
    concept_id: str | None,
    relationships: bool,
    timeout: float,
) -> dict[str, Any]:
    """Exercise one adapter's live API: search -> details -> relationships.

    Returns a dict with ``source``, ``available``, an ordered ``steps`` list of
    ``(name, ok, detail, elapsed_seconds)`` tuples, and whichever raw results
    were fetched (``search_concepts``, ``concept_details``, ``relationships``)
    for the caller to print in detail mode.
    """
    result: dict[str, Any] = {"source": source, "available": False, "steps": []}

    adapter = lkp._get_adapter(source)
    if adapter is None:
        env_var = _CHECK_CREDENTIALS.get(source)
        if env_var:
            result["skipped"] = f"set {env_var} to enable"
        result["steps"].append(("available", False, "no adapter configured/available", 0.0))
        return result
    result["available"] = True

    target_id = concept_id
    if target_id is None:
        ok, concepts, elapsed, err = await _time_call(
            asyncio.wait_for(adapter.search_concepts(query, limit=5), timeout)
        )
        count = len(concepts) if ok and concepts else 0
        detail = f"{count} result(s)" if ok else (err or "failed")
        result["steps"].append(("search_concepts", ok and count > 0, detail, elapsed))
        result["search_concepts"] = concepts if ok else []
        if ok and concepts:
            target_id = concepts[0].primary_id

    if target_id:
        ok, concept, elapsed, err = await _time_call(
            asyncio.wait_for(adapter.get_concept_details(target_id), timeout)
        )
        detail = (concept.primary_label if concept else "not found") if ok else (err or "failed")
        result["steps"].append(
            ("get_concept_details", ok and concept is not None, detail, elapsed)
        )
        result["concept_details"] = concept if ok else None

        if relationships:
            ok, rels, elapsed, err = await _time_call(
                asyncio.wait_for(adapter.get_relationships(target_id), timeout)
            )
            detail = f"{len(rels)} edge(s)" if ok and rels is not None else (err or "failed")
            result["steps"].append(("get_relationships", ok, detail, elapsed))
            result["relationships"] = rels if ok else []
    else:
        result["steps"].append(
            ("get_concept_details", False, "skipped (no id: search returned nothing)", 0.0)
        )

    return result


def _check_skipped(r: dict[str, Any]) -> bool:
    """True when a source was not tested because its credentials are not configured."""
    return bool(r.get("skipped"))


def _check_passed(r: dict[str, Any]) -> bool:
    return r["available"] and all(ok for _, ok, _, _ in r["steps"])


def _print_check_detail(r: dict[str, Any], relationships: bool) -> None:
    """Verbose, step-by-step report for a single source (the non-'all' path)."""
    source = r["source"].value

    if _check_skipped(r):
        console.print(f"[yellow]- {source} skipped: {r['skipped']}[/yellow]")
        return
    if not r["available"]:
        console.print(f"[red]✗ {source} has no adapter available in this environment.[/red]")
        return

    console.print(f"[bold blue]Checking {source}[/bold blue]")
    for name, ok, detail, elapsed in r["steps"]:
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {icon} {name:<20} {escape(detail):<40} [dim]({elapsed:.2f}s)[/dim]")

    concepts = r.get("search_concepts") or []
    if concepts:
        table = Table(title="search_concepts")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Type", style="yellow")
        for c in concepts:
            table.add_row(c.primary_id, c.primary_label or "", str(c.concept_type or ""))
        console.print(table)

    concept = r.get("concept_details")
    if concept:
        table = Table(title="get_concept_details")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        table.add_row("ID", concept.primary_id)
        table.add_row("Label", concept.primary_label or "")
        table.add_row("Type", str(concept.concept_type or ""))
        if concept.definitions:
            table.add_row("Definition", escape(concept.definitions[0][:200]))
        confidence = f"{concept.confidence_score:.2f}" if concept.confidence_score else ""
        table.add_row("Confidence", confidence)
        console.print(table)

    rels = r.get("relationships")
    if relationships and rels:
        table = Table(title="get_relationships")
        table.add_column("Relation", style="yellow")
        table.add_column("Related ID", style="cyan")
        table.add_column("Related Name", style="bold")
        table.add_column("Source", style="green")
        for rel in rels[:10]:
            table.add_row(
                str(rel.get("relation_label", "")),
                str(rel.get("related_id", "")),
                str(rel.get("related_name", "")),
                str(rel.get("source", "")),
            )
        console.print(table)

    console.print(
        f"\n[bold {'green' if _check_passed(r) else 'red'}]"
        f"{'PASS' if _check_passed(r) else 'FAIL'}[/bold {'green' if _check_passed(r) else 'red'}]"
    )


def _print_check_table(results: list[dict[str, Any]]) -> None:
    """Compact summary table for the 'all' path."""
    step_names = ["search_concepts", "get_concept_details", "get_relationships"]

    table = Table(title="Adapter Check Results")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Available", no_wrap=True)
    for name in step_names:
        table.add_column(name, no_wrap=True)
    table.add_column("Time", no_wrap=True)
    table.add_column("Notes", max_width=40)

    for r in results:
        if _check_skipped(r):
            table.add_row(
                r["source"].value, "[yellow]skipped[/yellow]", "-", "-", "-", "-", r["skipped"]
            )
            continue
        if not r["available"]:
            table.add_row(r["source"].value, "[red]no[/red]", "-", "-", "-", "-", "")
            continue

        steps_by_name = {name: (ok, detail, elapsed) for name, ok, detail, elapsed in r["steps"]}
        row = [r["source"].value, "[green]yes[/green]"]
        total_time = 0.0
        note = ""
        for name in step_names:
            if name not in steps_by_name:
                row.append("[dim]-[/dim]")
                continue
            ok, detail, elapsed = steps_by_name[name]
            total_time += elapsed
            row.append("[green]ok[/green]" if ok else "[red]fail[/red]")
            if not ok:
                note = detail
        row.append(f"{total_time:.2f}s")
        row.append(escape(note))
        table.add_row(*row)

    console.print(table)
    skipped = sum(1 for r in results if _check_skipped(r))
    tested = len(results) - skipped
    passed = sum(1 for r in results if _check_passed(r))
    summary = f"{passed}/{tested} sources passed"
    if skipped:
        summary += f" ({skipped} skipped: credentials not configured)"
    console.print(f"\n[bold]{summary}[/bold]")


@app.command()
def check(
    source: str = typer.Argument(
        ...,
        help="Knowledge source to test (e.g. WIKIPATHWAYS, STRING), or 'all' to smoke-test "
        "every source with an adapter",
    ),
    query: str | None = typer.Option(
        None,
        "--query",
        "-q",
        help="Search term used to drive the smoke test (default: BRCA1, or a term that "
        "suits the source, e.g. 'aspirin' for chemistry sources)",
    ),
    concept_id: str | None = typer.Option(
        None,
        "--id",
        help="Skip search_concepts and test get_concept_details/get_relationships on this "
        "ID directly",
    ),
    relationships: bool = typer.Option(
        True,
        "--relationships/--no-relationships",
        help="Also exercise get_relationships on the resolved concept",
    ),
    timeout: float = typer.Option(
        60.0, "--timeout", help="Per-call timeout in seconds (applies to each step)"
    ),
):
    """
    Smoke-test one (or every) adapter end-to-end against its live API.

    Runs ``search_concepts`` -> ``get_concept_details`` -> ``get_relationships``
    (in that order, feeding each step's result into the next) and reports
    per-step pass/fail, timing and a data preview. Use this to verify a new or
    modified adapter actually works before wiring it deeper into the codebase,
    instead of writing a throwaway script.

    Examples:
      knowledge-lookup check WIKIPATHWAYS --query "interleukin"
      knowledge-lookup check STRING --id STRING:9606.ENSP00000269305
      knowledge-lookup check all --query "diabetes" --no-relationships
    """
    lookup = CentralKnowledgeLookup()

    if source.strip().lower() == "all":
        targets = sorted(SOURCE_CATALOG.keys(), key=lambda s: s.value)
    else:
        try:
            targets = [KnowledgeSource(normalize_source_name(source))]
        except ValueError:
            console.print(f"[red]Error:[/red] Unknown source '{source}'")
            console.print(f"Available sources: {', '.join(s.value for s in SOURCE_CATALOG)}")
            raise typer.Exit(1) from None

    async def _run() -> list[dict[str, Any]]:
        try:
            results = []
            for src in targets:
                if len(targets) > 1:
                    console.print(f"[dim]Checking {src.value}...[/dim]")
                results.append(
                    await _check_source(
                        lookup,
                        src,
                        query or _CHECK_QUERIES.get(src, _CHECK_DEFAULT_QUERY),
                        concept_id,
                        relationships,
                        timeout,
                    )
                )
            return results
        finally:
            await lookup.close()

    results = asyncio.run(_run())

    if len(targets) == 1:
        _print_check_detail(results[0], relationships)
    else:
        _print_check_table(results)

    if not all(_check_passed(r) or _check_skipped(r) for r in results):
        raise typer.Exit(1)


@app.command("semmeddb-build")
def semmeddb_build(
    sources: list[Path] = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="NLM SemMedDB PREDICATION download(s): semmedVER43_2024_R_PREDICATION.sql.gz "
        "(MySQL dump) or the .csv.gz export; .gz optional",
    ),
    output: Path = typer.Option(
        ..., "--output", "-o", help="SQLite file to create (set SEMMEDDB_PATH to it afterwards)"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing output file"),
    aggregates: bool = typer.Option(
        True,
        "--aggregates/--no-aggregates",
        help="Precompute the CONCEPT and TRIPLE lookup tables (strongly recommended; adds "
        "build time and disk but keeps name search and hub concepts fast)",
    ),
    max_rows: int | None = typer.Option(
        None,
        "--max-rows",
        min=1,
        help="Only load the first N rows: a quick format check before a multi-hour build",
    ),
):
    """
    Convert a SemMedDB download into the SQLite database the SemMedDB adapter reads.

    SemMedDB has no public API: download the PREDICATION table from NLM (free UTS login,
    https://lhncbc.nlm.nih.gov/ii/tools/SemRep_SemMedDB_SKR/SemMedDB_download.html), then run
    this once. It streams the file (any size), loads the PREDICATION table and indexes it.
    The full final release (VER43, ~130 million predications) takes hours and tens of GB.

    Example:
      knowledge-lookup semmeddb-build semmedVER43_2024_R_PREDICATION.sql.gz -o semmeddb.sqlite
      export SEMMEDDB_PATH=$PWD/semmeddb.sqlite

    Check the format first with a small sample (seconds):
      knowledge-lookup semmeddb-build semmedVER43_2024_R_PREDICATION.csv.gz -o /tmp/s.sqlite \\
          --max-rows 100000
    """
    from knowledge_lookup.adapters._semmeddb_build import build_predication_db

    def report(rows: int, skipped: int) -> None:
        extra = f", {skipped:,} malformed rows skipped" if skipped else ""
        console.print(f"[dim]  {rows:,} predications loaded{extra}[/dim]")

    console.print(f"[bold]Building {output}[/bold] from {len(sources)} file(s)")
    try:
        stats = build_predication_db(
            sources,
            output,
            overwrite=force,
            progress=report,
            max_rows=max_rows,
            aggregates=aggregates,
        )
    except FileExistsError as e:
        console.print(f"[red]Error:[/red] {e}; pass --force to replace it")
        raise typer.Exit(1) from None
    except (ValueError, OSError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Done:[/green] {stats.rows:,} predications in {stats.seconds:,.0f}s "
        f"(indexes {stats.index_seconds:,.0f}s, lookup tables {stats.aggregate_seconds:,.0f}s), "
        f"{stats.skipped:,} skipped"
    )
    console.print(f"Next: export SEMMEDDB_PATH={output.resolve()}")


@app.command()
def info():
    """
    Show information about the Biomedical Knowledge Lookup package.
    """
    console.print("[bold blue]Biomedical Knowledge Lookup[/bold blue]")
    console.print(f"Version: {__version__}")
    console.print(f"Description: {__description__}")
    console.print("Repository: https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup")

    # Check available sources (every source with an adapter)
    lookup = CentralKnowledgeLookup()
    available_sources = [s.value for s in SOURCE_CATALOG if lookup._get_adapter(s)]
    console.print(f"Available sources: {len(available_sources)}/{len(SOURCE_CATALOG)}")


@app.command()
def benchmark(
    quick: bool = typer.Option(
        False,
        "--quick",
        "-q",
        help="Run only single-source + parallel speedup benchmarks (faster)",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Save results as JSON to this path",
    ),
):
    """
    Run system scalability benchmarks (single-source, parallel speedup, circuit breaker, concurrent, annotator).

    Reports per-adapter latency, parallel vs sequential speedup, and
    circuit breaker isolation behaviour.
    """
    from knowledge_lookup.benchmarks.run_benchmark import main as _benchmark_main

    asyncio.run(_benchmark_main(quick=quick, output=output))


@app.command()
def explore(
    port: int = typer.Option(8080, "--port", "-p", help="Port for the web UI"),
    open_browser: bool = typer.Option(
        True, "--browser/--no-browser", help="Open browser automatically"
    ),
):
    """
    Launch an interactive API explorer web UI for browsing UMLS concepts.

    Starts a lightweight web server with a search interface and REST API
    endpoints for exploring UMLS concepts, crosswalk codes, and
    terminology downloads.

    This is useful for interactive discovery without writing code.
    """
    import webbrowser

    url = f"http://localhost:{port}"

    console.print(f"[bold green]Starting UMLS Explorer on {url}[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    if open_browser:
        webbrowser.open(url)

    _run_explorer_server(port=port)


def _run_explorer_server(port: int = 8080) -> None:
    """Run the explorer web server (blocking).

    Serves a minimal web UI and REST API for UMLS exploration.
    """
    import http.server
    import urllib.parse

    class ExplorerHandler(http.server.BaseHTTPRequestHandler):
        """HTTP request handler for the UMLS explorer."""

        def log_message(self, fmt, *args):  # pragma: no cover
            """Suppress default HTTP log output."""
            pass

        def do_GET(self):  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/":
                self._serve_html()
            elif parsed.path == "/api/search":
                asyncio.run(self._handle_search(params))
            elif parsed.path == "/api/crosswalk":
                asyncio.run(self._handle_crosswalk(params))
            elif parsed.path == "/api/health":
                self._json_response({"status": "ok"})
            else:
                self.send_response(404)
                self.end_headers()

        def _serve_html(self):  # pragma: no cover
            """Serve the explorer web UI."""
            html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UMLS Explorer</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f7fa; color: #333; padding: 2rem; }
  .container { max-width: 1000px; margin: 0 auto; }
  h1 { margin-bottom: 0.5rem; color: #1a73e8; }
  .subtitle { color: #666; margin-bottom: 2rem; }
  .card { background: #fff; border-radius: 8px; padding: 1.5rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }
  .card h2 { margin-bottom: 1rem; font-size: 1.1rem; }
  input, select { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px;
                   font-size: 0.95rem; width: 100%; margin-bottom: 0.75rem; }
  button { background: #1a73e8; color: #fff; border: none; padding: 0.5rem 1.25rem;
            border-radius: 4px; cursor: pointer; font-size: 0.95rem; }
  button:hover { background: #1557b0; }
  pre { background: #f0f0f0; padding: 1rem; border-radius: 4px;
        overflow-x: auto; font-size: 0.85rem; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 0.5rem; text-align: left; border-bottom: 1px solid #eee; }
  th { font-weight: 600; color: #555; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px;
            font-size: 0.75rem; font-weight: 600; background: #e3f2fd; color: #1565c0; }
  .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .tab { padding: 0.5rem 1rem; cursor: pointer; border-radius: 4px 4px 0 0;
          background: #e0e0e0; }
  .tab.active { background: #fff; font-weight: 600; }
  .panel { display: none; }
  .panel.active { display: block; }
</style>
</head>
<body>
<div class="container">
  <h1>🔬 UMLS Explorer</h1>
  <p class="subtitle">Interactive exploration of the Unified Medical Language System</p>

  <div class="tabs">
    <div class="tab active" onclick="switchTab('search')">🔍 Search</div>
    <div class="tab" onclick="switchTab('crosswalk')">🔄 Crosswalk</div>
  </div>

  <!-- Search Panel -->
  <div id="panel-search" class="panel active">
    <div class="card">
      <h2>Search UMLS Concepts</h2>
      <input type="text" id="search-query" placeholder="e.g. cardiomyopathy, diabetes, BRCA1"
             onkeydown="if(event.key==='Enter') doSearch()">
      <div style="display:flex; gap:0.5rem;">
        <input type="text" id="search-sabs" placeholder="Source (optional, e.g. SNOMEDCT_US)" style="flex:2">
        <input type="number" id="search-limit" placeholder="Limit" value="10" style="flex:1">
      </div>
      <button onclick="doSearch()">Search</button>
    </div>
    <div id="search-results"></div>
  </div>

  <!-- Crosswalk Panel -->
  <div id="panel-crosswalk" class="panel">
    <div class="card">
      <h2>Crosswalk Codes Between Vocabularies</h2>
      <input type="text" id="xw-source" placeholder="Source vocab (e.g. ICD10CM)">
      <input type="text" id="xw-code" placeholder="Code (e.g. E11.9)">
      <input type="text" id="xw-target" placeholder="Target vocab (optional, e.g. SNOMEDCT_US)">
      <button onclick="doCrosswalk()">Convert</button>
    </div>
    <div id="crosswalk-results"></div>
  </div>
</div>

<script>
function switchTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.target.classList.add('active');
}

async function doSearch() {
  const q = document.getElementById('search-query').value;
  const sabs = document.getElementById('search-sabs').value;
  const limit = document.getElementById('search-limit').value || 10;
  const el = document.getElementById('search-results');
  el.innerHTML = '<p>Loading...</p>';
  try {
    const params = new URLSearchParams({query: q, limit, sabs});
    const resp = await fetch('/api/search?' + params);
    const data = await resp.json();
    if (!data.results || data.results.length === 0) {
      el.innerHTML = '<p>No results found.</p>';
      return;
    }
    let html = `<table><tr><th>CUI</th><th>Name</th><th>Source</th><th>Score</th></tr>`;
    for (const r of data.results) {
      html += `<tr><td><code>${r.cui}</code></td><td>${r.name}</td><td><span class="badge">${r.source || 'UMLS'}</span></td><td>${(r.score * 100).toFixed(0)}%</td></tr>`;
    }
    html += '</table>';
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<p style="color:red">Error: ' + e.message + '</p>';
  }
}

async function doCrosswalk() {
  const source = document.getElementById('xw-source').value;
  const code = document.getElementById('xw-code').value;
  const target = document.getElementById('xw-target').value;
  const el = document.getElementById('crosswalk-results');
  el.innerHTML = '<p>Loading...</p>';
  try {
    const params = new URLSearchParams({source, code, target_source: target});
    const resp = await fetch('/api/crosswalk?' + params);
    const data = await resp.json();
    if (!data.results || data.results.length === 0) {
      el.innerHTML = '<p>No mappings found.</p>';
      return;
    }
    let html = `<table><tr><th>CUI</th><th>Name</th><th>Source</th><th>Code</th></tr>`;
    for (const r of data.results) {
      html += `<tr><td><code>${r.cui}</code></td><td>${r.name}</td><td>${r.source}</td><td>${r.source_id || '-'}</td></tr>`;
    }
    html += '</table>';
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<p style="color:red">Error: ' + e.message + '</p>';
  }
}
</script>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        async def _handle_search(self, params: dict[str, list[str]]) -> None:
            query = params.get("query", [""])[0]
            limit = int(params.get("limit", ["10"])[0])
            sabs = params.get("sabs", [None])[0] or None

            lookup = CentralKnowledgeLookup()
            adapter = lookup._get_adapter(KnowledgeSource.UMLS)

            if adapter is None or not adapter.is_available():
                self._json_response({"error": "UMLS adapter not available"}, status=503)
                return

            umls_adapter = cast("UMLSAdapter", adapter)
            results = await umls_adapter.search_concepts(query, limit=limit, sabs=sabs)
            self._json_response(
                {
                    "query": query,
                    "results": [
                        {
                            "cui": r.primary_id,
                            "name": r.primary_label,
                            "source": r.sources[0] if r.sources else None,
                            "score": r.confidence_score,
                        }
                        for r in results
                    ],
                }
            )

        async def _handle_crosswalk(self, params: dict[str, list[str]]) -> None:
            source = params.get("source", [""])[0]
            code = params.get("code", [""])[0]
            target_source = params.get("target_source", [None])[0] or None

            if not source or not code:
                self._json_response({"error": "source and code are required"}, status=400)
                return

            lookup = CentralKnowledgeLookup()
            adapter = lookup._get_adapter(KnowledgeSource.UMLS)

            if adapter is None or not adapter.is_available():
                self._json_response({"error": "UMLS adapter not available"}, status=503)
                return

            umls_adapter = cast("UMLSAdapter", adapter)
            results = await umls_adapter.get_mappings(code, target_source=target_source or "")
            self._json_response(
                {
                    "source": f"{source}:{code}",
                    "results": [
                        {
                            "cui": r["cui"],
                            "name": r["name"],
                            "source": r["source"],
                            "source_id": r.get("source_id", ""),
                        }
                        for r in results
                    ],
                }
            )

        def _json_response(self, data: dict, status: int = 200) -> None:
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.HTTPServer(("127.0.0.1", port), ExplorerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Explorer stopped.[/yellow]")
        server.server_close()


if __name__ == "__main__":
    app()
