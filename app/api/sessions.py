"""Session ids and per-session locks for API channels.

Every channel prefixes its ids (``web:`` here, ``wa:`` in Semente's WhatsApp
router), so sessions from different channels never collide in the shared
session store.

The lock keeps two turns of the same session from running at once in this
process (a user sending a second message before the first answer). It does
not protect several instances; with Cloud SQL and more than one instance,
Cloud Run session affinity keeps a user on one instance most of the time.
"""

import threading

_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


def channel_session_id(channel: str, client_session_id: str) -> str:
    """Builds the id stored in the session store for a client session.

    Args:
        channel (str): Channel prefix, for example ``"web"``.
        client_session_id (str): The id sent by the client.

    Returns:
        str: ``"<channel>:<client_session_id>"``.
    """
    return f"{channel}:{client_session_id}"


def session_lock(session_id: str) -> threading.Lock:
    """Returns the lock of one session, creating it on first use.

    Args:
        session_id (str): The stored session id.

    Returns:
        threading.Lock: The lock to hold while the session's turn runs.
    """
    with _GUARD:
        lock = _LOCKS.get(session_id)
        if lock is None:
            lock = _LOCKS[session_id] = threading.Lock()
        return lock
