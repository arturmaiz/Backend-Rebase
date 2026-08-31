"""Cache proxy entrypoint.

Run from the src/ directory:
    python -m cache_proxy.app
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from logging_setup import configure_logging

logger = configure_logging("cache_proxy")

from cache_proxy.config import (  # noqa: E402
    CACHE_PROXY_HOST,
    CACHE_PROXY_PORT,
    MAX_ITEMS_IN_CACHE,
    TARGET_BLOB_SERVER,
    UPSTREAM_TIMEOUT,
)
from cache_proxy.routes import router as cache_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
        app.state.client = client
        logger.info(
            "cache proxy up on %s:%d (upstream=%s, capacity=%d)",
            CACHE_PROXY_HOST,
            CACHE_PROXY_PORT,
            TARGET_BLOB_SERVER,
            MAX_ITEMS_IN_CACHE,
        )
        yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(cache_router, prefix="/blobs")
    return app


def main() -> None:
    app = create_app()
    uvicorn.run(
        app,
        host=CACHE_PROXY_HOST,
        port=CACHE_PROXY_PORT,
        log_config=None,
    )


if __name__ == "__main__":
    main()
