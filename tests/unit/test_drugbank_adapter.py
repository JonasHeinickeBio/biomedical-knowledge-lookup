"""
Unit tests for DrugBankAdapter (DrugBank data served by MyChem.info).
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.drugbank_adapter import DrugBankAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

ASPIRIN = {
    "_license": "https://bit.ly/3Hikpvm",
    "cas": "50-78-2",
    "id": "DB00945",
    "inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    "name": "Acetylsalicylic acid",
    "synonyms": ["2-Acetoxybenzoic acid", "Acetylsalicylic acid", "Aspirin", "ASA"],
    "unii": "R16CO5Y76E",
}
CAFFEINE = {
    "_license": "https://bit.ly/3Hikpvm",
    "id": "DB00201",
    "name": "Caffeine",
    "synonyms": ["1,3,7-trimethylxanthine"],
}


def _query_response(*hits):
    """Shape of a MyChem.info /v1/query response."""
    return {"took": 3, "total": len(hits), "max_score": 28.8, "hits": list(hits)}


def _hit(record, _id="BSYNRYMUTXBXSQ-UHFFFAOYSA-N"):
    return {"_id": _id, "_score": 28.8, "drugbank": record}


class TestDrugBankAdapter:
    """Tests for DrugBankAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create DrugBankAdapter instance."""
        return DrugBankAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test DrugBankAdapter initialization."""
        adapter = DrugBankAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.DRUGBANK
        assert adapter.config == lookup_config
        assert adapter.api_url == "https://mychem.info/v1"

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.DRUGBANK

    def test_is_available(self, adapter):
        """The MyChem.info API needs no key."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.DRUGBANK: 5.0})
        adapter = DrugBankAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- search_concepts ---

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Search converts MyChem.info drugbank records to DRUG concepts."""
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value=_query_response(_hit(ASPIRIN), _hit(CAFFEINE, "RYYVLZVUVIJVGH")),
        ) as mock_req:
            results = await adapter.search_concepts("aspirin", limit=10)
        assert [r.primary_id for r in results] == ["DB00945", "DB00201"]
        assert results[0].primary_label == "Acetylsalicylic acid"
        assert results[0].concept_type == ConceptType.DRUG
        url, params = mock_req.call_args.args
        assert url == "https://mychem.info/v1/query"
        assert params["q"] == "(aspirin) AND _exists_:drugbank"
        assert params["size"] == 10
        assert "drugbank.id" in params["fields"]

    @pytest.mark.asyncio
    async def test_search_concepts_does_not_use_ols(self, adapter):
        """Regression: the retired OLS drugbank ontology is no longer queried."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_query_response()
        ) as mock_req:
            await adapter.search_concepts("aspirin")
        url = mock_req.call_args.args[0]
        assert "ols4" not in url
        assert "ontology" not in mock_req.call_args.args[1]

    @pytest.mark.asyncio
    async def test_search_concepts_escapes_query_syntax(self, adapter):
        """Lucene special characters in the query are escaped."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_query_response()
        ) as mock_req:
            await adapter.search_concepts("insulin (human): 5-FU", limit=3)
        assert mock_req.call_args.args[1]["q"] == (
            r"(insulin \(human\)\: 5\-FU) AND _exists_:drugbank"
        )

    @pytest.mark.asyncio
    async def test_search_concepts_empty_query(self, adapter):
        """A blank query returns [] without a request."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.search_concepts("   ") == []
        mock_req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_concepts_no_hits_key(self, adapter):
        """Test search_concepts with missing hits key."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value={}):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search_concepts returns empty on exception."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_skips_hits_without_drugbank(self, adapter):
        """Hits without drugbank data or with incomplete records are skipped."""
        data = _query_response(
            {"_id": "68001-623", "_score": 25.6},
            _hit({"id": "", "name": ""}),
            _hit(ASPIRIN),
        )
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value=data):
            results = await adapter.search_concepts("test")
        assert [r.primary_id for r in results] == ["DB00945"]

    @pytest.mark.asyncio
    async def test_search_concepts_deduplicates_and_limits(self, adapter):
        """Records repeated across hits (or as lists) appear once; limit is respected."""
        data = _query_response(
            _hit([ASPIRIN, CAFFEINE]),
            _hit(ASPIRIN, "OTHER"),
            _hit({"id": "DB00388", "name": "Phenylephrine"}, "SONNWYBIRXJNDC"),
        )
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value=data):
            results = await adapter.search_concepts("test", limit=2)
        assert [r.primary_id for r in results] == ["DB00945", "DB00201"]

    # --- get_concept_details ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize("concept_id", ["DB00945", "DRUGBANK:DB00945", " db00945 "])
    async def test_get_concept_details_success(self, adapter, concept_id):
        """get_concept_details queries drugbank.id and returns the matching record."""
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value=_query_response(_hit(ASPIRIN)),
        ) as mock_req:
            result = await adapter.get_concept_details(concept_id)
        assert result is not None
        assert result.primary_id == "DB00945"
        assert result.confidence_score == 0.95
        assert mock_req.call_args.args[1]["q"].upper() == 'DRUGBANK.ID:"DB00945"'

    @pytest.mark.asyncio
    async def test_get_concept_details_not_found(self, adapter):
        """Unknown IDs return None."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=_query_response()
        ):
            result = await adapter.get_concept_details("DB99999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_ignores_other_ids(self, adapter):
        """Only a record whose ID matches is returned."""
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value=_query_response(_hit(CAFFEINE)),
        ):
            result = await adapter.get_concept_details("DB00945")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_none_data(self, adapter):
        """Test get_concept_details returns None with None data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value=None):
            result = await adapter.get_concept_details("DB00945")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter):
        """Test get_concept_details returns None on exception."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            result = await adapter.get_concept_details("DB00945")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_id(self, adapter):
        """An empty ID returns None without a request."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_concept_details("DRUGBANK:") is None
        mock_req.assert_not_awaited()

    # --- converters ---

    def test_convert_result_basic(self, adapter):
        """Test _convert_drugbank_result_to_concept with a full record."""
        concept = adapter._convert_drugbank_result_to_concept(ASPIRIN)
        assert concept is not None
        assert concept.primary_id == "DB00945"
        assert concept.primary_label == "Acetylsalicylic acid"
        assert concept.concept_type == ConceptType.DRUG
        assert concept.confidence_score == 0.9
        assert concept.sources == [KnowledgeSource.DRUGBANK]
        assert concept.source_data[KnowledgeSource.DRUGBANK]["unii"] == "R16CO5Y76E"

    def test_convert_result_identifier_url(self, adapter):
        """The identifier links to the DrugBank drug page."""
        concept = adapter._convert_drugbank_result_to_concept(ASPIRIN)
        assert len(concept.identifiers) == 1
        assert concept.identifiers[0].identifier == "DB00945"
        assert concept.identifiers[0].url == "https://go.drugbank.com/drugs/DB00945"

    def test_convert_result_synonyms_exclude_label(self, adapter):
        """Synonyms are copied without repeating the label."""
        concept = adapter._convert_drugbank_result_to_concept(ASPIRIN)
        assert concept.synonyms == ["2-Acetoxybenzoic acid", "Aspirin", "ASA"]

    def test_convert_result_string_synonym(self, adapter):
        """A single synonym may be a string."""
        concept = adapter._convert_drugbank_result_to_concept(
            {"id": "DB00001", "name": "Lepirudin", "synonyms": "Hirudin variant-1"}
        )
        assert concept.synonyms == ["Hirudin variant-1"]

    def test_convert_result_chemical_identifiers(self, adapter):
        """CAS, UNII and InChIKey are exposed as prefixed categories."""
        concept = adapter._convert_drugbank_result_to_concept(ASPIRIN)
        assert concept.categories == [
            "cas:50-78-2",
            "unii:R16CO5Y76E",
            "inchi_key:BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        ]

    def test_convert_result_with_description(self, adapter):
        """A description, when served, becomes a definition."""
        concept = adapter._convert_drugbank_result_to_concept(
            {"id": "DB00001", "name": "Test Drug", "description": "A test drug description"}
        )
        assert concept.definitions == ["A test drug description"]

    def test_convert_result_no_optional_fields(self, adapter):
        """Missing optional fields leave the lists empty."""
        concept = adapter._convert_drugbank_result_to_concept({"id": "DB00001", "name": "X"})
        assert concept.synonyms == []
        assert concept.definitions == []
        assert concept.categories == []

    @pytest.mark.parametrize("record", [{"name": "Test Drug"}, {"id": "DB00001"}])
    def test_convert_result_missing_id_or_name(self, adapter, record):
        """Records without an ID or name are skipped."""
        assert adapter._convert_drugbank_result_to_concept(record) is None

    def test_convert_result_exception(self, adapter):
        """Test _convert_drugbank_result_to_concept returns None on exception."""
        assert adapter._convert_drugbank_result_to_concept(None) is None

    def test_convert_details_basic(self, adapter):
        """Test _convert_drugbank_details_to_concept with basic data."""
        concept = adapter._convert_drugbank_details_to_concept(ASPIRIN)
        assert concept is not None
        assert concept.primary_id == "DB00945"
        assert concept.confidence_score == 0.95
        assert concept.concept_type == ConceptType.DRUG

    def test_convert_details_exception(self, adapter):
        """Test _convert_drugbank_details_to_concept returns None on exception."""
        assert adapter._convert_drugbank_details_to_concept(None) is None
