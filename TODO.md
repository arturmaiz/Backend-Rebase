# TODO / Deferred Design Work

Tracked gaps in the blob storage design (`src/routes/blobs.py`). Ordered by the
numbering used in the design discussion.

## Current assumptions

These are deliberate scope choices for now, not oversights:

- No concurrent requests for the **same** blob id.
- No slow / trickled uploads (so no read timeouts or connection caps yet).

## #1 — In-memory count / size counters

Track total blob count and total bytes as in-memory counters, seeded once at
`warmup()` and updated under `_storage_lock`, instead of re-running
`_scan_storage()` on every POST. Today the scan is O(number-of-blobs) and runs
*inside* the lock, so every write is serialized behind a full directory scan
(with `MAX_BLOBS_TOTAL = 1_000_000` that is up to a million `stat()` calls).

## #2 — Shard blobs into subdirectories (later, not urgent)

Blobs currently live flat under `blobs/`. Shard into subdirectories
(`config.MAX_BLOBS_IN_FOLDER`) so a single directory never holds ~1M entries,
which most filesystems handle poorly. Ties into #1.

## #3 — fsync for power-loss durability

Optionally `fsync` the staged data file before the rename and the parent
directory after, for durability against power loss / kernel crash. Process
crashes are already handled by the staging + atomic-rename design. Cost is
roughly +0.5–2 ms/POST on SSD/NVMe, ~+10–20 ms on spinning disk (GET is
unaffected). Leave as a documented trade-off unless power-loss durability is
required.

## #4 / #5 — Quota accounting and resource limits (out of scope for now)

- Quota (`_scan_storage`) counts only committed `blobs/{id}/data`; transient
  space in `.staging` and `.backups` is intentionally ignored, so real disk use
  can briefly exceed `MAX_DISK_QUOTA` (e.g. ~2x a blob's size during overwrite).
- No request timeouts or concurrency cap (slowloris / FD / disk exhaustion).
  Covered by the "no trickled uploads" assumption above.

## #7 — GET consistency (later)

`get_blob` reads outside `_storage_lock`, so a concurrent DELETE or overwrite
can remove the directory between the `exists()` check and streaming, yielding a
500. Also guard `json.loads` against corrupt metadata.
