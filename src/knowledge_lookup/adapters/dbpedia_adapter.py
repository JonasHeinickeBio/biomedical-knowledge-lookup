"""
Adapter for DBpedia knowledge base.
"""

import logging
import re
from typing import Any
from urllib.parse import quote, unquote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ..utils.retry_utils import DEFAULT_RETRY_STRATEGIES, ErrorCategory
from ._xref_common import ExternalId, identifier_url, is_valid_external_id, normalize_external_id

logger = logging.getLogger(__name__)

# Full property IRIs as returned in SPARQL JSON results
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
DBO_ABSTRACT = "http://dbpedia.org/ontology/abstract"
DBO_ICD10 = "http://dbpedia.org/ontology/icd10"
OWL_SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"
WIKIDATA_ENTITY = "http://www.wikidata.org/entity/"
FREEBASE_NS = "http://rdf.freebase.com/ns/"
DBO_REDIRECTS = "http://dbpedia.org/ontology/wikiPageRedirects"

# Rows of owl:sameAs fetched per resource, and the number of distinct Wikidata links
# above which they are discarded: a few resources (``P53``, ``Interleukin_6``) are
# linked to ~15,000 unrelated Wikidata items by DBpedia's identity clustering.
_DBO = "http://dbpedia.org/ontology/"
DCT_SUBJECT = "http://purl.org/dc/terms/subject"
DBPEDIA_RESOURCE = "http://dbpedia.org/resource/"

# Object-valued properties exposed by get_relationships, with the edge label. ``subject``,
# ``class`` and ``routesOfAdministration`` were seen on live resources (Aspirin); the
# disease properties are the ones the DBpedia ontology declares on ``dbo:Disease``.
_RELATION_PROPERTIES: dict[str, str] = {
    DCT_SUBJECT: "has_category",
    f"{_DBO}class": "is_a",
    f"{_DBO}routesOfAdministration": "route_of_administration",
    f"{_DBO}symptom": "has_symptom",
    f"{_DBO}treatment": "treated_by",
    f"{_DBO}medication": "treated_by",
    f"{_DBO}differentialDiagnosis": "differential_diagnosis",
    f"{_DBO}medicalCause": "has_cause",
    f"{_DBO}medicalDiagnosis": "diagnosed_by",
    f"{_DBO}medicalSpecialty": "medical_specialty",
    f"{_DBO}vaccination": "vaccine",
}

_SAMEAS_ROW_LIMIT = 12
_MAX_WIKIDATA_LINKS = 5
_MAX_REDIRECT_HOPS = 2

# dbo: property -> how to expose it. The names were checked against live DBpedia
# resources (Crohn's disease, Aspirin). ICD-10 stays a category as it always was.
_EXTERNAL_IDS: dict[str, ExternalId] = {
    f"{_DBO}meshId": ExternalId(
        "MeSH", KnowledgeSource.MESH, url="https://id.nlm.nih.gov/mesh/{id}"
    ),
    # live values include stray URL fragments, so only C-numbers are accepted
    f"{_DBO}nciId": ExternalId("NCI Thesaurus", KnowledgeSource.NCIEVS, pattern=r"C\d+"),
    f"{_DBO}orpha": ExternalId(
        "Orphanet", KnowledgeSource.ORPHANET, prefix="ORPHA:", pattern=r"(?:ORPHA:)?\d+"
    ),
    f"{_DBO}omim": ExternalId("OMIM", KnowledgeSource.OMIM, url="https://omim.org/entry/{id}"),
    f"{_DBO}medlinePlus": ExternalId("MedlinePlus", KnowledgeSource.MEDLINEPLUS),
    f"{_DBO}kegg": ExternalId("KEGG", KnowledgeSource.KEGG),
    f"{_DBO}pubchem": ExternalId(
        "PubChem CID",
        KnowledgeSource.PUBCHEM,
        url="https://pubchem.ncbi.nlm.nih.gov/compound/{id}",
    ),
    f"{_DBO}chEBI": ExternalId("ChEBI", KnowledgeSource.CHEBI, prefix="CHEBI:"),
    f"{_DBO}chEMBL": ExternalId("ChEMBL", KnowledgeSource.CHEMBL, prefix="CHEMBL"),
    DBO_ICD10: ExternalId("ICD-10"),
    f"{_DBO}icd9": ExternalId("ICD-9"),
    f"{_DBO}diseasesDB": ExternalId("DiseasesDB"),
    f"{_DBO}eMedicineSubject": ExternalId("eMedicine subject"),
    f"{_DBO}eMedicineTopic": ExternalId("eMedicine topic"),
    f"{_DBO}casNumber": ExternalId("CAS"),
    f"{_DBO}atcCode": ExternalId("ATC", pattern=r"[A-Z]\d{2}[A-Z]{2}\d{2}"),
}

