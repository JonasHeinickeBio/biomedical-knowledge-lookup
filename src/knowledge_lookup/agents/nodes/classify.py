"""Graph node: infer what kind of thing the query is about.

Runs after ``preprocess``. The inferred :class:`~knowledge_lookup.models.ConceptType`
names are stored in ``inferred_concept_types`` so later nodes can pick sources
that suit the query (a gene symbol belongs with HGNC/UniProt/Ensembl, a drug
name with ChEMBL/PubChem/DrugBank) instead of treating every query alike.

Classification is deterministic first — identifier prefixes (``HP:``, ``GO:``,
``ENSG``, UniProt accessions, ...), gene-symbol shape, drug-name suffixes and a
few keyword cues. Only when no rule fires, and an LLM backend is configured,
the model is asked to pick from the known concept types. A caller-supplied
``concept_type_filter`` is taken as authoritative and skips both.
"""

from __future__ import annotations

import json
import logging
import re

from ...models import ConceptType
from ..config import call_llm
from ..state import LookupWorkflowState, make_step

logger = logging.getLogger(__name__)

_ID_PATTERNS: tuple[tuple[re.Pattern[str], ConceptType], ...] = (
    (re.compile(r"^HP:\d+$", re.I), ConceptType.PHENOTYPE),
    (re.compile(r"^(MONDO|DOID|OMIM|ORPHA(NET)?):\w+$", re.I), ConceptType.DISEASE),
    (re.compile(r"^GO:\d{7}$", re.I), ConceptType.BIOLOGICAL_PROCESS),
    (re.compile(r"^CHEBI:\d+$", re.I), ConceptType.CHEMICAL),
    (re.compile(r"^CHEMBL\d+$", re.I), ConceptType.DRUG),
    (re.compile(r"^DB\d{5}$"), ConceptType.DRUG),
    (re.compile(r"^ENSG\d{6,}(\.\d+)?$"), ConceptType.GENE),
    (re.compile(r"^ENS[A-Z]*P\d{6,}(\.\d+)?$"), ConceptType.PROTEIN),
    (re.compile(r"^HGNC:\d+$", re.I), ConceptType.GENE),
    (re.compile(r"^R-[A-Z]{3}-\d+$"), ConceptType.PATHWAY),
    (re.compile(r"^(hsa|map|ko|path:hsa)\d{5}$", re.I), ConceptType.PATHWAY),
    (re.compile(r"^WP\d+$"), ConceptType.PATHWAY),
    (
        re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"),
        ConceptType.PROTEIN,
    ),
    (re.compile(r"^IPR\d{6}$"), ConceptType.PROTEIN),
    (re.compile(r"^PF\d{5}$"), ConceptType.PROTEIN),
)

# An all-caps token containing a digit (TP53, BRCA1, IL6, HLA-DRB1) reads as a
# gene symbol; letters-only tokens (COPD, EGFR) are ambiguous with disease
# abbreviations, so they are left to the keyword rules and the LLM.
_GENE_SYMBOL = re.compile(r"^[A-Z][A-Z0-9-]{1,9}$")

_DRUG_SUFFIXES = (
    "mab",
    "nib",
    "vir",
    "statin",
    "pril",
    "sartan",
    "olol",
    "azole",
    "cillin",
    "mycin",
    "prazole",
    "gliptin",
    "glutide",
    "afil",
    "setron",
    "dipine",
    "tidine",
    "caine",
    "zepam",
    "oxetine",
    "formin",
    "parin",
    "platin",
    "tinib",
)

