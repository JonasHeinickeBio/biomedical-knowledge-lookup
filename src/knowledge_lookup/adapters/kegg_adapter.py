"""
KEGG Knowledge Source Adapter

Integrates with the KEGG REST API (https://rest.kegg.jp) for biological
pathways, genes, compounds, enzymes, reactions, orthology, networks,
glycans, diseases and drugs.

Supported REST operations: ``find``, ``get``, ``link`` and ``conv``.
"""

import logging
import re
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# KEGG flat-text fields are padded to this width before their value.
_FIELD_WIDTH = 12

# The ``find`` endpoint answers 400 (404 for "/") to these characters, so a label
# such as "TP53 protein, human" would silently find nothing in every database.
_UNSUPPORTED_QUERY_CHARS = re.compile(r"[,/:&#%*=<@!|\\]")


def sanitize_query(query: str) -> str:
    """Replace characters the KEGG ``find`` endpoint rejects with spaces."""
    return " ".join(_UNSUPPORTED_QUERY_CHARS.sub(" ", query).split())


# Searchable ``find`` databases, mapped to how results should be interpreted.
#   concept_type   -> ConceptType assigned to search hits
#   strip_prefixes -> id prefixes to remove from ``find`` results (e.g. ``ds:``)
#   organism       -> database requires an organism code in its URL path
_KEGG_SEARCH_DATABASES: dict[str, dict[str, Any]] = {
    "pathway": {"concept_type": ConceptType.PATHWAY, "strip_prefixes": ["path:"]},
    "gene": {
        "concept_type": ConceptType.GENE,
        "strip_prefixes": [],
        "organism": True,
    },
    "compound": {"concept_type": ConceptType.CHEMICAL, "strip_prefixes": []},
    "glycan": {"concept_type": ConceptType.CHEMICAL, "strip_prefixes": []},
    "enzyme": {"concept_type": ConceptType.MOLECULAR_FUNCTION, "strip_prefixes": []},
    "reaction": {"concept_type": ConceptType.BIOLOGICAL_PROCESS, "strip_prefixes": []},
    "orthology": {"concept_type": ConceptType.GENE, "strip_prefixes": []},
    "network": {"concept_type": ConceptType.PATHWAY, "strip_prefixes": []},
    "disease": {"concept_type": ConceptType.DISEASE, "strip_prefixes": ["ds:"]},
    "drug": {"concept_type": ConceptType.DRUG, "strip_prefixes": ["dr:"]},
}

# Default databases searched by ``search_concepts``. Kept intentionally narrow
# (disease + drug) so that general orchestrated lookups stay precise and the
# call sequence stays backward compatible.
DEFAULT_SEARCH_DATABASES: tuple[str, ...] = ("disease", "drug")

# Identifier patterns used to infer a KEGG entry's database from its ID.
_GENE_RE = re.compile(r"^[a-z][a-z0-9]{1,5}:\d+$")
_PATHWAY_RE = re.compile(r"^(?:path:)?(?:[a-z][a-z0-9]{1,5}|map)\d{5}$")
_EC_RE = re.compile(r"^\d+(\.\d+){0,3}\.?[a-z-]*$")


