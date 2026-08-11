"""Optional blob-server auto-registration with the load balancer.

When MASTER_NODE_ADDRESS is set, the blob server POSTs itself to
/internal/nodes/ and retries for up to 30s while the master is unreachable.
"""

import asyncio
import json
import logging
import os
import socket

import httpx


logger = logging.getLogger("blobs.registration")

MASTER_NODE_ADDRESS = os.getenv("MASTER_NODE_ADDRESS")

# Total time we keep retrying before giving up, and the gap between attempts.
REGISTRATION_RETRY_TOTAL_SECONDS = float(
    os.getenv("REGISTRATION_RETRY_TOTAL_SECONDS", "30")
)
REGISTRATION_RETRY_INTERVAL_SECONDS = float(
    os.getenv("REGISTRATION_RETRY_INTERVAL_SECONDS", "2")
)
REGISTRATION_ATTEMPT_TIMEOUT_SECONDS = float(
    os.getenv("REGISTRATION_ATTEMPT_TIMEOUT_SECONDS", "2")
)

# How this node tells the load balancer to reach it.
NODE_ADVERTISE_HOST = os.getenv("NODE_ADVERTISE_HOST") or socket.gethostname()
NODE_NAME = os.getenv("NODE_NAME")


def _normalize_master_url(address: str) -> str:
    if address.startswith(("http://", "https://")):
        return address.rstrip("/")
    return f"http://{address.rstrip('/')}"


async def register_with_master(
    port: int,
    *,
    master_address: str | None = None,
    clock=None,
) -> str | None:
    """
    Announce this blob server to the load balancer.

    Retries for REGISTRATION_RETRY_TOTAL_SECONDS while the master is unreachable
    or times out, then gives up. Returns the assigned node id, or None if we
    never got registered. A 4xx answer is final — retrying cannot start succeeding.
    """

    address = master_address if master_address is not None else MASTER_NODE_ADDRESS
    if not address:
        logger.info("MASTER_NODE_ADDRESS is not set, skipping self registration")
        return None

    clock = clock or asyncio.get_running_loop().time
    base_url = _normalize_master_url(address)
    url = f"{base_url}/internal/nodes/"

    payload: dict = {
        "destination": {"host": NODE_ADVERTISE_HOST, "port": port},
    }
    if NODE_NAME:
        payload["name"] = NODE_NAME

    body = json.dumps(payload).encode("utf-8")
    deadline = clock() + REGISTRATION_RETRY_TOTAL_SECONDS
    attempt = 0

    logger.info(
        "registering with master at %s as %s:%d (retrying for up to %.0fs)",
        url,
        NODE_ADVERTISE_HOST,
        port,
        REGISTRATION_RETRY_TOTAL_SECONDS,
    )

    async with httpx.AsyncClient(
        timeout=REGISTRATION_ATTEMPT_TIMEOUT_SECONDS
    ) as client:
        while True:
            attempt += 1
            try:
                response = await client.post(
                    url,
                    content=body,
                    headers={"content-type": "application/json"},
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "registration attempt %d failed: %s",
                    attempt,
                    exc,
                )
            else:
                if response.status_code == 200:
                    node_id = response.json().get("id")
                    logger.info(
                        "registered with master as node id=%s after %d attempt(s)",
                        node_id,
                        attempt,
                    )
                    return node_id

                if 400 <= response.status_code < 500:
                    logger.error(
                        "master rejected registration with %d: %s — not retrying",
                        response.status_code,
                        response.text,
                    )
                    return None

                logger.warning(
                    "registration attempt %d got %d from master",
                    attempt,
                    response.status_code,
                )

            remaining = deadline - clock()
            if remaining <= 0:
                logger.error(
                    "giving up on registration after %d attempt(s) and %.0fs",
                    attempt,
                    REGISTRATION_RETRY_TOTAL_SECONDS,
                )
                return None

            await asyncio.sleep(min(REGISTRATION_RETRY_INTERVAL_SECONDS, remaining))
