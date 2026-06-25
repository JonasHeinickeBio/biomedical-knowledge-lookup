"""
Concept Embedding Similarity Module

Computes and retrieves semantic similarity between UMLS concepts using
text embeddings.  Supports multiple embedding backends and caching of
computed embeddings in SQLite for fast nearest-neighbor search.

Motivation
----------
Research (Mao & Fung, NLM) shows combined word+graph embeddings outperform
path-based similarity for UMLS concepts.  This module provides a pluggable
interface for concept embedding, similarity scoring, and nearest-neighbor
search — enabling semantic clustering, relatedness ranking, and
knowledge-graph integration.

Usage::

    from knowledge_lookup.umls.embeddings import ConceptEmbedder

    embedder = ConceptEmbedder(adapter, model="sentence-transformers/all-MiniLM-L6-v2")
    # Compare two concepts
    score = await embedder.similarity("C0011849", "C0027051")
    print(f"Similarity: {score:.3f}")

    # Find most similar concepts
    nearest = await embedder.nearest_neighbors("carboplatin", k=5)
    for cui, score in nearest:
        print(f"{cui}: {score:.3f}")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------


class EmbeddingBackend:
    """Abstract base for text embedding models."""

    dimension: int = 384

    async def embed(self, text: str) -> list[float]:
        """Return a float vector for *text*."""
        raise NotImplementedError

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return vectors for multiple texts."""
        return [await self.embed(t) for t in texts]


class SentenceTransformerBackend(EmbeddingBackend):
    """Uses sentence-transformers for local embedding computation.

    Requires ``sentence-transformers`` installed separately.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F811
        except ImportError:
            raise ImportError(
                "SentenceTransformer backend requires `pip install sentence-transformers`"
            )
        self._model = SentenceTransformer(self.model_name, device=self.device)
        self.dimension = self._model.get_sentence_embedding_dimension()

    async def embed(self, text: str) -> list[float]:
        self._load()
        import asyncio

        def _run():
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()

        return await asyncio.to_thread(_run)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load()
        import asyncio

        def _run():
            vecs = self._model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vecs]

        return await asyncio.to_thread(_run)


class FastTextBackend(EmbeddingBackend):
    """Uses ``fasttext`` (Facebook) for lightweight local embeddings.

    Requires ``fasttext`` installed separately.
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        try:
            import fasttext  # noqa: F811
        except ImportError:
            raise ImportError("FastText backend requires `pip install fasttext`")
        if self.model_path and Path(self.model_path).exists():
            self._model = fasttext.load_model(self.model_path)
        else:
            # Use the small pretrained model
            import fasttext.util

            fasttext.util.download_model("en", if_exists="ignore")
            self._model = fasttext.load_model("cc.en.300.bin")
        self.dimension = self._model.get_dimension()

    async def embed(self, text: str) -> list[float]:
        self._load()
        import asyncio

        def _run():
            vec = self._model.get_sentence_vector(text)
            # L2-normalize
            import math

            norm = math.sqrt(sum(v * v for v in vec))
            return [v / norm for v in vec] if norm > 0 else vec.tolist()

        return await asyncio.to_thread(_run)


