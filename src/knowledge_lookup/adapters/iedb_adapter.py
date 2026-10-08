"""
IEDB adapter.

The Immune Epitope Database (https://www.iedb.org, NIAID) catalogues experimentally
characterised B cell, T cell and MHC-ligand epitopes. Its keyless "IQ-API"
(https://query-api.iedb.org, see https://help.iedb.org/hc/en-us/articles/4402872882189) is a
PostgREST service. Data may be used freely with attribution (cite Vita et al., Nucleic Acids
Res. 2025); there is no published rate limit, so requests are spaced politely.

PostgREST syntax used (all verified live):

* ``select=a,b`` limits columns - mandatory in practice: one popular epitope carries ~300
  assay ids and a whole antigen (``antigen_search`` for Spike) 780 KB of ``structure_ids``.
* ``col=eq.X``, ``col=in.(1,2,3)`` and ``limit=n``; ``or=(c1.ilike."*x*",c2.ilike."*x*")`` and
  ``and=(or(...),or(...))``. Values are double-quoted so commas/parentheses cannot break the
  filter.
* ``epitope_search``/``antigen_search`` columns such as ``structure_descriptions``,
  ``source_organism_names`` and ``parent_source_antigen_names`` are **arrays**, and
  ``ilike`` on them fails with ``operator does not exist: character varying[] ~~* unknown``.
  The ``cs.{...}`` operator matches whole elements only, and the ``*_iri_search`` arrays only
  accept ontology ids. So free-text search goes through ``epitope_export``, a flat table of
  text columns (``epitope__name``, ``epitope__source_molecule``, ``epitope__source_organism``,
  ``epitope__species``) with one row per epitope x source molecule x organism, joined back to
  ``epitope_search`` on ``structure_id``.
* ``Prefer: count=exact`` is NOT used: counting Spike epitopes took 53 s. Assay counts come
  from the ``tcell_ids`` / ``bcell_ids`` / ``elution_ids`` arrays of the single epitope instead.

Latency is uneven: ``eq`` / ``in`` lookups take 1-2 s, but a text filter that few rows satisfy
(for instance "SARS-CoV-2 Omicron spike") scans the table and took 6-15 s, so the class
allows 60 s per request (``min_request_timeout``).

The IEDB epitope id is ``IEDB_EPITOPE:<n>``; antigens are keyed by UniProt (``UNIPROT:P0DTC2``).
"""

import asyncio
import logging
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

IEDB_API_URL = "https://query-api.iedb.org"
IEDB_EPITOPE_URL = "https://www.iedb.org/epitope/{}"
IEDB_ANTIGEN_URL = "https://www.iedb.org/antigen/{}"

_MIN_INTERVAL = 0.5
_MAX_ROWS = 200
_MAX_PUBMED = 25
_MAX_TOKENS = 4

# Light projection for lists, heavier one for a single epitope (arrays of assay ids etc.).
_LIGHT_SELECT = (
    "structure_id,structure_iri,structure_type,linear_sequence,linear_sequence_length,"
    "structure_descriptions,parent_source_antigen_iris,parent_source_antigen_names,"
    "parent_source_antigen_source_org_iris,parent_source_antigen_source_org_names"
)
_DETAIL_SELECT = (
    _LIGHT_SELECT + ",curated_source_antigens,source_organism_iris,source_organism_names,"
    "host_organism_iris,host_organism_names,mhc_allele_iris,mhc_allele_names,mhc_classes,"
    "disease_iris,disease_names,tcell_ids,bcell_ids,elution_ids,pdb_ids,chebi_ids,pubmed_ids,"
    "epitope_structures_defined"
)
_ANTIGEN_SELECT = (
    "parent_source_antigen_iri,parent_source_antigen_names,"
    "parent_source_antigen_source_org_iri,parent_source_antigen_source_org_name"
)
_TEXT_COLUMNS = (
    "epitope__name",
    "epitope__source_molecule",
    "epitope__source_organism",
    "epitope__species",
)
# Short names researchers type -> substrings IEDB actually uses (OR-ed per token).
_ALIASES: dict[str, tuple[str, ...]] = {
    "sars-cov-2": ("SARS-CoV2", "SARS-CoV-2", "coronavirus 2"),
    "sars-cov2": ("SARS-CoV2", "SARS-CoV-2", "coronavirus 2"),
    "sarscov2": ("SARS-CoV2", "SARS-CoV-2", "coronavirus 2"),
    "covid": ("SARS-CoV2", "SARS-CoV-2", "coronavirus 2"),
    "covid-19": ("SARS-CoV2", "SARS-CoV-2", "coronavirus 2"),
    "ebv": ("Epstein-Barr", "gammaherpesvirus 4"),
    "hhv-4": ("Epstein-Barr", "gammaherpesvirus 4"),
    "cmv": ("cytomegalovirus", "betaherpesvirus 5"),
    "hcmv": ("cytomegalovirus", "betaherpesvirus 5"),
    "hhv-6": ("herpesvirus 6", "betaherpesvirus 6"),
    "hsv": ("herpes simplex", "alphaherpesvirus"),
    "vzv": ("varicella", "alphaherpesvirus 3"),
    "hiv": ("immunodeficiency virus",),
    "mers": ("MERS", "Middle East respiratory"),
}

