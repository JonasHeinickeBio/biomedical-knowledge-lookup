#!/usr/bin/env python3
"""
Command-line interface for Biomedical Knowledge Lookup.

A unified tool for biological concept lookup across multiple biomedical knowledge sources.
"""

import asyncio
import json
from typing import Optional  # noqa: UP035

import typer
from rich.console import Console
from rich.table import Table

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, __description__, __version__

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
    sources: Optional[list[str]] = typer.Option(  # noqa: UP007
        None,
        "--source",
        "-s",
        help="Knowledge sources to search (default: all available)",
    ),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results per source"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Cache directory path"),
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

        async def do_search():
            results = await lookup.search_concepts(
                query=query, sources=source_enums, max_results=limit
            )
            return results

        results = asyncio.run(do_search())

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
                        "source": list(r.sources)[0].value if r.sources else None,
                        "type": r.concept_type.value,
                        "uri": None,  # UnifiedConcept doesn't have URI
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
                        list(result.sources)[0].value if result.sources else "",
                        result.concept_type.value,
                        "",  # No URI in UnifiedConcept
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
                    list(result.sources)[0].value if result.sources else "",
                    result.concept_type.value,
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


if __name__ == "__main__":
    app()
