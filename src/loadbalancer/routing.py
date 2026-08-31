"""Decides which backend node handles a given blob id.

We route by hashing the id and taking it modulo the number of nodes, so the same
id always lands on the same node ("stickiness").
"""

from . import registry


def pick_node(blob_id: str) -> dict | None:
    """Return the node responsible for this blob id, or None if no nodes exist."""
    nodes = registry.all_nodes()
    if not nodes:
        return None

    index = hash(blob_id) % len(nodes)
    return nodes[index]
