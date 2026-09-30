"""Configuration for the analytics (page-views) service.

All values come from environment variables (loaded from analytics_project/.env by
logging_setup._load_dotenv).
"""

import os


# Where the page-views HTTP service listens for clients. Port defaults to 8001 so
# it does not clash with the users service (8000) if both run locally.
PAGEVIEWS_HOST = os.getenv("PAGEVIEWS_HOST", "0.0.0.0")
PAGEVIEWS_PORT = int(os.getenv("PAGEVIEWS_PORT", "8001"))

# Postgres connection settings for the local Postgres instance.
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "analyticsdb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# The cleaner ("The Wolf"): how much history to keep, and how often it runs.
# Reports only ever look back 24h, so buckets older than that are dead weight.
RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "24"))
CLEANER_INTERVAL_SECONDS = int(os.getenv("CLEANER_INTERVAL_SECONDS", "3600"))
