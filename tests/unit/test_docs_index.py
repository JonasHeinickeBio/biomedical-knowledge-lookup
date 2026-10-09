"""Guards for the documentation: every source is listed, indexes are fresh, links resolve."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytestmark = pytest.mark.unit


def test_every_adapter_is_in_exactly_one_domain_and_has_a_page():
    from _source_taxonomy import load_sources

    from knowledge_lookup.adapters import _ADAPTER_SPECS

    sources = load_sources()  # raises SystemExit on a missing, unknown or duplicated source
    assert len(sources) == len(_ADAPTER_SPECS)
    for s in sources:
        assert s.description, f"{s.name}: docs page has no front-matter description"
        assert s.requires, f"{s.name}: docs page has no Requires row"


def test_generated_indexes_are_up_to_date():
    """Run ``python scripts/build_source_index.py`` after adding or renaming a source."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_source_index.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_relative_markdown_links_resolve():
    broken = []
    files = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\]\(([^)\s]+?)\)", text):
            link = m.group(1)
            if link.startswith(("http", "#", "mailto")):
                continue
            path = link.split("#")[0]
            if path and not (f.parent / path).resolve().exists():
                broken.append(f"{f.relative_to(ROOT)} -> {link}")
    assert not broken, "\n".join(broken[:20])


def test_every_environment_variable_is_documented():
    """New ``os.getenv`` names must be added to docs/reference/environment-variables.md."""
    patterns = [
        re.compile(r"getenv\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']"),
        re.compile(r"environ\.get\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']"),
        re.compile(r"environ\[\s*[\"']([A-Z][A-Z0-9_]+)[\"']"),
        re.compile(r"^\w*(?:ENV|_VAR)\w*\s*(?::[^=]+)?=\s*[\"']([A-Z][A-Z0-9_]+)[\"']", re.M),
    ]
    found: set[str] = set()
    for f in (ROOT / "src" / "knowledge_lookup").rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for p in patterns:
            found.update(p.findall(text))
    found -= {"PYTEST_CURRENT_TEST"}
    page = (ROOT / "docs/reference/environment-variables.md").read_text(encoding="utf-8")
    missing = sorted(v for v in found if f"`{v}`" not in page)
    assert not missing, f"undocumented environment variables: {missing}"
