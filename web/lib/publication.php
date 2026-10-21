<?php

declare(strict_types=1);

require_once __DIR__ . '/db.php';

/** Shared with worker/newsroom/publication.py. Do not change the hash independently. */
function newsroom_publication_revision_sql(string $alias = 's'): string
{
    if (!preg_match('/^[a-z][a-z0-9_]*$/i', $alias)) {
        throw new InvalidArgumentException('Invalid story alias.');
    }
    $fields = ['headline', 'dek', 'summary', 'body_html', 'body_text', 'source_basis_json',
        'public_label', 'byline_name', 'byline_title', 'story_type', 'slug', 'topic_tags_json', 'display_date', 'sort_date'];
    $citationHash = '(SELECT GROUP_CONCAT(SHA2(CONCAT_WS(CHAR(31), COALESCE(sc.citation_number, ""),
        COALESCE(sc.label, ""), COALESCE(sc.source_url, ""), COALESCE(sc.quote_text, ""), COALESCE(sc.note_text, "")), 256)
        ORDER BY sc.citation_number SEPARATOR "") FROM story_citations sc WHERE sc.story_id = ' . $alias . '.id)';
    $count = '(SELECT COUNT(*) * 64 FROM story_citations sc WHERE sc.story_id = ' . $alias . '.id)';
    return 'IF(' . $count . ' > @@session.group_concat_max_len, NULL, SHA2(CONCAT_WS(CHAR(31), '
        . implode(', ', array_map(static fn(string $field): string => 'COALESCE(' . $alias . '.' . $field . ', "")', $fields))
        . ', COALESCE(' . $citationHash . ', "")), 256))';
}

function newsroom_publication_schema(): void
{
    static $ready = false;
    if ($ready) {
        return;
    }
    $db = newsroom_db();
    try {
        $db->query('SELECT story_id, decision_version FROM publication_reviews LIMIT 0');
    } catch (PDOException $exception) {
        if (($exception->errorInfo[0] ?? '') === '42S22') {
            try { $db->exec('ALTER TABLE publication_reviews ADD COLUMN decision_version BIGINT UNSIGNED NOT NULL DEFAULT 1'); }
            catch (PDOException $alterError) { if ((int) ($alterError->errorInfo[1] ?? 0) !== 1060) { throw $alterError; } }
            $ready = true;
            return;
        }
        if (($exception->errorInfo[0] ?? '') !== '42S02') {
            throw $exception;
        }
        $db->exec('CREATE TABLE IF NOT EXISTS publication_reviews (
            story_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
            state VARCHAR(32) NOT NULL,
            revision_hash CHAR(64) NOT NULL,
            approved_hash CHAR(64) DEFAULT NULL,
            reason TEXT,
            decision_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_publication_reviews_story FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci');
    }
    $ready = true;
}

function newsroom_publication_audit_schema(): void
{
    newsroom_publication_schema();
    newsroom_db()->exec('CREATE TABLE IF NOT EXISTS publication_review_events (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        story_id BIGINT UNSIGNED NOT NULL,
        action VARCHAR(32) NOT NULL,
        revision_hash CHAR(64) NOT NULL,
        reason TEXT,
        actor VARCHAR(128) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY idx_publication_review_events_story (story_id, id),
        CONSTRAINT fk_publication_review_events_story FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci');
}

/** Fail closed if policy storage cannot be read. Used by every public story query. */
function newsroom_publication_visibility_sql(string $alias = 's'): string
{
    $hash = newsroom_publication_revision_sql($alias);
    try {
        newsroom_publication_schema();
    } catch (Throwable $exception) {
        error_log('Newsroom publication policy unavailable.');
        return '0 = 1';
    }
    return 'NOT EXISTS (SELECT 1 FROM publication_reviews pvr WHERE pvr.story_id = ' . $alias . '.id
        AND (pvr.state <> "approved" OR pvr.approved_hash IS NULL OR ' . $hash . ' IS NULL OR pvr.approved_hash <> ' . $hash . '))';
}

/** Calendar summaries must not expose claims from a held meeting story. */
function newsroom_publication_meeting_visibility_sql(string $meetingExpression): string
{
    if (!preg_match('/^[a-z][a-z0-9_]*\.meeting_id$/i', $meetingExpression)) {
        throw new InvalidArgumentException('Invalid meeting expression.');
    }
    return 'NOT EXISTS (SELECT 1 FROM stories pms WHERE pms.meeting_id = ' . $meetingExpression . '
        AND NOT (' . newsroom_publication_visibility_sql('pms') . '))';
}

