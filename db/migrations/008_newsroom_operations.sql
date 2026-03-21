ALTER TABLE stories
    ADD COLUMN public_label VARCHAR(64) DEFAULT NULL AFTER story_type,
    ADD COLUMN byline_name VARCHAR(128) DEFAULT NULL AFTER public_label,
    ADD COLUMN byline_title VARCHAR(128) DEFAULT NULL AFTER byline_name,
    ADD COLUMN live_prep_notes MEDIUMTEXT DEFAULT NULL AFTER draft_updated_at;

ALTER TABLE community_events
    ADD COLUMN public_label VARCHAR(64) DEFAULT NULL AFTER source_type,
    ADD COLUMN byline_name VARCHAR(128) DEFAULT NULL AFTER public_label,
    ADD COLUMN byline_title VARCHAR(128) DEFAULT NULL AFTER byline_name,
    ADD COLUMN event_tier VARCHAR(32) DEFAULT NULL AFTER suggested_coverage_mode,
    ADD COLUMN live_prep_notes MEDIUMTEXT DEFAULT NULL AFTER updated_at;

CREATE TABLE IF NOT EXISTS follow_up_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_story_id BIGINT UNSIGNED NOT NULL,
    source_story_slug VARCHAR(191) DEFAULT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(191) DEFAULT NULL,
    topic_tags_json JSON DEFAULT NULL,
    workflow_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    priority VARCHAR(32) NOT NULL DEFAULT 'normal',
    due_at DATETIME DEFAULT NULL,
    notes MEDIUMTEXT DEFAULT NULL,
    draft_body MEDIUMTEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_follow_up_source_story (source_story_id),
    KEY idx_follow_up_workflow (workflow_status),
    KEY idx_follow_up_priority (priority),
    CONSTRAINT fk_follow_up_source_story
        FOREIGN KEY (source_story_id) REFERENCES stories (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
