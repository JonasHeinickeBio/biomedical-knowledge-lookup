"""
Wikidata Knowledge Base Adapter

Integrates with Wikidata SPARQL endpoint for general biomedical knowledge lookup.
"""

import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter, default_user_agent
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ..utils.retry_utils import DEFAULT_RETRY_STRATEGIES, ErrorCategory
from ._xref_common import ExternalId, identifier_url, normalize_external_id

logger = logging.getLogger(__name__)

# Wikidata item IDs are "Q" followed by digits; anything else could inject SPARQL.
_QID_PATTERN = re.compile(r"Q\d+")


# Wikidata property -> how to expose it. Property IDs and labels were checked against
# the live Wikidata API (wbgetentities). Ordered by importance for biomedical linking:
# clinical vocabularies first, then genes/proteins, chemicals and taxa.
_EXTERNAL_IDS: dict[str, ExternalId] = {
    # diseases / phenotypes / clinical terminology
    "P2892": ExternalId("UMLS CUI", KnowledgeSource.UMLS),
    "P486": ExternalId("MeSH", KnowledgeSource.MESH, url="https://id.nlm.nih.gov/mesh/{id}"),
    "P1748": ExternalId("NCI Thesaurus", KnowledgeSource.NCIEVS),
    "P5806": ExternalId("SNOMED CT", KnowledgeSource.SNOMEDCT),
    "P7329": ExternalId("ICD-11 (MMS)", KnowledgeSource.ICD11),
    "P492": ExternalId("OMIM", KnowledgeSource.OMIM, url="https://omim.org/entry/{id}"),
    "P699": ExternalId(
        "Disease Ontology", KnowledgeSource.DOID, url="http://purl.obolibrary.org/obo/{obo}"
    ),
    "P3841": ExternalId("HPO", KnowledgeSource.HPO, url="http://purl.obolibrary.org/obo/{obo}"),
    "P5270": ExternalId("Mondo", KnowledgeSource.MONDO, prefix="MONDO:"),
    "P1550": ExternalId("Orphanet", KnowledgeSource.ORPHANET, prefix="ORPHA:"),
    "P604": ExternalId("MedlinePlus", KnowledgeSource.MEDLINEPLUS),
    "P665": ExternalId("KEGG", KnowledgeSource.KEGG),
    "P10283": ExternalId("OpenAlex", KnowledgeSource.OPENALEX),
    "P494": ExternalId("ICD-10"),
    "P4229": ExternalId("ICD-10-CM"),
    "P493": ExternalId("ICD-9"),
    "P1692": ExternalId("ICD-9-CM"),
    "P7807": ExternalId("ICD-11 Foundation"),
    "P672": ExternalId("MeSH tree"),
    "P4317": ExternalId("GARD"),
    "P557": ExternalId("DiseasesDB"),
    "P673": ExternalId("eMedicine"),
    "P1036": ExternalId("DDC"),
    # genes / proteins / pathways
    "P351": ExternalId(
        "Entrez Gene", KnowledgeSource.NCBIGENE, url="https://www.ncbi.nlm.nih.gov/gene/{id}"
    ),
    "P354": ExternalId("HGNC", KnowledgeSource.HGNC, prefix="HGNC:"),
    "P594": ExternalId("Ensembl", KnowledgeSource.ENSEMBL),
    "P352": ExternalId(
        "UniProt", KnowledgeSource.UNIPROT, url="https://rest.uniprot.org/uniprotkb/{id}"
    ),
    "P353": ExternalId("HGNC symbol"),
    "P686": ExternalId("Gene Ontology", KnowledgeSource.GO),
    "P3937": ExternalId("Reactome", KnowledgeSource.REACTOME),
    "P2410": ExternalId("WikiPathways", KnowledgeSource.WIKIPATHWAYS),
    # chemicals / drugs / taxa
    "P662": ExternalId(
        "PubChem CID",
        KnowledgeSource.PUBCHEM,
        url="https://pubchem.ncbi.nlm.nih.gov/compound/{id}",
    ),
    "P592": ExternalId("ChEMBL", KnowledgeSource.CHEMBL),
    "P715": ExternalId(
        "DrugBank", KnowledgeSource.DRUGBANK, url="https://go.drugbank.com/drugs/{id}"
    ),
    "P683": ExternalId("ChEBI", KnowledgeSource.CHEBI, prefix="CHEBI:"),
    "P3345": ExternalId("RxNorm", KnowledgeSource.RXNORM),
    "P685": ExternalId("NCBI Taxon", KnowledgeSource.NCBITAXONOMY),
    "P267": ExternalId("ATC"),
    "P231": ExternalId("CAS"),
    "P235": ExternalId("InChIKey"),
}

