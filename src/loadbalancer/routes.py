"""HTTP routes for the load balancer.

Two groups:
- internal API (/internal/nodes/): backend nodes register here during the startup
  window.
- application API (/blobs/{id}): client requests that we forward to a backend
  node.
"""

import httpx
from fastapi import APIRouter, Request
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse, StreamingResponse

from . import lifecycle, registry, routing
from .validation import InvalidRegistration, validate_registration


REGISTRATION_OVER_MESSAGE = (
    "the request was rejected because registration period is over"
)

# Hop-by-hop headers describe a single connection, not the whole message, so we
# never relay them (same rule as the proxy). We also drop Host, so httpx sets the
# correct one for the node we forward to.
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

# On the way back we also drop Date and Server: our own server (uvicorn) sets
# those itself, so relaying the node's copies would duplicate them.
RESPONSE_DROP = HOP_BY_HOP | {"date", "server"}


internal_router = APIRouter()
blobs_router = APIRouter()


# --- internal API ---------------------------------------------------------


@internal_router.post("/nodes/")
async def register_node(request: Request):
    # Registrations are only accepted during the startup window.
    if not lifecycle.registration_open():
        return JSONResponse(
            status_code=403,
            content={"errorMessage": REGISTRATION_OVER_MESSAGE},
        )

    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"errorMessage": "body must be valid JSON"},
        )

    try:
        host, port, name = validate_registration(body)
    except InvalidRegistration as exc:
        return JSONResponse(status_code=400, content={"errorMessage": str(exc)})

    node_id = registry.upsert(host, port, name)
    print(f"[register] node {node_id} at {host}:{port} name={name!r}")
    return JSONResponse(status_code=200, content={"id": node_id})


@internal_router.get("/nodes/")
async def list_nodes():
    data = [
        {
            "id": node["id"],
            "destination": {"host": node["host"], "port": node["port"]},
            "name": node["name"],
        }
        for node in registry.all_nodes()
    ]
    return JSONResponse(status_code=200, content={"data": data})


# --- application API (forwarded to a backend node) ------------------------


async def _forward(request: Request, blob_id: str):
    # The application API only turns on once the registration window has closed.
    if lifecycle.registration_open():
        return JSONResponse(
            status_code=503,
            content={"errorMessage": "load balancer is still starting up"},
        )

    node = routing.pick_node(blob_id)
    if node is None:
        return JSONResponse(
            status_code=503,
            content={"errorMessage": "no backend nodes are registered"},
        )

    url = f"http://{node['host']}:{node['port']}/blobs/{blob_id}"

    # Forward the client's headers, minus hop-by-hop and Host.
    # We drop Host so httpx fills in the node's real host (its host:port) instead
    # of leaving the load balancer's Host in place. We keep Content-Length: the
    # blob server requires it, and its presence makes httpx send the body as-is
    # instead of switching to chunked encoding.
    forward_headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP and name.lower() != "host"
    }

    # Only POST carries a body to forward.
    body = request.stream() if request.method == "POST" else None

    client = request.app.state.client
    upstream_request = client.build_request(
        request.method,
        url,
        headers=forward_headers,
        content=body,
    )

    try:
        upstream = await client.send(upstream_request, stream=True)
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"errorMessage": "backend node timed out"},
        )
    except httpx.RequestError:
        return JSONResponse(
            status_code=502,
            content={"errorMessage": "could not reach backend node"},
        )

    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() not in RESPONSE_DROP
    }

    print(
        f"[route] {request.method} /blobs/{blob_id} -> "
        f"{node['host']}:{node['port']} ({upstream.status_code})"
    )

    # Stream the node's response straight back, and close the upstream response
    # once we have finished relaying it.
    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        headers=response_headers,
        background=BackgroundTask(upstream.aclose),
    )


@blobs_router.post("/{blob_id}")
async def post_blob(blob_id: str, request: Request):
    return await _forward(request, blob_id)


@blobs_router.get("/{blob_id}")
async def get_blob(blob_id: str, request: Request):
    return await _forward(request, blob_id)


@blobs_router.delete("/{blob_id}")
async def delete_blob(blob_id: str, request: Request):
    return await _forward(request, blob_id)
