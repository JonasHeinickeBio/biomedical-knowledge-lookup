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
LINK = re.compile(r"(?<!\!)\[([^\]]*)\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(```|~~~)")


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


def convert_blocks(lines: list[str]) -> list[str]:
    """Replace GitBook blocks outside code fences with plain Markdown."""
    out: list[str] = []
    in_fence = False
    in_hint = False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
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

    # rewrite links outside code fences
    in_fence = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines[i] = LINK.sub(
                lambda m: f"[{m.group(1)}]({rewrite_link(m.group(2), path, names)})", line
            )

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
