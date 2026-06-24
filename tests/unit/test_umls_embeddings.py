"""
Unit tests for Concept Embedding Similarity Module.
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.models import ConceptType, UnifiedConcept
from knowledge_lookup.umls.embeddings import (
    ConceptEmbedder,
    EmbeddingBackend,
    EmbeddingCache,
    cosine_similarity,
)

# ---------------------------------------------------------------------------
# Stub backend for testing without heavy dependencies
# ---------------------------------------------------------------------------


class StubBackend(EmbeddingBackend):
    """Fixed-dimension deterministic backend for testing."""

    def __init__(self, dim: int = 4):
        self.dimension = dim

    async def embed(self, text: str) -> list[float]:
        # Deterministic hash-based embedding
        h = hash(text)
        import random
        rng = random.Random(h)
        vec = [rng.random() for _ in range(self.dimension)]
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.search_concepts = AsyncMock(return_value=[
        UnifiedConcept(
            primary_id=c,
            primary_label=label,
            concept_type=ConceptType.DISEASE,
            confidence_score=0.9,
        )
        for c, label in [("C0011849", "Diabetes Mellitus"), ("C0027051", "Myocardial Infarction")]
    ])
    adapter.get_concept_details = AsyncMock(return_value=UnifiedConcept(
        primary_id="C0011849",
        primary_label="Diabetes Mellitus",
        concept_type=ConceptType.DISEASE,
    ))
    return adapter


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0

    def test_zero_norm(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestEmbeddingCache:
    @pytest.fixture
    def cache(self, tmp_path):
        return EmbeddingCache(db_path=tmp_path / "test_emb.db")

    def test_set_and_get(self, cache):
        cache.set("hello", [0.1, 0.2, 0.3])
        vec = cache.get("hello")
        assert vec == [0.1, 0.2, 0.3]

    def test_get_missing(self, cache):
        assert cache.get("nonexistent") is None

    def test_size(self, cache):
        assert cache.size() == 0
        cache.set("a", [1.0])
        cache.set("b", [2.0])
        assert cache.size() == 2

    def test_clear(self, cache):
        cache.set("a", [1.0])
        cache.clear()
        assert cache.size() == 0

    def test_overwrite(self, cache):
        cache.set("key", [1.0])
        cache.set("key", [2.0])
        assert cache.get("key") == [2.0]


class TestConceptEmbedder:
    @pytest.mark.asyncio
    async def test_embed_returns_vector(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        vec = await embedder.embed("test")
        assert isinstance(vec, list)
        assert len(vec) > 0
        assert all(isinstance(v, float) for v in vec)

    @pytest.mark.asyncio
    async def test_embed_caches(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        v1 = await embedder.embed("hello")
        v2 = await embedder.embed("hello")
        assert v1 == v2  # Same due to deterministic hash + cache

    @pytest.mark.asyncio
    async def test_similarity(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        score = await embedder.similarity("diabetes", "diabetes")
        assert 0.99 <= score <= 1.0  # Should be near 1.0 for same input

    @pytest.mark.asyncio
    async def test_similarity_with_resolve(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        score = await embedder.similarity("C0011849", "C0011849", resolve_a=True, resolve_b=True)
        assert score >= 0.0

    @pytest.mark.asyncio
    async def test_nearest_neighbors(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        neighbors = await embedder.nearest_neighbors("diabetes", k=2)
        assert len(neighbors) <= 2
        if neighbors:
            cui, score = neighbors[0]
            assert isinstance(cui, str)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_nearest_neighbors_with_candidates(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        neighbors = await embedder.nearest_neighbors(
            "diabetes",
            k=2,
            candidates=["C0011849", "C0027051"],
        )
        assert len(neighbors) == 2
        # Both should have valid scores
        for _, score in neighbors:
            assert -1.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_nearest_neighbors_empty_when_adapter_fails(self, mock_adapter):
        mock_adapter.search_concepts = AsyncMock(side_effect=Exception("fail"))
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        neighbors = await embedder.nearest_neighbors("test", k=5)
        assert neighbors == []

    def test_unknown_backend_raises(self, mock_adapter):
        with pytest.raises(ValueError, match="Unknown embedding backend"):
            ConceptEmbedder(mock_adapter, backend="nonexistent")

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        embedder = ConceptEmbedder(mock_adapter, backend=StubBackend())
        await embedder.close()  # Should be a no-op for StubBackend


class TestStubBackend:
    @pytest.mark.asyncio
    async def test_embed_dimension(self):
        backend = StubBackend(dim=8)
        vec = await backend.embed("test")
        assert len(vec) == 8

    @pytest.mark.asyncio
    async def test_embed_normalized(self):
        backend = StubBackend(dim=4)
        vec = await backend.embed("test")
        norm = math.sqrt(sum(v * v for v in vec))
        assert norm == pytest.approx(1.0, rel=1e-5)

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        backend = StubBackend(dim=3)
        vecs = await backend.embed_batch(["a", "b"])
        assert len(vecs) == 2
        assert all(len(v) == 3 for v in vecs)
