"""Helpers shared by the phenotype/identifier adapters (Monarch, HPOA, NodeNorm).

Kept private (leading underscore) and import-light: only the pydantic models, no network
or heavy third-party packages, so importing an adapter stays cheap.
"""

import re
from typing import NamedTuple

from ..models import KnowledgeSource, UnifiedConcept

# HPO "Frequency" branch (HP:0040279). Each term is defined by a percentage range in the
# ontology; we keep the term's name and use the *midpoint* of its range as a numeric
# fraction so frequencies from different sources can be compared and ranked. "Obligate"
# (100%) and "Excluded" (0%) are exact.
FREQUENCY_TERMS: dict[str, tuple[str, float]] = {
    "HP:0040280": ("Obligate", 1.0),  # 100%
    "HP:0040281": ("Very frequent", 0.9),  # 80-99%
    "HP:0040282": ("Frequent", 0.55),  # 30-79%
    "HP:0040283": ("Occasional", 0.17),  # 5-29%
    "HP:0040284": ("Very rare", 0.025),  # 1-4%
    "HP:0040285": ("Excluded", 0.0),  # 0%
}

_FRACTION_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
_PERCENT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%\s*$")


class Frequency(NamedTuple):
    """A parsed HPO frequency annotation.

    ``fraction`` is a number in [0, 1] (``None`` when the raw value is not understood),
    ``label`` a human-readable form ("Very frequent", "3/7", "40%"), ``raw`` the value
    exactly as found and ``term`` the HP frequency term id when the source used one.
    """

    fraction: float | None
    label: str | None
    raw: str
    term: str | None = None


def parse_frequency(raw: str | None) -> Frequency | None:
    """Parse an HPO frequency value: an ``HP:0040280``..``HP:0040285`` term, ``n/m`` or ``x%``.

    Returns ``None`` for empty input. Unrecognised text is returned with
    ``fraction=None`` so callers can still show the raw string.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    term = text.upper()
    if term in FREQUENCY_TERMS:
        name, fraction = FREQUENCY_TERMS[term]
        return Frequency(fraction, name, text, term)
    match = _FRACTION_RE.match(text)
    if match:
        numerator, denominator = int(match.group(1)), int(match.group(2))
        if denominator == 0:
            return Frequency(None, text, text)
        return Frequency(min(numerator / denominator, 1.0), text, text)
    match = _PERCENT_RE.match(text)
    if match:
        return Frequency(min(float(match.group(1)) / 100.0, 1.0), text, text)
    return Frequency(None, text, text)


def frequency_extras(freq: Frequency | None) -> dict[str, object]:
    """Relationship-dict keys for a frequency (empty when there is none)."""
    if freq is None:
        return {}
    extras: dict[str, object] = {"frequency_raw": freq.raw}
    if freq.fraction is not None:
        extras["frequency"] = round(freq.fraction, 4)
    if freq.label:
        extras["frequency_label"] = freq.label
    if freq.term:
        extras["frequency_term"] = freq.term
    return extras


# CURIE prefix -> KnowledgeSource, for the prefixes where the enum has a member. Used to
# attach cross-references as ``UnifiedConcept.identifiers`` (which require an enum source);
# everything else stays available through ``get_mappings`` / ``source_data``.
PREFIX_TO_SOURCE: dict[str, KnowledgeSource] = {
    "HGNC": KnowledgeSource.HGNC,
    "MONDO": KnowledgeSource.MONDO,
    "HP": KnowledgeSource.HPO,
    "OMIM": KnowledgeSource.OMIM,
    "NCBIGENE": KnowledgeSource.NCBI,
    "ENSEMBL": KnowledgeSource.ENSEMBL,
    "UNIPROTKB": KnowledgeSource.UNIPROT,
    "UMLS": KnowledgeSource.UMLS,
    "MESH": KnowledgeSource.MESH,
    "GO": KnowledgeSource.GO,
    "CHEBI": KnowledgeSource.CHEBI,
    "CHEMBL.COMPOUND": KnowledgeSource.CHEMBL,
    "PUBCHEM.COMPOUND": KnowledgeSource.PUBCHEM,
    "DRUGBANK": KnowledgeSource.DRUGBANK,
    "SNOMEDCT": KnowledgeSource.SNOMEDCT,
}

# Canonical spelling of common CURIE prefixes, keyed by lower-case. The services involved
# are mostly case-insensitive about prefixes, but a few (Monarch's /entity) are not, and
# users type "hp:0012432", "Ncbigene:672" or "orpha:558" freely.
CANONICAL_PREFIXES: dict[str, str] = {
    p.lower(): p
    for p in (
        "HGNC",
        "MONDO",
        "HP",
        "MP",
        "OMIM",
        "NCBIGene",
        "ENSEMBL",
        "UniProtKB",
        "UMLS",
        "MESH",
        "DOID",
        "EFO",
        "NCIT",
        "GO",
        "CHEBI",
        "SNOMEDCT",
        "ICD10",
        "ICD9",
        "MGI",
        "RGD",
        "ZFIN",
        "FB",
        "WB",
        "SGD",
        "Xenbase",
        "CLINVAR",
        "DECIPHER",
        "PMID",
        "NORD",
        "MEDDRA",
        "DRUGBANK",
        "MEDGEN",
    )
}


def split_curie(identifier: str) -> tuple[str, str] | None:
    """Split ``PREFIX:local`` into ``(prefix, local)``; ``None`` when there is no prefix."""
    if not identifier or ":" not in identifier:
        return None
    prefix, _, local = identifier.strip().partition(":")
    prefix, local = prefix.strip(), local.strip()
    if not prefix or not local:
        return None
    return prefix, local


def add_known_identifier(
    concept: UnifiedConcept, curie: str, label: str | None = None, url: str | None = None
) -> bool:
    """Attach ``curie`` to ``concept.identifiers`` when its prefix has a KnowledgeSource.

    The identifier is stored without its prefix for NCBI/Ensembl/UniProt style sources
    (matching the other adapters, e.g. HGNC stores ``672`` for NCBI Gene) and as a full
    CURIE for ontology-style sources. Returns whether anything was added.
    """
    parts = split_curie(curie)
    if parts is None:
        return False
    prefix, local = parts
    source = PREFIX_TO_SOURCE.get(prefix.upper())
    if source is None:
        return False
    keep_prefix = source in (
        KnowledgeSource.HGNC,
        KnowledgeSource.MONDO,
        KnowledgeSource.HPO,
        KnowledgeSource.OMIM,
        KnowledgeSource.GO,
        KnowledgeSource.CHEBI,
    )
    identifier = f"{prefix.upper()}:{local}" if keep_prefix else local
    for existing in concept.identifiers or []:
        if existing.source == source and existing.identifier == identifier:
            return False
    concept.add_identifier(source, identifier, label, url)
    return True
