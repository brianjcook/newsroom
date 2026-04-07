CREATE TABLE IF NOT EXISTS source_leads (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_item_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(191) DEFAULT NULL,
    lead_type VARCHAR(64) NOT NULL DEFAULT 'source_lead',
    workflow_status VARCHAR(32) NOT NULL DEFAULT 'monitor',
    priority VARCHAR(32) NOT NULL DEFAULT 'normal',
    editorial_score INT NOT NULL DEFAULT 0,
    editorial_signals_json JSON DEFAULT NULL,
    notes MEDIUMTEXT DEFAULT NULL,
    reported_angle VARCHAR(255) DEFAULT NULL,
    draft_headline VARCHAR(255) DEFAULT NULL,
    draft_dek TEXT DEFAULT NULL,
    draft_body MEDIUMTEXT DEFAULT NULL,
    questions_to_answer MEDIUMTEXT DEFAULT NULL,
    fact_check_notes MEDIUMTEXT DEFAULT NULL,
    next_steps_notes MEDIUMTEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_source_leads_source_item (source_item_id),
    KEY idx_source_leads_workflow (workflow_status),
    KEY idx_source_leads_priority (priority),
    CONSTRAINT fk_source_leads_source_item
        FOREIGN KEY (source_item_id) REFERENCES source_items (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
