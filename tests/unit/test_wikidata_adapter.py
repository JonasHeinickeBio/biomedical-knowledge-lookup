"""
Unit tests for WikidataAdapter.
"""

import re
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.wikidata_adapter import (
    _EXTERNAL_IDS,
    WikidataAdapter,
    _sparql_string_literal,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

_WDT = "http://www.wikidata.org/prop/direct/"


def _id_row(prop, value, instance_of=None):
    """One live-shaped details row: an external-id value or an instance-of label."""
    row = {
        "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q18216"},
        "itemLabel": {"xml:lang": "en", "type": "literal", "value": "aspirin"},
        "itemDescription": {"xml:lang": "en", "type": "literal", "value": "medication"},
    }
    if instance_of:
        row["instanceOfLabel"] = {"xml:lang": "en", "type": "literal", "value": instance_of}
    if value is not None:
        row["prop"] = {"type": "uri", "value": f"{_WDT}{prop}"}
        row["value"] = {"type": "literal", "value": value}
    return row


class TestWikidataAdapter:
    """Tests for WikidataAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create WikidataAdapter instance."""
        return WikidataAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test WikidataAdapter initialization."""
        adapter = WikidataAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.WIKIDATA
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.WIKIDATA

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.WIKIDATA: 5.0})
        adapter = WikidataAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts with actual results (lines 59-62)."""
        sparql_data = {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q12136"},
                        "itemLabel": {"value": "Diabetes mellitus"},
                        "itemDescription": {"value": "metabolic disease"},
                        "instanceOfLabel": {"value": "disease"},
                    }
                ]
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            results = await adapter.search_concepts("diabetes", limit=10)
            assert len(results) == 1
            assert results[0].primary_id == "Q12136"

    @pytest.mark.asyncio
    async def test_search_concepts_empty_bindings(self, adapter):
        """Test search when bindings is empty."""
        sparql_data = {"results": {"bindings": []}}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            results = await adapter.search_concepts("nonexistent")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_conversion_returns_none(self, adapter):
        """Test search when conversion returns None."""
        sparql_data = {"results": {"bindings": [{}]}}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            with patch.object(adapter, "_convert_wikidata_result_to_concept", return_value=None):
                results = await adapter.search_concepts("test")
                assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("SPARQL error")
            results = await adapter.search_concepts("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter):
        """Test successful get_concept_details (lines 79-110)."""
        sparql_data = {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q12136"},
                        "itemLabel": {"value": "Diabetes mellitus"},
                        "itemDescription": {"value": "metabolic disease"},
                        "instanceOfLabel": {"value": "disease"},
                        "umlsCui": {"value": "C0011849"},
                        "meshId": {"value": "D003924"},
                        "icd10": {"value": "E10"},
                        "ncbiTaxonId": {"value": "9606"},
                    }
                ]
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            result = await adapter.get_concept_details("Q12136")
            assert result is not None
            assert result.primary_id == "Q12136"

    @pytest.mark.asyncio
    async def test_get_concept_details_non_q_id(self, adapter):
        """Test get_concept_details with non-Q ID (returns None, lines 75-77)."""
        result = await adapter.get_concept_details("P12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_bindings(self, adapter):
        """Test get_concept_details with empty bindings."""
        sparql_data = {"results": {"bindings": []}}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            result = await adapter.get_concept_details("Q12136")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("SPARQL error")
            result = await adapter.get_concept_details("Q12136")
            assert result is None

    def test_convert_wikidata_result_full(self, adapter):
        """Test _convert_wikidata_result_to_concept with all fields (lines 114-141)."""
        result = {
            "item": {"value": "http://www.wikidata.org/entity/Q12136"},
            "itemLabel": {"value": "Diabetes mellitus"},
            "itemDescription": {"value": "metabolic disease"},
            "instanceOfLabel": {"value": "disease"},
        }
        concept = adapter._convert_wikidata_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "Q12136"
        assert concept.primary_label == "Diabetes mellitus"
        assert "metabolic disease" in concept.definitions
        assert "disease" in concept.categories

    def test_convert_wikidata_result_no_description(self, adapter):
        """Test _convert_wikidata_result_to_concept without description."""
        result = {
            "item": {"value": "http://www.wikidata.org/entity/Q12136"},
            "itemLabel": {"value": "Diabetes mellitus"},
        }
        concept = adapter._convert_wikidata_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0

    def test_convert_wikidata_result_no_instance_of(self, adapter):
        """Test _convert_wikidata_result_to_concept without instanceOf."""
        result = {
            "item": {"value": "http://www.wikidata.org/entity/Q12136"},
            "itemLabel": {"value": "Diabetes mellitus"},
            "instanceOfLabel": {"value": ""},
        }
        concept = adapter._convert_wikidata_result_to_concept(result)
        assert concept is not None
        assert len(concept.categories) == 0

    def test_convert_wikidata_result_error(self, adapter):
        """Test _convert_wikidata_result error handling."""
        concept = adapter._convert_wikidata_result_to_concept(None)
        assert concept is None

    def test_convert_wikidata_details_full(self, adapter):
        """Details rows carry one instance-of or one external-id value each."""
        bindings = [
            {
                "itemLabel": {"value": "Diabetes mellitus"},
                "itemDescription": {"value": "metabolic disease"},
                "instanceOfLabel": {"value": "disease"},
            },
            _id_row("P2892", "C0011849"),
            _id_row("P486", "D003924"),
            _id_row("P494", "E10"),
            _id_row("P685", "9606"),
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q12136", bindings)
        assert concept is not None
        assert concept.primary_id == "Q12136"
        assert concept.primary_label == "Diabetes mellitus"
        assert "metabolic disease" in concept.definitions
        assert "ICD-10: E10" in concept.categories
        assert "NCBI Taxon: 9606" in concept.categories
        assert "MeSH: D003924" in concept.categories

    def test_convert_wikidata_details_empty_bindings(self, adapter):
        """Test _convert_wikidata_details_to_concept with empty bindings."""
        concept = adapter._convert_wikidata_details_to_concept("Q12136", [])
        assert concept is None

    def test_convert_wikidata_details_no_optional_fields(self, adapter):
        """Test _convert_wikidata_details without optional fields."""
        bindings = [{"itemLabel": {"value": "Diabetes mellitus"}}]
        concept = adapter._convert_wikidata_details_to_concept("Q12136", bindings)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_wikidata_details_duplicate_instance_of(self, adapter):
        """Test _convert_wikidata_details when instanceOf already in categories."""
        bindings = [
            {"itemLabel": {"value": "Test"}, "instanceOfLabel": {"value": "disease"}},
            {"itemLabel": {"value": "Test"}, "instanceOfLabel": {"value": "disease"}},
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q12136", bindings)
        assert concept is not None
        assert concept.categories.count("disease") == 1

    def test_convert_wikidata_details_error(self, adapter):
        """Test _convert_wikidata_details error handling."""
        concept = adapter._convert_wikidata_details_to_concept("Q12136", None)
        assert concept is None

    def test_determine_concept_type_disease(self, adapter):
        """Test _determine_concept_type_from_instance_of for disease (lines 199-214)."""
        assert adapter._determine_concept_type_from_instance_of("disease") == ConceptType.DISEASE
        assert adapter._determine_concept_type_from_instance_of("disorder") == ConceptType.DISEASE
        assert adapter._determine_concept_type_from_instance_of("syndrome") == ConceptType.DISEASE

    def test_determine_concept_type_drug(self, adapter):
        """Test _determine_concept_type_from_instance_of for drug."""
        assert adapter._determine_concept_type_from_instance_of("drug") == ConceptType.DRUG
        assert (
            adapter._determine_concept_type_from_instance_of("pharmaceutical") == ConceptType.DRUG
        )
        assert adapter._determine_concept_type_from_instance_of("medication") == ConceptType.DRUG

    def test_determine_concept_type_gene(self, adapter):
        """Test _determine_concept_type_from_instance_of for gene."""
        assert adapter._determine_concept_type_from_instance_of("gene") == ConceptType.GENE
        assert (
            adapter._determine_concept_type_from_instance_of("genetic element") == ConceptType.GENE
        )

    def test_determine_concept_type_protein(self, adapter):
        """Test _determine_concept_type_from_instance_of for protein."""
        assert adapter._determine_concept_type_from_instance_of("protein") == ConceptType.PROTEIN

    def test_determine_concept_type_chemical(self, adapter):
        """Test _determine_concept_type_from_instance_of for chemical."""
        assert (
            adapter._determine_concept_type_from_instance_of("chemical compound")
            == ConceptType.CHEMICAL
        )

    def test_determine_concept_type_organism(self, adapter):
        """Test _determine_concept_type_from_instance_of for organism."""
        assert adapter._determine_concept_type_from_instance_of("taxon") == ConceptType.ORGANISM
        assert adapter._determine_concept_type_from_instance_of("species") == ConceptType.ORGANISM
        assert adapter._determine_concept_type_from_instance_of("organism") == ConceptType.ORGANISM

    def test_determine_concept_type_unknown(self, adapter):
        """Test _determine_concept_type_from_instance_of for unknown type."""
        assert (
            adapter._determine_concept_type_from_instance_of("something else")
            == ConceptType.UNKNOWN
        )

    def test_determine_concept_type_empty_string(self, adapter):
        """Test _determine_concept_type_from_instance_of with empty string."""
        assert adapter._determine_concept_type_from_instance_of("") == ConceptType.UNKNOWN

    # --- regression tests: SPARQL injection, ranking, MeSH ---

    @staticmethod
    def _strip_literals(sparql: str) -> str:
        """Remove SPARQL string literals (honouring escapes) to compare query structure."""
        return re.sub(r'"(?:[^"\\\n\r]|\\.)*"', '""', sparql)

    def test_sparql_string_literal_escapes(self):
        """_sparql_string_literal escapes backslashes, quotes and line breaks."""
        assert _sparql_string_literal("plain") == '"plain"'
        assert _sparql_string_literal("Crohn's") == '"Crohn\'s"'
        assert _sparql_string_literal('a"b') == '"a\\"b"'
        assert _sparql_string_literal("a\\b") == '"a\\\\b"'
        assert _sparql_string_literal("a\nb\rc\td") == '"a\\nb\\rc\\td"'

    @pytest.mark.asyncio
    async def test_search_query_injection_is_escaped(self, adapter):
        """Regression: search text cannot change the structure of the SPARQL query."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": {"bindings": []}}
            await adapter.search_concepts("aspirin", limit=5)
            benign = mock_req.call_args.args[1]["query"]
            malicious = 'x" . } } SELECT * WHERE { ?s ?p ?o } #\\'
            await adapter.search_concepts(malicious, limit=5)
            injected = mock_req.call_args.args[1]["query"]

        assert _sparql_string_literal(malicious) in injected
        assert self._strip_literals(injected) == self._strip_literals(benign)

    @pytest.mark.asyncio
    async def test_search_keeps_entity_search_ranking(self, adapter):
        """Results are ordered by the EntitySearch rank (apiOrdinal)."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": {"bindings": []}}
            await adapter.search_concepts("aspirin", limit=5)
            sparql = mock_req.call_args.args[1]["query"]
        assert "?ordinal wikibase:apiOrdinal true" in sparql
        assert "ORDER BY ?ordinal" in sparql
        assert "LIMIT 5" in sparql

    @pytest.mark.asyncio
    async def test_get_concept_details_rejects_non_qid_injection(self, adapter):
        """Regression: IDs that merely start with Q are not inserted into SPARQL."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            result = await adapter.get_concept_details("Q1 AS ?item) } SELECT * WHERE { ?s ?p ?o")
        assert result is None
        mock_req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_concept_details_mesh_is_not_umls(self, adapter):
        """Regression: MeSH IDs are kept as a category, not as a UMLS identifier."""
        # Shaped like the live rows for Q18216 (aspirin): one row per value
        bindings = [
            _id_row("P31", None, instance_of="type of chemical entity"),
            _id_row("P31", None, instance_of="medication"),
            _id_row("P2892", "C0004057"),
            _id_row("P486", "D001241"),
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"head": {"vars": []}, "results": {"bindings": bindings}}
            concept = await adapter.get_concept_details("Q18216")

        assert concept is not None
        sources = [(i.source, i.identifier) for i in concept.identifiers]
        assert (KnowledgeSource.UMLS, "C0004057") in sources
        assert (KnowledgeSource.MESH, "D001241") in sources
        # MeSH descriptor IDs must not be mistaken for UMLS CUIs
        assert (KnowledgeSource.UMLS, "D001241") not in sources
        assert concept.categories.count("MeSH: D001241") == 1
        assert "type of chemical entity" in concept.categories
        assert "medication" in concept.categories

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass

    @staticmethod
    def _search_row(qid: str, label: str, instance_of: str | None = None) -> dict:
        row = {
            "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
            "itemLabel": {"value": label},
        }
        if instance_of is not None:
            row["instanceOfLabel"] = {"value": instance_of}
        return row

    @pytest.mark.asyncio
    async def test_search_returns_each_item_once_with_merged_instance_of(self, adapter):
        """Regression: an item repeated once per P31 value and the repeats used up `limit`."""
        rows = [
            self._search_row("Q18216", "aspirin", "type of chemical entity"),
            self._search_row("Q18216", "aspirin", "medication"),
            self._search_row("Q10420388", "aspirin tablet", "pharmaceutical product"),
            self._search_row("Q10420388", "aspirin tablet", "pharmaceutical product"),
            self._search_row("Q2039267", "Aspirin", "family name"),
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": {"bindings": rows}}
            results = await adapter.search_concepts("aspirin", limit=2)

        assert [c.primary_id for c in results] == ["Q18216", "Q10420388"]
        assert results[0].categories == ["type of chemical entity", "medication"]
        assert results[1].categories == ["pharmaceutical product"]

    @pytest.mark.asyncio
    async def test_search_merge_types_an_unknown_item_from_a_later_row(self, adapter):
        rows = [
            self._search_row("Q12136", "diabetes mellitus"),
            self._search_row("Q12136", "diabetes mellitus", "disease"),
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": {"bindings": rows}}
            results = await adapter.search_concepts("diabetes", limit=5)

        assert len(results) == 1
        assert results[0].concept_type == ConceptType.DISEASE
        assert results[0].categories == ["disease"]

    @pytest.mark.asyncio
    async def test_search_limits_items_in_a_subquery(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": {"bindings": []}}
            await adapter.search_concepts("aspirin", limit=5)
            sparql = mock_req.call_args.args[1]["query"]

        # LIMIT closes the item subquery, before the P31 join multiplies the rows
        assert re.search(
            r"SELECT \?item \?ordinal WHERE \{.*LIMIT 5\s*\}\s*OPTIONAL", sparql, re.S
        )


# Values copied from the live Wikidata item for Crohn's disease (Q1472).
_CROHN = {
    "P1748": ["C35211", "C37262"],
    "P486": ["D003424"],
    "P672": ["C06.405.205.731.500", "C06.405.469.432.500"],
    "P604": ["000249"],
    "P665": ["H00286"],
    "P699": ["DOID:8778"],
    "P3841": ["HP:0100280"],
    "P4229": ["K50.1"],
    "P7329": ["DD70"],
    "P7807": ["1267652425"],
    "P492": ["266600"],
    "P10283": ["C2992200296", "C2779280984"],
    "P5806": ["34000006"],
    "P2892": ["C0156147"],
    "P4317": ["10232"],
    "P557": ["3178"],
    "P673": ["172940", "928288", "367666"],
    "P1036": ["616.344"],
}


@pytest.fixture
def crohn_rows():
    rows = [_id_row("P31", None, instance_of="type of disease")]
    for prop, values in _CROHN.items():
        rows.extend(_id_row(prop, v) for v in values)
    return rows


class TestWikidataExternalIdentifiers:
    """The external identifiers surfaced by get_concept_details."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return WikidataAdapter(lookup_config)

    def test_property_table_is_well_formed(self):
        assert all(re.fullmatch(r"P\d+", pid) for pid in _EXTERNAL_IDS)
        labels = [spec.label for spec in _EXTERNAL_IDS.values()]
        assert len(labels) == len(set(labels))  # labels double as category prefixes
        mapped = {spec.source for spec in _EXTERNAL_IDS.values() if spec.source}
        assert {
            KnowledgeSource.UMLS,
            KnowledgeSource.MESH,
            KnowledgeSource.NCIEVS,
            KnowledgeSource.SNOMEDCT,
            KnowledgeSource.ICD11,
            KnowledgeSource.OMIM,
            KnowledgeSource.DOID,
            KnowledgeSource.HPO,
        } <= mapped

    def test_clinical_identifiers_are_mapped_to_their_sources(self, adapter, crohn_rows):
        concept = adapter._convert_wikidata_details_to_concept("Q1472", crohn_rows)

        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ids >= {
            (KnowledgeSource.WIKIDATA, "Q1472"),
            (KnowledgeSource.NCIEVS, "C35211"),
            (KnowledgeSource.NCIEVS, "C37262"),
            (KnowledgeSource.MESH, "D003424"),
            (KnowledgeSource.MEDLINEPLUS, "000249"),
            (KnowledgeSource.KEGG, "H00286"),
            (KnowledgeSource.DOID, "DOID:8778"),
            (KnowledgeSource.HPO, "HP:0100280"),
            (KnowledgeSource.ICD11, "DD70"),
            (KnowledgeSource.OMIM, "266600"),
            (KnowledgeSource.OPENALEX, "C2992200296"),
            (KnowledgeSource.SNOMEDCT, "34000006"),
            (KnowledgeSource.UMLS, "C0156147"),
        }
        assert concept.concept_type == ConceptType.DISEASE

    def test_identifiers_without_a_knowledge_source_become_categories(self, adapter, crohn_rows):
        concept = adapter._convert_wikidata_details_to_concept("Q1472", crohn_rows)

        for expected in (
            "ICD-10-CM: K50.1",
            "ICD-11 Foundation: 1267652425",
            "MeSH tree: C06.405.205.731.500",
            "MeSH tree: C06.405.469.432.500",
            "GARD: 10232",
            "DiseasesDB: 3178",
            "eMedicine: 928288",
            "DDC: 616.344",
        ):
            assert expected in concept.categories

    def test_ontology_identifiers_get_resolvable_urls(self, adapter, crohn_rows):
        concept = adapter._convert_wikidata_details_to_concept("Q1472", crohn_rows)
        urls = {i.identifier: i.url for i in concept.identifiers}

        assert urls["DOID:8778"] == "http://purl.obolibrary.org/obo/DOID_8778"
        assert urls["HP:0100280"] == "http://purl.obolibrary.org/obo/HP_0100280"
        assert urls["D003424"] == "https://id.nlm.nih.gov/mesh/D003424"
        assert urls["266600"] == "https://omim.org/entry/266600"

    def test_bare_numbers_get_their_prefix(self, adapter):
        rows = [
            _id_row("P683", "15365"),
            _id_row("P354", "1100"),
            _id_row("P683", "CHEBI:15365"),  # already prefixed: not doubled
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q18216", rows)

        ids = [(i.source, i.identifier) for i in concept.identifiers]
        assert ids.count((KnowledgeSource.CHEBI, "CHEBI:15365")) == 1
        assert (KnowledgeSource.HGNC, "HGNC:1100") in ids

    def test_gene_protein_and_chemical_identifiers(self, adapter):
        rows = [
            _id_row("P351", "672"),
            _id_row("P594", "ENSG00000012048"),
            _id_row("P352", "P38398"),
            _id_row("P662", "2244"),
            _id_row("P592", "CHEMBL25"),
            _id_row("P715", "DB00945"),
            _id_row("P3345", "1191"),
            _id_row("P267", "N02BA01"),
            _id_row("P231", "50-78-2"),
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q18216", rows)

        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ids >= {
            (KnowledgeSource.NCBIGENE, "672"),
            (KnowledgeSource.ENSEMBL, "ENSG00000012048"),
            (KnowledgeSource.UNIPROT, "P38398"),
            (KnowledgeSource.PUBCHEM, "2244"),
            (KnowledgeSource.CHEMBL, "CHEMBL25"),
            (KnowledgeSource.DRUGBANK, "DB00945"),
            (KnowledgeSource.RXNORM, "1191"),
        }
        assert {"ATC: N02BA01", "CAS: 50-78-2"} <= set(concept.categories)

    def test_repeated_rows_and_unknown_properties_are_ignored(self, adapter):
        rows = [
            _id_row("P486", "D003424"),
            _id_row("P486", "D003424"),
            _id_row("P9999999", "whatever"),
            _id_row("P2892", ""),
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q1472", rows)

        assert [i.identifier for i in concept.identifiers] == ["Q1472", "D003424"]

    def test_type_comes_from_any_row_not_just_the_first(self, adapter):
        """The first row is often an identifier row with no instance-of label."""
        rows = [
            _id_row("P486", "D003924"),
            _id_row("P31", None, instance_of="human gene"),
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q1", rows)
        assert concept.concept_type == ConceptType.GENE

    @pytest.mark.asyncio
    async def test_query_requests_every_property_without_a_cross_product(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={}
        ) as mock_req:
            await adapter.get_concept_details("Q1472")

        sparql = mock_req.call_args.args[1]["query"]
        for pid in _EXTERNAL_IDS:
            assert f"wdt:{pid}" in sparql
        assert "UNION" in sparql
        assert sparql.count("OPTIONAL") == 1  # a chain of OPTIONALs would multiply rows
        assert "wd:Q1472" in sparql

    # --- concept type, found by running live against ~13 entities ---

    @pytest.mark.parametrize(
        ("instance_of", "expected"),
        [
            ("symptom", ConceptType.SYMPTOM),
            ("group of stereoisomers", ConceptType.CHEMICAL),
            ("simple carbohydrates", ConceptType.CHEMICAL),
            ("type of chemical entity", ConceptType.CHEMICAL),
        ],
    )
    def test_live_instance_of_labels_map_to_a_type(self, adapter, instance_of, expected):
        rows = [_id_row("P31", None, instance_of=instance_of)]
        concept = adapter._convert_wikidata_details_to_concept("Q1", rows)
        assert concept.concept_type == expected

    @pytest.mark.parametrize(
        ("prop", "value", "expected"),
        [
            ("P685", "9606", ConceptType.ORGANISM),
            ("P352", "P38398", ConceptType.PROTEIN),
            ("P351", "672", ConceptType.GENE),
            ("P715", "DB00945", ConceptType.DRUG),
            ("P683", "15365", ConceptType.CHEMICAL),
            ("P699", "DOID:8778", ConceptType.DISEASE),
            ("P3841", "HP:0012378", ConceptType.PHENOTYPE),
        ],
    )
    def test_type_falls_back_to_the_linked_vocabulary(self, adapter, prop, value, expected):
        """An unrecognised instance-of label must not leave the type UNKNOWN."""
        rows = [_id_row("P31", None, instance_of="something unmapped"), _id_row(prop, value)]
        concept = adapter._convert_wikidata_details_to_concept("Q1", rows)
        assert concept.concept_type == expected

    def test_instance_of_label_wins_over_the_fallback(self, adapter):
        rows = [_id_row("P31", None, instance_of="human gene"), _id_row("P352", "P38398")]
        concept = adapter._convert_wikidata_details_to_concept("Q1", rows)
        assert concept.concept_type == ConceptType.GENE

    def test_omim_alone_does_not_make_an_item_a_disease(self, adapter):
        """OMIM covers genes as well as phenotypes, so it is not used for typing."""
        concept = adapter._convert_wikidata_details_to_concept("Q1", [_id_row("P492", "113705")])
        assert concept.concept_type == ConceptType.UNKNOWN


def _sparql(*rows):
    return {"results": {"bindings": list(rows)}}


def _lit(value):
    return {"type": "literal", "value": value}


def _edge_row(prop, qid, label=None):
    row = {
        "prop": {"type": "uri", "value": f"{_WDT}{prop}"},
        "target": {"type": "uri", "value": f"http://www.wikidata.org/entity/{qid}"},
    }
    if label is not None:
        row["targetLabel"] = _lit(label)
    return row


class TestWikidataMappings:
    @pytest.fixture
    def adapter(self, lookup_config):
        return WikidataAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_mappings_use_the_shared_shape(self, adapter, crohn_rows):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql(*crohn_rows)
        ):
            mappings = await adapter.get_mappings("Q1472")

        assert {
            "fromId": "Q1472",
            "toId": "D003424",
            "fromSource": "Wikidata",
            "toSource": "MESH",
            "mappingType": "xref",
            "confidence": 0.9,
        } in mappings
        by_source = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("OMIM", "266600") in by_source
        assert ("NCIEVS", "C35211") in by_source
        # vocabularies without a KnowledgeSource are named by their label
        assert ("ICD-10-CM", "K50.1") in by_source
        assert all(m["fromSource"] == "Wikidata" for m in mappings)

    @pytest.mark.asyncio
    async def test_mappings_are_deduplicated(self, adapter):
        rows = [_id_row("P486", "D003424"), _id_row("P486", "D003424")]
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql(*rows)
        ):
            mappings = await adapter.get_mappings("Q1472")
        assert len(mappings) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", "not-a-qid", "Q1; DROP"])
    async def test_mappings_reject_non_qids_without_a_request(self, adapter, bad):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_mappings(bad) == []
        mock_req.assert_not_called()

    @pytest.mark.asyncio
    async def test_mappings_degrade_on_error(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            assert await adapter.get_mappings("Q1472") == []


class TestWikidataRelationships:
    @pytest.fixture
    def adapter(self, lookup_config):
        return WikidataAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_edges_carry_the_shared_fields(self, adapter):
        outgoing = _sparql(
            _edge_row("P279", "Q12136", "disease"),
            _edge_row("P780", "Q9690", "fatigue"),
            _edge_row("P2176", "Q19484", "metformin"),
            _edge_row("P2293", "Q18031", None),
        )
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            side_effect=[outgoing, _sparql()],
        ):
            edges = await adapter.get_relationships("Q1472")

        assert {
            "relation_label": "is_a",
            "related_id": "Q12136",
            "related_name": "disease",
            "source": "Wikidata",
            "property": "P279",
        } in edges
        labels = {e["relation_label"]: e for e in edges}
        assert labels["has_symptom"]["related_id"] == "Q9690"
        assert labels["treated_by"]["related_name"] == "metformin"
        # an item without an English label falls back to its Q-ID
        assert labels["has_gene"]["related_name"] == "Q18031"

    @pytest.mark.asyncio
    async def test_limit_applies_per_relation_label(self, adapter):
        """Aspirin has 87 drug interactions; they must not crowd out other edges."""
        rows = [_edge_row("P769", f"Q{100 + i}", f"drug {i}") for i in range(30)]
        rows.append(_edge_row("P2175", "Q1472", "Crohn's disease"))
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            side_effect=[_sparql(*rows), _sparql()],
        ):
            edges = await adapter.get_relationships("Q18216", limit=5)

        labels = [e["relation_label"] for e in edges]
        assert labels.count("interacts_with") == 5
        assert labels.count("treats") == 1

    @pytest.mark.asyncio
    async def test_direct_subclasses_are_has_subclass_edges(self, adapter):
        narrower = _sparql(
            {
                "target": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1"},
                "targetLabel": _lit("ileocolitis"),
            }
        )
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=[_sparql(), narrower]
        ) as mock_req:
            edges = await adapter.get_relationships("Q1472", limit=7)

        assert edges == [
            {
                "relation_label": "has_subclass",
                "related_id": "Q1",
                "related_name": "ileocolitis",
                "source": "Wikidata",
                "property": "P279",
            }
        ]
        sparql = mock_req.call_args_list[1].args[1]["query"]
        assert "?target wdt:P279 wd:Q1472" in sparql
        assert "LIMIT 7" in sparql

    @pytest.mark.asyncio
    async def test_narrower_can_be_switched_off(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql()
        ) as mock_req:
            await adapter.get_relationships("Q1472", include_narrower=False)
        assert mock_req.await_count == 1

    @pytest.mark.asyncio
    async def test_non_item_targets_and_unknown_properties_are_dropped(self, adapter):
        rows = [
            {
                "prop": {"value": f"{_WDT}P780"},
                "target": {"value": "http://www.wikidata.org/.well-known/genid/abc"},
            },
            _edge_row("P9999999", "Q5"),
            _edge_row("P780", "Q9690", "fatigue"),
        ]
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            side_effect=[_sparql(*rows), _sparql()],
        ):
            edges = await adapter.get_relationships("Q1472")
        assert [e["related_id"] for e in edges] == ["Q9690"]

    @pytest.mark.asyncio
    async def test_query_lists_every_relation_property(self, adapter):
        from knowledge_lookup.adapters.wikidata_adapter import _RELATION_PROPERTIES

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql()
        ) as mock_req:
            await adapter.get_relationships("Q1472")

        sparql = mock_req.call_args_list[0].args[1]["query"]
        for pid in _RELATION_PROPERTIES:
            assert f"wdt:{pid}" in sparql
        assert "wd:Q1472" in sparql

    def test_relation_labels_are_known_to_term_expansion(self):
        """is_a / has_subclass must be treated as taxonomic, the rest as associative."""
        from knowledge_lookup.adapters.wikidata_adapter import _RELATION_PROPERTIES
        from knowledge_lookup.core.term_expansion import is_taxonomic_relation

        assert is_taxonomic_relation("is_a")
        assert is_taxonomic_relation("has_subclass")
        taxonomic = {l for l in _RELATION_PROPERTIES.values() if is_taxonomic_relation(l)}
        assert taxonomic == {"is_a"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", "nope", "Q1 }"])
    async def test_rejects_non_qids_without_a_request(self, adapter, bad):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_relationships(bad) == []
        mock_req.assert_not_called()

    @pytest.mark.asyncio
    async def test_degrades_on_error(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            assert await adapter.get_relationships("Q1472") == []


class TestWikidataFindByIdentifier:
    @pytest.fixture
    def adapter(self, lookup_config):
        return WikidataAdapter(lookup_config)

    def _item(self, qid="Q1472", label="Crohn's disease"):
        return {
            "item": {"type": "uri", "value": f"http://www.wikidata.org/entity/{qid}"},
            "itemLabel": _lit(label),
            "itemDescription": _lit("type of inflammatory bowel disease"),
        }

    @pytest.mark.asyncio
    async def test_resolves_a_mesh_descriptor(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value=_sparql(self._item()),
        ) as mock_req:
            found = await adapter.find_by_identifier(KnowledgeSource.MESH, "D003424")

        assert [c.primary_id for c in found] == ["Q1472"]
        assert found[0].primary_label == "Crohn's disease"
        assert found[0].confidence_score == 0.95
        sparql = mock_req.call_args.args[1]["query"]
        assert 'wdt:P486 "D003424"' in sparql

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("source", "identifier", "expected"),
        [
            (KnowledgeSource.CHEBI, "CHEBI:15365", 'wdt:P683 "15365"'),  # stored bare
            (KnowledgeSource.HGNC, "HGNC:1100", 'wdt:P354 "1100"'),
            (KnowledgeSource.DOID, "DOID:8778", 'wdt:P699 "DOID:8778"'),  # stored prefixed
            ("MESH", "D003424", 'wdt:P486 "D003424"'),
            ("ICD-10-CM", "K50.1", 'wdt:P4229 "K50.1"'),  # no KnowledgeSource: by label
            ("P2892", "C0156147", 'wdt:P2892 "C0156147"'),  # by property number
        ],
    )
    async def test_source_and_identifier_forms(self, adapter, source, identifier, expected):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql()
        ) as mock_req:
            await adapter.find_by_identifier(source, identifier)
        assert expected in mock_req.call_args.args[1]["query"]

    @pytest.mark.asyncio
    async def test_identifier_is_an_escaped_literal(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql()
        ) as mock_req:
            await adapter.find_by_identifier(KnowledgeSource.OMIM, '1" } UNION { ?s ?p ?o')
        sparql = mock_req.call_args.args[1]["query"]
        # the quote that would end the literal is backslash-escaped, so the whole
        # input stays inside one string literal
        assert 'wdt:P492 "1\\" } UNION { ?s ?p ?o" .' in sparql

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("source", "identifier"),
        [(KnowledgeSource.BIOPORTAL, "x"), ("nonsense", "x"), (KnowledgeSource.MESH, "  ")],
    )
    async def test_unsupported_source_or_empty_id_makes_no_request(
        self, adapter, source, identifier
    ):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.find_by_identifier(source, identifier) == []
        mock_req.assert_not_called()

    @pytest.mark.asyncio
    async def test_degrades_on_error(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            assert await adapter.find_by_identifier(KnowledgeSource.MESH, "D003424") == []


class TestWikidataSynonymsAndArticle:
    @pytest.fixture
    def adapter(self, lookup_config):
        return WikidataAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_synonyms_are_deduplicated_aliases(self, adapter):
        data = _sparql(
            {"alias": _lit("Crohn disease")},
            {"alias": _lit("regional enteritis")},
            {"alias": _lit("Crohn disease")},
            {"alias": _lit(" ")},
        )
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=data
        ) as mock_req:
            synonyms = await adapter.get_synonyms("Q1472", languages=("en", "de"))

        assert synonyms == ["Crohn disease", "regional enteritis"]
        sparql = mock_req.call_args.args[1]["query"]
        assert 'LANG(?alias) IN ("en", "de")' in sparql
        assert "wd:Q1472 skos:altLabel" in sparql

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("qid", "languages"),
        [("bad", ("en",)), ("Q1", ()), ("Q1", ('en") } #',)), ("Q1", ("EN US",))],
    )
    async def test_synonyms_validate_inputs(self, adapter, qid, languages):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_synonyms(qid, languages=languages) == []
        mock_req.assert_not_called()

    @pytest.mark.asyncio
    async def test_wikipedia_article_bridges_to_dbpedia(self, adapter):
        data = _sparql(
            {
                "article": {"value": "https://en.wikipedia.org/wiki/Crohn%27s_disease"},
                "title": _lit("Crohn's disease"),
            }
        )
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=data
        ) as mock_req:
            article = await adapter.get_wikipedia_article("Q1472")

        assert article == {
            "title": "Crohn's disease",
            "url": "https://en.wikipedia.org/wiki/Crohn%27s_disease",
            "dbpedia_resource": "http://dbpedia.org/resource/Crohn's_disease",
        }
        assert "<https://en.wikipedia.org/>" in mock_req.call_args.args[1]["query"]

    @pytest.mark.asyncio
    async def test_other_languages_have_no_dbpedia_resource(self, adapter):
        data = _sparql(
            {
                "article": {"value": "https://de.wikipedia.org/wiki/Morbus_Crohn"},
                "title": _lit("Morbus Crohn"),
            }
        )
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value=data):
            article = await adapter.get_wikipedia_article("Q1472", language="de")
        assert "dbpedia_resource" not in article
        assert article["title"] == "Morbus Crohn"

    @pytest.mark.asyncio
    async def test_no_article_returns_none(self, adapter):
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_sparql()
        ):
            assert await adapter.get_wikipedia_article("Q1472") is None
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_wikipedia_article("nope") is None
            assert await adapter.get_wikipedia_article("Q1", language="e n") is None
        mock_req.assert_not_called()
