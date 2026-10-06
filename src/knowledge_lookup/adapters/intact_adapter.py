"""
IntAct Knowledge Source Adapter

Adapter for IntAct (EMBL-EBI), the open-source database of *curated, experimentally
observed* molecular interactions (IMEx consortium curation, mostly protein-protein).
Contrast with STRING: STRING scores predicted and text-mined functional association,
IntAct only records interactions a curator extracted from a publication, with the
detection method, interaction type and PubMed id of every piece of evidence.

Two EBI services are used, because each one is good at a different job:

- ``https://www.ebi.ac.uk/intact/ws/interactor/findInteractor/{query}`` (IntAct web
  service, JSON) finds interactors by UniProt accession, gene name or IntAct ``EBI-``
  accession; it backs :meth:`search_concepts` and :meth:`get_concept_details`. The
  sibling ``interaction/findInteractions`` endpoint is *not* used: every interaction
  record carries its complete XML/JSON/MITAB renderings, about 190 kB per interaction
  (verified live: 2 BRCA1 interactions = 460 kB), which is far too heavy to rank a
  protein's partners.
- PSICQUIC (``https://www.ebi.ac.uk/Tools/webservices/psicquic/intact/webservices/current/
  search/query/{query}``, tab-separated MITAB) returns the same interaction evidence in
  about 1.3 kB per row (``tab25``), and supports Lucene filters such as
  ``intact-miscore:[0.7 TO 1]`` and ``negative:false``. It backs
  :meth:`get_relationships` and, with one ``tab27`` row, :meth:`get_mappings`.

Identifiers
-----------
``primary_id`` is the UniProt accession (``P38398``) because that is what the rest of
the library links on; interactors without one (small molecules, nucleic acids, peptides)
keep their IntAct accession (``EBI-21978329``). Every method accepts a UniProt accession
(also isoforms, ``P38398-1``), an ``EBI-`` accession, with or without ``UniProt:`` /
``IntAct:`` prefix, or an exact gene name (``BRCA1``; human preferred).

Scores
------
``intact-miscore`` (0-1) is a per-pair confidence that grows with the number of
independent publications, detection methods and interaction types supporting the pair;
it is the same on every evidence row of a pair. It is *not* comparable to STRING scores.

Rate limits and licence
-----------------------
Keyless; EBI asks for polite use (no bulk crawling). IntAct data are CC BY 4.0.
"""

import logging
import re
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

_INTACT_WS_URL = "https://www.ebi.ac.uk/intact/ws"
_PSICQUIC_URL = (
    "https://www.ebi.ac.uk/Tools/webservices/psicquic/intact/webservices/current/search/query"
)

_UNIPROT_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})"
    r"(?:-\d+|-PRO_\d+)?$"
)
_ISOFORM_RE = re.compile(r"-(?:\d+|PRO_\d+)$")
_EBI_RE = re.compile(r"^EBI-\d+$", re.I)
_PREFIX_RE = re.compile(r"^(?:uniprotkb|uniprot|intact)\s*:\s*", re.I)
_PMID_RE = re.compile(r"pubmed:(\d+)")
_MI_LABEL_RE = re.compile(r'^psi-mi:"?(MI:\d+)"?\((.*)\)$')
_SCORE_RE = re.compile(r"intact-miscore:([0-9.]+)")

# get_relationships asks PSICQUIC for evidence rows in descending score tiers and stops at
# the first tier that yields ``limit`` distinct partners: PSICQUIC cannot sort, so for hubs
# (TP53 has >1000 evidence rows) a plain ``maxResults`` would return an arbitrary subset.
_SCORE_TIERS = (0.7, 0.4, 0.0)
_MAX_EVIDENCE_ROWS = 400  # ~0.5 MB of tab25 per request
_MAX_PMIDS = 10
_MAX_XREFS_PER_DB = 10

# MITAB xref databases kept by get_mappings: PSI-MI db name -> display source name
_XREF_DBS = {
    "refseq": "RefSeq",
    "rcsb pdb": "PDB",
    "interpro": "InterPro",
    "reactome": "Reactome",
    "dip": "DIP",
    "mint": "MINT",
    "efo": "Orphanet",
}

_INTERACTOR_TYPES: dict[str, ConceptType] = {
    "protein": ConceptType.PROTEIN,
    "peptide": ConceptType.PROTEIN,
    "gene": ConceptType.GENE,
    "small molecule": ConceptType.CHEMICAL,
}


