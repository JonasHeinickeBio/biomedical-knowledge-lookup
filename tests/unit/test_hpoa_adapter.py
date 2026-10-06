"""
Unit tests for HPOAAdapter and the phenotype.hpoa parser.

The parser is exercised on lines taken from the live file's first 64 KiB (REAL_SAMPLE) plus a
few documented-format rows for cases the sample does not contain (NOT, percentages, ORPHA).
No test downloads anything.
"""

import gzip
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import hpoa_adapter
from knowledge_lookup.adapters._pheno_common import parse_frequency
from knowledge_lookup.adapters.hpoa_adapter import HPOAAdapter, parse_hpoa
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import hpoa_sample as fx

pytestmark = pytest.mark.unit

HEADER_ROW = (
    "database_id\tdisease_name\tqualifier\thpo_id\treference\tevidence\tonset\tfrequency\t"
    "sex\tmodifier\taspect\tbiocuration"
)


@pytest.fixture
def hpoa_file(tmp_path):
    path = tmp_path / "phenotype.hpoa"
    text = fx.REAL_SAMPLE + "\n".join(fx.CONSTRUCTED_ROWS) + "\n" + fx.TRUNCATED_LINE
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def adapter(lookup_config, hpoa_file, monkeypatch):
    monkeypatch.setenv("HPOA_PATH", str(hpoa_file))
    return HPOAAdapter(lookup_config)


class TestParser:
    def test_header_metadata_and_counts(self, hpoa_file):
        index = parse_hpoa(hpoa_file)
        assert index.metadata["version"] == "2026-09-02"
        assert index.metadata["hpo-version"].endswith("hp.json")
        assert "HPO annotations for rare diseases" in index.metadata["description"]
        assert {"OMIM:619340", "OMIM:612567", "OMIM:117650", "OMIM:154700"} <= set(index.names)
        assert "ORPHA:2105" in index.names and "DECIPHER:5" in index.names
        # truncated final line (only 2 columns) is skipped, and the column header is not a row
        assert "OMIM:204870" not in index.names
        assert "database_id" not in index.names

    def test_row_fields(self, hpoa_file):
        index = parse_hpoa(hpoa_file)
        row = next(r for r in index.by_disease["OMIM:612567"] if r.hpo_id == "HP:0000143")
        assert row.disease_name.startswith("Inflammatory bowel disease 25")
        assert row.reference == "PMID:19890111" and row.evidence == "PCS"
        assert row.onset == "HP:0003593" and row.frequency == "1/1" and row.sex == "FEMALE"
        assert row.aspect == "P" and row.negated is False
        assert row.biocuration.startswith("HPO:probinson")

    def test_not_qualifier_and_indexes(self, hpoa_file):
        index = parse_hpoa(hpoa_file)
        row = next(r for r in index.by_hpo["HP:0001250"] if r.disease_id == "ORPHA:2105")
        assert row.negated is True
        assert {r.disease_id for r in index.by_hpo["HP:0001250"]} == {"ORPHA:2105", "DECIPHER:5"}

    def test_gzip_and_short_rows(self, tmp_path):
        path = tmp_path / "x.hpoa.gz"
        short = "OMIM:1\tName\t\tHP:0000001"  # only four columns
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write("#version: v\n" + HEADER_ROW + "\n" + short + "\n\nnot-a-row\tx\n")
        index = parse_hpoa(path)
        assert index.metadata["version"] == "v"
        (row,) = index.by_disease["OMIM:1"]
        assert row.frequency == "" and row.aspect == ""

    def test_disease_name_with_quotes(self, tmp_path):
        path = tmp_path / "q.hpoa"
        path.write_text(
            f'{HEADER_ROW}\nOMIM:2\t"Quoted" disease, type 1\t\tHP:0000002\t\t\t\t\t\t\tP\t\n'
        )
        assert parse_hpoa(path).names["OMIM:2"] == '"Quoted" disease, type 1'


