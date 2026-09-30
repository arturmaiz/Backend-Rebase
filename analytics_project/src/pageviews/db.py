"""Postgres connection plumbing for the analytics service (async).

- `connect()` opens a single async psycopg connection from the config settings.
- `create_schema()` runs schema.sql once to create the `page_views` table.

psycopg sends SQL via a cursor (await cur.execute(...)) and only persists writes
after `await conn.commit()`. We use psycopg's async mode so the FastAPI handlers
can `await` the database without blocking the event loop.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import psycopg

from .config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


logger = logging.getLogger("pageviews.db")

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
    """Create the `page_views` table if it does not already exist."""
    sql = SCHEMA_PATH.read_text()
    async with conn.cursor() as cur:
        await cur.execute(sql)
    await conn.commit()
    logger.info("page_views table is ready")


async def increment_buckets(
    conn: psycopg.AsyncConnection,
    rows: list[tuple[str, datetime, int]],
) -> None:
    """Apply a batch of (page, hour, count) increments as ONE atomic upsert.

    Each row either creates a new bucket at `count`, or adds `count` to the
    existing bucket for that (page, hour). Because it is a single multi-row SQL
    statement, the whole batch is atomic and safe under concurrent calls without
    an explicit transaction -- exactly the constraint the assignment asks for.

    The caller is responsible for committing. `single` passes a one-row list;
    `multi` passes one row per (page, hour) entry in its payload.
    """
    if not rows:
        return

    # Build "(%s, %s, %s), (%s, %s, %s), ..." for however many rows we got. Only
    # the placeholders are formatted into the string; every actual value still
    # travels as a bound parameter, so this is not SQL injection.
    values_sql = ", ".join(["(%s, %s, %s)"] * len(rows))
    params = [field for row in rows for field in row]

    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            INSERT INTO page_views (page, hour, count)
            VALUES {values_sql}
            ON CONFLICT (page, hour)
            DO UPDATE SET count = page_views.count + EXCLUDED.count
            """,
            params,
        )


async def fetch_report(
    conn: psycopg.AsyncConnection,
    page: str,
    lower: datetime,
    upper: datetime,
    order: str,
    take: int | None,
) -> list[tuple[datetime, int]]:
    """Return (hour, count) rows for a page within [lower, upper).

    `lower`/`upper` are the 24-hour window bounds (both UTC, already floored to
    the hour) computed by the caller: lower = H - 24h, upper = H, where H is
    "now" floored to its hour. We only return buckets that actually exist
    (decision: no zero-filling), ordered by the real timestamp so the sequence
    wraps naturally across midnight. `take`, when set, caps the row count.
    """
    # order is validated to a fixed keyword, so it is safe to inline; every real
    # value (page, bounds, take) still travels as a bound parameter.
    direction = "DESC" if order.lower() == "desc" else "ASC"
    sql = f"""
        SELECT hour, count
        FROM page_views
        WHERE page = %s
          AND hour >= %s
          AND hour <  %s
        ORDER BY hour {direction}
    """
    params: list = [page, lower, upper]
    if take is not None:
        sql += " LIMIT %s"
        params.append(take)

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def delete_old_buckets(conn: psycopg.AsyncConnection, cutoff: datetime) -> int:
    """Delete every bucket older than `cutoff` and return how many were removed.

    A single DELETE statement (atomic on its own). The predicate is broad on
    purpose -- "anything older than the window" -- so the cleaner is self-healing:
    it converges the table to the desired state no matter how many runs were
    missed. The caller commits.
    """
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM page_views WHERE hour < %s", (cutoff,))
        return cur.rowcount


async def main() -> None:
    """Standalone entrypoint: create the table, then report the columns.

    Run with:  cd analytics_project/src && python -m pageviews.db
    """
    logging.basicConfig(level=logging.INFO)
    async with await connect() as conn:
        await create_schema(conn)
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'page_views'
                ORDER BY ordinal_position
                """
            )
            print("page_views table columns:")
            for column_name, data_type, is_nullable in await cur.fetchall():
                nn = "NOT NULL" if is_nullable == "NO" else "nullable"
                print(f"  {column_name:<14} {data_type:<26} {nn}")


if __name__ == "__main__":
    asyncio.run(main())
