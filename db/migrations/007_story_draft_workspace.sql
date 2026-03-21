ALTER TABLE stories
    ADD COLUMN draft_headline VARCHAR(255) DEFAULT NULL AFTER summary,
    ADD COLUMN draft_dek TEXT DEFAULT NULL AFTER draft_headline,
    ADD COLUMN draft_body MEDIUMTEXT DEFAULT NULL AFTER draft_dek,
    ADD COLUMN draft_updated_at DATETIME DEFAULT NULL AFTER draft_body;