# Characters that may not appear inside a SPARQL <IRI> reference
_IRI_FORBIDDEN = re.compile(r'[<>"{}|^`\\\s]')


def _local_name(iri: str) -> str:
    """Last path segment of an IRI, percent-decoded: ``.../Crohn%27s_disease``."""
    return unquote(iri.rsplit("/", 1)[-1])


def _references(
    properties: list[dict[str, Any]], entity_uri: str
) -> list[tuple[str, KnowledgeSource | None, str, str | None]]:
    """External references on a resource as ``(label, source, value, url)``.

    ``source`` is ``None`` for vocabularies without a ``KnowledgeSource`` (they are
    kept as ``"<label>: <value>"`` categories). Shared by the details converter and
    ``get_mappings`` so both apply the same validation: values must look like the
    identifier, and more than ``_MAX_WIKIDATA_LINKS`` Wikidata links are an
    ambiguous cluster and dropped.
    """
    refs: list[tuple[str, KnowledgeSource | None, str, str | None]] = []
    seen: set[tuple[str, str]] = set()

    def _add(label: str, source: KnowledgeSource | None, value: str, url: str | None) -> None:
        if (label, value) not in seen:
            seen.add((label, value))
            refs.append((label, source, value, url))

    qids = {
        row["value"]["value"].removeprefix(WIKIDATA_ENTITY)
        for row in properties
        if row["property"]["value"] == OWL_SAME_AS
        and row["value"]["value"].startswith(WIKIDATA_ENTITY)
    }
    if len(qids) > _MAX_WIKIDATA_LINKS:
        logger.debug("Ignoring %d Wikidata sameAs links on %s", len(qids), entity_uri)
        qids = set()

    for row in properties:
        property_uri = row["property"]["value"]
        value = row["value"]["value"]
        if property_uri == OWL_SAME_AS:
            if value.startswith(WIKIDATA_ENTITY):
                qid = value.removeprefix(WIKIDATA_ENTITY)
                if qid in qids:
                    _add("Wikidata", KnowledgeSource.WIKIDATA, qid, value)
            elif value.startswith(FREEBASE_NS):
                # m.0h1n9 -> /m/0h1n9 (the form Wikidata and Freebase dumps use)
                mid = "/" + value.removeprefix(FREEBASE_NS).replace(".", "/")
                _add("Freebase", None, mid, None)
        elif property_uri in _EXTERNAL_IDS:
            spec = _EXTERNAL_IDS[property_uri]
            value = normalize_external_id(spec, value)
            if is_valid_external_id(spec, value):
                _add(spec.label, spec.source, value, identifier_url(spec, value))
    return refs


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


def _free_text_phrase(query: str) -> str:
    """Reduce *query* to plain words for Virtuoso's ``bif:contains``.

    ``bif:contains`` has its own expression syntax (quotes, AND/OR, wildcards)
    inside the SPARQL literal; keeping only word characters makes the phrase
    safe for both layers.
    """
    return " ".join(re.findall(r"\w+", query))


def _binding_value(binding: Any, key: str) -> str:
    """The ``value`` of *key* in a SPARQL JSON result row, or ``""``."""
    cell = binding.get(key) if isinstance(binding, dict) else None
    return cell.get("value", "") if isinstance(cell, dict) else ""


