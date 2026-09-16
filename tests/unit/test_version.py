"""Unit tests for the `__version__` placeholder and its fallback in knowledge_lookup/__init__.py."""

import importlib.metadata
import re
from pathlib import Path
from unittest.mock import patch

import pytest

import knowledge_lookup

pytestmark = pytest.mark.unit

# poetry-dynamic-versioning's default substitution pattern, applied with re.MULTILINE.
SUBSTITUTION_PATTERN = r"(^__version__\s*(?::.*?)?=\s*['\"])[^'\"]*(['\"])"


def test_build_substitution_matches_exactly_one_line():
    source = Path(knowledge_lookup.__file__).read_text(encoding="utf-8")

    matches = list(re.finditer(SUBSTITUTION_PATTERN, source, re.MULTILINE))

    assert len(matches) == 1


def test_placeholder_falls_back_to_installed_distribution_version():
    with patch("importlib.metadata.version", return_value="2.0.0") as version:
        assert knowledge_lookup._resolve_version("0.0.0") == "2.0.0"

    version.assert_called_once_with("biomedical-knowledge-lookup")


def test_substituted_version_is_kept_without_reading_metadata():
    with patch("importlib.metadata.version") as version:
        assert knowledge_lookup._resolve_version("2.0.0.post3+g9503315") == "2.0.0.post3+g9503315"

    version.assert_not_called()


def test_placeholder_is_kept_when_distribution_is_not_installed():
    missing = importlib.metadata.PackageNotFoundError("biomedical-knowledge-lookup")
    with patch("importlib.metadata.version", side_effect=missing):
        assert knowledge_lookup._resolve_version("0.0.0") == "0.0.0"


def test_package_exposes_a_version_string():
    assert isinstance(knowledge_lookup.__version__, str)
    assert knowledge_lookup.__version__
