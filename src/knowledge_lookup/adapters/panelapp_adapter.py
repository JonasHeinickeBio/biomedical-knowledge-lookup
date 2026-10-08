"""
Genomics England PanelApp adapter (expert-reviewed gene panels).

PanelApp is a public knowledgebase of gene-disease panels curated and reviewed by clinicians
and scientists. Every gene on a panel carries a traffic-light **confidence level** (green =
diagnostic-grade, amber = borderline, red = insufficient evidence), a mode of inheritance,
phenotypes and publications. Keyless REST API, verified live 2026-10:
``https://panelapp.genomicsengland.co.uk/api/v1`` (``PANELAPP_API_BASE`` selects another
deployment with the same API, e.g. PanelApp Australia ``https://panelapp-aus.org/api/v1``).

Quirks of the API that shape this adapter (all verified, none documented):

* ``panels/?search=...`` and ``?page_size=...`` are **silently ignored**: every call returns
  the first 100 panels (~75 KB). ``panels/?name=...`` filters by case-insensitive substring of
  the panel name only (one phrase, word order matters). Free-text search is therefore done
  locally over the full panel list (433 panels, 5 pages, ~375 KB), fetched once and cached for
  ten minutes; it matches name, disease group and *relevant disorders* (so ``ME/CFS`` style
  queries can hit panels whose names do not contain the words).
* ``genes/?entity_name=BRCA1`` is an **exact, case-sensitive symbol** match (the adapter
  upper-cases it) and returns one record per panel containing the gene (BRCA1: 28 records,
  ~50 KB). ``hgnc_id=`` and ``confidence_level=`` are ignored on ``genes/``; HGNC ids are
  therefore resolved to symbols through the HGNC REST service (``rest.genenames.org``).
* ``panels/{id}/genes/`` pages hold 100 genes and *does* honour ``confidence_level=3|2|1``.
  ``panels/{id}/`` returns the whole panel including every gene (25 KB for 27 genes, 470 KB
  for the 494-gene mitochondrial panel), so it is used only for single-panel details.
* ``confidence_level`` is ``"3"`` green, ``"2"`` amber, ``"1"`` red, ``"0"`` no list.

Requests are spaced 0.3 s apart. No rate limit is published.

**Terms of use** (Genomics England "PanelApp Terms of Use", December 2019, section 1.1): use of
the website *and API* is not permitted for commercial purposes (including commercial research)
or for diagnostic use / medical decision-making without a separate agreement with Genomics
England; panels are research information, not clinical advice. Third-party content (e.g. OMIM,
Johns Hopkins University) must be acknowledged. Cite PanelApp (Martin et al., Nat Genet 2019,
PMID 31676867) and the panel version. Review the current terms before any non-research use.
"""

import asyncio
import logging
import os
import re
import time
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

PANELAPP_DEFAULT_BASE = "https://panelapp.genomicsengland.co.uk/api/v1"
HGNC_FETCH_URL = "https://rest.genenames.org/fetch/hgnc_id"

_MIN_INTERVAL = 0.3  # seconds between requests; PanelApp publishes no limit
_PANEL_LIST_TTL = 600.0  # seconds the full panel list stays cached
_MAX_LIST_PAGES = 15  # safety bound for the paged panel list (433 panels = 5 pages today)
_MAX_GENE_PAGES = 3
_DEFAULT_RELATION_LIMIT = 25

_PANEL_ID_RE = re.compile(r"^(?:panelapp|panel)?\s*:?\s*(\d{1,7})$", re.IGNORECASE)
_HGNC_RE = re.compile(r"^(?:hgnc)\s*:\s*(\d{1,7})$", re.IGNORECASE)
_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._@-]{0,30}$")
_OMIM_RE = re.compile(r"OMIM:(\d+)")
_TEST_CODE_RE = re.compile(r"^[A-Z]{1,3}\d{2,4}$")  # R169, GT220, TP313 ...

#: PanelApp confidence_level -> traffic-light name (and rank for sorting, best first)
_LEVELS = {"3": "green", "2": "amber", "1": "red", "0": "none"}
_LEVEL_NUMBER = {"green": "3", "amber": "2", "red": "1"}
_LEVEL_RANK = {"green": 0, "amber": 1, "red": 2, "none": 3}


