"""Postgres connection plumbing for the users microservice (async).

- `connect()` opens a single async psycopg connection from the config settings.
- `create_schema()` runs schema.sql once to create the `users` table.

psycopg sends SQL via a cursor (await cur.execute(...)) and only persists
writes after `await conn.commit()`. We use psycopg's async mode so the FastAPI
handlers can `await` the database without blocking the event loop.
"""

import asyncio
import logging
from pathlib import Path

import psycopg

from .config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


logger = logging.getLogger("users.db")

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def connect() -> psycopg.AsyncConnection:
    """Open one async Postgres connection using the configured settings."""
    return await psycopg.AsyncConnection.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


async def create_schema(conn: psycopg.AsyncConnection) -> None:
    """Create the `users` table if it does not already exist."""
    sql = SCHEMA_PATH.read_text()
    async with conn.cursor() as cur:
        await cur.execute(sql)
    await conn.commit()
    logger.info("users table is ready")


async def fetch_active_user(
    conn: psycopg.AsyncConnection, email: str
) -> tuple | None:
    """Return (email, full_name, joined_at) for an ACTIVE user, else None.

    "Active" means the row exists AND deleted_since IS NULL, so a soft-deleted
    user is reported the same as a missing one (both come back as None).
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT email, full_name, joined_at
            FROM users
            WHERE email = %s AND deleted_since IS NULL
            """,
            (email,),
        )
        return await cur.fetchone()


async def soft_delete_user(
    conn: psycopg.AsyncConnection, email: str, now
) -> int:
    """Soft-delete an active user; return how many rows were affected.

    The `AND deleted_since IS NULL` guard means we only stamp a user who is
    currently active, so we never overwrite an earlier deletion time. The caller
    reads the return value: 1 = we just soft-deleted; 0 = missing or already
    inactive. The caller is responsible for committing.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET deleted_since = %s
            WHERE email = %s AND deleted_since IS NULL
            """,
            (now, email),
        )
        return cur.rowcount


async def get_user_row(conn: psycopg.AsyncConnection, email: str) -> tuple | None:
    """Read the current state of a user by email (no active-only filter).

    Return value distinguishes all three states we care about for the upsert:
    - None           -> no row at all (user never existed)
    - (None,)        -> row exists and is active (deleted_since is NULL)
    - (<timestamp>,) -> row exists but is soft-deleted
    """
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT deleted_since FROM users WHERE email = %s",
            (email,),
        )
        return await cur.fetchone()


async def insert_user(
    conn: psycopg.AsyncConnection,
    user_id: int,
    email: str,
    full_name: str,
    joined_at,
) -> None:
    """Insert a brand-new user row (user_id is a 64-bit Snowflake ID)."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, email, full_name, joined_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, email, full_name, joined_at),
        )


async def update_user_active(
    conn: psycopg.AsyncConnection, email: str, full_name: str
) -> None:
    """Clear the soft-delete flag and refresh the name for an existing user.

    Deliberately does NOT touch id or joined_at, so a returning user keeps their
    original identity and join date. Setting deleted_since to NULL is a no-op if
    it was already NULL, so this works for both "reactivate" and "already active".
    """
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE users SET deleted_since = NULL, full_name = %s WHERE email = %s",
            (full_name, email),
        )


async def main() -> None:
    """Standalone entrypoint: create the table, then report the columns.

    Run with:  cd db_project/src && python -m users.db
    """
    logging.basicConfig(level=logging.INFO)
    async with await connect() as conn:
        await create_schema(conn)
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
                ORDER BY ordinal_position
                """
            )
            print("users table columns:")
            for column_name, data_type, is_nullable in await cur.fetchall():
                nn = "NOT NULL" if is_nullable == "NO" else "nullable"
                print(f"  {column_name:<14} {data_type:<26} {nn}")


if __name__ == "__main__":
    asyncio.run(main())
