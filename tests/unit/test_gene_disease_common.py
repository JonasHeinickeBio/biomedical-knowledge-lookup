"""Unit tests for the helpers shared by the ClinGen and GenCC adapters."""

import pytest

from knowledge_lookup.adapters._gene_disease_common import (
    classification_key,
    classification_rank,
    classification_strength,
    normalize_disease_curie,
    normalize_hgnc,
    relation_for_classification,
    summarize,
)

pytestmark = pytest.mark.unit


def test_classification_vocabulary():
    assert classification_key("Disputed Evidence") == "disputed"
    assert classification_key("  Refuted Evidence ") == "refuted"
    assert classification_key(None) == ""
    order = ["Definitive", "Strong", "Moderate", "Supportive", "Limited", "Animal Model Only"]
    order += ["No Known Disease Relationship", "Disputed Evidence", "Refuted Evidence"]
    ranks = [classification_rank(c) for c in order]
    assert ranks == sorted(ranks, reverse=True) and len(set(ranks)) == len(ranks)
    assert classification_rank("something else") == 0
    assert classification_strength("Definitive") == 1.0
    assert classification_strength("Refuted") == 0.0
    assert classification_strength("nope") is None


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Definitive", "associated_with"),
        ("Limited", "associated_with"),
        ("Supportive", "associated_with"),
        ("Disputed Evidence", "disputed_association_with"),
        ("Refuted", "refuted_association_with"),
        ("No Known Disease Relationship", "no_known_relationship_with"),
        ("Animal Model Only", "animal_model_association_with"),
        ("unknown", "associated_with"),
    ],
)
def test_relation_for_classification(label, expected):
    assert relation_for_classification(label) == expected


def test_summarize_consensus_and_conflict():
    assert summarize([]) == {}
    assert summarize([("a", "")]) == {}
    one = summarize([("ClinGen", "Definitive")])
    assert one["best_classification"] == one["consensus_classification"] == "Definitive"
    assert one["n_submitters"] == 1 and one["conflicting"] is False and one["supported"] is True
    mixed = summarize([("A", "Definitive"), ("B", "Strong"), ("C", "Strong"), ("A", "Limited")])
    assert mixed["best_classification"] == "Definitive"
    assert mixed["consensus_classification"] == "Strong"
    assert mixed["n_submitters"] == 3
    assert mixed["classification_counts"] == {"Definitive": 1, "Strong": 2, "Limited": 1}
    tie = summarize([("A", "Definitive"), ("B", "Limited")])
    assert tie["consensus_classification"] == "Limited"  # ties go to the conservative side
    conflict = summarize([("A", "Moderate"), ("B", "Disputed Evidence")])
    assert conflict["conflicting"] is True
    weak = summarize([("A", "Limited"), ("B", "Refuted Evidence")])
    assert weak["conflicting"] is False
    negative = summarize([("A", "Refuted Evidence")])
    assert negative["supported"] is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("HGNC:1100", ("id", "HGNC:1100")),
        ("hgnc: 1100", ("id", "HGNC:1100")),
        ("1100", ("id", "HGNC:1100")),
        ("brca1", ("symbol", "BRCA1")),
        ("MT-ATP6", ("symbol", "MT-ATP6")),
        ("two words", None),
        ("MONDO:0007947", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_hgnc(raw, expected):
    assert normalize_hgnc(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("MONDO:0007947", "MONDO:0007947"),
        ("mondo:7947", "MONDO:0007947"),
        ("Orphanet:558", "ORPHA:558"),
        ("Orphanet_558", "ORPHA:558"),
        ("orpha:558", "ORPHA:558"),
        ("omim:154700", "OMIM:154700"),
        ("OMIM:", None),
        ("BRCA1", None),
        ("HGNC:1100", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_disease_curie(raw, expected):
    assert normalize_disease_curie(raw) == expected
