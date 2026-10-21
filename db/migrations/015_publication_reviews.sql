CREATE TABLE IF NOT EXISTS publication_reviews (
    story_id BIGINT UNSIGNED NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'hold',
    decision_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    revision_hash CHAR(64) NOT NULL,
    approved_hash CHAR(64) DEFAULT NULL,
    reason TEXT DEFAULT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (story_id),
    KEY idx_publication_reviews_state (state),
    CONSTRAINT fk_publication_reviews_story FOREIGN KEY (story_id)
        REFERENCES stories (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
