"""
Rhea adapter.

Rhea (https://www.rhea-db.org, SIB Swiss Institute of Bioinformatics) is the expert-curated
database of biochemical reactions behind UniProt's catalytic-activity annotation, with every
participant tied to a ChEBI compound. Data is CC BY 4.0 (attribute Rhea / SIB). No key.

Two keyless services are used, both verified live:

* **Search** - ``https://www.rhea-db.org/rhea?query=...&columns=...&format=tsv&limit=...``
  returns one row per *master* reaction. ``query`` accepts free text, ``RHEA:23444``,
  ``CHEBI:16651`` (every reaction that uses the compound, the most useful reverse lookup for
  metabolomics) and ``ec:1.1.1.27``. Unknown ``columns`` are silently dropped from the header,
  so rows are read by header name. Useful columns: ``rhea-id``, ``equation``, ``chebi`` (names),
  ``chebi-id``, ``ec``, ``uniprot`` (the header says "Enzymes": a UniProtKB count),
  ``pubmed``, ``go``, ``reaction-xref(KEGG|MetaCyc|Reactome|EcoCyc|M-CSA)``. Multi-valued cells
  are separated by ``;`` (Reactome ids by ``,``). ``format=json`` adds ``status`` and
  ``comment``. Lucene syntax characters in a query give a 500 HTML page, so they are blanked.
  The same endpoint under ``/rhea/<id>.json`` (single-record downloads) sits behind a
  Cloudflare challenge and is not used. Directional (L->R, R->L) and bidirectional variants
  are *not* in the search index (``query=RHEA:23445`` finds nothing).
* **SPARQL** - ``https://sparql.rhea-db.org/sparql`` for what search cannot give: participants
  with side and stoichiometry (predicate ``rh:containsN``), directional / bidirectional
  variants (``rh:directionalReaction``, ``rh:bidirectionalReaction``), the generic parent
  reaction (``rdfs:subClassOf``) and status. It answers ``application/sparql-results+json``
  even when JSON is requested, so bodies are parsed by hand. Reaction ids come in blocks
  ``N`` (master), ``N+1`` (L->R), ``N+2`` (R->L), ``N+3`` (bidirectional); the master of a
  variant is found by probing those four candidates (an inverse triple pattern times out).
  The endpoint stalls occasionally (one 60 s timeout seen); only relationships suffer, search
  and details do not use it except to resolve variant ids.

Requests are spaced by ``_MIN_INTERVAL`` (no published limit).
"""

import asyncio
import csv
import io
import json
import logging
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

RHEA_SEARCH_URL = "https://www.rhea-db.org/rhea"
RHEA_SPARQL_URL = "https://sparql.rhea-db.org/sparql"
RHEA_ENTRY_URL = "https://www.rhea-db.org/rhea/{}"
RH = "http://rdf.rhea-db.org/"

_MIN_INTERVAL = 0.5
_MAX_ROWS = 100
_SEARCH_COLUMNS = "rhea-id,equation,ec,chebi-id"
_DETAIL_COLUMNS = (
    "rhea-id,equation,chebi,chebi-id,ec,uniprot,pubmed,go,"
    "reaction-xref(KEGG),reaction-xref(MetaCyc),reaction-xref(Reactome),"
    "reaction-xref(EcoCyc),reaction-xref(M-CSA)"
)
# Header text -> field name, for the columns requested above.
_HEADERS = {
    "Reaction identifier": "id",
    "Equation": "equation",
    "ChEBI name": "chebi_names",
    "ChEBI identifier": "chebi_ids",
    "EC number": "ec",
    "Enzymes": "uniprot_count",
    "PubMed": "pubmed",
    "Gene Ontology": "go",
    "Cross-reference (KEGG)": "kegg",
    "Cross-reference (MetaCyc)": "metacyc",
    "Cross-reference (Reactome)": "reactome",
    "Cross-reference (EcoCyc)": "ecocyc",
    "Cross-reference (M-CSA)": "mcsa",
}
# (field, target database) pairs reported by get_mappings, in this order.
_XREF_FIELDS = (
    ("ec", "EC"),
    ("kegg", "KEGG"),
    ("metacyc", "MetaCyc"),
    ("reactome", "Reactome"),
    ("ecocyc", "EcoCyc"),
    ("mcsa", "M-CSA"),
)

