"""
Unit tests for MonarchAdapter (Monarch Initiative API v3), driven by trimmed real responses.
"""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from knowledge_lookup.adapters.monarch_adapter import MonarchAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import monarch_responses as fx

pytestmark = pytest.mark.unit

BASE = "https://api-v3.monarchinitiative.org/v3/api"


def _not_found() -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=404)


def _empty(items=None):
    return {"limit": 20, "offset": 0, "total": len(items or []), "items": items or []}


class FakeMonarch:
    """Dispatches ``_make_request`` calls to fixture data and records them."""

    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []
        self.entities = {
            "MONDO:0005404": fx.ENTITY_DISEASE_MECFS,
            "HGNC:1100": fx.ENTITY_GENE_BRCA1,
        }
        self.assoc = {
            "biolink:DiseaseToPhenotypicFeatureAssociation": fx.ASSOC_DISEASE_TO_PHENOTYPE,
            "biolink:CausalGeneToDiseaseAssociation": fx.ASSOC_CAUSAL_GENE_DISEASE,
            "biolink:CorrelatedGeneToDiseaseAssociation": fx.ASSOC_CORRELATED_GENE_DISEASE,
            "biolink:GeneToGeneHomologyAssociation": fx.ASSOC_HOMOLOGY,
            "biolink:VariantToDiseaseAssociation": fx.ASSOC_VARIANT,
        }
        self.search_results = _empty()

    async def request(self, url, params=None, headers=None, json_data=None):
        self.calls.append((url, params))
        path = url.removeprefix(BASE)
        if path.startswith("/entity/"):
            entity = self.entities.get(path.removeprefix("/entity/"))
            if entity is None:
                raise _not_found()
            return entity
        if path == "/search":
            return self.search_results
        if path == "/association":
            return self.assoc.get(params["category"], _empty())
        raise AssertionError(f"unexpected URL {url}")

    def association_calls(self):
        return [p for u, p in self.calls if u.endswith("/association")]


@pytest.fixture
def adapter(lookup_config):
    return MonarchAdapter(lookup_config)


@pytest.fixture
def fake(adapter):
    fake = FakeMonarch()
    with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake.request)):
        yield fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.MONARCH
        assert adapter.source == KnowledgeSource.MONARCH
        assert adapter.is_available() is True
        assert adapter.base_url == BASE

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("hp:0012432", "HP:0012432"),
            ("hgnc:1100", "HGNC:1100"),
            ("ncbigene:672", "NCBIGene:672"),
            ("omim:154700", "OMIM:154700"),
            ("ORPHA:558", "Orphanet:558"),
            ("orphanet:558", "Orphanet:558"),
            ("MONDO:0005148", "MONDO:0005148"),
            ("zzz:1", "ZZZ:1"),
            ("BRCA1", None),
            ("", None),
            (":1", None),
        ],
    )
    def test_normalize_curie(self, raw, expected):
        assert MonarchAdapter._normalize_curie(raw) == expected