class TestFrequencyParsing:
    @pytest.mark.parametrize(
        "raw, fraction, label, term",
        [
            ("HP:0040280", 1.0, "Obligate", "HP:0040280"),
            ("HP:0040281", 0.9, "Very frequent", "HP:0040281"),
            ("HP:0040282", 0.55, "Frequent", "HP:0040282"),
            ("HP:0040283", 0.17, "Occasional", "HP:0040283"),
            ("HP:0040284", 0.025, "Very rare", "HP:0040284"),
            ("HP:0040285", 0.0, "Excluded", "HP:0040285"),
            ("hp:0040281", 0.9, "Very frequent", "HP:0040281"),
            ("3/7", 3 / 7, "3/7", None),
            ("2/2", 1.0, "2/2", None),
            ("0/3", 0.0, "0/3", None),
            ("47.9%", 0.479, "47.9%", None),
            (" 30 % ", 0.3, "30 %", None),
            ("1/0", None, "1/0", None),
            ("some text", None, "some text", None),
        ],
    )
    def test_parse(self, raw, fraction, label, term):
        freq = parse_frequency(raw)
        assert freq.fraction == (pytest.approx(fraction) if fraction is not None else None)
        assert freq.label == label
        assert freq.term == term
        assert freq.raw == raw.strip()

    def test_empty(self):
        assert parse_frequency("") is None
        assert parse_frequency("   ") is None
        assert parse_frequency(None) is None


