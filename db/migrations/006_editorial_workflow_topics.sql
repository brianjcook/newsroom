ALTER TABLE stories
    ADD COLUMN workflow_status VARCHAR(32) NOT NULL DEFAULT 'published' AFTER admin_notes,
    ADD COLUMN watch_live TINYINT(1) NOT NULL DEFAULT 0 AFTER workflow_status,
    ADD COLUMN follow_up_needed TINYINT(1) NOT NULL DEFAULT 0 AFTER watch_live,
    ADD COLUMN topic_tags_json JSON DEFAULT NULL AFTER follow_up_needed;

ALTER TABLE community_events
    ADD COLUMN workflow_status VARCHAR(32) NOT NULL DEFAULT 'watch' AFTER admin_notes,
    ADD COLUMN watch_live TINYINT(1) NOT NULL DEFAULT 0 AFTER workflow_status,
    ADD COLUMN follow_up_needed TINYINT(1) NOT NULL DEFAULT 0 AFTER watch_live,
    ADD COLUMN topic_tags_json JSON DEFAULT NULL AFTER follow_up_needed;
