"""The cleaner ("The Wolf") -- a standalone janitor for the page_views table.

Reports only ever read the last RETENTION_HOURS, so any older bucket is dead
weight. This process wakes up every CLEANER_INTERVAL_SECONDS, deletes buckets
older than the window in one atomic statement, logs how many it removed, and
sleeps again. It is separate from the web service on purpose, and the system is
correct even if it never runs -- it only manages space, not correctness.

Run with:  cd analytics_project/src && python -m pageviews.cleaner
"""

import asyncio
from datetime import datetime, timedelta, timezone

from logging_setup import configure_logging


logger = configure_logging("pageviews.cleaner")

from .config import CLEANER_INTERVAL_SECONDS, RETENTION_HOURS
from .db import connect, delete_old_buckets


def _cutoff(now: datetime) -> datetime:
    """Oldest hour a report can still need: current hour (floored) minus retention.

    Buckets with hour < this value can never appear in any report, so they are
    safe to delete. We keep the boundary bucket itself (hour == cutoff) because
    the report window includes it.
    """
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    return current_hour - timedelta(hours=RETENTION_HOURS)


async def clean_once() -> int:
    """Run one cleanup pass; return the number of buckets removed."""
    cutoff = _cutoff(datetime.now(timezone.utc))
    async with await connect() as conn:
        removed = await delete_old_buckets(conn, cutoff)
        await conn.commit()

    logger.info(
        "cleaner removed %d bucket(s) older than %s",
        removed,
        cutoff.isoformat(),
        extra={"event": "cleaner_run", "removed": removed},
    )
    return removed


async def main() -> None:
    """Loop forever: clean, then sleep. One bad run should not kill the loop."""
    logger.info(
        "cleaner starting (interval=%ds, retention=%dh)",
        CLEANER_INTERVAL_SECONDS,
        RETENTION_HOURS,
    )
    while True:
        try:
            await clean_once()
        except Exception:
            logger.exception("cleaner run failed; retrying next interval")
        await asyncio.sleep(CLEANER_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
