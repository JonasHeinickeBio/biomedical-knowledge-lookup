"""Unit tests for OpenFDAEventsAdapter (real openFDA count responses, no network)."""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.openfdaevents_adapter import (
    BASE_URL,
    CAVEAT,
    OpenFDAEventsAdapter,
    clean_term,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import openfdaevents_responses as fx

pytestmark = pytest.mark.unit

ASPIRIN = 'patient.drug.openfda.generic_name.exact:"ASPIRIN"'
FATIGUE = 'patient.reaction.reactionmeddrapt.exact:"FATIGUE"'


class NotFound(Exception):
    """Stands in for aiohttp's 404 ClientResponseError (openFDA: no matches)."""

    status = 404


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OPENFDA_API_KEY", raising=False)


@pytest.fixture
def adapter():
    return OpenFDAEventsAdapter(LookupConfig())


def fake_api(routes):
    """Answer ``_make_request`` by ``(search, count)``; missing routes raise a 404."""

    async def fake(url, params=None, **kwargs):
        assert url == BASE_URL
        key = (params["search"], params["count"])
        if key not in routes:
            raise NotFound()
        value = routes[key]
        if isinstance(value, Exception):
            raise value
        return value

    return AsyncMock(side_effect=fake)


FULL_ROUTES = {
    (ASPIRIN, "serious"): fx.ASPIRIN_SERIOUS,
    (FATIGUE, "serious"): fx.FATIGUE_SERIOUS,
    (ASPIRIN, "patient.reaction.reactionmeddrapt.exact"): fx.ASPIRIN_REACTIONS,
    (FATIGUE, "patient.drug.openfda.generic_name.exact"): fx.FATIGUE_DRUGS,
    (ASPIRIN, "patient.drug.drugindication.exact"): fx.ASPIRIN_INDICATIONS,
    (
        'patient.drug.openfda.generic_name:"ASPIRIN"',
        "patient.drug.openfda.generic_name.exact",
    ): fx.SEARCH_DRUG_ASPIRIN,
    (
        'patient.reaction.reactionmeddrapt:"ASPIRIN"',
        "patient.reaction.reactionmeddrapt.exact",
    ): {"results": [{"term": "ASPIRIN-EXACERBATED RESPIRATORY DISEASE", "count": 617}]},
    (
        'patient.drug.openfda.generic_name:"CHRONIC FATIGUE SYNDROME"',
        "patient.drug.openfda.generic_name.exact",
    ): NotFound(),
    (
        'patient.reaction.reactionmeddrapt:"CHRONIC FATIGUE SYNDROME"',
        "patient.reaction.reactionmeddrapt.exact",
    ): fx.SEARCH_REACTION_CFS,
}


@pytest.fixture
def api(adapter):
    with patch.object(adapter, "_make_request", new=fake_api(FULL_ROUTES)) as mock:
        yield mock


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.OPENFDAEVENTS
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("FAERS:DRUG:aspirin", ("drug", "ASPIRIN")),
            ("drug: aspirin", ("drug", "ASPIRIN")),
            ("FAERS:REACTION:Fatigue", ("reaction", "FATIGUE")),
            ("reaction:chronic  fatigue syndrome", ("reaction", "CHRONIC FATIGUE SYNDROME")),
            ("PT:fatigue", ("reaction", "FATIGUE")),
            ("MedDRA:fatigue", ("reaction", "FATIGUE")),
            ("aspirin", (None, "ASPIRIN")),
            ('as"pi\\rin', (None, "ASPIRIN")),
            ("DRUG:", (None, "DRUG:")),
            ("", None),
            ('""', None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert OpenFDAEventsAdapter.parse_id(raw) == expected

    def test_clean_term(self):
        assert clean_term(' a "b"\\ c ') == "A B C"
        assert clean_term(None) == ""


class TestRequestParameters:
    @pytest.mark.asyncio
    async def test_no_key_by_default(self, adapter, api):
        await adapter.get_concept_details("aspirin")
        assert all("api_key" not in c.kwargs["params"] for c in api.call_args_list)

    @pytest.mark.asyncio
    async def test_key_from_environment_and_limit_clamp(self, monkeypatch):
        monkeypatch.setenv("OPENFDA_API_KEY", "test-key")
        adapter = OpenFDAEventsAdapter(LookupConfig())
        mock = AsyncMock(return_value=fx.ASPIRIN_REACTIONS)
        with patch.object(adapter, "_make_request", new=mock):
            await adapter._query(ASPIRIN, "patient.reaction.reactionmeddrapt.exact", 5000)
            await adapter._query(ASPIRIN, "serious")
        first, second = (c.kwargs["params"] for c in mock.call_args_list)
        assert first["api_key"] == "test-key" and first["limit"] == 1000
        assert "limit" not in second


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_drug_and_reaction_names(self, adapter, api):
        results = await adapter.search_concepts("aspirin", limit=10)
        ids = [c.primary_id for c in results]
        # unrelated co-listed drugs (FUROSEMIDE...) are filtered out
        assert ids == [
            "FAERS:DRUG:ASPIRIN",
            "FAERS:DRUG:ASPIRIN 81 MG",
            "FAERS:DRUG:ASPIRIN 325 MG",
            "FAERS:DRUG:ACETAMINOPHEN, ASPIRIN, AND CAFFEINE",
            "FAERS:REACTION:ASPIRIN-EXACERBATED RESPIRATORY DISEASE",
        ]
        drug, reaction = results[0], results[-1]
        assert drug.concept_type == ConceptType.DRUG
        assert reaction.concept_type == ConceptType.PHENOTYPE
        assert drug.primary_label == "ASPIRIN"
        assert drug.source_data[KnowledgeSource.OPENFDAEVENTS]["report_count"] == 534081
        assert reaction.source_data[KnowledgeSource.OPENFDAEVENTS]["caveat"] == CAVEAT
        assert "FAERS" in drug.categories

    @pytest.mark.asyncio
    async def test_limit_splits_between_drugs_and_reactions(self, adapter, api):
        results = await adapter.search_concepts("aspirin", limit=2)
        assert [c.primary_id for c in results] == [
            "FAERS:DRUG:ASPIRIN",
            "FAERS:REACTION:ASPIRIN-EXACERBATED RESPIRATORY DISEASE",
        ]
        assert len(await adapter.search_concepts("aspirin", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_reaction_only_match_and_404_side(self, adapter, api):
        results = await adapter.search_concepts("chronic fatigue syndrome", limit=5)
        assert [c.primary_id for c in results] == ["FAERS:REACTION:CHRONIC FATIGUE SYNDROME"]

    @pytest.mark.asyncio
    async def test_no_match_anywhere(self, adapter):
        with patch.object(adapter, "_make_request", new=fake_api({})):
            assert await adapter.search_concepts("zzzz") == []

    @pytest.mark.asyncio
    async def test_empty_inputs_make_no_request(self, adapter):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("  ", 5) == []
            assert await adapter.search_concepts('""', 5) == []
            assert await adapter.search_concepts("aspirin", 0) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_failures_return_empty(self, adapter):
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("429"))):
            assert await adapter.search_concepts("aspirin") == []
        with patch.object(adapter, "_query", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("aspirin") == []

    @pytest.mark.asyncio
    async def test_malformed_payloads(self, adapter):
        for bad in ([], {"results": "x"}, {"error": {}}, {"results": [{"term": "A"}, "junk"]}):
            with patch.object(adapter, "_make_request", new=AsyncMock(return_value=bad)):
                assert await adapter.search_concepts("aspirin") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_drug_details(self, adapter, api):
        concept = await adapter.get_concept_details("FAERS:DRUG:Aspirin")
        assert concept.primary_id == "FAERS:DRUG:ASPIRIN"
        assert concept.concept_type == ConceptType.DRUG
        data = concept.source_data[KnowledgeSource.OPENFDAEVENTS]
        assert data["total_reports"] == 381371 + 152457
        assert data["serious_reports"] == 381371
        assert data["non_serious_reports"] == 152457
        assert api.call_args.kwargs["params"]["search"] == ASPIRIN

    @pytest.mark.asyncio
    async def test_bare_name_falls_back_to_reaction(self, adapter, api):
        concept = await adapter.get_concept_details("fatigue")
        assert concept.primary_id == "FAERS:REACTION:FATIGUE"
        assert concept.source_data[KnowledgeSource.OPENFDAEVENTS]["total_reports"] == 766149

    @pytest.mark.asyncio
    async def test_unknown_and_invalid(self, adapter, api):
        assert await adapter.get_concept_details("drug:notadrug") is None
        assert await adapter.get_concept_details("notathing") is None
        assert await adapter.get_concept_details("") is None

    @pytest.mark.asyncio
    async def test_zero_totals_and_failures(self, adapter):
        zero = {(ASPIRIN, "serious"): {"results": [{"term": 1, "count": 0}]}}
        with patch.object(adapter, "_make_request", new=fake_api(zero)):
            assert await adapter.get_concept_details("drug:aspirin") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("x"))):
            assert await adapter.get_concept_details("drug:aspirin") is None
        with patch.object(adapter, "_totals", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("drug:aspirin") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_drug_to_reactions(self, adapter, api):
        rels = await adapter.get_relationships("FAERS:DRUG:ASPIRIN", limit=3)
        assert [r["related_name"] for r in rels] == ["FATIGUE", "DYSPNOEA", "DIARRHOEA"]
        first = rels[0]
        assert first["relation_label"] == "reported_adverse_event"
        assert first["related_id"] == "FAERS:REACTION:FATIGUE"
        assert first["report_count"] == 33155
        assert first["total_reports"] == 533828
        assert first["report_proportion"] == pytest.approx(33155 / 533828, abs=1e-6)
        assert first["source"] == "OPENFDAEVENTS" and first["evidence"] == CAVEAT
        assert all(
            set(r) >= {"relation_label", "related_id", "related_name", "source"} for r in rels
        )

    @pytest.mark.asyncio
    async def test_limit_is_sent_and_respected(self, adapter, api):
        rels = await adapter.get_relationships("drug:aspirin", limit=2)
        assert len(rels) == 2
        counts_call = next(
            c
            for c in api.call_args_list
            if c.kwargs["params"]["count"].endswith("reactionmeddrapt.exact")
        )
        assert counts_call.kwargs["params"]["limit"] == 2
        assert await adapter.get_relationships("drug:aspirin", limit=0) == []

    @pytest.mark.asyncio
    async def test_reaction_to_drugs(self, adapter, api):
        rels = await adapter.get_relationships("reaction:fatigue", limit=10)
        assert rels[0]["relation_label"] == "reported_with_drug"
        assert rels[0]["related_id"] == "FAERS:DRUG:PREDNISONE"
        assert rels[0]["total_reports"] == 766149
        assert {r["entity_type"] for r in rels} == {"drug"}

    @pytest.mark.asyncio
    async def test_bare_names_resolve_kind(self, adapter, api):
        drug_rels = await adapter.get_relationships("aspirin", limit=2)
        assert drug_rels[0]["relation_label"] == "reported_adverse_event"
        reaction_rels = await adapter.get_relationships("fatigue", limit=2)
        assert reaction_rels[0]["relation_label"] == "reported_with_drug"

    @pytest.mark.asyncio
    async def test_indications_are_opt_in_and_case_folded(self, adapter, api):
        rels = await adapter.get_relationships("drug:aspirin", limit=2, include_indications=True)
        indications = [r for r in rels if r["relation_label"] == "reported_indication"]
        assert indications[0]["related_name"] == "PRODUCT USED FOR UNKNOWN INDICATION"
        assert indications[0]["report_count"] == 130100 + 92142
        names = [r["related_name"] for r in indications]
        assert len(names) == len(set(names))
        assert (
            next(r for r in indications if r["related_name"] == "HYPERTENSION")["report_count"]
            == 38543 + 14866
        )
        before = api.call_count
        await adapter.get_relationships("drug:aspirin", limit=2)
        assert api.call_count - before == 2  # totals + reactions only

    @pytest.mark.asyncio
    async def test_indication_counts_helper(self, adapter, api):
        counts = await adapter.get_indication_counts("aspirin", limit=10)
        assert counts["PRODUCT USED FOR UNKNOWN INDICATION"] == 222242
        assert list(counts.values()) == sorted(counts.values(), reverse=True)
        assert await adapter.get_indication_counts("") == {}
        assert await adapter.get_indication_counts("drug:notadrug") == {}

    @pytest.mark.asyncio
    async def test_unknown_names_and_failures(self, adapter, api):
        assert await adapter.get_relationships("drug:notadrug") == []
        assert await adapter.get_relationships("") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("x"))):
            assert await adapter.get_relationships("drug:aspirin") == []
        with patch.object(adapter, "_totals", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("drug:aspirin") == []

    @pytest.mark.asyncio
    async def test_totals_without_rows(self, adapter):
        routes = {(ASPIRIN, "serious"): fx.ASPIRIN_SERIOUS}
        with patch.object(adapter, "_make_request", new=fake_api(routes)):
            assert await adapter.get_relationships("drug:aspirin") == []

    @pytest.mark.asyncio
    async def test_mappings_not_supported(self, adapter):
        assert await adapter.get_mappings("FAERS:DRUG:ASPIRIN") == []

    @pytest.mark.asyncio
    async def test_non_404_errors_are_logged_not_raised(self, adapter, caplog):
        class Boom(Exception):
            status = 429

        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=Boom("slow down"))):
            with caplog.at_level("WARNING"):
                assert await adapter._query(ASPIRIN, "serious") is None
        assert "slow down" in caplog.text
