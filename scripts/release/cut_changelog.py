#!/usr/bin/env python3
"""Cut the `[Unreleased]` section of CHANGELOG.md into a new dated version
section, and print the next version number.

Used by .github/workflows/release-draft.yml on every push to `main`: it
decides whether there's anything to release, what the next version should
be (semver bump inferred from the Unreleased section's content), and
rewrites CHANGELOG.md accordingly. Also writes the cut section's body to
a separate file so it can be used as GitHub Release notes.

Exit codes:
  0 - cut a release; printed "version=X.Y.Z" and wrote --notes-out
  2 - nothing to release (Unreleased section is empty) — not an error,
      the caller should just skip creating a release
  1 - unexpected error (bad CHANGELOG.md shape, bad current version, ...)
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)
NEXT_VERSION_HEADING_RE = re.compile(r"^## \[", re.MULTILINE)
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def latest_tag_version() -> tuple[int, int, int]:
    """Return the latest `vX.Y.Z` tag's version, or (0, 0, 0) if none exist."""
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match=v*"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return (0, 0, 0)
    m = VERSION_RE.match(out)
    if not m:
        raise SystemExit(f"ERROR: latest tag {out!r} is not a vX.Y.Z tag")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def split_unreleased_section(changelog: str) -> tuple[str, str, str]:
    """Return (before, unreleased_body, after) for CHANGELOG.md's content.

    `before` ends right after the "## [Unreleased]" heading line (with its
    trailing newline); `unreleased_body` is everything up to (not including)
    the next "## [" heading; `after` is that heading onward.
    """
    m = UNRELEASED_RE.search(changelog)
    if not m:
        raise SystemExit("ERROR: no '## [Unreleased]' heading found in CHANGELOG.md")
    before = changelog[: m.end()]
    rest = changelog[m.end() :]
    next_heading = NEXT_VERSION_HEADING_RE.search(rest)
    if not next_heading:
        raise SystemExit("ERROR: no version heading found after '## [Unreleased]'")
    unreleased_body = rest[: next_heading.start()]
    after = rest[next_heading.start() :]
    return before, unreleased_body, after


def is_empty(unreleased_body: str) -> bool:
    """True if the Unreleased section has no real content, only subsection
    headings like "### Added" / "### Fixed" with nothing under them."""
    for line in unreleased_body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("###"):
            continue
        return False
    return True


def bump(current: tuple[int, int, int], unreleased_body: str) -> tuple[int, int, int]:
    major, minor, patch = current
    # Deliberately narrow: matches this changelog's existing convention for
    # flagging a breaking change (e.g. "- **Breaking:** ..." or
    # "- **Breaking (internal):** ..."), not the word "breaking" anywhere in
    # prose (a bug-fix entry describing broken behavior is not a bump signal).
    if re.search(r"^\s*-\s*\*\*Breaking\b", unreleased_body, re.MULTILINE):
        return (major + 1, 0, 0)
    if re.search(r"^### Added\b", unreleased_body, re.MULTILINE):
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changelog", default="CHANGELOG.md", type=Path)
    parser.add_argument("--notes-out", default="release_notes.md", type=Path)
    parser.add_argument(
        "--github-output",
        help="Path to append version=X.Y.Z to (GITHUB_OUTPUT), optional",
    )
    args = parser.parse_args()

    changelog = args.changelog.read_text(encoding="utf-8")
    before, unreleased_body, after = split_unreleased_section(changelog)

    if is_empty(unreleased_body):
        print("Nothing to release: [Unreleased] section is empty.", file=sys.stderr)
        return 2

    current = latest_tag_version()
    next_version = bump(current, unreleased_body)
    version_str = f"{next_version[0]}.{next_version[1]}.{next_version[2]}"
    today = datetime.date.today().isoformat()

    # `before` ends right after "## [Unreleased]" (no trailing newline, per
    # the `$` in UNRELEASED_RE); `after` starts at the next "## [" heading.
    # Leave [Unreleased] empty and insert the cut content as a new, dated
    # version section directly beneath it.
    new_changelog = (
        f"{before}\n\n"
        f"## [{version_str}] - {today}\n\n"
        f"{unreleased_body.strip()}\n\n"
        f"{after}"
    )
    args.changelog.write_text(new_changelog, encoding="utf-8")
    args.notes_out.write_text(unreleased_body.strip() + "\n", encoding="utf-8")

    print(f"version={version_str}")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            f.write(f"version={version_str}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
