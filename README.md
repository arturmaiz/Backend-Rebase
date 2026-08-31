# Backend Rebase — Home Assignments

Python implementations of all backend-rebase lessons, runnable from a single repo.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: add LOGZIO_TOKEN for Logz.io
```

All services run from the `src/` directory:

```bash
cd src
```

## Quick demo (meeting stack)

Starts load balancer + two auto-registering blob nodes:

```bash
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh
```

Nodes register with the LB during the first **20 seconds**. After that window closes, use the **load balancer** URL (`http://127.0.0.1:8080`) for blob operations.

### Manual commands

**Terminal 1 — Load balancer**

```bash
cd src && python -m loadbalancer.app
```

**Terminal 2 — Blob node 1**

```bash
cd src
PORT=3001 DATA_DIR=../data-node1 NODE_NAME=node-1 \
  MASTER_NODE_ADDRESS=http://127.0.0.1:8080 NODE_ADVERTISE_HOST=127.0.0.1 \
  python server.py
```

**Terminal 3 — Blob node 2** (optional second node)

```bash
cd src
PORT=3002 DATA_DIR=../data-node2 NODE_NAME=node-2 \
  MASTER_NODE_ADDRESS=http://127.0.0.1:8080 NODE_ADVERTISE_HOST=127.0.0.1 \
  python server.py
```

**Test via load balancer** (after 20s registration window):

```bash
curl -X POST http://127.0.0.1:8080/blobs/hello \
  -H 'Content-Length: 5' -H 'Content-Type: text/plain' \
  -d 'world'

curl http://127.0.0.1:8080/blobs/hello
curl http://127.0.0.1:8080/internal/nodes/
```

## Logz.io (distributed flow)

Set in `.env`:

```
LOGZIO_TOKEN=your-token
LOGZIO_TYPE=backend-rebase
LOGZIO_SERVICE=Artur&Tom
```

Both the blob server and load balancer ship logs to Logz.io when `LOGZIO_TOKEN` is set. Search by `service` and follow registration → routing → blob operations across nodes.

## Lessons in this repo

| Lesson | Entry point | Notes |
|--------|-------------|-------|
| 1. Primality test | `python primality.py input.txt` | Multiprocessing, all CPU cores |
| 2. Blob HTTP server | `python server.py` | Streaming, quota, crash-safe overwrite |
| 3. HTTP forward proxy | `python proxy.py` | `curl -x 127.0.0.1:43210 http://httpbin.org/uuid` |
| 4. Load balancer | `python -m loadbalancer.app` | Registration window, circuit breaker |
| 5. Cache proxy | `python -m cache_proxy.app` | LRU cache, `X-Cache: HIT/MISS` |
| 6. Integration | `MASTER_NODE_ADDRESS` + Logz.io | Auto-registration on blob startup |

### Cache proxy (optional front door)

```bash
cd src
TARGET_BLOB_SERVER=http://127.0.0.1:8080 python -m cache_proxy.app
# listens on :9000

curl -X POST http://127.0.0.1:9000/blobs/cached -H 'Content-Length: 3' -d 'abc'
curl -i http://127.0.0.1:9000/blobs/cached   # X-Cache: MISS
curl -i http://127.0.0.1:9000/blobs/cached   # X-Cache: HIT
```

## Environment variables

| Variable | Default | Used by |
|----------|---------|---------|
| `PORT` | `3000` | Blob server |
| `DATA_DIR` | `../data` | Blob server storage |
| `MASTER_NODE_ADDRESS` | — | Blob server auto-registration |
| `NODE_ADVERTISE_HOST` | hostname | Address sent to LB |
| `NODE_NAME` | — | Optional node label |
| `LB_PORT` | `8080` | Load balancer |
| `LOGZIO_TOKEN` | — | Logz.io shipping |
| `TARGET_BLOB_SERVER` | `http://127.0.0.1:8080` | Cache proxy upstream |
| `CACHE_PROXY_PORT` | `9000` | Cache proxy |
| `MAX_ITEMS_IN_CACHE` | `10` | Cache proxy LRU size |
