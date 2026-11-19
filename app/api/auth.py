"""Optional API key check for the web channel.

On Cloud Run the service is private and Cloud Run IAM checks the caller's
ID token before a request reaches the app, so no key is needed. Set
``PASTO_BACANO_API_KEY`` only when the service must be public (for example
when the WhatsApp webhook shares it) or for local tests; clients then send
``Authorization: Bearer <key>`` (the website's ``AGENT_AUTH=apikey`` mode).
"""

import hmac
import os
from typing import Callable, Optional

from fastapi import HTTPException, Request


def api_key_dependency(api_key: Optional[str] = None) -> Callable[[Request], None]:
    """Builds a FastAPI dependency that enforces the key when one is configured.

    Args:
        api_key (str | None): The expected key; defaults to ``PASTO_BACANO_API_KEY``.
            Empty or unset disables the check.

    Returns:
        Callable: The dependency, raising HTTP 401 on a missing or wrong key.
    """
    expected = api_key if api_key is not None else os.getenv("PASTO_BACANO_API_KEY", "")

    def check(request: Request) -> None:
        if not expected:
            return
        header = request.headers.get("authorization", "")
        supplied = header[7:] if header.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Unauthorized")

    return check
