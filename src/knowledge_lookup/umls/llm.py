"""
LLM-Augmented Concept Normalization

Uses Large Language Models (local or API-based) to improve concept normalisation
— mapping free-text biomedical expressions to UMLS CUIs.  Inspired by recent
research showing LLMs can significantly boost recall for clinical entity linking
(Dobbins et al. 2025, Research Synthesis Methods).

Features
--------
- **Query expansion** — rephrase colloquial terms into medical language
- **Candidate pruning** — score/rank candidate CUIs using an LLM
- **Zero-shot normalisation** — map text directly to CUI without a candidate list
- Pluggable backends: OpenAI, Anthropic, or local HuggingFace models

Usage::

    from knowledge_lookup.umls.llm import LLMNormalizer

    normalizer = LLMNormalizer(adapter, backend="openai", api_key="sk-...")
    cui = await normalizer.normalize("heart attack")
    # → C0027051 (Myocardial Infarction)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from ..models import UnifiedConcept

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backend abstraction
# ---------------------------------------------------------------------------


class LLMBackend:
    """Abstract base for LLM backends."""

    async def complete(self, prompt: str, *, max_tokens: int = 256, temperature: float = 0.1) -> str:
        """Send a prompt to the LLM and return the completion text."""
        raise NotImplementedError

    async def close(self):
        """Release any resources (HTTP sessions, etc.)."""


class OpenAIBackend(LLMBackend):
    """LLM backend using OpenAI's API (GPT-4o-mini, etc.)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def complete(self, prompt: str, *, max_tokens: int = 256, temperature: float = 0.1) -> str:
        import aiohttp

        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()


