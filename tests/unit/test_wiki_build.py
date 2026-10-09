"""The GitHub wiki is generated from docs/; make sure the output is self-consistent."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def wiki(tmp_path_factory):
    from build_wiki import build

    out = tmp_path_factory.mktemp("wiki")
    pages = build(out)
    return out, pages


def test_home_sidebar_and_footer_exist(wiki):
    out, pages = wiki
    assert "Home" in pages
    for name in ("Home.md", "_Sidebar.md", "_Footer.md"):
        assert (out / name).is_file()


def test_every_adapter_page_is_a_wiki_page(wiki):
    _out, pages = wiki
    sources = [p for p in pages if p.startswith("Source-")]
    assert len(sources) == len(list((ROOT / "docs" / "adapters").glob("*/*_adapter.md")))


def test_wiki_links_resolve_and_gitbook_blocks_are_gone(wiki):
    out, pages = wiki
    names = set(pages) | {"_Sidebar", "_Footer"}
    broken, leftovers = [], []
    for f in out.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        in_fence = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if re.search(r"\{%\s*(end)?(hint|tabs?|code)\b", line) and "`{%" not in line:
                leftovers.append(f.name)
            for m in re.finditer(r"\]\(([^)\s]+)\)", line):
                target = m.group(1)
                if target.startswith(("http", "mailto")):
                    continue
                page = target.split("#")[0]
                if page and page not in names:
                    broken.append(f"{f.name} -> {target}")
    assert not broken, broken[:10]
    assert not leftovers, leftovers[:10]


def test_sidebar_lists_the_domains(wiki):
    out, _pages = wiki
    sidebar = (out / "_Sidebar.md").read_text(encoding="utf-8")
    assert "<details>" in sidebar and "Source-HGNC" in sidebar