class DBpediaAdapter(KnowledgeSourceAdapter):
    """Adapter for DBpedia knowledge base.

    The public endpoint is a Virtuoso instance limited to 10,000 rows, a 120 s query
    time (``MaxQueryExecutionTime``) and 50 connections per IP. A query that runs out
    of time is *not* an error: it returns HTTP 200 with partial results and says so only
    in the ``X-SQL-State``/``X-SQL-Message`` headers (https://www.dbpedia.org/resources/sparql/).
    """

    #: Longer than the endpoint's 120 s query time, so a slow query is cut off by the
    #: server (with partial results) and not by us (with nothing).
    min_request_timeout = 125.0
    #: Politeness: far below the 50 connections per IP the endpoint allows.
    max_concurrent_requests = 5
    #: One retry after a pause instead of two immediate ones (the endpoint is often
    #: overloaded, and an instant retry only adds to the load).
    retry_strategies = {
        **DEFAULT_RETRY_STRATEGIES,
        ErrorCategory.NETWORK_ERROR: (2, 2.0, 10.0),
    }

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.sparql_endpoint = "https://dbpedia.org/sparql"
        self.base_url = "https://dbpedia.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DBPEDIA

    def _inspect_response(self, response: Any) -> None:
        """Warn when Virtuoso answered with partial results.

        A timed-out ("anytime") query still returns 200 and a valid JSON body, so the
        only sign is in the headers; ``X-SPARQL-MaxRows`` marks the 10,000-row cap.
        """
        headers = getattr(response, "headers", None) or {}
        try:
            state = headers.get("X-SQL-State")
            max_rows = headers.get("X-SPARQL-MaxRows")
        except Exception:
            return
        if state or max_rows:
            logger.warning(
                "DBpedia returned partial results (X-SQL-State=%s, X-SQL-Message=%s, "
                "X-SPARQL-MaxRows=%s); identifiers or relations may be missing",
                state,
                headers.get("X-SQL-Message"),
                max_rows,
            )

    def is_available(self) -> bool:
        return True  # DBpedia is publicly available

    async def _make_request(
        self,
        url: str,
        params: dict[Any, Any] | None = None,
        headers: dict[Any, Any] | None = None,
        json_data: dict[Any, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an async HTTP request to DBpedia, logging URL, params, and errors.
        """
        logger.debug(f"DBpedia API Request URL: {url}")
        logger.debug(f"DBpedia API Request Params: {params}")
        if headers:
            logger.debug(f"DBpedia API Request Headers: {headers}")
        try:
            return await super()._make_request(url, params, headers)
        except Exception as e:
            logger.error(f"DBpedia _make_request failed for URL {url}: {e}", exc_info=True)
            return {}

    async def run_sparql_query(self, sparql_query: str, limit: int | None = None) -> Any:
        """
        Run a generic SPARQL query against DBpedia and return the raw results.
        """
        if limit is not None and "LIMIT" not in sparql_query:
            sparql_query += f"\nLIMIT {limit}"
        params = {"query": sparql_query, "format": "json"}
        return await self._make_request(self.sparql_endpoint, params)

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """
        Search DBpedia for concepts matching the query string.

        Each resource is returned once. The ``rdf:type`` join yields one row per
        type, so ``LIMIT`` is applied to resources in a subquery and the rows are
        merged by resource, combining their types into ``categories``.
        """
        try:
            phrase = _free_text_phrase(query)
            if not phrase:
                return []
            exact_label = _sparql_string_literal(query.lower())
            contains_expr = _sparql_string_literal(f"'{phrase}'")
            sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT ?resource ?label ?abstract ?type ?exactMatch WHERE {{
              {{
                SELECT DISTINCT ?resource ?label (IF(LCASE(STR(?label)) = {exact_label}, 1, 0) AS ?exactMatch) WHERE {{
                  ?resource rdfs:label ?label .
                  ?label bif:contains {contains_expr} .
                  FILTER (lang(?label) = 'en')
                }}
                ORDER BY DESC(?exactMatch)
                LIMIT {min(int(limit), 50)}
              }}
              OPTIONAL {{ ?resource dbo:abstract ?abstract . FILTER (lang(?abstract) = 'en') }}
              OPTIONAL {{ ?resource rdf:type ?type }}
            }}
            ORDER BY DESC(?exactMatch)
            """  # noqa: E501
            data = await self.run_sparql_query(sparql_query)
            concepts: list[UnifiedConcept] = []
            by_resource: dict[str, UnifiedConcept] = {}
            if "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"]:
                    resource_uri = _binding_value(binding, "resource")
                    if resource_uri in by_resource:
                        self._merge_dbpedia_row(by_resource[resource_uri], binding)
                        continue
                    if len(concepts) >= limit:
                        continue
                    concept = self._convert_dbpedia_result_to_concept(binding)
                    if concept:
                        concepts.append(concept)
                        by_resource[resource_uri] = concept
            logger.info(f"DBpedia search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"DBpedia search failed for '{query}': {e}")
            return []

    @staticmethod
    def _merge_dbpedia_row(concept: UnifiedConcept, row: dict[str, Any]) -> None:
        """Fold another search row for the same resource into *concept*.

        Adds the row's type to ``categories`` (each once) and its abstract when
        the concept has no definition yet.
        """
        type_uri = _binding_value(row, "type")
        if type_uri and concept.categories is not None:
            category = type_uri.split("/")[-1]
            if category not in concept.categories:
                concept.categories.append(category)
        abstract = _binding_value(row, "abstract")
        if abstract and concept.definitions is not None and not concept.definitions:
            concept.definitions.append(abstract[:500] + "..." if len(abstract) > 500 else abstract)

    async def _fetch_entity_rows(self, iri: str) -> list[dict[str, Any]]:
        """The label/abstract/type/identifier rows of one resource (empty if unknown)."""
        props = ", ".join(f"<{p}>" for p in _EXTERNAL_IDS)
        # Only English (or language-less) literals, so labels in other languages do
        # not use up the LIMIT before the abstract is reached. owl:sameAs is a
        # LIMITed subquery: a resource can have thousands of links.
        sparql_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?property ?value WHERE {{
              {{
                <{iri}> ?property ?value .
                FILTER (?property IN (rdfs:label, dbo:abstract, rdf:type,
                                      dbo:wikiPageRedirects, {props}))
                FILTER (!isLiteral(?value) || lang(?value) = ""
                        || langMatches(lang(?value), "en"))
              }} UNION {{
                SELECT ?property ?value WHERE {{
                  <{iri}> owl:sameAs ?value .
                  BIND(owl:sameAs AS ?property)
                  FILTER (STRSTARTS(STR(?value), "{WIKIDATA_ENTITY}")
                          || STRSTARTS(STR(?value), "{FREEBASE_NS}"))
                }} LIMIT {_SAMEAS_ROW_LIMIT}
              }}
            }}
            """
        data = await self.run_sparql_query(sparql_query, limit=200)
        if isinstance(data, dict) and "results" in data:
            return list(data["results"].get("bindings") or [])
        return []

    @staticmethod
    def _to_resource_iri(concept_id: str) -> str:
        """A bare name or IRI as a safe ``http://dbpedia.org/resource/...`` IRI."""
        if not concept_id.startswith(DBPEDIA_RESOURCE):
            concept_id = f"{DBPEDIA_RESOURCE}{concept_id.strip().replace(' ', '_')}"
        # Percent-encode characters that would end the <IRI> and inject SPARQL
        return _IRI_FORBIDDEN.sub(lambda m: quote(m.group(0)), concept_id)

    async def _resolve_entity(self, concept_id: str) -> tuple[str, list[dict[str, Any]]] | None:
        """Fetch a resource's rows, following Wikipedia redirects; ``None`` if unknown.

        Redirect pages (e.g. ``Severe_acute_respiratory_syndrome_coronavirus_2``) carry no
        data of their own, so up to two ``dbo:wikiPageRedirects`` hops are followed.
        """
        iri = self._to_resource_iri(concept_id)
        bindings = await self._fetch_entity_rows(iri)
        for _ in range(_MAX_REDIRECT_HOPS):
            target = next(
                (
                    row["value"]["value"]
                    for row in bindings
                    if row["property"]["value"] == DBO_REDIRECTS
                ),
                None,
            )
            if not target:
                break
            iri = _IRI_FORBIDDEN.sub(lambda m: quote(m.group(0)), target)
            bindings = await self._fetch_entity_rows(iri)
        # No bindings means DBpedia has no such resource
        return (iri, bindings) if bindings else None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get details for a specific DBpedia concept/entity.

        Redirect pages are followed (see :meth:`_resolve_entity`).
        """
        try:
            resolved = await self._resolve_entity(concept_id)
            if resolved is None:
                return None
            iri, bindings = resolved
            return self._convert_dbpedia_entity_to_unified(iri, bindings)
        except Exception as e:
            logger.error(f"Failed to get DBpedia concept details for '{concept_id}': {e}")
            return None

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Cross-database references of a resource, from its identifier properties.

        ``{fromId, toId, fromSource, toSource, mappingType, confidence}`` as in the
        Ensembl/KEGG adapters; ``toSource`` is the ``KnowledgeSource`` value where there
        is one, else the vocabulary label (``ICD-10``, ``CAS``, ...). Degrades to ``[]``.
        """
        try:
            resolved = await self._resolve_entity(concept_id)
            if resolved is None:
                return []
            iri, rows = resolved
            from_id = _local_name(iri)
            return [
                {
                    "fromId": from_id,
                    "toId": value,
                    "fromSource": "DBpedia",
                    "toSource": source.value if source is not None else label,
                    "mappingType": "sameAs" if source == KnowledgeSource.WIKIDATA else "xref",
                    "confidence": 0.9,
                }
                for label, source, value, _url in _references(rows, iri)
            ]
        except Exception as e:
            logger.warning(f"DBpedia get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Typed edges from a resource to other resources.

        Wikipedia categories (``has_category``), drug class (``is_a``), route of
        administration and, for diseases, symptom/treatment/cause links, per
        ``_RELATION_PROPERTIES``. ``limit`` caps the edges per relation label.
        Returns ``{relation_label, related_id, related_name, source, property}`` dicts;
        degrades to ``[]`` on any failure.
        """
        try:
            if limit <= 0:
                return []
            iri = self._to_resource_iri(concept_id)
            props = ", ".join(f"<{p}>" for p in _RELATION_PROPERTIES)
            data = await self.run_sparql_query(
                f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT ?property ?target ?label WHERE {{
                  <{iri}> ?property ?target .
                  FILTER (?property IN ({props}))
                  FILTER (isIRI(?target) && STRSTARTS(STR(?target), "{DBPEDIA_RESOURCE}"))
                  OPTIONAL {{ ?target rdfs:label ?label . FILTER (lang(?label) = "en") }}
                }}
                """,
                limit=300,
            )
            rows = (
                (data.get("results") or {}).get("bindings") or [] if isinstance(data, dict) else []
            )
            edges: list[dict[str, Any]] = []
            per_label: dict[str, int] = {}
            seen: set[tuple[str, str]] = set()
            for row in rows:
                prop = row.get("property", {}).get("value", "")
                label = _RELATION_PROPERTIES.get(prop)
                target = _local_name(row.get("target", {}).get("value", ""))
                if label is None or not target:
                    continue
                if (label, target) in seen or per_label.get(label, 0) >= limit:
                    continue
                seen.add((label, target))
                per_label[label] = per_label.get(label, 0) + 1
                name = row.get("label", {}).get("value") or target.replace("_", " ")
                edges.append(
                    {
                        "relation_label": label,
                        "related_id": target,
                        "related_name": name,
                        "source": "DBpedia",
                        "property": prop,
                    }
                )
            return edges
        except Exception as e:
            logger.warning(f"DBpedia get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_synonyms(self, concept_id: str, limit: int = 50) -> list[str]:
        """Alternative names: the titles of Wikipedia pages that redirect to the resource
        (``Crohn disease``, ``Morbus Crohn``, common misspellings). Degrades to ``[]``."""
        try:
            if limit <= 0:
                return []
            iri = self._to_resource_iri(concept_id)
            data = await self.run_sparql_query(
                f"""
                PREFIX dbo: <http://dbpedia.org/ontology/>
                SELECT ?redirect WHERE {{ ?redirect dbo:wikiPageRedirects <{iri}> . }}
                """,
                limit=int(limit),
            )
            rows = (
                (data.get("results") or {}).get("bindings") or [] if isinstance(data, dict) else []
            )
            own = _local_name(iri).replace("_", " ").lower()
            names: list[str] = []
            for row in rows:
                name = _local_name(row.get("redirect", {}).get("value", "")).replace("_", " ")
                if name and name.lower() != own and name not in names:
                    names.append(name)
            return names
        except Exception as e:
            logger.warning(f"DBpedia get_synonyms failed for '{concept_id}': {e}")
            return []

    async def find_by_identifier(
        self, source: KnowledgeSource | str, identifier: str, limit: int = 5
    ) -> list[UnifiedConcept]:
        """Reverse lookup: the resources that carry an external identifier.

        ``source`` is a ``KnowledgeSource`` (``MESH``, ``OMIM``, ``CHEMBL``, ...), a
        vocabulary label (``"ICD-10"``, ``"CAS"``) or ``WIKIDATA`` (resolved through
        ``owl:sameAs``, with a Q-ID). The identifier may carry its CURIE prefix.
        Returns ``[]`` for an unsupported source or on any failure.
        """
        try:
            value = (identifier or "").strip()
            key = str(getattr(source, "value", source)).strip()
            if not value or limit <= 0:
                return []

            if key.upper() == KnowledgeSource.WIKIDATA.value:
                if not re.fullmatch(r"Q\d+", value):
                    return []
                condition = f"?resource owl:sameAs <{WIKIDATA_ENTITY}{value}> ."
            else:
                prop = next(
                    (
                        iri
                        for iri, spec in _EXTERNAL_IDS.items()
                        if (spec.source is not None and spec.source.value == key.upper())
                        or spec.label.lower() == key.lower()
                    ),
                    None,
                )
                if prop is None:
                    return []
                spec = _EXTERNAL_IDS[prop]
                # DBpedia stores some ids bare (chEBI 15365, chEMBL 25)
                if spec.prefix and value.upper().startswith(spec.prefix.upper()):
                    value = value[len(spec.prefix) :]
                condition = (
                    f"?resource <{prop}> ?id . FILTER (STR(?id) = {_sparql_string_literal(value)})"
                )

            data = await self.run_sparql_query(
                f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT ?resource ?label WHERE {{
                  {condition}
                  OPTIONAL {{ ?resource rdfs:label ?label . FILTER (lang(?label) = "en") }}
                }}
                """,
                limit=int(limit),
            )
            rows = (
                (data.get("results") or {}).get("bindings") or [] if isinstance(data, dict) else []
            )
            concepts: list[UnifiedConcept] = []
            for row in rows:
                resource = row.get("resource", {}).get("value", "")
                if not resource:
                    continue
                row.setdefault(
                    "label", {"value": _local_name(resource).replace("_", " "), "type": "literal"}
                )
                concept = self._convert_dbpedia_result_to_concept(row)
                if concept is not None:
                    concept.confidence_score = 0.9
                    concepts.append(concept)
            return concepts
        except Exception as e:
            logger.warning(f"DBpedia find_by_identifier failed for '{identifier}': {e}")
            return []

    def _convert_dbpedia_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        try:
            if "resource" not in result or "label" not in result:
                return None
            resource_uri = result["resource"]["value"]
            label = result["label"]["value"]
            resource_id = resource_uri.split("/")[-1]
            concept = UnifiedConcept(
                primary_id=resource_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )
            concept.add_identifier(KnowledgeSource.DBPEDIA, resource_id, label, resource_uri)
            if "abstract" in result:
                abstract = result["abstract"]["value"]
                if concept.definitions is not None:
                    concept.definitions.append(
                        abstract[:500] + "..." if len(abstract) > 500 else abstract
                    )
            if "type" in result:
                type_uri = result["type"]["value"]
                if concept.categories is not None:
                    concept.categories.append(type_uri.split("/")[-1])
            concept.confidence_score = 0.6
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.DBPEDIA] = result
            return concept
        except Exception as e:
            logger.error(f"Error converting DBpedia result: {e}")
            return None

    def _convert_dbpedia_entity_to_unified(
        self, entity_uri: str, properties: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        try:
            entity_id = entity_uri.split("/")[-1]

            # Find label first to initialize concept
            label = ""
            for prop in properties:
                if (
                    prop["property"]["value"] == RDFS_LABEL
                    and prop["value"].get("xml:lang") == "en"
                ):
                    label = prop["value"]["value"]
                    break

            if not label:
                label = entity_id.replace("_", " ")

            concept = UnifiedConcept(
                primary_id=entity_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )
            concept.add_identifier(KnowledgeSource.DBPEDIA, entity_id, label, entity_uri)

            def _add_category(category: str) -> None:
                # DBpedia repeats rdf:type rows (one per named graph)
                if concept.categories is not None and category not in concept.categories:
                    concept.categories.append(category)

            abstract = ""
            for prop in properties:
                property_uri = prop["property"]["value"]
                value = prop["value"]["value"]
                if property_uri == DBO_ABSTRACT and prop["value"].get("xml:lang") == "en":
                    abstract = value
                elif property_uri == RDF_TYPE:
                    _add_category(value.split("/")[-1])

            for ref_label, source, value, url in _references(properties, entity_uri):
                if source is None:
                    _add_category(f"{ref_label}: {value}")
                else:
                    concept.add_identifier(source, value, label, url)
                    if source == KnowledgeSource.MESH:
                        # kept as a category too, as before MESH identifiers existed
                        _add_category(f"{ref_label}: {value}")

            if abstract and concept.definitions is not None:
                concept.definitions.append(
                    abstract[:1000] + "..." if len(abstract) > 1000 else abstract
                )

            concept.confidence_score = 0.65
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.DBPEDIA] = properties
            return concept
        except Exception as e:
            logger.error(f"Error converting DBpedia entity: {e}")
            return None
