"""
Unit tests for ClinPGxAdapter (HTTP mocked with trimmed real ClinPGx responses).
"""

import time
from unittest.mock import AsyncMock

import pytest

from knowledge_lookup.adapters.clinpgx_adapter import (
    CLINPGX_BASE_URL,
    ClinPGxAdapter,
    _evidence_rank,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import clinpgx_responses as fx

pytestmark = pytest.mark.unit


class NotFound(Exception):
    """Stands in for aiohttp.ClientResponseError (the base class reads ``.status``)."""

    status = 404


def _router(overrides=None):
    """``_make_request`` replacement routing by path and params (real fixtures)."""
    overrides = overrides or {}

    async def fake(url, params=None, headers=None, json_data=None):
        assert url.startswith(CLINPGX_BASE_URL + "/")
        path = url[len(CLINPGX_BASE_URL) + 1 :]
        params = params or {}
        key = (path, tuple(sorted(params.items())))
        for k in (key, path):
            if k in overrides:
                value = overrides[k]
                if isinstance(value, Exception):
                    raise value
                return value
        if path == "gene" and params.get("symbol") == "CYP2D6":
            return fx.GENE_SEARCH
        if path == "chemical" and params.get("name") == "codeine":
            return fx.CHEMICAL_SEARCH
        if path == "variant" and params.get("symbol") == "rs3892097":
            return fx.VARIANT_SEARCH
        if path == "haplotype" and params.get("symbol") == "CYP2D6*4":
            return fx.HAPLOTYPE_SEARCH
        if path == "haplotype" and params.get("gene.symbol") == "CYP2D6":
            return fx.HAPLOTYPES_OF_GENE
        if path == "gene/PA128":
            return fx.GENE_MAX if params.get("view") == "max" else fx.GENE_MIN
        if path == "chemical/PA449088":
            return fx.CHEMICAL_MAX if params.get("view") == "max" else fx.CHEMICAL_MIN
        if path == "variant/PA166156104":
            return fx.VARIANT_MAX
        if path == "haplotype/PA165816579":
            return fx.HAPLOTYPE_SEARCH
        if path == "clinicalAnnotation":
            if params.get("location.genes.symbol") == "CYP2D6":
                return fx.CLINICAL_ANNOTATIONS_GENE
            if params.get("relatedChemicals.name") == "codeine":
                return fx.CLINICAL_ANNOTATIONS_CHEMICAL
        if path == "guidelineAnnotation":
            if params.get("relatedGenes.symbol") == "CYP2D6":
                return fx.GUIDELINES_GENE
            if params.get("relatedChemicals.name") == "codeine":
                return fx.GUIDELINES_CHEMICAL
        if path == "drugLabel" and params.get("relatedChemicals.name") == "codeine":
            return fx.DRUG_LABELS_CHEMICAL
        raise NotFound(path)  # the real API answers 404 "No results matching criteria."

    return AsyncMock(side_effect=fake)


@pytest.fixture
def adapter(lookup_config):
    a = ClinPGxAdapter(lookup_config)
    a._last_request = float("-inf")
    return a


def _patch(adapter, router):
    adapter._make_request = router
    return router


def _paths(router):
    return [c.args[0][len(CLINPGX_BASE_URL) + 1 :] for c in router.call_args_list]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CLINPGX
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("PA128", "PA128"),
            ("pa128", "PA128"),
            (" CLINPGX:PA128 ", "PA128"),
            ("PharmGKB : PA449088", "PA449088"),
            ("CYP2D6", None),
            ("PA", None),
            ("PA12x", None),
            ("", None),
            (None, None),
            (128, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert ClinPGxAdapter.normalize_id(raw) == expected

    @pytest.mark.parametrize(
        "pa_id,first",
        [("PA128", "gene"), ("PA449088", "chemical"), ("PA166156104", "variant")],
    )
    def test_probe_order_guesses_kind(self, pa_id, first):
        order = ClinPGxAdapter._probe_order(pa_id)
        assert order[0] == first
        assert sorted(order) == ["chemical", "gene", "haplotype", "variant"]

    def test_evidence_rank(self):
        assert _evidence_rank("1A") < _evidence_rank("2B") < _evidence_rank("4")
        assert _evidence_rank("") == _evidence_rank("unknown") == 6


@pytest.mark.asyncio
class TestSearch:
    async def test_gene_symbol_any_case(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("cyp2d6")
        assert [(c.primary_id, c.primary_label) for c in result] == [("PA128", "CYP2D6")]
        c = result[0]
        assert c.concept_type == ConceptType.GENE
        assert "cytochrome P450 family 2 subfamily D member 6" in c.synonyms
        # symbol is exact and case sensitive: the upper-case spelling is tried first
        assert router.call_args_list[0].args[1] == {"symbol": "CYP2D6"}
        # a gene hit makes the chemical lookups unnecessary
        assert _paths(router) == ["gene"]

    async def test_gene_as_typed_after_upper_case_miss(self, adapter):
        gene = {"data": [{"objCls": "Gene", "id": "PA1", "symbol": "C10orf2", "name": "n"}]}
        router = _patch(adapter, _router({("gene", (("symbol", "C10orf2"),)): gene}))
        result = await adapter.search_concepts("C10orf2")
        assert [c.primary_id for c in result] == ["PA1"]
        assert [c.args[1]["symbol"] for c in router.call_args_list] == ["C10ORF2", "C10orf2"]

    async def test_drug_name_any_case(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("Codeine")
        assert [(c.primary_id, c.primary_label) for c in result] == [("PA449088", "codeine")]
        assert result[0].concept_type == ConceptType.DRUG
        assert "Prodrug" in result[0].categories
        assert _paths(router) == ["gene", "gene", "chemical"]  # codeine matched lower-case

    async def test_drug_name_as_typed(self, adapter):
        chem = {"data": [{"objCls": "Chemical", "id": "PA9", "name": "Odd-Name", "types": []}]}
        _patch(adapter, _router({("chemical", (("name", "Odd-Name"),)): chem}))
        result = await adapter.search_concepts("Odd-Name")
        assert [c.primary_id for c in result] == ["PA9"]

    async def test_rsid_goes_to_variants_only(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("RS3892097")
        assert [(c.primary_id, c.primary_label) for c in result] == [("PA166156104", "rs3892097")]
        assert result[0].concept_type == ConceptType.MOLECULAR_ENTITY
        assert _paths(router) == ["variant"]
        assert router.call_args_list[0].args[1] == {"symbol": "rs3892097"}

    async def test_star_allele_goes_to_haplotypes_only(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("cyp2d6*4")
        assert [(c.primary_id, c.primary_label) for c in result] == [("PA165816579", "CYP2D6*4")]
        assert _paths(router) == ["haplotype"]

    async def test_pa_id_query(self, adapter):
        _patch(adapter, _router())
        result = await adapter.search_concepts("CLINPGX:PA128")
        assert [c.primary_id for c in result] == ["PA128"]

    async def test_unknown_pa_id_query(self, adapter):
        _patch(adapter, _router())
        assert await adapter.search_concepts("PA999") == []

    async def test_no_match_returns_empty(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.search_concepts("paracetamol") == []  # synonyms do not match
        assert _paths(router) == ["gene", "gene", "chemical"]  # lower case == as typed

    async def test_limit_and_blank(self, adapter):
        router = _patch(adapter, _router())
        both = {"data": fx.GENE_SEARCH["data"] * 3, "status": "success"}
        _patch(adapter, _router({("gene", (("symbol", "CYP2D6"),)): both}))
        assert len(await adapter.search_concepts("CYP2D6", limit=2)) == 2
        router = _patch(adapter, _router())
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts("CYP2D6", limit=0) == []
        router.assert_not_called()

    async def test_rows_without_id_are_skipped(self, adapter):
        _patch(adapter, _router({("gene", (("symbol", "CYP2D6"),)): {"data": [{"symbol": "X"}]}}))
        assert await adapter.search_concepts("CYP2D6") == []

    async def test_error_returns_empty(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.search_concepts("CYP2D6") == []

    async def test_non_json_shape_returns_empty(self, adapter):
        _patch(adapter, AsyncMock(return_value=["unexpected"]))
        assert await adapter.search_concepts("CYP2D6") == []
        _patch(adapter, AsyncMock(return_value={"data": "oops"}))
        assert await adapter.search_concepts("CYP2D6") == []


@pytest.mark.asyncio
class TestDetails:
    async def test_gene(self, adapter):
        _patch(adapter, _router())
        c = await adapter.get_concept_details("PA128")
        assert c.primary_label == "CYP2D6"
        assert c.concept_type == ConceptType.GENE
        assert "CPIC gene" in c.categories and "VIP Tier 1" in c.categories
        assert "CPD6" in c.synonyms
        assert c.definitions and "key pharmacogenes" in c.definitions[0]
        assert "<" not in c.definitions[0] and len(c.definitions[0]) <= 600
        ids = {(i.source, i.identifier) for i in c.identifiers}
        assert (KnowledgeSource.HGNC, "HGNC:2625") in ids
        assert (KnowledgeSource.ENSEMBL, "ENSG00000100197") in ids
        assert (KnowledgeSource.NCBI, "1565") in ids
        data = c.source_data[KnowledgeSource.CLINPGX]
        assert data["kind"] == "gene" and "CC BY-SA 4.0" in data["license"]
        assert data["cpicGene"] is True
        assert "vipSummary" not in data  # nested/bulky fields are not copied

    async def test_chemical(self, adapter):
        _patch(adapter, _router())
        c = await adapter.get_concept_details("CLINPGX:PA449088")
        assert c.primary_label == "codeine" and c.concept_type == ConceptType.DRUG
        assert "Codicept" in c.synonyms  # trade names
        ids = {(i.source, i.identifier) for i in c.identifiers}
        assert (KnowledgeSource.DRUGBANK, "DB00318") in ids
        assert (KnowledgeSource.RXNORM, "2670") in ids

    async def test_variant_and_haplotype(self, adapter):
        router = _patch(adapter, _router())
        v = await adapter.get_concept_details("PA166156104")
        assert v.primary_label == "rs3892097"
        assert {(i.source, i.identifier) for i in v.identifiers} >= {
            (KnowledgeSource.DBSNP, "rs3892097"),
            (KnowledgeSource.CLINVAR, "16889"),
        }
        # variant ids probe the variant endpoint first
        assert _paths(router)[0] == "variant/PA166156104"
        h = await adapter.get_concept_details("PA165816579")
        assert h.primary_label == "CYP2D6*4"

    async def test_kind_is_remembered(self, adapter):
        router = _patch(adapter, _router())
        await adapter.get_concept_details("PA128")
        await adapter.get_concept_details("PA128")
        assert _paths(router) == ["gene/PA128", "gene/PA128"]

    async def test_probes_other_kinds_on_miss(self, adapter):
        router = _patch(adapter, _router())
        # PA449088 < 1e6 probes the chemical first; gene-sized ids probe gene first and fall through
        await adapter.get_concept_details("PA449088")
        assert _paths(router) == ["chemical/PA449088"]
        router.reset_mock()
        adapter._kinds.clear()
        assert await adapter.get_concept_details("PA128") is not None
        assert _paths(router) == ["gene/PA128"]

    async def test_unknown_id_probes_all_kinds(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_concept_details("PA7") is None
        assert _paths(router) == [
            "gene/PA7",
            "chemical/PA7",
            "variant/PA7",
            "haplotype/PA7",
        ]

    async def test_invalid_id_makes_no_request(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_concept_details("CYP2D6") is None
        router.assert_not_called()

    async def test_error(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_concept_details("PA128") is None


@pytest.mark.asyncio
class TestRelationships:
    async def test_gene(self, adapter):
        router = _patch(adapter, _router())
        rels = await adapter.get_relationships("PA128")
        assert _paths(router) == [
            "gene/PA128",
            "clinicalAnnotation",
            "guidelineAnnotation",
            "haplotype",
        ]
        assert router.call_args_list[1].args[1] == {
            "location.genes.symbol": "CYP2D6",
            "view": "min",
        }
        labels = {r["relation_label"] for r in rels}
        assert labels == {"has_clinical_annotation", "has_guideline", "has_haplotype"}
        for r in rels:
            assert r["source"] == "ClinPGx" and r["related_id"] and r["related_name"]

        clin = {
            r["related_name"]: r for r in rels if r["relation_label"] == "has_clinical_annotation"
        }
        assert set(clin) == {"tramadol", "amitriptyline", "codeine"}
        # best level wins, categories are merged over all annotations of the pair
        assert clin["codeine"]["level_of_evidence"] == "1A"
        assert clin["codeine"]["phenotype_categories"] == ["Efficacy", "Toxicity"]
        assert clin["codeine"]["annotation_count"] == 2
        assert len(clin["codeine"]["annotation_ids"]) == 2
        assert clin["tramadol"]["level_of_evidence"] == "1A"
        assert clin["amitriptyline"]["phenotype_categories"] == ["Metabolism/PK", "Toxicity"]

        guides = [r for r in rels if r["relation_label"] == "has_guideline"]
        assert guides[0]["guideline_source"] == "CPIC"  # CPIC before DPWG/CPNDS
        assert {g["guideline_source"] for g in guides} == {"CPIC", "DPWG", "CPNDS"}
        cpic = guides[0]
        assert cpic["guideline_name"].startswith("Annotation of CPIC Clinical Guideline")
        assert cpic["guideline_id"].startswith("PA")
        assert isinstance(cpic["dosing_information"], bool)

        haps = [r for r in rels if r["relation_label"] == "has_haplotype"]
        assert len(haps) == 3 and haps[0]["related_name"].startswith("CYP2D6*")
        assert haps[0]["reference_allele"] is False

    async def test_clinical_annotations_sorted_by_evidence(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships("PA128")
        clin = [r for r in rels if r["relation_label"] == "has_clinical_annotation"]
        ranks = [_evidence_rank(r["level_of_evidence"]) for r in clin]
        assert ranks == sorted(ranks)

    async def test_limit_caps_each_label(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships("PA128", limit=1)
        counts: dict[str, int] = {}
        for r in rels:
            counts[r["relation_label"]] = counts.get(r["relation_label"], 0) + 1
        assert counts == {"has_clinical_annotation": 1, "has_guideline": 1, "has_haplotype": 1}

    async def test_chemical(self, adapter):
        router = _patch(adapter, _router())
        rels = await adapter.get_relationships("CLINPGX:PA449088")
        assert "drugLabel" in _paths(router)
        assert router.call_args_list[1].args[1] == {
            "relatedChemicals.name": "codeine",
            "view": "min",
        }
        by_label: dict[str, list[dict]] = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)
        assert set(by_label) == {"has_clinical_annotation", "has_guideline", "has_label"}
        genes = {r["related_name"]: r for r in by_label["has_clinical_annotation"]}
        assert genes["CYP2D6"]["level_of_evidence"] == "1A"
        assert genes["UGT2B7"]["level_of_evidence"] == "3"
        assert {g["related_name"] for g in by_label["has_guideline"]} == {"CYP2D6"}
        labels = {r["label_source"]: r for r in by_label["has_label"]}
        assert labels["FDA"]["testing_level"] == "Actionable PGx"
        assert labels["FDA"]["prescribing_genes"] == ["CYP2D6"]
        assert labels["FDA"]["biomarker_status"] == "On FDA Biomarker List"
        assert labels["FDA"]["related_id"].startswith("PA")

    async def test_haplotype_and_variant(self, adapter):
        _patch(adapter, _router())
        hap = await adapter.get_relationships("PA165816579")
        assert [(r["relation_label"], r["related_id"], r["related_name"]) for r in hap] == [
            ("haplotype_of", "PA128", "CYP2D6")
        ]
        var = await adapter.get_relationships("PA166156104")
        assert [(r["relation_label"], r["related_id"]) for r in var] == [
            ("located_in_gene", "PA128")
        ]

    async def test_missing_gene_link_is_dropped(self, adapter):
        hap = {"data": {"objCls": "StarAllele", "id": "PA165816579", "symbol": "X*1"}}
        _patch(adapter, _router({"haplotype/PA165816579": hap}))
        assert await adapter.get_relationships("PA165816579") == []

    async def test_unknown_and_invalid(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_relationships("PA7") == []
        assert await adapter.get_relationships("CYP2D6") == []
        assert await adapter.get_relationships("PA128", limit=0) == []
        assert router.call_count == 4  # only the four probes of the unknown PA7

    async def test_objects_without_name_make_no_annotation_requests(self, adapter):
        nameless = {"data": {"objCls": "Gene", "id": "PA128"}, "status": "success"}
        router = _patch(adapter, _router({"gene/PA128": nameless}))
        assert await adapter.get_relationships("PA128") == []
        assert _paths(router) == ["gene/PA128"]
        chem = {"data": {"objCls": "Chemical", "id": "PA449088"}, "status": "success"}
        router = _patch(adapter, _router({"chemical/PA449088": chem}))
        assert await adapter.get_relationships("PA449088") == []

    async def test_error(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_relationships("PA128") == []


@pytest.mark.asyncio
class TestMappings:
    async def test_gene(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings("PA128")
        got = {(m["toSource"], m["toId"]) for m in maps}
        assert {
            ("HGNC", "HGNC:2625"),
            ("ENSEMBL", "ENSG00000100197"),
            ("NCBI", "1565"),
            ("UNIPROT", "Q6NWU0"),
            ("OMIM", "124030"),
            ("CTD", "1565"),
        } <= got
        # references to things that are not the same entity are not mapped
        assert not any(m["toSource"] in {"GenBank", "RefSeq RNA"} for m in maps)
        for m in maps:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "PA128" and m["fromSource"] == "ClinPGx"
        assert len(got) == len(maps)

    async def test_chemical_includes_atc_codes(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings("PA449088")
        got = {(m["toSource"], m["toId"]) for m in maps}
        assert {
            ("DRUGBANK", "DB00318"),
            ("PUBCHEM", "5284371"),
            ("CHEBI", "CHEBI:16714"),
            ("MESH", "D003061"),
            ("RXNORM", "2670"),
            ("UMLS", "C0009214"),
            ("ATC", "R05DA04"),
        } <= got
        atc = [m for m in maps if m["toSource"] == "ATC"]
        assert atc and all(m["mappingType"] == "atc_code" for m in atc)

    async def test_variant(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings("PA166156104")
        assert {(m["toSource"], m["toId"]) for m in maps} == {
            ("DBSNP", "rs3892097"),
            ("CLINVAR", "16889"),
        }

    async def test_duplicates_and_blank_ids_collapsed(self, adapter):
        chem = {
            "data": {
                "objCls": "Chemical",
                "id": "PA449088",
                "name": "codeine",
                "linkOuts": [
                    {"resource": "DrugBank", "resourceId": "DB00318"},
                    {"resource": "DrugBank", "resourceId": "DB00318"},
                    {"resource": "DrugBank", "resourceId": ""},
                ],
            }
        }
        _patch(adapter, _router({"chemical/PA449088": chem}))
        maps = await adapter.get_mappings("PA449088")
        assert [(m["toSource"], m["toId"]) for m in maps] == [("DRUGBANK", "DB00318")]

    async def test_unknown_invalid_and_error(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_mappings("PA7") == []
        assert await adapter.get_mappings("CYP2D6") == []
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_mappings("PA128") == []


@pytest.mark.asyncio
class TestHttp:
    async def test_requests_are_spaced_for_two_per_second(self, adapter, monkeypatch):
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        monkeypatch.setattr("knowledge_lookup.adapters.clinpgx_adapter.asyncio.sleep", fake_sleep)
        _patch(adapter, _router())
        adapter._last_request = time.monotonic()
        await adapter._get("gene", {"symbol": "CYP2D6"})
        assert sleeps and 0 < sleeps[0] <= 0.55

    async def test_not_found_is_empty_other_errors_propagate(self, adapter):
        _patch(adapter, AsyncMock(side_effect=NotFound("gene")))
        assert await adapter._get("gene", {"symbol": "NOPE"}) == []
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        with pytest.raises(RuntimeError):
            await adapter._get("gene", {"symbol": "NOPE"})

    async def test_fail_status_body_without_rows(self, adapter):
        _patch(adapter, AsyncMock(return_value=fx.NOT_FOUND))
        assert await adapter._get("gene", {"symbol": "NOPE"}) == []
