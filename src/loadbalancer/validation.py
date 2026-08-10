"""Validation for the POST /internal/nodes registration payload.

The endpoint hands us whatever JSON arrived; this module decides whether it is
acceptable and hands back cleaned values. On any problem we raise
InvalidRegistration with a human-readable message, which the route turns into a
400 response.

We decided the strict character set applies to `name` only. `host` is validated
by length and a looser pattern so real addresses like "127.0.0.1" are legal.
"""

import re
from typing import Any

from .config import MAX_HOST_LENGTH, MAX_NAME_LENGTH


# name: the strict "textual field" character set from the assignment.
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# host: letters/digits plus dot and hyphen, so "127.0.0.1" and "node-a" pass.
HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")

PORT_MIN = 0
PORT_MAX = 65535


class InvalidRegistration(Exception):
    """Raised when a registration payload fails validation."""


def validate_registration(body: Any) -> tuple[str, int, str | None]:
    """Validate a parsed JSON body and return (host, port, name).

    `name` is None when it was missing, null, or an empty string.
    """
    if not isinstance(body, dict):
        raise InvalidRegistration("body must be a JSON object")

    destination = body.get("destination")
    if destination is None:
        raise InvalidRegistration("destination is required")
    if not isinstance(destination, dict):
        raise InvalidRegistration("destination must be an object")

    host = _validate_host(destination.get("host"))
    port = _validate_port(destination.get("port"))
    name = _validate_name(body.get("name"))
    return host, port, name


def _validate_host(host: Any) -> str:
    if host is None:
        raise InvalidRegistration("destination.host is required")
    if not isinstance(host, str):
        raise InvalidRegistration("destination.host must be a string")
    if not host:
        raise InvalidRegistration("destination.host must not be empty")
    if len(host) > MAX_HOST_LENGTH:
        raise InvalidRegistration(
            f"destination.host must be at most {MAX_HOST_LENGTH} characters"
        )
    if not HOST_PATTERN.match(host):
        raise InvalidRegistration("destination.host contains invalid characters")
    return host


def _validate_port(port: Any) -> int:
    # bool is a subclass of int in Python, so True/False would sneak through an
    # isinstance(int) check; reject it explicitly.
    if port is None:
        raise InvalidRegistration("destination.port is required")
    if isinstance(port, bool) or not isinstance(port, int):
        raise InvalidRegistration("destination.port must be an integer")
    if port < PORT_MIN or port > PORT_MAX:
        raise InvalidRegistration(
            f"destination.port must be between {PORT_MIN} and {PORT_MAX}"
        )
    return port


def _validate_name(name: Any) -> str | None:
    # null and "" are both "no name".
    if name is None or name == "":
        return None
    if not isinstance(name, str):
        raise InvalidRegistration("name must be a string")
    if len(name) > MAX_NAME_LENGTH:
        raise InvalidRegistration(
            f"name must be at most {MAX_NAME_LENGTH} characters"
        )
    if not NAME_PATTERN.match(name):
        raise InvalidRegistration("name contains invalid characters")
    return name