def _strip_prefix(identifier: str) -> str:
    return _PREFIX_RE.sub("", identifier.strip()).strip()


def _tokens(cell: str) -> list[tuple[str, str]]:
    """Split a MITAB multi-value cell into ``(db, value)`` pairs, dropping ``(label)`` tails."""
    pairs: list[tuple[str, str]] = []
    for token in cell.split("|"):
        token = token.strip()
        if not token or token == "-" or ":" not in token:
            continue
        db, value = token.split(":", 1)
        value = re.sub(r"\([^()]*\)$", "", value).strip().strip('"')
        pairs.append((db.strip().lower(), value))
    return pairs


def _label(cell: str) -> str:
    """The ``(label)`` of the first value in a MITAB cell such as ``psi-mi:"MI:0018"(two hybrid)``."""
    match = _MI_LABEL_RE.match(cell.split("|")[0].strip())
    return match.group(2) if match else ""


def _taxon(cell: str) -> tuple[int | None, str]:
    """``taxid:9606(human)|taxid:9606(Homo sapiens)`` -> ``(9606, "Homo sapiens")``."""
    entries = [e for e in cell.split("|") if e.startswith("taxid:")]
    if not entries:
        return None, ""
    match = re.match(r'taxid:(-?\d+)(?:\("?(.*?)"?\))?$', entries[-1])
    if not match:
        return None, ""
    taxid = int(match.group(1))
    return (taxid if taxid > 0 else None), (match.group(2) or "")


def _partner_name(alias_cell: str, fallback: str) -> str:
    """Gene name of an interactor from the MITAB alias cell (``uniprotkb:BRIP1(gene name)``)."""
    short = ""
    for token in alias_cell.split("|"):
        if token.endswith("(gene name)"):
            return token.split(":", 1)[1][: -len("(gene name)")]
        if token.endswith("(display_short)") and not short:
            short = token.split(":", 1)[1][: -len("(display_short)")]
    return short or fallback


