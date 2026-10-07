"""
Unit tests for SnomedCTAdapter.

Fixtures are synthetic (shaped after Snowstorm's documented JSON; the public server was
unreachable during development), so these tests pin the adapter's contract, not the
live server's behaviour.
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import snomedct_adapter as mod
from knowledge_lookup.adapters.snomedct_adapter import SnomedCTAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import snomedct_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(mod.ENV_URL, raising=False)
    monkeypatch.delenv(mod.ENV_BRANCH, raising=False)


@pytest.fixture
def adapter(lookup_config):
    a = SnomedCTAdapter(lookup_config)
    a._last_request = float("-inf")
    return a


def _router(**overrides):
    async def fake(url, params=None, headers=None, json_data=None):
        for needle, value in overrides.items():
            if needle in url:
                if isinstance(value, Exception):
                    raise value
                return value
        if "/descriptions" in url:
            return fx.DESCRIPTION_SEARCH_FATIGUE
        if "/children" in url:
            return fx.CHILDREN_FATIGUE
        if "/members" in url:
            return fx.ICD10_MEMBERS
        if "/browser/" in url and url.endswith("/84229001"):
            return fx.BROWSER_FATIGUE
        return {}

    return AsyncMock(side_effect=fake)


class TestConfiguration:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.SNOMEDCT
        assert adapter.is_available() is True
        assert adapter.min_request_timeout >= 30

    def test_defaults_and_env_overrides(self, adapter, monkeypatch):
        assert adapter.base_url == mod.DEFAULT_SNOWSTORM_URL
        assert adapter.branch == "MAIN"
        monkeypatch.setenv(mod.ENV_URL, "https://snowstorm.example.de/snowstorm/snomed-ct/")
        monkeypatch.setenv(mod.ENV_BRANCH, "/MAIN/SNOMEDCT-DE/")
        assert adapter.base_url == "https://snowstorm.example.de/snowstorm/snomed-ct"
        assert adapter.branch == "MAIN/SNOMEDCT-DE"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("84229001", "84229001"),
            ("SNOMEDCT:84229001", "84229001"),
            ("snomed: 84229001", "84229001"),
            ("SCTID:52448006", "52448006"),
            ("SNOMEDCT_US:52448006", "52448006"),
            ("12345", None),
            ("fatigue", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert SnomedCTAdapter.normalize_id(raw) == expected

    @pytest.mark.asyncio
    async def test_requests_send_polite_headers_and_use_configured_server(
        self, adapter, monkeypatch
    ):
        monkeypatch.setenv(mod.ENV_URL, "https://my.server/snomed")
        monkeypatch.setenv(mod.ENV_BRANCH, "MAIN/SNOMEDCT-DE")
        mock = _router()
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_concepts("fatigue")
        (url,), kwargs = mock.call_args.args[:1], mock.call_args
        assert url == "https://my.server/snomed/MAIN/SNOMEDCT-DE/descriptions"
        headers = kwargs.kwargs["headers"]
        assert headers["Accept-Language"] == "en"
        assert "biomedical-knowledge-lookup" in headers["User-Agent"]
        params = mock.call_args.args[1]
        assert params["active"] == "true" and params["conceptActive"] == "true"

    @pytest.mark.asyncio
    async def test_public_server_is_throttled_private_is_not(self, adapter, monkeypatch):
        sleeps = []

        async def fake_sleep(s):
            sleeps.append(s)

        with patch.object(adapter, "_make_request", new=_router()):
            with patch.object(mod.asyncio, "sleep", new=fake_sleep):
                await adapter._get(f"{adapter.base_url}/x")
                await adapter._get(f"{adapter.base_url}/x")
                assert sleeps and 0 < sleeps[0] <= mod._PUBLIC_INTERVAL + 1e-6
                sleeps.clear()
                monkeypatch.setenv(mod.ENV_URL, "http://localhost:8080")
                adapter._last_request = 0.0
                await adapter._get("http://localhost:8080/x")
                assert sleeps == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_groups_by_concept(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            res = await adapter.search_concepts("fatigue", limit=10)
        # Fatigue appears once despite two matching descriptions; the orphan item (no
        # embedded concept) is kept, labelled with its matched term.
        assert [c.primary_id for c in res] == ["84229001", "52448006", "111111111"]
        fatigue = res[0]
        assert fatigue.primary_label == "Fatigue"
        assert fatigue.concept_type == ConceptType.PHENOTYPE
        assert fatigue.semantic_types == ["finding"]
        data = fatigue.source_data[KnowledgeSource.SNOMEDCT]
        assert data["fsn"] == "Fatigue (finding)" and data["semantic_tag"] == "finding"
        assert "Tiredness" in fatigue.synonyms  # the matched term
        assert res[1].concept_type == ConceptType.DISEASE

    @pytest.mark.asyncio
    async def test_search_limit_and_blank(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            assert len(await adapter.search_concepts("fatigue", limit=1)) == 1
            assert await adapter.search_concepts("fatigue", limit=0) == []
        assert await adapter.search_concepts("  ") == []

    @pytest.mark.asyncio
    async def test_search_by_sctid(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            res = await adapter.search_concepts("SNOMEDCT:84229001")
        assert [c.primary_id for c in res] == ["84229001"]
        assert "Lack of energy" in res[0].synonyms

    @pytest.mark.asyncio
    async def test_search_orphan_item_uses_item_term(self, adapter):
        page = {
            "items": [
                {"term": "Orphan term", "conceptId": "111111111", "concept": {}},
            ]
        }
        with patch.object(adapter, "_make_request", new=_router(descriptions=page)):
            res = await adapter.search_concepts("orphan")
        assert [(c.primary_id, c.primary_label) for c in res] == [("111111111", "Orphan term")]

    @pytest.mark.asyncio
    async def test_search_empty_and_error(self, adapter):
        with patch.object(adapter, "_make_request", new=_router(descriptions={"items": []})):
            assert await adapter.search_concepts("zzz") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("fatigue") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value="junk")):
            assert await adapter.search_concepts("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            c = await adapter.get_concept_details("SNOMEDCT:84229001")
        assert c.primary_id == "84229001" and c.primary_label == "Fatigue"
        assert c.synonyms == ["Tiredness", "Lack of energy"]  # no FSN/PT dupes, inactive, non-en
        assert c.definitions == ["Feeling of exhaustion."]
        data = c.source_data[KnowledgeSource.SNOMEDCT]
        assert data["definition_status"] == "PRIMITIVE"
        assert data["effective_time"] == "20020131"
        assert data["branch"] == "MAIN"
        assert c.identifiers[0].url.endswith("84229001")

    @pytest.mark.asyncio
    async def test_details_missing_invalid_error_and_no_label(self, adapter):
        assert await adapter.get_concept_details("fatigue") is None
        with patch.object(adapter, "_make_request", new=_router()):
            assert await adapter.get_concept_details("99999999") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("84229001") is None
        bare = {"conceptId": "84229001", "descriptions": []}
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=bare)):
            assert await adapter.get_concept_details("84229001") is None

    @pytest.mark.asyncio
    async def test_browser_concept_is_cached_across_calls(self, adapter):
        mock = _router()
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.get_concept_details("84229001")
            await adapter.get_relationships("84229001")
        urls = [c.args[0] for c in mock.call_args_list]
        assert sum("/browser/" in u for u in urls) == 1

    @pytest.mark.asyncio
    async def test_cache_is_bounded(self, adapter):
        page = {"conceptId": "1", "pt": {"term": "x"}}
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=page)):
            for i in range(70):
                await adapter._browser_concept(str(100000 + i))
        assert len(adapter._concept_cache) == 64

    @pytest.mark.parametrize(
        "fsn,ctype",
        [
            ("Dementia (disorder)", ConceptType.DISEASE),
            ("Fatigue (finding)", ConceptType.PHENOTYPE),
            ("Biopsy (procedure)", ConceptType.PROCEDURE),
            ("Muscle structure (body structure)", ConceptType.ANATOMICAL_ENTITY),
            ("Aspirin (substance)", ConceptType.CHEMICAL),
            ("Aspirin (medicinal product)", ConceptType.DRUG),
            ("Escherichia coli (organism)", ConceptType.ORGANISM),
            ("Weird thing (situation)", ConceptType.UNKNOWN),
            ("No tag at all", ConceptType.UNKNOWN),
        ],
    )
    def test_semantic_tag_to_concept_type(self, adapter, fsn, ctype):
        c = adapter._concept_from_mini("123456", {"fsn": {"term": fsn}, "pt": {"term": "x"}})
        assert c.concept_type == ctype


class TestRelationships:
    @pytest.mark.asyncio
    async def test_is_a_attributes_and_children(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            rels = await adapter.get_relationships("84229001")
        triples = [(r["relation_label"], r["related_id"], r["related_name"]) for r in rels]
        assert triples[0] == ("is_a", "404684003", "Clinical finding")
        assert ("finding_site", "113343008", "Muscle structure") in triples
        assert ("has_subtype", "272060000", "Chronic fatigue") in triples
        assert ("has_subtype", "272061001", "Acute fatigue") in triples  # PT missing -> FSN stem
        assert all(r["related_id"] != "999999999" for r in rels)  # inactive parent skipped
        assert sum(r["relation_label"] == "is_a" for r in rels) == 1  # stated duplicate skipped
        site = next(r for r in rels if r["relation_label"] == "finding_site")
        assert site["group"] == 1 and site["attribute_id"] == "363698007"
        assert all(
            set(r) >= {"relation_label", "related_id", "related_name", "source"} for r in rels
        )

    @pytest.mark.asyncio
    async def test_limit_trims_children_first(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            rels = await adapter.get_relationships("84229001", limit=2)
        assert [r["relation_label"] for r in rels] == ["is_a", "finding_site"]

    @pytest.mark.asyncio
    async def test_relationships_edge_cases(self, adapter):
        assert await adapter.get_relationships("nope") == []
        assert await adapter.get_relationships("84229001", limit=0) == []
        with patch.object(adapter, "_make_request", new=_router()):
            assert await adapter.get_relationships("99999999") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("84229001") == []

    @pytest.mark.asyncio
    async def test_attribute_without_name_falls_back_to_id(self, adapter):
        concept = {
            "conceptId": "84229001",
            "pt": {"term": "Fatigue"},
            "relationships": [
                {
                    "active": True,
                    "typeId": "246075003",
                    "target": {"conceptId": "1", "pt": {"term": "T"}},
                }
            ],
        }
        with patch.object(adapter, "_make_request", new=_router(**{"/browser/": concept})):
            rels = await adapter.get_relationships("84229001")
        assert rels[0]["relation_label"] == "attribute_246075003"


class TestMappings:
    @pytest.mark.asyncio
    async def test_icd10_mappings(self, adapter):
        mock = _router()
        with patch.object(adapter, "_make_request", new=mock):
            maps = await adapter.get_mappings("SNOMEDCT:52448006")
        assert [m["toId"] for m in maps] == ["F03.9", "G30.9"]
        first = maps[0]
        assert (first["fromId"], first["fromSource"], first["toSource"]) == (
            "52448006",
            "SNOMEDCT",
            "ICD10",
        )
        assert first["mapAdvice"] == "ALWAYS F03.9"
        assert {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"} <= set(
            first
        )
        params = mock.call_args.args[1]
        assert params["referenceSet"] == mod.ICD10_MAP_REFSET
        assert params["referencedComponentId"] == "52448006"

    @pytest.mark.asyncio
    async def test_mappings_edge_cases(self, adapter):
        assert await adapter.get_mappings("nope") == []
        with patch.object(adapter, "_make_request", new=_router(members={"items": []})):
            assert await adapter.get_mappings("52448006") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("52448006") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=[{"x": 1}])):
            assert await adapter.get_mappings("52448006") == []  # bare list -> items w/o fields
