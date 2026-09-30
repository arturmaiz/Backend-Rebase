-- The single table this service owns: one row per "bucket".
--
-- A bucket is the view-count for ONE page during ONE round hour, so the natural
-- identity of a row is the pair (page, hour) -- that pair is the primary key.
--
-- page  : which page the views belong to (e.g. altman.html). Part of the key.
-- hour  : the bucket's hour, minutes/seconds zeroed, stored in UTC. Carrying the
--         full date+hour (not just 0-23) is what lets us tell today's 21:00 from
--         yesterday's 21:00, run the "last 24 hours" report, and clean old rows.
--         Part of the key.
-- count : how many views landed in this bucket. BIGINT so a busy page can never
--         overflow the counter. NOT NULL DEFAULT 0 so a bucket always holds a
--         real number, never NULL.
--
-- The composite PRIMARY KEY (page, hour) does three jobs at once: it guarantees
-- one row per bucket, it builds the index we look buckets up by, and it is the
-- UNIQUE constraint that INSERT ... ON CONFLICT (page, hour) needs so a concurrent
-- increment can safely add to an existing bucket instead of creating a duplicate.
CREATE TABLE IF NOT EXISTS page_views (
    page  VARCHAR(200) NOT NULL,
    hour  TIMESTAMPTZ  NOT NULL,
    count BIGINT       NOT NULL DEFAULT 0,
    PRIMARY KEY (page, hour)
);