_ID_RE = re.compile(
    r"^(?:https?://(?:www\.rhea-db\.org/rhea|rdf\.rhea-db\.org)/|RHEA[:_\s]?)?(\d{1,8})$",
    re.IGNORECASE,
)
_CHEBI_RE = re.compile(r"^CHEBI[:_](\d+)$", re.IGNORECASE)
_EC_RE = re.compile(r"^(?:EC[:\s]?)?(\d+\.\d+\.\d+\.(?:\d+|-))$", re.IGNORECASE)
_LUCENE_RE = re.compile(r'[+\-&|!(){}\[\]^"~*?:\\/]')
_STOICH_RE = re.compile(r"contains(\d+|N|n)$")
_GO_RE = re.compile(r"^(GO:\d+)\s*(.*)$")
_PREFIX_RE = re.compile(r"^(?:KEGG|MetaCyc|Reactome|EcoCyc|M-CSA):")


def _split(cell: str, separators: str = ";") -> list[str]:
    parts = re.split(f"[{re.escape(separators)}]", cell or "")
    return [p.strip() for p in parts if p.strip()]


def _bare(cell: str, separators: str = ";,") -> list[str]:
    """Split a cross-reference cell and drop the ``KEGG:`` / ``Reactome:`` style prefix."""
    return [_PREFIX_RE.sub("", item) for item in _split(cell, separators)]