class TestAvailabilityAndLoading:
    def test_source_and_availability(self, adapter, tmp_path, monkeypatch):
        assert adapter.get_source() == KnowledgeSource.HPOA
        assert adapter.is_available() is True  # HPOA_PATH points at a real file
        monkeypatch.setenv("HPOA_PATH", str(tmp_path / "missing.hpoa"))
        assert adapter.is_available() is False
        monkeypatch.delenv("HPOA_PATH")
        assert adapter.is_available() is True  # default path downloads on first use

    def test_construction_never_loads_or_downloads(self, lookup_config, monkeypatch):
        monkeypatch.delenv("HPOA_PATH", raising=False)
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset") as ensure:
            created = HPOAAdapter(lookup_config)
            assert created._index is None
            ensure.assert_not_called()

    @pytest.mark.asyncio
    async def test_downloads_lazily_once_via_dataset_cache(
        self, lookup_config, hpoa_file, monkeypatch
    ):
        monkeypatch.delenv("HPOA_PATH", raising=False)
        adapter = HPOAAdapter(lookup_config)
        ensure = AsyncMock(return_value=hpoa_file)
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", ensure):
            assert await adapter.search_concepts("marfan")
            assert await adapter.get_concept_details("OMIM:154700")
        ensure.assert_awaited_once()
        assert ensure.await_args.args[0] == hpoa_adapter.HPOA_URL
        assert ensure.await_args.kwargs["filename"] == "phenotype.hpoa"

    @pytest.mark.asyncio
    async def test_load_failure_returns_empty_and_retries_next_call(
        self, lookup_config, hpoa_file, monkeypatch
    ):
        monkeypatch.delenv("HPOA_PATH", raising=False)
        adapter = HPOAAdapter(lookup_config)
        ensure = AsyncMock(side_effect=[OSError("offline"), hpoa_file])
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", ensure):
            assert await adapter.search_concepts("marfan") == []
            assert await adapter.search_concepts("marfan")  # second attempt succeeds

    @pytest.mark.asyncio
    async def test_every_method_degrades_when_data_unavailable(self, lookup_config, monkeypatch):
        monkeypatch.delenv("HPOA_PATH", raising=False)
        adapter = HPOAAdapter(lookup_config)
        ensure = AsyncMock(side_effect=OSError("offline"))
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", ensure):
            assert await adapter.get_concept_details("OMIM:154700") is None
            assert await adapter.get_relationships("OMIM:154700") == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_name_substring_case_insensitive(self, adapter):
        concepts = await adapter.search_concepts("MARFAN")
        assert [c.primary_id for c in concepts] == ["OMIM:154700"]
        concept = concepts[0]
        assert concept.primary_label == "Marfan syndrome"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.confidence_score == 0.9  # name prefix match
        assert KnowledgeSource.HPOA in concept.sources

    @pytest.mark.asyncio
    async def test_ranking_exact_prefix_word_substring(self, adapter):
        index = await adapter._ensure_index()
        for did, name in [
            ("OMIM:9001", "fatigue"),
            ("OMIM:9002", "Fatigue, chronic"),
            ("OMIM:9003", "Severe fatigue disorder"),
            ("OMIM:9004", "Antifatigue syndrome"),
        ]:
            index.names[did] = name
        index._lowered = None
        concepts = await adapter.search_concepts("fatigue")
        scores = {c.primary_id: c.confidence_score for c in concepts}
        assert scores["OMIM:9001"] == 1.0
        assert scores["OMIM:9002"] == 0.9
        assert scores["OMIM:9003"] == 0.8
        assert scores["OMIM:9004"] == 0.7
        assert concepts[0].primary_id == "OMIM:9001"
        assert concepts[1].primary_id == "OMIM:9002"

    @pytest.mark.asyncio
    async def test_search_by_disease_id_variants(self, adapter):
        for query in ("OMIM:154700", "omim:154700", "154700"):
            (concept,) = await adapter.search_concepts(query)
            assert concept.primary_id == "OMIM:154700"
        (orpha,) = await adapter.search_concepts("Orphanet:2105")
        assert orpha.primary_id == "ORPHA:2105"
        (decipher,) = await adapter.search_concepts("decipher:5")
        assert decipher.primary_id == "DECIPHER:5"

    @pytest.mark.asyncio
    async def test_search_by_hp_id_lists_non_excluded_diseases(self, adapter):
        concepts = await adapter.search_concepts("HP:0001250")
        assert {c.primary_id for c in concepts} == {"DECIPHER:5"}  # ORPHA:2105 has it as NOT

    @pytest.mark.asyncio
    async def test_limit_empty_and_no_match(self, adapter):
        assert len(await adapter.search_concepts("e", limit=2)) == 2
        assert await adapter.search_concepts("") == []
        assert await adapter.search_concepts("zzzz-no-such-disease") == []
        assert await adapter.search_concepts("marfan", limit=0) == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_disease_details_summary(self, adapter):
        concept = await adapter.get_concept_details("OMIM:154700")
        assert concept.primary_id == "OMIM:154700"
        assert concept.primary_label == "Marfan syndrome"
        assert (KnowledgeSource.OMIM, "OMIM:154700") in {
            (i.source, i.identifier) for i in concept.identifiers
        }
        assert "hpoa:OMIM" in concept.categories
        data = concept.source_data[KnowledgeSource.HPOA]
        assert data["annotations"] == 4
        assert data["phenotypes"] == 2
        assert data["inheritance"] == ["HP:0000006"]
        assert data["hpoa_version"] == "2026-09-02"
        assert "PMID:28050285" in data["references"]

    @pytest.mark.asyncio
    async def test_excluded_phenotypes_counted(self, adapter):
        data = (await adapter.get_concept_details("ORPHA:2105")).source_data[KnowledgeSource.HPOA]
        assert data["excluded_phenotypes"] == 1 and data["phenotypes"] == 2

    @pytest.mark.asyncio
    async def test_non_omim_has_no_omim_identifier(self, adapter):
        concept = await adapter.get_concept_details("ORPHA:2105")
        assert {i.source for i in concept.identifiers} == {KnowledgeSource.HPOA}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cid", ["OMIM:0", "HP:0001250", "", "banana", "OMIM:", "ICD10:G93.3"])
    async def test_unknown_inputs(self, adapter, cid):
        assert await adapter.get_concept_details(cid) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_disease_to_phenotypes_with_frequency_sorted(self, adapter):
        rels = await adapter.get_relationships("OMIM:154700")
        assert [r["related_id"] for r in rels] == ["HP:0000768", "HP:0003179"]
        obligate, merged = rels
        assert obligate["relation_label"] == "has_phenotype"
        assert obligate["frequency"] == 1.0 and obligate["frequency_label"] == "Obligate"
        assert obligate["frequency_term"] == "HP:0040280"
        assert obligate["evidence"] == "TAS"
        assert obligate["evidence_label"] == "traceable author statement"
        assert obligate["source"] == "HPOA" and obligate["direction"] == "outgoing"
        assert obligate["related_name"] == "HP:0000768"  # file has no HPO labels
        # two rows for HP:0003179 (different references) are merged into one edge
        assert merged["references"] == ["PMID:28050285", "PMID:26339165"]
        assert merged["frequency"] == pytest.approx(0.479)
        assert merged["onset"] == "HP:0003581" and merged["onset_label"] == "Adult onset"

    @pytest.mark.asyncio
    async def test_numeric_frequency_from_fraction_and_percentage(self, adapter):
        rels = await adapter.get_relationships("OMIM:612567")
        edge = next(r for r in rels if r["related_id"] == "HP:0000143")
        assert edge["frequency"] == 1.0 and edge["frequency_raw"] == "1/1"
        assert edge["sex"] == "FEMALE" and edge["onset_label"] == "Infantile onset"
        pct = next(r for r in await adapter.get_relationships("DECIPHER:5"))
        assert pct["frequency"] == 0.3 and pct["frequency_raw"] == "30%"

    @pytest.mark.asyncio
    async def test_not_qualifier_and_term_frequency(self, adapter):
        rels = {r["related_id"]: r for r in await adapter.get_relationships("ORPHA:2105")}
        assert rels["HP:0001250"]["relation_label"] == "not_has_phenotype"
        assert rels["HP:0012378"]["frequency"] == 0.55
        assert rels["HP:0012378"]["frequency_label"] == "Frequent"
        # the NOT row has no frequency, so it sorts after the frequent ones
        assert list(rels)[-1] == "HP:0001250"

    @pytest.mark.asyncio
    async def test_modifier_is_reported(self, adapter):
        rels = await adapter.get_relationships("OMIM:117650")
        assert any(r.get("modifier") == "HP:0012828" for r in rels)

    @pytest.mark.asyncio
    async def test_aspect_filter(self, adapter):
        inheritance = await adapter.get_relationships("OMIM:154700", aspect="I")
        assert [(r["related_id"], r["relation_label"]) for r in inheritance] == [
            ("HP:0000006", "has_inheritance")
        ]
        everything = await adapter.get_relationships("OMIM:154700", aspect=None)
        assert {r["aspect"] for r in everything} == {"P", "I"}
        assert await adapter.get_relationships("OMIM:154700", aspect="c") == []
        course = await adapter.get_relationships("ORPHA:2105", aspect="i")
        assert course[0]["relation_label"] == "has_inheritance"

    @pytest.mark.asyncio
    async def test_phenotype_to_diseases(self, adapter):
        rels = await adapter.get_relationships("HP:0000768")
        assert [r["related_id"] for r in rels] == ["OMIM:154700"]
        edge = rels[0]
        assert edge["relation_label"] == "phenotype_of"
        assert edge["related_name"] == "Marfan syndrome"
        assert edge["direction"] == "incoming"
        negated = await adapter.get_relationships("hp:0001250")
        assert {(r["related_id"], r["relation_label"]) for r in negated} == {
            ("ORPHA:2105", "not_phenotype_of"),
            ("DECIPHER:5", "phenotype_of"),
        }

    @pytest.mark.asyncio
    async def test_phenotype_with_non_phenotype_aspect_label(self, adapter):
        rels = await adapter.get_relationships("HP:0000006", aspect="I")
        assert {r["relation_label"] for r in rels} == {"inheritance_of"}

    @pytest.mark.asyncio
    async def test_limit_and_bad_input(self, adapter):
        assert len(await adapter.get_relationships("OMIM:612567", limit=1)) == 1
        assert await adapter.get_relationships("OMIM:612567", limit=0) == []
        assert await adapter.get_relationships("nonsense") == []
        assert await adapter.get_relationships("OMIM:424242") == []
        assert await adapter.get_relationships("HP:9999999") == []

    @pytest.mark.asyncio
    async def test_mappings_not_supported_returns_empty(self, adapter):
        assert await adapter.get_mappings("OMIM:154700") == []
