"""Unit-test fixtures.

Unit tests must not touch the network. The agent-workflow nodes call an LLM
(``knowledge_lookup.agents.config.call_llm``); this autouse fixture stubs it to
return ``None`` so those nodes exercise their deterministic rule-based path.
Tests that want to assert LLM behaviour can still override ``call_llm``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _no_llm_in_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = AsyncMock(return_value=None)
    for mod in (
        "knowledge_lookup.agents.config",
        "knowledge_lookup.agents.nodes.review",
        "knowledge_lookup.agents.nodes.refine",
        "knowledge_lookup.agents.nodes.filter",
        "knowledge_lookup.agents.nodes.preprocess",
    ):
        try:
            monkeypatch.setattr(f"{mod}.call_llm", stub, raising=False)
        except Exception:  # noqa: BLE001 - module may not import without extras
            pass
