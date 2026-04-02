ALTER TABLE follow_up_items
    ADD COLUMN draft_headline VARCHAR(255) DEFAULT NULL AFTER notes,
    ADD COLUMN draft_dek TEXT DEFAULT NULL AFTER draft_headline,
    ADD COLUMN reported_angle VARCHAR(255) DEFAULT NULL AFTER draft_dek,
    ADD COLUMN questions_to_answer MEDIUMTEXT DEFAULT NULL AFTER reported_angle,
    ADD COLUMN fact_check_notes MEDIUMTEXT DEFAULT NULL AFTER questions_to_answer,
    ADD COLUMN next_steps_notes MEDIUMTEXT DEFAULT NULL AFTER fact_check_notes;

CREATE TABLE IF NOT EXISTS follow_up_sources (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    follow_up_id BIGINT UNSIGNED NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'official',
    title VARCHAR(255) DEFAULT NULL,
    source_url VARCHAR(1024) DEFAULT NULL,
    publisher VARCHAR(255) DEFAULT NULL,
    priority VARCHAR(32) NOT NULL DEFAULT 'supporting',
    notes MEDIUMTEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_follow_up_sources_follow_up (follow_up_id),
    CONSTRAINT fk_follow_up_sources_follow_up
        FOREIGN KEY (follow_up_id) REFERENCES follow_up_items (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS follow_up_contacts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    follow_up_id BIGINT UNSIGNED NOT NULL,
    full_name VARCHAR(255) DEFAULT NULL,
    role_title VARCHAR(255) DEFAULT NULL,
    organization VARCHAR(255) DEFAULT NULL,
    email VARCHAR(255) DEFAULT NULL,
    outreach_status VARCHAR(32) NOT NULL DEFAULT 'not_started',
    quote_status VARCHAR(32) NOT NULL DEFAULT 'not_requested',
    quote_text MEDIUMTEXT DEFAULT NULL,
    notes MEDIUMTEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_follow_up_contacts_follow_up (follow_up_id),
    KEY idx_follow_up_contacts_outreach (outreach_status),
    CONSTRAINT fk_follow_up_contacts_follow_up
        FOREIGN KEY (follow_up_id) REFERENCES follow_up_items (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
