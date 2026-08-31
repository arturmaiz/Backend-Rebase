#!/usr/bin/env bash
# Run all services for the meeting demo (load balancer + two blob nodes).
# Usage: ./scripts/run_demo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/src"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export NODE_ADVERTISE_HOST="${NODE_ADVERTISE_HOST:-127.0.0.1}"
export LB_PORT="${LB_PORT:-8080}"
export MASTER_NODE_ADDRESS="${MASTER_NODE_ADDRESS:-http://127.0.0.1:${LB_PORT}}"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "Starting load balancer on port ${LB_PORT}..."
python -m loadbalancer.app &
PIDS+=($!)
sleep 1

echo "Starting blob node 1 on port 3001..."
PORT=3001 DATA_DIR="$ROOT/data-node1" NODE_NAME=node-1 \
  MASTER_NODE_ADDRESS="$MASTER_NODE_ADDRESS" NODE_ADVERTISE_HOST="$NODE_ADVERTISE_HOST" \
  python server.py &
PIDS+=($!)

echo "Starting blob node 2 on port 3002..."
PORT=3002 DATA_DIR="$ROOT/data-node2" NODE_NAME=node-2 \
  MASTER_NODE_ADDRESS="$MASTER_NODE_ADDRESS" NODE_ADVERTISE_HOST="$NODE_ADVERTISE_HOST" \
  python server.py &
PIDS+=($!)

echo ""
echo "Demo stack is running:"
echo "  Load balancer:  http://127.0.0.1:${LB_PORT}"
echo "  Blob node 1:      http://127.0.0.1:3001"
echo "  Blob node 2:      http://127.0.0.1:3002"
echo ""
echo "Wait ~${REGISTRATION_DURATION_SECONDS:-20}s for registration to close, then:"
echo "  curl -X POST http://127.0.0.1:${LB_PORT}/blobs/demo -H 'Content-Length: 5' -d 'hello'"
echo "  curl http://127.0.0.1:${LB_PORT}/blobs/demo"
echo ""
echo "Press Ctrl+C to stop all services."

wait
