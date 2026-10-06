"""Unit tests for ICD10GMAdapter, using a tiny synthetic ClaML sample (no downloads)."""

import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import icd10gm_adapter
from knowledge_lookup.adapters.icd10gm_adapter import (
    ICD10GMAdapter,
    fold_accents,
    fold_translit,
    load_claml,
    normalise_code,
    parse_claml,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "icd10gm_claml_sample.xml"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "ICD10GM_CLAML_PATH",
        "ICD10GM_URL",
        "ICD10GM_YEAR",
        "ICD10GM_MEMBER",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, service: None)
    icd10gm_adapter._INDEX_CACHE.clear()


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv("ICD10GM_CLAML_PATH", str(SAMPLE))
    return ICD10GMAdapter(LookupConfig())


class TestFoldingAndCodes:
    def test_folding(self):
        assert fold_accents("Ermüdung") == "ermudung"
        assert fold_translit("Ermüdung") == "ermuedung"
        assert fold_accents("Größe") == "grosse"
        assert fold_translit("Größe") == "groesse"
        assert fold_translit("") == ""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("G93.3", "G93.3"),
            ("g933", "G93.3"),
            (" icd10gm:G93.3 ", "G93.3"),
            ("ICD-10-GM: u09.9", "U09.9"),
            ("G93.3†", "G93.3"),
            ("U09.9!", "U09.9"),
            ("R53", "R53"),
            ("G90-G99", "G90-G99"),
            ("vi", "VI"),
            ("", ""),
        ],
    )
    def test_normalise_code(self, raw, expected):
        assert normalise_code(raw) == expected


class TestParser:
    def test_parse_sample(self):
        with SAMPLE.open("rb") as stream:
            index = parse_claml(stream)
        assert index.version == "2099"
        assert len(index.classes) == 14
        g933 = index.get("g93.3")
        assert g933.kind == "category"
        assert g933.label == "Chronisches Fatigue-Syndrom"
        assert g933.parents == ["G93"]
        assert [t for t, _ in g933.inclusions] == [
            "Myalgische Enzephalomyelitis",
            "Postvirales Müdigkeitssyndrom",
        ]
        # references via text content and via the code attribute
        assert [refs for _, refs in g933.exclusions] == [("F48.0",), ("R53",)]
        assert g933.notes == ["Nur bei gesicherter Diagnose zu verwenden."]
        assert index.get("VI").children == ["G90-G99"]
        assert index.get("U09.9").usage == "aster"

    def test_path(self):
        with SAMPLE.open("rb") as stream:
            index = parse_claml(stream)
        assert [c.code for c in index.path("G93.3")] == ["VI", "G90-G99", "G93", "G93.3"]
        assert index.path("NOPE") == []

    def test_path_survives_cycles(self):
        xml = (
            b"<ClaML><Class code='A' kind='category'><SuperClass code='B'/>"
            b"<Rubric kind='preferred'><Label>a</Label></Rubric></Class>"
            b"<Class code='B' kind='category'><SuperClass code='A'/>"
            b"<Rubric kind='preferred'><Label>b</Label></Rubric></Class></ClaML>"
        )
        index = parse_claml(io.BytesIO(xml))
        assert [c.code for c in index.path("A")] == ["B", "A"]

    def test_namespace_codeless_class_and_preferred_long(self):
        xml = (
            b'<ClaML xmlns="http://example.org/claml">'
            b"<Class kind='category'><Rubric kind='preferred'><Label>x</Label></Rubric></Class>"
            b"<Class code='Z99.1' kind='category'>"
            b"<Rubric kind='preferredLong'><Label>Lange Bezeichnung</Label></Rubric>"
            b"<Rubric kind='note'><Label/></Rubric>"
            b"<Rubric kind='text'><Label>ignored</Label></Rubric>"
            b"<Rubric kind='inclusion'/>"
            b"<SuperClass code=''/><SubClass code=''/>"
            b"</Class></ClaML>"
        )
        index = parse_claml(io.BytesIO(xml))
        assert [c.code for c in index.classes] == ["Z99.1"]
        cls = index.get("Z99.1")
        assert cls.label == "Lange Bezeichnung"  # falls back to the long label
        assert cls.notes == [] and cls.inclusions == []

    def test_large_documents_clear_root(self):
        classes = "".join(
            f"<Class code='A{n:02d}' kind='category'>"
            f"<Rubric kind='preferred'><Label>t{n}</Label></Rubric></Class>"
            for n in range(60)
        )
        padded = "<ClaML>" + "<Meta name='m' value='v'/>" * 600 + classes + "</ClaML>"
        assert len(parse_claml(io.BytesIO(padded.encode())).classes) == 60

    def test_load_claml_zip_and_errors(self, tmp_path):
        archive = tmp_path / "icd10gm2099syst-claml.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("readme.xml", "<x/>")
            z.write(SAMPLE, "claml_icd10gm2099.xml")
            z.writestr("ClaML.dtd", "<!-- dtd -->")
        assert len(load_claml(archive).classes) == 14

        no_claml_name = tmp_path / "other.zip"
        with zipfile.ZipFile(no_claml_name, "w") as z:
            z.write(SAMPLE, "export.xml")
        assert len(load_claml(no_claml_name).classes) == 14

        empty = tmp_path / "empty.zip"
        with zipfile.ZipFile(empty, "w") as z:
            z.writestr("note.txt", "no xml")
        with pytest.raises(ValueError):
            load_claml(empty)
        assert len(load_claml(SAMPLE).classes) == 14


