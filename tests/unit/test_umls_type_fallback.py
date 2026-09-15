"""Regression test: UMLS concept details fall back to semantic-type TUIs.

`_convert_profile` used `a or b` to fall back from semantic type names to TUIs,
but `ConceptType.UNKNOWN` is a truthy str enum, so the fallback never ran.
"""

from types import SimpleNamespace

import pytest

from knowledge_lookup.adapters.umls_adapter import UMLSAdapter
from knowledge_lookup.models import ConceptType, LookupConfig

pytestmark = pytest.mark.unit


def test_details_fall_back_to_semantic_type_tui(monkeypatch):
    monkeypatch.setattr(UMLSAdapter, "_initialize_client", lambda self: None)
    adapter = UMLSAdapter(LookupConfig())
    tui, expected = next(
        (tui, mapped)
        for tui, mapped in UMLSAdapter.SEMANTIC_TYPE_TUI_MAP.items()
        if mapped != ConceptType.UNKNOWN
    )
    unmapped_name = "Semantic type name that is not in the name map"
    assert unmapped_name not in UMLSAdapter.SEMANTIC_TYPE_NAME_MAP

    concept_info = SimpleNamespace(
        name="Example concept",
        semantic_types=[
            {
                "name": unmapped_name,
                "uri": f"https://uts-ws.nlm.nih.gov/rest/semantic-network/2026AA/TUI/{tui}",
            }
        ],
    )
    profile = SimpleNamespace(definitions=[], preferred_atom=None, atoms=[], relations=[])

    concept = adapter._convert_profile("C0000001", concept_info, profile)

    assert concept.concept_type == expected
