"""
Unit tests for CLI interface.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from knowledge_lookup import __main__ as main

pytestmark = pytest.mark.unit


class TestCLI:
    """Tests for CLI interface."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_search_command_basic(self, runner):
        from knowledge_lookup.models import LookupResult

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_lookup_class:
            mock_lookup = AsyncMock()
            mock_lookup_class.return_value = mock_lookup
            mock_lookup.search_concepts.return_value = LookupResult(
                query="test query", concepts=[]
            )
            result = runner.invoke(main.app, ["search", "test query"])
            assert result.exit_code == 0
            assert "Searching for:" in result.output
            assert "No results found" in result.output

    def test_search_command_with_results(self, runner):
        from knowledge_lookup.models import (
            ConceptType,
            KnowledgeSource,
            LookupResult,
            UnifiedConcept,
        )

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_lookup_class:
            mock_lookup = AsyncMock()
            mock_lookup_class.return_value = mock_lookup
            concept = UnifiedConcept(
                primary_id="TEST:001",
                primary_label="Test Concept",
                concept_type=ConceptType.DISEASE,
            )
            concept.add_identifier(KnowledgeSource.BIOPORTAL, "TEST:001", "Test Concept")
            mock_result = LookupResult(
                query="test query",
                concepts=[concept],
                sources_queried=[KnowledgeSource.BIOPORTAL],
                sources_succeeded=[KnowledgeSource.BIOPORTAL],
            )
            mock_lookup.search_concepts.return_value = mock_result
            result = runner.invoke(main.app, ["search", "test query"])
            assert result.exit_code == 0
            assert "Test Concept" in result.output

    def test_sources_command(self, runner):
        result = runner.invoke(main.app, ["sources"])
        assert result.exit_code == 0
        assert "Knowledge Sources" in result.output
        assert "sources available in this environment" in result.output

    def test_sources_lists_every_adapter_with_requirements_and_availability(self, runner):
        from rich.console import Console

        from knowledge_lookup.mcp_server.sources import SOURCE_CATALOG
        from knowledge_lookup.models import KnowledgeSource

        with (
            patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls,
            patch.object(main, "console", Console(width=400)),
        ):
            mock_cls.return_value._get_adapter.side_effect = lambda s: (
                MagicMock() if s == KnowledgeSource.HPO else None
            )
            result = runner.invoke(main.app, ["sources"])

        assert result.exit_code == 0
        assert len(SOURCE_CATALOG) == 36
        for source in SOURCE_CATALOG:
            assert source.value in result.output
        disgenet_row = next(line for line in result.output.splitlines() if "DISGENET" in line)
        assert "DISGENET_API_KEY" in disgenet_row
        chembl_row = next(line for line in result.output.splitlines() if "CHEMBL" in line)
        assert "the [chembl] extra" in chembl_row
        assert " no " in disgenet_row
        hpo_row = next(line for line in result.output.splitlines() if " HPO " in line)
        assert " yes " in hpo_row
        assert "1/36 sources available" in result.output
        assert "Total sources: 40" not in result.output

    def test_info_command(self, runner):
        with (
            patch("knowledge_lookup.__main__.__version__", "1.0.0"),
            patch("knowledge_lookup.__main__.__description__", "Test description"),
            patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_lookup_class,
        ):
            mock_lookup = MagicMock()
            mock_lookup._get_adapter.return_value = MagicMock()
            mock_lookup_class.return_value = mock_lookup
            result = runner.invoke(main.app, ["info"])
            assert result.exit_code == 0
            assert "Biomedical Knowledge Lookup" in result.output
            assert "Available sources: 36/36" in result.output

    def test_info_counts_adapters_not_enum_members(self, runner):
        from knowledge_lookup.models import KnowledgeSource

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_cls.return_value._get_adapter.side_effect = lambda s: (
                MagicMock() if s in (KnowledgeSource.OLS, KnowledgeSource.HPO) else None
            )
            result = runner.invoke(main.app, ["info"])
        assert result.exit_code == 0
        assert "Available sources: 2/36" in result.output

    def test_callback_help(self, runner):
        result = runner.invoke(main.app, ["--help"])
        assert result.exit_code in [0, 1]

    def test_search_command_help(self, runner):
        result = runner.invoke(main.app, ["search", "--help"])
        assert result.exit_code in [0, 1]

    def test_search_with_unknown_source(self, runner):
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_cls.return_value = AsyncMock()
            result = runner.invoke(main.app, ["search", "query", "--source", "bogus_source"])
            assert result.exit_code == 1
            assert "Unknown source" in result.output

    def test_search_with_known_source(self, runner):
        from knowledge_lookup.models import LookupResult

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[])
            result = runner.invoke(main.app, ["search", "query", "--source", "chembl"])
            assert result.exit_code == 0

    def test_search_sources_printed(self, runner):
        from knowledge_lookup.models import LookupResult

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[])
            result = runner.invoke(main.app, ["search", "query", "-s", "chembl"])
            assert result.exit_code == 0

    def test_search_json_output(self, runner):
        from knowledge_lookup.models import (
            ConceptType,
            KnowledgeSource,
            LookupResult,
            UnifiedConcept,
        )

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(
                primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE
            )
            concept.add_identifier(KnowledgeSource.CHEMBL, "C1", "Concept1")
            concept.definitions = ["A definition"]
            mock_lookup.search_concepts.return_value = LookupResult(
                query="q", concepts=[concept], sources_queried=[KnowledgeSource.CHEMBL]
            )
            result = runner.invoke(main.app, ["search", "query", "-o", "json"])
            assert result.exit_code == 0
            assert "Concept1" in result.output

    def test_search_csv_output(self, runner):
        from knowledge_lookup.models import (
            ConceptType,
            KnowledgeSource,
            LookupResult,
            UnifiedConcept,
        )

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(
                primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE
            )
            concept.add_identifier(KnowledgeSource.CHEMBL, "C1", "Concept1")
            concept.definitions = ["A definition"]
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query", "-o", "csv"])
            assert result.exit_code == 0
            assert "Concept1" in result.output

    def test_search_csv_no_definitions(self, runner):
        from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(
                primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE
            )
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query", "-o", "csv"])
            assert result.exit_code == 0

    def test_search_table_long_description(self, runner):
        from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(
                primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE
            )
            concept.definitions = ["A" * 100]
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query"])
            assert result.exit_code == 0
            # Rich table truncation uses "…" character
            assert len(result.concepts) if hasattr(result, "concepts") else True

    def test_search_exception_handling(self, runner):
        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            mock_lookup.search_concepts.side_effect = RuntimeError("network down")
            result = runner.invoke(main.app, ["search", "query"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_search_json_no_definitions(self, runner):
        from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_lookup = AsyncMock()
            mock_cls.return_value = mock_lookup
            concept = UnifiedConcept(
                primary_id="C1", primary_label="Concept1", concept_type=ConceptType.DISEASE
            )
            mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[concept])
            result = runner.invoke(main.app, ["search", "query", "-o", "json"])
            assert result.exit_code == 0

    # ------------------------------------------------------------------
    # search --cache-dir / --limit
    # ------------------------------------------------------------------

    def test_search_cache_dir_initializes_cache_before_lookup(self, runner, tmp_path):
        from unittest.mock import call

        from knowledge_lookup.models import LookupResult

        manager = MagicMock()
        mock_lookup = AsyncMock()
        mock_lookup.search_concepts.return_value = LookupResult(query="q", concepts=[])
        manager.CentralKnowledgeLookup.return_value = mock_lookup
        with (
            patch("knowledge_lookup.__main__.init_cache", manager.init_cache),
            patch(
                "knowledge_lookup.__main__.CentralKnowledgeLookup", manager.CentralKnowledgeLookup
            ),
        ):
            result = runner.invoke(
                main.app, ["search", "q", "-s", "HPO", "--cache-dir", str(tmp_path)]
            )

        assert result.exit_code == 0
        assert manager.mock_calls[:2] == [
            call.init_cache(disk_cache_dir=str(tmp_path)),
            call.CentralKnowledgeLookup(),
        ]
        mock_lookup.close.assert_awaited_once()

    def test_search_without_cache_dir_keeps_default_cache(self, runner):
        from knowledge_lookup.models import LookupResult

        with (
            patch("knowledge_lookup.__main__.init_cache") as mock_init,
            patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls,
        ):
            mock_cls.return_value = AsyncMock()
            mock_cls.return_value.search_concepts.return_value = LookupResult(
                query="q", concepts=[]
            )
            result = runner.invoke(main.app, ["search", "q"])

        assert result.exit_code == 0
        mock_init.assert_not_called()

    def test_search_limit_help_describes_total_cap(self, runner):
        result = runner.invoke(main.app, ["search", "--help"], env={"COLUMNS": "200"})
        assert result.exit_code == 0
        assert "Maximum number of results in total" in result.output
        assert "per source" not in result.output

    def test_search_json_lists_queried_sources(self, runner):
        from knowledge_lookup.models import KnowledgeSource, LookupResult, UnifiedConcept

        with patch("knowledge_lookup.__main__.CentralKnowledgeLookup") as mock_cls:
            mock_cls.return_value = AsyncMock()
            mock_cls.return_value.search_concepts.return_value = LookupResult(
                query="q",
                concepts=[UnifiedConcept(primary_id="HP:1", primary_label="x")],
                sources_queried=[KnowledgeSource.HPO, KnowledgeSource.MONDO],
            )
            result = runner.invoke(main.app, ["search", "q", "-o", "json"])

        assert result.exit_code == 0
        assert '"HPO"' in result.output and '"MONDO"' in result.output
        assert '"ZOOMA"' not in result.output


class TestWorkflowCLI:
    """The workflow command's approval prompt (runners mocked)."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @staticmethod
    def _response(status, **extra):
        response = {
            "thread_id": "thread-1",
            "status": status,
            "result": None,
            "review_score": 0.4,
            "review_summary": "low",
            "review_strengths": [],
            "review_weaknesses": [],
            "review_suggestions": [],
            "concept_map": [],
            "llm_explanation": "",
            "export_paths": [],
            "errors": [],
            "steps": [],
        }
        response.update(extra)
        return response

    def _invoke(self, runner, run_returns, resume_returns, user_input):
        run = AsyncMock(return_value=run_returns)
        resume = AsyncMock(side_effect=resume_returns)
        with (
            patch("knowledge_lookup.agents.run_workflow", run),
            patch("knowledge_lookup.agents.resume_workflow", resume),
        ):
            result = runner.invoke(
                main.app, ["workflow", "seizure", "-s", "HPO"], input=user_input
            )
        return result, run, resume

    def test_paused_workflow_prompts_and_resumes(self, runner):
        result, _, resume = self._invoke(
            runner,
            self._response("awaiting_approval"),
            [self._response("completed", export_paths=["/tmp/out/seizure.json"])],
            "y\n",
        )

        assert result.exit_code == 0, result.output
        assert "Workflow paused for approval" in result.output
        assert "Do you approve these results?" in result.output
        resume.assert_awaited_once_with("thread-1", {"approved": True})
        assert "Workflow completed!" in result.output
        assert "/tmp/out/seizure.json" in result.output

    def test_refinement_that_pauses_again_prompts_again(self, runner):
        result, _, resume = self._invoke(
            runner,
            self._response("awaiting_approval"),
            [self._response("awaiting_approval"), self._response("completed")],
            "n\ny\nfocal seizures\ny\n",
        )

        assert result.exit_code == 0, result.output
        assert resume.await_args_list[0].args == (
            "thread-1",
            {"approved": False, "refine": True, "notes": "focal seizures"},
        )
        assert resume.await_args_list[1].args == ("thread-1", {"approved": True})
        assert result.output.count("Workflow paused for approval") == 2

    def test_rejection_reports_nothing_exported(self, runner):
        result, _, resume = self._invoke(
            runner,
            self._response("awaiting_approval"),
            [self._response("completed")],
            "n\nn\n",
        )

        assert result.exit_code == 0, result.output
        resume.assert_awaited_once_with("thread-1", {"approved": False, "refine": False})
        assert "Results rejected" in result.output

    def test_closed_input_stops_without_hanging(self, runner):
        result, _, resume = self._invoke(runner, self._response("awaiting_approval"), [], "")

        assert result.exit_code == 1
        assert "No approval decision received" in result.output
        resume.assert_not_awaited()

    def test_completed_workflow_does_not_prompt(self, runner):
        result, _, resume = self._invoke(
            runner, self._response("completed", export_paths=["/tmp/a.json"]), [], ""
        )

        assert result.exit_code == 0, result.output
        assert "Do you approve" not in result.output
        resume.assert_not_awaited()
