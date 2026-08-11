"""Load balancer entrypoint.
"""

from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from logging_setup import configure_logging

logger = configure_logging("lb")

from . import lifecycle  # noqa: E402
from .config import (  # noqa: E402
    LB_HOST,
    LB_PORT,
    REGISTRATION_DURATION_SECONDS,
    UPSTREAM_TIMEOUT,
)
from .routes import blobs_router, internal_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook.

    On startup we stamp the process start time (which opens the registration
    window) and open one shared httpx client for all forwarding, mirroring the
    proxy's single AsyncClient. The `async with` closes the client on shutdown.
    """
    lifecycle.start()
    async with httpx.AsyncClient(
        timeout=UPSTREAM_TIMEOUT, follow_redirects=False
    ) as client:
        app.state.client = client
        logger.info(
            "load balancer up; accepting node registrations for %ss",
            REGISTRATION_DURATION_SECONDS,
        )
        yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(internal_router, prefix="/internal")
    app.include_router(blobs_router, prefix="/blobs")
    return app


def main() -> None:
    app = create_app()
    logger.info("starting load balancer on %s:%d", LB_HOST, LB_PORT)
    # log_config=None keeps our logging_setup handlers (including Logz.io).
    uvicorn.run(app, host=LB_HOST, port=LB_PORT, log_config=None)


if __name__ == "__main__":
    main()
