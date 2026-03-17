CREATE TABLE IF NOT EXISTS municipalities (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    state_code CHAR(2) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    website_url VARCHAR(512) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_municipalities_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO municipalities (name, state_code, slug, website_url)
VALUES ('Wareham', 'MA', 'wareham-ma', 'https://www.wareham.gov')
ON DUPLICATE KEY UPDATE
    website_url = VALUES(website_url);

CREATE TABLE IF NOT EXISTS governing_bodies (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    municipality_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    body_type VARCHAR(64) DEFAULT NULL,
    slug VARCHAR(160) NOT NULL,
    source_page_url VARCHAR(512) DEFAULT NULL,
    agenda_center_name VARCHAR(255) DEFAULT NULL,
    description TEXT,
    meeting_schedule_text TEXT,
    meeting_location_text TEXT,
    contact_email VARCHAR(255) DEFAULT NULL,
    contact_phone VARCHAR(64) DEFAULT NULL,
    address_text TEXT,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_governing_bodies_slug (slug),
    KEY idx_governing_bodies_municipality (municipality_id),
    CONSTRAINT fk_governing_bodies_municipality
        FOREIGN KEY (municipality_id) REFERENCES municipalities(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS people (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) DEFAULT NULL,
    person_type VARCHAR(64) DEFAULT NULL,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_people_name_email (full_name, email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS body_roles (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    governing_body_id BIGINT UNSIGNED NOT NULL,
    person_id BIGINT UNSIGNED NOT NULL,
    role_title VARCHAR(255) NOT NULL,
    role_class VARCHAR(64) DEFAULT NULL,
    term_end_date DATE DEFAULT NULL,
    is_current TINYINT(1) NOT NULL DEFAULT 1,
    source_url VARCHAR(512) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_body_roles_current (governing_body_id, person_id, role_title, is_current),
    CONSTRAINT fk_body_roles_governing_body
        FOREIGN KEY (governing_body_id) REFERENCES governing_bodies(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_body_roles_person
        FOREIGN KEY (person_id) REFERENCES people(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE meetings
    ADD COLUMN governing_body_id BIGINT UNSIGNED NULL AFTER source_item_id,
    ADD COLUMN title VARCHAR(255) DEFAULT NULL AFTER governing_body,
    ADD COLUMN normalized_title VARCHAR(255) DEFAULT NULL AFTER title;

ALTER TABLE meetings
    ADD KEY idx_meetings_governing_body (governing_body_id),
    ADD CONSTRAINT fk_meetings_governing_body
        FOREIGN KEY (governing_body_id) REFERENCES governing_bodies(id)
        ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS meeting_artifacts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    meeting_id BIGINT UNSIGNED NOT NULL,
    source_item_id BIGINT UNSIGNED DEFAULT NULL,
    document_id BIGINT UNSIGNED DEFAULT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    format VARCHAR(32) DEFAULT NULL,
    title VARCHAR(255) DEFAULT NULL,
    source_url VARCHAR(512) NOT NULL,
    posted_at DATETIME DEFAULT NULL,
    version_label VARCHAR(128) DEFAULT NULL,
    is_primary TINYINT(1) NOT NULL DEFAULT 0,
    is_amended TINYINT(1) NOT NULL DEFAULT 0,
    storage_path VARCHAR(512) DEFAULT NULL,
    mime_type VARCHAR(128) DEFAULT NULL,
    sha256 CHAR(64) DEFAULT NULL,
    extraction_status VARCHAR(32) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_meeting_artifacts_source (meeting_id, source_url(191)),
    KEY idx_meeting_artifacts_meeting (meeting_id),
    CONSTRAINT fk_meeting_artifacts_meeting
        FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_meeting_artifacts_source_item
        FOREIGN KEY (source_item_id) REFERENCES source_items(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_meeting_artifacts_document
        FOREIGN KEY (document_id) REFERENCES documents(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE stories
    ADD COLUMN governing_body_id BIGINT UNSIGNED NULL AFTER meeting_id,
    ADD COLUMN display_date DATETIME DEFAULT NULL AFTER published_at,
    ADD COLUMN sort_date DATETIME DEFAULT NULL AFTER display_date;

ALTER TABLE stories
    ADD KEY idx_stories_sort_date (sort_date),
    ADD CONSTRAINT fk_stories_governing_body
        FOREIGN KEY (governing_body_id) REFERENCES governing_bodies(id)
        ON DELETE SET NULL;

ALTER TABLE calendar_events
    ADD COLUMN governing_body_id BIGINT UNSIGNED NULL AFTER meeting_id,
    ADD KEY idx_calendar_events_governing_body (governing_body_id),
    ADD CONSTRAINT fk_calendar_events_governing_body
        FOREIGN KEY (governing_body_id) REFERENCES governing_bodies(id)
        ON DELETE SET NULL;
