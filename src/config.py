import os
import re
from pathlib import Path


PORT = int(os.getenv("PORT", "3000"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

MAX_PAYLOAD_LENGTH = 10 * 1024 * 1024  # 10 MiB
MAX_DISK_QUOTA = 1024 * 1024 * 1024    # 1 GiB

MAX_HEADER_KEY_LENGTH = 30
MAX_HEADER_VALUE_LENGTH = 400
MAX_HEADER_COUNT = 20

MAX_ID_LENGTH = 200
MAX_BLOBS_TOTAL = 1_000_000

# Only needed for Level 3
MAX_BLOBS_IN_FOLDER = 1_000

VALID_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")