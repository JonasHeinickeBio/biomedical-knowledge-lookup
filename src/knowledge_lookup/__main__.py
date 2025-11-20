#!/usr/bin/env python3
"""
Command-line interface for Biomedical Knowledge Lookup.

A unified tool for biological concept lookup across multiple biomedical knowledge sources.
"""

import asyncio
import json
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

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
    sources: Optional[List[str]] = typer.Option(
        None,
        "--source",
        "-s",
        help="Knowledge sources to search (default: all available)",
    ),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results per source"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir", help="Cache directory path"),
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
                    raise typer.Exit(1)
        else:
            source_enums = None

        # Perform search
        console.print(f"[bold blue]Searching for:[/bold blue] {query}")
        if source_enums:
            console.print(
                f"[bold blue]Sources:[/bold blue] {', '.join([s.value for s in source_enums])}"
            )

        async def do_search():
            results = await lookup.search_concepts(query=query, sources=source_enums, limit=limit)
            return results

        results = asyncio.run(do_search())

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        # Output results
        if output == "json":
            output_data = {
                "query": query,
                "sources": [s.value for s in (source_enums or list(KnowledgeSource))],
                "total_results": len(results),
                "results": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "description": r.description,
                        "source": r.source.value,
                        "type": r.type.value if r.type else None,
                        "uri": r.uri,
                        "score": getattr(r, "score", None),
                    }
                    for r in results
                ],
            }
            console.print_json(json.dumps(output_data, indent=2))

            for result in results:
                writer.writerow(
                    [
                        result.id,
                        result.name,
                        result.description or "",
                        result.source.value,
                        result.type.value if result.type else "",
                        result.uri or "",
                        getattr(result, "score", ""),
                    ]
                )

        else:  # table format
            table = Table(title=f"Search Results for '{query}'")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="bold")
            table.add_column("Source", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Description", max_width=50)

            for result in results:
                table.add_row(
                    result.id,
                    result.name,
                    result.source.value,
                    result.type.value if result.type else "",
                    result.description or ""
                    if len(result.description or "") <= 50
                    else (result.description or "")[:47] + "...",
                )

            console.print(table)
            console.print(f"\n[bold green]Total results:[/bold green] {len(results)}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


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
    from knowledge_lookup import __description__, __version__

    console.print("[bold blue]Biomedical Knowledge Lookup[/bold blue]")
    console.print(f"Version: {__version__}")
    console.print(f"Description: {__description__}")
    console.print("Repository: https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup")

    # Check available sources
    lookup = CentralKnowledgeLookup()
    available_sources = [s.value for s in KnowledgeSource if lookup._get_adapter(s)]
    console.print(f"Available sources: {len(available_sources)}/{len(KnowledgeSource)}")


if __name__ == "__main__":
    app()
