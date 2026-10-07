"""Unit tests for AlphaFoldAdapter (mocked AlphaFold DB / UniProt responses captured live)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import alphafold_adapter as mod
from knowledge_lookup.adapters.alphafold_adapter import AlphaFoldAdapter, normalize_identifier
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import alphafold_responses as fx

pytestmark = pytest.mark.unit

AF = KnowledgeSource.ALPHAFOLD


def route(table):
    """AsyncMock side effect answering by URL substring; unknown URLs raise (HTTP 404)."""

    async def fake(url, params=None, headers=None, json_data=None):
        for needle, value in table.items():
            if needle in url:
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
        raise RuntimeError(f"404 {url}")

    return AsyncMock(side_effect=fake)


TABLE = {
    "/prediction/P38398": fx.PREDICTION_P38398,
    "/prediction/AF-P38398-F1": fx.PREDICTION_P38398[:1],
    "/prediction/AF-P38398-8-F1": fx.PREDICTION_P38398[1:2],
    "/prediction/P42898": fx.PREDICTION_P42898,
    "/uniprotkb/search": fx.UNIPROT_SEARCH_BRCA1,
    "/uniprotkb/P38398": fx.UNIPROT_P38398_PDB,
}


@pytest.fixture
def adapter(lookup_config):
    return AlphaFoldAdapter(lookup_config)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ALPHAFOLD
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("P38398", ("accession", "P38398")),
            ("p38398", ("accession", "P38398")),
            ("UniProt:P38398", ("accession", "P38398")),
            ("P38398-2", ("accession", "P38398-2")),
            ("A0A024R161", ("accession", "A0A024R161")),
            ("AF-P38398-F1", ("entry", "AF-P38398-F1")),
            ("af-p38398-2-f1", ("entry", "AF-P38398-2-F1")),
            ("alphafold:AF-P38398-F1", ("entry", "AF-P38398-F1")),
            ("BRCA1", ("query", "BRCA1")),
            ("breast cancer type 1", ("query", "breast cancer type 1")),
            ("", None),
            ("   ", None),
        ],
    )
    def test_normalize_identifier(self, raw, expected):
        assert normalize_identifier(raw) == expected


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_by_accession(self, adapter):
        mock = route(TABLE)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("p38398")
        assert concept.primary_id == "AF-P38398-F1"
        assert concept.primary_label == "Breast cancer type 1 susceptibility protein"
        assert concept.concept_type == ConceptType.PROTEIN
        assert {(i.source, i.identifier) for i in concept.identifiers} == {
            (AF, "AF-P38398-F1"),
            (KnowledgeSource.UNIPROT, "P38398"),
        }
        assert concept.identifiers[0].url == "https://alphafold.ebi.ac.uk/entry/AF-P38398-F1"
        assert {"BRCA1", "BRCA1_HUMAN", "P38398"} <= set(concept.synonyms)
        assert concept.categories == ["Homo sapiens"]
        assert "pLDDT 41.6" in concept.definitions[0] and "v6" in concept.definitions[0]
        data = concept.source_data[AF]
        assert data["global_plddt"] == pytest.approx(41.59)
        assert data["plddt_fractions"]["very_low"] == pytest.approx(0.804)
        assert data["sequence_length"] == 1863
        assert data["model_version"] == 6
        assert data["urls"]["model_cif"].endswith("model_v6.cif")
        assert data["urls"]["pae_json"].endswith("predicted_aligned_error_v6.json")
        assert "sequence" not in data  # large and available from UniProt
        assert [e["entry_id"] for e in data["other_entries"]] == [
            "AF-P38398-8-F1",
            "AF-P38398-7-F1",
        ]
        assert mock.await_args.args[0].endswith("/prediction/P38398")

    @pytest.mark.asyncio
    async def test_details_by_entry_id_selects_that_entry(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            concept = await adapter.get_concept_details("AF-P38398-8-F1")
        assert concept.primary_id == "AF-P38398-8-F1"
        assert any(i.identifier == "P38398-8" for i in concept.identifiers)

    @pytest.mark.asyncio
    async def test_details_by_gene_symbol_resolves_via_uniprot(self, adapter):
        mock = route(TABLE)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("BRCA1")
        assert concept.primary_id == "AF-P38398-F1"
        search = mock.await_args_list[0]
        assert search.args[0] == "https://rest.uniprot.org/uniprotkb/search"
        assert search.kwargs["params"]["query"] == (
            "gene_exact:BRCA1 AND organism_id:9606 AND reviewed:true"
        )
        assert search.kwargs["params"]["size"] == 1

    @pytest.mark.asyncio
    async def test_missing_invalid_and_errors(self, adapter):
        mock = route({"/uniprotkb/search": fx.UNIPROT_SEARCH_EMPTY})
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.get_concept_details("Q8WZ42") is None  # no model: 404
            assert await adapter.get_concept_details("NOPEGENE") is None
            assert await adapter.get_concept_details("") is None
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            assert await adapter.get_concept_details("P38398") is None
        with patch.object(adapter, "_entries_for", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_concept_details("P38398") is None

    @pytest.mark.asyncio
    async def test_entry_without_optional_fields(self, adapter):
        bare = [{"entryId": "AF-Q00000-F1"}]
        with patch.object(adapter, "_make_request", route({"/prediction/Q00000": bare})):
            concept = await adapter.get_concept_details("Q00000")
        assert concept.primary_label == "AF-Q00000-F1"
        assert concept.categories == []
        assert concept.source_data[AF]["sequence_length"] is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_by_accession_and_entry(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            by_acc = await adapter.search_concepts("P38398", limit=3)
            by_entry = await adapter.search_concepts("AF-P38398-F1", limit=3)
        assert by_acc[0].primary_id == by_entry[0].primary_id == "AF-P38398-F1"

    @pytest.mark.asyncio
    async def test_search_by_gene_symbol(self, adapter):
        mock = route(TABLE)
        with patch.object(adapter, "_make_request", mock):
            concepts = await adapter.search_concepts("BRCA1", limit=5)
        assert [c.primary_id for c in concepts] == ["AF-P38398-F1"]
        assert mock.await_args_list[0].kwargs["params"]["size"] == 5

    @pytest.mark.asyncio
    async def test_gene_falls_back_to_unreviewed(self, adapter):
        seen: list[str] = []

        async def fake(url, params=None, headers=None, json_data=None):
            if "/search" in url:
                seen.append(params["query"])
                if "reviewed:true" in params["query"]:
                    return fx.UNIPROT_SEARCH_EMPTY
                return fx.UNIPROT_SEARCH_BRCA1
            return fx.PREDICTION_P38398

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            concepts = await adapter.search_concepts("BRCA1", 1)
        assert len(concepts) == 1
        assert len(seen) == 2 and "reviewed:true" not in seen[1]

    @pytest.mark.asyncio
    async def test_protein_name_phrase(self, adapter):
        mock = route(TABLE)
        with patch.object(adapter, "_make_request", mock):
            await adapter.search_concepts('breast "cancer" (type 1)', limit=2)
        query = mock.await_args_list[0].kwargs["params"]["query"]
        assert "gene_exact" not in query and "reviewed:true" in query
        assert '"' not in query.split(" AND ")[0].strip("()")

    @pytest.mark.asyncio
    async def test_search_limit_caps_resolutions(self, adapter):
        many = {"results": [{"primaryAccession": f"P{i:05d}"} for i in range(1, 9)]}
        mock = route({"/uniprotkb/search": many})
        with patch.object(adapter, "_make_request", mock):
            await adapter.search_concepts("kinase", limit=50)
        assert mock.await_args_list[0].kwargs["params"]["size"] == mod.MAX_SEARCH_RESOLUTIONS

    @pytest.mark.asyncio
    async def test_empty_blank_zero_and_errors(self, adapter):
        mock = route({"/uniprotkb/search": fx.UNIPROT_SEARCH_EMPTY})
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.search_concepts("fatigue", 5) == []
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("BRCA1", 0) == []
            assert await adapter.search_concepts("Q8WZ42", 5) == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=OSError("down"))):
            assert await adapter.search_concepts("BRCA1", 5) == []
        with patch.object(adapter, "_resolve_accessions", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.search_concepts("BRCA1", 5) == []

    @pytest.mark.asyncio
    async def test_resolved_accession_without_model_is_skipped(self, adapter):
        with patch.object(
            adapter, "_make_request", route({"/uniprotkb/search": fx.UNIPROT_SEARCH_BRCA1})
        ):
            assert await adapter.search_concepts("BRCA1", 5) == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_predicted_and_experimental_structures(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            rels = await adapter.get_relationships("P38398", limit=6)
        predicted = [r for r in rels if r["relation_label"] == "has_predicted_structure"]
        experimental = [r for r in rels if r["relation_label"] == "has_experimental_structure"]
        assert len(rels) == 6 and len(predicted) == 3 and len(experimental) == 3
        assert predicted[0]["related_id"] == "AF-P38398-F1"
        assert predicted[0]["model_url"].startswith("https://alphafold.ebi.ac.uk/files/")
        # best resolution first, NMR (no resolution) last
        assert [r["related_id"] for r in experimental] == ["1T15", "1T29", "1JNX"]
        assert experimental[0]["method"] == "X-ray" and experimental[0]["resolution"] == "1.85 A"
        assert experimental[0]["related_name"] == "PDB 1T15 (X-ray, 1.85 A)"
        assert experimental[0]["page_url"].endswith("/1T15")

    @pytest.mark.asyncio
    async def test_limit_one_and_nmr_name(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            one = await adapter.get_relationships("P38398", limit=1)
            many = await adapter.get_relationships("P38398", limit=50)
        assert [r["relation_label"] for r in one] == ["has_predicted_structure"]
        nmr = next(r for r in many if r["related_id"] == "1JM7")
        assert nmr["related_name"] == "PDB 1JM7 (NMR)"

    @pytest.mark.asyncio
    async def test_uniprot_failure_keeps_predicted_structures(self, adapter):
        table = {k: v for k, v in TABLE.items() if k != "/uniprotkb/P38398"}
        with patch.object(adapter, "_make_request", route(table)):
            rels = await adapter.get_relationships("P38398", limit=4)
        assert {r["relation_label"] for r in rels} == {"has_predicted_structure"}

    @pytest.mark.asyncio
    async def test_isoform_accession_queries_uniprot_canonical_entry(self, adapter):
        entries = copy.deepcopy(fx.PREDICTION_P38398[1:2])
        mock = route({"/prediction/P38398-8": entries, "/uniprotkb/P38398": fx.UNIPROT_P38398_PDB})
        with patch.object(adapter, "_make_request", mock):
            rels = await adapter.get_relationships("P38398-8", limit=4)
        assert any(r["relation_label"] == "has_experimental_structure" for r in rels)
        assert mock.await_args_list[-1].args[0].endswith("/uniprotkb/P38398")

    @pytest.mark.asyncio
    async def test_edge_cases(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            assert await adapter.get_relationships("P38398", limit=0) == []
            assert await adapter.get_relationships("Q8WZ42") == []
        with patch.object(adapter, "_entries_for", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_relationships("P38398") == []

    @pytest.mark.asyncio
    async def test_xref_without_pdb_id_or_resolution_is_handled(self, adapter):
        odd = {
            "uniProtKBCrossReferences": [
                {"database": "PDB", "id": "9ZZZ", "properties": []},
                {"database": "PDB", "properties": []},
                {"database": "Ensembl", "id": "ENST1"},
            ]
        }
        table = {**TABLE, "/uniprotkb/P38398": odd}
        with patch.object(adapter, "_make_request", route(table)):
            rels = await adapter.get_relationships("P38398", limit=10)
        experimental = [r for r in rels if r["relation_label"] == "has_experimental_structure"]
        assert [r["related_id"] for r in experimental] == ["9ZZZ"]
        assert experimental[0]["related_name"] == "PDB 9ZZZ"


class TestMappings:
    @pytest.mark.asyncio
    async def test_accession_to_alphafold_entries(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            maps = await adapter.get_mappings("p38398")
        assert [m["toId"] for m in maps] == [
            "AF-P38398-F1",
            "AF-P38398-8-F1",
            "AF-P38398-7-F1",
        ]
        assert all(
            m["fromId"] == "P38398"
            and m["fromSource"] == "UniProt"
            and m["toSource"] == "AlphaFold"
            and m["mappingType"] == "has_predicted_structure"
            and m["confidence"] == 1.0
            for m in maps
        )

    @pytest.mark.asyncio
    async def test_entry_to_uniprot_and_gene_symbol(self, adapter):
        with patch.object(adapter, "_make_request", route(TABLE)):
            from_entry = await adapter.get_mappings("AF-P38398-F1")
            from_gene = await adapter.get_mappings("BRCA1")
        assert from_entry == [
            {
                "fromId": "AF-P38398-F1",
                "toId": "P38398",
                "fromSource": "AlphaFold",
                "toSource": "UniProt",
                "mappingType": "predicted_structure_of",
                "confidence": 1.0,
            }
        ]
        assert {m["fromId"] for m in from_gene} == {"P38398"}

    @pytest.mark.asyncio
    async def test_entry_without_accession_and_failures(self, adapter):
        with patch.object(
            adapter, "_make_request", route({"/prediction/AF-Q00000-F1": [{"entryId": "AF-X"}]})
        ):
            assert await adapter.get_mappings("AF-Q00000-F1") == []
        with patch.object(adapter, "_make_request", route({})):
            assert await adapter.get_mappings("Q8WZ42") == []
            assert await adapter.get_mappings("") == []
        with patch.object(adapter, "_entries_for", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_mappings("P38398") == []
