"""
Unit tests for IntActAdapter (responses in tests/fixtures/intact_responses.py are trimmed
live IntAct web-service / PSICQUIC payloads).
"""

from unittest.mock import AsyncMock, patch
from urllib.parse import unquote

import aiohttp
import pytest
from fixtures.intact_responses import (
    BRCA1_TAB25,
    BRCA1_TAB27,
    FIND_BRCA1,
    FIND_EMPTY,
    FIND_P38398,
    FIND_TNF,
    IL6_TAB25,
)

from knowledge_lookup.adapters.intact_adapter import (
    IntActAdapter,
    _label,
    _partner_name,
    _taxon,
    _tokens,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


def _not_found() -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=None, history=(), status=404)  # type: ignore[arg-type]


@pytest.fixture
def adapter(lookup_config):
    return IntActAdapter(lookup_config)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.INTACT
        assert adapter.source == KnowledgeSource.INTACT
        assert adapter.is_available() is True
        assert adapter.min_request_timeout == 60.0

    def test_rate_limit_custom(self):
        config = LookupConfig(rate_limits={KnowledgeSource.INTACT: 3.0})
        assert IntActAdapter(config).get_rate_limit() == 3.0

    def test_mitab_helpers(self):
        assert _tokens("intact:EBI-1|uniprotkb:P1(gene name)|-|junk") == [
            ("intact", "EBI-1"),
            ("uniprotkb", "P1"),
        ]
        assert _label('psi-mi:"MI:0018"(two hybrid)') == "two hybrid"
        assert _label("-") == ""
        assert _taxon("taxid:9606(human)|taxid:9606(Homo sapiens)") == (9606, "Homo sapiens")
        assert _taxon("taxid:-2(chemical synthesis)") == (None, "chemical synthesis")
        assert _taxon("-") == (None, "")
        assert _taxon("taxid:abc") == (None, "")
        assert _partner_name("uniprotkb:X(gene name synonym)|psi-mi:Y(display_short)", "id") == "Y"
        assert _partner_name("-", "fallback") == "fallback"