_WDT_PREFIX = "http://www.wikidata.org/prop/direct/"
_ENTITY_PREFIX = "http://www.wikidata.org/entity/"

# Item-valued Wikidata properties exposed by get_relationships, with the edge label.
# Labels follow the ones other adapters use (see TAXONOMIC_/ASSOCIATIVE_RELATION_LABELS
# in core.term_expansion): ``is_a``/``has_subclass`` are taxonomic, the rest associative.
# Property IDs and labels were checked against the live Wikidata API.
_RELATION_PROPERTIES: dict[str, str] = {
    "P279": "is_a",  # subclass of
    "P171": "is_a",  # parent taxon
    "P31": "instance_of",
    "P361": "part_of",
    "P527": "has_part",
    "P780": "has_symptom",  # symptoms and signs
    "P2176": "treated_by",  # drug or therapy used for treatment
    "P5642": "risk_factor",
    "P828": "has_cause",
    "P2293": "has_gene",  # genetic association
    "P2175": "treats",  # medical condition treated
    "P769": "interacts_with",  # significant drug interaction
    "P129": "interacts_with",  # physically interacts with
    "P3780": "active_ingredient_in",
    "P4954": "may_prevent",  # may prevent disease
    "P688": "encodes",
    "P702": "encoded_by",
}

_LANGUAGE_PATTERN = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]+)*")
_MAPPING_CONFIDENCE = 0.9
_EXACT_ID_CONFIDENCE = 0.95


def _sparql_headers() -> dict[str, str]:
    """Request headers; the User-Agent carries the contact URL the Wikimedia policy asks for."""
    return {"Accept": "application/sparql-results+json", "User-Agent": default_user_agent()}


def _wikidata_property_for(source: KnowledgeSource | str) -> str | None:
    """The external-id property for a KnowledgeSource, a ``P`` number or a label."""
    key = getattr(source, "value", source)
    if not isinstance(key, str):
        return None
    key = key.strip()
    if re.fullmatch(r"P\d+", key) and key in _EXTERNAL_IDS:
        return key
    for pid, spec in _EXTERNAL_IDS.items():
        if (spec.source is not None and spec.source.value == key.upper()) or (
            spec.label.lower() == key.lower()
        ):
            return pid
    return None


# Fallback concept type by linked vocabulary, most specific first. Only used when no
# instance-of label maps to a type (e.g. "group of stereoisomers" for ibuprofen).
_TYPE_FROM_IDENTIFIERS: tuple[tuple[KnowledgeSource, ConceptType], ...] = (
    (KnowledgeSource.NCBITAXONOMY, ConceptType.ORGANISM),
    (KnowledgeSource.UNIPROT, ConceptType.PROTEIN),
    (KnowledgeSource.NCBIGENE, ConceptType.GENE),
    (KnowledgeSource.ENSEMBL, ConceptType.GENE),
    (KnowledgeSource.HGNC, ConceptType.GENE),
    (KnowledgeSource.DRUGBANK, ConceptType.DRUG),
    (KnowledgeSource.RXNORM, ConceptType.DRUG),
    (KnowledgeSource.CHEBI, ConceptType.CHEMICAL),
    (KnowledgeSource.PUBCHEM, ConceptType.CHEMICAL),
    (KnowledgeSource.CHEMBL, ConceptType.CHEMICAL),
    (KnowledgeSource.DOID, ConceptType.DISEASE),
    (KnowledgeSource.MONDO, ConceptType.DISEASE),
    (KnowledgeSource.ORPHANET, ConceptType.DISEASE),
    (KnowledgeSource.HPO, ConceptType.PHENOTYPE),
)


