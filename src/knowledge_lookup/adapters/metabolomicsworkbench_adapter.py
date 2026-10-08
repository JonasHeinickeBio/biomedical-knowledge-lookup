"""
Metabolomics Workbench adapter.

The Metabolomics Workbench (NIH Common Fund, hosted at UC San Diego) is a repository of
metabolomics studies (ids ``ST000001``...) plus two metabolite vocabularies: the compound
database (registry numbers, cross-referenced to PubChem, KEGG, HMDB, ChEBI) and RefMet, a
standardised name list with chemical classification. Many ME/CFS and Long COVID plasma,
stool and urine studies are deposited here (``ST002003`` plasma ME/CFS case-control,
``ST003103`` Long COVID mitochondrial dysfunction).

REST API (https://www.metabolomicsworkbench.org/rest/), keyless, verified live 2026-10:

* Responses are JSON, but the shape changes with the number of hits: several records come as
  an object keyed ``"1"``, ``"2"``..., a single record as a *flat* object and no record as
  ``[]``. All three are handled by :meth:`_records`. Bad parameters answer HTTP 200 with an
  HTML message, which the JSON parser rejects.
* ``refmet/match/{text}`` is the only fuzzy name lookup (one best RefMet entry, ``"-"`` fields
  when nothing matches); ``compound/name/...`` does **not** exist (only formula, regno,
  inchi_key, lm_id, pubchem_cid, hmdb_id, kegg_id, smiles, abbrev). ``refmet/{refmet_id |
  name | pubchem_cid | inchi_key}/{value}/all`` returns the full RefMet record including the
  compound ``regno`` (can be negative for lipid classes with no compound record) and
  ``compound/regno/{n}/all`` the KEGG / HMDB / ChEBI / LIPID MAPS ids.
* ``study/study_title/{text}/summary`` is a substring title search (newest first).
  ``study/study_id/{id}/summary`` is a **prefix** match (``ST0020`` returns every ST0020xx
  study), so exact ids are filtered client side. ``.../disease`` gives the studied condition
  (``[]`` when not annotated) and ``study/study_id/{id}/metabolites`` the measured features
  with RefMet names (empty ``refmet_name`` or ``Standard`` for unmatched ones; big studies
  return ~100 KB in several seconds). ``study/refmet_name/{name}/summary`` lists the studies
  measuring a metabolite (common metabolites such as lactic acid return ~100 KB).
* Slashes and colons inside a name (lipids like ``MG 18:0/0:0/0:0``) must stay unescaped in
  the path; ``%2F`` makes the server answer 404.
* The ``study_url`` field of title searches is malformed (it contains the search term), so the
  adapter builds the study page URL from the id.

No rate limit is published; calls are spaced at least 0.5 s apart. Data are deposited by
submitters under ``CC BY 4.0`` (the ``license`` field of each study; cite the study and the
Workbench).

Concept ids: ``RM0135904`` (RefMet id, the metabolite primary id), ``ST002003`` (study) and
``regno:37125`` (compound registry number); any other text is tried as an exact RefMet name.
"""

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

MW_BASE_URL = "https://www.metabolomicsworkbench.org/rest"
STUDY_PAGE_URL = "https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID="
REFMET_PAGE_URL = (
    "https://www.metabolomicsworkbench.org/databases/refmet/refmet_details.php?REFMET_ID="
)

_MIN_INTERVAL = 0.5
_MAX_SEARCH = 100
_DEFAULT_RELATIONS = 50
_UNMATCHED_NAMES = {"", "-", "standard", "unknown"}

_STUDY_RE = re.compile(r"^(?:mwb?|mw_study|study)?\s*[:_]?\s*(ST\d{6})$", re.IGNORECASE)
_REFMET_RE = re.compile(r"^(?:refmet\s*[:_]\s*)?(RM\d{7})$", re.IGNORECASE)
_REGNO_RE = re.compile(r"^(?:regno|mwrn|mw_regno)\s*[:_]\s*(\d{1,9})$", re.IGNORECASE)

# (record key, prefix used in mapping CURIEs, KnowledgeSource name for a ConceptIdentifier or None)
_XREFS: tuple[tuple[str, str, str | None], ...] = (
    ("pubchem_cid", "PUBCHEM", "PUBCHEM"),
    ("kegg_id", "KEGG", "KEGG"),
    ("chebi_id", "CHEBI", "CHEBI"),
    ("lm_id", "LIPIDMAPS", "LIPIDMAPS"),
    ("hmdb_id", "HMDB", None),
    ("metacyc_id", "METACYC", None),
    ("inchi_key", "INCHIKEY", None),
)


def _clean(value: Any) -> str:
    """Stripped string, with the API's placeholders (``-``, ``[]``) mapped to ``''``."""
    if value is None or isinstance(value, (list, dict)):
        return ""
    text = str(value).strip()
    return "" if text == "-" else text


