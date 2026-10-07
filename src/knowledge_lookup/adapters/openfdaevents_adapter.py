"""
openFDA drug adverse events (FAERS) Knowledge Source Adapter

Queries the openFDA ``drug/event`` endpoint (https://api.fda.gov/drug/event.json), which
serves the FDA Adverse Event Reporting System (FAERS): spontaneous reports from patients,
physicians, and manufacturers. Two kinds of concepts are exposed:

* **drugs** by openFDA generic name (``patient.drug.openfda.generic_name``), id
  ``FAERS:DRUG:ASPIRIN``;
* **reactions** by MedDRA preferred term (``patient.reaction.reactionmeddrapt``), id
  ``FAERS:REACTION:FATIGUE``. openFDA publishes the term text only, not MedDRA codes, so no
  MedDRA code identifier is claimed.

**Read FAERS counts as reporting counts, never as risks.** Reports are spontaneous and
unverified: no denominator (exposed patients), no causality assessment, duplicate reports of
one event, stimulated and under-reporting, and strong *confounding by indication*: a drug
that treats a fatiguing disease is "associated" with fatigue because the disease causes it.
A drug in a report may be suspect, concomitant or interacting; the searches used here match a
drug anywhere in the report (openFDA cannot correlate the role with the drug name). The
proportions returned (``reports with this reaction / total reports mentioning the drug``)
are descriptive, not incidence. See the docs page for the contrast with the OFFSIDES and SIDER
adapters.

API facts (verified live 2026-10-07):

* Keyless limits: 240 requests/minute and 1000 requests/day per IP; with a key
  (``OPENFDA_API_KEY``, sent as ``api_key``) 240/minute and 120 000/day. The responses carry
  no rate-limit headers.
* ``count=<field>.exact`` returns the 1000 most frequent values at most; ``limit`` above
  1000 is rejected with a misleading HTTP 403 ``API_KEY_MISSING``. The ``.exact`` fields are
  case sensitive and stored upper-case (``"FATIGUE"``, ``"ASPIRIN"``).
* No matches is HTTP 404 ``NOT_FOUND`` (not an empty list); the shared retry layer treats it
  as "service answered" and the adapter returns ``[]`` / ``None``.
* Counting a field of the *matching reports* includes every other value in those reports:
  the reactions of aspirin reports are fine, but the "drugs" of a reaction are all drugs that
  were co-listed, dominated by commonly used ones. ``count=serious`` (1 = serious, 2 = not)
  is used as a cheap total (it sums to ~99.95 % of ``meta.results.total``, the rest lack the
  field); fetching ``limit=1`` for the exact total would transfer ~100 KB of one full report.
* Latency 1-2.5 s.

Licence: openFDA data is public; see https://open.fda.gov/terms/ and the disclaimer carried
in every response ("Do not rely on openFDA to make decisions regarding medical care").
"""

import asyncio
import logging
import os
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov/drug/event.json"
API_KEY_ENV = "OPENFDA_API_KEY"
MAX_COUNT_LIMIT = 1000  # larger values give a 403 API_KEY_MISSING (openFDA quirk)
DEFAULT_REL_LIMIT = 25

DRUG_FIELD = "patient.drug.openfda.generic_name"
REACTION_FIELD = "patient.reaction.reactionmeddrapt"
INDICATION_FIELD = "patient.drug.drugindication"

DRUG_PREFIX = "FAERS:DRUG:"
REACTION_PREFIX = "FAERS:REACTION:"

CAVEAT = (
    "FAERS spontaneous reports: not causal, no denominator, duplicates and reporting bias "
    "possible, confounded by indication."
)

_PREFIX_RE = re.compile(
    r"^(?:FAERS:|OPENFDA:)?(DRUG|REACTION|PT|MEDDRA)\s*:\s*(.+)$", re.IGNORECASE
)


def clean_term(value: str) -> str:
    """Upper-case a name and drop characters that would break the Lucene query string."""
    return re.sub(r'["\\]', "", re.sub(r"\s+", " ", value or "")).strip().upper()