_EPITOPE_ID_RE = re.compile(
    r"^(?:IEDB[_:\s-]?EPITOPE[:_\s]?|IEDB[:_\s])?(\d{1,9})$", re.IGNORECASE
)
_UNIPROT_RE = re.compile(
    r"^(?:UNIPROT:)?([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})"
    r"(?:\.\d+)?$",
    re.IGNORECASE,
)
_SEQUENCE_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]{6,60}$")
_UNIPROT_NAME_SUFFIX_RE = re.compile(r"\s*\((?:UniProt|GenPept|PDB):[^)]*\)\s*$")


def _quote(value: str) -> str:
    """PostgREST double-quoted filter value (escapes backslash and double quote)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _strs(value: Any) -> list[str]:
    """A JSON array column as a list of non-empty strings (``null`` -> ``[]``)."""
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if v not in (None, "")]


def _pairs(iris: Any, names: Any) -> list[tuple[str, str]]:
    """Pair parallel ``*_iris`` / ``*_names`` columns - only when that is unambiguous.

    IEDB sorts each array on its own, so with more than one element the n-th iri does not
    belong to the n-th name (``source_organism_iris`` listed ``NCBITaxon:9606`` beside
    "SARS-CoV2"). A single element each is safe; otherwise only the iris are kept.
    """
    iri_list, name_list = _strs(iris), _strs(names)
    if len(iri_list) == len(name_list) == 1:
        return [(iri_list[0], name_list[0])]
    return [(iri, "") for iri in iri_list]


def _antigen_iri(iri: str) -> str:
    """IEDB files GenBank proteins under ``UNIPROT:`` too (``UNIPROT:QHD43416.1``); fix that."""
    prefix, _, accession = iri.partition(":")
    if prefix.upper() == "UNIPROT" and not _UNIPROT_RE.match(accession):
        return f"GENPEPT:{accession}"
    return iri


def _antigen_name(text: str) -> str:
    return _UNIPROT_NAME_SUFFIX_RE.sub("", text or "").strip()


_NAME_ACCESSION_RE = re.compile(r"\(UniProt:([A-Z0-9]+)\)\s*$")


def _antigens(row: dict[str, Any]) -> list[tuple[str, str]]:
    """Reference-proteome antigens as ``(UNIPROT:acc, name)``.

    The accession is read from the ``(UniProt:P0DTC2)`` suffix of the name, which stays right
    even though the iri and name arrays are sorted independently.
    """
    found: list[tuple[str, str]] = []
    for name in _strs(row.get("parent_source_antigen_names")):
        match = _NAME_ACCESSION_RE.search(name)
        if match and not name.startswith("Two components"):
            found.append((f"UNIPROT:{match.group(1)}", _antigen_name(name)))
    known = {iri for iri, _ in found}
    found += [
        (iri, "") for iri in _strs(row.get("parent_source_antigen_iris")) if iri not in known
    ]
    return found


class IEDBAdapter(KnowledgeSourceAdapter):
    """Adapter for the IEDB IQ-API (epitopes and their source antigens)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.base_url = IEDB_API_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.IEDB

    def is_available(self) -> bool:
        return True  # public API, no key

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _get(self, table: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """GET a PostgREST table; a PostgREST error object raises (and is logged upstream)."""
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(
            f"{self.base_url}/{table}", params, {"Accept": "application/json"}
        )
        if isinstance(data, dict):
            raise RuntimeError(f"IEDB error: {data.get('message') or data}")
        return [row for row in data or [] if isinstance(row, dict)]

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _epitope_number(concept_id: str) -> int | None:
        """``IEDB_EPITOPE:122017`` / ``IEDB:122017`` / ``122017`` -> ``122017``."""
        match = _EPITOPE_ID_RE.match((concept_id or "").strip())
        return int(match.group(1)) if match else None

    @staticmethod
    def _uniprot(concept_id: str) -> str | None:
        """``UNIPROT:P0DTC2`` / ``P0DTC2.1`` -> ``"P0DTC2"``; not an accession -> ``None``."""
        text = (concept_id or "").strip()
        match = _UNIPROT_RE.match(text)
        if not match:
            return None
        return match.group(1).upper()

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search epitopes by IEDB id, exact peptide, UniProt antigen, or free text.

        Free text must match every word in the epitope name, source molecule (antigen) or
        organism, so ``SARS-CoV-2 spike`` finds Spike epitopes of SARS-CoV-2 and ``EBV``
        finds Epstein-Barr virus epitopes (a few common virus abbreviations are expanded).
        Results are unordered, and one epitope can appear under several source organisms.
        An all-caps amino-acid string is tried as an exact ``linear_sequence`` first.
        """
        text = " ".join((query or "").split())
        if not text or limit <= 0:
            return []
        try:
            number = self._epitope_number(text)
            if number is not None:
                rows = await self._get(
                    "epitope_search", {"structure_id": f"eq.{number}", "select": _LIGHT_SELECT}
                )
                return self._concepts(rows, limit)
            accession = self._uniprot(text)
            if accession:
                antigen = await self._antigen(accession)
                return [antigen] if antigen else []
            if _SEQUENCE_RE.match(text):
                rows = await self._get(
                    "epitope_search",
                    {
                        "linear_sequence": f"eq.{text}",
                        "select": _LIGHT_SELECT,
                        "limit": min(limit, _MAX_ROWS),
                    },
                )
                if rows:
                    return self._concepts(rows, limit)
            concepts = await self._text_search(text, limit)
            logger.info(f"IEDB search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"IEDB search failed for '{text}': {e}")
            return []

    async def _text_search(self, text: str, limit: int) -> list[UnifiedConcept]:
        groups = []
        for token in text.split()[:_MAX_TOKENS]:
            patterns = _ALIASES.get(token.lower(), (token,))
            terms = [f"{col}.ilike.{_quote(f'*{p}*')}" for p in patterns for col in _TEXT_COLUMNS]
            groups.append(f"or({','.join(terms)})")
        rows = await self._get(
            "epitope_export",
            {
                "and": f"({','.join(groups)})",
                "select": "structure_id",
                "limit": min(max(limit * 5, 20), _MAX_ROWS),
            },
        )
        ids: list[int] = []
        for row in rows:
            value = row.get("structure_id")
            if isinstance(value, int) and value not in ids:
                ids.append(value)
        ids = ids[:limit]
        if not ids:
            return []
        found = await self._get(
            "epitope_search",
            {"structure_id": f"in.({','.join(map(str, ids))})", "select": _LIGHT_SELECT},
        )
        order = {value: i for i, value in enumerate(ids)}
        found.sort(key=lambda r: order.get(r.get("structure_id") or 0, len(order)))
        return self._concepts(found, limit)

    def _concepts(self, rows: list[dict[str, Any]], limit: int) -> list[UnifiedConcept]:
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for row in rows:
            concept = self._epitope_to_concept(row)
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concepts.append(concept)
        return concepts[:limit]

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full epitope record (assay counts, MHC alleles, diseases, hosts, PDB, PubMed).

        ``IEDB_EPITOPE:1309147`` / ``1309147`` give an epitope; a UniProt accession
        (``UNIPROT:P0DTC2``) gives the antigen with its source organism. The epitope's IEDB
        text summary is added as a definition when that (slow) lookup succeeds.
        """
        text = (concept_id or "").strip()
        try:
            number = self._epitope_number(text)
            if number is None:
                accession = self._uniprot(text)
                return await self._antigen(accession) if accession else None
            row = await self._epitope_row(number)
            concept = self._epitope_to_concept(row, detailed=True) if row else None
            if concept is not None and concept.definitions is not None:
                summary = await self._summary(number)
                if summary:
                    concept.definitions.append(summary)
            return concept
        except Exception as e:
            logger.error(f"IEDB get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _epitope_row(self, number: int) -> dict[str, Any] | None:
        rows = await self._get(
            "epitope_search", {"structure_id": f"eq.{number}", "select": _DETAIL_SELECT}
        )
        return rows[0] if rows else None

    async def _summary(self, number: int) -> str:
        try:
            rows = await self._get(
                "epitope_summary", {"structure_id": f"eq.{number}", "select": "epitope_summary"}
            )
        except Exception as e:
            logger.warning(f"IEDB epitope summary unavailable for {number}: {e}")
            return ""
        return " ".join(str(rows[0].get("epitope_summary") or "").split()) if rows else ""

    async def _antigen_row(self, accession: str) -> dict[str, Any] | None:
        rows = await self._get(
            "antigen_search",
            {
                "parent_source_antigen_iri": f"eq.UNIPROT:{accession}",
                "select": _ANTIGEN_SELECT,
                "limit": 1,
            },
        )
        return rows[0] if rows else None

    async def _antigen(self, accession: str) -> UnifiedConcept | None:
        row = await self._antigen_row(accession)
        if row is None:
            return None
        names = [_antigen_name(n) for n in _strs(row.get("parent_source_antigen_names"))]
        names = [n for n in names if n and not n.startswith("Two components")]
        label = names[0] if names else accession
        concept = self._create_concept(f"UNIPROT:{accession}", label, ConceptType.PROTEIN)
        if concept.identifiers:
            concept.identifiers[0].url = IEDB_ANTIGEN_URL.format(f"UNIPROT:{accession}")
        concept.add_identifier(
            KnowledgeSource.UNIPROT,
            accession,
            label,
            f"https://www.uniprot.org/uniprotkb/{accession}",
        )
        taxon = str(row.get("parent_source_antigen_source_org_iri") or "")
        organism = str(row.get("parent_source_antigen_source_org_name") or "")
        if concept.synonyms is not None:
            concept.synonyms.extend(n for n in names[1:] if n != label)
        if concept.semantic_types is not None:
            concept.semantic_types.append("IEDB source antigen")
        if concept.definitions is not None and organism:
            concept.definitions.append(
                f"{label}, source antigen of IEDB epitopes from {organism}."
            )
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            data = {"organism": organism, "organism_iri": taxon, "names": names}
            concept.source_data[self.get_source()] = {k: v for k, v in data.items() if v}
        return concept

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Source antigen, organisms, hosts, assay counts, MHC alleles and diseases of an epitope.

        * ``has_source_antigen`` - the reference-proteome antigen (``UNIPROT:``) and each
          curated antigen record (``UNIPROT:`` / ``GENPEPT:`` accession) with
          ``starting_position`` / ``ending_position`` of the epitope in it.
        * ``has_source_organism`` - NCBITaxon organisms of the antigen records;
          ``has_host_organism`` - organisms in which the response was measured.
        * ``has_tcell_assays`` / ``has_bcell_assays`` / ``has_mhc_ligand_assays`` - one entry
          per assay type with ``count``; ``related_id`` is the IQ-API query listing them.
        * ``restricted_by_mhc_allele`` - MRO allele ids with names (T cell / MHC ligand data).
        * ``associated_with_disease`` - disease ids/names the epitope was studied in.

        For an antigen id only ``has_source_organism`` is returned.
        """
        text = (concept_id or "").strip()
        if limit <= 0:
            return []
        try:
            number = self._epitope_number(text)
            if number is None:
                accession = self._uniprot(text)
                antigen = await self._antigen_row(accession) if accession else None
                if antigen is None:
                    return []
                return self._organism_rels(
                    [
                        (
                            str(antigen.get("parent_source_antigen_source_org_iri") or ""),
                            str(antigen.get("parent_source_antigen_source_org_name") or ""),
                        )
                    ]
                )[:limit]
            row = await self._epitope_row(number)
        except Exception as e:
            logger.error(f"IEDB get_relationships failed for '{concept_id}': {e}")
            return []
        if not row:
            return []
        return self._epitope_relationships(number, row)[:limit]

    @staticmethod
    def _rel(label: str, related_id: str, name: str, **extra: Any) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": related_id,
            "related_name": name,
            "source": "IEDB",
            **extra,
        }

    def _organism_rels(
        self, pairs: list[tuple[str, str]], label: str = "has_source_organism"
    ) -> list[dict[str, Any]]:
        rels: list[dict[str, Any]] = []
        seen: set[str] = set()
        for iri, name in pairs:
            # IEDB also has internal "taxon:1000..." ids for strains; only NCBI ids are portable.
            if iri.startswith("NCBITaxon:") and iri not in seen:
                seen.add(iri)
                rels.append(self._rel(label, iri, name))
        return rels

    def _epitope_relationships(self, number: int, row: dict[str, Any]) -> list[dict[str, Any]]:
        rels: list[dict[str, Any]] = []
        antigens = _antigens(row)
        for iri, name in antigens:
            rels.append(self._rel("has_source_antigen", iri, name))
        seen = {iri for iri, _ in antigens}
        curated = row.get("curated_source_antigens")
        curated_rels: list[dict[str, Any]] = []
        for item in curated if isinstance(curated, list) else []:
            if not isinstance(item, dict):
                continue
            iri = _antigen_iri(str(item.get("iri") or ""))
            key = f"{iri}:{item.get('starting_position')}:{item.get('ending_position')}"
            if not iri or key in seen:
                continue
            seen.add(key)
            extra = {
                k: item[k]
                for k in ("starting_position", "ending_position", "source_organism_name")
                if item.get(k) is not None
            }
            curated_rels.append(
                self._rel("has_source_antigen", iri, _antigen_name(item.get("name", "")), **extra)
            )
        organisms = _pairs(
            row.get("parent_source_antigen_source_org_iris"),
            row.get("parent_source_antigen_source_org_names"),
        )
        organisms += [
            (str(i.get("source_organism_iri") or ""), str(i.get("source_organism_name") or ""))
            for i in (curated if isinstance(curated, list) else [])
            if isinstance(i, dict)
        ]
        # Prefer the first non-empty name seen for an id.
        named = {iri: name for iri, name in reversed(organisms) if name}
        rels.extend(self._organism_rels([(iri, named.get(iri, name)) for iri, name in organisms]))
        # Hosts, MHC alleles and diseases come as independently sorted iri / name arrays, so
        # only the names are reliable; they are used as the related id.
        for name in _strs(row.get("host_organism_names")):
            rels.append(self._rel("has_host_organism", name, name))
        for label, key, table, name in (
            ("has_tcell_assays", "tcell_ids", "tcell_search", "T cell assays"),
            ("has_bcell_assays", "bcell_ids", "bcell_search", "B cell assays"),
            ("has_mhc_ligand_assays", "elution_ids", "mhc_search", "MHC ligand assays"),
        ):
            count = len(row.get(key) or [])
            if count:
                rels.append(
                    self._rel(label, f"{table}?structure_id=eq.{number}", name, count=count)
                )
        for name in _strs(row.get("mhc_allele_names")):
            rels.append(self._rel("restricted_by_mhc_allele", name, name))
        for name in _strs(row.get("disease_names")):
            rels.append(self._rel("associated_with_disease", name, name))
        # One record per curated database entry (often dozens of strain accessions): last.
        return rels + curated_rels

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """UniProt, NCBI Protein, NCBITaxon, PDB, ChEBI and PubMed ids of an epitope or antigen.

        UniProt comes from the reference-proteome antigen and from curated ``UNIPROT:``
        records (version suffixes are kept, e.g. ``P0DTC2.1``); NCBI Protein from curated
        ``GENPEPT:`` records. PubMed ids are capped at 25 (popular epitopes have 80+).
        """
        text = (concept_id or "").strip()
        try:
            number = self._epitope_number(text)
            if number is None:
                accession = self._uniprot(text)
                antigen = await self._antigen_row(accession) if accession else None
                if antigen is None:
                    return []
                row: dict[str, Any] | None = {
                    "parent_source_antigen_iris": [f"UNIPROT:{accession}"],
                    "parent_source_antigen_source_org_iris": _strs(
                        [antigen.get("parent_source_antigen_source_org_iri")]
                    ),
                }
                from_id = f"UNIPROT:{accession}"
            else:
                row = await self._epitope_row(number)
                from_id = f"IEDB_EPITOPE:{number}"
        except Exception as e:
            logger.error(f"IEDB get_mappings failed for '{concept_id}': {e}")
            return []
        if not row:
            return []
        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(database: str, identifier: str) -> None:
            if identifier and (database, identifier) not in seen:
                seen.add((database, identifier))
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": identifier,
                        "fromSource": "IEDB",
                        "toSource": database,
                        "mappingType": "xref",
                        "confidence": 0.95,
                    }
                )

        curated = row.get("curated_source_antigens")
        iris = [iri for iri, _ in _antigens(row)]
        iris += [
            _antigen_iri(str(item.get("iri") or ""))
            for item in (curated if isinstance(curated, list) else [])
            if isinstance(item, dict)
        ]
        for iri in iris:
            prefix, _, accession = iri.partition(":")
            if prefix == "UNIPROT":
                add("UniProt", accession)
            elif prefix == "GENPEPT":
                add("NCBI Protein", accession)
        taxa = _strs(row.get("parent_source_antigen_source_org_iris"))
        taxa += _strs(row.get("source_organism_iris"))
        taxa += [
            str(i.get("source_organism_iri") or "")
            for i in (curated if isinstance(curated, list) else [])
            if isinstance(i, dict)
        ]
        for iri in taxa:
            if iri.startswith("NCBITaxon:"):
                add("NCBITaxon", iri)
        for pdb in _strs(row.get("pdb_ids")):
            add("PDB", pdb.upper())
        for chebi in _strs(row.get("chebi_ids")):
            add("ChEBI", chebi if chebi.upper().startswith("CHEBI:") else f"CHEBI:{chebi}")
        for pubmed in _strs(row.get("pubmed_ids"))[:_MAX_PUBMED]:
            add("PubMed", pubmed)
        return mappings

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _epitope_to_concept(
        self, row: dict[str, Any], detailed: bool = False
    ) -> UnifiedConcept | None:
        structure_id = row.get("structure_id")
        if not isinstance(structure_id, int):
            return None
        descriptions = _strs(row.get("structure_descriptions"))
        sequence = str(row.get("linear_sequence") or "")
        label = sequence or (descriptions[0] if descriptions else f"IEDB epitope {structure_id}")
        concept = self._create_concept(
            f"IEDB_EPITOPE:{structure_id}", label, ConceptType.MOLECULAR_ENTITY
        )
        if concept.identifiers:
            concept.identifiers[0].url = IEDB_EPITOPE_URL.format(structure_id)
        structure_type = str(row.get("structure_type") or "")
        if concept.synonyms is not None:
            concept.synonyms.extend(d for d in descriptions if d != label)
        if concept.categories is not None and structure_type:
            concept.categories.append(structure_type)
        if concept.semantic_types is not None:
            concept.semantic_types.append("epitope")
        antigens = _antigens(row)
        organisms = _pairs(
            row.get("parent_source_antigen_source_org_iris"),
            row.get("parent_source_antigen_source_org_names"),
        )
        for iri, name in antigens:
            if iri.startswith("UNIPROT:"):
                accession = iri.split(":", 1)[1]
                concept.add_identifier(
                    KnowledgeSource.UNIPROT,
                    accession,
                    name or None,
                    f"https://www.uniprot.org/uniprotkb/{accession}",
                )
        for iri, name in organisms:
            if iri.startswith("NCBITaxon:"):
                taxon = iri.split(":", 1)[1]
                concept.add_identifier(
                    KnowledgeSource.NCBITAXONOMY,
                    taxon,
                    name or None,
                    f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={taxon}",
                )
        if concept.definitions is not None:
            antigen_text = ", ".join(n or i for i, n in antigens)
            organism_text = ", ".join(n or i for i, n in organisms)
            kind = structure_type.lower() or "epitope"
            size = row.get("linear_sequence_length")
            sized = f" of {size} residues" if size else ""
            origin = f" from {antigen_text}" if antigen_text else ""
            origin += f" ({organism_text})" if organism_text else ""
            concept.definitions.append(f"IEDB {kind}{sized}{origin}.")
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            data: dict[str, Any] = {
                "structure_type": structure_type,
                "linear_sequence": sequence,
                "linear_sequence_length": row.get("linear_sequence_length"),
                "antigens": [i for i, _ in antigens],
                "organisms": [i for i, _ in organisms],
            }
            if detailed:
                data.update(
                    tcell_assay_count=len(row.get("tcell_ids") or []),
                    bcell_assay_count=len(row.get("bcell_ids") or []),
                    mhc_ligand_assay_count=len(row.get("elution_ids") or []),
                    mhc_classes=_strs(row.get("mhc_classes")),
                    mhc_alleles=_strs(row.get("mhc_allele_names")),
                    diseases=_strs(row.get("disease_names")),
                    hosts=_strs(row.get("host_organism_names")),
                    pdb_ids=_strs(row.get("pdb_ids")),
                    pubmed_count=len(_strs(row.get("pubmed_ids"))),
                    epitope_structures_defined=_strs(row.get("epitope_structures_defined")),
                )
            concept.source_data[self.get_source()] = {
                k: v for k, v in data.items() if v not in (None, "", [], 0)
            }
        return concept