_KEYWORD_RULES: tuple[tuple[re.Pattern[str], ConceptType], ...] = (
    (
        re.compile(r"\b(pathway|signal(?:l)?ing|cascade|metabolism|biosynthesis)\b", re.I),
        ConceptType.PATHWAY,
    ),
    (
        re.compile(r"\b(receptor|kinase|enzyme|transporter|protein|antibody)\b", re.I),
        ConceptType.PROTEIN,
    ),
    (re.compile(r"\bgene\b", re.I), ConceptType.GENE),
    (re.compile(r"\b(cells?|neurons?|lymphocytes?|macrophages?)\b", re.I), ConceptType.CELL_TYPE),
    (
        re.compile(
            r"(syndrome|disease|disorder|cancer|carcinoma|lymphoma|leukemia|leukaemia|diabetes|"
            r"infection|itis|osis|emia|opathy|oma)\b",
            re.I,
        ),
        ConceptType.DISEASE,
    ),
    (
        re.compile(
            r"\b(pain|fever|cough|nausea|headache|seizures?|rash|fatigue|dyspnea|vomiting|"
            r"dizziness|tremor)\b",
            re.I,
        ),
        ConceptType.SYMPTOM,
    ),
    (
        re.compile(r"\b(inhibitor|agonist|antagonist|drug|therapy|treatment)\b", re.I),
        ConceptType.DRUG,
    ),
)


def infer_concept_types(query: str) -> list[ConceptType]:
    """Infer the likely concept types of a (possibly comma-separated) *query*.

    Each comma-separated term is classified independently and the union is
    returned in first-seen order. An empty list means "no rule fired".
    """
    found: list[ConceptType] = []

    def _add(concept_type: ConceptType) -> None:
        if concept_type not in found:
            found.append(concept_type)

    for term in (t.strip() for t in query.split(",")):
        if not term:
            continue
        matched = False
        for pattern, concept_type in _ID_PATTERNS:
            if pattern.match(term):
                _add(concept_type)
                matched = True
                break
        if matched:
            continue
        if _GENE_SYMBOL.match(term) and any(ch.isdigit() for ch in term) and term == term.upper():
            _add(ConceptType.GENE)
            continue
        lowered = term.lower()
        if " " not in lowered and lowered.endswith(_DRUG_SUFFIXES) and len(lowered) > 5:
            _add(ConceptType.DRUG)
            continue
        for pattern, concept_type in _KEYWORD_RULES:
            if pattern.search(term):
                _add(concept_type)
                break
    return found


def _parse_llm_types(text: str | None) -> list[ConceptType]:
    """Parse an LLM reply (a JSON list of type names) into known concept types."""
    if not text:
        return []
    match = re.search(r"\[.*?\]", text, re.S)
    if not match:
        return []
    try:
        raw = json.loads(match.group(0))
    except (ValueError, TypeError):
        return []
    types: list[ConceptType] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            concept_type = ConceptType(str(item).strip().upper())
        except ValueError:
            continue
        if concept_type != ConceptType.UNKNOWN and concept_type not in types:
            types.append(concept_type)
    return types[:3]


_LLM_CANDIDATES = (
    "DISEASE, SYMPTOM, PHENOTYPE, GENE, PROTEIN, DRUG, CHEMICAL, METABOLITE, PATHWAY, "
    "BIOLOGICAL_PROCESS, MOLECULAR_FUNCTION, CELL_TYPE, ANATOMICAL_ENTITY, PROCEDURE, TREATMENT"
)


async def _classify_with_llm(query: str) -> list[ConceptType]:
    prompt = (
        "Classify this biomedical search query into at most 3 concept types.\n"
        f"Query: {query!r}\n"
        f"Allowed types: {_LLM_CANDIDATES}\n"
        'Reply with only a JSON list such as ["GENE", "PROTEIN"].'
    )
    return _parse_llm_types(await call_llm(prompt, max_tokens=60, temperature=0.0))


async def classify_node(state: LookupWorkflowState) -> dict:
    """Record the concept types the query most likely refers to."""
    forced = [t for t in (state.get("concept_type_filter") or []) if t]
    if forced:
        types = [ct for ct in (_try_type(t) for t in forced) if ct is not None]
        how = "from the concept_type filter"
    else:
        query = state.get("original_query") or state["query"]
        types = infer_concept_types(query)
        how = "by rules"
        if not types:
            types = await _classify_with_llm(query)
            how = "by LLM" if types else "no rule or LLM match"

    names = [ct.value for ct in types]
    detail = (
        f"Inferred {', '.join(names)} ({how})" if names else f"No concept type inferred ({how})"
    )
    return {
        "inferred_concept_types": names,
        "steps": [make_step("ClassifyAgent", "classify", detail)],
    }


def _try_type(name: str) -> ConceptType | None:
    try:
        return ConceptType(str(name).upper())
    except ValueError:
        return None
