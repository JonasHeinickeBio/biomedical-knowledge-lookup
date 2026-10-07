"""
Unit tests for NodeNormAdapter (NCATS Node Normalizer + Name Resolver), driven by trimmed real
responses.
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.nodenorm_adapter import (
    NodeNormAdapter,
    _concept_type,
    canonical_curie,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import nodenorm_responses as fx

pytestmark = pytest.mark.unit

NN = "https://nodenormalization-sri.renci.org"
NR = "https://name-resolution-sri.renci.org"


@pytest.fixture
def adapter(lookup_config):
    return NodeNormAdapter(lookup_config)


def mocked(adapter, return_value=None, side_effect=None):
    return patch.object(
        adapter, "_make_request", AsyncMock(return_value=return_value, side_effect=side_effect)
    )


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.NODENORM
        assert adapter.is_available() is True
        assert adapter.conflate is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("hgnc:1100", "HGNC:1100"),
            ("Mondo:0005404", "MONDO:0005404"),
            ("ncbigene:672", "NCBIGene:672"),
            ("UNIPROTKB:P38398", "UniProtKB:P38398"),
            ("mesh:D015673", "MESH:D015673"),
            ("PMID:123", "PMID:123"),
            ("weird:1", "weird:1"),  # unknown prefixes are passed through untouched
            ("diabetes", None),
            ("", None),
            ("HP:", None),
        ],
    )
    def test_canonical_curie(self, raw, expected):
        assert canonical_curie(raw) == expected

    def test_concept_type_uses_most_specific_known_type(self):
        assert _concept_type(["biolink:Disease", "biolink:NamedThing"]) == ConceptType.DISEASE
        assert _concept_type(["biolink:Gene", "biolink:GeneOrGeneProduct"]) == ConceptType.GENE
        assert _concept_type(["biolink:Protein"]) == ConceptType.PROTEIN
        assert _concept_type(["biolink:SmallMolecule"]) == ConceptType.CHEMICAL
        assert _concept_type(["biolink:NamedThing"]) == ConceptType.UNKNOWN
        assert _concept_type([]) == ConceptType.UNKNOWN


class TestSearch:
    @pytest.mark.asyncio
    async def test_name_resolver_lookup(self, adapter):
        with mocked(adapter, fx.NAMERES_LOOKUP) as request:
            concepts = await adapter.search_concepts("chronic fatigue syndrome", limit=5)
        request.assert_awaited_once_with(
            f"{NR}/lookup", {"string": "chronic fatigue syndrome", "limit": 5}
        )
        top, second = concepts
        assert top.primary_id == "MONDO:0005404"
        assert top.primary_label == "myalgic encephalomeyelitis/chronic fatigue syndrome"
        assert top.concept_type == ConceptType.DISEASE
        assert top.confidence_score == 1.0
        assert 0 < second.confidence_score < 1.0
        assert "Disease" in top.semantic_types
        assert "ME/CFS" in top.synonyms and top.primary_label not in top.synonyms
        assert (KnowledgeSource.MONDO, "MONDO:0005404") in {
            (i.source, i.identifier) for i in top.identifiers
        }
        meta = top.source_data[KnowledgeSource.NODENORM]
        assert meta["clique_identifier_count"] == 15 and meta["curie"] == "MONDO:0005404"

    @pytest.mark.asyncio
    async def test_limit_caps_results_and_request_size(self, adapter):
        with mocked(adapter, fx.NAMERES_LOOKUP) as request:
            assert len(await adapter.search_concepts("x", limit=1)) == 1
            await adapter.search_concepts("x", limit=500)
        assert request.await_args.args[1]["limit"] == 100

    @pytest.mark.asyncio
    async def test_synonyms_are_capped(self, adapter):
        hit = {
            "curie": "X:1",
            "label": "x",
            "synonyms": [f"s{i}" for i in range(100)],
            "types": [],
        }
        with mocked(adapter, [hit]):
            (concept,) = await adapter.search_concepts("x")
        assert len(concept.synonyms) == 30
        assert concept.confidence_score == 0.5  # no score -> neutral

    @pytest.mark.asyncio
    async def test_taxa_become_categories_and_hits_without_curie_are_skipped(self, adapter):
        hits = [
            {"label": "no curie"},
            {"curie": "NCBIGene:672", "label": "BRCA1", "taxa": ["NCBITaxon:9606"]},
        ]
        with mocked(adapter, hits):
            concepts = await adapter.search_concepts("brca1")
        assert [c.primary_id for c in concepts] == ["NCBIGene:672"]
        assert concepts[0].categories == ["taxon:NCBITaxon:9606"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query, limit", [("", 5), ("  ", 5), ("x", 0)])
    async def test_empty_inputs(self, adapter, query, limit):
        with mocked(adapter, fx.NAMERES_LOOKUP) as request:
            assert await adapter.search_concepts(query, limit) == []
        request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_errors_and_odd_payloads(self, adapter):
        with mocked(adapter, side_effect=RuntimeError("down")):
            assert await adapter.search_concepts("x") == []
        with mocked(adapter, {"detail": "nope"}):
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_normalized_node(self, adapter):
        with mocked(adapter, fx.NORMALIZED_MONDO) as request:
            concept = await adapter.get_concept_details("mondo:0005404")
        request.assert_awaited_once_with(
            f"{NN}/get_normalized_nodes",
            {"curie": "MONDO:0005404", "conflate": "true", "description": "true"},
        )
        assert concept.primary_id == "MONDO:0005404"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.primary_label == "myalgic encephalomeyelitis/chronic fatigue syndrome"
        assert concept.semantic_types[0] == "Disease" and "NamedThing" in concept.semantic_types
        assert concept.definitions and len(concept.definitions) == 2
        assert "chronic fatigue syndrome" in concept.synonyms  # equivalent-id labels
        idents = {(i.source, i.identifier) for i in concept.identifiers}
        assert (KnowledgeSource.MESH, "D015673") in idents
        assert (KnowledgeSource.UMLS, "C0015674") in idents
        assert concept.source_data[KnowledgeSource.NODENORM]["information_content"] == 100.0

    @pytest.mark.asyncio
    async def test_preferred_id_may_use_another_prefix(self, adapter):
        payload = {"HGNC:1100": fx.NORMALIZED_BATCH["HGNC:1100"]}
        with mocked(adapter, payload):
            concept = await adapter.get_concept_details("hgnc:1100")
        assert concept.primary_id == "NCBIGene:672"
        assert concept.concept_type == ConceptType.GENE

    @pytest.mark.asyncio
    async def test_unknown_curie_and_non_curie(self, adapter):
        with mocked(adapter, {"NOTAREAL:1": None}) as request:
            assert await adapter.get_concept_details("NOTAREAL:1") is None
            assert await adapter.get_concept_details("diabetes") is None
            assert await adapter.get_concept_details("") is None
        assert request.await_count == 1  # only the CURIE-shaped one hit the network

    @pytest.mark.asyncio
    async def test_error_and_bad_payload(self, adapter):
        with mocked(adapter, side_effect=RuntimeError("x")):
            assert await adapter.get_concept_details("MONDO:1") is None
        with mocked(adapter, ["unexpected"]):
            assert await adapter.get_concept_details("MONDO:1") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_equivalent_identifiers(self, adapter):
        with mocked(adapter, fx.NORMALIZED_MONDO):
            mappings = await adapter.get_mappings("mondo:0005404")
        assert mappings[0] == {
            "fromId": "MONDO:0005404",
            "toId": "DOID:8544",
            "fromSource": "NODENORM",
            "toSource": "DOID",
            "mappingType": "equivalent",
            "confidence": 1.0,
            "toLabel": "chronic fatigue syndrome",
        }
        targets = {m["toId"] for m in mappings}
        assert {"MESH:D015673", "UMLS:C0015674", "SNOMEDCT:51771007", "ICD10:G93.32"} <= targets
        assert "MONDO:0005404" not in targets  # the input itself is not a mapping
        unlabeled = next(m for m in mappings if m["toId"] == "MEDDRA:10008874")
        assert "toLabel" not in unlabeled
        assert {m["mappingType"] for m in mappings} == {"equivalent"}

    @pytest.mark.asyncio
    async def test_unknown_input_and_error(self, adapter):
        with mocked(adapter, {"NOTAREAL:1": None}):
            assert await adapter.get_mappings("NOTAREAL:1") == []
        assert await adapter.get_mappings("diabetes") == []
        with mocked(adapter, side_effect=RuntimeError("x")):
            assert await adapter.get_mappings("MONDO:1") == []


class TestNormalizeCuries:
    @pytest.mark.asyncio
    async def test_batch_post_keyed_by_original_input(self, adapter):
        with mocked(adapter, fx.NORMALIZED_BATCH) as request:
            result = await adapter.normalize_curies(
                ["mondo:0005404", "MONDO:0005404", "hgnc:1100", "NOTAREAL:1", "no colon", "BAD:"]
            )
        (call,) = request.await_args_list
        assert call.args == (f"{NN}/get_normalized_nodes",)
        assert call.kwargs["json_data"] == {
            "curies": ["MONDO:0005404", "HGNC:1100", "NOTAREAL:1"],
            "conflate": True,
            "description": False,
        }
        assert set(result) == {
            "mondo:0005404",
            "MONDO:0005404",
            "hgnc:1100",
            "NOTAREAL:1",
            "no colon",
            "BAD:",
        }
        assert result["mondo:0005404"] == result["MONDO:0005404"]
        record = result["MONDO:0005404"]
        assert record["id"] == "MONDO:0005404"
        assert record["type"] == "biolink:Disease"
        assert record["information_content"] == 100.0
        assert {"identifier": "DOID:8544", "label": "chronic fatigue syndrome"} in record[
            "equivalent_identifiers"
        ]
        assert result["hgnc:1100"]["id"] == "NCBIGene:672"
        assert (
            result["NOTAREAL:1"] is None and result["no colon"] is None and result["BAD:"] is None
        )

    @pytest.mark.asyncio
    async def test_description_flag(self, adapter):
        with mocked(adapter, {"MONDO:0005404": fx.NORMALIZED_MONDO["MONDO:0005404"]}) as request:
            result = await adapter.normalize_curies(["MONDO:0005404"], description=True)
        assert request.await_args.kwargs["json_data"]["description"] is True
        assert len(result["MONDO:0005404"]["descriptions"]) == 2

    @pytest.mark.asyncio
    async def test_description_falls_back_to_preferred_id_description(self, adapter):
        node = {
            "id": {"identifier": "X:1", "label": "x", "description": "only here"},
            "equivalent_identifiers": [{"identifier": "X:1", "label": "x", "extra": "dropped"}],
            "type": ["biolink:Gene"],
            "taxa": ["NCBITaxon:9606"],
        }
        with mocked(adapter, {"X:1": node}):
            record = (await adapter.normalize_curies(["X:1"]))["X:1"]
        assert record["descriptions"] == ["only here"]
        assert record["taxa"] == ["NCBITaxon:9606"]
        assert record["equivalent_identifiers"] == [{"identifier": "X:1", "label": "x"}]
        assert record["information_content"] is None

    @pytest.mark.asyncio
    async def test_large_input_is_chunked(self, adapter):
        curies = [f"MONDO:{i:07d}" for i in range(250)]
        with mocked(adapter, {}) as request:
            result = await adapter.normalize_curies(curies)
        assert request.await_count == 3
        sizes = [len(c.kwargs["json_data"]["curies"]) for c in request.await_args_list]
        assert sizes == [100, 100, 50]
        assert len(result) == 250 and all(v is None for v in result.values())

    @pytest.mark.asyncio
    async def test_failed_batch_gives_none_but_other_batches_survive(self, adapter):
        curies = [f"MONDO:{i:07d}" for i in range(150)]
        good = {c: {"id": {"identifier": c, "label": "x"}, "type": []} for c in curies[100:]}
        with mocked(adapter, side_effect=[RuntimeError("boom"), good]):
            result = await adapter.normalize_curies(curies)
        assert result[curies[0]] is None
        assert result[curies[120]]["id"] == curies[120]

    @pytest.mark.asyncio
    async def test_empty_and_non_string_inputs(self, adapter):
        with mocked(adapter, {}) as request:
            assert await adapter.normalize_curies([]) == {}
            assert await adapter.normalize_curies([None, 5]) == {}  # type: ignore[list-item]
        request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_dict_response_is_ignored(self, adapter):
        with mocked(adapter, ["unexpected"]):
            assert await adapter.normalize_curies(["MONDO:1"]) == {"MONDO:1": None}


class TestBulkLookup:
    @pytest.mark.asyncio
    async def test_bulk_lookup(self, adapter):
        with mocked(adapter, fx.NAMERES_BULK) as request:
            result = await adapter.bulk_lookup(["chronic fatigue syndrome", "long covid", " "], 2)
        request.assert_awaited_once_with(
            f"{NR}/bulk-lookup",
            json_data={"strings": ["chronic fatigue syndrome", "long covid"], "limit": 2},
        )
        assert result["long covid"][0]["curie"] == "MONDO:0100233"
        assert result["long covid"][0]["label"] == "long COVID-19"
        assert result["long covid"][0]["types"][0] == "biolink:Disease"
        assert set(result["chronic fatigue syndrome"][0]) == {"curie", "label", "types", "score"}

    @pytest.mark.asyncio
    async def test_missing_names_give_empty_lists(self, adapter):
        with mocked(adapter, {"known": [{"curie": "A:1", "label": "a"}], "unknown": []}):
            result = await adapter.bulk_lookup(["known", "unknown", "absent"])
        assert result["known"][0]["curie"] == "A:1"
        assert result["unknown"] == [] and result["absent"] == []

    @pytest.mark.asyncio
    async def test_empty_error_and_bad_payload(self, adapter):
        with mocked(adapter, {}) as request:
            assert await adapter.bulk_lookup([]) == {}
            assert await adapter.bulk_lookup(["x"], limit=0) == {}
        request.assert_not_awaited()
        with mocked(adapter, side_effect=RuntimeError("x")):
            assert await adapter.bulk_lookup(["x"]) == {}
        with mocked(adapter, ["unexpected"]):
            assert await adapter.bulk_lookup(["x"]) == {}
