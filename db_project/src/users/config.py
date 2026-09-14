"""Configuration for the users microservice.

All values come from environment variables (loaded from db_project/.env by
logging_setup._load_dotenv)
"""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Where the users HTTP service listens for clients.
USERS_HOST = os.getenv("USERS_HOST", "0.0.0.0")
USERS_PORT = int(os.getenv("USERS_PORT", "8000"))

# Postgres connection settings. These match the docker command in the notes.
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "usersdb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Field length caps that mirror the table's column definitions, so we can
# reject over-long input before it ever reaches Postgres if we choose to.
MAX_EMAIL_LENGTH = 200
MAX_FULL_NAME_LENGTH = 200

# Identifies this node when minting Snowflake IDs (0..1023). Each independently
# running instance must use a distinct value so their ids can never collide.
SNOWFLAKE_MACHINE_ID = int(os.getenv("SNOWFLAKE_MACHINE_ID", "0"))