class OpenAIBackend(EmbeddingBackend):
    """OpenAI embedding API backend."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self.dimension = 1536 if "small" in model else 3072
        self._session = None

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import aiohttp

        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": texts, "model": self.model}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [item["embedding"] for item in data["data"]]


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Embedding cache (SQLite-backed)
# ---------------------------------------------------------------------------


class EmbeddingCache:
    """Persistent embedding cache in SQLite.

    Stores precomputed vectors keyed by text hash so repeated embeddings
    of the same term are instant.
    """

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = Path(
            db_path or (Path.home() / ".cache" / "knowledge-lookup" / "embeddings.db")
        )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS embeddings ("
                "  text_hash TEXT PRIMARY KEY,"
                "  text TEXT NOT NULL,"
                "  vector BLOB NOT NULL,"
                "  dimension INTEGER NOT NULL,"
                "  created_at REAL NOT NULL"
                ")"
            )

    def get(self, text: str) -> list[float] | None:
        """Retrieve cached embedding for *text*."""
        import hashlib

        text_hash = hashlib.md5(text.encode()).hexdigest()
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT vector FROM embeddings WHERE text_hash = ?", (text_hash,)
            ).fetchone()
        if row:
            return json.loads(row[0])
        return None

    def set(self, text: str, vector: list[float]) -> None:
        """Store an embedding for *text*."""
        import hashlib

        text_hash = hashlib.md5(text.encode()).hexdigest()
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (text_hash, text, vector, dimension, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (text_hash, text, json.dumps(vector), len(vector), time.time()),
            )

    def size(self) -> int:
        """Number of cached embeddings."""
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return row[0] if row else 0

    def clear(self) -> None:
        """Clear all cached embeddings."""
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM embeddings")


# ---------------------------------------------------------------------------
# Concept Embedder — main public class
# ---------------------------------------------------------------------------


@dataclass
class SimilarityResult:
    """Result of a similarity comparison."""

    concept_a: str
    concept_b: str
    similarity: float
    method: str = "cosine"


class ConceptEmbedder:
    """Compute and search concept embeddings.

    Parameters
    ----------
    adapter :
        A UMLS adapter (or any adapter with ``search_concepts`` and
        ``get_concept_details``).
    backend :
        Embedding backend.  One of ``"sentence-transformers"``,
        ``"fasttext"``, ``"openai"``, or an ``EmbeddingBackend`` instance.
    api_key :
        API key for the OpenAI backend.
    model :
        Model name override.
    cache_dir :
        Directory for the embedding cache.  ``None`` = default ``~/.cache/``.
    """

    _BACKENDS = {
        "sentence-transformers": SentenceTransformerBackend,
        "fasttext": FastTextBackend,
        "openai": OpenAIBackend,
    }

    def __init__(
        self,
        adapter: Any,
        *,
        backend: str | EmbeddingBackend = "sentence-transformers",
        api_key: str | None = None,
        model: str | None = None,
        cache_dir: str | Path | None = None,
    ):
        self.adapter = adapter

        if isinstance(backend, str):
            backend_cls = self._BACKENDS.get(backend)
            if backend_cls is None:
                raise ValueError(
                    f"Unknown embedding backend '{backend}'. Options: {list(self._BACKENDS)}"
                )
            kwargs: dict[str, Any] = {}
            if api_key is not None:
                kwargs["api_key"] = api_key
            if model is not None:
                kwargs["model"] = model
            self._backend = backend_cls(**kwargs)
        else:
            self._backend = backend

        self._cache = EmbeddingCache(Path(cache_dir) / "embeddings.db" if cache_dir else None)

    async def embed(self, text: str) -> list[float]:
        """Compute (or retrieve cached) embedding for *text*."""
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = await self._backend.embed(text)
        self._cache.set(text, vector)
        return vector

    async def similarity(
        self,
        a: str,
        b: str,
        *,
        resolve_a: bool = False,
        resolve_b: bool = False,
    ) -> float:
        """Cosine similarity between two concepts or terms.

        Parameters
        ----------
        a, b :
            CUI IDs (e.g. ``"C0011849"``) or free-text terms.
            If a CUI is given and *resolve* is ``True``, the concept name
            is fetched from the adapter.
        resolve_a, resolve_b :
            Whether to resolve CUI IDs to concept names (requires adapter).
        """
        text_a = await self._resolve(a) if resolve_a else a
        text_b = await self._resolve(b) if resolve_b else b
        vec_a = await self.embed(text_a)
        vec_b = await self.embed(text_b)
        return cosine_similarity(vec_a, vec_b)

    async def nearest_neighbors(
        self,
        query: str,
        *,
        k: int = 10,
        candidates: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Find the *k* most similar concepts to *query*.

        Parameters
        ----------
        query :
            A CUI or free-text term.
        k :
            Number of neighbors to return.
        candidates :
            Optional list of CUIs to search within.  If ``None``, uses the
            adapter to search and generates embeddings on the fly.

        Returns
        -------
        ``[(cui_or_term, similarity_score), ...]`` sorted descending.
        """
        query_vec = await self.embed(query)

        if candidates is None:
            # Fetch candidates from the adapter
            try:
                concepts = await self.adapter.search_concepts(query, limit=50)
            except Exception as exc:
                logger.error("Failed to search concepts: %s", exc)
                return []
            candidate_ids = [c.primary_id for c in concepts]
            candidate_texts = [c.primary_label for c in concepts]
        else:
            candidate_ids = candidates
            # Resolve candidate names from adapter
            candidate_texts = await self._resolve_candidates(candidate_ids)

        # Embed candidates in batch
        candidate_vecs = await self._backend.embed_batch(candidate_texts)

        # Score and rank
        scored: list[tuple[str, float]] = []
        for cui, vec in zip(candidate_ids, candidate_vecs, strict=False):
            sim = cosine_similarity(query_vec, vec)
            scored.append((cui, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    async def _resolve(self, cui: str) -> str:
        """Resolve a CUI to its label via the adapter."""
        try:
            concept = await self.adapter.get_concept_details(cui)
            if concept and concept.primary_label:
                return concept.primary_label
        except Exception:
            pass
        return cui

    async def _resolve_candidates(self, cuis: list[str]) -> list[str]:
        """Resolve a list of CUIs to their labels."""
        texts: list[str] = []
        for cui in cuis:
            texts.append(await self._resolve(cui))
        return texts

    async def close(self):
        """Cleanup backend resources."""
        if hasattr(self._backend, "close"):
            await self._backend.close()
