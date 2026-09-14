"""Analytics (page-views) service entrypoint.

Wires together logging, the Postgres-backed routes, and uvicorn. On startup we
ensure the `page_views` table exists, then serve the page-views and report APIs.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from psycopg import OperationalError

from logging_setup import configure_logging


logger = configure_logging("pageviews")

from .config import DB_HOST, DB_PORT, PAGEVIEWS_HOST, PAGEVIEWS_PORT
from .db import connect, create_schema
from .routes import router as pageviews_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the schema exists before we start accepting requests.

    If the database is unreachable at startup we log a clear message and fail
    fast -- there is no point serving requests we cannot fulfil.
    """
    try:
        async with await connect() as conn:
            await create_schema(conn)
    except OperationalError:
        logger.error(
            "could not connect to the database at %s:%s on startup; is Postgres running?",
            DB_HOST,
            DB_PORT,
        )
        raise
    yield


async def db_unavailable_handler(request: Request, exc: OperationalError) -> JSONResponse:
    """Turn a lost/failed DB connection into a clean 503 instead of a raw 500."""
    logger.error("database unavailable while handling %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "database unavailable"},
    )


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    # No prefix: this service serves two path roots (/page-views and /report),
    # so each endpoint declares its own full path in routes.py.
    app.include_router(pageviews_router)
    # Any OperationalError bubbling out of an endpoint (e.g. DB down) becomes 503.
    app.add_exception_handler(OperationalError, db_unavailable_handler)
    return app


def main() -> None:
    app = create_app()
    logger.info("starting analytics service on port %d", PAGEVIEWS_PORT)
    uvicorn.run(app, host=PAGEVIEWS_HOST, port=PAGEVIEWS_PORT, log_config=None)


if __name__ == "__main__":
    main()
