"""Unit tests for IEDBAdapter (IEDB IQ-API, PostgREST); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import iedb_adapter
from knowledge_lookup.adapters.iedb_adapter import IEDBAdapter, _pairs, _quote
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import iedb_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(iedb_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return IEDBAdapter(lookup_config)


class Router:
    """Fake ``_make_request``: answers by table name; records every (table, params) call."""

    def __init__(self, **tables):
        self.tables = tables
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, url, params=None, headers=None, json_data=None):
        assert headers == {"Accept": "application/json"}
        table = url.rsplit("/", 1)[-1]
        self.calls.append((table, params))
        value = self.tables.get(table, [])
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(params)
        return copy.deepcopy(value)

    def patched(self, adapter):
        return patch.object(adapter, "_make_request", self)

    def params(self, table):
        return [p for t, p in self.calls if t == table]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.IEDB
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("IEDB_EPITOPE:1309147", 1309147),
            ("iedb_epitope:68", 68),
            ("IEDB:68", 68),
            ("IEDB-EPITOPE 68", 68),
            ("68", 68),
            (" 1309147 ", 1309147),
            ("P0DTC2", None),
            ("spike", None),
            ("", None),
            (None, None),
        ],
    )
    def test_epitope_number(self, raw, expected):
        assert IEDBAdapter._epitope_number(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("P0DTC2", "P0DTC2"),
            ("UNIPROT:p0dtc2", "P0DTC2"),
            ("P0DTC2.1", "P0DTC2"),
            ("P03211", "P03211"),
            ("A0A024R161", "A0A024R161"),
            ("QHD43416.1", None),  # GenBank accession
            ("spike", None),
            ("SPIKE", None),
            ("68", None),
            ("", None),
        ],
    )
    def test_uniprot(self, raw, expected):
        assert IEDBAdapter._uniprot(raw) == expected

    def test_helpers(self):
        assert _quote('a"b\\c') == '"a\\"b\\\\c"'
        assert _pairs(["A"], ["a"]) == [("A", "a")]
        # independently sorted arrays: names cannot be trusted next to ids
        assert _pairs(["A", "B"], ["b", "a"]) == [("A", ""), ("B", "")]
        assert _pairs(None, ["a"]) == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_epitope_id(self, adapter):
        router = Router(epitope_search=[fx.LIGHT_YLQ])
        with router.patched(adapter):
            result = await adapter.search_concepts("IEDB_EPITOPE:1309147")
        assert [c.primary_id for c in result] == ["IEDB_EPITOPE:1309147"]
        assert router.params("epitope_search")[0]["structure_id"] == "eq.1309147"
        assert "tcell_ids" not in router.params("epitope_search")[0]["select"]

    @pytest.mark.asyncio
    async def test_uniprot_accession_gives_antigen(self, adapter):
        router = Router(antigen_search=fx.ANTIGEN_SPIKE)
        with router.patched(adapter):
            result = await adapter.search_concepts("UNIPROT:P0DTC2")
        assert result[0].primary_id == "UNIPROT:P0DTC2"
        assert result[0].concept_type == ConceptType.PROTEIN
        with Router().patched(adapter):
            assert await adapter.search_concepts("P99999") == []

    @pytest.mark.asyncio
    async def test_exact_peptide_sequence(self, adapter):
        router = Router(epitope_search=[fx.LIGHT_YLQ])
        with router.patched(adapter):
            result = await adapter.search_concepts("YLQPRTFLL", 5)
        assert result[0].primary_label == "YLQPRTFLL"
        params = router.params("epitope_search")[0]
        assert params["linear_sequence"] == "eq.YLQPRTFLL" and params["limit"] == 5
        assert router.params("epitope_export") == []

    @pytest.mark.asyncio
    async def test_sequence_miss_falls_back_to_text_search(self, adapter):
        router = Router(
            epitope_search=lambda p: [] if "linear_sequence" in p else [fx.LIGHT_YLQ],
            epitope_export=[{"structure_id": 1309147}],
        )
        with router.patched(adapter):
            result = await adapter.search_concepts("SPIKEPEPTIDE")
        assert [c.primary_id for c in result] == ["IEDB_EPITOPE:1309147"]

    @pytest.mark.asyncio
    async def test_text_search_builds_filter_and_keeps_export_order(self, adapter):
        router = Router(
            epitope_export=fx.EXPORT_ROWS,
            epitope_search=fx.LIGHT_ROWS,
        )
        with router.patched(adapter):
            result = await adapter.search_concepts("SARS-CoV-2 spike", 10)
        # export order is 68, 1309147, 2711844 (duplicates and null ids dropped)
        assert [c.primary_id for c in result] == [
            "IEDB_EPITOPE:68",
            "IEDB_EPITOPE:1309147",
            "IEDB_EPITOPE:2711844",
        ]
        export = router.params("epitope_export")[0]
        assert export["select"] == "structure_id" and export["limit"] == 50
        assert export["and"].startswith('(or(epitope__name.ilike."*SARS-CoV2*"')
        assert 'epitope__species.ilike."*coronavirus 2*"' in export["and"]
        assert export["and"].count("or(") == 2  # one group per word
        assert 'epitope__source_molecule.ilike."*spike*"' in export["and"]
        lookup = router.params("epitope_search")[0]
        assert lookup["structure_id"] == "in.(68,1309147,2711844)"

    @pytest.mark.asyncio
    async def test_limit_and_alias(self, adapter):
        router = Router(epitope_export=fx.EXPORT_ROWS, epitope_search=fx.LIGHT_ROWS)
        with router.patched(adapter):
            result = await adapter.search_concepts("EBV", 2)
        assert len(result) == 2
        assert router.params("epitope_search")[0]["structure_id"] == "in.(68,1309147)"
        assert "Epstein-Barr" in router.params("epitope_export")[0]["and"]

    @pytest.mark.asyncio
    async def test_filter_values_are_quoted(self, adapter):
        router = Router()
        with router.patched(adapter):
            await adapter.search_concepts('a,b) "x"')
        assert '\\"x\\"' in router.params("epitope_export")[0]["and"]

    @pytest.mark.asyncio
    async def test_no_hits(self, adapter):
        router = Router(epitope_export=[])
        with router.patched(adapter):
            assert await adapter.search_concepts("zzzzqq") == []
        assert router.params("epitope_search") == []

    @pytest.mark.asyncio
    async def test_blank_bad_limit_and_errors(self, adapter):
        router = Router(epitope_export=fx.PGRST_ERROR)
        with router.patched(adapter):
            assert await adapter.search_concepts("  ") == []
            assert await adapter.search_concepts("spike", 0) == []
            assert router.calls == []
            assert await adapter.search_concepts("spike") == []
        router = Router(epitope_export=RuntimeError("boom"))
        with router.patched(adapter):
            assert await adapter.search_concepts("spike") == []

    @pytest.mark.asyncio
    async def test_error_object_raises_inside_get(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.PGRST_ERROR)):
            with pytest.raises(RuntimeError, match="operator does not exist"):
                await adapter._get("epitope_search", {})
        with patch.object(adapter, "_make_request", AsyncMock(return_value=None)):
            assert await adapter._get("epitope_search", {}) == []


class TestConcepts:
    @pytest.mark.asyncio
    async def test_light_concept(self, adapter):
        router = Router(epitope_search=[fx.LIGHT_YLQ])
        with router.patched(adapter):
            (c,) = await adapter.search_concepts("1309147")
        assert c.concept_type == ConceptType.MOLECULAR_ENTITY
        assert c.primary_label == "YLQPRTFLL"
        assert c.categories == ["Linear peptide"] and c.semantic_types == ["epitope"]
        assert c.identifiers[0].url == "https://www.iedb.org/epitope/1309147"
        assert {(i.source, i.identifier) for i in c.identifiers} >= {
            ("UNIPROT", "P0DTC2"),
            ("NCBITAXONOMY", "2697049"),
        }
        assert c.definitions == [
            "IEDB linear peptide of 9 residues from Spike glycoprotein (SARS-CoV2)."
        ]
        data = c.source_data[KnowledgeSource.IEDB]
        assert data["antigens"] == ["UNIPROT:P0DTC2"] and "tcell_assay_count" not in data

    @pytest.mark.asyncio
    async def test_discontinuous_epitope(self, adapter):
        router = Router(epitope_search=[fx.LIGHT_DISCONTINUOUS])
        with router.patched(adapter):
            (c,) = await adapter.search_concepts("2711844")
        assert c.primary_label == "A123, G142, Y144"
        assert c.synonyms == ["A123 G142 Y144"]
        assert c.categories == ["Discontinuous peptide"]
        # several antigens / organisms: the sorted name arrays cannot be paired with ids
        assert c.definitions == [
            "IEDB discontinuous peptide from Spike glycoprotein, UNIPROT:P59594 "
            "(NCBITaxon:2697049, NCBITaxon:227984)."
        ]

    def test_unusable_rows(self, adapter):
        assert adapter._epitope_to_concept(fx.NO_ID_ROW) is None
        assert adapter._epitope_to_concept({"structure_id": 7}).primary_label == "IEDB epitope 7"
        assert adapter._concepts([fx.NO_ID_ROW, fx.LIGHT_YLQ, fx.LIGHT_YLQ], 5)[0].primary_id == (
            "IEDB_EPITOPE:1309147"
        )


class TestDetails:
    @pytest.mark.asyncio
    async def test_detailed_epitope(self, adapter):
        router = Router(epitope_search=[fx.DETAIL_YLQ], epitope_summary=fx.SUMMARY)
        with router.patched(adapter):
            c = await adapter.get_concept_details("IEDB_EPITOPE:1309147")
        assert c.primary_id == "IEDB_EPITOPE:1309147"
        assert len(c.definitions) == 2 and c.definitions[1].startswith("YLQPRTFLL is a linear")
        assert "  " not in c.definitions[1]
        data = c.source_data[KnowledgeSource.IEDB]
        assert data["tcell_assay_count"] == 3 and data["mhc_ligand_assay_count"] == 2
        assert "bcell_assay_count" not in data
        assert data["mhc_alleles"][0] == "HLA-A*01:01" and data["pubmed_count"] == 40
        assert data["hosts"] == ["Homo sapiens (human)", "Mus musculus BALB/c"]
        assert data["diseases"][1] == "COVID-19" and data["pdb_ids"] == ["7n1a", "7n1f"]
        assert "tcell_ids" in router.params("epitope_search")[0]["select"]

    @pytest.mark.asyncio
    async def test_summary_failure_and_missing_summary_are_tolerated(self, adapter):
        router = Router(epitope_search=[fx.DETAIL_YLQ], epitope_summary=RuntimeError("slow"))
        with router.patched(adapter):
            c = await adapter.get_concept_details("1309147")
        assert len(c.definitions) == 1
        router = Router(epitope_search=[fx.DETAIL_YLQ], epitope_summary=[])
        with router.patched(adapter):
            c = await adapter.get_concept_details("1309147")
        assert len(c.definitions) == 1

    @pytest.mark.asyncio
    async def test_antigen(self, adapter):
        router = Router(antigen_search=fx.ANTIGEN_SPIKE)
        with router.patched(adapter):
            c = await adapter.get_concept_details("P0DTC2")
        assert c.primary_id == "UNIPROT:P0DTC2" and c.primary_label == "Spike glycoprotein"
        assert c.synonyms == ["S1 subunit"]  # "Two components" composite names are dropped
        assert ("UNIPROT", "P0DTC2") in {(i.source, i.identifier) for i in c.identifiers}
        assert "SARS-CoV2" in c.definitions[0]
        params = router.params("antigen_search")[0]
        assert params["parent_source_antigen_iri"] == "eq.UNIPROT:P0DTC2" and params["limit"] == 1
        assert "structure_ids" not in params["select"]  # 780 KB for Spike

    @pytest.mark.asyncio
    async def test_antigen_without_names_or_organism(self, adapter):
        router = Router(antigen_search=fx.ANTIGEN_NO_NAME)
        with router.patched(adapter):
            c = await adapter.get_concept_details("P03211")
        assert c.primary_label == "P03211" and not c.definitions

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        with Router().patched(adapter):
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("spike") is None
            assert await adapter.get_concept_details("99999999") is None
            assert await adapter.get_concept_details("P99999") is None
        with Router(epitope_search=RuntimeError("boom")).patched(adapter):
            assert await adapter.get_concept_details("1309147") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_epitope(self, adapter):
        router = Router(epitope_search=[fx.DETAIL_YLQ])
        with router.patched(adapter):
            rels = await adapter.get_relationships("IEDB_EPITOPE:1309147", 100)
        by_label: dict[str, list] = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)
        assert set(by_label) == {
            "has_source_antigen",
            "has_source_organism",
            "has_host_organism",
            "has_tcell_assays",
            "has_mhc_ligand_assays",
            "restricted_by_mhc_allele",
            "associated_with_disease",
        }
        antigens = by_label["has_source_antigen"]
        assert antigens[0] == {
            "relation_label": "has_source_antigen",
            "related_id": "UNIPROT:P0DTC2",
            "related_name": "Spike glycoprotein",
            "source": "IEDB",
        }
        curated = {a["related_id"]: a for a in antigens[1:]}
        assert set(curated) == {"GENPEPT:BCN86353.1", "UNIPROT:P0DTC2.1", "GENPEPT:QHD43416.1"}
        assert curated["UNIPROT:P0DTC2.1"]["starting_position"] == 269
        assert curated["GENPEPT:BCN86353.1"]["ending_position"] == 286
        assert rels[-3:] == antigens[-3:]  # curated records come last
        organisms = {r["related_id"]: r["related_name"] for r in by_label["has_source_organism"]}
        assert organisms == {
            "NCBITaxon:2697049": "SARS-CoV2",
            "NCBITaxon:9606": "Homo sapiens (human)",
        }
        assert [r["related_id"] for r in by_label["has_host_organism"]] == [
            "Homo sapiens (human)",
            "Mus musculus BALB/c",
        ]
        assert by_label["has_tcell_assays"][0]["count"] == 3
        assert (
            by_label["has_tcell_assays"][0]["related_id"] == "tcell_search?structure_id=eq.1309147"
        )
        assert by_label["has_mhc_ligand_assays"][0]["count"] == 2
        assert "has_bcell_assays" not in by_label
        assert [r["related_id"] for r in by_label["restricted_by_mhc_allele"]] == [
            "HLA-A*01:01",
            "HLA-A*02:01",
            "HLA-A2",
        ]
        assert by_label["associated_with_disease"][1]["related_name"] == "COVID-19"

    @pytest.mark.asyncio
    async def test_bcell_assays_and_limit(self, adapter):
        row = {**fx.DETAIL_YLQ, "bcell_ids": [1, 2, 3, 4]}
        with Router(epitope_search=[row]).patched(adapter):
            rels = await adapter.get_relationships("1309147", 100)
            limited = await adapter.get_relationships("1309147", 2)
        bcell = next(r for r in rels if r["relation_label"] == "has_bcell_assays")
        assert bcell["count"] == 4 and bcell["related_name"] == "B cell assays"
        assert len(limited) == 2

    @pytest.mark.asyncio
    async def test_antigen(self, adapter):
        with Router(antigen_search=fx.ANTIGEN_SPIKE).patched(adapter):
            rels = await adapter.get_relationships("UNIPROT:P0DTC2")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [
            ("has_source_organism", "NCBITaxon:2697049")
        ]

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        with Router().patched(adapter):
            assert await adapter.get_relationships("spike") == []
            assert await adapter.get_relationships("1309147", 0) == []
            assert await adapter.get_relationships("99999999") == []
            assert await adapter.get_relationships("P99999") == []
        with Router(epitope_search=RuntimeError("boom")).patched(adapter):
            assert await adapter.get_relationships("1309147") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_epitope(self, adapter):
        with Router(epitope_search=[fx.DETAIL_YLQ]).patched(adapter):
            maps = await adapter.get_mappings("IEDB_EPITOPE:1309147")
        pairs = [(m["toSource"], m["toId"]) for m in maps]
        assert pairs[0] == ("UniProt", "P0DTC2")
        assert ("UniProt", "P0DTC2.1") in pairs
        assert ("NCBI Protein", "BCN86353.1") in pairs
        assert ("NCBI Protein", "QHD43416.1") in pairs  # not mislabelled as UniProt
        assert ("UniProt", "QHD43416.1") not in pairs
        assert ("NCBITaxon", "NCBITaxon:2697049") in pairs
        assert ("NCBITaxon", "NCBITaxon:9606") in pairs
        assert ("PDB", "7N1A") in pairs
        assert ("ChEBI", "CHEBI:15377") in pairs and ("ChEBI", "CHEBI:16236") in pairs
        assert len([p for p in pairs if p[0] == "PubMed"]) == 25
        assert len(pairs) == len(set(pairs))
        assert all(
            m["fromId"] == "IEDB_EPITOPE:1309147" and m["fromSource"] == "IEDB" for m in maps
        )
        assert {m["mappingType"] for m in maps} == {"xref"}

    @pytest.mark.asyncio
    async def test_antigen(self, adapter):
        with Router(antigen_search=fx.ANTIGEN_SPIKE).patched(adapter):
            maps = await adapter.get_mappings("P0DTC2")
        assert [(m["fromId"], m["toSource"], m["toId"]) for m in maps] == [
            ("UNIPROT:P0DTC2", "UniProt", "P0DTC2"),
            ("UNIPROT:P0DTC2", "NCBITaxon", "NCBITaxon:2697049"),
        ]

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        with Router().patched(adapter):
            assert await adapter.get_mappings("spike") == []
            assert await adapter.get_mappings("99999999") == []
            assert await adapter.get_mappings("P99999") == []
        with Router(epitope_search=RuntimeError("boom")).patched(adapter):
            assert await adapter.get_mappings("1309147") == []


class TestTransport:
    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(iedb_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(iedb_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[])):
            await adapter._get("epitope_search", {})
            await adapter._get("epitope_search", {})
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6
