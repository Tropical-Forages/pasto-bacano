"""Forage selection tools: the Tropical Forages core service.

Thin wrappers over the Tropical Forages selection MCP server
(``domain/services/forage_selection.py``): find a forage by name, list the
selection criteria, search forages for a place or use, and read a fact sheet.
They do not need a registered area. Offered only when
``PASTO_BACANO_FORAGE_MCP_URL`` is set. Descriptions and fixed texts are in
``domain/prompts/tools.yml`` (``forage_tools``).
"""

from typing import Optional

from semente import ToolResult, tool
from semente.configs.prompts import get_tool_description, get_tool_result_text
from semente.logging import log_warning

from domain.services import forage_selection
from domain.services.forage_selection import ForageServiceUnavailable

_COMPONENT = "forage_tools"


def _run(tool_key: str, mcp_tool: str, arguments: dict) -> ToolResult:
    try:
        return ToolResult(content=forage_selection.call_tool(mcp_tool, arguments))
    except ForageServiceUnavailable as error:
        log_warning(f"{tool_key}: {error}")
        return ToolResult(content=get_tool_result_text(_COMPONENT, tool_key, "service_unavailable"))


@tool(description=get_tool_description(_COMPONENT, "find_forage"))
def find_forage(name: str, limit: int = 5) -> ToolResult:
    return _run("find_forage", "find_forage", {"name": name, "limit": limit})


@tool(description=get_tool_description(_COMPONENT, "list_forage_features"))
def list_forage_features() -> ToolResult:
    return _run("list_forage_features", "list_features", {})


@tool(description=get_tool_description(_COMPONENT, "search_tropical_forages"))
def search_tropical_forages(
    categorical_filters: Optional[dict[str, list[str]]] = None,
    numeric_filters: Optional[dict[str, str]] = None,
    limit: int = 15,
) -> ToolResult:
    return _run(
        "search_tropical_forages",
        "search_tropical_forages",
        {"categorical_filters": categorical_filters, "numeric_filters": numeric_filters, "limit": limit},
    )


@tool(description=get_tool_description(_COMPONENT, "read_forage_factsheet"))
def read_forage_factsheet(name: str, section: str = "overview") -> ToolResult:
    return _run("read_forage_factsheet", "read_forage_factsheet", {"name": name, "section": section})


FORAGE_TOOLS = [find_forage, list_forage_features, search_tropical_forages, read_forage_factsheet]


def forage_tools() -> list:
    """The forage tools when the service is configured, otherwise none."""
    return FORAGE_TOOLS if forage_selection.is_configured() else []
