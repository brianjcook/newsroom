ALTER TABLE generation_runs
    ADD COLUMN documents_fetched INT NOT NULL DEFAULT 0 AFTER items_discovered,
    ADD COLUMN extractions_created INT NOT NULL DEFAULT 0 AFTER documents_fetched,
    ADD COLUMN meetings_normalized INT NOT NULL DEFAULT 0 AFTER extractions_created;
