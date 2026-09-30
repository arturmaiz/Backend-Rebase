"""HTTP routes for the analytics (page-views) service.

Endpoints:
- POST /page-views/single/  (increment one page at one time)
- POST /page-views/multi/   (aggregated increments across pages/hours)
- GET  /report/{page}       (last-24-hours report -- built later)
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from .db import connect, fetch_report, increment_buckets


logger = logging.getLogger("pageviews.routes")

router = APIRouter()

# The custom format used by the multi payload's hour keys, e.g. "2025-06-01_21:00".
MULTI_HOUR_FORMAT = "%Y-%m-%d_%H:%M"


def _to_utc(timestamp: str) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware UTC datetime.

    A naive timestamp (no zone) is assumed to be UTC; a zoned one is converted
    to UTC. Used for both single's `timestamp` and report's `now` param.
    """
    dt = datetime.fromisoformat(timestamp)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_to_hour(timestamp: str) -> datetime:
    """Parse single's ISO-8601 timestamp and round DOWN to its round hour (UTC).

    Minutes/seconds are zeroed so the view lands in the right bucket.
    """
    return _to_utc(timestamp).replace(minute=0, second=0, microsecond=0)


def _multi_key_to_hour(hour_key: str) -> datetime:
    """Parse a multi hour key like "2025-06-01_21:00" into a UTC datetime.

    These keys are already round hours, so we only parse and attach UTC.
    """
    return datetime.strptime(hour_key, MULTI_HOUR_FORMAT).replace(tzinfo=timezone.utc)


class SinglePageView(BaseModel):
    """Request body for POST /page-views/single/. We assume valid input."""

    page: str
    timestamp: str


@router.post("/page-views/single/")
async def increment_single(payload: SinglePageView):
    """Record one view: add 1 to the (page, rounded-hour) bucket."""
    hour = _iso_to_hour(payload.timestamp)
    async with await connect() as conn:
        await increment_buckets(conn, [(payload.page, hour, 1)])
        await conn.commit()

    logger.info(
        "single increment",
        extra={"event": "increment_single", "page": payload.page},
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/page-views/multi/")
async def increment_multi(payload: dict[str, dict[str, int]]):
    """Record aggregated views: {page: {hour_key: count}} -> one atomic upsert.

    We flatten the nested payload into (page, hour, count) triples, then hand the
    whole batch to a single multi-row upsert.
    """
    rows = [
        (page, _multi_key_to_hour(hour_key), count)
        for page, hours in payload.items()
        for hour_key, count in hours.items()
    ]

    async with await connect() as conn:
        await increment_buckets(conn, rows)
        await conn.commit()

    logger.info(
        "multi increment",
        extra={"event": "increment_multi", "rows": len(rows)},
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/report/{page}")
async def get_report(
    page: str,
    now: str | None = None,
    order: str = "asc",
    take: int | None = None,
):
    """Last-24-hours view report for a page, split by round hour.

    The window is the 24 completed hours before "now": with H = now floored to
    its hour, we return buckets in [H - 24h, H). Ordering by the real timestamp
    makes the hours wrap correctly across midnight (e.g. 21, 22, 23, 0, ...).
    """
    when = _to_utc(now) if now is not None else datetime.now(timezone.utc)
    upper = when.replace(minute=0, second=0, microsecond=0)
    lower = upper - timedelta(hours=24)

    async with await connect() as conn:
        rows = await fetch_report(conn, page, lower, upper, order, take)

    # Shape into the assignment's response: hour-of-day (0-23) and its views.
    # Convert to UTC before reading .hour so the value is correct regardless of
    # the database session's timezone.
    data = [{"h": hour.astimezone(timezone.utc).hour, "v": count} for hour, count in rows]
    return {"data": data}
