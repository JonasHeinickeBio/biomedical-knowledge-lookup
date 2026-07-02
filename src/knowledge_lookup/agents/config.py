"""LLM configuration and API call helpers.

Supports Blablador (Helmholtz AI), OpenAI, and Anthropic backends.
Configuration is loaded from environment variables.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def load_llm_config() -> dict[str, str | None]:
    """Load LLM configuration from environment variables.

    Checks for (in order):
    1. BLABLADOR_API_KEY / BLABLADOR_API_BASE / BLABLADOR_MODEL
    2. OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL
    3. ANTHROPIC_API_KEY / ANTHROPIC_MODEL

    Returns:
        Dict with keys: backend, api_key, base_url, model
    """
    # Try Blablador first (Helmholtz AI - OpenAI-compatible)
    blablador_key = os.getenv("BLABLADOR_API_KEY")
    if blablador_key:
        base_url = os.getenv(
            "BLABLADOR_API_BASE",
            "https://api.helmholtz-blablador.fz-juelich.de/v1/",
        )
        # Ensure the base_url includes the chat completions endpoint
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/chat/completions"):
            base_url = base_url + "/chat/completions"
        return {
            "backend": "openai",
            "api_key": blablador_key,
            "base_url": base_url,
            "model": os.getenv("BLABLADOR_MODEL", "alias-fast"),
        }

    # Try OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        base_url = os.getenv("OPENAI_API_BASE")
        if base_url:
            base_url = base_url.rstrip("/")
            if not base_url.endswith("/chat/completions"):
                base_url = base_url + "/chat/completions"
        return {
            "backend": "openai",
            "api_key": openai_key,
            "base_url": base_url,
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }

    # Try Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        return {
            "backend": "anthropic",
            "api_key": anthropic_key,
            "base_url": None,
            "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        }

    return {"backend": None, "api_key": None, "base_url": None, "model": None}


async def call_llm(
    prompt: str, *, max_tokens: int = 1024, temperature: float = 0.2
) -> str | None:
    """Call the configured LLM backend.

    Returns the completion text, or None if no LLM is configured or call fails.
    """
    config = load_llm_config()
    if not config["api_key"] or not config["backend"]:
        logger.info("No LLM configured - falling back to rule-based review")
        return None

    try:
        from ..umls.llm import AnthropicBackend, LLMBackend, OpenAIBackend

        backend: LLMBackend
        if config["backend"] == "openai":
            backend = OpenAIBackend(
                api_key=config["api_key"],
                model=config["model"] or "gpt-4o-mini",
                base_url=config["base_url"],
            )
        elif config["backend"] == "anthropic":
            backend = AnthropicBackend(
                api_key=config["api_key"],
                model=config["model"] or "claude-sonnet-4-20250514",
            )
        else:
            return None

        result = await backend.complete(
            prompt, max_tokens=max_tokens, temperature=temperature
        )
        await backend.close()
        return result

    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return None
