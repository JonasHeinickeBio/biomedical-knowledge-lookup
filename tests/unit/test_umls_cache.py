"""
Unit tests for UMLS Local Cache (umls_cache module).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.umls.cache import PartialMatcher, UMLSCache


class TestPartialMatcher:
    """Tests for the stdlib-based fuzzy matcher."""

    def test_exact_match(self):
        m = PartialMatcher()
        assert m.score("diabetes", "diabetes") == 1.0

    def test_case_insensitive(self):
        m = PartialMatcher()
        assert m.score("DIABETES", "Diabetes") == 1.0

    def test_substring_match(self):
        m = PartialMatcher()
        score = m.score("diabetes", "diabetes mellitus")
        assert score >= 0.85

    def test_trigram_overlap(self):
        m = PartialMatcher()
        score = m.score("cardiomyopathy", "cardmyopathy")
        assert 0.4 <= score <= 1.0

    def test_no_match(self):
        m = PartialMatcher(min_score=0.5)
        assert m.score("xyz", "abc") == 0.0

    def test_empty_strings(self):
        m = PartialMatcher()
        assert m.score("", "test") == 0.0
        assert m.score("test", "") == 0.0
        assert m.score("", "") == 0.0

    def test_filter_ranks_correctly(self):
        m = PartialMatcher(min_score=0.0)
        candidates = [
            {"cui": "C001", "name": "Diabetes mellitus"},
            {"cui": "C002", "name": "Diabetes insipidus"},
            {"cui": "C003", "name": "Hypertension"},
        ]
        results = m.filter("diabetes", candidates)
        assert len(results) == 3
        # Diabetes mellitus should rank first (highest score)
        assert results[0]["cui"] == "C001"
        assert results[0]["score"] >= results[1]["score"]

    def test_filter_with_threshold(self):
        m = PartialMatcher(min_score=0.8)
        candidates = [
            {"cui": "C001", "name": "Diabetes mellitus"},
            {"cui": "C002", "name": "Hypertension"},
        ]
        results = m.filter("diabetes", candidates)
        assert len(results) == 1
        assert results[0]["cui"] == "C001"

    def test_char_overlap_fallback(self):
        """Very short strings should use character overlap."""
        m = PartialMatcher()
        score = m.score("ab", "ac")
        assert score > 0  # should have some overlap


class TestUMLSCache:
    """Tests for the SQLite-backed UMLS cache."""

    @pytest.fixture
    def cache(self):
        """Create a temp UMLSCache for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_umls.db"
            c = UMLSCache(db_path=db_path, auto_fts=True)
            yield c
            c.clear()

    # ── Basic write/read ─────────────────────────────────────────

    def test_cache_search_result_and_get(self, cache: UMLSCache):
        cache.cache_search_result(
            cui="C001",
            name="Diabetes mellitus",
            source="SNOMEDCT",
            semantic_types=["Disease or Syndrome"],
            definitions=["A metabolic disorder"],
            synonyms=["Diabetes", "DM"],
            categories=["SNOMEDCT"],
            confidence=0.95,
        )
        concept = cache.get_concept("C001")
        assert concept is not None
        assert concept["cui"] == "C001"
        assert concept["name"] == "Diabetes mellitus"
        assert concept["source"] == "SNOMEDCT"
        assert concept["confidence"] == 0.95
        assert "Disease or Syndrome" in concept["semantic_types"]
        assert "A metabolic disorder" in concept["definitions"]
        assert "Diabetes" in concept["synonyms"]

    def test_get_nonexistent(self, cache: UMLSCache):
        assert cache.get_concept("XYZ123") is None

    # ── FTS search ───────────────────────────────────────────────

    def test_search_by_exact_name(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes mellitus", "SNOMEDCT")
        results = cache.search_concepts("diabetes", limit=10)
        assert len(results) >= 1
        assert any(r["cui"] == "C001" for r in results)

    def test_search_by_partial_name(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes mellitus", "SNOMEDCT")
        results = cache.search_concepts("diab", limit=10)
        assert len(results) >= 1
        assert any(r["cui"] == "C001" for r in results)

    def test_search_empty_query(self, cache: UMLSCache):
        assert cache.search_concepts("") == []
        assert cache.search_concepts("   ") == []

    def test_search_no_results(self, cache: UMLSCache):
        results = cache.search_concepts("nonexistent", limit=10)
        assert results == []

    def test_search_with_multiple_concepts(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes mellitus", "SNOMEDCT")
        cache.cache_search_result("C002", "Diabetes insipidus", "ICD10CM")
        cache.cache_search_result("C003", "Hypertension", "ICD10CM")

        results = cache.search_concepts("diabetes", limit=10)
        assert len(results) >= 2
        assert any(r["cui"] == "C001" for r in results)
        assert any(r["cui"] == "C002" for r in results)

    def test_search_respects_limit(self, cache: UMLSCache):
        for i in range(5):
            cache.cache_search_result(f"C{i:03d}", f"Disease {i}")
        results = cache.search_concepts("disease", limit=3)
        assert len(results) <= 3

    # ── Fuzzy fallback ───────────────────────────────────────────

    def test_search_fuzzy_fallback(self, cache: UMLSCache):
        """When FTS returns few results, partial=True should find near matches."""
        cache.cache_search_result("C001", "Diabetes mellitus", "SNOMEDCT")
        cache.cache_search_result("C002", "Cardiomyopathy", "SNOMEDCT")

        # FTS won't match "diabet" but fuzzy fallback should (substring)
        results = cache.search_concepts("diabet", limit=10, partial=True)
        assert len(results) >= 1
        assert any(r["cui"] == "C001" for r in results)

    # ── Mappings ─────────────────────────────────────────────────

    def test_cache_and_get_mappings(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes")
        cache.cache_mappings("C001", [
            {"source": "SNOMEDCT", "source_id": "73211009", "source_name": "Diabetes mellitus"},
            {"source": "ICD10CM", "source_id": "E11", "source_name": "Type 2 diabetes"},
        ])

        mappings = cache.get_mappings("C001")
        assert len(mappings) == 2
        assert any(m["source_id"] == "73211009" for m in mappings)

    def test_get_mappings_filtered_by_source(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes")
        cache.cache_mappings("C001", [
            {"source": "SNOMEDCT", "source_id": "73211009", "source_name": "Diabetes"},
            {"source": "ICD10CM", "source_id": "E11", "source_name": "Diabetes"},
        ])

        mappings = cache.get_mappings("C001", target_source="SNOMEDCT")
        assert len(mappings) == 1
        assert mappings[0]["source"] == "SNOMEDCT"

    # ── Relationships ────────────────────────────────────────────

    def test_cache_and_get_relationships(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes")
        cache.cache_relationships("C001", [
            {"relation_label": "PAR", "related_id": "C000", "related_name": "Parent", "source": "SNOMEDCT"},
            {"relation_label": "CHD", "related_id": "C002", "related_name": "Child", "source": "SNOMEDCT"},
        ])

        rels = cache.get_relationships("C001")
        assert len(rels) == 2
        assert any(r["relation_label"] == "PAR" for r in rels)

    # ── Bulk import ──────────────────────────────────────────────

    def test_bulk_cache_concepts(self, cache: UMLSCache):
        concepts = [
            {"cui": "C001", "name": "Diabetes", "source": "SNOMEDCT", "confidence": 0.9},
            {"cui": "C002", "name": "Hypertension", "source": "ICD10CM", "confidence": 0.8},
        ]
        count = cache.bulk_cache_concepts(concepts)
        assert count == 2
        assert cache.size() == 2

    def test_bulk_cache_empty(self, cache: UMLSCache):
        assert cache.bulk_cache_concepts([]) == 0

    # ── Introspection ────────────────────────────────────────────

    def test_size(self, cache: UMLSCache):
        assert cache.size() == 0
        cache.cache_search_result("C001", "Test")
        assert cache.size() == 1

    def test_clear(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Test")
        assert cache.size() == 1
        cache.clear()
        assert cache.size() == 0

    def test_stats(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Test")
        stats = cache.stats()
        assert stats["concepts"] == 1
        assert stats["db_size_bytes"] > 0
        assert stats["db_path"]

    # ── Edge cases ───────────────────────────────────────────────

    def test_double_insert_does_not_raise(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Diabetes")
        cache.cache_search_result("C001", "Diabetes mellitus")  # update
        assert cache.size() == 1
        concept = cache.get_concept("C001")
        assert concept is not None
        assert concept["name"] == "Diabetes mellitus"

    def test_special_chars_in_query(self, cache: UMLSCache):
        cache.cache_search_result("C001", "COVID-19", "SNOMEDCT")
        results = cache.search_concepts("COVID-19", limit=10)
        assert len(results) >= 1

    def test_unicode(self, cache: UMLSCache):
        cache.cache_search_result("C001", "Cáncer", "SNOMEDCT")
        results = cache.search_concepts("cáncer", limit=10)
        assert len(results) >= 1