function newsroom_publication_decide(int $storyId, string $action, string $expectedHash, string $reason, ?int $expectedVersion = null): void
{
    if (!in_array($action, ['hold', 'withdraw', 'approve'], true) || $storyId <= 0) {
        throw new RuntimeException('Choose a valid publication decision.');
    }
    $reason = trim($reason);
    if ($action !== 'approve' && $reason === '') {
        throw new RuntimeException('Please provide a reason for this decision.');
    }
    if (!preg_match('/^[a-f0-9]{64}$/', $expectedHash)) {
        throw new RuntimeException('Reload the story before making a decision.');
    }
    newsroom_publication_audit_schema();
    $db = newsroom_db();
    $db->exec('SET TRANSACTION ISOLATION LEVEL READ COMMITTED');
    $db->beginTransaction();
    try {
        $statement = $db->prepare('SELECT s.*, ' . newsroom_publication_revision_sql('s') . ' AS revision_hash
            FROM stories s WHERE s.id = :id FOR UPDATE');
        $statement->execute([':id' => $storyId]);
        $story = $statement->fetch();
        if (!$story || !hash_equals((string) ($story['revision_hash'] ?? str_repeat('0', 64)), $expectedHash)) {
            throw new RuntimeException('This story changed. Reload and review the current version before deciding.');
        }
        $reviewLock = $db->prepare('SELECT decision_version FROM publication_reviews WHERE story_id = :id FOR UPDATE');
        $reviewLock->execute([':id' => $storyId]);
        $currentVersion = (int) ($reviewLock->fetchColumn() ?: 0);
        if ($expectedVersion !== null && $expectedVersion !== $currentVersion) {
            throw new RuntimeException('A newer publisher decision exists. Reload before making another decision.');
        }
        if ($action === 'approve' && empty($story['revision_hash'])) {
            throw new RuntimeException('The source list is too large to verify this revision safely. Keep this story on hold.');
        }
        if ($action === 'approve' && (trim((string) $story['headline']) === '' || trim(strip_tags((string) $story['body_html'])) === '')) {
            throw new RuntimeException('A headline and story body are required before publication.');
        }
        $state = ['hold' => 'hold', 'withdraw' => 'withdrawn', 'approve' => 'approved'][$action];
        $reason = $reason !== '' ? $reason : 'Publisher approved this exact revision.';
        $statement = $db->prepare('INSERT INTO publication_reviews
            (story_id, state, revision_hash, approved_hash, reason) VALUES (:id, :state, :hash, :approved, :reason)
            ON DUPLICATE KEY UPDATE state = VALUES(state), revision_hash = VALUES(revision_hash),
                approved_hash = VALUES(approved_hash), reason = VALUES(reason), decision_version = decision_version + 1, updated_at = CURRENT_TIMESTAMP');
        $statement->execute([':id' => $storyId, ':state' => $state, ':hash' => $expectedHash,
            ':approved' => $action === 'approve' ? $expectedHash : null, ':reason' => $reason]);
        $status = ['hold' => 'draft', 'withdraw' => 'suppressed', 'approve' => 'published'][$action];
        $statement = $db->prepare('UPDATE stories SET publish_status = :status,
            published_at = CASE WHEN :is_approval = 1 THEN COALESCE(published_at, NOW()) ELSE published_at END WHERE id = :id');
        $statement->execute([':status' => $status, ':is_approval' => $action === 'approve' ? 1 : 0, ':id' => $storyId]);
        $statement = $db->prepare('INSERT INTO publication_review_events (story_id, action, revision_hash, reason, actor)
            VALUES (:id, :action, :hash, :reason, :actor)');
        $statement->execute([':id' => $storyId, ':action' => $action, ':hash' => $expectedHash,
            ':reason' => $reason, ':actor' => (string) newsroom_env('NEWSROOM_EDITORIAL_USER', 'publisher')]);
        $db->commit();
    } catch (Throwable $exception) {
        if ($db->inTransaction()) {
            $db->rollBack();
        }
        throw $exception;
    }
}

function newsroom_publication_require_publisher(): void
{
    $auth = newsroom_config()['editorial_auth'];
    if (empty($auth['user']) || empty($auth['password'])) {
        http_response_code(503);
        exit('Publisher access is not configured.');
    }
    newsroom_require_editorial_login();
    newsroom_start_session();
    header('Cache-Control: private, no-store, max-age=0');
    header('X-Robots-Tag: noindex, nofollow');
}

/** Show the actual HTML text without executing markup, styles or external media. */
function newsroom_publication_preview_html(string $html): string
{
    if (!class_exists('DOMDocument')) { return '<pre>' . htmlspecialchars($html, ENT_QUOTES, 'UTF-8') . '</pre>'; }
    $document = new DOMDocument();
    $previous = libxml_use_internal_errors(true);
    $document->loadHTML('<?xml encoding="UTF-8"><div>' . $html . '</div>', LIBXML_NONET);
    libxml_clear_errors();
    libxml_use_internal_errors($previous);
    $allowed = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'br', 'hr', 'a', 'sup'];
    $render = static function (DOMNode $node) use (&$render, $allowed): string {
        if ($node instanceof DOMText) {
            return htmlspecialchars($node->textContent, ENT_QUOTES, 'UTF-8');
        }
        $tag = strtolower($node->nodeName);
        if (in_array($tag, ['script', 'style', 'iframe', 'object', 'embed', 'img', 'svg'], true)) {
            return '';
        }
        $children = '';
        foreach ($node->childNodes as $child) { $children .= $render($child); }
        if (!in_array($tag, $allowed, true)) { return $children; }
        if (in_array($tag, ['br', 'hr'], true)) { return '<' . $tag . '>'; }
        return '<' . $tag . '>' . $children . '</' . $tag . '>';
    };
    return $render($document);
}

/** Metadata assembled after approval is not part of the reviewed revision. */
function newsroom_publication_reviewed_story(array $row): array
{
    $id = (int) ($row['id'] ?? 0);
    if ($id <= 0) { return $row; }
    static $reviews = [];
    if (!array_key_exists($id, $reviews)) {
        newsroom_publication_schema();
        $query = newsroom_db()->prepare('SELECT story_id FROM publication_reviews WHERE story_id = :id');
        $query->execute([':id' => $id]);
        $reviews[$id] = (bool) $query->fetch();
    }
    if ($reviews[$id]) {
        foreach (['meeting_date', 'meeting_time', 'location_name', 'body_name', 'artifact_structured_json', 'agenda_source_meta_json', 'agenda_url', 'minutes_url'] as $field) {
            $row[$field] = null;
        }
    }
    return $row;
}
