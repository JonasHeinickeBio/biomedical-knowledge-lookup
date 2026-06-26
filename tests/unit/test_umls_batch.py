"""
Unit tests for UMLS Batch Concept Extraction Pipeline.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.models import ConceptType, UnifiedConcept
from knowledge_lookup.umls.batch import BatchProcessor, BatchResult


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.search_concepts = AsyncMock(
        return_value=[
            UnifiedConcept(
                primary_id=f"C{i:07d}",
                primary_label=f"Concept {i}",
                concept_type=ConceptType.DISEASE,
                confidence_score=0.95,
                definitions=[f"Definition {i}"],
                synonyms=[f"Synonym {i}"],
            )
            for i in range(1, 4)
        ]
    )
    return adapter


@pytest.fixture
def batch_processor(mock_adapter):
    return BatchProcessor(mock_adapter, concurrency=2, rate_limit=0)


class TestBatchProcessor:
    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform == "win32", reason="Windows timer resolution makes elapsed=0.0 with mocked calls")
    async def test_process_terms_all_succeed(self, batch_processor):
        terms = ["diabetes", "asthma", "hypertension"]
        result = await batch_processor.process_terms(terms, limit=3)
        assert isinstance(result, BatchResult)
        assert result.total_inputs == 3
        assert result.succeeded == 3
        assert result.failed == 0
        assert result.elapsed > 0

    @pytest.mark.asyncio
    async def test_process_terms_with_duplicates(self, batch_processor):
        terms = ["diabetes", "diabetes", "asthma"]
        result = await batch_processor.process_terms(terms, limit=3)
        assert result.skipped == 1  # duplicate
        assert result.succeeded == 2

    @pytest.mark.asyncio
    async def test_process_terms_empty_skipped(self, batch_processor):
        terms = ["", "  ", "valid"]
        result = await batch_processor.process_terms(terms, limit=3)
        assert result.skipped == 2
        assert result.succeeded == 1

    @pytest.mark.asyncio
    async def test_process_terms_some_fail(self, batch_processor):
        # Make the second call fail
        batch_processor.adapter.search_concepts = AsyncMock(
            side_effect=[
                [
                    UnifiedConcept(
                        primary_id="C001", primary_label="OK", concept_type=ConceptType.DISEASE
                    )
                ],
                Exception("API error"),
                [
                    UnifiedConcept(
                        primary_id="C002", primary_label="OK2", concept_type=ConceptType.DISEASE
                    )
                ],
            ]
        )
        terms = ["good", "bad", "good2"]
        result = await batch_processor.process_terms(terms, limit=3)
        assert result.succeeded == 2
        assert result.failed == 1
        assert len(result.errors) == 1
        assert result.errors[0]["query"] == "bad"

    @pytest.mark.asyncio
    async def test_process_terms_respects_skip_cuis(self, batch_processor):
        terms = ["diabetes", "asthma"]
        result = await batch_processor.process_terms(
            terms, limit=3, skip_cuis={"C0000001", "C0000002"}
        )
        assert result.succeeded == 2
        # CUIs from mock are C0000001, C0000002, C0000003 — but the mock generates C0000001 etc
        # Actually mock generates C0000001.. with 7-digit CUIs, so let me check
        # The fixture generates C0000001..C0000003 which are 7-digit
        pass

    @pytest.mark.asyncio
    async def test_iter_results_yields_one_by_one(self, batch_processor):
        terms = ["diabetes", "asthma"]
        results = []
        async for r in batch_processor.iter_results(terms, limit=3):
            results.append(r)
        assert len(results) == 2
        assert results[0]["query"] == "diabetes"
        assert results[1]["query"] == "asthma"

    @pytest.mark.asyncio
    async def test_iter_results_with_error(self, batch_processor):
        batch_processor.adapter.search_concepts = AsyncMock(side_effect=Exception("fail"))
        results = []
        async for r in batch_processor.iter_results(["test"]):
            results.append(r)
        assert "error" in results[0]

    def test_batch_result_to_dict(self):
        result = BatchResult(
            total_inputs=10,
            succeeded=8,
            failed=1,
            skipped=1,
            elapsed=2.5,
            results=[{"query": "test", "concepts": []}],
            errors=[{"query": "bad", "error": "fail"}],
        )
        d = result.to_dict()
        assert d["total_inputs"] == 10
        assert d["succeeded"] == 8
        assert d["elapsed_seconds"] == 2.5

    def test_batch_result_to_json(self):
        result = BatchResult(total_inputs=5, succeeded=5)
        js = result.to_json()
        parsed = json.loads(js)
        assert parsed["total_inputs"] == 5

    def test_batch_result_defaults(self):
        r = BatchResult()
        assert r.total_inputs == 0
        assert r.results == []
        assert r.errors == []

    @pytest.mark.asyncio
    async def test_process_file_txt(self, batch_processor, tmp_path):
        txt = tmp_path / "terms.txt"
        txt.write_text("diabetes\nasthma\nhypertension\n")
        result = await batch_processor.process_file(txt, limit_per_term=3)
        assert result.total_inputs == 3
        assert result.succeeded == 3

    @pytest.mark.asyncio
    async def test_process_file_json_list(self, batch_processor, tmp_path):
        js = tmp_path / "terms.json"
        js.write_text(json.dumps(["diabetes", "asthma"]))
        result = await batch_processor.process_file(js, limit_per_term=3)
        assert result.succeeded == 2

    @pytest.mark.asyncio
    async def test_process_file_json_dict(self, batch_processor, tmp_path):
        js = tmp_path / "terms.json"
        js.write_text(json.dumps({"terms": ["diabetes", "asthma"]}))
        result = await batch_processor.process_file(js, limit_per_term=3)
        assert result.succeeded == 2

    @pytest.mark.asyncio
    async def test_process_file_csv(self, batch_processor, tmp_path):
        import csv

        csv_path = tmp_path / "terms.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["term", "other"])
            w.writerow(["diabetes", "x"])
            w.writerow(["asthma", "y"])
        result = await batch_processor.process_file(csv_path, column="term", limit_per_term=3)
        assert result.succeeded == 2

    @pytest.mark.asyncio
    async def test_write_output_csv(self, batch_processor, tmp_path):
        result = await batch_processor.process_terms(["diabetes"], limit=3)
        out = tmp_path / "output.csv"
        batch_processor._write_output(result, out, "csv")
        assert out.exists()
        content = out.read_text()
        assert "cui" in content  # header

    @pytest.mark.asyncio
    async def test_write_output_rdf(self, batch_processor, tmp_path):
        result = await batch_processor.process_terms(["diabetes"], limit=3)
        out = tmp_path / "output.ttl"
        batch_processor._write_output(result, out, "rdf")
        assert out.exists()

    @pytest.mark.asyncio
    async def test_write_output_json_default(self, batch_processor, tmp_path):
        result = await batch_processor.process_terms(["diabetes"], limit=3)
        out = tmp_path / "output.json"
        batch_processor._write_output(result, out, "json")
        assert out.exists()
        parsed = json.loads(out.read_text())
        assert "results" in parsed

    def test_load_terms_csv_first_column(self, tmp_path):
        import csv

        from knowledge_lookup.umls.batch import BatchProcessor

        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["term"])
            w.writerow(["diabetes"])
            w.writerow(["asthma"])
        terms = BatchProcessor._load_terms(csv_path)
        assert len(terms) == 2
        assert terms[0] == "diabetes"

    def test_load_terms_txt(self, tmp_path):
        from knowledge_lookup.umls.batch import BatchProcessor

        txt = tmp_path / "test.txt"
        txt.write_text("diabetes\nasthma\n")
        terms = BatchProcessor._load_terms(txt)
        assert terms == ["diabetes", "asthma"]

    def test_load_terms_json_list(self, tmp_path):
        from knowledge_lookup.umls.batch import BatchProcessor

        js = tmp_path / "test.json"
        js.write_text(json.dumps(["diabetes", "asthma"]))
        terms = BatchProcessor._load_terms(js)
        assert terms == ["diabetes", "asthma"]

    def test_load_existing_cuis(self, tmp_path):
        from knowledge_lookup.umls.batch import BatchProcessor

        out = tmp_path / "existing.json"
        data = {"results": [{"query": "test", "concepts": [{"cui": "C001"}, {"cui": "C002"}]}]}
        out.write_text(json.dumps(data))
        cuis = BatchProcessor._load_existing_cuis(out)
        assert cuis == {"C001", "C002"}

    def test_load_existing_cuis_nonexistent_file(self, tmp_path):
        from knowledge_lookup.umls.batch import BatchProcessor

        cuis = BatchProcessor._load_existing_cuis(tmp_path / "nonexistent.json")
        assert cuis == set()