class TestSearch:
    @pytest.mark.asyncio
    async def test_merges_diseases_and_human_genes_by_score(self, adapter, fake):
        gene_hits = copy.deepcopy(fx.SEARCH_HUMAN_GENE)
        disease_hits = copy.deepcopy(fx.SEARCH_DISEASE_PHENOTYPE)
        responses = iter([disease_hits, gene_hits])

        async def route(url, params=None, headers=None, json_data=None):
            fake.calls.append((url, params))
            return next(responses)

        adapter._make_request.side_effect = route
        concepts = await adapter.search_concepts("brca1", limit=10)

        scores = [c.confidence_score for c in concepts]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 1.0
        ids = [c.primary_id for c in concepts]
        assert "HGNC:1100" in ids and "MONDO:0005404" in ids and "HP:0012432" in ids
        types = {c.primary_id: c.concept_type for c in concepts}
        assert types["HGNC:1100"] == ConceptType.GENE
        assert types["MONDO:0005404"] == ConceptType.DISEASE
        assert types["HP:0012432"] == ConceptType.PHENOTYPE

        (_, disease_params), (_, gene_params) = fake.calls
        assert disease_params["category"] == ["biolink:Disease", "biolink:PhenotypicFeature"]
        assert "in_taxon_label" not in disease_params
        assert gene_params["category"] == ["biolink:Gene"]
        assert gene_params["in_taxon_label"] == "Homo sapiens"

    @pytest.mark.asyncio
    async def test_gene_concept_fields(self, adapter, fake):
        fake.search_results = fx.SEARCH_HUMAN_GENE
        concepts = await adapter.search_concepts("BRCA1", limit=5)
        brca1 = next(c for c in concepts if c.primary_id == "HGNC:1100")
        assert brca1.primary_label == "BRCA1"
        assert "BRCA1 DNA repair associated" in brca1.synonyms
        assert "RNF53" in brca1.synonyms
        assert "BRCA1" not in brca1.synonyms  # the label itself is not repeated
        assert "taxon:Homo sapiens" in brca1.categories
        assert brca1.semantic_types == ["Gene"]
        sources = {(i.source, i.identifier) for i in brca1.identifiers}
        assert (KnowledgeSource.OMIM, "OMIM:113705") in sources
        assert (KnowledgeSource.ENSEMBL, "ENSG00000012048") in sources
        assert KnowledgeSource.MONARCH in brca1.sources

    @pytest.mark.asyncio
    async def test_can_include_non_human_genes(self, adapter, fake):
        adapter.human_genes_only = False
        await adapter.search_concepts("BRCA1")
        gene_params = fake.calls[1][1]
        assert "in_taxon_label" not in gene_params

    @pytest.mark.asyncio
    async def test_limit_and_dedup(self, adapter, fake):
        fake.search_results = fx.SEARCH_DISEASE_PHENOTYPE  # same hits returned for both calls
        concepts = await adapter.search_concepts("fatigue", limit=2)
        assert len(concepts) == 2
        assert len({c.primary_id for c in concepts}) == 2
        assert fake.calls[0][1]["limit"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query, limit", [("", 5), ("   ", 5), ("x", 0)])
    async def test_empty_query_or_limit(self, adapter, fake, query, limit):
        assert await adapter.search_concepts(query, limit) == []
        assert fake.calls == []

    @pytest.mark.asyncio
    async def test_skips_hits_without_id_or_name_and_handles_zero_scores(self, adapter, fake):
        fake.search_results = _empty(
            [{"id": "X:1", "category": "biolink:Disease"}, {"id": "X:2", "name": "ok"}]
        )
        concepts = await adapter.search_concepts("x")
        assert [c.primary_id for c in concepts] == ["X:2"]
        assert concepts[0].confidence_score == 0.5  # no scores at all -> neutral

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("down"))):
            assert await adapter.search_concepts("BRCA1") == []

    @pytest.mark.asyncio
    async def test_unexpected_payload_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=["not", "a", "dict"])):
            assert await adapter.search_concepts("BRCA1") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_disease_details(self, adapter, fake):
        concept = await adapter.get_concept_details("MONDO:0005404")
        assert concept.primary_id == "MONDO:0005404"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.confidence_score == 1.0
        assert concept.definitions and "long-term fatigue" in concept.definitions[0]
        assert "chronic fatigue syndrome" in concept.synonyms
        assert "CFS" in concept.synonyms
        assert concept.parents == ["MONDO:0002254", "MONDO:0003939"]
        assert concept.children == []
        idents = {(i.source, i.identifier) for i in concept.identifiers}
        assert (KnowledgeSource.MESH, "D015673") in idents
        assert (KnowledgeSource.UMLS, "C0015674") in idents
        data = concept.source_data[KnowledgeSource.MONARCH]
        assert data["association_counts"] == {"DiseaseToPhenotypicFeatureAssociation": 1}
        assert not any("closure" in key for key in data)
        assert "node_hierarchy" not in data

    @pytest.mark.asyncio
    async def test_lowercase_prefix_is_canonicalised(self, adapter, fake):
        concept = await adapter.get_concept_details("mondo:0005404")
        assert concept.primary_id == "MONDO:0005404"
        assert fake.calls[0][0] == f"{BASE}/entity/MONDO:0005404"

    @pytest.mark.asyncio
    async def test_omim_resolved_through_xref_search(self, adapter, fake):
        fake.search_results = _empty(
            [
                {"id": "MONDO:0000001", "xref": ["OMIM:999999"]},
                {"id": "HGNC:1100", "xref": ["ENSEMBL:ENSG00000012048", "OMIM:113705"]},
            ]
        )
        concept = await adapter.get_concept_details("omim:113705")
        assert concept.primary_id == "HGNC:1100"
        assert concept.concept_type == ConceptType.GENE
        urls = [u for u, _ in fake.calls]
        assert urls == [f"{BASE}/search", f"{BASE}/entity/HGNC:1100"]  # no wasted /entity/OMIM

    @pytest.mark.asyncio
    async def test_xref_search_ignores_unrelated_text_hits(self, adapter, fake):
        fake.search_results = _empty([{"id": "MONDO:0000001", "xref": ["OMIM:1"], "name": "x"}])
        assert await adapter.get_concept_details("OMIM:113705") is None

    @pytest.mark.asyncio
    async def test_falls_back_to_xref_when_entity_404s(self, adapter, fake):
        fake.search_results = _empty([{"id": "HGNC:1100", "xref": ["NCBIGene:672"]}])
        concept = await adapter.get_concept_details("NCBIGene:672")
        assert concept.primary_id == "HGNC:1100"

    @pytest.mark.asyncio
    async def test_unknown_id_and_non_curie(self, adapter, fake):
        assert await adapter.get_concept_details("NCBIGene:672") is None  # 404, no xref hit
        assert await adapter.get_concept_details("BRCA1") is None
        assert await adapter.get_concept_details("") is None

    @pytest.mark.asyncio
    async def test_non_404_error_returns_none(self, adapter):
        boom = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=500)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=boom)):
            assert await adapter.get_concept_details("MONDO:0005404") is None

    @pytest.mark.asyncio
    async def test_entity_without_name_is_rejected(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"id": "MONDO:1"})):
            assert await adapter.get_concept_details("MONDO:1") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_xrefs_and_mappings_deduplicated(self, adapter, fake):
        mappings = await adapter.get_mappings("MONDO:0005404")
        targets = [m["toId"] for m in mappings]
        assert len(targets) == len(set(targets))
        assert {"MESH:D015673", "UMLS:C0015674", "Orphanet:1983", "ICD9:780.71"} <= set(targets)
        assert "MONDO:0005404" not in targets
        sample = next(m for m in mappings if m["toId"] == "MESH:D015673")
        assert sample == {
            "fromId": "MONDO:0005404",
            "toId": "MESH:D015673",
            "fromSource": "MONARCH",
            "toSource": "MESH",
            "mappingType": "xref",
            "confidence": 0.9,
        }

    @pytest.mark.asyncio
    async def test_same_as_and_invalid_targets(self, adapter):
        entity = {
            "id": "MONDO:1",
            "name": "x",
            "xref": ["notacurie", "A:1"],
            "same_as": ["B:2"],
            "mappings": [{"id": "A:1"}, {"url": "x"}],
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=entity)):
            mappings = await adapter.get_mappings("MONDO:1")
        assert [m["toId"] for m in mappings] == ["A:1", "B:2"]

    @pytest.mark.asyncio
    async def test_unknown_and_error(self, adapter, fake):
        assert await adapter.get_mappings("BRCA1") == []
        assert await adapter.get_mappings("NCBIGene:672") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("MONDO:0005404") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_gene_relationships(self, adapter, fake):
        rels = await adapter.get_relationships("HGNC:1100", limit=5)
        labels = {r["relation_label"] for r in rels}
        assert {"causes", "gene_associated_with_condition", "orthologous_to"} <= labels
        # gene -> phenotype fixture is the disease table, so only check the typed edges
        causes = next(r for r in rels if r["relation_label"] == "causes")
        assert causes["related_id"] == "MONDO:0054748"
        assert causes["related_name"] == "Fanconi anemia, complementation group S"
        assert causes["source"] == "MONARCH"
        assert causes["direction"] == "outgoing"
        assert causes["primary_source"] == "infores:omim"
        ortholog = next(r for r in rels if r["relation_label"] == "orthologous_to")
        assert ortholog["species"] == "Sus scrofa"
        assert ortholog["related_category"] == "biolink:Gene"
        # HGNC prefix implies Gene: no /entity round-trip, and one call per association category
        assert not any("/entity/" in u for u, _ in fake.calls)
        categories = [p["category"] for p in fake.association_calls()]
        assert categories == [
            "biolink:GeneToPhenotypicFeatureAssociation",
            "biolink:CausalGeneToDiseaseAssociation",
            "biolink:CorrelatedGeneToDiseaseAssociation",
            "biolink:GeneToGeneHomologyAssociation",
        ]
        assert all(
            p["subject"] == "HGNC:1100" and p["limit"] == 5 for p in fake.association_calls()
        )

    @pytest.mark.asyncio
    async def test_disease_phenotypes_carry_frequency_qualifiers(self, adapter, fake):
        rels = await adapter.get_relationships("MONDO:0007947", limit=10)
        phenos = {r["related_id"]: r for r in rels if r["relation_label"] == "has_phenotype"}

        term = phenos["HP:0000768"]
        assert term["frequency"] == 0.9
        assert term["frequency_label"] == "Very frequent"
        assert term["frequency_term"] == "HP:0040281"
        assert term["evidence"] == ["ECO:0000304"]
        assert term["primary_source"] == "infores:orphanet"

        observed = phenos["HP:0003179"]
        assert observed["frequency"] == pytest.approx(0.4795, abs=1e-4)
        assert observed["frequency_count"] == 140 and observed["frequency_total"] == 292
        assert observed["frequency_label"] == "140/292"
        assert observed["publications"] == ["PMID:28050285", "PMID:26339165"]
        assert "onset" not in observed  # absent qualifiers are not emitted as empty keys

    @pytest.mark.asyncio
    async def test_disease_genes_variants_and_inverse_labels(self, adapter, fake):
        rels = await adapter.get_relationships("MONDO:0007947", limit=3)
        by_label = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)
        assert by_label["caused_by"][0]["direction"] == "incoming"
        assert "condition_associated_with_gene" in by_label
        variant_call = next(p for p in fake.association_calls() if "Variant" in p["category"])
        assert variant_call["limit"] == 3  # min(cap of 5, limit)
        gene_calls = [p for p in fake.association_calls() if "GeneToDisease" in p["category"]]
        assert all(p["object"] == "MONDO:0007947" for p in gene_calls)

    @pytest.mark.asyncio
    async def test_variant_cap_is_five(self, adapter, fake):
        await adapter.get_relationships("MONDO:0007947", limit=50)
        variant_call = next(p for p in fake.association_calls() if "Variant" in p["category"])
        assert variant_call["limit"] == 5

    @pytest.mark.asyncio
    async def test_phenotype_relationships(self, adapter, fake):
        fake.assoc["biolink:DiseaseToPhenotypicFeatureAssociation"] = fx.ASSOC_HP_DISEASES
        fake.assoc["biolink:GeneToPhenotypicFeatureAssociation"] = fx.ASSOC_HP_GENES
        rels = await adapter.get_relationships("hp:0012432")
        assert {r["relation_label"] for r in rels} == {"phenotype_of"}
        assert {r["related_category"] for r in rels} == {"biolink:Disease", "biolink:Gene"}
        assert all(p["object"] == "HP:0012432" for p in fake.association_calls())

    @pytest.mark.asyncio
    async def test_duplicates_are_merged(self, adapter, fake):
        doubled = copy.deepcopy(fx.ASSOC_CAUSAL_GENE_DISEASE)
        doubled["items"] = doubled["items"] * 2
        fake.assoc["biolink:CausalGeneToDiseaseAssociation"] = doubled
        rels = await adapter.get_relationships("HGNC:1100")
        assert len([r for r in rels if r["relation_label"] == "causes"]) == 1

    @pytest.mark.asyncio
    async def test_negated_association_gets_not_prefix(self, adapter, fake):
        negated = copy.deepcopy(fx.ASSOC_DISEASE_TO_PHENOTYPE)
        negated["items"][0]["negated"] = True
        fake.assoc["biolink:DiseaseToPhenotypicFeatureAssociation"] = negated
        rels = await adapter.get_relationships("MONDO:0007947")
        assert any(r["relation_label"] == "not_has_phenotype" for r in rels)

    @pytest.mark.asyncio
    async def test_onset_and_sex_qualifiers(self, adapter, fake):
        data = copy.deepcopy(fx.ASSOC_DISEASE_TO_PHENOTYPE)
        data["items"][0].update(
            {
                "onset_qualifier": "HP:0003593",
                "onset_qualifier_label": "Infantile onset",
                "sex_qualifier_label": "female",
            }
        )
        fake.assoc["biolink:DiseaseToPhenotypicFeatureAssociation"] = data
        rels = await adapter.get_relationships("MONDO:0007947")
        edge = next(r for r in rels if r["related_id"] == "HP:0000768")
        assert edge["onset"] == "Infantile onset" and edge["onset_id"] == "HP:0003593"
        assert edge["sex"] == "female"

    @pytest.mark.asyncio
    async def test_omim_id_resolves_category_via_search(self, adapter, fake):
        fake.search_results = _empty([{"id": "MONDO:0005404", "xref": ["OMIM:999"]}])
        rels = await adapter.get_relationships("OMIM:999", limit=2)
        assert rels  # disease plan was used
        assert fake.association_calls()[0]["subject"] == "MONDO:0005404"

    @pytest.mark.asyncio
    async def test_unsupported_category_and_bad_input(self, adapter, fake):
        fake.entities["CL:0000001"] = {
            "id": "CL:0000001",
            "name": "cell",
            "category": "biolink:Cell",
        }
        assert await adapter.get_relationships("CL:0000001") == []
        assert await adapter.get_relationships("nonsense") == []
        assert await adapter.get_relationships("OMIM:404") == []
        assert await adapter.get_relationships("HGNC:1100", limit=0) == []

    @pytest.mark.asyncio
    async def test_association_without_related_id_is_skipped(self, adapter):
        assert adapter._convert_association({"predicate": "biolink:causes"}, "subject") is None

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("HGNC:1100") == []


class TestFrequencySelection:
    def test_prefers_observed_quotient_then_percentage_then_term(self, adapter):
        both = {
            "has_quotient": 0.5,
            "has_count": 1,
            "has_total": 2,
            "frequency_qualifier": "HP:0040281",
        }
        freq = adapter._association_frequency(both)
        assert freq.fraction == 0.5 and freq.label == "1/2" and freq.term == "HP:0040281"

        pct_only = adapter._association_frequency({"has_percentage": 25.0})
        assert pct_only.fraction == 0.25 and pct_only.label == "25%"

        term_only = adapter._association_frequency(
            {"frequency_qualifier": "HP:0040283", "frequency_qualifier_label": "Occasional"}
        )
        assert term_only.fraction == 0.17 and term_only.label == "Occasional"

        assert adapter._association_frequency({}) is None