class MetabolomicsWorkbenchAdapter(KnowledgeSourceAdapter):
    """Metabolomics Workbench studies, RefMet metabolites and compound cross-references."""

    min_request_timeout = 60.0  # large metabolite listings take several seconds

    def __init__(self, config):
        super().__init__(config)
        self.base_url = MW_BASE_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.METABOLOMICSWORKBENCH

    def is_available(self) -> bool:
        return True  # public, keyless REST API

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> Any:
        """GET ``{base}/{path}``; ``path`` must already be URL-safe (see :meth:`_seg`)."""
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        return await self._make_request(f"{self.base_url}/{path}")

    @staticmethod
    def _seg(text: str) -> str:
        """Escape a free-text path segment; ``/`` and ``:`` stay raw (``%2F`` gives a 404)."""
        return quote(text.strip(), safe="/:,()+'")

    @staticmethod
    def _records(data: Any) -> list[dict[str, Any]]:
        """Normalise the three response shapes: numbered object, flat object, ``[]``."""
        if not isinstance(data, dict) or not data:
            return []
        values = list(data.values())
        if all(isinstance(v, dict) for v in values):
            return values
        return [data]

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("study", "ST002003")``, ``("refmet", "RM0135904")``, ``("regno", "37125")`` or
        ``("name", "<text>")`` for anything else (an exact RefMet name)."""
        text = (concept_id or "").strip()
        if not text:
            return None
        for kind, pattern in (("study", _STUDY_RE), ("refmet", _REFMET_RE), ("regno", _REGNO_RE)):
            match = pattern.match(text)
            if match:
                value = match.group(1)
                return kind, value.upper() if kind != "regno" else str(int(value))
        return "name", text

    async def _refmet_record(self, kind: str, value: str) -> dict[str, Any] | None:
        field = {"refmet": "refmet_id", "name": "name"}[kind]
        records = self._records(await self._get(f"refmet/{field}/{self._seg(value)}/all"))
        return records[0] if records else None

    async def _compound_record(self, regno: str) -> dict[str, Any] | None:
        if not regno.isdigit() or int(regno) <= 0:  # negative regnos mark classes without record
            return None
        records = self._records(await self._get(f"compound/regno/{regno}/all"))
        return records[0] if records else None

    async def _study_summary(self, study_id: str) -> dict[str, Any] | None:
        for record in self._records(await self._get(f"study/study_id/{study_id}/summary")):
            if _clean(record.get("study_id")).upper() == study_id:  # the API matches prefixes
                return record
        return None

    async def _metabolite_parts(
        self, kind: str, value: str
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """``(refmet record, compound record)`` for a metabolite id; either may be ``{}``."""
        if kind == "regno":
            compound = await self._compound_record(value)
            return ({}, compound) if compound else None
        refmet = await self._refmet_record(kind, value)
        if refmet is None:
            return None
        compound = await self._compound_record(_clean(refmet.get("regno"))) or {}
        return refmet, compound

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Best RefMet metabolite for the text (if any) followed by studies whose title matches.

        An id (``ST002003``, ``RM0135904``, ``regno:37125``) goes straight to details. Study
        titles are matched as a substring, so a short term like ``lactate`` can match many
        studies; results are newest first and capped at ``limit``.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            parsed = self._parse_id(text)
            if parsed is not None and parsed[0] != "name":
                concept = await self.get_concept_details(text)
                return [concept] if concept else []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            cap = min(limit, _MAX_SEARCH)
            try:
                match = self._records(await self._get(f"refmet/match/{self._seg(text)}"))
                hit = self._match_to_concept(match[0]) if match else None
                if hit is not None:
                    seen.add(hit.primary_id)
                    concepts.append(hit)
            except Exception as e:
                logger.warning(f"Metabolomics Workbench RefMet match failed for '{text}': {e}")
            studies = await self._get(f"study/study_title/{self._seg(text)}/summary")
            for rank, record in enumerate(self._records(studies)):
                if len(concepts) >= cap:
                    break
                concept = self._study_to_concept(record)
                if concept is None or concept.primary_id in seen:
                    continue
                seen.add(concept.primary_id)
                concept.confidence_score = max(0.5, 0.85 - 0.01 * rank)
                concepts.append(concept)
            logger.info(
                f"Metabolomics Workbench search '{text}' returned {len(concepts)} concepts"
            )
            return concepts
        except Exception as e:
            logger.error(f"Metabolomics Workbench search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """A study (summary + annotated disease) or a metabolite (RefMet + compound record)."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        kind, value = parsed
        try:
            if kind == "study":
                summary = await self._study_summary(value)
                if summary is None:
                    return None
                disease = await self._disease(value)
                concept = self._study_to_concept(summary, disease)
            else:
                parts = await self._metabolite_parts(kind, value)
                if parts is None:
                    return None
                concept = self._metabolite_to_concept(*parts)
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(
                f"Metabolomics Workbench get_concept_details failed for '{concept_id}': {e}"
            )
            return None

    async def _disease(self, study_id: str) -> str:
        """Annotated disease of a study; failures only cost the annotation."""
        try:
            records = self._records(await self._get(f"study/study_id/{study_id}/disease"))
            return _clean(records[0].get("Disease")) if records else ""
        except Exception as e:
            logger.warning(f"Metabolomics Workbench disease lookup failed for {study_id}: {e}")
            return ""

    # ------------------------------------------------------------------
    # Mappings / relationships
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """PubChem CID, KEGG, HMDB, ChEBI, LIPID MAPS, MetaCyc and InChIKey of a metabolite.

        Taken from the RefMet and compound records of the same registry entry, so they are
        ``xref`` (same compound, not necessarily the same stereoisomer: lactic acid's RefMet
        entry is the L form, while another registry number holds the racemate), confidence 0.95.
        Studies have no cross-references.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None or parsed[0] == "study":
            return []
        try:
            parts = await self._metabolite_parts(*parsed)
        except Exception as e:
            logger.error(f"Metabolomics Workbench get_mappings failed for '{concept_id}': {e}")
            return []
        if parts is None:
            return []
        refmet, compound = parts
        from_id = _clean(refmet.get("refmet_id")) or f"regno:{_clean(compound.get('regno'))}"
        mappings: list[dict[str, Any]] = []
        for _field, prefix, value in self._iter_xrefs(refmet, compound):
            mappings.append(
                {
                    "fromId": from_id,
                    "toId": f"{prefix}:{value}",
                    "fromSource": "METABOLOMICSWORKBENCH",
                    "toSource": prefix,
                    "mappingType": "xref",
                    "confidence": 0.95,
                }
            )
        return mappings

    async def get_relationships(
        self, concept_id: str, limit: int = _DEFAULT_RELATIONS
    ) -> list[dict[str, Any]]:
        """Study -> measured metabolites (``measures_metabolite``) and metabolite -> studies
        (``measured_in_study``, newest first).

        A study's metabolite list is de-duplicated by RefMet name over all its analyses
        (``analyses`` counts them); unmatched features are skipped, and ``related_id`` is the
        RefMet *name* because the study endpoint does not return RefMet ids (pass it to
        :meth:`get_concept_details` to resolve). Both directions are capped at ``limit``;
        common metabolites occur in over a thousand studies, big studies have hundreds of
        features, and both listings can be ~100 KB.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None or limit <= 0:
            return []
        kind, value = parsed
        try:
            if kind == "study":
                return await self._study_metabolites(value, limit)
            parts = await self._metabolite_parts(kind, value)
            name = _clean(parts[0].get("name")) if parts else ""
            if not name:
                return []
            data = await self._get(f"study/refmet_name/{self._seg(name)}/summary")
            studies = sorted(
                {_clean(r.get("study_id")) for r in self._records(data)} - {""}, reverse=True
            )
            return [
                {
                    "relation_label": "measured_in_study",
                    "related_id": study,
                    "related_name": study,
                    "source": "METABOLOMICSWORKBENCH",
                    "total_studies": len(studies),
                }
                for study in studies[:limit]
            ]
        except Exception as e:
            logger.error(
                f"Metabolomics Workbench get_relationships failed for '{concept_id}': {e}"
            )
            return []

    async def _study_metabolites(self, study_id: str, limit: int) -> list[dict[str, Any]]:
        data = await self._get(f"study/study_id/{study_id}/metabolites")
        found: dict[str, dict[str, Any]] = {}
        for record in self._records(data):
            if _clean(record.get("study_id")).upper() != study_id:
                continue
            name = _clean(record.get("refmet_name"))
            if name.casefold() in _UNMATCHED_NAMES:
                continue
            entry = found.setdefault(
                name,
                {
                    "relation_label": "measures_metabolite",
                    "related_id": name,
                    "related_name": name,
                    "source": "METABOLOMICSWORKBENCH",
                    "analysis_ids": [],
                },
            )
            analysis = _clean(record.get("analysis_id"))
            if analysis and analysis not in entry["analysis_ids"]:
                entry["analysis_ids"].append(analysis)
        relationships = list(found.values())[:limit]
        for entry in relationships:
            entry["analyses"] = len(entry["analysis_ids"])
        return relationships

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _add_unique(target: list[str] | None, value: str) -> None:
        if target is not None and value and value.casefold() not in {t.casefold() for t in target}:
            target.append(value)

    def _study_to_concept(
        self, record: dict[str, Any], disease: str = ""
    ) -> UnifiedConcept | None:
        study_id, title = _clean(record.get("study_id")), _clean(record.get("study_title"))
        if not study_id or not title:
            return None
        concept = self._create_concept(study_id, title, ConceptType.STUDY)
        if concept.identifiers:
            concept.identifiers[0].url = f"{STUDY_PAGE_URL}{study_id}"
        species, analysis = _clean(record.get("species")), _clean(record.get("analysis_type"))
        parts = [f"{analysis} metabolomics study" if analysis else "Metabolomics study"]
        if species:
            parts.append(f"of {species}")
        if _clean(record.get("number_of_samples")):
            parts.append(f"({record['number_of_samples']} samples)")
        if _clean(record.get("institute")):
            parts.append(f"deposited by {record['institute']}")
        if disease:
            parts.append(f"; condition: {disease}")
        if concept.definitions is not None:
            concept.definitions.append(" ".join(parts).replace(" ;", ";"))
        for target, value in (
            (concept.categories, species),
            (concept.categories, disease),
            (concept.semantic_types, analysis),
        ):
            self._add_unique(target, value)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": "study",
                **{
                    k: _clean(record.get(k))
                    for k in (
                        "species",
                        "institute",
                        "analysis_type",
                        "number_of_samples",
                        "submission_date",
                        "release_date",
                        "version",
                        "license",
                    )
                },
                "disease": disease,
            }
        return concept

    def _match_to_concept(self, record: dict[str, Any]) -> UnifiedConcept | None:
        """Search hit from ``refmet/match`` (name, formula, classes; ``-`` when no match)."""
        ref_id, name = _clean(record.get("refmet_id")), _clean(record.get("refmet_name"))
        if not ref_id or not name:
            return None
        concept = self._create_concept(ref_id, name, ConceptType.METABOLITE)
        if concept.identifiers:
            concept.identifiers[0].url = f"{REFMET_PAGE_URL}{ref_id}"
        self._add_classification(concept, record)
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": "metabolite",
                "formula": _clean(record.get("formula")),
                "exactmass": _clean(record.get("exactmass")),
            }
        return concept

    def _add_classification(self, concept: UnifiedConcept, record: dict[str, Any]) -> None:
        for key in ("super_class", "main_class", "sub_class"):
            self._add_unique(concept.categories, _clean(record.get(key)))

    def _iter_xrefs(
        self, refmet: dict[str, Any], compound: dict[str, Any]
    ) -> list[tuple[str, str, str]]:
        """Unique ``(field, CURIE prefix, value)``; the RefMet record wins over the compound."""
        out: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        for field, prefix, _ks in _XREFS:
            for record in (refmet, compound):
                value = _clean(record.get(field))
                if prefix == "CHEBI":
                    value = value.removeprefix("CHEBI:")
                if value and (prefix, value) not in seen:
                    seen.add((prefix, value))
                    out.append((field, prefix, value))
        return out

    def _metabolite_to_concept(
        self, refmet: dict[str, Any], compound: dict[str, Any]
    ) -> UnifiedConcept | None:
        ref_id = _clean(refmet.get("refmet_id"))
        regno = _clean(compound.get("regno")) or _clean(refmet.get("regno"))
        label = _clean(refmet.get("name")) or _clean(compound.get("name"))
        primary = ref_id or (f"regno:{regno}" if regno else "")
        if not primary or not label:
            return None
        concept = self._create_concept(primary, label, ConceptType.METABOLITE)
        if ref_id and concept.identifiers:
            concept.identifiers[0].url = f"{REFMET_PAGE_URL}{ref_id}"
        for name in (compound.get("name"), compound.get("sys_name")):
            if _clean(name).casefold() != label.casefold():
                self._add_unique(concept.synonyms, _clean(name))
        self._add_classification(concept, refmet)
        formula = _clean(refmet.get("formula")) or _clean(compound.get("formula"))
        mass = _clean(refmet.get("exactmass")) or _clean(compound.get("exactmass"))
        if concept.definitions is not None and formula:
            concept.definitions.append(
                f"Metabolite {label}, formula {formula}" + (f", exact mass {mass}" if mass else "")
            )
        known = {i.source for i in concept.identifiers or []}
        for _field, prefix, value in self._iter_xrefs(refmet, compound):
            source = next(ks for f, p, ks in _XREFS if p == prefix)
            if source and KnowledgeSource(source) not in known:
                concept.add_identifier(KnowledgeSource(source), value, label)
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "kind": "metabolite",
                "refmet_id": ref_id,
                "regno": regno,
                "formula": formula,
                "exactmass": mass,
                "smiles": _clean(refmet.get("smiles")) or _clean(compound.get("smiles")),
                "inchi_key": _clean(refmet.get("inchi_key")) or _clean(compound.get("inchi_key")),
                "hmdb_id": _clean(compound.get("hmdb_id")),
                "metacyc_id": _clean(compound.get("metacyc_id")),
            }
        return concept
