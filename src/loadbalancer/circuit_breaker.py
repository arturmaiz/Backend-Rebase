"""Per-node circuit breaker (assignment optional feature).

Counts consecutive destination timeouts. After NODE_MAX_FAILURES the node is
"burned": every request that would route to it fails fast with 503. After
BURNED_NODE_COOLDOWN_SECONDS the breaker resets from scratch — there is no
half-open trial call; the node is simply trusted again.
"""

import logging
import time

from .config import BURNED_NODE_COOLDOWN_SECONDS, NODE_MAX_FAILURES


logger = logging.getLogger("lb.circuit_breaker")


class CircuitBreaker:
    def __init__(
        self,
        node_id: str,
        *,
        max_failures: int = NODE_MAX_FAILURES,
        cooldown_seconds: float = BURNED_NODE_COOLDOWN_SECONDS,
        clock=time.monotonic,
    ) -> None:
        self.node_id = node_id
        self._max_failures = max_failures
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock

        self._failure_count = 0
        self._burned_at: float | None = None

    @property
    def failure_count(self) -> int:
        self._expire_cooldown()
        return self._failure_count

    def is_burned(self) -> bool:
        """True while the node must fail fast. Expires the cooldown lazily."""
        self._expire_cooldown()
        return self._burned_at is not None

    def record_success(self) -> None:
        self._expire_cooldown()

        if self._failure_count:
            logger.info(
                "node=%s recovered, failure count reset from %d to 0",
                self.node_id,
                self._failure_count,
            )

        self._failure_count = 0

    def record_failure(self) -> None:
        """Record one consecutive timeout. Burns the node at the threshold."""
        self._expire_cooldown()

        # A burned node should not be called at all, so nothing left to count.
        if self._burned_at is not None:
            return

        self._failure_count += 1
        logger.warning(
            "node=%s failure count = %d/%d",
            self.node_id,
            self._failure_count,
            self._max_failures,
        )

        if self._failure_count >= self._max_failures:
            self._burned_at = self._clock()
            logger.error(
                "node=%s is burned after %d consecutive failures, "
                "cooling down for %.0fs",
                self.node_id,
                self._failure_count,
                self._cooldown_seconds,
            )

    def _expire_cooldown(self) -> None:
        if self._burned_at is None:
            return

        if self._clock() - self._burned_at < self._cooldown_seconds:
            return

        logger.info(
            "node=%s cooldown elapsed, breaker reset to available",
            self.node_id,
        )
        self._burned_at = None
        self._failure_count = 0