class TestAvailability:
    def test_unconfigured(self):
        assert ICD10GMAdapter(LookupConfig()).is_available() is False

    def test_path_url_and_config_key(self, monkeypatch):
        monkeypatch.setenv("ICD10GM_CLAML_PATH", "/data/claml.xml")
        assert ICD10GMAdapter(LookupConfig()).is_available() is True
        monkeypatch.delenv("ICD10GM_CLAML_PATH")
        monkeypatch.setenv("ICD10GM_URL", "https://mirror.example/icd.zip")
        assert ICD10GMAdapter(LookupConfig()).is_available() is True
        monkeypatch.delenv("ICD10GM_URL")
        monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, s: "/x.xml")
        assert ICD10GMAdapter(LookupConfig()).is_available() is True

    def test_blank_values_do_not_count(self, monkeypatch):
        monkeypatch.setenv("ICD10GM_CLAML_PATH", "   ")
        monkeypatch.setenv("ICD10GM_URL", "  ")
        assert ICD10GMAdapter(LookupConfig()).is_available() is False

    def test_source_and_lazy_construction(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ICD10GM
        assert adapter._index is None  # nothing is parsed or downloaded at construction


class TestSearch:
    @pytest.mark.asyncio
    async def test_exact_code(self, adapter):
        concepts = await adapter.search_concepts("G93.3")
        assert concepts[0].primary_id == "G93.3"
        assert concepts[0].primary_label == "Chronisches Fatigue-Syndrom"
        assert concepts[0].confidence_score == 1.0
        assert concepts[0].concept_type == ConceptType.DISEASE
        assert concepts[0].labels == {"de": "Chronisches Fatigue-Syndrom"}
        assert concepts[0].synonyms == [
            "Myalgische Enzephalomyelitis",
            "Postvirales Müdigkeitssyndrom",
        ]

    @pytest.mark.asyncio
    async def test_dotless_lowercase_and_curie(self, adapter):
        for query in ("g933", "ICD10GM:G93.3", "G93.3†"):
            assert (await adapter.search_concepts(query))[0].primary_id == "G93.3"

    @pytest.mark.asyncio
    async def test_prefix_search_skips_chapters_and_respects_limit(self, adapter):
        codes = [c.primary_id for c in await adapter.search_concepts("G93")]
        assert codes == ["G93", "G93.2", "G93.3"]  # exact first, then prefix matches
        assert len(await adapter.search_concepts("G93", limit=2)) == 2
        assert await adapter.search_concepts("G93", limit=0) == []

    @pytest.mark.asyncio
    async def test_block_and_chapter_codes(self, adapter):
        block = await adapter.search_concepts("G90-G99")
        assert block[0].primary_id == "G90-G99"
        assert block[0].semantic_types == ["block"]
        assert (await adapter.search_concepts("VI"))[0].primary_id == "VI"

    @pytest.mark.asyncio
    async def test_text_search_is_case_and_umlaut_insensitive(self, adapter):
        for query in ("fatigue", "FATIGUE", "chronisches fatigue-syndrom"):
            assert (await adapter.search_concepts(query))[0].primary_id == "G93.3"
        for query in ("Ermüdung", "ermudung", "ERMUEDUNG", "Ermuedung"):
            ids = [c.primary_id for c in await adapter.search_concepts(query)]
            assert "R53" in ids, query
        assert "G93.3" in [c.primary_id for c in await adapter.search_concepts("Müdigkeit")]

    @pytest.mark.asyncio
    async def test_ranking(self, adapter):
        concepts = await adapter.search_concepts("Unwohlsein und Ermüdung")
        assert concepts[0].primary_id == "R53"  # exact title beats others
        assert concepts[0].concept_type == ConceptType.SYMPTOM  # R chapter
        starts = await adapter.search_concepts("Chronisches")
        assert starts[0].primary_id == "G93.3"
        assert starts[0].confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_inclusion_term_and_multi_token(self, adapter):
        concepts = await adapter.search_concepts("Myalgische Enzephalomyelitis")
        assert concepts[0].primary_id == "G93.3"
        assert concepts[0].confidence_score == 0.6
        tokens = await adapter.search_concepts("Syndrom Fatigue")  # any order
        assert tokens[0].primary_id == "G93.3"
        assert tokens[0].confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_no_results_and_blank(self, adapter):
        assert await adapter.search_concepts("Zahnschmerzen") == []
        assert await adapter.search_concepts("Z99.9") == []
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts("???") == []

    @pytest.mark.asyncio
    async def test_title_search_limit(self, adapter):
        assert len(await adapter.search_concepts("e", limit=3)) == 3


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_with_hierarchy(self, adapter):
        concept = await adapter.get_concept_details("G93.3")
        assert concept.primary_id == "G93.3"
        assert concept.parents == ["G93"]
        assert concept.children == []
        assert concept.categories == [
            "chapter:VI Krankheiten des Nervensystems",
            "block:G90-G99 Sonstige Krankheiten des Nervensystems",
            "category:G93 Sonstige Krankheiten des Gehirns",
        ]
        data = concept.source_data[KnowledgeSource.ICD10GM]
        assert [h["code"] for h in data["hierarchy"]] == ["VI", "G90-G99", "G93", "G93.3"]
        assert data["version"] == "2099"
        assert data["exclusions"][0].startswith("Neurasthenie")
        assert data["notes"] == ["Nur bei gesicherter Diagnose zu verwenden."]

    @pytest.mark.asyncio
    async def test_details_variants_and_unknown(self, adapter):
        assert (await adapter.get_concept_details("g933")).primary_id == "G93.3"
        assert (await adapter.get_concept_details("ICD10GM:U09.9")).semantic_types == [
            "category",
            "aster",
        ]
        assert await adapter.get_concept_details("Q99.9") is None
        assert await adapter.get_concept_details("") is None

    @pytest.mark.asyncio
    async def test_long_label_becomes_definition(self, tmp_path, monkeypatch):
        xml = tmp_path / "c.xml"
        xml.write_text(
            "<ClaML><Class code='A00' kind='category'>"
            "<Rubric kind='preferred'><Label>Kurz</Label></Rubric>"
            "<Rubric kind='preferredLong'><Label>Lang</Label></Rubric></Class></ClaML>"
        )
        monkeypatch.setenv("ICD10GM_CLAML_PATH", str(xml))
        concept = await ICD10GMAdapter(LookupConfig()).get_concept_details("A00")
        assert concept.definitions == ["Lang"]


class TestRelationships:
    @pytest.mark.asyncio
    async def test_parents_children_and_references(self, adapter):
        rels = await adapter.get_relationships("G93.3")
        assert {(r["relation_label"], r["related_id"]) for r in rels} == {
            ("is_a", "G93"),
            ("excludes", "F48.0"),
            ("excludes", "R53"),
        }
        parent = next(r for r in rels if r["relation_label"] == "is_a")
        assert parent == {
            "relation_label": "is_a",
            "related_id": "G93",
            "related_name": "Sonstige Krankheiten des Gehirns",
            "source": "ICD10GM",
        }

    @pytest.mark.asyncio
    async def test_children_and_limit(self, adapter):
        rels = await adapter.get_relationships("G93")
        assert [r["related_id"] for r in rels if r["relation_label"] == "has_subtype"] == [
            "G93.2",
            "G93.3",
        ]
        limited = await adapter.get_relationships("G93", limit=1)
        assert [r["related_id"] for r in limited if r["relation_label"] == "has_subtype"] == [
            "G93.2"
        ]

    @pytest.mark.asyncio
    async def test_dangling_references_keep_the_code(self, adapter):
        index = await adapter._ensure_index()
        index.by_code["R53"].exclusions.append(("Fatigue (Z99.9)", ("Z99.9",)))
        rels = await adapter.get_relationships("R53")
        assert {"relation_label": "excludes", "related_id": "G93.3"}.items() <= next(
            r for r in rels if r["related_id"] == "G93.3"
        ).items()
        dangling = next(r for r in rels if r["related_id"] == "Z99.9")
        assert dangling["related_name"] == "Z99.9"

    @pytest.mark.asyncio
    async def test_unknown_code(self, adapter):
        assert await adapter.get_relationships("Q99.9") == []
        assert await adapter.get_relationships("") == []


class TestLoading:
    @pytest.mark.asyncio
    async def test_missing_file_degrades_gracefully(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ICD10GM_CLAML_PATH", str(tmp_path / "missing.xml"))
        adapter = ICD10GMAdapter(LookupConfig())
        assert await adapter.search_concepts("fatigue") == []
        assert await adapter.get_concept_details("G93.3") is None
        assert await adapter.get_relationships("G93.3") == []

    @pytest.mark.asyncio
    async def test_corrupt_file(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text("<ClaML><Class")
        monkeypatch.setenv("ICD10GM_CLAML_PATH", str(bad))
        assert await ICD10GMAdapter(LookupConfig()).search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_unconfigured_returns_empty(self):
        assert await ICD10GMAdapter(LookupConfig()).search_concepts("fatigue") == []

    @pytest.mark.asyncio
    async def test_index_is_built_once_and_shared(self, adapter, monkeypatch):
        calls = []
        real = icd10gm_adapter.load_claml
        monkeypatch.setattr(icd10gm_adapter, "load_claml", lambda p: calls.append(p) or real(p))
        await adapter.search_concepts("G93")
        await adapter.search_concepts("R53")
        other = ICD10GMAdapter(LookupConfig())
        await other.search_concepts("U09")
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_config_key_path(self, monkeypatch):
        monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, s: str(SAMPLE))
        concepts = await ICD10GMAdapter(LookupConfig()).search_concepts("U09.9")
        assert concepts[0].primary_id == "U09.9"

    @pytest.mark.asyncio
    async def test_url_mode_uses_dataset_cache_lazily(self, monkeypatch):
        monkeypatch.setenv("ICD10GM_URL", "https://mirror.example/icd10gm{year}.zip")
        monkeypatch.setenv("ICD10GM_YEAR", "2099")
        monkeypatch.setenv("ICD10GM_MEMBER", "claml_icd10gm2099.xml")
        ensure = AsyncMock(return_value=SAMPLE)
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", ensure):
            adapter = ICD10GMAdapter(LookupConfig())
            ensure.assert_not_awaited()  # never at construction
            assert adapter.is_available() is True
            assert ensure.await_count == 0
            concepts = await adapter.search_concepts("G93.3")
        assert concepts[0].primary_id == "G93.3"
        ensure.assert_awaited_once()
        assert ensure.await_args.args == ("https://mirror.example/icd10gm2099.zip",)
        assert ensure.await_args.kwargs["member"] == "claml_icd10gm2099.xml"
        assert ensure.await_args.kwargs["filename"] == "icd10gm2099_claml.xml"
        assert ensure.await_args.kwargs["max_age_days"] is None

    @pytest.mark.asyncio
    async def test_url_mode_download_failure(self, monkeypatch):
        monkeypatch.setenv("ICD10GM_URL", "https://mirror.example/icd.zip")
        with patch(
            "knowledge_lookup.utils.dataset_cache.ensure_dataset",
            AsyncMock(side_effect=OSError("offline")),
        ):
            assert await ICD10GMAdapter(LookupConfig()).search_concepts("fatigue") == []
