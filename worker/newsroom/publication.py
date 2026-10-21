"""Fail-closed publication decisions shared by scheduled newsroom tasks.

This is conservative triage, not a legal determination. Publisher decisions are
bound to the exact stored revision and survive every subsequent worker run.
"""
import re

REVISION_FIELDS = (
    'headline', 'dek', 'summary', 'body_html', 'body_text', 'source_basis_json',
    'public_label', 'byline_name', 'byline_title', 'story_type', 'slug',
    'topic_tags_json', 'display_date', 'sort_date',
)


def revision_hash_sql(alias=''):
    alias = alias or 'stories'
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', alias):
        raise ValueError('Invalid story alias')
    fields = ','.join("COALESCE({}.{},'')".format(alias, name) for name in REVISION_FIELDS)
    citation_fields = ','.join("COALESCE(sc.{},'')".format(name) for name in (
        'citation_number', 'label', 'source_url', 'quote_text', 'note_text',
    ))
    citation_hashes = (
        "COALESCE((SELECT GROUP_CONCAT(SHA2(CONCAT_WS(CHAR(31),{}),256) "
        "ORDER BY sc.citation_number SEPARATOR '') FROM story_citations sc "
        "WHERE sc.story_id={}.id),'')"
    ).format(citation_fields, alias)
    return (
        "IF((SELECT COUNT(*)*64 FROM story_citations sc WHERE sc.story_id={0}.id)"
        ">@@session.group_concat_max_len,NULL,SHA2(CONCAT_WS(CHAR(31),{1},{2}),256))"
    ).format(alias, fields, citation_hashes)


PUBLICATION_REVIEW_SCHEMA = """
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def ensure_publication_schema(connection):
    with connection.cursor() as cursor:
        cursor.execute(PUBLICATION_REVIEW_SCHEMA)
        cursor.execute("SHOW COLUMNS FROM publication_reviews LIKE 'decision_version'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE publication_reviews ADD COLUMN decision_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER state")


SENSITIVE_PATTERNS = (
    ('allegations or misconduct', r'\b(?:alleg(?:ed|edly|ation|ations)|misconduct|fraud|corrupt(?:ion)?|embezzl\w*|harass\w*|discriminat\w*|abuse|assault|sexual|violations?|disciplinary|discipline|termination)\b'),
    ('crime or police proceedings', r'\b(?:arrest\w*|criminal|crime|charged|charges|suspect|defendant|victim|indict\w*|prosecut\w*|convict\w*|homicide|murder|police\s+(?:log|investigation))\b'),
    ('litigation or private personnel matters', r'\b(?:litigation|lawsuit|legal\s+claim|settlement|executive\s+session|personnel\s+(?:matter|issue|complaint|hearing)|disciplinary\s+hearing)\b'),
    ('minors or private personal information', r'\b(?:minor\s+child|juvenile|child\s+(?:abuse|custody|welfare)|student\s+(?:discipline|disciplinary|records?|privacy)|medical\s+(?:records?|condition)|social\s+security|date\s+of\s+birth|domestic\s+violence)\b|\b\d{3}-\d{2}-\d{4}\b'),
    ('election advocacy or endorsements', r'\b(?:endorse(?:ment|ments)?|vote\s+for\s+[A-Z][a-z]+|campaign\s+donation)\b'),
)


def sensitive_reasons(*texts):
    text = ' '.join(str(value or '') for value in texts)
    return [reason for reason, pattern in SENSITIVE_PATTERNS if re.search(pattern, text, re.IGNORECASE)]


def _normalized_text(value):
    return ' '.join(str(value or '').split())


def material_revision_changed(existing, candidate, previous_basis, next_basis):
    # Render-version changes alone must not revoke a valid publisher decision.
    for key in ('headline', 'dek', 'summary'):
        if _normalized_text(existing.get(key)) != _normalized_text(candidate.get(key)):
            return True
    old_html = re.sub(r'<p class="story-update">.*?</p>', '', str(existing.get('body_html') or ''), flags=re.DOTALL)
    if _normalized_text(old_html) != _normalized_text(candidate.get('body_html')):
        return True
    for key in ('source_item_id', 'extraction_id', 'source_url', 'artifact_type', 'artifact_posted_at', 'is_amended'):
        if previous_basis.get(key) != next_basis.get(key):
            return True
    return False


def publication_decision(existing, review, material_change, reasons):
    """Return preserve, hold, or publish. No approval is inferred from a source."""
    if existing and existing.get('publish_status') != 'published':
        return 'preserve', 'Existing unpublished story requires a publisher action.'
    if review:
        if review.get('state') in ('hold', 'withdrawn'):
            return 'preserve', review.get('reason') or 'Publisher review remains in force.'
        if review.get('state') != 'approved':
            return 'hold', 'Unrecognized review state requires publisher review.'
        actual_hash = existing.get('revision_hash') if existing else None
        if not actual_hash or review.get('approved_hash') != actual_hash:
            return 'hold', 'The stored story has changed since publisher approval.'
        if material_change:
            return 'hold', 'Content or source changed after publisher approval.'
        return 'preserve', 'Approved revision is unchanged; preserve it exactly.'
    if reasons:
        return 'hold', '; '.join(reasons)
    return 'publish', ''


def hold_story(connection, story_id, reason):
    """Caller locks the story first; record the exact stored revision in SQL."""
    with connection.cursor() as cursor:
        cursor.execute("UPDATE stories SET publish_status = 'draft' WHERE id = %s", (story_id,))
        cursor.execute(
            "INSERT INTO publication_reviews (story_id,state,revision_hash,approved_hash,reason) "
            "SELECT id,'hold',COALESCE(" + revision_hash_sql() + ",REPEAT('0',64)),NULL,%s FROM stories WHERE id=%s "
            "ON DUPLICATE KEY UPDATE state='hold',decision_version=decision_version+1,revision_hash=VALUES(revision_hash),approved_hash=NULL,reason=VALUES(reason),updated_at=NOW()",
            (reason, story_id),
        )
