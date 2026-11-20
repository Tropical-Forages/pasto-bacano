"""Client for the Tropical Forages selection MCP server (core service).

The server (``tf_interactive_selection_tool/soft_api``, deployed on Cloud Run as
``tf-selection-mcp``) wraps the CIAT Tropical Forages selection tool. It speaks
MCP over streamable HTTP at ``{PASTO_BACANO_FORAGE_MCP_URL}/mcp``. On Cloud Run
the call carries a Google ID token of the service account, so the server can
stay private; without metadata credentials (local runs) no token is sent.
"""

import asyncio
import os
from typing import Any

from semente.logging import log_debug, log_warning

URL_ENV = "PASTO_BACANO_FORAGE_MCP_URL"
TIMEOUT_SECONDS = 30


class ForageServiceUnavailable(Exception):
    """The forage selection service could not be reached or failed."""


def base_url() -> str:
    """Returns the configured server URL without a trailing slash, or an empty string."""
    return os.getenv(URL_ENV, "").strip().rstrip("/")


def is_configured() -> bool:
    """True when the forage selection tools should be offered."""
    return bool(base_url())


def _auth_headers(audience: str) -> dict:
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        token = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)
        return {"Authorization": f"Bearer {token}"}
    except Exception as error:  # noqa: BLE001 — local runs have no metadata server
        log_debug(f"forage_selection: no ID token ({error}); calling without auth")
        return {}


async def _call(name: str, arguments: dict) -> str:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url = base_url()
    async with streamablehttp_client(f"{url}/mcp", headers=_auth_headers(url), timeout=TIMEOUT_SECONDS) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
    text = "".join(getattr(item, "text", "") for item in result.content)
    if result.isError:
        raise ForageServiceUnavailable(text[:500] or "tool error")
    return text


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Calls one tool of the forage selection server and returns its text (JSON).

    Args:
        name (str): MCP tool name, for example ``search_tropical_forages``.
        arguments (dict): Tool arguments; empty values are dropped.

    Returns:
        str: The tool's text result.

    Raises:
        ForageServiceUnavailable: When the server is not configured, unreachable or fails.
    """
    if not is_configured():
        raise ForageServiceUnavailable(f"{URL_ENV} is not set")
    arguments = {key: value for key, value in arguments.items() if value not in (None, "", [], {})}
    log_debug(f"forage_selection: {name} {arguments}")
    try:
        return asyncio.run(_call(name, arguments))
    except ForageServiceUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 — network, auth or protocol errors
        log_warning(f"forage_selection: {name} failed: {error!r}")
        raise ForageServiceUnavailable(str(error)) from error
