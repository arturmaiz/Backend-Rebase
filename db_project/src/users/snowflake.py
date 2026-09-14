"""A tiny Snowflake ID generator.

A Snowflake ID is a single 64-bit, time-ordered integer, laid out like this:

    | 1 bit  | 41 bits          | 10 bits     | 12 bits    |
    | unused | ms since epoch   | machine id  | sequence   |

- unused sign bit : kept 0 so the value is always a positive signed bigint.
- 41-bit timestamp: milliseconds since a custom epoch (~69 years of range).
- 10-bit machine id: which node/process minted it (0..1023).
- 12-bit sequence : counter for ids minted in the SAME millisecond (0..4095).

Because the timestamp sits in the high bits, sorting the integers sorts users
by (roughly) creation time -- something random UUIDs cannot give you, and the
reason new ids always land at the right edge of the primary-key index.
"""

import threading
import time


# Custom epoch: 2024-01-01T00:00:00Z, in milliseconds. Anchoring the epoch near
# "now" maximizes how far into the future the 41-bit timestamp can reach.
DEFAULT_EPOCH_MS = 1_704_067_200_000

MACHINE_ID_BITS = 10
SEQUENCE_BITS = 12

MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1  # 1023
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1  # 4095

# How far left to shift each field so it lands in its slot of the 64-bit layout.
MACHINE_ID_SHIFT = SEQUENCE_BITS  # 12
TIMESTAMP_SHIFT = SEQUENCE_BITS + MACHINE_ID_BITS  # 22


class SnowflakeGenerator:
    """Mints monotonically increasing 64-bit ids for a single machine id."""

    def __init__(self, machine_id: int = 0, epoch_ms: int = DEFAULT_EPOCH_MS):
        if not 0 <= machine_id <= MAX_MACHINE_ID:
            raise ValueError(f"machine_id must be between 0 and {MAX_MACHINE_ID}")
        self.machine_id = machine_id
        self.epoch_ms = epoch_ms
        self._lock = threading.Lock()
        self._last_ms = -1
        self._sequence = 0

    def next_id(self) -> int:
        """Return the next unique, time-ordered id.

        The lock makes a single generator safe to share across threads: only one
        caller at a time can read/advance the (_last_ms, _sequence) pair.
        """
        with self._lock:
            now = self._current_ms()

            if now < self._last_ms:
                # The wall clock jumped backwards (e.g. NTP correction). Minting
                # now could reuse a (ms, sequence) pair from the future, so refuse.
                raise RuntimeError(
                    f"clock moved backwards by {self._last_ms - now} ms; "
                    "refusing to generate id"
                )

            if now == self._last_ms:
                # Same millisecond as the last id: bump the sequence. The & wraps
                # 4095 -> 0, which signals we have exhausted this millisecond.
                self._sequence = (self._sequence + 1) & MAX_SEQUENCE
                if self._sequence == 0:
                    now = self._wait_next_ms(self._last_ms)
            else:
                # A fresh millisecond: restart the per-ms counter.
                self._sequence = 0

            self._last_ms = now
            return (
                ((now - self.epoch_ms) << TIMESTAMP_SHIFT)
                | (self.machine_id << MACHINE_ID_SHIFT)
                | self._sequence
            )

    @staticmethod
    def _current_ms() -> int:
        return time.time_ns() // 1_000_000

    def _wait_next_ms(self, last_ms: int) -> int:
        """Spin until the clock advances past last_ms (we burned 4096 ids in 1ms)."""
        now = self._current_ms()
        while now <= last_ms:
            now = self._current_ms()
        return now
