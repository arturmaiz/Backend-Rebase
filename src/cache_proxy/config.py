import os


CACHE_PROXY_HOST = os.getenv("CACHE_PROXY_HOST", "0.0.0.0")
CACHE_PROXY_PORT = int(os.getenv("CACHE_PROXY_PORT", "9000"))

# Upstream blob API (typically the load balancer).
TARGET_BLOB_SERVER = os.getenv(
    "TARGET_BLOB_SERVER", "http://127.0.0.1:8080"
).rstrip("/")

MAX_ITEMS_IN_CACHE = int(os.getenv("MAX_ITEMS_IN_CACHE", "10"))
UPSTREAM_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "30"))
