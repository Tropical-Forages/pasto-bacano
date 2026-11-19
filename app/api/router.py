"""Web chat channel: ``POST /api/chat``, ``GET /api/health`` and ``GET /api/media/{id}``.

The router only translates between HTTP and the Semente harness; the agent,
tools and prompts are the same as in Streamlit and WhatsApp.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from semente.logging import log_error, log_info
from starlette.concurrency import run_in_threadpool

from app.api.auth import api_key_dependency
from app.api.media import MediaStore, MemoryMediaStore, collect_attachments, media_store_from_env
from app.api.models import ChatRequest, ChatResponse
from app.api.sessions import channel_session_id, session_lock

CHANNEL = "web"
# Separator the remediation agent puts between its three messages; WhatsApp
# sends them as separate messages, the web shows them as paragraphs.
_PAUSE = "[PAUSE]"


def _model_error(text: str) -> Optional[str]:
    """Returns the error status when the reply is a raw model error instead of an answer.

    When the model call fails (for example Gemini overloaded, HTTP 503), the
    engine returns the provider's error JSON as the reply text and Semente
    passes it on. That text must never reach the user.
    """
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except ValueError:
        return None
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return None
    return str(error.get("status") or error.get("code") or "UNKNOWN")


def _reply_text(output: Any) -> str:
    text = getattr(output, "content", "") or ""
    return "\n\n".join(part.strip() for part in text.split(_PAUSE) if part.strip())


def build_router(
    harness: Any,
    media_store: Optional[MediaStore] = None,
    api_key: Optional[str] = None,
    public_base_url: Optional[str] = None,
) -> APIRouter:
    """Builds the web channel router.

    Args:
        harness: The Semente ``Harness`` (anything with ``run(user_id=, session_id=, input=, session_state=)``).
        media_store (MediaStore | None): Where attachments go; from the environment when omitted.
        api_key (str | None): Optional bearer key; ``PASTO_BACANO_API_KEY`` when omitted.
        public_base_url (str | None): Base URL used in memory store links; the request URL when omitted.

    Returns:
        APIRouter: Routes under ``/api``.
    """
    store = media_store or media_store_from_env()
    router = APIRouter(prefix="/api", tags=["web"])
    require_key = api_key_dependency(api_key)

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_key)])
    async def chat(body: ChatRequest, request: Request) -> ChatResponse:
        session_id = channel_session_id(CHANNEL, body.session_id)
        initial_state = {"preferred_language": body.language} if body.language else None

        def run_turn() -> Any:
            with session_lock(session_id):
                return harness.run(
                    user_id=session_id, session_id=session_id, input=body.agent_input(), session_state=initial_state
                )

        try:
            output = await run_in_threadpool(run_turn)
        except Exception as error:  # noqa: BLE001 — never leak internals to the client
            log_error(f"api.chat: agent failed for {session_id}: {error}")
            raise HTTPException(status_code=500, detail="The agent could not answer. Please try again.") from None

        error_status = _model_error(getattr(output, "content", "") or "")
        if error_status:
            log_error(f"api.chat: model error for {session_id}: {error_status}")
            raise HTTPException(status_code=503, detail="The assistant is busy right now. Please try again in a moment.")

        base_url = public_base_url or str(request.base_url)
        attachments = await run_in_threadpool(collect_attachments, output, store, base_url)
        log_info(f"api.chat: answered {session_id} ({len(attachments)} attachments)")
        return ChatResponse(reply=_reply_text(output), attachments=attachments)

    if isinstance(store, MemoryMediaStore):

        @router.get("/media/{media_id}")
        def media(media_id: str) -> Response:
            item = store.get(media_id)
            if item is None:
                raise HTTPException(status_code=404, detail="Not found")
            return Response(content=item.content, media_type=item.mime_type)

    return router
