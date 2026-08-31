"""The in-memory registry of backend nodes.

State lives in a single module-level dict, the same way blobs.py keeps its
shared state at module level. There is exactly one registry per load-balancer
process, so a module-level store is the natural fit (the in-memory mirror of how
the blob server treats its data directory as one shared store).

A node's identity is its (host, port) pair: that is what makes registration an
"upsert". Registering the same host:port twice does not create a second entry;
it just updates the name of the one already there.

We key the dict by (host, port). Python dicts preserve insertion order, which
matters later: once registration closes we route by hash(id) % number_of_nodes,
and that needs a stable ordering so index N always means the same node.

Each node is a plain dict: {"id", "host", "port", "name", "breaker"}, matching
how the rest of the codebase represents records (e.g. stored_headers in
blobs.py). The breaker tracks consecutive timeouts for that node.
"""

import logging
from uuid import uuid4

from .circuit_breaker import CircuitBreaker


logger = logging.getLogger("lb.registry")

_nodes: dict[tuple[str, int], dict] = {}


def upsert(host: str, port: int, name: str | None) -> str:
    """Insert a new node or update an existing one's name.

    Identity is (host, port). Returns the node's id (the existing id when the
    node was already registered, otherwise a freshly generated one).
    """
    key = (host, port)
    existing = _nodes.get(key)
    if existing is not None:
        existing["name"] = name
        logger.info(
            "updated node id=%s address=%s:%d name=%r",
            existing["id"],
            host,
            port,
            name,
        )
        return existing["id"]

    node_id = uuid4().hex
    _nodes[key] = {
        "id": node_id,
        "host": host,
        "port": port,
        "name": name,
        "breaker": CircuitBreaker(node_id),
    }
    logger.info(
        "registered node id=%s address=%s:%d name=%r (%d node(s) total)",
        node_id,
        host,
        port,
        name,
        len(_nodes),
    )
    return node_id


def all_nodes() -> list[dict]:
    """Every registered node, in registration order."""
    return list(_nodes.values())


def count() -> int:
    """How many nodes are registered."""
    return len(_nodes)