class OpenFDAEventsAdapter(KnowledgeSourceAdapter):
    """Adapter for openFDA drug adverse event reports (FAERS); keyless, optional key."""

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get_api_key("openfda") or os.getenv(API_KEY_ENV)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OPENFDAEVENTS

    def is_available(self) -> bool:
        return True  # public API; the key only raises the daily quota

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str | None, str] | None:
        """``FAERS:DRUG:ASPIRIN`` -> ``("drug", "ASPIRIN")``; bare names -> ``(None, NAME)``.

        Recognised prefixes: ``FAERS:DRUG:``, ``DRUG:``, ``FAERS:REACTION:``, ``REACTION:``,
        ``PT:``, ``MEDDRA:`` (the last two mean a preferred term).
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        match = _PREFIX_RE.match(text)
        if match:
            kind = "drug" if match.group(1).upper() == "DRUG" else "reaction"
            term = clean_term(match.group(2))
            return (kind, term) if term else None
        term = clean_term(text)
        return (None, term) if term else None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _query(self, search: str, count: str, limit: int | None = None) -> list | None:
        """One ``count`` query; the ``results`` list, or ``None`` (no match / failure)."""
        params: dict[str, Any] = {"search": search, "count": count}
        if limit is not None:
            params["limit"] = max(1, min(int(limit), MAX_COUNT_LIMIT))
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            data = await self._make_request(BASE_URL, params=params)
        except Exception as e:
            if getattr(e, "status", None) == 404:  # openFDA's "no matches" answer
                logger.debug(f"openFDA events: no matches for {search}")
            else:
                logger.warning(f"openFDA events query failed ({search}, {count}): {e}")
            return None
        results = data.get("results") if isinstance(data, dict) else None
        return results if isinstance(results, list) else None

    @staticmethod
    def _exact_search(kind: str, term: str) -> str:
        field = DRUG_FIELD if kind == "drug" else REACTION_FIELD
        return f'{field}.exact:"{term}"'

    async def _totals(self, search: str) -> dict[str, int] | None:
        """Total / serious / non-serious report counts for ``search`` (via ``count=serious``)."""
        rows = await self._query(search, "serious")
        if not rows:
            return None
        counts = {
            str(r.get("term")): int(r.get("count") or 0) for r in rows if isinstance(r, dict)
        }
        serious, other = counts.get("1", 0), counts.get("2", 0)
        total = serious + other
        if total == 0:
            return None
        return {"total_reports": total, "serious_reports": serious, "non_serious_reports": other}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Find drugs (generic names) and reactions (MedDRA PTs) whose name contains ``query``.

        Two requests: the drug-name and reaction-term fields are each searched, their ``.exact``
        values counted, and values containing every query word kept (the count includes
        co-listed names, so unrelated ones must be filtered out). Half of ``limit`` (rounded
        up) goes to drugs, the rest to reactions; a short side is topped up from the other.
        ``report_count`` in ``source_data`` is the number of reports listing that name among
        the matching reports.
        """
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            term = clean_term(query)
            if not term:
                return []
            drugs, reactions = await asyncio.gather(
                self._matching_terms("drug", term), self._matching_terms("reaction", term)
            )
            n_drugs = min(len(drugs), max((limit + 1) // 2, limit - len(reactions)))
            concepts = [self._term_concept("drug", t, c) for t, c in drugs[:n_drugs]]
            room = limit - len(concepts)
            concepts += [self._term_concept("reaction", t, c) for t, c in reactions[:room]]
            return concepts[:limit]
        except Exception as e:
            logger.error(f"openFDA events search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Drug or reaction with report totals (a drug is tried first for bare names)."""
        try:
            parsed = self.parse_id(concept_id)
            if parsed is None:
                return None
            kind, term = parsed
            for candidate in (kind,) if kind else ("drug", "reaction"):
                totals = await self._totals(self._exact_search(candidate, term))
                if totals:
                    return self._term_concept(candidate, term, None, totals)
            return None
        except Exception as e:
            logger.error(f"openFDA events get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self,
        concept_id: str,
        limit: int = DEFAULT_REL_LIMIT,
        include_indications: bool = False,
    ) -> list[dict[str, Any]]:
        """Report-count edges (descriptive only, see the module docstring caveats).

        Drug -> reactions: ``reported_adverse_event`` edges, most reported first, each with
        ``report_count``, ``total_reports`` and ``report_proportion`` (= reports with this
        reaction / reports mentioning the drug). ``include_indications=True`` adds up to ten
        ``reported_indication`` edges (what the drug was reported as taken for) from one
        extra request: the easiest way to see confounding by indication.
        Reaction -> drugs: ``reported_with_drug`` edges (all co-listed drugs, so common drugs
        dominate), with the same count fields. Names are the upper-case openFDA values.
        Typically 2 requests (3 with indications); an unknown name gives ``[]``.
        """
        try:
            limit = max(0, min(int(limit), MAX_COUNT_LIMIT))
            parsed = self.parse_id(concept_id)
            if parsed is None or limit == 0:
                return []
            kind, term = parsed
            if kind is None:  # bare name: a drug if it has reports, otherwise a reaction
                details = await self.get_concept_details(term)
                kind = "reaction" if details and DRUG_PREFIX not in details.primary_id else "drug"
            search = self._exact_search(kind, term)
            if kind == "drug":
                count_field, label, prefix, other = (
                    f"{REACTION_FIELD}.exact",
                    "reported_adverse_event",
                    REACTION_PREFIX,
                    "reaction",
                )
            else:
                count_field, label, prefix, other = (
                    f"{DRUG_FIELD}.exact",
                    "reported_with_drug",
                    DRUG_PREFIX,
                    "drug",
                )
            want_indications = include_indications and kind == "drug"
            totals, rows, indications = await asyncio.gather(
                self._totals(search),
                self._query(search, count_field, limit),
                self._query(search, f"{INDICATION_FIELD}.exact", min(limit, 10))
                if want_indications
                else asyncio.sleep(0, None),
            )
            if not totals or not rows:
                return []
            total = totals["total_reports"]
            edges = self._edges(rows, label, prefix, other, total, term, limit)
            if indications:
                edges += self._edges(
                    indications,
                    "reported_indication",
                    "FAERS:INDICATION:",
                    "indication",
                    total,
                    term,
                    10,
                )
            return edges
        except Exception as e:
            logger.warning(f"openFDA events get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_indication_counts(self, drug: str, limit: int = 10) -> dict[str, int]:
        """Reported indications (``patient.drug.drugindication``) for reports with ``drug``."""
        parsed = self.parse_id(drug)
        if parsed is None:
            return {}
        rows = await self._query(
            self._exact_search("drug", parsed[1]), f"{INDICATION_FIELD}.exact", limit
        )
        counts: dict[str, int] = {}
        for row in rows or []:
            if self._valid_row(row):
                name = str(row["term"]).upper()
                counts[name] = counts.get(name, 0) + int(row["count"])
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_row(row: Any) -> bool:
        return isinstance(row, dict) and bool(row.get("term")) and "count" in row

    async def _matching_terms(self, kind: str, term: str) -> list[tuple[str, int]]:
        """``.exact`` values containing every word of ``term`` among reports matching it."""
        field = DRUG_FIELD if kind == "drug" else REACTION_FIELD
        words = term.split()
        rows = await self._query(f'{field}:"{term}"', f"{field}.exact", 100)
        found = []
        for row in rows or []:
            if self._valid_row(row):
                name = str(row["term"]).upper()
                if all(w in name for w in words):
                    found.append((name, int(row["count"])))
        return found

    def _edges(
        self,
        rows: list,
        label: str,
        prefix: str,
        entity_type: str,
        total: int,
        term: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        # openFDA keeps case variants of free-text values (indications: "HYPERTENSION" and
        # "Hypertension"); fold them and add their counts (a report may list both, so the sum
        # can slightly overstate).
        merged: dict[str, int] = {}
        for row in rows:
            if self._valid_row(row):
                name = str(row["term"]).upper()
                if name != term:
                    merged[name] = merged.get(name, 0) + int(row["count"])
        edges: list[dict[str, Any]] = []
        for name, count in sorted(merged.items(), key=lambda kv: -kv[1]):
            edges.append(
                {
                    "relation_label": label,
                    "related_id": f"{prefix}{name}",
                    "related_name": name,
                    "source": "OPENFDAEVENTS",
                    "entity_type": entity_type,
                    "report_count": count,
                    "total_reports": total,
                    "report_proportion": round(count / total, 6) if total else None,
                    "evidence": CAVEAT,
                }
            )
            if len(edges) >= limit:
                break
        return edges

    def _term_concept(
        self,
        kind: str,
        term: str,
        report_count: int | None,
        totals: dict[str, int] | None = None,
    ) -> UnifiedConcept:
        """Build a drug (DRUG) or reaction (PHENOTYPE: a MedDRA PT is any clinical finding)."""
        if kind == "drug":
            concept = self._create_concept(f"{DRUG_PREFIX}{term}", term, ConceptType.DRUG)
            semantic = "drug (openFDA generic name)"
        else:
            concept = self._create_concept(f"{REACTION_PREFIX}{term}", term, ConceptType.PHENOTYPE)
            semantic = "adverse event (MedDRA preferred term)"
        if concept.semantic_types is not None:
            concept.semantic_types.append(semantic)
        if concept.categories is not None:
            concept.categories.append("FAERS")
        concept.confidence_score = 0.7
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {"kind": kind, "term": term, "caveat": CAVEAT}
            if report_count is not None:
                data["report_count"] = report_count
            if totals:
                data.update(totals)
            concept.source_data[KnowledgeSource.OPENFDAEVENTS] = data
        return concept
