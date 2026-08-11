import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from logging_setup import configure_logging

logger = configure_logging("blobs")

from config import DATA_DIR, PORT  # noqa: E402
from registration import (  # noqa: E402
    MASTER_NODE_ADDRESS,
    register_with_master,
)
from routes.blobs import cleanup_temp_files, router as blobs_router  # noqa: E402


def warmup() -> None:
    """
    Prepare the storage before the HTTP server starts.
    """

    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    cleanup_temp_files()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Register in the background: the load balancer's registration window is
        # short, and it may probe us while we are still retrying.
        task = None
        if MASTER_NODE_ADDRESS:
            task = asyncio.create_task(register_with_master(PORT))

        yield

        if task is not None and not task.done():
            task.cancel()

    app = FastAPI(lifespan=lifespan)

    app.include_router(
        blobs_router,
        prefix="/blobs",
    )

    return app


def main() -> None:
    warmup()

    app = create_app()

    logger.info("starting blob server on port %d", PORT)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_config=None,
    )


if __name__ == "__main__":
    main()