class RheaAdapter(KnowledgeSourceAdapter):
    """Adapter for Rhea reactions (TSV search + SPARQL for structure)."""

    min_request_timeout = 45.0

    def __init__(self, config):
        super().__init__(config)
        self.search_url = RHEA_SEARCH_URL
        self.sparql_url = RHEA_SPARQL_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.RHEA

    def is_available(self) -> bool:
        return True  # public services, no key

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _wait_turn(self) -> None:
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _search(self, query: str, columns: str, limit: int, fmt: str = "tsv") -> str | None:
        await self._wait_turn()
        params = {"query": query, "columns": columns, "format": fmt, "limit": limit}
        return await self._make_request_text(self.search_url, params)

    async def _tsv(self, query: str, columns: str, limit: int) -> list[dict[str, str]]:
        """Run a search and return its rows keyed by field name (de-duplicated by id)."""
        text = await self._search(query, columns, min(limit, _MAX_ROWS))
        text = (text or "").strip("\r\n")
        if text.lstrip().startswith("<"):
            raise RuntimeError("Rhea returned an HTML page (blocked or invalid query)")
        reader = csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader, [])
        names = [_HEADERS.get(h, h) for h in header]
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for values in reader:
            row = dict(zip(names, values, strict=False))
            rid = row.get("id", "")
            if rid and rid not in seen:
                seen.add(rid)
                rows.append(row)
        return rows

    async def _status(self, number: str) -> dict[str, Any]:
        """``status`` / ``comment`` / ``balanced`` / ``transport`` from the JSON search format."""
        text = await self._search(f"RHEA:{number}", "rhea-id", 1, "json")
        data = json.loads(text or "{}")
        results = data.get("results") or []
        return results[0] if results else {}

    async def _sparql(self, query: str) -> list[dict[str, str]]:
        await self._wait_turn()
        text = await self._make_request_text(
            self.sparql_url, {"query": query}, {"Accept": "application/sparql-results+json"}
        )
        data = json.loads(text or "{}")
        bindings = (data.get("results") or {}).get("bindings") or []
        return [{k: str(v.get("value", "")) for k, v in row.items()} for row in bindings]

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _number(concept_id: str) -> str | None:
        """``RHEA:23444`` / ``23444`` / ``rhea_23444`` / Rhea URL -> ``"23444"``."""
        match = _ID_RE.match((concept_id or "").strip())
        return str(int(match.group(1))) if match else None

    @staticmethod
    def _search_query(text: str) -> str:
        """Translate user text into the Rhea query language."""
        match = _ID_RE.match(text)
        if match:
            return f"RHEA:{int(match.group(1))}"
        match = _CHEBI_RE.match(text)
        if match:
            return f"CHEBI:{int(match.group(1))}"
        match = _EC_RE.match(text)
        if match:
            return f"ec:{match.group(1)}"
        return " ".join(_LUCENE_RE.sub(" ", text).split())

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search reactions by text, ``RHEA:`` id, ``CHEBI:`` id or EC number.

        ``CHEBI:16651`` returns every reaction that uses (S)-lactate as a participant, in
        Rhea's relevance order. Directional / bidirectional ids are resolved to a concept
        too (via SPARQL) although the search index does not list them.
        """
        text = " ".join((query or "").split())
        if not text or limit <= 0:
            return []
        try:
            rhea_query = self._search_query(text)
            if not rhea_query:
                return []
            rows = await self._tsv(rhea_query, _SEARCH_COLUMNS, limit)
            concepts = [c for c in (self._row_to_concept(r) for r in rows[:limit]) if c]
            if not concepts and _ID_RE.match(text):
                variant = await self.get_concept_details(text)
                concepts = [variant] if variant else []
            logger.info(f"Rhea search for '{text}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"Rhea search failed for '{text}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Reaction with EC numbers, GO term, cross-references and curation status.

        Accepts ``RHEA:23444`` / ``23444``. Master reactions come from the TSV search plus
        the JSON status; directional and bidirectional ids (``RHEA:23445`` ... ``23447``)
        are described from SPARQL and point at their master reaction.
        """
        number = self._number(concept_id)
        if number is None:
            return None
        try:
            rows = await self._tsv(f"RHEA:{number}", _DETAIL_COLUMNS, 1)
            if rows:
                try:
                    status = await self._status(number)
                except Exception as e:
                    logger.warning(f"Rhea status lookup failed for {number}: {e}")
                    status = {}
                return self._row_to_concept(rows[0], status, detailed=True)
            return await self._variant_concept(number)
        except Exception as e:
            logger.error(f"Rhea get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _info(self, number: str) -> dict[str, Any]:
        """Facts about one reaction node from SPARQL (any of master / L-R / R-L / bidi)."""
        query = (
            f"PREFIX rh: <{RH}> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
            "SELECT ?p ?o ?olabel ?osubs WHERE { "
            f"rh:{number} ?p ?o . "
            "FILTER(?p IN (rdfs:subClassOf, rh:directionalReaction, rh:bidirectionalReaction, "
            "rh:status, rh:equation, rh:substrates, rh:ec)) "
            "OPTIONAL { ?o rdfs:label ?olabel } OPTIONAL { ?o rh:substrates ?osubs } }"
        )
        info: dict[str, Any] = {
            "kind": "master",
            "ec": [],
            "parents": [],
            "directional": [],
            "bidirectional": [],
        }
        found = False
        for row in await self._sparql(query):
            found = True
            predicate = row.get("p", "").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            obj = row.get("o", "")
            tail = obj.rsplit("/", 1)[-1]
            if predicate == "equation":
                info["equation"] = obj
            elif predicate == "status":
                info["status"] = tail.lower()
            elif predicate == "ec":
                info["ec"].append(f"EC:{tail}")
            elif predicate == "substrates":
                info["substrates_side"] = tail.rsplit("_", 1)[-1]
            elif predicate == "subClassOf":
                if tail in ("DirectionalReaction", "BidirectionalReaction"):
                    info["kind"] = tail.replace("Reaction", "").lower()
                elif tail.isdigit():
                    info["parents"].append((f"RHEA:{tail}", row.get("olabel", "")))
            elif predicate in ("directionalReaction", "bidirectionalReaction"):
                key = "directional" if predicate == "directionalReaction" else "bidirectional"
                direction = "L-R" if row.get("osubs", "").endswith("_L") else "R-L"
                info[key].append((f"RHEA:{tail}", row.get("olabel", ""), direction))
        return info if found else {}

    async def _master_number(self, number: str) -> str | None:
        """Master reaction of a directional / bidirectional id (blocks of four)."""
        value = int(number)
        candidates = " ".join(f"rh:{value - k}" for k in range(4) if value - k > 0)
        query = (
            f"PREFIX rh: <{RH}> SELECT ?m WHERE {{ VALUES ?m {{ {candidates} }} "
            f"?m ?p rh:{number} . "
            "FILTER(?p IN (rh:directionalReaction, rh:bidirectionalReaction)) }"
        )
        for row in await self._sparql(query):
            return row.get("m", "").rsplit("/", 1)[-1]
        return None

    async def _variant_concept(self, number: str) -> UnifiedConcept | None:
        info = await self._info(number)
        if not info or info["kind"] == "master" or not info.get("equation"):
            return None
        master = await self._master_number(number)
        concept = self._create_concept(
            f"RHEA:{number}", info["equation"], ConceptType.MOLECULAR_FUNCTION
        )
        if concept.identifiers:
            concept.identifiers[0].url = RHEA_ENTRY_URL.format(number)
        if concept.semantic_types is not None:
            concept.semantic_types.append(f"{info['kind']} reaction")
        if concept.categories is not None:
            concept.categories.extend(info["ec"])
        if master:
            concept.parents = [f"RHEA:{master}"]
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            data = {
                "equation": info["equation"],
                "direction": self._direction(info),
                "status": info.get("status"),
                "master": f"RHEA:{master}" if master else None,
                "ec": info["ec"],
            }
            concept.source_data[self.get_source()] = {k: v for k, v in data.items() if v}
        return concept

    @staticmethod
    def _direction(info: dict[str, Any]) -> str:
        if info["kind"] == "bidirectional":
            return "bidirectional"
        return "L-R" if info.get("substrates_side") == "L" else "R-L"

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Participants, EC numbers, GO term, generic parent and directional variants.

        * ``has_substrate`` / ``has_product`` - ChEBI participants of the left / right side as
          written for this reaction (``side`` L/R, ``stoichiometry``); a master or
          bidirectional reaction is reversible, so "substrate" just means left side.
          For an R->L variant the sides are swapped to match its reaction direction.
        * ``has_ec_number`` - ``EC:`` numbers (name is the number itself).
        * ``has_go_term`` - GO molecular-function term of the reaction (master only).
        * ``is_a`` - the generic Rhea reaction this one specialises (``a (2S)-2-hydroxy...``).
        * ``has_directional_variant`` / ``has_bidirectional_variant`` (master) or
          ``variant_of`` (variant) with ``direction`` L-R / R-L / bidirectional.
        """
        number = self._number(concept_id)
        if number is None or limit <= 0:
            return []
        try:
            info = await self._info(number)
        except Exception as e:
            logger.error(f"Rhea get_relationships failed for '{concept_id}': {e}")
            return []
        if not info:
            return []
        rels: list[dict[str, Any]] = []
        master = number
        if info["kind"] != "master":
            found = await self._master_number(number)
            master = found or ""
            if found:
                rels.append(
                    self._rel("variant_of", f"RHEA:{found}", "", direction=self._direction(info))
                )
        if master:
            rels.extend(await self._participant_relations(master, info))
        for ec in info["ec"]:
            rels.append(self._rel("has_ec_number", ec, ec))
        for related_id, label in info["parents"]:
            rels.append(self._rel("is_a", related_id, label))
        for related_id, label, direction in info["directional"]:
            rels.append(
                self._rel("has_directional_variant", related_id, label, direction=direction)
            )
        for related_id, label, _ in info["bidirectional"]:
            rels.append(
                self._rel(
                    "has_bidirectional_variant", related_id, label, direction="bidirectional"
                )
            )
        if info["kind"] == "master":
            rels.extend(await self._go_relations(number))
        return rels[:limit]

    @staticmethod
    def _rel(label: str, related_id: str, name: str, **extra: Any) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": related_id,
            "related_name": name,
            "source": "Rhea",
            **extra,
        }

    async def _participant_relations(
        self, master: str, info: dict[str, Any]
    ) -> list[dict[str, Any]]:
        query = (
            f"PREFIX rh: <{RH}> SELECT ?side ?pred ?acc ?name WHERE {{ "
            f"VALUES ?side {{ rh:{master}_L rh:{master}_R }} ?side ?pred ?part . "
            f'FILTER(STRSTARTS(STR(?pred), "{RH}contains") && ?pred != rh:contains) '
            "?part rh:compound ?c . ?c rh:accession ?acc . ?c rh:name ?name }"
        )
        swap = info["kind"] == "directional" and info.get("substrates_side") == "R"
        entries = []
        for row in await self._sparql(query):
            side = row.get("side", "")[-1:]
            stoich = _STOICH_RE.search(row.get("pred", ""))
            if side not in ("L", "R") or not stoich:
                continue
            entries.append((side, row.get("name", ""), row.get("acc", ""), stoich.group(1)))
        rels = []
        for side, name, acc, count in sorted(entries, key=lambda e: (e[0], e[1].lower())):
            left = (side == "L") != swap
            rels.append(
                self._rel(
                    "has_substrate" if left else "has_product",
                    acc,
                    name,
                    side=side,
                    stoichiometry=int(count) if count.isdigit() else count,
                )
            )
        rels.sort(key=lambda r: r["relation_label"] != "has_substrate")
        return rels

    async def _go_relations(self, number: str) -> list[dict[str, Any]]:
        try:
            rows = await self._tsv(f"RHEA:{number}", "rhea-id,go", 1)
        except Exception as e:
            logger.error(f"Rhea GO lookup failed for {number}: {e}")
            return []
        rels = []
        for cell in _split(rows[0].get("go", "") if rows else ""):
            match = _GO_RE.match(cell)
            if match:
                rels.append(self._rel("has_go_term", match.group(1), match.group(2)))
        return rels

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """EC, KEGG, MetaCyc, Reactome, EcoCyc, M-CSA, GO and a UniProt enzyme count.

        The UniProt entry is ``mappingType: "enzyme_count"`` with the number of UniProtKB
        enzymes annotated with the reaction in ``count`` and the UniProt query that lists them
        (``rhea:23444``) as ``toId``. Variant ids map via their master reaction.
        """
        number = self._number(concept_id)
        if number is None:
            return []
        try:
            rows = await self._tsv(f"RHEA:{number}", _DETAIL_COLUMNS, 1)
            if not rows:
                master = await self._master_number(number)
                rows = await self._tsv(f"RHEA:{master}", _DETAIL_COLUMNS, 1) if master else []
        except Exception as e:
            logger.error(f"Rhea get_mappings failed for '{concept_id}': {e}")
            return []
        if not rows:
            return []
        row = rows[0]
        from_id = f"RHEA:{number}"
        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(database: str, identifier: str, mapping_type: str = "xref", **extra: Any) -> None:
            if identifier and (database, identifier) not in seen:
                seen.add((database, identifier))
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": identifier,
                        "fromSource": "RHEA",
                        "toSource": database,
                        "mappingType": mapping_type,
                        "confidence": 0.95,
                        **extra,
                    }
                )

        for key, database in _XREF_FIELDS:
            for cell in _bare(row.get(key, "")) if key != "ec" else _split(row.get(key, "")):
                add(database, cell)
        for cell in _split(row.get("go", "")):
            match = _GO_RE.match(cell)
            if match:
                add("GO", match.group(1))
        count = row.get("uniprot_count", "")
        if count.isdigit() and int(count) > 0:
            add(
                "UniProt",
                f"rhea:{row.get('id', from_id).split(':')[-1]}",
                "enzyme_count",
                count=int(count),
            )
        return mappings

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _row_to_concept(
        self, row: dict[str, str], status: dict[str, Any] | None = None, detailed: bool = False
    ) -> UnifiedConcept | None:
        rhea_id = row.get("id", "").strip()
        equation = row.get("equation", "").strip()
        if not _ID_RE.match(rhea_id) or not equation:
            return None
        number = rhea_id.split(":")[-1]
        concept = self._create_concept(rhea_id, equation, ConceptType.MOLECULAR_FUNCTION)
        if concept.identifiers:
            concept.identifiers[0].url = RHEA_ENTRY_URL.format(number)
        ecs = _split(row.get("ec", ""))
        if concept.categories is not None:
            concept.categories.extend(ecs)
        if concept.semantic_types is not None:
            concept.semantic_types.append("master reaction")
        concept.confidence_score = 0.9
        data: dict[str, Any] = {
            "equation": equation,
            "ec": ecs,
            "chebi_ids": _split(row.get("chebi_ids", "")),
        }
        if detailed:
            data.update(
                chebi_names=_split(row.get("chebi_names", "")),
                pubmed=_split(row.get("pubmed", "")),
                go=_split(row.get("go", "")),
                kegg=_bare(row.get("kegg", "")),
                metacyc=_bare(row.get("metacyc", "")),
                reactome=_bare(row.get("reactome", "")),
                uniprot_count=int(row["uniprot_count"])
                if row.get("uniprot_count", "").isdigit()
                else None,
            )
            self._add_identifiers(concept, data)
        if status:
            data["status"] = status.get("status")
            data["balanced"] = status.get("balanced")
            data["transport"] = status.get("transport")
            comment = " ".join(str(status.get("comment") or "").split())
            if comment and concept.definitions is not None:
                concept.definitions.append(comment)
            if status.get("transport") and concept.semantic_types is not None:
                concept.semantic_types.append("transport reaction")
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                k: v for k, v in data.items() if v not in (None, [], "")
            }
        return concept

    @staticmethod
    def _add_identifiers(concept: UnifiedConcept, data: dict[str, Any]) -> None:
        for entry in data.get("kegg", []):
            concept.add_identifier(
                KnowledgeSource.KEGG, entry, None, f"https://www.genome.jp/entry/{entry}"
            )
        for entry in data.get("reactome", []):
            concept.add_identifier(
                KnowledgeSource.REACTOME,
                entry,
                None,
                f"https://reactome.org/content/detail/{entry}",
            )
        for entry in data.get("go", []):
            match = _GO_RE.match(entry)
            if match:
                concept.add_identifier(
                    KnowledgeSource.GO,
                    match.group(1),
                    match.group(2) or None,
                    f"https://amigo.geneontology.org/amigo/term/{match.group(1)}",
                )
