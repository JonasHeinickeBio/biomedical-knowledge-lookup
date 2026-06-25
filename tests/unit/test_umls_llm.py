"""
Unit tests for LLM-Augmented Concept Normalization.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.models import ConceptType, UnifiedConcept
from knowledge_lookup.umls.llm import (
    AnthropicBackend,
    LLMNormalizer,
    NormalizationResult,
    OpenAIBackend,
)


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.search_concepts = AsyncMock(
        return_value=[
            UnifiedConcept(
                primary_id="C0027051",
                primary_label="Myocardial Infarction",
                concept_type=ConceptType.DISEASE,
                confidence_score=0.95,
            ),
            UnifiedConcept(
                primary_id="C0011849",
                primary_label="Diabetes Mellitus",
                concept_type=ConceptType.DISEASE,
                confidence_score=0.85,
            ),
        ]
    )
    return adapter


@pytest.fixture
def mock_llm_backend():
    backend = MagicMock()
    backend.complete = AsyncMock(return_value="Myocardial Infarction")
    backend.close = AsyncMock()
    return backend


class TestNormalizationResult:
    def test_defaults(self):
        r = NormalizationResult(query="test")
        assert r.query == "test"
        assert r.cui is None
        assert r.confidence == 0.0
        assert r.method == "none"

    def test_full_result(self):
        r = NormalizationResult(
            query="heart attack",
            normalized_form="Myocardial Infarction",
            cui="C0027051",
            concept_name="Myocardial Infarction",
            confidence=0.95,
            method="llm_expanded",
            raw_llm_output="Myocardial Infarction",
        )
        assert r.cui == "C0027051"


class TestLLMNormalizer:
    @pytest.mark.asyncio
    async def test_normalize_direct(self, mock_adapter, mock_llm_backend):
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=False,
            prune_candidates=False,
        )
        result = await normalizer.normalize("myocardial infarction")
        assert isinstance(result, NormalizationResult)
        assert result.cui == "C0027051"
        assert result.concept_name == "Myocardial Infarction"

    @pytest.mark.asyncio
    async def test_normalize_expands_query(self, mock_adapter, mock_llm_backend):
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=True,
            prune_candidates=False,
        )
        result = await normalizer.normalize("heart attack")
        assert result.method == "llm_expanded"
        assert mock_llm_backend.complete.called

    @pytest.mark.asyncio
    async def test_normalize_empty_query(self, mock_adapter, mock_llm_backend):
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
        )
        result = await normalizer.normalize("")
        assert result.method == "none"

    @pytest.mark.asyncio
    async def test_normalize_no_results(self, mock_adapter, mock_llm_backend):
        mock_adapter.search_concepts = AsyncMock(return_value=[])
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=False,
        )
        result = await normalizer.normalize("nonexistent")
        assert result.cui is None
        assert result.method == "direct"

    @pytest.mark.asyncio
    async def test_normalize_api_error(self, mock_adapter, mock_llm_backend):
        mock_adapter.search_concepts = AsyncMock(side_effect=Exception("API fail"))
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=False,
        )
        result = await normalizer.normalize("test")
        assert result.cui is None

    @pytest.mark.asyncio
    async def test_batch_normalize(self, mock_adapter, mock_llm_backend):
        mock_adapter.search_concepts = AsyncMock(
            return_value=[
                UnifiedConcept(
                    primary_id="C001",
                    primary_label="Test",
                    concept_type=ConceptType.DISEASE,
                    confidence_score=0.9,
                ),
            ]
        )
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=False,
            prune_candidates=False,
        )
        results = await normalizer.batch_normalize(["a", "b", "c"])
        assert len(results) == 3
        assert all(r.cui == "C001" for r in results)

    @pytest.mark.asyncio
    async def test_prune_picks_best_candidate(self, mock_adapter, mock_llm_backend):
        # LLM returns C0011849
        mock_llm_backend.complete = AsyncMock(return_value="C0011849")
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=False,
            prune_candidates=True,
        )
        result = await normalizer.normalize("diabetes")
        assert result.method == "direct+llm_pruned"

    @pytest.mark.asyncio
    async def test_prune_fallback_to_top_score(self, mock_adapter, mock_llm_backend):
        # LLM returns something without a CUI
        mock_llm_backend.complete = AsyncMock(return_value="I think none of these match")
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
            expand_queries=False,
            prune_candidates=True,
        )
        result = await normalizer.normalize("test")
        # Falls back to highest confidence → C0027051 (0.95)
        assert result.cui == "C0027051"

    @pytest.mark.asyncio
    async def test_close_backend(self, mock_adapter, mock_llm_backend):
        normalizer = LLMNormalizer(
            mock_adapter,
            backend=mock_llm_backend,
        )
        await normalizer.close()
        mock_llm_backend.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_backend_string_unknown_raises(self, mock_adapter):
        with pytest.raises(ValueError, match="Unknown LLM backend"):
            LLMNormalizer(mock_adapter, backend="nonexistent")


class TestOpenAIBackend:
    @pytest.mark.asyncio
    async def test_complete_success(self):
        mock_data = {"choices": [{"message": {"content": "Myocardial Infarction"}}]}
        mock_resp = AsyncMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.json = AsyncMock(return_value=mock_data)
        mock_resp.raise_for_status = MagicMock()

        with patch("aiohttp.ClientSession.post", return_value=mock_resp):
            backend = OpenAIBackend(api_key="test-key")
            result = await backend.complete("test prompt")
            assert result == "Myocardial Infarction"

    @pytest.mark.asyncio
    async def test_custom_base_url(self):
        backend = OpenAIBackend(api_key="test-key", base_url="https://custom.example.com/v1")
        assert "custom.example.com" in backend.base_url


class TestAnthropicBackend:
    @pytest.mark.asyncio
    async def test_complete_success(self):
        mock_data = {"content": [{"text": "Myocardial Infarction"}]}
        mock_resp = AsyncMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.json = AsyncMock(return_value=mock_data)
        mock_resp.raise_for_status = MagicMock()

        with patch("aiohttp.ClientSession.post", return_value=mock_resp):
            backend = AnthropicBackend(api_key="test-key")
            result = await backend.complete("test prompt")
            assert result == "Myocardial Infarction"
            await backend.close()

    @pytest.mark.asyncio
    async def test_close(self):
        backend = AnthropicBackend(api_key="test-key")
        assert backend._session is None
        await backend.close()
        # No-op when no session
