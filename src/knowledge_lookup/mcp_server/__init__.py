"""
MCP server exposing biomedical knowledge lookup to LLM agents.

Requires the optional ``mcp`` extra::

    pip install "biomedical-knowledge-lookup[mcp]"
    knowledge-lookup-mcp                      # stdio (Claude Code / Desktop, Cursor, ...)
    knowledge-lookup-mcp --transport streamable-http --port 8000

See ``docs/guides/mcp-server.md`` for the tool reference and client configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .server import ServerSettings, create_server

__all__ = ["ServerSettings", "create_server", "main"]

_MISSING_EXTRA = (
    "The MCP server needs the optional 'mcp' extra: pip install 'biomedical-knowledge-lookup[mcp]'"
)


def _import_server() -> Any:
    try:
        from . import server
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] == "mcp":
            raise ImportError(_MISSING_EXTRA) from exc
        raise
    return server


def __getattr__(name: str) -> Any:
    if name in ("ServerSettings", "create_server"):
        return getattr(_import_server(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point (``knowledge-lookup-mcp``)."""
    try:
        server = _import_server()
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc
    server.run(argv)
