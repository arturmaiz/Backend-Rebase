"""Configuration for the load balancer process.
"""

import os


# Where the load balancer itself listens for clients.
LB_HOST = os.getenv("LB_HOST", "0.0.0.0")
LB_PORT = int(os.getenv("LB_PORT", "8080"))

# How long (from process start) we accept node registrations. After this window
# the node set is frozen and the /blobs API becomes usable. Env-configurable so
# testing can widen the window; the assignment's real value is 20.
REGISTRATION_DURATION_SECONDS = int(os.getenv("REGISTRATION_DURATION_SECONDS", "20"))

# Timeout when forwarding a client request to a backend node. Same idea as the
# proxy's UPSTREAM_TIMEOUT: never let one stuck node hang us forever.
UPSTREAM_TIMEOUT = 30.0

# Validation limits for the registration payload.
MAX_HOST_LENGTH = 50
MAX_NAME_LENGTH = 50

# --- Optional circuit-breaker feature (not used yet; reserved for later) ---
NODE_MAX_FAILURES = 3
BURNED_NODE_COOLDOWN_SECONDS = 60