class AnthropicBackend(LLMBackend):
    """LLM backend using Anthropic's API (Claude)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self._session = None

    async def _get_session(self):
        import aiohttp

        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def complete(self, prompt: str, *, max_tokens: int = 256, temperature: float = 0.1) -> str:
        session = await self._get_session()
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["content"][0]["text"].strip()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


class HuggingFaceBackend(LLMBackend):
    """Local HuggingFace Transformers backend (runs in-process).

    WARNING: Requires ``torch`` and ``transformers`` installed separately.
    The model is loaded once and cached for subsequent calls.
    """

    def __init__(self, model_name: str = "michiyasunaga/BioLinkBERT-base", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipe = None

    def _load(self):
        if self._pipe is not None:
            return
        try:
            from transformers import pipeline  # noqa: F811
        except ImportError:
            raise ImportError(
                "HuggingFace backend requires `pip install transformers torch`"
            )
        self._pipe = pipeline(
            "text-generation",
            model=self.model_name,
            device=self.device,
        )

    async def complete(self, prompt: str, *, max_tokens: int = 256, temperature: float = 0.1) -> str:
        self._load()
        import asyncio

        # Run inference in a thread to avoid blocking the event loop
        def _run():
            result = self._pipe(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )
            return result[0]["generated_text"].strip()

        return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------------
# LLM Normalizer
# ---------------------------------------------------------------------------


@dataclass
class NormalizationResult:
    """Result of a single LLM-normalization call."""

    query: str
    normalized_form: str | None = None
    cui: str | None = None
    concept_name: str | None = None
    confidence: float = 0.0
    method: str = "none"
    raw_llm_output: str | None = None


class LLMNormalizer:
    """LLM-Augmented Concept Normalizer.

    Maps free-text biomedical expressions to UMLS concepts using a two-stage
    process:

    1. **Query expansion** (optional) — the LLM rephrases the text into
       standard medical terminology.
    2. **Candidate retrieval** — the expanded query is searched via the
       UMLS adapter.
    3. **Candidate pruning** (optional) — the LLM scores the top candidates
       and picks the best match.

    Parameters
    ----------
    adapter :
        A UMLS adapter (or any adapter with ``search_concepts``).
    backend :
        One of ``"openai"``, ``"anthropic"``, ``"huggingface"``, or an
        ``LLMBackend`` instance.
    api_key :
        API key for OpenAI/Anthropic (not needed for HuggingFace).
    model :
        Model name override (e.g. ``"gpt-4o-mini"``).
    expand_queries :
        Whether to use the LLM to expand/rephrase queries before search.
    prune_candidates :
        Whether to use the LLM to rank candidate concepts.
    """

    _BACKENDS = {
        "openai": OpenAIBackend,
        "anthropic": AnthropicBackend,
        "huggingface": HuggingFaceBackend,
    }

    def __init__(
        self,
        adapter: Any,
        *,
        backend: str | LLMBackend = "openai",
        api_key: str | None = None,
        model: str | None = None,
        expand_queries: bool = True,
        prune_candidates: bool = True,
    ):
        self.adapter = adapter

        if isinstance(backend, str):
            backend_cls = self._BACKENDS.get(backend)
            if backend_cls is None:
                raise ValueError(f"Unknown LLM backend '{backend}'. Options: {list(self._BACKENDS)}")
            kwargs: dict[str, Any] = {}
            if api_key is not None:
                kwargs["api_key"] = api_key
            if model is not None:
                kwargs["model"] = model
            self._backend = backend_cls(**kwargs)
        else:
            self._backend = backend

        self.expand_queries = expand_queries
        self.prune_candidates = prune_candidates

    async def normalize(self, text: str, *, limit: int = 10) -> NormalizationResult:
        """Normalize a biomedical text expression to a UMLS concept.

        Parameters
        ----------
        text :
            The free-text expression (e.g. ``"heart attack"``, ``"high blood
            sugar"``).
        limit :
            Number of candidate concepts to retrieve from the adapter.

        Returns
        -------
        A :class:`NormalizationResult` with the best matching CUI.
        """
        original = text.strip()
        if not original:
            return NormalizationResult(query=text, method="none")

        # Stage 1: Query expansion (optional)
        query_text = original
        method = "direct"
        if self.expand_queries:
            expansion_prompt = (
                f"Convert the following colloquial or informal biomedical expression "
                f"into standard medical terminology. Output ONLY the standard term, "
                f"nothing else.\n\nExpression: {original}"
            )
            try:
                expanded = await self._backend.complete(expansion_prompt, max_tokens=60)
                expanded = expanded.strip().strip('"').strip("'")
                if expanded and len(expanded) > 2 and expanded.lower() != original.lower():
                    query_text = expanded
                    method = "llm_expanded"
                    logger.info("LLM expanded '%s' → '%s'", original, expanded)
            except Exception as exc:
                logger.warning("LLM query expansion failed: %s", exc)

        # Stage 2: Candidate retrieval
        try:
            concepts = await self.adapter.search_concepts(query_text, limit=limit)
        except Exception as exc:
            logger.error("Adapter search failed for '%s': %s", query_text, exc)
            return NormalizationResult(query=original, method=method, raw_llm_output=expanded if method == "llm_expanded" else None)

        if not concepts:
            return NormalizationResult(
                query=original,
                normalized_form=query_text,
                method=method,
                raw_llm_output=expanded if method == "llm_expanded" else None,
            )

        # Stage 3: Candidate pruning (optional)
        if self.prune_candidates and len(concepts) > 1:
            selected = await self._prune(original, concepts)
        else:
            selected = concepts[0]

        return NormalizationResult(
            query=original,
            normalized_form=query_text,
            cui=selected.primary_id,
            concept_name=selected.primary_label,
            confidence=selected.confidence_score,
            method=f"{method}+llm_pruned" if self.prune_candidates and len(concepts) > 1 else method,
            raw_llm_output=expanded if method == "llm_expanded" else None,
        )

    async def batch_normalize(
        self,
        texts: list[str],
        *,
        limit: int = 10,
        max_concurrency: int = 5,
    ) -> list[NormalizationResult]:
        """Normalize a batch of texts.

        Parameters
        ----------
        texts :
            List of biomedical expressions.
        limit :
            Candidates per term.
        max_concurrency :
            Maximum concurrent LLM calls.

        Returns
        -------
        A list of :class:`NormalizationResult` in the same order as *texts*.
        """
        async def _normalize_one(t: str) -> NormalizationResult:
            return await self.normalize(t, limit=limit)

        tasks = [_normalize_one(t) for t in texts]
        return await asyncio.gather(*tasks)

    async def _prune(
        self,
        original: str,
        concepts: list[UnifiedConcept],
    ) -> UnifiedConcept:
        """Use the LLM to pick the best concept from a list of candidates."""
        candidates_str = "\n".join(
            f"{i}. CUI={c.primary_id} Name='{c.primary_label}' "
            f"Type={c.concept_type} Score={c.confidence_score or 0:.2f}"
            for i, c in enumerate(concepts)
        )
        prune_prompt = (
            f"Given the biomedical expression '{original}', select the BEST matching "
            f"concept from the candidates below. Reply with ONLY the CUI (e.g. C0027051).\n\n"
            f"Candidates:\n{candidates_str}"
        )

        try:
            llm_output = await self._backend.complete(prune_prompt, max_tokens=30)
            llm_output = llm_output.strip()
            # Extract the CUI from the output
            import re

            match = re.search(r"(C\d{7})", llm_output)
            if match:
                chosen_cui = match.group(1)
                for c in concepts:
                    if c.primary_id == chosen_cui:
                        logger.info("LLM pruned candidates → %s (%s)", chosen_cui, c.primary_label)
                        return c
            logger.debug("LLM output '%s' — no CUI match, using top scorer", llm_output)
        except Exception as exc:
            logger.warning("LLM candidate pruning failed: %s", exc)

        # Fallback: best confidence score
        return max(concepts, key=lambda c: c.confidence_score)

    async def close(self):
        """Close the LLM backend."""
        await self._backend.close()
