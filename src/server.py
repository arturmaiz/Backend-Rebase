# src/server.py

from pathlib import Path

import uvicorn
from fastapi import FastAPI

from config import DATA_DIR, PORT
from routes.blobs import cleanup_temp_files, router as blobs_router


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

    app = FastAPI()

    app.include_router(
        blobs_router,
        prefix="/blobs",
    )

    return app


def main() -> None:
    warmup()

    app = create_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
    )


if __name__ == "__main__":
    main()