class KEGGAdapter(KnowledgeSourceAdapter):
    """Adapter for the KEGG REST API."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.kegg.jp"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.KEGG

    def is_available(self) -> bool:
        return True

    @staticmethod
    def supported_databases() -> list[str]:
        """Return the list of KEGG databases supported by ``search_concepts``."""
        return list(_KEGG_SEARCH_DATABASES)

    # ------------------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------------------

    async def search_concepts(
        self,
        query: str,
        limit: int = 20,
        *,
        databases: list[str] | None = None,
        organism: str = "hsa",
    ) -> list[UnifiedConcept]:
        """Search KEGG using the ``find`` operation.

        Parameters
        ----------
        query:
            Free-text search term.
        limit:
            Maximum number of concepts to return across all databases.
        databases:
            KEGG databases to search. Defaults to ``("disease", "drug")`` to
            preserve historical behaviour. Supported values are returned by
            :meth:`supported_databases` (e.g. ``pathway``, ``gene``,
            ``compound``, ``enzyme``, ``reaction``, ``orthology``).
        organism:
            Organism code used when searching organism-scoped databases such
            as ``gene`` (default ``hsa``).
        """
        try:
            selected = list(databases) if databases else list(DEFAULT_SEARCH_DATABASES)
            concepts: list[UnifiedConcept] = []
            cleaned = sanitize_query(query)
            if not cleaned:
                return []
            encoded_query = quote(cleaned)

            for db in selected:
                if len(concepts) >= limit:
                    break
                config = _KEGG_SEARCH_DATABASES.get(db)
                if config is None:
                    logger.warning(f"KEGG: unsupported search database '{db}'")
                    continue

                if config.get("organism"):
                    segment = f"{organism}/{encoded_query}"
                else:
                    segment = f"{db}/{encoded_query}"

                data = await self._make_request_text(f"{self.base_url}/find/{segment}")
                if not data:
                    continue

                remaining = limit - len(concepts)
                concepts.extend(self._parse_find_lines(db, data, remaining))

            logger.info(f"KEGG search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"KEGG search failed for '{query}': {e}")
            return []

    def _parse_find_lines(self, db: str, text: str, limit: int) -> list[UnifiedConcept]:
        """Parse tab-separated ``find`` output into concepts."""
        config = _KEGG_SEARCH_DATABASES[db]
        concept_type = config["concept_type"]
        strip_prefixes = config["strip_prefixes"]

        concepts: list[UnifiedConcept] = []
        for line in text.strip().split("\n"):
            if len(concepts) >= limit:
                break
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            entry_id = parts[0].strip()
            label = parts[1].split(";")[0].strip()
            for prefix in strip_prefixes:
                if entry_id.startswith(prefix):
                    entry_id = entry_id[len(prefix) :]
                    break
            if not entry_id:
                continue

            concept = UnifiedConcept(
                primary_id=entry_id,
                primary_label=label or entry_id,
                concept_type=concept_type,
            )
            concept.add_identifier(
                KnowledgeSource.KEGG,
                entry_id,
                label or entry_id,
                self._entry_url(entry_id),
            )
            concept.confidence_score = 0.8
            concepts.append(concept)

        return concepts

    # ------------------------------------------------------------------
    # DETAILS
    # ------------------------------------------------------------------

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information from KEGG via the ``get`` operation.

        Accepts disease (``H00001``), drug (``D00001``), gene (``hsa:3531``),
        pathway (``hsa00010`` / ``map00010`` / ``path:hsa00010``), compound
        (``C01405``), orthology (``K00844``), reaction (``R00002``), glycan
        (``G00001``), enzyme (``2.7.1.1``) and network (``nt06017``) IDs.
        """
        try:
            entry = self._build_get_entry(concept_id)
            if entry is None:
                logger.warning(f"KEGG: cannot resolve entry id '{concept_id}'")
                return None

            data = await self._make_request_text(f"{self.base_url}/get/{entry}")
            if not data:
                return None

            return self._parse_kegg_text(concept_id, data)

        except Exception as e:
            logger.error(f"Failed to get KEGG concept details for '{concept_id}': {e}")
            return None

    def _build_get_entry(self, concept_id: str) -> str | None:
        """Normalise a user supplied id into a KEGG ``get`` entry token."""
        cid = concept_id.strip()

        # Already organism- or database-scoped (e.g. hsa:3531, path:hsa00010).
        if ":" in cid:
            db, _, rest = cid.partition(":")
            if db == "path":
                return rest
            if db in {"hs", "hsa", "mmu", "sce", "eco", "ath", "dr", "ds", "cpd", "path"}:
                return cid
            if _GENE_RE.match(cid):
                return cid
            # Unknown namespace -> not resolvable by KEGG.
            return None

        if re.match(r"^H\d+$", cid):
            return f"ds:{cid}"
        if re.match(r"^D\d+$", cid):
            return f"dr:{cid}"
        if re.match(r"^[CKRG]\d+$", cid):
            return cid
        if re.match(r"^(?:[a-z][a-z0-9]{1,5}|map)\d{5}$", cid):
            return cid
        if re.match(r"^nt\d+$", cid):
            return cid
        if _EC_RE.match(cid) and "." in cid:
            return cid
        return None

    @staticmethod
    def _entry_url(kegg_id: str) -> str:
        return f"https://www.kegg.jp/entry/{kegg_id}"

    def _parse_kegg_text(self, kegg_id: str, text: str) -> UnifiedConcept | None:
        """Parse KEGG flat-text (DBGET) format into a :class:`UnifiedConcept`."""
        try:
            if not text:
                return None

            fields = self._parse_fields(text)
            concept_type = self._detect_concept_type(kegg_id, fields)

            label = ""
            name_values = fields.get("NAME") or fields.get("GENE")
            if name_values:
                label = name_values[0].split(";")[0].strip()
            label = label or kegg_id

            concept = UnifiedConcept(
                primary_id=kegg_id,
                primary_label=label,
                concept_type=concept_type,
            )
            concept.add_identifier(
                KnowledgeSource.KEGG,
                kegg_id,
                label,
                self._entry_url(kegg_id),
            )

            if concept.definitions is not None:
                for description in fields.get("DESCRIPTION", []):
                    description = description.strip()
                    if description and description not in concept.definitions:
                        concept.definitions.append(description)

            if concept.synonyms is not None:
                synonyms = fields.get("NAME", [])
                for synonym in synonyms[1:]:
                    for token in synonym.split(";"):
                        token = token.strip()
                        if token and token not in concept.synonyms:
                            concept.synonyms.append(token)

            extras: dict[str, Any] = {"raw_text": text}
            if fields.get("CLASS"):
                extras["class"] = fields["CLASS"][0].strip()
            if fields.get("ORGANISM"):
                extras["organism"] = fields["ORGANISM"][0].strip()
            if fields.get("SYMBOL"):
                extras["symbol"] = fields["SYMBOL"][0].strip()
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.KEGG] = extras

            concept.confidence_score = 1.0
            return concept

        except Exception as e:
            logger.error(f"Error parsing KEGG text: {e}")
            return None

    def _parse_fields(self, text: str) -> dict[str, list[str]]:
        """Parse DBGET flat text into ``{FIELD: [values]}`` handling wrapping."""
        fields: dict[str, list[str]] = {}
        current: str | None = None

        for raw in text.splitlines():
            if not raw.strip():
                continue
            # Continuation lines are indented by _FIELD_WIDTH spaces.
            if raw[:_FIELD_WIDTH].strip() == "" and raw[_FIELD_WIDTH:].strip():
                if current is not None:
                    fields.setdefault(current, []).append(raw[_FIELD_WIDTH:].strip())
                continue

            parts = raw.split(None, 1)
            key = parts[0]
            value = parts[1].strip() if len(parts) > 1 else ""
            if key == "ENTRY":
                tokens = value.split()
                fields.setdefault("ENTRY", [])
                if tokens:
                    fields["ENTRY"] = [tokens[0]]
                if len(tokens) > 1:
                    fields["ENTRY_TYPE"] = [tokens[-1]]
                current = None
                continue

            fields.setdefault(key, [])
            if value:
                fields[key].append(value)
            current = key

        return fields

    def _detect_concept_type(self, kegg_id: str, fields: dict[str, list[str]]) -> ConceptType:
        """Infer the concept type from the id and/or the ENTRY field token."""
        entry_type = (fields.get("ENTRY_TYPE") or [""])[0].lower()
        type_map = {
            "pathway": ConceptType.PATHWAY,
            "gene": ConceptType.GENE,
            "disease": ConceptType.DISEASE,
            "drug": ConceptType.DRUG,
            "compound": ConceptType.CHEMICAL,
            "enzyme": ConceptType.MOLECULAR_FUNCTION,
            "reaction": ConceptType.BIOLOGICAL_PROCESS,
            "orthology": ConceptType.GENE,
            "glycan": ConceptType.CHEMICAL,
            "network": ConceptType.PATHWAY,
        }
        if entry_type in type_map:
            return type_map[entry_type]

        if re.match(r"^H\d+$", kegg_id):
            return ConceptType.DISEASE
        if re.match(r"^D\d+$", kegg_id):
            return ConceptType.DRUG
        if re.match(r"^[CKRG]\d+$", kegg_id):
            return ConceptType.CHEMICAL if kegg_id[0] in "CG" else ConceptType.GENE
        if _GENE_RE.match(kegg_id):
            return ConceptType.GENE
        if _PATHWAY_RE.match(kegg_id) or re.match(r"^nt\d+$", kegg_id):
            return ConceptType.PATHWAY
        if _EC_RE.match(kegg_id) and "." in kegg_id:
            return ConceptType.MOLECULAR_FUNCTION
        return ConceptType.UNKNOWN

    # ------------------------------------------------------------------
    # MAPPINGS (DBLINKS)
    # ------------------------------------------------------------------

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return cross-references for an entry parsed from its DBLINKS block."""
        entry = self._build_get_entry(concept_id)
        if entry is None:
            return []
        try:
            text = await self._make_request_text(f"{self.base_url}/get/{entry}")
            if not text:
                return []

            mappings: list[dict[str, Any]] = []
            for db_name, ids in self._parse_dblinks(text):
                is_kegg = db_name.upper().startswith("KEGG")
                for target_id in ids:
                    mappings.append(
                        {
                            "fromId": concept_id,
                            "toId": target_id,
                            "fromSource": "KEGG",
                            "toSource": db_name,
                            "mappingType": "exact" if is_kegg else "related",
                            "confidence": 1.0 if is_kegg else 0.9,
                        }
                    )

            logger.info(f"KEGG found {len(mappings)} mappings for '{concept_id}'")
            return mappings

        except Exception as e:
            logger.error(f"KEGG mapping lookup failed for '{concept_id}': {e}")
            return []

    def _parse_dblinks(self, text: str) -> list[tuple[str, list[str]]]:
        """Parse the ``DBLINKS`` block into ``[(database, [ids])]``."""
        result: list[tuple[str, list[str]]] = []
        in_block = False

        for raw in text.splitlines():
            if raw.startswith("DBLINKS"):
                in_block = True
                chunk = raw[_FIELD_WIDTH:].strip()
            elif in_block and raw[:_FIELD_WIDTH].strip() == "" and raw[_FIELD_WIDTH:].strip():
                chunk = raw[_FIELD_WIDTH:].strip()
            elif in_block:
                break
            else:
                continue

            if not chunk or ":" not in chunk:
                continue
            db_name, _, id_part = chunk.partition(":")
            ids = [token for token in id_part.split() if token]
            if db_name.strip() and ids:
                result.append((db_name.strip(), ids))

        return result

    # ------------------------------------------------------------------
    # RELATIONSHIPS (link)
    # ------------------------------------------------------------------

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Return linked entries using the KEGG ``link`` operation.

        Genes are linked to their pathways; pathways are linked to their genes.
        """
        entry = self._build_get_entry(concept_id)
        if entry is None:
            return []

        concept_type = self._detect_concept_type(
            concept_id, self._fields_for_detection(concept_id)
        )

        try:
            if concept_type == ConceptType.GENE:
                url = f"{self.base_url}/link/pathway/{entry}"
                relation = "in_pathway"
                target_source = "KEGG_PATHWAY"
            elif concept_type == ConceptType.PATHWAY:
                organism = entry[: entry.find(":")] if ":" in entry else entry[:3]
                url = f"{self.base_url}/link/{organism or 'hsa'}/{entry}"
                relation = "has_gene"
                target_source = "KEGG_GENE"
            else:
                return []

            data = await self._make_request_text(url)
            if not data:
                return []

            relationships: list[dict[str, Any]] = []
            for line in data.strip().split("\n"):
                # KEGG ``link`` output is ``<source>\t<target>``; the linked
                # entry is always the second (target) column.
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                related_id = parts[1].strip()
                if not related_id:
                    continue
                relationships.append(
                    {
                        "relation_label": relation,
                        "related_id": related_id,
                        "related_name": None,
                        "source": target_source,
                    }
                )

            logger.info(f"KEGG found {len(relationships)} relationships for '{concept_id}'")
            return relationships

        except Exception as e:
            logger.error(f"KEGG relationship lookup failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _fields_for_detection(concept_id: str) -> dict[str, list[str]]:
        """Minimal field map so type detection can run on an id alone."""
        return {}
