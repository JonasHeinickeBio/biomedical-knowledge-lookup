"""
Agent Workflow Package

Provides an intelligent agent workflow for biomedical knowledge lookup built on LangGraph:

- **LangGraph Workflow**: StateGraph with human-in-the-loop interrupts
- **Lookup Node**: Orchestrates searches via CentralKnowledgeLookup
- **Review Node**: LLM-powered quality assessment (Blablador/OpenAI) with rule-based fallback
- **Approval Node**: Human-in-the-loop via LangGraph interrupt()
- **Refine Node**: Query refinement based on feedback
- **Export Node**: Multi-format export (JSON, CSV, TTL)

Quick Start::

    from knowledge_lookup.agents import run_workflow, resume_workflow

    # Run the workflow (pauses at approval)
    result = await run_workflow("insulin receptor", max_results=20)

    # Resume with user decision
    result = await resume_workflow(
        result["thread_id"],
        {"approved": True}
    )

Module Structure::

    agents/
    ├── __init__.py      # Public API (this file)
    ├── config.py        # LLM configuration and API call helpers
    ├── state.py         # Workflow state TypedDict and serialization
    ├── graph.py         # LangGraph graph construction
    ├── routing.py       # Conditional edge routing logic
    ├── runners.py       # High-level run_workflow / resume_workflow
    └── nodes/
        ├── __init__.py  # Re-exports all nodes
        ├── lookup.py    # Knowledge source search
        ├── review.py    # LLM + rule-based quality review
        ├── approval.py  # Human-in-the-loop interrupt
        ├── refine.py    # Query refinement
        └── export.py    # Multi-format export
"""

from .config import call_llm, load_llm_config
from .graph import build_workflow_graph
from .runners import resume_workflow, run_workflow
from .state import (
    LookupWorkflowState,
    dict_to_lookup_result,
    lookup_result_to_dict,
    make_step,
)

__all__ = [
    # High-level API
    "run_workflow",
    "resume_workflow",
    "build_workflow_graph",
    # State
    "LookupWorkflowState",
    "lookup_result_to_dict",
    "dict_to_lookup_result",
    "make_step",
    # Config
    "load_llm_config",
    "call_llm",
]
