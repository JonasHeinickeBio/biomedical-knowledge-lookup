#!/usr/bin/env python3
"""Turn the GitBook sources in ``docs/`` into GitHub wiki pages.

``docs/`` is the single source of truth. The wiki is flat, has no GitBook blocks and
resolves links by page name, so this script:

* names each page after its H1 (``Source-<name>`` for adapter pages, ``Home`` for the landing page),
* rewrites relative ``.md`` links to wiki page links and other repository links to GitHub URLs,
* converts ``{% hint %}``, ``{% tabs %}`` and ``{% code %}`` blocks to plain Markdown,
* adds a "generated from" banner to every page,
* builds ``_Sidebar.md`` from ``docs/SUMMARY.md`` and a ``_Footer.md``.

Usage:
    python scripts/build_wiki.py --out wiki-build

The GitHub Action ``.github/workflows/wiki.yml`` runs this on every push to ``main`` that
touches ``docs/`` and pushes the result to the wiki repository. Do not edit the wiki by hand.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPO = "JonasHeinickeBio/biomedical-knowledge-lookup"
BLOB = f"https://github.com/{REPO}/blob/main"
TREE = f"https://github.com/{REPO}/tree/main"

HINT_LABEL = {
    "info": "ℹ️ **Note**",
    "success": "✅ **Tip**",
    "warning": "⚠️ **Warning**",
    "danger": "🛑 **Caution**",
}
# [text](destination "optional title"): the destination is either <...> or text with at most one
# level of balanced parentheses (file names such as ``a_(b).md``).
LINK = re.compile(
    r"(?<!\!)\[([^\]]*)\]\((<[^>\n]*>|(?:[^()\s]|\([^()\s]*\))+)"
    r"(\s+(?:\"[^\"]*\"|'[^']*'))?\)"
)
FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


class Fence:
    """Track fenced code blocks the way CommonMark does.

    A fence closes only with the same character and at least as many of them as the opener,
    so a three-backtick line inside a four-backtick block stays literal.
    """

    def __init__(self) -> None:
        self.marker: str | None = None

    def feed(self, line: str) -> bool:
        """Return True when ``line`` is inside a fence or is a fence line itself."""
        m = FENCE_LINE.match(line)
        if self.marker is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                self.marker = m.group(1)
                return True
            return False
        if m and m.group(1)[0] == self.marker[0] and len(m.group(1)) >= len(self.marker):
            if not m.group(2).strip():
                self.marker = None
        return True


def sanitize(text: str) -> str:
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[^\w\s.+-]", "", text)  # no parentheses: they end Markdown link targets
    return re.sub(r"\s+", "-", text.strip()).strip("-")


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta, text[m.end() :]


def page_names() -> dict[Path, str]:
    names: dict[Path, str] = {}
    used: dict[str, Path] = {}
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(DOCS)
        if rel.as_posix() == "SUMMARY.md":
            continue
        _meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        h1 = re.search(r"^# (.+)$", body, re.M)
        title = h1.group(1).removesuffix(" adapter").strip() if h1 else path.stem
        if rel.as_posix() == "README.md":
            name = "Home"
        elif rel.parts[0] == "adapters" and len(rel.parts) == 3:
            name = "Source-" + sanitize(title)
        else:
            name = sanitize(title)
        if name in used:
            raise SystemExit(f"wiki page name clash: {name!r} for {rel} and {used[name]}")
        used[name] = rel
        names[path.resolve()] = name
    return names


def rewrite_link(target: str, src: Path, names: dict[Path, str]) -> str:
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return target
    path, _, anchor = target.partition("#")
    resolved = (src.parent / path).resolve()
    if resolved in names:
        return names[resolved] + (f"#{anchor}" if anchor else "")
    try:
        rel = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return target
    if resolved.is_dir():
        return f"{TREE}/{rel}"
    return f"{BLOB}/{rel}" + (f"#{anchor}" if anchor else "")


def rewrite_links(line: str, src: Path, names: dict[Path, str]) -> str:
    """Rewrite every Markdown link in ``line`` (angle-bracket and parenthesised targets included)."""

    def one(m: re.Match[str]) -> str:
        dest = m.group(2)
        if dest.startswith("<"):
            dest = dest[1:-1]
        new = rewrite_link(dest, src, names)
        if new == dest:  # external or in-page link: leave exactly as written
            return m.group(0)
        if re.search(r"[\s()]", new):
            new = f"<{new}>"
        return f"[{m.group(1)}]({new}{m.group(3) or ''})"

    return LINK.sub(one, line)


def convert_blocks(lines: list[str]) -> list[str]:
    """Replace GitBook blocks outside code fences with plain Markdown."""
    out: list[str] = []
    fence = Fence()
    in_hint = False
    for line in lines:
        if fence.feed(line):
            out.append(f"> {line}" if in_hint else line)
            continue
        stripped = line.strip()
        m = re.match(r'\{%\s*hint(?:\s+style="(\w+)")?\s*%\}', stripped)
        if m:
            in_hint = True
            out.append(f"> {HINT_LABEL.get(m.group(1) or 'info', HINT_LABEL['info'])}")
            out.append(">")
            continue
        if re.match(r"\{%\s*endhint\s*%\}", stripped):
            in_hint = False
            continue
        m = re.match(r'\{%\s*tab\s+title="([^"]+)"\s*%\}', stripped)
        if m:
            out.append(f"**{m.group(1)}**")
            continue
        m = re.match(r'\{%\s*code(?:\s+title="([^"]+)")?[^%]*%\}', stripped)
        if m:
            if m.group(1):
                out.append(f"`{m.group(1)}`")
            continue
        if re.match(r"\{%\s*(endtab|tabs|endtabs|endcode)\s*%\}", stripped):
            continue
        if stripped.startswith("{%"):
            continue
        out.append(f"> {line}" if in_hint and line.strip() else (">" if in_hint else line))
    return out


def convert_page(path: Path, names: dict[Path, str]) -> str:
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    lines = convert_blocks(body.splitlines())

    # rewrite links outside code fences (inside a hint the fence lines carry a "> " prefix)
    fence = Fence()
    for i, line in enumerate(lines):
        if not fence.feed(line.removeprefix("> ")):
            lines[i] = rewrite_links(line, path, names)

    rel = path.relative_to(ROOT).as_posix()
    banner = (
        f"> Generated from [`{rel}`]({BLOB}/{rel}). Edit it there; changes made in the wiki "
        "are overwritten on the next sync."
    )
    desc = f"*{meta['description']}*" if meta.get("description") else ""
    insert = [x for x in ("", desc, "", banner, "") if x is not None]
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines[i + 1 : i + 1] = insert
            break
    else:
        lines = [banner, "", *lines]
    return "\n".join(lines).rstrip() + "\n"


def build_sidebar(names: dict[Path, str]) -> str:
    out = ["**[Home](Home)**", ""]
    heading = None
    details = False
    for line in (DOCS / "SUMMARY.md").read_text(encoding="utf-8").splitlines():
        h = re.match(r"^## (.+)$", line)
        if h:
            if details:
                out.append("</details>\n")
            elif heading is not None:
                out.append("")
            heading = h.group(1)
            details = heading.startswith("Sources:")
            if details:
                out.append(
                    f"<details><summary><b>{heading.removeprefix('Sources: ')}</b></summary>\n"
                )
            else:
                out.append(f"### {heading}\n")
            continue
        m = re.match(r"^\* \[([^\]]+)\]\(([^)]+)\)", line)
        if not m or heading is None:
            continue
        title, target = m.groups()
        link = rewrite_link(target, DOCS / "SUMMARY.md", names)
        out.append(f"* [{title}]({link})")
    if details:
        out.append("</details>")
    return "\n".join(out) + "\n"


def build(out_dir: Path) -> list[str]:
    names = page_names()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for path, name in names.items():
        (out_dir / f"{name}.md").write_text(convert_page(path, names), encoding="utf-8")
    (out_dir / "_Sidebar.md").write_text(build_sidebar(names), encoding="utf-8")
    (out_dir / "_Footer.md").write_text(
        f"Generated from [`docs/`]({TREE}/docs) in the repository. "
        f"[Report a problem](https://github.com/{REPO}/issues) · "
        f"[Read the same docs on GitBook](https://github.com/{REPO}#documentation)\n",
        encoding="utf-8",
    )
    return sorted(names.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    pages = build(args.out)
    print(f"wrote {len(pages)} pages + _Sidebar + _Footer to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