class TestSearch:
    @pytest.mark.asyncio
    async def test_gene_name_search_filters_species_and_isoforms(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_BRCA1
            concepts = await adapter.search_concepts("BRCA1", limit=10)
        # human proteins only: no mouse/worm/isoform/mRNA hits
        assert [c.primary_id for c in concepts] == ["P38398", "Q9NQR3"]
        assert concepts[0].concept_type == ConceptType.PROTEIN
        assert concepts[0].confidence_score == 0.9
        url, params = req.call_args.args
        assert url.endswith("/interactor/findInteractor/BRCA1")
        assert params == {"page": 0, "pageSize": 40}

    @pytest.mark.asyncio
    async def test_other_species_when_taxid_none(self, lookup_config):
        adapter = IntActAdapter(lookup_config, taxid=None)
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_BRCA1
            concepts = await adapter.search_concepts("BRCA1", limit=20)
        ids = [c.primary_id for c in concepts]
        assert "P48754" in ids and "B6VQ60" in ids
        assert not any("-" in i for i in ids)  # isoforms still dropped

    @pytest.mark.asyncio
    async def test_limit_and_dedupe(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_TNF
            concepts = await adapter.search_concepts("TNF", limit=2)
        assert [c.primary_label for c in concepts] == ["TRAF2", "TNF"]
        dup = {"content": FIND_TNF["content"][:1] * 2}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = dup
            assert len(await adapter.search_concepts("TNF")) == 1

    @pytest.mark.asyncio
    async def test_accession_search_accepts_any_species_and_prefix(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_P38398
            concepts = await adapter.search_concepts("UniProt:P38398")
        assert [c.primary_id for c in concepts] == ["P38398"]
        assert req.call_args.args[0].endswith("/findInteractor/P38398")

    @pytest.mark.asyncio
    async def test_no_match_and_invalid_input(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_EMPTY
            assert await adapter.search_concepts("fatigue") == []
            assert await adapter.search_concepts("  ") == []
            assert await adapter.search_concepts("BRCA1", limit=0) == []
            req.return_value = ["unexpected"]
            assert await adapter.search_concepts("BRCA1") == []
            req.side_effect = _not_found()
            assert await adapter.search_concepts("zzzz") == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = RuntimeError("boom")
            assert await adapter.search_concepts("BRCA1") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_by_gene_name_prefers_most_connected_human(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_BRCA1
            concept = await adapter.get_concept_details("brca1")
        assert concept.primary_id == "P38398"
        assert concept.primary_label == "BRCA1"
        assert concept.concept_type == ConceptType.PROTEIN
        assert concept.confidence_score == 1.0
        assert concept.definitions == ["Breast cancer type 1 susceptibility protein"]
        assert "taxon:9606" in concept.categories and "Homo sapiens" in concept.categories
        assert concept.semantic_types == ["protein"]
        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ("INTACT", "EBI-349905") in ids and ("UNIPROT", "P38398") in ids
        assert concept.source_data[KnowledgeSource.INTACT]["interactionCount"] == 551

    @pytest.mark.asyncio
    async def test_details_by_accessions(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_P38398
            by_uniprot = await adapter.get_concept_details("P38398")
            by_ebi = await adapter.get_concept_details("IntAct:EBI-349905")
            isoform = await adapter.get_concept_details("P38398-1")
        assert by_uniprot.primary_id == by_ebi.primary_id == "P38398"
        assert isoform.primary_id == "P38398-1"

    @pytest.mark.asyncio
    async def test_non_protein_interactor_type(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_BRCA1
            concept = await adapter.get_concept_details("EBI-34592130")
        assert concept.primary_id == "ENST00000357654"
        assert concept.concept_type == ConceptType.MOLECULAR_ENTITY
        assert all(i.source != "UNIPROT" for i in concept.identifiers)

    @pytest.mark.asyncio
    async def test_unknown_returns_none(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = FIND_EMPTY
            assert await adapter.get_concept_details("zzzzqqq") is None
            assert await adapter.get_concept_details("") is None
            req.return_value = FIND_BRCA1
            assert await adapter.get_concept_details("P99999") is None  # not in the hits
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_concept_details("P38398") is None

    def test_converter_rejects_incomplete_records(self, adapter):
        assert adapter._convert_interactor_to_concept({"interactorName": "X"}) is None
        assert adapter._convert_interactor_to_concept({"interactorAc": "EBI-1"}) is None
        assert adapter._convert_interactor_to_concept(None) is None  # type: ignore[arg-type]


class TestRelationships:
    @pytest.mark.asyncio
    async def test_partners_sorted_by_score_and_aggregated(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = BRCA1_TAB25
            rels = await adapter.get_relationships("P38398", limit=5)
        assert req.await_count == 1  # first tier already holds 5 partners
        url, params = req.call_args.args
        assert unquote(url).endswith("/id:P38398 AND negative:false AND intact-miscore:[0.7 TO 1]")
        assert params == {"format": "tab25", "maxResults": 400}

        assert [r["related_id"] for r in rels] == [
            "Q9BX63",
            "Q99728",
            "Q99708",
            "P03372",
            "Q9GZX5",
        ]
        brip1 = rels[0]
        assert brip1["relation_label"] == "interacts_with"
        assert brip1["related_name"] == "BRIP1"
        assert brip1["source"] == "IntAct"
        assert brip1["related_id_source"] == "UniProt"
        assert brip1["score"] == 0.98
        assert brip1["evidence_count"] == 3
        assert brip1["pmids"] == ["17525340"]
        assert brip1["detection_methods"] == [
            "anti bait coimmunoprecipitation",
            "tandem affinity purification",
        ]
        assert set(brip1["interaction_types"]) == {"association", "physical association"}
        assert brip1["species"] == "Homo sapiens" and brip1["taxid"] == 9606
        assert brip1["intact_id"].startswith("EBI-")

    @pytest.mark.asyncio
    async def test_both_orientations_merge_into_one_edge(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = BRCA1_TAB25
            rels = await adapter.get_relationships("P38398", limit=5)
        esr1 = next(r for r in rels if r["related_id"] == "P03372")
        assert esr1["evidence_count"] == 2 and esr1["related_name"] == "ESR1"
        znf = next(r for r in rels if r["related_id"] == "Q9GZX5")
        assert znf["evidence_count"] == 3
        assert znf["detection_methods"] == ["two hybrid", "pull down", "coimmunoprecipitation"]

    @pytest.mark.asyncio
    async def test_falls_back_to_lower_score_tiers_and_keeps_non_uniprot_partners(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = BRCA1_TAB25
            rels = await adapter.get_relationships("P38398", limit=25)
        assert req.await_count == 3  # fewer than 25 partners at every tier
        queries = [unquote(c.args[0]) for c in req.await_args_list]
        assert "intact-miscore:[0.4 TO 1]" in queries[1]
        assert queries[2].endswith("negative:false")
        by_id = {r["related_id"]: r for r in rels}
        assert by_id["EBI-2694074"]["related_id_source"] == "IntAct"
        assert by_id["ENSG00000096717"]["related_id_source"] == "Ensembl"
        assert rels[-1]["score"] == 0.35
        # non-protein partners have no gene name: the IntAct short label stands in
        assert by_id["EBI-2694074"]["related_name"] == "mdm2_human_probe"
        assert by_id["ENSG00000096717"]["related_name"] == "sir1_human_gene"

    @pytest.mark.asyncio
    async def test_isoform_and_chain_partners_merge_into_canonical_accession(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = IL6_TAB25
            rels = await adapter.get_relationships("EBI-720533", limit=1)
        assert len(rels) == 1
        il6r = rels[0]
        assert il6r["related_id"] == "P08887" and il6r["related_name"] == "IL6R"
        assert il6r["isoforms"] == ["P08887-PRO_0000450730"]
        assert il6r["evidence_count"] == 5 and il6r["score"] == 0.91

    @pytest.mark.asyncio
    async def test_gene_name_is_resolved_first(self, adapter):
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws,
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as psq,
        ):
            ws.return_value = FIND_BRCA1
            psq.return_value = BRCA1_TAB25
            rels = await adapter.get_relationships("BRCA1", limit=2)
        assert [r["related_name"] for r in rels] == ["BRIP1", "BARD1"]
        assert "id:P38398 AND" in unquote(psq.call_args.args[0])

    @pytest.mark.asyncio
    async def test_limit_and_invalid_input(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = BRCA1_TAB25
            assert len(await adapter.get_relationships("P38398", limit=2)) == 2
            assert await adapter.get_relationships("P38398", limit=0) == []
            assert await adapter.get_relationships("") == []

    @pytest.mark.asyncio
    async def test_unmatched_malformed_and_self_rows_are_skipped(self, adapter):
        self_row = "\t".join(["uniprotkb:P38398", "uniprotkb:P38398"] + ["-"] * 12 + ["x"])
        other_row = "\t".join(["uniprotkb:Q1", "uniprotkb:Q2"] + ["-"] * 12 + ["x"])
        text = f"short\tcells\n{self_row}\n{other_row}\n\n"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = text
            assert await adapter.get_relationships("P38398") == []

    @pytest.mark.asyncio
    async def test_row_without_partner_id_or_score(self, adapter):
        cells = ["uniprotkb:P38398", "-"] + ["-"] * 13
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = "\t".join(cells)
            assert await adapter.get_relationships("P38398") == []

    @pytest.mark.asyncio
    async def test_no_interactions_and_errors(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as req:
            req.return_value = ""
            assert await adapter.get_relationships("P38398") == []
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_relationships("P38398") == []
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws:
            ws.return_value = FIND_EMPTY
            assert await adapter.get_relationships("zzzzqqq") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_cross_references(self, adapter):
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws,
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as psq,
        ):
            ws.return_value = FIND_P38398
            psq.return_value = BRCA1_TAB27
            mappings = await adapter.get_mappings("P38398")
        assert psq.call_args.args[1] == {"format": "tab27", "maxResults": 1}
        by_target = {(m["toSource"], m["toId"]): m for m in mappings}
        assert by_target[("IntAct", "EBI-349905")]["mappingType"] == "exact"
        assert by_target[("Ensembl", "ENSG00000012048")]["mappingType"] == "exact"
        assert ("Ensembl", "ENSP00000350283") in by_target  # version stripped
        assert by_target[("PDB", "1JM7")]["mappingType"] == "related"
        assert ("InterPro", "IPR001357") in by_target
        assert any(s == "Reactome" for s, _ in by_target)
        assert any(s == "Orphanet" for s, _ in by_target)
        assert len([m for m in mappings if m["toSource"] == "UniProt"]) <= 5
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "P38398" and m["fromSource"] == "IntAct"
        assert all(
            sum(1 for m in mappings if m["toSource"] == src) <= 10
            for src in ("PDB", "RefSeq", "Reactome", "InterPro")
        )

    @pytest.mark.asyncio
    async def test_partner_side_b_is_used_when_interactor_is_column_b(self, adapter):
        cells = BRCA1_TAB27.rstrip("\n").split("\t")
        cells[0], cells[1] = cells[1], cells[0]
        cells[2], cells[3] = cells[3], cells[2]
        cells[22], cells[23] = cells[23], cells[22]
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws,
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as psq,
        ):
            ws.return_value = FIND_P38398
            psq.return_value = "\t".join(cells)
            mappings = await adapter.get_mappings("P38398")
        assert ("Ensembl", "ENSG00000012048") in {(m["toSource"], m["toId"]) for m in mappings}

    @pytest.mark.asyncio
    async def test_interactor_level_mappings_survive_xref_failures(self, adapter):
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws,
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as psq,
        ):
            ws.return_value = FIND_P38398
            psq.side_effect = RuntimeError("boom")
            mappings = await adapter.get_mappings("EBI-349905")
        assert [(m["toSource"], m["toId"]) for m in mappings] == [("IntAct", "EBI-349905")]
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws,
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as psq,
        ):
            ws.return_value = FIND_P38398
            psq.return_value = "short\trow"
            assert len(await adapter.get_mappings("P38398")) == 1
            psq.return_value = "\t".join(["uniprotkb:Q1", "uniprotkb:Q2"] + ["-"] * 40)
            assert len(await adapter.get_mappings("P38398")) == 1

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as ws:
            ws.return_value = FIND_EMPTY
            assert await adapter.get_mappings("zzzz") == []
            assert await adapter.get_mappings("") == []
            ws.side_effect = RuntimeError("boom")
            assert await adapter.get_mappings("P38398") == []
