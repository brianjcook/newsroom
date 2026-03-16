CREATE TABLE IF NOT EXISTS sources (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    base_url VARCHAR(512) NOT NULL,
    list_url VARCHAR(512) NOT NULL,
    parser_key VARCHAR(128) NOT NULL,
    poll_frequency VARCHAR(32) NOT NULL DEFAULT 'daily',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_sources_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS source_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_id BIGINT UNSIGNED NOT NULL,
    external_id VARCHAR(191) DEFAULT NULL,
    canonical_url VARCHAR(512) NOT NULL,
    title VARCHAR(512) DEFAULT NULL,
    item_type VARCHAR(64) NOT NULL,
    published_at DATETIME DEFAULT NULL,
    first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    content_hash CHAR(64) DEFAULT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'discovered',
    raw_meta_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_source_items_source_url (source_id, canonical_url(191)),
    KEY idx_source_items_status (status),
    CONSTRAINT fk_source_items_source
        FOREIGN KEY (source_id) REFERENCES sources(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_item_id BIGINT UNSIGNED NOT NULL,
    document_url VARCHAR(512) NOT NULL,
    document_type VARCHAR(64) NOT NULL,
    mime_type VARCHAR(128) DEFAULT NULL,
    storage_path VARCHAR(512) NOT NULL,
    sha256 CHAR(64) DEFAULT NULL,
    fetched_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    http_status INT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_documents_item_url (source_item_id, document_url(191)),
    CONSTRAINT fk_documents_source_item
        FOREIGN KEY (source_item_id) REFERENCES source_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS document_extractions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    document_id BIGINT UNSIGNED NOT NULL,
    extractor_version VARCHAR(64) NOT NULL,
    title VARCHAR(512) DEFAULT NULL,
    body_text MEDIUMTEXT,
    structured_json JSON DEFAULT NULL,
    confidence_score DECIMAL(5,2) DEFAULT NULL,
    warnings_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_document_extractions_document (document_id),
    CONSTRAINT fk_document_extractions_document
        FOREIGN KEY (document_id) REFERENCES documents(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meetings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_item_id BIGINT UNSIGNED NOT NULL,
    governing_body VARCHAR(255) DEFAULT NULL,
    meeting_type VARCHAR(100) DEFAULT NULL,
    meeting_date DATE DEFAULT NULL,
    meeting_time TIME DEFAULT NULL,
    location_name VARCHAR(255) DEFAULT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    agenda_posted_at DATETIME DEFAULT NULL,
    minutes_posted_at DATETIME DEFAULT NULL,
    meeting_key VARCHAR(191) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_meetings_meeting_key (meeting_key),
    KEY idx_meetings_date (meeting_date),
    CONSTRAINT fk_meetings_source_item
        FOREIGN KEY (source_item_id) REFERENCES source_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    meeting_id BIGINT UNSIGNED DEFAULT NULL,
    story_type VARCHAR(64) NOT NULL,
    slug VARCHAR(191) NOT NULL,
    headline VARCHAR(255) NOT NULL,
    dek VARCHAR(512) DEFAULT NULL,
    summary TEXT,
    body_html MEDIUMTEXT NOT NULL,
    body_text MEDIUMTEXT,
    tone_profile VARCHAR(64) NOT NULL DEFAULT 'straight_civic',
    publish_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    published_at DATETIME DEFAULT NULL,
    source_basis_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_stories_slug (slug),
    KEY idx_stories_publish_status (publish_status),
    KEY idx_stories_published_at (published_at),
    CONSTRAINT fk_stories_meeting
        FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS story_citations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    story_id BIGINT UNSIGNED NOT NULL,
    citation_number INT NOT NULL,
    label VARCHAR(255) DEFAULT NULL,
    source_url VARCHAR(512) NOT NULL,
    document_id BIGINT UNSIGNED DEFAULT NULL,
    quote_text TEXT,
    note_text TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_story_citations_number (story_id, citation_number),
    CONSTRAINT fk_story_citations_story
        FOREIGN KEY (story_id) REFERENCES stories(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_story_citations_document
        FOREIGN KEY (document_id) REFERENCES documents(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS calendar_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    meeting_id BIGINT UNSIGNED DEFAULT NULL,
    title VARCHAR(255) NOT NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME DEFAULT NULL,
    location_name VARCHAR(255) DEFAULT NULL,
    body_name VARCHAR(255) DEFAULT NULL,
    source_url VARCHAR(512) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_calendar_events_starts_at (starts_at),
    CONSTRAINT fk_calendar_events_meeting
        FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS generation_runs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME DEFAULT NULL,
    run_status VARCHAR(32) NOT NULL DEFAULT 'running',
    items_discovered INT NOT NULL DEFAULT 0,
    stories_published INT NOT NULL DEFAULT 0,
    events_created INT NOT NULL DEFAULT 0,
    warnings_json JSON DEFAULT NULL,
    errors_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_generation_runs_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
