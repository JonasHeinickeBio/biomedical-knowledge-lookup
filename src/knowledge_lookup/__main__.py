#!/usr/bin/env python3
"""
Command-line interface for Biomedical Knowledge Lookup.

A unified tool for biological concept lookup across multiple biomedical knowledge sources.
"""

import asyncio
import json
from typing import cast

import typer
from rich.console import Console
from rich.table import Table

from knowledge_lookup import (
    CentralKnowledgeLookup,
    KnowledgeSource,
    LookupResult,
    __description__,
    __version__,
)

try:
    from knowledge_lookup.adapters.umls_adapter import UMLSAdapter
except ImportError:
    UMLSAdapter = None  # type: ignore[assignment,misc]

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

    Search for biological concepts across 29+ biomedical knowledge sources.
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
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results per source"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Cache directory path"),
    partial: bool = typer.Option(
        False, "--partial", "-p", help="Enable partial/fuzzy matching (UMLS adapter)"
    ),
):
    """
    Search for biological concepts across knowledge sources.
    """
    try:
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

        async def do_search(lkp=None):
            if partial and (source_enums is None or KnowledgeSource.UMLS in source_enums):
                # Direct UMLS adapter call with partial_search enabled
                lkp = CentralKnowledgeLookup()
                umls_adapter = lkp._get_adapter(KnowledgeSource.UMLS)
                if umls_adapter and umls_adapter.is_available():
                    umls_adapter_casted = cast("UMLSAdapter", umls_adapter)
                    umls_concepts = await umls_adapter_casted.search_concepts(
                        query, limit=limit, partial_search=True
                    )
                    result = LookupResult(query=query)
                    result.add_concepts(umls_concepts, KnowledgeSource.UMLS)
                    return result
            return await lkp.search_concepts(
                query=query,
                sources=source_enums,
                max_results=limit,
            )

        results = asyncio.run(do_search(lookup))

        if not results.concepts:
            console.print("[yellow]No results found.[/yellow]")
            return

        # Output results
        if output == "json":
            output_data = {
                "query": query,
                "sources": [s.value for s in (source_enums or list(KnowledgeSource))],
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
        None, "--source", "-s", help="Knowledge sources to search"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    export_formats: list[str] = typer.Option(
        ["json"], "--format", "-f", help="Export formats (json, csv, ttl)"
    ),
    export_path: str | None = typer.Option(
        None, "--export-path", "-e", help="Export directory path"
    ),
    max_iterations: int = typer.Option(3, "--max-iter", help="Maximum refinement rounds"),
    auto_approve: float = typer.Option(0.8, "--auto-approve", help="Auto-approve threshold (0-1)"),
    concept_types: list[str] | None = typer.Option(
        None, "--type", "-t", help="Filter by concept types"
    ),
):
    """
    Run the intelligent agent workflow with review and approval.

    The workflow performs:
    1. Parallel lookup across knowledge sources
    2. Automated quality review with scoring
    3. Human approval gate (or auto-approve if score is high enough)
    4. Optional refinement rounds based on feedback
    5. Export to configured formats
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
        )

    result = asyncio.run(_run())

    # Display review
    if result.get("review_score") is not None:
        score = result["review_score"]
        color = "green" if score >= auto_approve else "yellow" if score >= 0.5 else "red"
        console.print(f"\n[bold {color}]Review Score: {score:.2f}[/bold {color}]")
        if result.get("review_summary"):
            console.print(f"[dim]{result['review_summary']}[/dim]")

    # Check if paused for approval
    if result.get("status") == "awaiting_approval":
        console.print("\n[bold yellow]Workflow paused for approval.[/bold yellow]")
        console.print(f"Thread ID: {result['thread_id']}")

        # Show concept preview
        res = result.get("result")
        if res and res.concepts:
            console.print(f"\n[bold]Found {len(res.concepts)} concepts:[/bold]")
            table = Table()
            table.add_column("ID", style="cyan")
            table.add_column("Label", style="bold")
            table.add_column("Type", style="yellow")
            table.add_column("UMLS CUI", style="magenta")
            table.add_column("Confidence", style="green")
            for c in res.concepts[:10]:
                umls_cui = _get_concept_umls_cui(c)
                table.add_row(
                    c.primary_id,
                    c.primary_label or "",
                    str(c.concept_type) if c.concept_type else "",
                    umls_cui or "-",
                    f"{c.confidence_score:.2f}" if c.confidence_score else "",
                )
            console.print(table)

        # Interactive approval
        approve = typer.confirm("Do you approve these results?")
        if approve:
            decision = {"approved": True}
        else:
            refine = typer.confirm("Would you like to refine the search?")
            if refine:
                notes = typer.prompt("Enter refinement notes (or press Enter to skip)", default="")
                decision = {"approved": False, "refine": True, "notes": notes}
            else:
                decision = {"approved": False, "refine": False}

        async def _resume():
            return await resume_workflow(result["thread_id"], decision)

        final = asyncio.run(_resume())
        result = final

    # Display final results
    if result.get("status") == "completed":
        console.print("\n[bold green]Workflow completed![/bold green]")
        res = result.get("result")
        if res and res.concepts:
            console.print(f"[bold]Final results: {len(res.concepts)} concepts[/bold]")
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


@app.command()
def sources():
    """
    List all available knowledge sources.
    """
    table = Table(title="Available Knowledge Sources")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Requires API Key", style="yellow")

    source_info = {
        KnowledgeSource.BIOPORTAL: ("NCBI BioPortal ontology repository", True),
        KnowledgeSource.OLS: ("Ontology Lookup Service", False),
        KnowledgeSource.UMLS: ("Unified Medical Language System", True),
        KnowledgeSource.CHEMBL: ("Chemical database", False),
        KnowledgeSource.DISGENET: ("Disease-gene associations", False),
        KnowledgeSource.DRUGBANK: ("Drug information database", False),
        KnowledgeSource.ENSEMBL: ("Genome annotation database", False),
        KnowledgeSource.GO: ("Gene Ontology", False),
        KnowledgeSource.HPO: ("Human Phenotype Ontology", False),
        KnowledgeSource.MONDO: ("Mondo Disease Ontology", False),
        KnowledgeSource.OPENTARGETS: ("Target-disease associations", False),
        KnowledgeSource.PUBCHEM: ("Chemical information", False),
        KnowledgeSource.REACTOME: ("Pathway database", False),
        KnowledgeSource.UNIPROT: ("Protein sequence database", False),
        KnowledgeSource.WIKIDATA: ("Structured knowledge base", False),
        KnowledgeSource.ZOOMA: ("Ontology mapping service", False),
    }

    for source, (description, requires_key) in source_info.items():
        table.add_row(source.value, description, "Yes" if requires_key else "No")

    console.print(table)
    console.print(f"\n[dim]Total sources: {len(KnowledgeSource)}[/dim]")


@app.command()
def info():
    """
    Show information about the Biomedical Knowledge Lookup package.
    """
    console.print("[bold blue]Biomedical Knowledge Lookup[/bold blue]")
    console.print(f"Version: {__version__}")
    console.print(f"Description: {__description__}")
    console.print("Repository: https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup")

    # Check available sources
    lookup = CentralKnowledgeLookup()
    available_sources = [s.value for s in KnowledgeSource if lookup._get_adapter(s)]
    console.print(f"Available sources: {len(available_sources)}/{len(KnowledgeSource)}")


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
