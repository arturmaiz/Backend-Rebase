"""Tracks the registration window.

The load balancer has two phases: for the first REGISTRATION_DURATION_SECONDS it
accepts node registrations, and after that it serves /blobs traffic. This module
just answers "which phase are we in right now?".
"""

import time

from .config import REGISTRATION_DURATION_SECONDS


# Set once, when the server boots (see start()). None means "not started yet".
_started_at: float | None = None


def start() -> None:
    """Record the moment the server came up. Call this once at startup."""
    global _started_at
    _started_at = time.time()


def registration_open() -> bool:
    """True while we are still inside the registration window."""
    if _started_at is None:
        return False
    return (time.time() - _started_at) < REGISTRATION_DURATION_SECONDS
