"""HTTP API of Pasto Bacano: the agent as an endpoint for external clients.

Each channel is a separate router on the FastAPI app that Semente builds
(``app.main``). This package holds the web channel used by the Time2Graze
website (``POST /api/chat``); the WhatsApp webhook comes from Semente and is
mounted on the same app, so both channels share one agent.

Modules:
    models    request and response schemas (the website contract)
    sessions  channel namespaced session ids and per-session locks
    media     storage of maps, PDFs and videos returned as attachment links
    auth      optional API key check (Cloud Run IAM is the main protection)
    router    the FastAPI router of the web channel
"""

from app.api.router import build_router

__all__ = ["build_router"]
