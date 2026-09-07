"""HTTP routes for the users microservice."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from .config import SNOWFLAKE_MACHINE_ID
from .db import (
    connect,
    fetch_active_user,
    get_user_row,
    insert_user,
    soft_delete_user,
    update_user_active,
)
from .snowflake import SnowflakeGenerator


logger = logging.getLogger("users.routes")

router = APIRouter()

# One generator shared by every request: it holds the per-millisecond sequence
# state, so a single long-lived instance is what keeps ids unique and ordered.
id_generator = SnowflakeGenerator(machine_id=SNOWFLAKE_MACHINE_ID)


class UpsertUser(BaseModel):
    """Request body for POST /users/. We assume valid input per the assignment."""

    email: str
    full_name: str


@router.post("/")
async def upsert_user(payload: UpsertUser):
    """UPSERT a user. Returns only a status code (CQRS), plus a structured log.

    Three outcomes, decided from the row's state BEFORE we write:
    - no row        -> INSERT       -> 201 created
    - soft-deleted  -> clear flag   -> 200 reactivated
    - active        -> refresh name -> 200 already active
    """
    email = payload.email
    full_name = payload.full_name
    now = datetime.now(timezone.utc)

    async with await connect() as conn:
        row = await get_user_row(conn, email)
        if row is None:
            await insert_user(conn, id_generator.next_id(), email, full_name, now)
            event, http_status = "user_created", status.HTTP_201_CREATED
        else:
            (deleted_since,) = row
            await update_user_active(conn, email, full_name)
            if deleted_since is not None:
                event, http_status = "user_reactivated", status.HTTP_200_OK
            else:
                event, http_status = "user_already_active", status.HTTP_200_OK
        await conn.commit()

    logger.info(event.replace("_", " "), extra={"event": event, "email": email})
    return Response(status_code=http_status)


@router.get("/{email}")
async def get_user(email: str):
    """Return an active user's public fields, or 404 if missing/soft-deleted."""
    async with await connect() as conn:
        row = await fetch_active_user(conn, email)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    email, full_name, joined_at = row
    return {
        "email": email,
        "full_name": full_name,
        "joined_at": joined_at.astimezone(timezone.utc).isoformat(),
    }


@router.delete("/{email}")
async def delete_user(email: str):
    """Soft-delete a user if active. Empty 204 either way; log the outcome."""
    now = datetime.now(timezone.utc)
    async with await connect() as conn:
        affected = await soft_delete_user(conn, email, now)
        await conn.commit()

    if affected == 1:
        logger.info(
            "user soft-deleted",
            extra={"event": "user_soft_deleted", "email": email},
        )
    else:
        logger.info(
            "user delete no-op (missing or already inactive)",
            extra={"event": "user_delete_noop", "email": email},
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
