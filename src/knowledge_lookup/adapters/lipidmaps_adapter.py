"""
LIPID MAPS adapter.

Wraps two keyless LIPID MAPS services (https://www.lipidmaps.org), because neither one
covers all lookups on its own:

* **REST** (``https://www.lipidmaps.org/rest/compound/<field>/<value>/all``) - exact
  look-ups into LMSD, the LIPID MAPS Structure Database. The searchable fields are
  ``lm_id``, ``abbrev`` (bulk abbreviation such as ``PC(34:1)``), ``abbrev_chains``
  (``PC(16:0_18:1)``), ``formula``, ``inchi_key``, ``pubchem_cid``, ``chebi_id``,
  ``hmdb_id``, ``kegg_id``, ``regno`` and ``smiles``. There is **no name search**:
  ``compound/name/cholesterol`` answers with an HTML error saying the input item does not
  exist. A miss is ``200 []``; an unknown field is ``200 text/html``; an abbreviation that
  contains ``/`` must keep the slash raw (``%2F`` gives a 404).
* **SPARQL** (``https://lipidmaps.org/sparql``) - used for the free-text name search, the
  SwissLipids cross-references and lipid class members, none of which the REST API offers.
  Lipids are ``https://www.lipidmaps.org/rdf/<LM id>`` nodes with two ``rdfs:label`` values
  (common and systematic name), ``rdfs:subClassOf`` pointing at the sub class node and
  ``owl:equivalentClass`` pointing at ChEBI / SwissLipids. Category nodes are
  ``.../rdf/category/<n>`` labelled like ``Cholesterol and derivatives [ST0101]``; the
  hierarchy between category nodes is stored inverted (parent ``subClassOf`` child) so it is
  not used here. Send ``Accept: application/json`` or the answer arrives as
  ``application/sparql-results+json``, which aiohttp's ``json()`` rejects.

RefMet is not part of LIPID MAPS; its identifier is obtained best effort from the
Metabolomics Workbench REST service (``refmet/inchi_key/<key>/all``).

Identifiers are LMSD ids (``LMGP01010005``) and class codes (``LMGP``, ``LMGP01``,
``LMGP0101`` = category, main class, sub class; the bracketed ``GP0101`` form is accepted).
LIPID MAPS data is free to use with attribution (cite Sud et al., Nucleic Acids Res. 2007 and
O'Donnell et al.); see https://www.lipidmaps.org/about/terms_of_use. Requests are spaced by
``_MIN_INTERVAL`` because no daily limit is published.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

LIPIDMAPS_REST_URL = "https://www.lipidmaps.org/rest"
LIPIDMAPS_SPARQL_URL = "https://lipidmaps.org/sparql"
REFMET_REST_URL = "https://www.metabolomicsworkbench.org/rest/refmet"
LIPIDMAPS_ENTRY_URL = "https://www.lipidmaps.org/databases/lmsd/{}"
RDF_BASE = "https://www.lipidmaps.org/rdf/"
CATEGORY_BASE = "https://www.lipidmaps.org/rdf/category/"

# Politeness: LIPID MAPS publishes no rate limit; stay at ~2 requests per second.
_MIN_INTERVAL = 0.5
_MAX_SYNONYMS = 50
_MAX_ROWS = 100
_MAX_TOKENS = 5

_CORES = ("FA", "GL", "GP", "SP", "ST", "PR", "SL", "PK")
_LM_ID_RE = re.compile(r"^LM[A-Z]{2}\d{8}$")
_CLASS_RE = re.compile(rf"^(?:LM)?\[?({'|'.join(_CORES)})((?:\d{{2}}){{0,2}})\]?$")
_INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
_HMDB_RE = re.compile(r"^HMDB(\d{5,7})$", re.IGNORECASE)
_CHEBI_RE = re.compile(r"^CHEBI[:_](\d+)$", re.IGNORECASE)
_KEGG_RE = re.compile(r"^C\d{5}$")
_CID_RE = re.compile(r"^(?:PUBCHEM[:_]?|CID[:_]?)(\d+)$", re.IGNORECASE)
_FORMULA_RE = re.compile(r"^(?:[A-Z][a-z]?\d*){2,}$")
# "PC(34:1)", "PC 34:1", "ST 27:1;O", "PC(16:0_18:1)", "PC(O-16:0/18:1)", "FA 20:4"
_ABBREV_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,9}[ (]\s*(?:[OPopd]-)?[dtm]?\d+:\d+")
_BRACKET_RE = re.compile(r"^(.*?)\s*\[([A-Z]{2}(?:\d{2}){0,2})\]\s*$")
_SAFE_PATH = "/(),:;_-+"
_XREF_FIELDS = (
    ("pubchem_cid", "PubChem"),
    ("chebi_id", "ChEBI"),
    ("hmdb_id", "HMDB"),
    ("kegg_id", "KEGG"),
    ("lipidbank_id", "LipidBank"),
    ("metacyc_id", "MetaCyc"),
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _sparql_literal(text: str) -> str:
    """Escape *text* for a double-quoted SPARQL string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _split_class(label: str) -> tuple[str, str]:
    """``"Cholesterol and derivatives [ST0101]"`` -> ``("Cholesterol and derivatives", "ST0101")``."""
    match = _BRACKET_RE.match(label or "")
    if match:
        return match.group(1).strip(), match.group(2)
    return _clean(label), ""


