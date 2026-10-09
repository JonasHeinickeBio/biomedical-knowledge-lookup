#!/usr/bin/env python3
"""Regenerate every place that lists the knowledge sources.

Writes, from the adapter pages and ``_source_taxonomy.TAXONOMY``:

* ``docs/SUMMARY.md``           the GitBook sidebar (hand-written parts live in this script)
* ``docs/adapters/README.md``   everything after the "## All adapters" heading
* ``docs/README.md`` and ``README.md``   the blocks between
  ``<!-- sources:start -->`` and ``<!-- sources:end -->``

Usage:
    poetry run python scripts/build_source_index.py          # rewrite the files
    poetry run python scripts/build_source_index.py --check  # exit 1 if they are stale
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _source_taxonomy import ROOT, TAXONOMY, SourceMeta, load_sources  # noqa: E402

SUMMARY_HEAD = """\
# Table of contents

* [Introduction](README.md)

## Getting started

* [Installation](getting-started/installation.md)
* [Quickstart](getting-started/quickstart.md)
* [Configuration](getting-started/configuration.md)
* [Troubleshooting and FAQ](getting-started/troubleshooting.md)
* [Upgrading to 2.0](getting-started/upgrading-to-2.0.md)

## Guides

* [Searching concepts](guides/searching-concepts.md)
* [Term expansion](guides/term-expansion.md)
* [Multi-source annotation](guides/multi-source-annotation.md)
* [CURIE management](guides/curie-management.md)
* [Caching](guides/caching.md)
* [Exporting results](guides/exporting-results.md)
* [Command-line interface](guides/cli.md)
* [Agent workflow](guides/agent-workflow.md)
* [MCP server](guides/mcp-server.md)

## Choosing sources

* [Which source for which question](guides/choosing-sources.md)
* [Recipes](guides/recipes.md)
* [What each source returns](guides/data-coverage.md)
* [All adapters](adapters/README.md)
"""

SUMMARY_TAIL = """
## Examples

* [Examples overview](examples/README.md)
* [Use cases](examples/use-cases.md)
* [Source availability](examples/availability-status.md)
* [Notebooks](examples/notebooks/README.md)

## Reference

* [API reference](reference/api-reference.md)
* [Architecture](reference/architecture.md)
* [Environment variables](reference/environment-variables.md)
* [Glossary](reference/glossary.md)

## Project

* [Contributing](contributing/README.md)
* [Writing an adapter](contributing/writing-an-adapter.md)
* [Changelog](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/CHANGELOG.md)
"""


def esc(s: str) -> str:
    return s.replace("|", "\\|")


def by_group(sources: list[SourceMeta]) -> dict[str, list[SourceMeta]]:
    out: dict[str, list[SourceMeta]] = {k: [] for k, *_ in TAXONOMY}
    for s in sources:
        out[s.group].append(s)
    return out


def build_summary(sources: list[SourceMeta]) -> str:
    groups = by_group(sources)
    parts = [SUMMARY_HEAD]
    for key, title, _blurb, _m in TAXONOMY:
        parts.append(f"\n## Sources: {title}\n")
        parts.extend(f"* [{s.title}]({s.path})" for s in groups[key])
    parts.append(SUMMARY_TAIL)
    return "\n".join(parts)


def build_adapter_index(sources: list[SourceMeta]) -> str:
    groups = by_group(sources)
    out = [
        f"## All adapters\n\nThe {len(sources)} adapters are grouped by what they are used for. "
        '"Access" says what you need before the adapter works; most need nothing.\n'
    ]
    for key, title, blurb, _m in TAXONOMY:
        out.append(f"### {title}\n\n{blurb}\n")
        out.append("| Adapter | Covers | Identifier example | Access |\n|---|---|---|---|")
        for s in groups[key]:
            link = s.path.removeprefix("adapters/")
            out.append(
                f"| [{esc(s.title)}]({link}) | {esc(s.short_description)} | "
                f"{esc(s.identifiers)} | {esc(s.requires)} |"
            )
        out.append("")
    return "\n".join(out)


def overview_table(sources: list[SourceMeta], prefix: str) -> str:
    groups = by_group(sources)
    rows = ["| Domain | Sources | Examples |", "|---|---|---|"]
    for key, title, blurb, _m in TAXONOMY:
        names = ", ".join(s.title.split(" (")[0] for s in groups[key][:5])
        more = f" and {len(groups[key]) - 5} more" if len(groups[key]) > 5 else ""
        rows.append(f"| **{title}**<br>{blurb} | {len(groups[key])} | {esc(names)}{more} |")
    return "\n".join(rows)


def readme_sources(sources: list[SourceMeta]) -> str:
    groups = by_group(sources)
    n_open = sum(1 for s in sources if s.access == "Open")
    out = [
        f"{len(sources)} adapters in {len(TAXONOMY)} domains; {n_open} work with no key, extra or "
        "download. Use the name as `KnowledgeSource.<NAME>` in Python or `--source <NAME>` on the "
        "CLI.\n",
        overview_table(sources, "docs/"),
        "\n<details>\n<summary><strong>Every source by name, with what it needs</strong></summary>\n",
    ]
    tags = {
        "Key or login": "key",
        "Extra": "extra",
        "Opt-in download": "download",
        "Local file": "file",
    }
    for key, title, _blurb, _m in TAXONOMY:
        names = " · ".join(
            f"[`{s.name}`](docs/{s.path})" + (f" ({tags[s.access]})" if s.access in tags else "")
            for s in groups[key]
        )
        out.append(f"\n**{title}**: {names}")
    out.append("\n</details>")
    out.append(
        "\n*No tag* means the source needs nothing. *(key)* needs a free key or account, *(extra)* a "
        "pip extra, *(download)* an opt-in dataset download (`<NAME>_DOWNLOAD=1`), *(file)* a file you "
        "provide. See [which source for which question]"
        "(docs/guides/choosing-sources.md) for what to use when."
    )
    return "\n".join(out)


def docs_home_sources(sources: list[SourceMeta]) -> str:
    return overview_table(sources, "")


def replace_block(path: Path, start: str, end: str, body: str) -> str:
    text = path.read_text(encoding="utf-8")
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(text):
        raise SystemExit(f"{path}: markers {start} ... {end} not found")
    return pat.sub(lambda _m: f"{start}\n{body}\n{end}", text, count=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    sources = load_sources()

    new: dict[Path, str] = {ROOT / "docs/SUMMARY.md": build_summary(sources)}
    idx = ROOT / "docs/adapters/README.md"
    text = idx.read_text(encoding="utf-8")
    new[idx] = text[: text.index("## All adapters")] + build_adapter_index(sources)
    new[ROOT / "README.md"] = replace_block(
        ROOT / "README.md",
        "<!-- sources:start -->",
        "<!-- sources:end -->",
        readme_sources(sources),
    )
    new[ROOT / "docs/README.md"] = replace_block(
        ROOT / "docs/README.md",
        "<!-- sources:start -->",
        "<!-- sources:end -->",
        docs_home_sources(sources),
    )

    stale = [p for p, t in new.items() if p.read_text(encoding="utf-8") != t]
    if args.check:
        for p in stale:
            print("stale:", p.relative_to(ROOT))
        sys.exit(1 if stale else 0)
    for p, t in new.items():
        p.write_text(t, encoding="utf-8")
    print(f"updated {len(stale)} file(s); {len(sources)} sources")


if __name__ == "__main__":
    main()
