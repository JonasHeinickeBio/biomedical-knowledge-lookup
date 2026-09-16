#!/usr/bin/env python3
"""Read release facts from CHANGELOG.md for .github/workflows/release-draft.yml.

Subcommands:
  top-version      print the version of the newest `## [X.Y.Z]` section
  notes VERSION    print the body of the `## [VERSION]` section
  has-unreleased   exit 0 if `## [Unreleased]` has entries, 1 if it is empty
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cut_changelog import is_empty, split_unreleased_section  # noqa: E402

VERSION_HEADING_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\][^\n]*$", re.MULTILINE)
ANY_HEADING_RE = re.compile(r"^## \[[^\]]+\][^\n]*$", re.MULTILINE)


def top_version(changelog: str) -> str:
    match = VERSION_HEADING_RE.search(changelog)
    if not match:
        raise SystemExit("ERROR: no '## [X.Y.Z]' section found in CHANGELOG.md")
    return match.group(1)


def section_notes(changelog: str, version: str) -> str:
    headings = list(ANY_HEADING_RE.finditer(changelog))
    for index, heading in enumerate(headings):
        if heading.group(0).startswith(f"## [{version}]"):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
            return changelog[heading.end() : end].strip() + "\n"
    raise SystemExit(f"ERROR: no '## [{version}]' section found in CHANGELOG.md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changelog", default="CHANGELOG.md", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("top-version")
    notes = commands.add_parser("notes")
    notes.add_argument("version")
    commands.add_parser("has-unreleased")
    args = parser.parse_args()

    changelog = args.changelog.read_text(encoding="utf-8")
    if args.command == "top-version":
        print(top_version(changelog))
    elif args.command == "notes":
        sys.stdout.write(section_notes(changelog, args.version))
    else:
        _, unreleased_body, _ = split_unreleased_section(changelog)
        return 1 if is_empty(unreleased_body) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
