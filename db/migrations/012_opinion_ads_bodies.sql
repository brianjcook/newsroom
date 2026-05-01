ALTER TABLE source_leads
    ADD COLUMN promoted_story_id BIGINT UNSIGNED DEFAULT NULL AFTER next_steps_notes,
    ADD KEY idx_source_leads_promoted_story (promoted_story_id),
    ADD CONSTRAINT fk_source_leads_promoted_story
        FOREIGN KEY (promoted_story_id) REFERENCES stories (id)
        ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS ad_slots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    slug VARCHAR(80) NOT NULL,
    label VARCHAR(128) NOT NULL,
    description VARCHAR(255) DEFAULT NULL,
    placement VARCHAR(80) NOT NULL DEFAULT 'site',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_ad_slots_slug (slug),
    KEY idx_ad_slots_placement (placement)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ad_campaigns (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    slot_id BIGINT UNSIGNED NOT NULL,
    advertiser_name VARCHAR(255) NOT NULL,
    headline VARCHAR(255) NOT NULL,
    body_text TEXT DEFAULT NULL,
    destination_url VARCHAR(1024) DEFAULT NULL,
    label VARCHAR(64) NOT NULL DEFAULT 'Advertisement',
    starts_at DATETIME DEFAULT NULL,
    ends_at DATETIME DEFAULT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    notes MEDIUMTEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_ad_campaigns_slot_status (slot_id, status),
    KEY idx_ad_campaigns_dates (starts_at, ends_at),
    CONSTRAINT fk_ad_campaigns_slot
        FOREIGN KEY (slot_id) REFERENCES ad_slots (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO ad_slots (slug, label, description, placement)
SELECT 'homepage-sponsor-strip', 'Homepage Sponsor Strip', 'Thin sponsorship unit below the masthead on the homepage.', 'homepage'
WHERE NOT EXISTS (SELECT 1 FROM ad_slots WHERE slug = 'homepage-sponsor-strip');

INSERT INTO ad_slots (slug, label, description, placement)
SELECT 'homepage-rail', 'Homepage Rail', 'Small local sponsor unit in the front-page rail.', 'homepage'
WHERE NOT EXISTS (SELECT 1 FROM ad_slots WHERE slug = 'homepage-rail');

INSERT INTO ad_slots (slug, label, description, placement)
SELECT 'story-rail', 'Story Rail', 'Right-rail sponsor unit on article pages.', 'story'
WHERE NOT EXISTS (SELECT 1 FROM ad_slots WHERE slug = 'story-rail');

INSERT INTO ad_slots (slug, label, description, placement)
SELECT 'story-inline', 'Story Inline', 'Inline article sponsor unit between story sections.', 'story'
WHERE NOT EXISTS (SELECT 1 FROM ad_slots WHERE slug = 'story-inline');

INSERT INTO ad_slots (slug, label, description, placement)
SELECT 'calendar-top', 'Calendar Top', 'Sponsor unit above the public calendar.', 'calendar'
WHERE NOT EXISTS (SELECT 1 FROM ad_slots WHERE slug = 'calendar-top');

INSERT INTO ad_slots (slug, label, description, placement)
SELECT 'topic-sponsor', 'Topic Sponsor', 'Topic-page sponsor unit for beat or topic coverage.', 'topic'
WHERE NOT EXISTS (SELECT 1 FROM ad_slots WHERE slug = 'topic-sponsor');
