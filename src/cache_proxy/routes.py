"""HTTP cache proxy for the blob API (lesson 5, part 2)."""

import logging

import httpx
from fastapi import APIRouter, Request, Response

from cache.lru import LeastRecentlyUsedCache
from cache_proxy.config import MAX_ITEMS_IN_CACHE, TARGET_BLOB_SERVER, UPSTREAM_TIMEOUT
from cache_proxy.models import CachedBlob


logger = logging.getLogger("cache_proxy.routes")

router = APIRouter()
cache = LeastRecentlyUsedCache(MAX_ITEMS_IN_CACHE)

# Headers we set ourselves or that must not be forwarded from upstream.
RESPONSE_DROP = {
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
}


def _upstream_url(blob_id: str) -> str:
    return f"{TARGET_BLOB_SERVER}/blobs/{blob_id}"


def _forward_request_headers(request: Request) -> dict[str, str]:
    return {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in {"host", "connection", "keep-alive"}
    }


def _extract_stored_headers(response: httpx.Response) -> dict[str, str]:
    stored: dict[str, str] = {}
    for name, value in response.headers.items():
        lower = name.lower()
        if lower == "content-type" or lower.startswith("x-rebase-"):
            stored[lower] = value
    return stored


def _response_from_cache(entry: CachedBlob, *, cache_status: str) -> Response:
    headers = dict(entry.headers)
    headers["X-Cache"] = cache_status
    headers["Content-Length"] = str(len(entry.body))
    return Response(
        content=entry.body,
        status_code=entry.status_code,
        media_type=entry.media_type,
        headers=headers,
    )


def _entry_from_response(response: httpx.Response) -> CachedBlob:
    stored_headers = _extract_stored_headers(response)
    media_type = stored_headers.pop(
        "content-type", response.headers.get("content-type", "application/octet-stream")
    )
    return CachedBlob(
        body=response.content,
        headers=stored_headers,
        media_type=media_type,
        status_code=response.status_code,
    )


@router.post("/{blob_id}")
async def post_blob(blob_id: str, request: Request):
    client: httpx.AsyncClient = request.app.state.client
    headers = _forward_request_headers(request)

    upstream = await client.post(
        _upstream_url(blob_id),
        headers=headers,
        content=request.stream(),
    )

    if 200 <= upstream.status_code < 300:
        try:
            refresh = await client.get(_upstream_url(blob_id))
            if refresh.status_code == 200:
                cache.put(blob_id, _entry_from_response(refresh))
                logger.info("cached blob %s after POST", blob_id)
        except httpx.HTTPError:
            logger.warning("POST succeeded but cache refresh failed for %s", blob_id)

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers={
            name: value
            for name, value in upstream.headers.items()
            if name.lower() not in RESPONSE_DROP
        },
    )


@router.get("/{blob_id}")
async def get_blob(blob_id: str, request: Request):
    cached = cache.try_get(blob_id)
    if cached is not None:
        logger.info("cache HIT for %s", blob_id)
        return _response_from_cache(cached, cache_status="HIT")

    client: httpx.AsyncClient = request.app.state.client
    try:
        upstream = await client.get(_upstream_url(blob_id))
    except httpx.HTTPError:
        return Response(status_code=502, content="could not reach upstream blob server")

    if upstream.status_code == 200:
        entry = _entry_from_response(upstream)
        cache.put(blob_id, entry)
        logger.info("cache MISS for %s (stored after upstream GET)", blob_id)
        return _response_from_cache(entry, cache_status="MISS")

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers={
            name: value
            for name, value in upstream.headers.items()
            if name.lower() not in RESPONSE_DROP
        },
    )


@router.delete("/{blob_id}")
async def delete_blob(blob_id: str, request: Request):
    client: httpx.AsyncClient = request.app.state.client
    upstream = await client.delete(_upstream_url(blob_id))

    if 200 <= upstream.status_code < 300 or upstream.status_code == 204:
        cache.remove(blob_id)
        logger.info("removed %s from cache after DELETE", blob_id)

    if upstream.status_code == 204:
        return Response(status_code=204)

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
