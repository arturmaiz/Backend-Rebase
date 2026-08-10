"""Load balancer entrypoint.
"""

from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from . import lifecycle
from .config import LB_HOST, LB_PORT, REGISTRATION_DURATION_SECONDS, UPSTREAM_TIMEOUT
from .routes import blobs_router, internal_router


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
        print(
            f"[startup] load balancer up; accepting node registrations for "
            f"{REGISTRATION_DURATION_SECONDS}s"
        )
        yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(internal_router, prefix="/internal")
    app.include_router(blobs_router, prefix="/blobs")
    return app


def main() -> None:
    app = create_app()
    uvicorn.run(app, host=LB_HOST, port=LB_PORT)


if __name__ == "__main__":
    main()