class IntActAdapter(KnowledgeSourceAdapter):
    """Adapter for IntAct curated molecular interactions (human proteins by default)."""

    # PSICQUIC occasionally takes several seconds on hub proteins (TP53: ~4 s for 100 rows)
    min_request_timeout = 60.0

    def __init__(self, config, taxid: int | None = 9606):
        super().__init__(config)
        self.base_url = _INTACT_WS_URL
        self.psicquic_url = _PSICQUIC_URL
        # NCBI taxon id used to filter gene-name searches; None searches every species
        self.taxid = taxid

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.INTACT

    def is_available(self) -> bool:
        return True  # keyless public services

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search interactors by gene name, UniProt accession or ``EBI-`` accession.

        IntAct indexes molecules, not diseases or phenotypes: ``fatigue`` finds nothing,
        ``IL6`` finds the interleukin-6 protein. Results keep IntAct's relevance order;
        isoforms, chains and non-protein interactors (mRNA, gene records) are dropped and
        only ``taxid`` (human by default) is kept.
        """
        query = _strip_prefix(query or "")
        if not query or limit < 1:
            return []
        try:
            hits = await self._find_interactors(query, size=max(limit * 4, 20))
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for hit in hits:
                if not self._is_search_hit(hit, query):
                    continue
                concept = self._convert_interactor_to_concept(hit, confidence=0.9)
                if concept and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
                if len(concepts) >= limit:
                    break
            logger.info(f"IntAct search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"IntAct search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get an interactor (protein name, species, interaction count) by accession or name."""
        try:
            hit = await self._resolve_interactor(concept_id)
            return self._convert_interactor_to_concept(hit, confidence=1.0) if hit else None
        except Exception as e:
            logger.error(f"IntAct get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Return experimentally observed interaction partners, best score first.

        One ``interacts_with`` edge per partner (``related_id`` is the partner's UniProt
        accession, ``related_name`` its gene name) aggregated over all evidence rows:

        - ``score``: ``intact-miscore`` (0-1), the sort key
        - ``evidence_count``: number of curated evidence rows for the pair
        - ``detection_methods`` / ``interaction_types``: PSI-MI names, most frequent first
        - ``pmids``: up to 10 PubMed ids
        - ``species`` / ``taxid``: of the partner

        Evidence rows come from PSICQUIC in score tiers (>=0.7, >=0.4, all) and negative
        interactions are excluded. For very connected proteins the first tier is capped at
        400 rows, so the cut-off partners are still high scoring but the list may miss a few
        equally good ones. Self-interactions are skipped. Degrades to ``[]`` on any failure.
        """
        if limit < 1:
            return []
        try:
            accession = await self._resolve_accession(concept_id)
            if not accession:
                return []
            partners: dict[str, dict[str, Any]] = {}
            for min_score in _SCORE_TIERS:
                partners = await self._fetch_partners(accession, min_score)
                if len(partners) >= limit:
                    break
            ranked = sorted(
                partners.values(),
                key=lambda p: (-p["score"], -p["evidence_count"], p["related_name"].lower()),
            )
            return ranked[:limit]
        except Exception as e:
            logger.warning(f"IntAct get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return identifiers of the same interactor in other databases.

        Always: IntAct ``EBI-`` accession <-> UniProt accession (``exact``). When the
        interactor has interactions, one PSICQUIC ``tab27`` row adds Ensembl gene and
        protein ids, RefSeq, PDB, InterPro, Reactome, DIP, MINT and Orphanet disease xrefs
        (up to 10 per database, ``related``), plus up to 5 secondary UniProt accessions.
        Same ``{fromId, toId, fromSource, toSource, mappingType, confidence}`` shape as the
        Ensembl/KEGG adapters; degrades to ``[]`` on any failure.
        """
        try:
            hit = await self._resolve_interactor(concept_id)
            if not hit:
                return []
            ac = hit.get("interactorAc") or ""
            accession = hit.get("interactorPreferredIdentifier") or ac
            from_id = accession
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(to_source: str, to_id: str, mapping_type: str = "exact") -> None:
                if not to_id or (to_source, to_id) in seen or to_id == from_id:
                    return
                seen.add((to_source, to_id))
                mappings.append(
                    {
                        "fromId": from_id,
                        "toId": to_id,
                        "fromSource": "IntAct",
                        "toSource": to_source,
                        "mappingType": mapping_type,
                        "confidence": 1.0 if mapping_type == "exact" else 0.8,
                    }
                )

            if ac:
                add("IntAct", ac)
            if accession != ac and accession:
                add("UniProt", accession)
            try:
                row = await self._fetch_first_row(accession or ac)
            except Exception as e:  # the interactor-level mappings above are still valid
                logger.warning(f"IntAct xref lookup failed for '{concept_id}': {e}")
                row = []
            for source, to_id, mapping_type in self._row_xrefs(row, {accession.upper(), ac}):
                add(source, to_id, mapping_type)
            return mappings
        except Exception as e:
            logger.warning(f"IntAct get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # IntAct web service (interactors)
    # ------------------------------------------------------------------

    async def _find_interactors(self, query: str, size: int = 10) -> list[dict[str, Any]]:
        url = f"{self.base_url}/interactor/findInteractor/{quote(query, safe='')}"
        try:
            data = await self._make_request(url, {"page": 0, "pageSize": min(size, 100)})
        except Exception as e:  # 404 = no such interactor
            if getattr(e, "status", None) == 404:
                return []
            raise
        content = data.get("content") if isinstance(data, dict) else None
        return [h for h in content if isinstance(h, dict)] if isinstance(content, list) else []

    def _is_search_hit(self, hit: dict[str, Any], query: str) -> bool:
        """Proteins only, no isoforms/chains, restricted to ``self.taxid``."""
        if hit.get("interactorType") != "protein":
            return False
        if _ISOFORM_RE.search(str(hit.get("interactorPreferredIdentifier") or "")):
            return False
        # accession lookups name the exact molecule asked for, whatever the species
        kind = self._id_kind(query)
        return not (kind == "name" and self.taxid and hit.get("interactorTaxId") != self.taxid)

    @staticmethod
    def _id_kind(identifier: str) -> str:
        identifier = _strip_prefix(identifier)
        if _EBI_RE.match(identifier):
            return "ebi"
        if _UNIPROT_RE.match(identifier.upper()):
            return "uniprot"
        return "name"

    async def _resolve_interactor(self, concept_id: str) -> dict[str, Any]:
        """Find the one interactor an id or exact gene name refers to (``{}`` if unknown)."""
        query = _strip_prefix(concept_id or "")
        if not query:
            return {}
        hits = await self._find_interactors(query, size=30)
        kind = self._id_kind(query)
        wanted = query.upper()
        if kind == "uniprot":
            matches = [
                h for h in hits if str(h.get("interactorPreferredIdentifier")).upper() == wanted
            ]
        elif kind == "ebi":
            matches = [h for h in hits if str(h.get("interactorAc")).upper() == wanted]
        else:
            matches = [
                h
                for h in hits
                if str(h.get("interactorName", "")).upper() == wanted
                and h.get("interactorType") == "protein"
                and not _ISOFORM_RE.search(str(h.get("interactorPreferredIdentifier") or ""))
            ]
            in_species = [
                h for h in matches if not self.taxid or h.get("interactorTaxId") == self.taxid
            ]
            matches = in_species or matches
        if not matches:
            return {}
        return max(matches, key=lambda h: h.get("interactionCount") or 0)

    async def _resolve_accession(self, concept_id: str) -> str:
        """The id PSICQUIC ``id:`` queries need: UniProt/EBI accessions pass straight through."""
        query = _strip_prefix(concept_id or "")
        if not query:
            return ""
        if self._id_kind(query) != "name":
            return query.upper()
        hit = await self._resolve_interactor(query)
        return str(hit.get("interactorPreferredIdentifier") or hit.get("interactorAc") or "")

    # ------------------------------------------------------------------
    # PSICQUIC (interaction evidence)
    # ------------------------------------------------------------------

    async def _psicquic(self, query: str, fmt: str, max_results: int) -> list[list[str]]:
        """Run a PSICQUIC query and return the MITAB rows split into columns."""
        url = f"{self.psicquic_url}/{quote(query, safe='')}"
        text = await self._make_request_text(url, {"format": fmt, "maxResults": max_results})
        return [line.split("\t") for line in (text or "").splitlines() if line.strip()]

    async def _fetch_first_row(self, accession: str) -> list[str]:
        rows = await self._psicquic(f"id:{accession} AND negative:false", "tab27", 1)
        return rows[0] if rows else []

    async def _fetch_partners(self, accession: str, min_score: float) -> dict[str, dict[str, Any]]:
        """Aggregate the PSICQUIC evidence rows with ``intact-miscore >= min_score`` per partner."""
        query = f"id:{accession} AND negative:false"
        if min_score > 0:
            query += f" AND intact-miscore:[{min_score} TO 1]"
        rows = await self._psicquic(query, "tab25", _MAX_EVIDENCE_ROWS)
        self_ids = {accession.upper()}
        partners: dict[str, dict[str, Any]] = {}
        for row in rows:
            if len(row) < 15:
                continue
            side = self._partner_side(row, self_ids)
            if side is None:
                continue
            self._add_evidence(partners, row, side)
        for partner in partners.values():
            partner["detection_methods"] = self._by_frequency(partner.pop("_methods"))
            partner["interaction_types"] = self._by_frequency(partner.pop("_types"))
            partner["pmids"] = partner["pmids"][:_MAX_PMIDS]
        return partners

    @staticmethod
    def _partner_side(row: list[str], self_ids: set[str]) -> int | None:
        """Return 1 when the partner is column B (self is A), 0 when it is A, None to skip."""

        def holds_self(id_cell: str, alt_cell: str) -> bool:
            return any(v.upper() in self_ids for _, v in _tokens(id_cell) + _tokens(alt_cell))

        a_self = holds_self(row[0], row[2])
        b_self = holds_self(row[1], row[3])
        if a_self == b_self:  # self-interaction (both) or an unrelated row (neither)
            return None
        return 1 if a_self else 0

    @staticmethod
    def _add_evidence(partners: dict[str, dict[str, Any]], row: list[str], side: int) -> None:
        ids = _tokens(row[side])
        if not ids:
            return
        db, raw_value = ids[0]
        source = {"uniprotkb": "UniProt", "intact": "IntAct", "ensembl": "Ensembl"}.get(db, db)
        # Isoform (P08887-2) and chain (P08887-PRO_0000450730) partners count towards the
        # canonical accession, which is what other sources link on
        value = _ISOFORM_RE.sub("", raw_value) if db == "uniprotkb" else raw_value
        score_match = _SCORE_RE.search(row[14])
        score = float(score_match.group(1)) if score_match else 0.0
        taxid, species = _taxon(row[9 + side])

        partner = partners.get(value)
        if partner is None:
            intact_ids = [v for d, v in _tokens(row[2 + side]) if d == "intact"]
            partner = partners[value] = {
                "relation_label": "interacts_with",
                "related_id": value,
                "related_name": _partner_name(row[4 + side], value),
                "source": "IntAct",
                "related_id_source": source,
                "score": score,
                "evidence_count": 0,
                "pmids": [],
                "species": species,
                "taxid": taxid,
                "_methods": [],
                "_types": [],
            }
            if intact_ids:
                partner["intact_id"] = intact_ids[0]
        if raw_value != value:
            partner.setdefault("isoforms", [])
            if raw_value not in partner["isoforms"]:
                partner["isoforms"].append(raw_value)
        partner["score"] = max(partner["score"], score)
        partner["evidence_count"] += 1
        partner["_methods"].append(_label(row[6]))
        partner["_types"].append(_label(row[11]))
        for pmid in _PMID_RE.findall(row[8]):
            if pmid not in partner["pmids"]:
                partner["pmids"].append(pmid)

    @staticmethod
    def _by_frequency(values: list[str]) -> list[str]:
        counts: dict[str, int] = {}
        for value in values:
            if value:
                counts[value] = counts.get(value, 0) + 1
        return sorted(counts, key=lambda v: -counts[v])

    @staticmethod
    def _row_xrefs(row: list[str], self_ids: set[str]) -> list[tuple[str, str, str]]:
        """Cross-references of the query interactor from a ``tab27`` row.

        Returns ``(toSource, toId, mappingType)`` triples. The interactor is whichever side
        of the row (A: columns 1/3/23, B: 2/4/24) holds one of ``self_ids``.
        """
        if len(row) < 24:
            return []

        def holds_self(side: int) -> bool:
            return any(
                v.upper() in self_ids for _, v in _tokens(row[side]) + _tokens(row[2 + side])
            )

        if holds_self(0):
            side = 0
        elif holds_self(1):
            side = 1
        else:
            return []

        out: list[tuple[str, str, str]] = []
        taken: dict[str, int] = {}
        secondary = 0
        for db, value in _tokens(row[2 + side]):
            if db == "uniprotkb" and value.upper() not in self_ids and secondary < 5:
                secondary += 1
                out.append(("UniProt", value, "related"))
            elif db == "ensembl" and value.startswith("ENSP"):
                out.append(("Ensembl", value.split(".")[0], "exact"))
        for db, value in _tokens(row[22 + side]):
            if db == "ensembl" and value.startswith("ENSG"):
                out.append(("Ensembl", value.split(".")[0], "exact"))
            elif db in _XREF_DBS and (db != "efo" or value.startswith("Orphanet")):
                source = _XREF_DBS[db]
                if taken.get(source, 0) < _MAX_XREFS_PER_DB:
                    taken[source] = taken.get(source, 0) + 1
                    out.append((source, value, "related"))
        return out

    # ------------------------------------------------------------------
    # Converter
    # ------------------------------------------------------------------

    def _convert_interactor_to_concept(
        self, hit: dict[str, Any], confidence: float = 1.0
    ) -> UnifiedConcept | None:
        """Convert a ``findInteractor`` record to a UnifiedConcept (``PROTEIN`` for proteins)."""
        try:
            ac = hit.get("interactorAc") or ""
            accession = hit.get("interactorPreferredIdentifier") or ac
            name = hit.get("interactorName") or ""
            if not accession or not name:
                return None

            interactor_type = str(hit.get("interactorType") or "")
            concept = self._create_concept(
                accession,
                name,
                _INTERACTOR_TYPES.get(interactor_type, ConceptType.MOLECULAR_ENTITY),
            )
            description = hit.get("interactorDescription")
            if description:
                concept.synonyms = [description]
                concept.definitions = [description]
            categories = []
            if hit.get("interactorTaxId"):
                categories.append(f"taxon:{hit['interactorTaxId']}")
            if hit.get("interactorSpecies"):
                categories.append(str(hit["interactorSpecies"]))
            concept.categories = categories
            if interactor_type:
                concept.semantic_types = [interactor_type]

            if ac and ac != accession:
                concept.add_identifier(
                    KnowledgeSource.INTACT,
                    ac,
                    name,
                    f"https://www.ebi.ac.uk/intact/search?query={ac}",
                )
            if _UNIPROT_RE.match(accession):
                concept.add_identifier(
                    KnowledgeSource.UNIPROT,
                    accession,
                    name,
                    f"https://www.uniprot.org/uniprot/{accession}",
                )
            concept.confidence_score = confidence
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.INTACT] = hit
            return concept
        except Exception as e:
            logger.error(f"Error converting IntAct result: {e}")
            return None
