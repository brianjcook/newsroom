ALTER TABLE generation_runs
    ADD COLUMN stories_updated INT NOT NULL DEFAULT 0 AFTER stories_published,
    ADD COLUMN events_updated INT NOT NULL DEFAULT 0 AFTER events_created;
