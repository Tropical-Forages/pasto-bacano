"""Vertex AI compatibility for Agno's Gemini model (Agno and Semente stay unchanged).

When a tool returns an image (for example the map of a registered area), Agno
sends it to the model as a user message right after the tool result, and then
merges both into one user turn: ``[function_response, text, image]``. The
Gemini API accepts that turn, but Vertex AI rejects it with "Requests ending
with a model turn are not supported". Vertex accepts the same parts when the
function responses come last: ``[text, image, function_response]``.

Vertex AI also rejects file parts typed ``application/json``, which is how
Agno sends an uploaded farm boundary (GeoJSON). Those parts are sent as
``text/plain``, which Vertex accepts and the model reads the same way.

``install()`` wraps ``Gemini._format_messages`` so that, only when Vertex AI is
used, both changes are applied to the request.
"""

import os
from typing import Any

from agno.models.google.gemini import Gemini

_INSTALLED_FLAG = "_pasto_bacano_vertex_compat"
_JSON_MIME_TYPES = {"application/json", "application/geo+json"}


def _uses_vertex(model: Any) -> bool:
    client = getattr(model, "client", None)
    if client is not None and getattr(client, "vertexai", None) is not None:
        return bool(client.vertexai)
    if getattr(model, "vertexai", False):
        return True
    return os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true"


def reorder_function_responses(contents: list) -> list:
    """Moves function responses after the other parts in turns that mix both.

    Args:
        contents (list): Gemini ``Content`` objects as built by Agno.

    Returns:
        list: The same list, changed in place.
    """
    for content in contents:
        parts = getattr(content, "parts", None) or []
        responses = [p for p in parts if getattr(p, "function_response", None) is not None]
        if responses and len(responses) < len(parts):
            content.parts = [p for p in parts if getattr(p, "function_response", None) is None] + responses
    return contents


def retype_json_files(contents: list) -> list:
    """Sends inline JSON and GeoJSON file parts as plain text (Vertex rejects JSON mime types).

    Args:
        contents (list): Gemini ``Content`` objects as built by Agno.

    Returns:
        list: The same list, changed in place.
    """
    for content in contents:
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and (inline.mime_type or "").lower() in _JSON_MIME_TYPES:
                inline.mime_type = "text/plain"
    return contents


def install() -> None:
    """Patches Agno's Gemini formatter once; safe to call more than once."""
    original = Gemini._format_messages
    if getattr(original, _INSTALLED_FLAG, False):
        return

    def _format_messages(self, messages, *args, **kwargs):
        formatted, system_message = original(self, messages, *args, **kwargs)
        if _uses_vertex(self):
            reorder_function_responses(formatted)
            retype_json_files(formatted)
        return formatted, system_message

    setattr(_format_messages, _INSTALLED_FLAG, True)
    Gemini._format_messages = _format_messages
