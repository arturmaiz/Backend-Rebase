"""Users microservice entrypoint.

Wires together logging, the Postgres-backed routes, and uvicorn. On startup we
ensure the `users` table exists, then serve the /users API.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from logging_setup import configure_logging


logger = configure_logging("users")

from .config import USERS_HOST, USERS_PORT
from .db import connect, create_schema
from .routes import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the schema exists before we start accepting requests."""
    async with await connect() as conn:
        await create_schema(conn)
    yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(users_router, prefix="/users")
    return app


def main() -> None:
    app = create_app()
    logger.info("starting users service on port %d", USERS_PORT)
    uvicorn.run(app, host=USERS_HOST, port=USERS_PORT, log_config=None)


if __name__ == "__main__":
    main()