def _sparql_string_literal(value: str) -> str:
    """Return *value* as a double-quoted SPARQL string literal.

    Escapes every character that could end the literal or break the query
    (backslash, double quote, line breaks), so user input cannot inject SPARQL.
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
    )
    return f'"{escaped}"'


def _binding_value(binding: Any, key: str) -> str:
    """The ``value`` of *key* in a SPARQL JSON result row, or ``""``."""
    cell = binding.get(key) if isinstance(binding, dict) else None
    return cell.get("value", "") if isinstance(cell, dict) else ""


class WikidataAdapter(KnowledgeSourceAdapter):
    """Adapter for Wikidata.

    The public Query Service enforces a 60 s query deadline, 60 s of processing time
    per client per minute, 30 failed queries per minute and 5 parallel queries per IP;
    clients over a limit get HTTP 429 with ``Retry-After`` and, if they keep going, a
    ban (https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual). The
    class attributes below follow those rules.
    """

    #: Longer than the server's 60 s deadline, so a query that finishes late is not
    #: cut off client-side and then re-run.
    min_request_timeout = 65.0
    #: Well under the 5 parallel queries per IP the service allows.
    max_concurrent_requests = 3
    #: A query that timed out (HTTP 500) or hit a flaky connection is retried once after
    #: a pause, not twice immediately: failed and slow queries count against the quota.
    retry_strategies = {
        **DEFAULT_RETRY_STRATEGIES,
        ErrorCategory.NETWORK_ERROR: (2, 2.0, 10.0),
        ErrorCategory.SERVER_ERROR: (2, 2.0, 10.0),
    }

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.sparql_endpoint = "https://query.wikidata.org/sparql"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.WIKIDATA

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Wikidata for concepts.

        Each item is returned once. The "instance of" (P31) join yields one row
        per value, so ``LIMIT`` is applied to items in a subquery and the rows are
        merged by item, combining their instance-of labels into ``categories``.
        """
        try:
            # SPARQL query to search for items by label. The search text is passed
            # as an escaped literal; ?ordinal keeps the EntitySearch ranking.
            sparql_query = f"""
            SELECT ?item ?itemLabel ?itemDescription ?instanceOfLabel ?ordinal WHERE {{
              {{
                SELECT ?item ?ordinal WHERE {{
                  SERVICE wikibase:mwapi {{
                    bd:serviceParam wikibase:api "EntitySearch" .
                    bd:serviceParam wikibase:endpoint "www.wikidata.org" .
                    bd:serviceParam mwapi:search {_sparql_string_literal(query)} .
                    bd:serviceParam mwapi:language "en" .
                    ?item wikibase:apiOutputItem mwapi:item .
                    ?ordinal wikibase:apiOrdinal true .
                  }}
                }}
                ORDER BY ?ordinal
                LIMIT {int(limit)}
              }}
              OPTIONAL {{ ?item wdt:P31 ?instanceOf . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            ORDER BY ?ordinal
            """

            params = {"query": sparql_query, "format": "json"}

            headers = _sparql_headers()

            data = await self._make_request(self.sparql_endpoint, params, headers=headers)

            concepts: list[UnifiedConcept] = []
            by_item: dict[str, UnifiedConcept] = {}
            if "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"]:
                    item_uri = _binding_value(binding, "item")
                    if item_uri in by_item:
                        self._merge_instance_of(by_item[item_uri], binding)
                        continue
                    if len(concepts) >= limit:
                        continue
                    concept = self._convert_wikidata_result_to_concept(binding)
                    if concept:
                        concepts.append(concept)
                        if item_uri:
                            by_item[item_uri] = concept

            logger.info(f"Wikidata search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Wikidata search failed for '{query}': {e}")
            return []

    def _merge_instance_of(self, concept: UnifiedConcept, binding: dict[str, Any]) -> None:
        """Fold another search row for the same item into *concept*.

        Adds the row's instance-of label to ``categories`` and, while the concept
        type is still ``UNKNOWN``, derives the type from it.
        """
        instance_of = _binding_value(binding, "instanceOfLabel")
        if not instance_of:
            return
        if concept.categories is not None and instance_of not in concept.categories:
            concept.categories.append(instance_of)
        current_type = getattr(concept.concept_type, "value", concept.concept_type)
        if current_type == ConceptType.UNKNOWN.value:
            concept.concept_type = self._determine_concept_type_from_instance_of(instance_of)

    async def _run_sparql(self, sparql_query: str) -> dict[str, Any]:
        """Send *sparql_query* to the Query Service and return the parsed JSON."""
        params = {"query": sparql_query, "format": "json"}
        data = await self._make_request(self.sparql_endpoint, params, headers=_sparql_headers())
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _bindings(data: dict[str, Any]) -> list[dict[str, Any]]:
        results = data.get("results")
        return list(results.get("bindings") or []) if isinstance(results, dict) else []

    async def _fetch_item_rows(self, concept_id: str) -> list[dict[str, Any]] | None:
        """One row per instance-of value and per external-identifier value of an item.

        A UNION, not a chain of OPTIONALs, which would multiply into a cross product.
        Returns ``None`` when the response carries no result set at all.
        """
        wdt_props = " ".join(f"wdt:{pid}" for pid in _EXTERNAL_IDS)
        sparql_query = f"""
            SELECT ?item ?itemLabel ?itemDescription ?instanceOfLabel ?prop ?value WHERE {{
              BIND(wd:{concept_id} AS ?item)
              OPTIONAL {{
                {{ ?item wdt:P31 ?instanceOf . }}
                UNION
                {{ VALUES ?prop {{ {wdt_props} }} ?item ?prop ?value . }}
              }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            """
        data = await self._run_sparql(sparql_query)
        if "results" not in data or "bindings" not in data["results"]:
            return None
        return list(data["results"]["bindings"])

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information from Wikidata."""
        try:
            # concept_id must be a Wikidata Q-ID (e.g., Q12136); it is inserted
            # into the query as wd:<id>, so reject anything else.
            if not _QID_PATTERN.fullmatch(concept_id):
                return None
            bindings = await self._fetch_item_rows(concept_id)
            if bindings is None:
                return None
            return self._convert_wikidata_details_to_concept(concept_id, bindings)
        except Exception as e:
            logger.error(f"Failed to get Wikidata concept details for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-database references of an item, from its external identifiers.

        Same ``{fromId, toId, fromSource, toSource, mappingType, confidence}`` shape as
        the Ensembl and KEGG adapters. ``toSource`` is the ``KnowledgeSource`` value
        where there is one (``MESH``, ``OMIM``, ...), otherwise the vocabulary label
        (``ICD-10-CM``, ``GARD``, ...). Degrades to ``[]`` on any failure.
        """
        try:
            if not _QID_PATTERN.fullmatch(concept_id.strip()):
                return []
            rows = await self._fetch_item_rows(concept_id.strip())
            if not rows:
                return []
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for row in rows:
                spec = _EXTERNAL_IDS.get(_binding_value(row, "prop").removeprefix(_WDT_PREFIX))
                value = _binding_value(row, "value")
                if spec is None or not value:
                    continue
                value = normalize_external_id(spec, value)
                to_source = spec.source.value if spec.source is not None else spec.label
                if (to_source, value) in seen:
                    continue
                seen.add((to_source, value))
                mappings.append(
                    {
                        "fromId": concept_id.strip(),
                        "toId": value,
                        "fromSource": "Wikidata",
                        "toSource": to_source,
                        "mappingType": "xref",
                        "confidence": _MAPPING_CONFIDENCE,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"Wikidata get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_relationships(
        self, concept_id: str, limit: int = 10, include_narrower: bool = True
    ) -> list[dict[str, Any]]:
        """Typed edges from an item to other items.

        Follows the item-valued properties in ``_RELATION_PROPERTIES`` (subclass of,
        symptoms, treatments, genetic associations, drug interactions, ...). ``limit``
        caps the edges *per relation label*, since a drug can have dozens of
        interactions that would otherwise crowd out everything else. With
        ``include_narrower`` the direct subclasses are added as ``has_subclass``.
        Returns ``{relation_label, related_id, related_name, source, property}``
        dicts; degrades to ``[]`` on any failure.
        """
        try:
            qid = concept_id.strip()
            if not _QID_PATTERN.fullmatch(qid) or limit <= 0:
                return []

            wdt_props = " ".join(f"wdt:{pid}" for pid in _RELATION_PROPERTIES)
            data = await self._run_sparql(
                f"""
                SELECT ?prop ?target ?targetLabel WHERE {{
                  VALUES ?prop {{ {wdt_props} }}
                  wd:{qid} ?prop ?target .
                  FILTER(STRSTARTS(STR(?target), "{_ENTITY_PREFIX}Q"))
                  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
                }}
                LIMIT 500
                """
            )

            edges: list[dict[str, Any]] = []
            per_label: dict[str, int] = {}
            seen: set[tuple[str, str]] = set()
            for row in self._bindings(data):
                pid = _binding_value(row, "prop").removeprefix(_WDT_PREFIX)
                label = _RELATION_PROPERTIES.get(pid)
                target = _binding_value(row, "target").removeprefix(_ENTITY_PREFIX)
                if label is None or not _QID_PATTERN.fullmatch(target):
                    continue
                if (label, target) in seen or per_label.get(label, 0) >= limit:
                    continue
                seen.add((label, target))
                per_label[label] = per_label.get(label, 0) + 1
                edges.append(self._edge(label, target, _binding_value(row, "targetLabel"), pid))

            if include_narrower:
                narrower = await self._run_sparql(
                    f"""
                    SELECT ?target ?targetLabel WHERE {{
                      ?target wdt:P279 wd:{qid} .
                      SERVICE wikibase:label {{
                        bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en".
                      }}
                    }}
                    LIMIT {int(limit)}
                    """
                )
                for row in self._bindings(narrower):
                    target = _binding_value(row, "target").removeprefix(_ENTITY_PREFIX)
                    if _QID_PATTERN.fullmatch(target) and ("has_subclass", target) not in seen:
                        seen.add(("has_subclass", target))
                        edges.append(
                            self._edge(
                                "has_subclass", target, _binding_value(row, "targetLabel"), "P279"
                            )
                        )
            return edges
        except Exception as e:
            logger.warning(f"Wikidata get_relationships failed for '{concept_id}': {e}")
            return []

    @staticmethod
    def _edge(label: str, target: str, name: str, pid: str) -> dict[str, Any]:
        return {
            "relation_label": label,
            "related_id": target,
            "related_name": name or target,
            "source": "Wikidata",
            "property": pid,
        }

    async def find_by_identifier(
        self, source: KnowledgeSource | str, identifier: str, limit: int = 5
    ) -> list[UnifiedConcept]:
        """Reverse lookup: the Wikidata items that carry an external identifier.

        ``source`` is a ``KnowledgeSource`` (``MESH``, ``OMIM``, ``UMLS``, ...), a
        vocabulary label (``"ICD-10-CM"``) or a Wikidata property (``"P486"``). The
        identifier may carry its CURIE prefix (``DOID:8778``, ``CHEBI:15365``); it is
        matched in the form Wikidata stores. Returns ``[]`` for a source Wikidata has
        no identifier property for, or on any failure.
        """
        try:
            pid = _wikidata_property_for(source)
            value = (identifier or "").strip()
            if pid is None or not value or limit <= 0:
                return []
            spec = _EXTERNAL_IDS[pid]
            # Wikidata stores some ids without the CURIE prefix (ChEBI 15365, HGNC 1100)
            if spec.prefix and value.upper().startswith(spec.prefix.upper()):
                value = value[len(spec.prefix) :]
            data = await self._run_sparql(
                f"""
                SELECT ?item ?itemLabel ?itemDescription WHERE {{
                  ?item wdt:{pid} {_sparql_string_literal(value)} .
                  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
                }}
                LIMIT {int(limit)}
                """
            )
            concepts: list[UnifiedConcept] = []
            for row in self._bindings(data):
                concept = self._convert_wikidata_result_to_concept(row)
                if concept is not None:
                    concept.confidence_score = _EXACT_ID_CONFIDENCE
                    concepts.append(concept)
            return concepts
        except Exception as e:
            logger.warning(f"Wikidata find_by_identifier failed for '{identifier}': {e}")
            return []

    async def get_synonyms(
        self, concept_id: str, languages: tuple[str, ...] = ("en",)
    ) -> list[str]:
        """Aliases (``skos:altLabel``) of an item in the given language codes."""
        try:
            qid = concept_id.strip()
            langs = [lang.strip().lower() for lang in languages]
            if not _QID_PATTERN.fullmatch(qid) or not langs:
                return []
            if not all(_LANGUAGE_PATTERN.fullmatch(lang) for lang in langs):
                return []
            lang_list = ", ".join(f'"{lang}"' for lang in langs)
            data = await self._run_sparql(
                f"""
                SELECT ?alias WHERE {{
                  wd:{qid} skos:altLabel ?alias .
                  FILTER(LANG(?alias) IN ({lang_list}))
                }}
                """
            )
            aliases: list[str] = []
            for row in self._bindings(data):
                alias = _binding_value(row, "alias").strip()
                if alias and alias not in aliases:
                    aliases.append(alias)
            return aliases
        except Exception as e:
            logger.warning(f"Wikidata get_synonyms failed for '{concept_id}': {e}")
            return []

    async def get_wikipedia_article(
        self, concept_id: str, language: str = "en"
    ) -> dict[str, str] | None:
        """The item's Wikipedia article: ``{title, url}`` (plus ``dbpedia_resource``
        for English), or ``None``. Bridges a Q-ID to the DBpedia adapter, whose
        resource names are English Wikipedia titles."""
        try:
            qid = concept_id.strip()
            lang = language.strip().lower()
            if not _QID_PATTERN.fullmatch(qid) or not _LANGUAGE_PATTERN.fullmatch(lang):
                return None
            data = await self._run_sparql(
                f"""
                SELECT ?article ?title WHERE {{
                  ?article schema:about wd:{qid} ;
                           schema:isPartOf <https://{lang}.wikipedia.org/> ;
                           schema:name ?title .
                }}
                LIMIT 1
                """
            )
            rows = self._bindings(data)
            if not rows:
                return None
            title = _binding_value(rows[0], "title")
            url = _binding_value(rows[0], "article")
            if not title or not url:
                return None
            article = {"title": title, "url": url}
            if lang == "en":
                article["dbpedia_resource"] = "http://dbpedia.org/resource/" + title.replace(
                    " ", "_"
                )
            return article
        except Exception as e:
            logger.warning(f"Wikidata get_wikipedia_article failed for '{concept_id}': {e}")
            return None

    def _convert_wikidata_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Wikidata search result to unified concept."""
        try:
            item_uri = result["item"]["value"]
            item_id = item_uri.split("/")[-1]
            label = result["itemLabel"]["value"]

            instance_of = result.get("instanceOfLabel", {}).get("value", "")
            concept_type = self._determine_concept_type_from_instance_of(instance_of)

            concept = UnifiedConcept(
                primary_id=item_id, primary_label=label, concept_type=concept_type
            )

            concept.add_identifier(KnowledgeSource.WIKIDATA, item_id, label, item_uri)

            if "itemDescription" in result:
                if concept.definitions is not None:
                    concept.definitions.append(result["itemDescription"]["value"])

            if instance_of:
                if concept.categories is not None:
                    concept.categories.append(instance_of)

            concept.confidence_score = 0.7
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.WIKIDATA] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Wikidata result: {e}")
            return None

    def _convert_wikidata_details_to_concept(
        self, item_id: str, bindings: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        """Convert Wikidata detailed concept to unified concept."""
        try:
            if not bindings:
                return None

            first = bindings[0]
            label = first["itemLabel"]["value"]

            concept = UnifiedConcept(
                primary_id=item_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            concept.add_identifier(
                KnowledgeSource.WIKIDATA,
                item_id,
                label,
                f"http://www.wikidata.org/entity/{item_id}",
            )

            description = next(
                (d for d in (_binding_value(b, "itemDescription") for b in bindings) if d), ""
            )
            if description and concept.definitions is not None:
                concept.definitions.append(description)

            def _add_category(category: str) -> None:
                if concept.categories is not None and category not in concept.categories:
                    concept.categories.append(category)

            # The first row may be an identifier row, so scan every instance-of label
            # and take the first one that maps to a known concept type.
            instance_labels = [
                lbl for b in bindings if (lbl := _binding_value(b, "instanceOfLabel"))
            ]
            for lbl in instance_labels:
                _add_category(lbl)
            for lbl in instance_labels:
                concept_type = self._determine_concept_type_from_instance_of(lbl)
                if concept_type != ConceptType.UNKNOWN:
                    concept.concept_type = concept_type
                    break

            seen: set[tuple[str, str]] = set()
            held_sources: set[KnowledgeSource] = set()
            for b in bindings:
                prop = _binding_value(b, "prop")
                value = _binding_value(b, "value")
                spec = _EXTERNAL_IDS.get(prop.removeprefix(_WDT_PREFIX))
                if spec is None or not value:
                    continue
                value = normalize_external_id(spec, value)
                if (spec.label, value) in seen:
                    continue
                seen.add((spec.label, value))
                if spec.source is not None:
                    held_sources.add(spec.source)
                    url = identifier_url(spec, value)
                    concept.add_identifier(spec.source, value, label, url)
                    # MeSH, ICD-10 and NCBI Taxon were exposed as categories before
                    # identifiers existed for them; keep that for compatibility.
                    if spec.source in (KnowledgeSource.MESH, KnowledgeSource.NCBITAXONOMY):
                        _add_category(f"{spec.label}: {value}")
                else:
                    _add_category(f"{spec.label}: {value}")

            if concept.concept_type == ConceptType.UNKNOWN:
                # No usable instance-of label: infer the type from which vocabularies
                # the item is linked to.
                for source, inferred in _TYPE_FROM_IDENTIFIERS:
                    if source in held_sources:
                        concept.concept_type = inferred
                        break

            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.WIKIDATA] = bindings

            return concept

        except Exception as e:
            logger.error(f"Error converting Wikidata details: {e}")
            return None

    def _determine_concept_type_from_instance_of(self, instance_of: str) -> ConceptType:
        """Determine concept type from Wikidata 'instance of' label."""
        io_lower = instance_of.lower()

        if any(t in io_lower for t in ["disease", "disorder", "syndrome"]):
            return ConceptType.DISEASE
        elif any(t in io_lower for t in ["symptom", "clinical sign", "medical sign"]):
            return ConceptType.SYMPTOM
        elif any(t in io_lower for t in ["drug", "pharmaceutical", "medication"]):
            return ConceptType.DRUG
        elif any(t in io_lower for t in ["gene", "genetic"]):
            return ConceptType.GENE
        elif any(t in io_lower for t in ["protein"]):
            return ConceptType.PROTEIN
        elif any(t in io_lower for t in ["chemical", "compound", "isomer", "carbohydrate"]):
            return ConceptType.CHEMICAL
        elif any(t in io_lower for t in ["taxon", "species", "organism"]):
            return ConceptType.ORGANISM

        return ConceptType.UNKNOWN
