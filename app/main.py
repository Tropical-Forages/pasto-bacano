"""ASGI entry point of the Pasto Bacano agent service.

Starts the agent as a web API (the Streamlit chat in ``app/streamlit_app.py``
is a separate entry point and is not affected):

    uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8080

Channels are switched on with ``PASTO_BACANO_CHANNELS`` (comma separated,
default ``web``):

    web       POST /api/chat for the Time2Graze website (app.api)
    whatsapp  Semente's WhatsApp webhook (/whatsapp/webhook); needs the WHATSAPP_* variables
    a2a       Semente's A2A endpoint (/a2a) for other agents

The app is assembled here instead of with ``semente.build.build_app`` so each
channel can be enabled on its own (``build_app`` mounts WhatsApp whenever
``semente.yaml`` lists it, and then requires its tokens). Semente's own
channel classes are used unchanged, and all channels share the same cached
harness, so they run the same agent.
"""

import os

from fastapi import FastAPI
from semente.core.harness import get_harness
from semente.logging import log_info
from semente.manifest import Manifest

from app.api import build_router

KNOWN_CHANNELS = ("web", "whatsapp", "a2a")


def enabled_channels(value: str | None = None) -> list[str]:
    """Parses ``PASTO_BACANO_CHANNELS``.

    Args:
        value (str | None): Comma separated channel names; the env var when omitted.

    Returns:
        list[str]: Known channel names in order (``["web"]`` when empty).

    Raises:
        ValueError: If an unknown channel is listed.
    """
    raw = value if value is not None else os.getenv("PASTO_BACANO_CHANNELS", "web")
    channels = [c.strip().lower() for c in raw.split(",") if c.strip()] or ["web"]
    unknown = [c for c in channels if c not in KNOWN_CHANNELS]
    if unknown:
        raise ValueError(f"Unknown channel(s) in PASTO_BACANO_CHANNELS: {', '.join(unknown)}")
    return channels


def create_app(channels: list[str] | None = None) -> FastAPI:
    """Builds the FastAPI app with the enabled channels.

    Args:
        channels (list[str] | None): Channels to mount; from the environment when omitted.

    Returns:
        FastAPI: The ASGI app to serve with uvicorn.
    """
    manifest_path = os.getenv("SEMENTE_MANIFEST", "semente.yaml")
    manifest = Manifest.load(manifest_path)
    harness = get_harness(manifest_path)
    channels = channels or enabled_channels()

    app = FastAPI(title="Pasto Bacano agent")
    if "web" in channels:
        app.include_router(build_router(harness, public_base_url=os.getenv("PASTO_BACANO_PUBLIC_URL") or None))
    if "whatsapp" in channels:
        from semente.interfaces.whatsapp import Whatsapp

        app.include_router(Whatsapp(agent=harness).get_router())
    if "a2a" in channels:
        from semente.interfaces.a2a import A2A

        app.include_router(A2A(agent=harness, name=manifest.name, card=manifest.a2a).get_router())

    log_info(f"Pasto Bacano agent: channels enabled: {', '.join(channels)}")
    return app