def _class_codes(lm_id: str) -> list[str]:
    """``LMGP01010005`` -> ``["LMGP0101", "LMGP01", "LMGP"]`` (sub class first)."""
    if not _LM_ID_RE.match(lm_id):
        return []
    core, main, sub = lm_id[2:4], lm_id[4:6], lm_id[4:8]
    return [f"LM{core}{sub}", f"LM{core}{main}", f"LM{core}"]


class LipidMapsAdapter(KnowledgeSourceAdapter):
    """Adapter for LIPID MAPS (LMSD) via its REST and SPARQL services."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.rest_url = LIPIDMAPS_REST_URL
        self.sparql_url = LIPIDMAPS_SPARQL_URL
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.LIPIDMAPS

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

    async def _rest(self, field: str, value: str, output: str = "all") -> list[dict[str, Any]]:
        """Run one REST lookup and return its records (``[]`` for a miss).

        The service answers 200 with ``[]`` for a miss, ``Row1..RowN`` objects for several hits
        and an HTML page for an unknown field, so the body is parsed by hand.
        """
        await self._wait_turn()
        path = f"{self.rest_url}/compound/{field}/{quote(value, safe=_SAFE_PATH)}/{output}"
        text = await self._make_request_text(path)
        text = (text or "").strip()
        if not text.startswith(("{", "[")):
            return []
        data = json.loads(text)
        if isinstance(data, dict):
            if any(key.startswith("Row") for key in data):
                rows = [row for key, row in data.items() if key.startswith("Row")]
            else:
                rows = [data]
        else:
            rows = data
        return [row for row in rows if isinstance(row, dict) and row.get("lm_id")]

    async def _sparql(self, query: str) -> list[dict[str, str]]:
        """Run a SPARQL SELECT and flatten each binding to ``{variable: value}``."""
        await self._wait_turn()
        data = await self._make_request(
            self.sparql_url, {"query": query}, {"Accept": "application/json"}
        )
        bindings = ((data or {}).get("results") or {}).get("bindings") or []
        return [{k: str(v.get("value", "")) for k, v in row.items()} for row in bindings]

    # ------------------------------------------------------------------
    # Identifier handling
    # ------------------------------------------------------------------

    @staticmethod
    def _lm_id(concept_id: str) -> str | None:
        text = (concept_id or "").strip().upper().replace("LIPIDMAPS:", "")
        text = text.rsplit("/", 1)[-1]
        return text if _LM_ID_RE.match(text) else None

    @staticmethod
    def _class_code(concept_id: str) -> str | None:
        """``LMST0101`` / ``ST0101`` / ``[ST0101]`` -> ``"ST0101"``; not a class -> ``None``."""
        match = _CLASS_RE.match((concept_id or "").strip().upper())
        if not match:
            return None
        digits = match.group(2)
        raw = (concept_id or "").strip().upper()
        # A bare two-letter code ("PC", "ST") is ordinary text; require LM prefix or digits.
        if not digits and not raw.startswith("LM"):
            return None
        return f"{match.group(1)}{digits}"

    def _id_route(self, text: str) -> tuple[str, str] | None:
        """Map an identifier-like query to the REST ``(field, value)`` that answers it."""
        lm_id = self._lm_id(text)
        if lm_id:
            return "lm_id", lm_id
        if _INCHIKEY_RE.match(text.upper()):
            return "inchi_key", text.upper()
        hmdb = _HMDB_RE.match(text)
        if hmdb:
            return "hmdb_id", f"HMDB{int(hmdb.group(1)):07d}"
        chebi = _CHEBI_RE.match(text)
        if chebi:
            return "chebi_id", str(int(chebi.group(1)))
        cid = _CID_RE.match(text)
        if cid:
            return "pubchem_cid", str(int(cid.group(1)))
        if _KEGG_RE.match(text.upper()):
            return "kegg_id", text.upper()
        return None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Find lipids by id, cross-reference id, abbreviation, formula or name.

        Identifier-, abbreviation- and formula-shaped queries use the exact REST lookups;
        everything else (and every REST miss) is a case-insensitive SPARQL label search in
        which all words must occur, exact labels first, then shorter labels. LIPID MAPS holds
        a common and a systematic name per lipid, so ``cholesterol`` also finds
        ``cholest-5-en-3beta-ol``; trivial names of other lipids need their own spelling.
        """
        text = _clean(query)
        if not text or limit <= 0:
            return []
        try:
            klass = self._class_code(text)
            if klass:
                concept = await self._class_concept(klass)
                return [concept] if concept else []
            concepts = await self._search_rest(text, limit)
            if not concepts:
                concepts = await self._search_name(text, limit)
            logger.info(f"LIPID MAPS search for '{text}' returned {len(concepts)} concepts")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"LIPID MAPS search failed for '{text}': {e}")
            return []

    async def _search_rest(self, text: str, limit: int) -> list[UnifiedConcept]:
        routes: list[tuple[str, str]] = []
        route = self._id_route(text)
        if route:
            routes.append(route)
        elif _ABBREV_RE.match(text):
            if "_" in text:
                routes.append(("abbrev_chains", text))
            routes.append(("abbrev", text))
        elif _FORMULA_RE.match(text) and any(ch.isdigit() for ch in text):
            routes.append(("formula", text))
        for field, value in routes:
            try:
                rows = await self._rest(field, value)
            except Exception as e:
                logger.error(f"LIPID MAPS REST {field}={value} failed: {e}")
                continue
            concepts = self._unique(self._record_to_concept(r) for r in rows[:limit])
            if concepts:
                return concepts
        return []

    @staticmethod
    def _unique(items: Any) -> list[UnifiedConcept]:
        seen: set[str] = set()
        out: list[UnifiedConcept] = []
        for concept in items:
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                out.append(concept)
        return out

    async def _search_name(self, text: str, limit: int) -> list[UnifiedConcept]:
        tokens = text.lower().split()[:_MAX_TOKENS]
        conditions = " && ".join(f'CONTAINS(LCASE(?name), "{_sparql_literal(t)}")' for t in tokens)
        exact = _sparql_literal(" ".join(tokens))
        query = (
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
            "PREFIX chebi: <http://purl.obolibrary.org/obo/chebi/> "
            "PREFIX lmo: <https://www.lipidmaps.org/ontology/> "
            "SELECT ?s ?name ?formula ?abbrev ?clsLabel WHERE { "
            "?s rdfs:label ?name . "
            f'FILTER(STRSTARTS(STR(?s), "{RDF_BASE}LM") && {conditions}) '
            "OPTIONAL { ?s chebi:formula ?formula } "
            "OPTIONAL { ?s lmo:abbrev ?abbrev } "
            "OPTIONAL { ?s rdfs:subClassOf ?cls . ?cls rdfs:label ?clsLabel } } "
            f'ORDER BY (LCASE(?name) != "{exact}") STRLEN(?name) '
            f"LIMIT {min(max(limit * 3, 10), _MAX_ROWS)}"
        )
        rows = await self._sparql(query)
        return self._unique(self._sparql_row_to_concept(r) for r in rows)[:limit]

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Full LMSD record (REST ``all``) for an LM id; class codes give a class concept.

        Cross-reference ids (InChIKey, ``HMDB0000067``, ``CHEBI:16113``, ``CID:5997``, KEGG
        compound ids) are accepted too and resolve to the first matching lipid.
        """
        text = _clean(concept_id)
        if not text:
            return None
        try:
            klass = self._class_code(text)
            if klass:
                return await self._class_concept(klass)
            route = self._id_route(text)
            if route is None:
                return None
            rows = await self._rest(*route)
            return self._record_to_concept(rows[0]) if rows else None
        except Exception as e:
            logger.error(f"LIPID MAPS get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships / mappings
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Classification path of a lipid, or the contents of a lipid class.

        * lipid -> ``is_a`` sub class, main class and category (``level`` names the rung,
          ``direct`` is true for the sub class); ids are class codes such as ``LMGP0101``.
        * sub class -> ``has_member`` lipids (at most ``limit``) and ``is_a`` its main class
          and category; main class / category -> ``has_subclass`` child classes.
        """
        text = _clean(concept_id)
        if not text or limit <= 0:
            return []
        try:
            klass = self._class_code(text)
            if klass:
                return await self._class_relationships(klass, limit)
            lm_id = self._lm_id(text)
            if lm_id is None:
                return []
            rows = await self._rest("lm_id", lm_id, "classification")
            if not rows:
                return []
            row = rows[0]
            rels: list[dict[str, Any]] = []
            for level, key, code in zip(
                ("sub_class", "main_class", "core"),
                ("sub_class", "main_class", "core"),
                _class_codes(lm_id),
                strict=True,
            ):
                name, _ = _split_class(row.get(key, ""))
                if name:
                    rels.append(
                        {
                            "relation_label": "is_a",
                            "related_id": code,
                            "related_name": name,
                            "source": "LIPID MAPS",
                            "level": level,
                            "direct": level == "sub_class",
                        }
                    )
            return rels[:limit]
        except Exception as e:
            logger.error(f"LIPID MAPS get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-references of a lipid: PubChem, ChEBI, HMDB, KEGG, LipidBank, SwissLipids, RefMet.

        PubChem/ChEBI/HMDB/KEGG/LipidBank come from the REST record. SwissLipids (and a second
        ChEBI statement) come from ``owl:equivalentClass`` in the SPARQL endpoint; RefMet
        comes from the Metabolomics Workbench using the InChIKey. Both extra calls are best
        effort: a failure only drops those mappings.
        """
        lm_id = self._lm_id(_clean(concept_id))
        if lm_id is None:
            return []
        try:
            rows = await self._rest("lm_id", lm_id)
        except Exception as e:
            logger.error(f"LIPID MAPS get_mappings failed for '{concept_id}': {e}")
            return []
        if not rows:
            return []
        row = rows[0]
        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(database: str, identifier: str, confidence: float = 0.95) -> None:
            if identifier and (database, identifier) not in seen:
                seen.add((database, identifier))
                mappings.append(
                    {
                        "fromId": lm_id,
                        "toId": identifier,
                        "fromSource": "LIPIDMAPS",
                        "toSource": database,
                        "mappingType": "xref",
                        "confidence": confidence,
                    }
                )

        for key, database in _XREF_FIELDS:
            value = _clean(row.get(key))
            if value:
                add(database, f"CHEBI:{value}" if database == "ChEBI" else value)
        try:
            query = (
                "SELECT ?o WHERE { "
                f"<{RDF_BASE}{lm_id}> <http://www.w3.org/2002/07/owl#equivalentClass> ?o }}"
            )
            for item in await self._sparql(query):
                uri = item.get("o", "")
                if "swisslipids.org" in uri:
                    add("SwissLipids", uri.rsplit("/", 1)[-1].replace("_", ":"))
                elif "CHEBI_" in uri:
                    add("ChEBI", "CHEBI:" + uri.rsplit("_", 1)[-1])
        except Exception as e:
            logger.error(f"LIPID MAPS SPARQL cross-references failed for '{lm_id}': {e}")
        refmet = await self._refmet_id(_clean(row.get("inchi_key")))
        if refmet:
            add("RefMet", refmet, 0.9)
        return mappings

    async def _refmet_id(self, inchi_key: str) -> str:
        if not _INCHIKEY_RE.match(inchi_key):
            return ""
        try:
            await self._wait_turn()
            data = await self._make_request(f"{REFMET_REST_URL}/inchi_key/{inchi_key}/all")
            return _clean((data or {}).get("refmet_id")) if isinstance(data, dict) else ""
        except Exception as e:
            logger.error(f"RefMet lookup failed for '{inchi_key}': {e}")
            return ""

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    async def _class_labels(self, codes: list[str]) -> dict[str, str]:
        """``{"ST0101": "Cholesterol and derivatives", ...}`` for the given class codes."""
        conditions = " || ".join(f'CONTAINS(?l, "[{c}]")' for c in codes)
        query = (
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
            "SELECT ?l WHERE { ?c rdfs:label ?l . "
            f'FILTER(STRSTARTS(STR(?c), "{CATEGORY_BASE}") && ({conditions})) }}'
        )
        labels: dict[str, str] = {}
        for item in await self._sparql(query):
            name, code = _split_class(item.get("l", ""))
            if code in codes and name:
                labels[code] = name
        return labels

    async def _class_concept(self, code: str) -> UnifiedConcept | None:
        names = await self._class_labels([code])
        if code not in names:
            return None
        concept_id = f"LM{code}"
        concept = self._create_concept(concept_id, names[code], ConceptType.CHEMICAL)
        level = {2: "category", 4: "main class", 6: "sub class"}[len(code)]
        if concept.semantic_types is not None:
            concept.semantic_types.append(f"lipid {level}")
        if concept.synonyms is not None:
            concept.synonyms.append(f"[{code}]")
        if concept.definitions is not None:
            concept.definitions.append(f"LIPID MAPS lipid {level} {code}: {names[code]}")
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {"class_code": code, "level": level}
        return concept

    async def _class_relationships(self, code: str, limit: int) -> list[dict[str, Any]]:
        parents = [f"{code[:n]}" for n in (4, 2) if n < len(code)]
        names = await self._class_labels([code, *parents])
        rels: list[dict[str, Any]] = []
        for parent in parents:
            if parent in names:
                rels.append(
                    {
                        "relation_label": "is_a",
                        "related_id": f"LM{parent}",
                        "related_name": names[parent],
                        "source": "LIPID MAPS",
                        "direct": parent == parents[0],
                    }
                )
        if len(code) == 6:
            query = (
                "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
                "SELECT ?s ?name WHERE { ?cat rdfs:label ?l . "
                f'FILTER(STRSTARTS(STR(?cat), "{CATEGORY_BASE}") && CONTAINS(?l, "[{code}]")) '
                "?s rdfs:subClassOf ?cat . ?s rdfs:label ?name . "
                f'FILTER(STRSTARTS(STR(?s), "{RDF_BASE}LM")) }} '
                f"LIMIT {min(limit * 3, _MAX_ROWS)}"
            )
            seen: set[str] = set()
            for item in await self._sparql(query):
                member = item.get("s", "").rsplit("/", 1)[-1]
                if member in seen:
                    continue
                seen.add(member)
                rels.append(
                    {
                        "relation_label": "has_member",
                        "related_id": member,
                        "related_name": item.get("name", ""),
                        "source": "LIPID MAPS",
                    }
                )
                if len(seen) >= limit:
                    break
        else:
            width = len(code) + 2
            query = (
                "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
                "SELECT ?l WHERE { ?c rdfs:label ?l . "
                f'FILTER(STRSTARTS(STR(?c), "{CATEGORY_BASE}") && CONTAINS(?l, "[{code}")) }}'
            )
            for item in await self._sparql(query):
                name, child = _split_class(item.get("l", ""))
                if child and len(child) == width and child.startswith(code) and name:
                    rels.append(
                        {
                            "relation_label": "has_subclass",
                            "related_id": f"LM{child}",
                            "related_name": name,
                            "source": "LIPID MAPS",
                        }
                    )
            rels = rels[: max(limit, 1) + len(parents)]
        return rels

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _record_to_concept(self, row: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a REST ``all`` record (flat string fields) to a concept."""
        lm_id = _clean(row.get("lm_id"))
        sys_name = _clean(row.get("sys_name"))
        label = _clean(row.get("name")) or sys_name or lm_id
        if not lm_id:
            return None
        concept = self._create_concept(lm_id, label, ConceptType.CHEMICAL)
        if concept.identifiers:
            concept.identifiers[0].url = LIPIDMAPS_ENTRY_URL.format(lm_id)
        if concept.synonyms is not None:
            names = [sys_name, _clean(row.get("abbrev")), _clean(row.get("abbrev_chains"))]
            names += [_clean(s) for s in (row.get("synonyms") or "").split(";")]
            for name in names:
                if name and name != label and name not in concept.synonyms:
                    concept.synonyms.append(name)
            del concept.synonyms[_MAX_SYNONYMS:]
        levels = {k: _split_class(row.get(k, "")) for k in ("core", "main_class", "sub_class")}
        if concept.categories is not None:
            concept.categories.extend(name for name, _ in levels.values() if name)
        if concept.semantic_types is not None:
            concept.semantic_types.append("lipid")
        sub_name, sub_code = levels["sub_class"]
        if sub_name:
            concept.parents = [sub_name]
            if concept.definitions is not None:
                core_name = levels["core"][0]
                concept.definitions.append(
                    f"Lipid classified as {sub_name} ({sub_code}) within {core_name}."
                )
        pubchem, chebi, kegg = (_clean(row.get(k)) for k in ("pubchem_cid", "chebi_id", "kegg_id"))
        if pubchem:
            concept.add_identifier(
                KnowledgeSource.PUBCHEM,
                pubchem,
                label,
                f"https://pubchem.ncbi.nlm.nih.gov/compound/{pubchem}",
            )
        if chebi:
            concept.add_identifier(
                KnowledgeSource.CHEBI,
                f"CHEBI:{chebi}",
                label,
                f"https://www.ebi.ac.uk/chebi/{chebi}",
            )
        if kegg:
            concept.add_identifier(
                KnowledgeSource.KEGG, kegg, label, f"https://www.genome.jp/entry/{kegg}"
            )
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            keep = (
                "regno",
                "sys_name",
                "abbrev",
                "abbrev_chains",
                "core",
                "main_class",
                "sub_class",
                "formula",
                "exactmass",
                "inchi_key",
                "inchi",
                "smiles",
                "hmdb_id",
                "lipidbank_id",
            )
            concept.source_data[self.get_source()] = {
                k: row[k] for k in keep if row.get(k) not in (None, "")
            }
        return concept

    def _sparql_row_to_concept(self, row: dict[str, str]) -> UnifiedConcept | None:
        """Convert a SPARQL name-search row (thin: id, name, formula, abbreviation, class)."""
        lm_id = row.get("s", "").rsplit("/", 1)[-1]
        label = _clean(row.get("name"))
        if not _LM_ID_RE.match(lm_id) or not label:
            return None
        concept = self._create_concept(lm_id, label, ConceptType.CHEMICAL)
        if concept.identifiers:
            concept.identifiers[0].url = LIPIDMAPS_ENTRY_URL.format(lm_id)
        abbrev = _clean(row.get("abbrev"))
        if abbrev and concept.synonyms is not None:
            concept.synonyms.append(abbrev)
        class_name, class_code = _split_class(row.get("clsLabel", ""))
        if class_name:
            if concept.categories is not None:
                concept.categories.append(class_name)
            concept.parents = [class_name]
        if concept.semantic_types is not None:
            concept.semantic_types.append("lipid")
        concept.confidence_score = 0.8
        if isinstance(concept.source_data, dict):
            data = {
                "formula": row.get("formula"),
                "abbrev": abbrev,
                "sub_class": f"{class_name} [{class_code}]" if class_code else class_name,
            }
            concept.source_data[self.get_source()] = {k: v for k, v in data.items() if v}
        return concept
