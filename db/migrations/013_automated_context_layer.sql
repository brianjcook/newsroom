ALTER TABLE sources
    ADD COLUMN automation_mode VARCHAR(32) NOT NULL DEFAULT 'auto_publish' AFTER parser_key,
    ADD COLUMN authority_tier VARCHAR(32) NOT NULL DEFAULT 'official' AFTER automation_mode,
    ADD COLUMN privacy_risk VARCHAR(32) NOT NULL DEFAULT 'low' AFTER authority_tier,
    ADD COLUMN context_enabled TINYINT(1) NOT NULL DEFAULT 1 AFTER privacy_risk,
    ADD COLUMN auto_publish_allowed TINYINT(1) NOT NULL DEFAULT 1 AFTER context_enabled,
    ADD COLUMN attribution_note VARCHAR(255) DEFAULT NULL AFTER auto_publish_allowed;

CREATE TABLE IF NOT EXISTS context_entities (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    municipality_id BIGINT UNSIGNED DEFAULT NULL,
    entity_type VARCHAR(64) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    normalized_key VARCHAR(191) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    meta_json JSON DEFAULT NULL,
    first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_context_entities_type_key (entity_type, normalized_key),
    KEY idx_context_entities_municipality (municipality_id),
    CONSTRAINT fk_context_entities_municipality
        FOREIGN KEY (municipality_id) REFERENCES municipalities (id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS source_observations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_item_id BIGINT UNSIGNED NOT NULL,
    document_id BIGINT UNSIGNED DEFAULT NULL,
    entity_id BIGINT UNSIGNED DEFAULT NULL,
    observation_type VARCHAR(80) NOT NULL,
    observation_label VARCHAR(255) NOT NULL,
    observation_value TEXT DEFAULT NULL,
    observation_json JSON DEFAULT NULL,
    observed_at DATETIME DEFAULT NULL,
    source_url VARCHAR(512) NOT NULL,
    confidence_score DECIMAL(5,2) DEFAULT NULL,
    is_public_context TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_source_observation (
        source_item_id,
        entity_id,
        observation_type(32),
        observation_label(48),
        source_url(64)
    ),
    KEY idx_source_observations_entity (entity_id),
    KEY idx_source_observations_type (observation_type),
    KEY idx_source_observations_public (is_public_context),
    CONSTRAINT fk_source_observations_source_item
        FOREIGN KEY (source_item_id) REFERENCES source_items (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_source_observations_document
        FOREIGN KEY (document_id) REFERENCES documents (id)
        ON DELETE SET NULL,
    CONSTRAINT fk_source_observations_entity
        FOREIGN KEY (entity_id) REFERENCES context_entities (id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS story_context_links (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    story_id BIGINT UNSIGNED NOT NULL,
    entity_id BIGINT UNSIGNED NOT NULL,
    relevance_score INT NOT NULL DEFAULT 0,
    context_reason VARCHAR(255) DEFAULT NULL,
    source_basis_json JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_story_context_entity (story_id, entity_id),
    KEY idx_story_context_entity (entity_id),
    KEY idx_story_context_score (relevance_score),
    CONSTRAINT fk_story_context_story
        FOREIGN KEY (story_id) REFERENCES stories (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_story_context_entity
        FOREIGN KEY (entity_id) REFERENCES context_entities (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

UPDATE sources
SET automation_mode = 'auto_publish',
    authority_tier = 'official',
    privacy_risk = 'low',
    context_enabled = 1,
    auto_publish_allowed = 1,
    attribution_note = 'Official Town of Wareham agenda and minutes records.'
WHERE slug = 'wareham-agenda-center';

UPDATE sources
SET automation_mode = 'guarded_context',
    authority_tier = 'official',
    privacy_risk = 'high',
    context_enabled = 1,
    auto_publish_allowed = 0,
    attribution_note = 'Official public-safety logs; never auto-publish individual-log stories.'
WHERE slug = 'wareham-police-logs';

UPDATE sources
SET automation_mode = 'context_only',
    authority_tier = 'specialized',
    privacy_risk = 'low',
    context_enabled = 1,
    auto_publish_allowed = 0,
    attribution_note = 'Outside environmental context source; use for attribution and context only.'
WHERE slug = 'buzzards-bay-coalition-news';

UPDATE sources
SET automation_mode = 'calendar_sync',
    authority_tier = 'community',
    privacy_risk = 'low',
    context_enabled = 1,
    auto_publish_allowed = 1,
    attribution_note = 'Community event listings synced into the public calendar.'
WHERE slug = 'discover-wareham-events';

INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    automation_mode,
    authority_tier,
    privacy_risk,
    context_enabled,
    auto_publish_allowed,
    attribution_note,
    poll_frequency,
    is_active
)
SELECT
    'Wareham Permit Report Archive',
    'wareham-permit-report-archive',
    'official_documents',
    'https://www.wareham.gov',
    'https://www.wareham.gov/Archive.aspx?AMID=63',
    'wareham_permit_report_archive',
    'context_only',
    'official',
    'low',
    1,
    0,
    'Official monthly permit reports; enrich land-use stories but do not auto-publish standalone stories.',
    'daily',
    1
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE slug = 'wareham-permit-report-archive');

INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    automation_mode,
    authority_tier,
    privacy_risk,
    context_enabled,
    auto_publish_allowed,
    attribution_note,
    poll_frequency,
    is_active
)
SELECT
    'Wareham Town Meeting Documents',
    'wareham-town-meeting-documents',
    'official_documents',
    'https://www.wareham.gov',
    'https://www.wareham.gov/351/Town-Meeting-Information',
    'wareham_town_meeting_documents',
    'context_only',
    'official',
    'low',
    1,
    0,
    'Official Town Meeting warrants, reports, capital plans, and minutes for context.',
    'daily',
    1
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE slug = 'wareham-town-meeting-documents');

INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    automation_mode,
    authority_tier,
    privacy_risk,
    context_enabled,
    auto_publish_allowed,
    attribution_note,
    poll_frequency,
    is_active
)
SELECT
    'Wareham Bids and RFPs',
    'wareham-bids-rfps',
    'official_documents',
    'https://www.wareham.gov',
    'https://www.wareham.gov/bids.aspx',
    'wareham_bids_rfps',
    'context_only',
    'official',
    'low',
    1,
    0,
    'Official procurement postings; enrich budget, infrastructure, and contract stories.',
    'daily',
    1
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE slug = 'wareham-bids-rfps');

INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    automation_mode,
    authority_tier,
    privacy_risk,
    context_enabled,
    auto_publish_allowed,
    attribution_note,
    poll_frequency,
    is_active
)
SELECT
    'Wareham Assessor Reference',
    'wareham-assessor-reference',
    'official_reference',
    'https://gis.vgsi.com/warehamma/',
    'https://gis.vgsi.com/warehamma/',
    'wareham_assessor_reference',
    'context_reference',
    'official',
    'low',
    1,
    0,
    'Official assessor reference used for generated parcel and property-record links.',
    'weekly',
    1
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE slug = 'wareham-assessor-reference');