def _level_name(raw: Any) -> str:
    return _LEVELS.get(str(raw), "none")


def _normalise_level(level: str | int | None) -> str | None:
    """``"green"``/``3``/``"3"`` -> ``"3"``; ``None`` for no filter or an unknown value."""
    if level is None:
        return None
    text = str(level).strip().lower()
    if text in _LEVEL_NUMBER:
        return _LEVEL_NUMBER[text]
    return text if text in ("1", "2", "3") else None


class PanelAppAdapter(KnowledgeSourceAdapter):
    """Adapter for the PanelApp REST API (gene panels, gene evidence levels)."""

    min_request_timeout = 60.0

    def __init__(self, config):
        super().__init__(config)
        base = (os.getenv("PANELAPP_API_BASE") or PANELAPP_DEFAULT_BASE).strip().rstrip("/")
        if not base.lower().startswith("https://"):
            logger.warning("PANELAPP_API_BASE must be an https URL; using the default")
            base = PANELAPP_DEFAULT_BASE
        self.base_url = base
        # human-facing site root, e.g. https://panelapp.genomicsengland.co.uk
        self.site_url = re.sub(r"/api/v\d+$", "", base)
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0
        self._panel_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._panel_lock = asyncio.Lock()
        self._symbol_by_hgnc: dict[str, str] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.PANELAPP

    def is_available(self) -> bool:
        return True  # public API, no key

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``<base>/<path>``, spacing requests politely. Returns ``{}`` for non-objects."""
        async with self._throttle_lock:
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        data = await self._make_request(f"{self.base_url}/{path}", params)
        return data if isinstance(data, dict) else {}

    async def _panel_list(self) -> list[dict[str, Any]]:
        """All public panels (without genes), cached for ``_PANEL_LIST_TTL`` seconds."""
        async with self._panel_lock:
            cached = self._panel_cache
            if cached and time.monotonic() - cached[0] < _PANEL_LIST_TTL:
                return cached[1]
            panels: list[dict[str, Any]] = []
            seen: set[Any] = set()
            for page in range(1, _MAX_LIST_PAGES + 1):
                data = await self._get("panels/", {"page": page})
                for panel in data.get("results") or []:
                    if isinstance(panel, dict) and panel.get("id") not in seen:
                        seen.add(panel.get("id"))
                        panels.append(panel)
                if not data.get("next"):
                    break
            self._panel_cache = (time.monotonic(), panels)
            return panels

    async def _gene_records(self, symbol: str) -> list[dict[str, Any]]:
        """Every panel entry of one gene (exact upper-case HGNC symbol), paged defensively."""
        records: list[dict[str, Any]] = []
        for page in range(1, _MAX_GENE_PAGES + 1):
            params: dict[str, Any] = {"entity_name": symbol.upper()}
            if page > 1:
                params["page"] = page
            data = await self._get("genes/", params)
            records.extend(
                r
                for r in data.get("results") or []
                if isinstance(r, dict) and r.get("entity_type", "gene") == "gene"
            )
            if not data.get("next"):
                break
        return records

    async def _hgnc_symbol(self, hgnc_number: str) -> str | None:
        """Approved symbol of ``HGNC:<n>``; ``genes/`` cannot filter by HGNC id."""
        key = f"HGNC:{hgnc_number}"
        if key in self._symbol_by_hgnc:
            return self._symbol_by_hgnc[key]
        data = await self._make_request(
            f"{HGNC_FETCH_URL}/{key}", headers={"Accept": "application/json"}
        )
        docs = (data.get("response") or {}).get("docs") if isinstance(data, dict) else None
        symbol = docs[0].get("symbol") if docs else None
        if symbol:
            self._symbol_by_hgnc[key] = str(symbol)
            return str(symbol)
        return None

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_id(concept_id: str) -> tuple[str, str] | None:
        """``("panel", "158")``, ``("hgnc", "1100")`` or ``("symbol", "BRCA1")``."""
        text = (concept_id or "").strip()
        if not text:
            return None
        match = _HGNC_RE.match(text)
        if match:
            return "hgnc", match.group(1)
        match = _PANEL_ID_RE.match(text)
        if match:
            return "panel", match.group(1)
        text = re.sub(r"^(?:hgnc\s+symbol|symbol)\s*:\s*", "", text, flags=re.IGNORECASE)
        if _SYMBOL_RE.match(text):
            return "symbol", text.upper()
        return None

    async def _resolve_gene(self, concept_id: str) -> tuple[str, list[dict[str, Any]]] | None:
        """``(symbol, panel entries)`` for a gene id/symbol; ``None`` when not a gene."""
        parsed = self._parse_id(concept_id)
        if parsed is None or parsed[0] == "panel":
            return None
        kind, value = parsed
        symbol: str | None = value
        if kind == "hgnc":
            symbol = await self._hgnc_symbol(value)
        if not symbol:
            return None
        records = await self._gene_records(symbol)
        return (symbol, records) if records else None

    # ------------------------------------------------------------------
    # Search / details
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Panels matching ``query`` plus the gene with that exact symbol, if any.

        Panel matching is local and token based over name, disease group/sub-group and
        relevant disorders (every token must occur; name hits rank above disorder hits). A
        gene is looked up (one extra request) only when the query is a single symbol-like
        token, because PanelApp has no gene search beyond exact symbols.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        concepts: list[UnifiedConcept] = []
        try:
            for symbol_concept in await self._symbol_hit(text):
                concepts.append(symbol_concept)
        except Exception as e:
            logger.warning(f"PanelApp gene lookup failed for '{text}': {e}")
        try:
            panels = await self._panel_list()
            concepts.extend(self._rank_panels(panels, text))
        except Exception as e:
            logger.error(f"PanelApp search failed for '{text}': {e}")
        concepts = concepts[:limit]
        logger.info(f"PanelApp search for '{text}' returned {len(concepts)} concepts")
        return concepts

    async def _symbol_hit(self, text: str) -> list[UnifiedConcept]:
        parsed = self._parse_id(text)
        if parsed is None or parsed[0] == "panel" or " " in text:
            return []
        resolved = await self._resolve_gene(text)
        if resolved is None:
            return []
        concept = self._gene_to_concept(resolved[0], resolved[1])
        if concept is None:
            return []
        concept.confidence_score = 0.95
        return [concept]

    def _rank_panels(self, panels: list[dict[str, Any]], text: str) -> list[UnifiedConcept]:
        tokens = [t for t in re.split(r"[\s,;/]+", text.casefold()) if t]
        scored: list[tuple[float, int, UnifiedConcept]] = []
        for panel in panels:
            name = str(panel.get("name") or "").casefold()
            context = " ".join(
                [
                    name,
                    str(panel.get("disease_group") or "").casefold(),
                    str(panel.get("disease_sub_group") or "").casefold(),
                    " ".join(str(d) for d in panel.get("relevant_disorders") or []).casefold(),
                ]
            )
            if not tokens or not all(t in context for t in tokens):
                continue
            if name == text.casefold():
                score = 0.95
            elif all(t in name for t in tokens):
                score = 0.8
            else:
                score = 0.6  # matched only via disease group / relevant disorders
            concept = self._panel_to_concept(panel)
            if concept is None:
                continue
            concept.confidence_score = score
            genes = (panel.get("stats") or {}).get("number_of_genes") or 0
            scored.append((score, int(genes), concept))
        scored.sort(key=lambda s: (-s[0], -s[1], s[2].primary_label))
        return [c for _, _, c in scored]

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Panel (numeric id) or gene (``HGNC:1100`` / symbol) with evidence summary.

        Panel ``source_data[PANELAPP]``: ``version``, ``disease_group``, ``relevant_disorders``,
        ``stats`` and ``gene_confidence_counts`` (green/amber/red). Gene: ``n_panels``,
        ``confidence_counts`` over its panels, ``omim_gene``, ``ensembl_id`` and the most
        specific modes of inheritance seen.
        """
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return None
        try:
            if parsed[0] == "panel":
                data = await self._get(f"panels/{parsed[1]}/")
                concept = self._panel_to_concept(data, genes=data.get("genes"))
            else:
                resolved = await self._resolve_gene(concept_id)
                if resolved is None:
                    return None
                concept = self._gene_to_concept(resolved[0], resolved[1])
            if concept is not None:
                concept.confidence_score = 0.95
            return concept
        except Exception as e:
            logger.error(f"PanelApp get_concept_details failed for '{concept_id}': {e}")
            return None

    # ------------------------------------------------------------------
    # Mappings
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Gene -> HGNC symbol, Ensembl (GRCh38 release as served) and OMIM gene id.

        Panels have no cross-references in the API, so they return ``[]``. Ids are exactly
        those PanelApp exposes (its HGNC data are from a 2017 release; symbols may be stale).
        """
        parsed = self._parse_id(concept_id)
        if parsed is None or parsed[0] == "panel":
            return []
        try:
            resolved = await self._resolve_gene(concept_id)
        except Exception as e:
            logger.error(f"PanelApp get_mappings failed for '{concept_id}': {e}")
            return []
        if resolved is None:
            return []
        gene_data = self._gene_data(resolved[1])
        hgnc_id = str(gene_data.get("hgnc_id") or "")
        from_id = hgnc_id or resolved[0]
        targets: list[tuple[str, str, str]] = []
        if gene_data.get("hgnc_symbol") or gene_data.get("gene_symbol"):
            symbol = str(gene_data.get("hgnc_symbol") or gene_data.get("gene_symbol"))
            targets.append(("HGNC.SYMBOL", f"HGNC.SYMBOL:{symbol}", "exact"))
        ensembl = self._ensembl_id(gene_data)
        if ensembl:
            targets.append(("ENSEMBL", ensembl, "exact"))
        for omim in gene_data.get("omim_gene") or []:
            targets.append(("OMIM", f"OMIM:{omim}", "exact"))
        return [
            {
                "fromId": from_id,
                "toId": to_id,
                "fromSource": "HGNC",
                "toSource": prefix,
                "mappingType": mapping_type,
                "confidence": 0.95,
            }
            for prefix, to_id, mapping_type in targets
        ]

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_relationships(
        self,
        concept_id: str,
        limit: int = _DEFAULT_RELATION_LIMIT,
        evidence_level: str | int | None = None,
    ) -> list[dict[str, Any]]:
        """Gene -> panels / phenotypes and panel -> genes / relevant disorders.

        ``limit`` caps each relation type; ``evidence_level`` (``green``/``amber``/``red`` or
        ``3``/``2``/``1``) keeps only that confidence level. Results are ordered green first.

        * gene: ``listed_in_panel`` (``related_id`` panel id; extras ``confidence_level``,
          ``mode_of_inheritance``, ``phenotypes``, ``publications``, ``panel_version``,
          ``penetrance``) and ``associated_with_phenotype`` (distinct phenotype strings from
          green/amber entries first; ``related_id`` is ``OMIM:<n>`` when the string has one).
        * panel: ``has_gene`` (``related_id`` HGNC id, ``related_name`` symbol; same extras)
          and ``has_relevant_disorder`` (free-text disorder or NHS test-directory code such
          as ``R169``).
        """
        if limit <= 0:
            return []
        level = _normalise_level(evidence_level)
        if evidence_level is not None and level is None:
            return []
        parsed = self._parse_id(concept_id)
        if parsed is None:
            return []
        try:
            if parsed[0] == "panel":
                return await self._panel_relationships(parsed[1], limit, level)
            resolved = await self._resolve_gene(concept_id)
            if resolved is None:
                return []
            return self._gene_relationships(resolved[1], limit, level)
        except Exception as e:
            logger.error(f"PanelApp get_relationships failed for '{concept_id}': {e}")
            return []

    def _gene_relationships(
        self, records: list[dict[str, Any]], limit: int, level: str | None
    ) -> list[dict[str, Any]]:
        records = [r for r in records if level is None or str(r.get("confidence_level")) == level]
        records.sort(
            key=lambda r: (
                _LEVEL_RANK[_level_name(r.get("confidence_level"))],
                str((r.get("panel") or {}).get("name") or ""),
            )
        )
        out: list[dict[str, Any]] = []
        seen_panels: set[str] = set()
        for rec in records:
            panel = rec.get("panel") or {}
            panel_id = str(panel.get("id") or "")
            if not panel_id or panel_id in seen_panels:
                continue
            seen_panels.add(panel_id)
            out.append(
                {
                    "relation_label": "listed_in_panel",
                    "related_id": panel_id,
                    "related_name": str(panel.get("name") or ""),
                    "source": "PANELAPP",
                    **self._entry_extras(rec),
                    "panel_version": panel.get("version"),
                    "disease_group": panel.get("disease_group"),
                }
            )
            if len(out) >= limit:
                break
        phenotypes: list[dict[str, Any]] = []
        seen_pheno: set[str] = set()
        for rec in records:
            if _level_name(rec.get("confidence_level")) == "red":
                continue  # red = insufficient evidence; its phenotypes are not asserted
            for phenotype in rec.get("phenotypes") or []:
                text = str(phenotype).strip()
                if not text or text.casefold() in seen_pheno:
                    continue
                seen_pheno.add(text.casefold())
                omim = _OMIM_RE.search(text)
                phenotypes.append(
                    {
                        "relation_label": "associated_with_phenotype",
                        "related_id": f"OMIM:{omim.group(1)}" if omim else text,
                        "related_name": text,
                        "source": "PANELAPP",
                        "confidence_level": _level_name(rec.get("confidence_level")),
                        "panel": (rec.get("panel") or {}).get("name"),
                    }
                )
        # OMIM-coded phenotypes first: the free-text field also holds notes ("Adult only")
        phenotypes.sort(key=lambda p: not str(p["related_id"]).startswith("OMIM:"))
        return out + phenotypes[:limit]

    async def _panel_relationships(
        self, panel_id: str, limit: int, level: str | None
    ) -> list[dict[str, Any]]:
        levels = [level] if level else ["3", "2", "1"]  # best evidence first
        genes: list[dict[str, Any]] = []
        panel_meta: dict[str, Any] = {}
        for lv in levels:
            page = 1
            while len(genes) < limit and page <= _MAX_GENE_PAGES:
                params: dict[str, Any] = {"confidence_level": lv}
                if page > 1:
                    params["page"] = page
                data = await self._get(f"panels/{panel_id}/genes/", params)
                for rec in data.get("results") or []:
                    if isinstance(rec, dict) and rec.get("entity_type", "gene") == "gene":
                        genes.append(rec)
                        panel_meta = panel_meta or rec.get("panel") or {}
                if not data.get("next"):
                    break
                page += 1
            if len(genes) >= limit:
                break
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in genes:
            gene_data = rec.get("gene_data") or {}
            symbol = str(rec.get("entity_name") or gene_data.get("gene_symbol") or "")
            related_id = str(gene_data.get("hgnc_id") or symbol)
            if not related_id or related_id in seen:
                continue
            seen.add(related_id)
            out.append(
                {
                    "relation_label": "has_gene",
                    "related_id": related_id,
                    "related_name": symbol,
                    "source": "PANELAPP",
                    **self._entry_extras(rec),
                }
            )
            if len(out) >= limit:
                break
        if not panel_meta:
            # no genes at the requested level; fetch the panel itself for its disorders
            try:
                panel_meta = await self._get(f"panels/{panel_id}/")
            except Exception as e:
                logger.warning(f"PanelApp panel {panel_id} metadata failed: {e}")
        for disorder in (panel_meta.get("relevant_disorders") or [])[:limit]:
            text = str(disorder).strip()
            if text:
                out.append(
                    {
                        "relation_label": "has_relevant_disorder",
                        "related_id": text,
                        "related_name": text,
                        "source": "PANELAPP",
                        "is_test_directory_code": bool(_TEST_CODE_RE.match(text)),
                    }
                )
        return out

    @staticmethod
    def _entry_extras(rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "confidence_level": _level_name(rec.get("confidence_level")),
            "mode_of_inheritance": rec.get("mode_of_inheritance") or None,
            "mode_of_pathogenicity": rec.get("mode_of_pathogenicity") or None,
            "penetrance": rec.get("penetrance") or None,
            "phenotypes": list(rec.get("phenotypes") or []),
            "publications": list(rec.get("publications") or []),
        }

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _gene_data(records: list[dict[str, Any]]) -> dict[str, Any]:
        for rec in records:
            if isinstance(rec.get("gene_data"), dict):
                return rec["gene_data"]
        return {}

    @staticmethod
    def _ensembl_id(gene_data: dict[str, Any]) -> str | None:
        """Ensembl gene id, preferring GRCh38 (newest release listed)."""
        ensembl = gene_data.get("ensembl_genes") or {}
        for build in ("GRch38", "GRch37"):
            releases = ensembl.get(build) or {}
            for release in sorted(
                releases, key=lambda r: int(r) if str(r).isdigit() else 0, reverse=True
            ):
                ens_id = (releases[release] or {}).get("ensembl_id")
                if ens_id:
                    return str(ens_id)
        return None

    def _gene_to_concept(
        self, symbol: str, records: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        if not records:
            return None
        gene_data = self._gene_data(records)
        hgnc_id = str(gene_data.get("hgnc_id") or "")
        primary_id = hgnc_id or symbol
        label = str(gene_data.get("gene_symbol") or gene_data.get("hgnc_symbol") or symbol)
        concept = self._create_concept(primary_id, label, ConceptType.GENE)
        concept.add_identifier(
            self.get_source(), primary_id, label, f"{self.site_url}/panels/entities/{label}"
        )
        if gene_data.get("gene_name") and concept.definitions is not None:
            concept.definitions.append(str(gene_data["gene_name"]))
        if concept.synonyms is not None:
            concept.synonyms.extend(str(a) for a in gene_data.get("alias") or [])
        counts = {"green": 0, "amber": 0, "red": 0}
        modes: set[str] = set()
        for rec in records:
            name = _level_name(rec.get("confidence_level"))
            if name in counts:
                counts[name] += 1
            if name == "green" and rec.get("mode_of_inheritance"):
                modes.add(str(rec["mode_of_inheritance"]))
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = {
                "hgnc_id": hgnc_id or None,
                "gene_name": gene_data.get("gene_name"),
                "n_panels": len({(r.get("panel") or {}).get("id") for r in records}),
                "confidence_counts": counts,
                "green_modes_of_inheritance": sorted(modes),
                "omim_gene": list(gene_data.get("omim_gene") or []),
                "ensembl_id": self._ensembl_id(gene_data),
                "biotype": gene_data.get("biotype"),
                "api_base": self.base_url,
            }
        return concept

    def _panel_to_concept(
        self, panel: dict[str, Any], genes: list[dict[str, Any]] | None = None
    ) -> UnifiedConcept | None:
        panel_id, name = panel.get("id"), panel.get("name")
        if panel_id is None or not name:
            return None
        pid = str(panel_id)
        concept = self._create_concept(pid, str(name), ConceptType.DISEASE)
        concept.add_identifier(self.get_source(), pid, str(name), f"{self.site_url}/panels/{pid}/")
        disorders = [str(d) for d in panel.get("relevant_disorders") or []]
        if concept.synonyms is not None:
            concept.synonyms.extend(d for d in disorders if not _TEST_CODE_RE.match(d))
        if concept.definitions is not None:
            group = " / ".join(
                str(x) for x in (panel.get("disease_group"), panel.get("disease_sub_group")) if x
            )
            concept.definitions.append(
                f"PanelApp gene panel{f' ({group})' if group else ''}, "
                f"version {panel.get('version')}"
            )
        if concept.categories is not None and panel.get("disease_group"):
            concept.categories.append(str(panel["disease_group"]))
        data: dict[str, Any] = {
            "version": panel.get("version"),
            "version_created": panel.get("version_created"),
            "disease_group": panel.get("disease_group"),
            "disease_sub_group": panel.get("disease_sub_group"),
            "relevant_disorders": disorders,
            "stats": panel.get("stats"),
            "types": [t.get("slug") for t in panel.get("types") or [] if isinstance(t, dict)],
            "status": panel.get("status"),
            "api_base": self.base_url,
        }
        if genes is not None:
            counts = {"green": 0, "amber": 0, "red": 0}
            for rec in genes:
                lv = _level_name(rec.get("confidence_level"))
                if lv in counts:
                    counts[lv] += 1
            data["gene_confidence_counts"] = counts
        if isinstance(concept.source_data, dict):
            concept.source_data[self.get_source()] = data
        return concept
